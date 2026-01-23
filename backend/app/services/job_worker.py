"""Background worker base class for processing queued jobs.

Provides a generic worker pattern that polls for jobs using JobQueueService
and processes them with heartbeat monitoring and graceful shutdown support.
"""
import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Generic, TypeVar

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import get_settings
from app.services.job_queue_service import HEARTBEAT_INTERVAL, JobQueueService

logger = logging.getLogger(__name__)
settings = get_settings()

T = TypeVar("T")


class JobWorker(ABC, Generic[T]):
    """Base class for job workers.

    Subclasses implement process_job() for job-specific processing logic.
    The worker handles:
    - Polling for pending jobs
    - Heartbeat updates during processing
    - Graceful shutdown
    - Stale job sweeping

    Type Parameters:
        T: The job model type (e.g., ArenaSimulation, Live20Run)

    Attributes:
        session_factory: Factory for creating database sessions
        queue_service: JobQueueService instance for queue operations
        poll_interval: Seconds to wait between polling when no jobs found
    """

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        queue_service: JobQueueService[T],
        poll_interval: float = 5.0,
    ) -> None:
        """Initialize the job worker.

        Args:
            session_factory: Factory for creating async database sessions
            queue_service: JobQueueService for queue operations
            poll_interval: Seconds to wait between polls when idle (default: 5.0)
        """
        self.session_factory = session_factory
        self.queue_service = queue_service
        self.poll_interval = poll_interval
        self._running = False
        self._current_job_id: int | None = None
        self._sweeper_task: asyncio.Task | None = None

    @abstractmethod
    async def process_job(self, job: T) -> None:
        """Process a single job.

        Subclasses must implement this method with job-specific processing logic.
        The implementation should:
        - Support resume from partial completion
        - Check for cancellation periodically using queue_service.is_cancelled()
        - Handle errors gracefully (let them propagate for retry handling)

        Args:
            job: The job instance to process

        Raises:
            Any exception will cause the job to be marked as failed with retry
        """
        pass

    async def start(self) -> None:
        """Start the worker loop.

        Begins polling for jobs and processing them. Also starts a background
        sweeper task to detect and reset stale jobs.
        """
        self._running = True
        logger.info(f"[{self.queue_service.worker_id}] Worker starting")

        # Start sweeper task
        self._sweeper_task = asyncio.create_task(self._sweeper_loop())

        while self._running:
            try:
                job = await self.queue_service.claim_next_job()

                if job:
                    self._current_job_id = job.id
                    logger.info(
                        f"[{self.queue_service.worker_id}] Processing job {job.id}"
                    )

                    # Start heartbeat task
                    heartbeat_task = asyncio.create_task(self._heartbeat_loop(job.id))

                    try:
                        await self.process_job(job)
                        await self.queue_service.mark_completed(job.id)
                        logger.info(
                            f"[{self.queue_service.worker_id}] Job {job.id} completed"
                        )
                    except Exception as e:
                        logger.error(
                            f"[{self.queue_service.worker_id}] Job {job.id} failed: {e}",
                            exc_info=True,
                        )
                        await self.queue_service.mark_failed(job.id, str(e))
                    finally:
                        heartbeat_task.cancel()
                        try:
                            await heartbeat_task
                        except asyncio.CancelledError:
                            pass
                        self._current_job_id = None
                else:
                    # No pending jobs, wait before polling again
                    await asyncio.sleep(self.poll_interval)

            except asyncio.CancelledError:
                # Worker is being stopped, exit loop
                logger.info(
                    f"[{self.queue_service.worker_id}] Worker loop cancelled"
                )
                break
            except Exception as e:
                logger.error(
                    f"[{self.queue_service.worker_id}] Worker loop error: {e}",
                    exc_info=True,
                )
                await asyncio.sleep(self.poll_interval)

    async def stop(self) -> None:
        """Stop the worker loop gracefully.

        Signals the worker to stop and waits for the current job to complete
        (up to 30 seconds). Also cancels the sweeper task.
        """
        self._running = False
        logger.info(f"[{self.queue_service.worker_id}] Worker stopping")

        # Cancel sweeper task
        if self._sweeper_task:
            self._sweeper_task.cancel()
            try:
                await self._sweeper_task
            except asyncio.CancelledError:
                pass

        # Wait for current job to finish (graceful shutdown)
        if self._current_job_id:
            logger.info(
                f"[{self.queue_service.worker_id}] Waiting for job "
                f"{self._current_job_id} to complete..."
            )
            # Give it up to configured seconds to finish current iteration
            for _ in range(settings.worker_shutdown_iterations):
                if self._current_job_id is None:
                    break
                await asyncio.sleep(settings.worker_shutdown_sleep)

        logger.info(f"[{self.queue_service.worker_id}] Worker stopped")

    async def _heartbeat_loop(self, job_id: int) -> None:
        """Send periodic heartbeats while processing a job.

        Runs as a background task during job processing to update
        the heartbeat_at timestamp, preventing the sweeper from
        marking the job as stale.

        Args:
            job_id: The database ID of the job being processed
        """
        while True:
            await asyncio.sleep(HEARTBEAT_INTERVAL)
            try:
                await self.queue_service.update_heartbeat(job_id)
                logger.debug(
                    f"[{self.queue_service.worker_id}] Heartbeat sent for job {job_id}"
                )
            except Exception as e:
                logger.error(
                    f"[{self.queue_service.worker_id}] Heartbeat failed for "
                    f"job {job_id}: {e}"
                )

    async def _sweeper_loop(self) -> None:
        """Periodically check for and reset stale jobs.

        Runs at configured interval to detect jobs that have stopped
        sending heartbeats and reset them for retry.
        """
        while self._running:
            try:
                await asyncio.sleep(settings.worker_sweeper_interval)
                reset_count = await self.queue_service.reset_stale_jobs()
                if reset_count > 0:
                    logger.info(
                        f"[{self.queue_service.worker_id}] Sweeper reset "
                        f"{reset_count} stale jobs"
                    )
            except asyncio.CancelledError:
                # Sweeper is being stopped
                break
            except Exception as e:
                logger.error(
                    f"[{self.queue_service.worker_id}] Sweeper error: {e}",
                    exc_info=True,
                )
