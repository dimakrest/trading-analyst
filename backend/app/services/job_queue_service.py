"""Generic PostgreSQL-based job queue service.

Provides atomic job claiming using SELECT FOR UPDATE SKIP LOCKED pattern.
Works with any job model that has the required queue columns:
- status, worker_id, claimed_at, heartbeat_at, retry_count, max_retries, last_error
"""
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Generic, TypeVar

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

T = TypeVar("T")  # Job model type

HEARTBEAT_INTERVAL = settings.job_heartbeat_interval
STALE_JOB_THRESHOLD = settings.job_stale_threshold


class JobQueueService(Generic[T]):
    """Generic queue service for PostgreSQL-backed job queues.

    Uses SELECT FOR UPDATE SKIP LOCKED for atomic job claiming.
    Supports heartbeat-based stale job detection and automatic retry.

    Type Parameters:
        T: The job model class (e.g., ArenaSimulation, Live20Run)

    Attributes:
        session_factory: Factory for creating database sessions
        model_class: The SQLAlchemy model class for jobs
        worker_id: Unique identifier for this worker instance
    """

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        model_class: type[T],
        worker_id: str | None = None,
        worker_type: str | None = None,
    ) -> None:
        """Initialize the job queue service.

        Args:
            session_factory: Factory for creating async database sessions
            model_class: The SQLAlchemy model class for jobs
            worker_id: Optional worker ID. If not provided, generates a unique ID.
            worker_type: Optional worker type prefix (e.g., 'arena', 'live20').
                        Used to generate more descriptive worker IDs for debugging.
                        If not provided, defaults to 'worker'.
        """
        self.session_factory = session_factory
        self.model_class = model_class
        if worker_id:
            self.worker_id = worker_id
        else:
            prefix = worker_type or "worker"
            self.worker_id = f"{prefix}-{uuid.uuid4().hex[:8]}"

    async def is_cancelled(self, job_id: int) -> bool:
        """Check if a job has been cancelled.

        Used by workers to check for cancellation between processing iterations.

        Args:
            job_id: The database ID of the job to check

        Returns:
            True if the job status is 'cancelled', False otherwise
        """
        async with self.session_factory() as session:
            result = await session.execute(
                select(self.model_class.status).where(self.model_class.id == job_id)
            )
            status = result.scalar_one_or_none()
            return status == "cancelled"

    async def reset_stranded_jobs(self) -> int:
        """Reset all running jobs to pending on startup.

        Called during application startup for immediate recovery.
        Since this is a local-first single-instance app, any 'running'
        jobs at startup are definitely orphaned from the previous process.

        Note: Does NOT increment retry_count because server restart is not
        considered a job failure - just a process interruption.

        Returns:
            Number of jobs reset.
        """
        async with self.session_factory() as session:
            result = await session.execute(
                select(self.model_class).where(self.model_class.status == "running")
            )
            stranded_jobs = result.scalars().all()

            reset_count = 0
            for job in stranded_jobs:
                job.status = "pending"
                job.worker_id = None
                job.claimed_at = None
                # Don't increment retry_count - server restart is not a job failure
                job.last_error = "Server restarted - job will be resumed"
                reset_count += 1
                logger.info(f"Reset stranded job {job.id} for immediate resume")

            await session.commit()
            return reset_count

    async def claim_next_job(self) -> T | None:
        """Atomically claim the next pending job.

        Uses SELECT FOR UPDATE SKIP LOCKED to ensure only one worker
        can claim a specific job, even under concurrent access.

        Returns:
            The claimed job instance, or None if no pending jobs available.
        """
        async with self.session_factory() as session:
            async with session.begin():
                # Atomic SELECT FOR UPDATE SKIP LOCKED
                result = await session.execute(
                    select(self.model_class)
                    .where(self.model_class.status == "pending")
                    .order_by(self.model_class.created_at)
                    .limit(1)
                    .with_for_update(skip_locked=True)
                )
                job = result.scalar_one_or_none()

                if job:
                    now = datetime.now(timezone.utc)
                    job.status = "running"
                    job.worker_id = self.worker_id
                    job.claimed_at = now
                    job.heartbeat_at = now

                    logger.info(f"Claimed job {job.id} (worker={self.worker_id})")

                return job

    async def update_heartbeat(self, job_id: int) -> None:
        """Update job heartbeat to show it's still being processed.

        Should be called periodically (every HEARTBEAT_INTERVAL seconds)
        by the worker while processing a job.

        Args:
            job_id: The database ID of the job to update
        """
        async with self.session_factory() as session:
            await session.execute(
                update(self.model_class)
                .where(self.model_class.id == job_id)
                .values(heartbeat_at=datetime.now(timezone.utc))
            )
            await session.commit()

    async def mark_completed(self, job_id: int) -> None:
        """Mark a job as completed.

        Args:
            job_id: The database ID of the job to mark as completed
        """
        async with self.session_factory() as session:
            await session.execute(
                update(self.model_class)
                .where(self.model_class.id == job_id)
                .values(
                    status="completed",
                    heartbeat_at=datetime.now(timezone.utc),
                    last_error=None,
                )
            )
            await session.commit()
            logger.info(f"Job {job_id} completed")

    async def mark_failed(self, job_id: int, error: str) -> None:
        """Mark a job as failed with error message.

        If the job has remaining retries (retry_count < max_retries),
        resets the job to 'pending' for automatic retry. Otherwise,
        marks the job as permanently 'failed'.

        Args:
            job_id: The database ID of the job
            error: Error message describing the failure
        """
        async with self.session_factory() as session:
            result = await session.execute(
                select(self.model_class).where(self.model_class.id == job_id)
            )
            job = result.scalar_one_or_none()

            if job:
                job.last_error = error
                if job.retry_count < job.max_retries:
                    # Reset to pending for retry
                    job.status = "pending"
                    job.retry_count += 1
                    job.worker_id = None
                    job.claimed_at = None
                    logger.info(
                        f"Job {job_id} failed, will retry ({job.retry_count}/{job.max_retries})"
                    )
                else:
                    # Max retries exceeded
                    job.status = "failed"
                    logger.error(
                        f"Job {job_id} failed permanently after {job.max_retries} retries: {error}"
                    )

                await session.commit()

    async def reset_stale_jobs(self) -> int:
        """Reset jobs that have gone stale (no heartbeat for too long).

        A job is considered stale if its heartbeat_at timestamp is older
        than STALE_JOB_THRESHOLD seconds. Stale jobs are reset to 'pending'
        for retry (with retry_count increment), or marked as 'failed' if
        max_retries is exceeded.

        Returns:
            Number of jobs reset to pending.
        """
        stale_threshold = datetime.now(timezone.utc) - timedelta(
            seconds=STALE_JOB_THRESHOLD
        )

        async with self.session_factory() as session:
            # Find stale running jobs
            result = await session.execute(
                select(self.model_class)
                .where(self.model_class.status == "running")
                .where(self.model_class.heartbeat_at < stale_threshold)
            )
            stale_jobs = result.scalars().all()

            reset_count = 0
            for job in stale_jobs:
                if job.retry_count < job.max_retries:
                    job.status = "pending"
                    job.retry_count += 1
                    job.worker_id = None
                    job.claimed_at = None
                    job.last_error = (
                        f"Job stale (no heartbeat for {STALE_JOB_THRESHOLD}s)"
                    )
                    reset_count += 1
                    logger.warning(
                        f"Reset stale job {job.id} for retry ({job.retry_count}/{job.max_retries})"
                    )
                else:
                    job.status = "failed"
                    job.last_error = f"Job stale after {job.max_retries} retries"
                    logger.error(
                        f"Job {job.id} failed permanently (stale after max retries)"
                    )

            await session.commit()
            return reset_count
