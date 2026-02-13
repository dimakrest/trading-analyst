"""Tests for generic job queue service.

Tests the JobQueueService with Live20Run as the concrete model.
The service is generic and works with any model that has the required queue columns.
"""
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.models.live20_run import Live20Run
from app.services.job_queue_service import (
    JobQueueService,
    HEARTBEAT_INTERVAL,
    STALE_JOB_THRESHOLD,
)


async def create_live20_run(
    session_factory,
    status: str = "pending",
    retry_count: int = 0,
    max_retries: int = 3,
    heartbeat_at: datetime | None = None,
    worker_id: str | None = None,
    last_error: str | None = None,
) -> Live20Run:
    """Helper to create a Live20Run for testing."""
    async with session_factory() as session:
        run = Live20Run(
            status=status,
            symbol_count=5,
            long_count=0,
            short_count=0,
            no_setup_count=0,
            input_symbols=["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA"],
            retry_count=retry_count,
            max_retries=max_retries,
            heartbeat_at=heartbeat_at,
            worker_id=worker_id,
            last_error=last_error,
        )
        session.add(run)
        await session.commit()
        await session.refresh(run)
        return run


async def get_run_by_id(session_factory, run_id: int) -> Live20Run | None:
    """Helper to get a Live20Run by ID."""
    async with session_factory() as session:
        result = await session.execute(
            select(Live20Run).where(Live20Run.id == run_id)
        )
        return result.scalar_one_or_none()


@pytest.mark.unit
class TestJobQueueServiceInitialization:
    """Tests for JobQueueService initialization."""

    def test_init_with_custom_worker_id(self, rollback_session_factory):
        """Should use provided worker ID."""
        service = JobQueueService(
            rollback_session_factory, Live20Run, worker_id="custom-worker-123"
        )
        assert service.worker_id == "custom-worker-123"

    def test_init_generates_worker_id(self, rollback_session_factory):
        """Should generate unique worker ID with default 'worker' prefix if not provided."""
        service = JobQueueService(rollback_session_factory, Live20Run)
        assert service.worker_id.startswith("worker-")
        assert len(service.worker_id) == len("worker-") + 8

    def test_init_with_worker_type(self, rollback_session_factory):
        """Should generate worker ID with custom type prefix."""
        service = JobQueueService(
            rollback_session_factory, Live20Run, worker_type="live20"
        )
        assert service.worker_id.startswith("live20-")
        assert len(service.worker_id) == len("live20-") + 8

    def test_init_worker_id_takes_precedence_over_worker_type(self, rollback_session_factory):
        """Should use explicit worker_id even if worker_type is also provided."""
        service = JobQueueService(
            rollback_session_factory,
            Live20Run,
            worker_id="explicit-id",
            worker_type="live20",
        )
        assert service.worker_id == "explicit-id"

    def test_init_stores_model_class(self, rollback_session_factory):
        """Should store the model class for queries."""
        service = JobQueueService(rollback_session_factory, Live20Run)
        assert service.model_class == Live20Run


@pytest.mark.unit
class TestClaimNextJob:
    """Tests for claim_next_job method."""

    @pytest.mark.asyncio
    async def test_claim_next_job_returns_none_when_empty(
        self, rollback_session_factory):
        """Should return None when no pending jobs exist."""
        service = JobQueueService(rollback_session_factory, Live20Run)

        result = await service.claim_next_job()

        assert result is None

    @pytest.mark.asyncio
    async def test_claim_next_job_returns_pending_job(
        self, rollback_session_factory):
        """Should return and claim a pending job."""
        run = await create_live20_run(rollback_session_factory, status="pending")
        service = JobQueueService(rollback_session_factory, Live20Run)

        claimed = await service.claim_next_job()

        assert claimed is not None
        assert claimed.id == run.id

    @pytest.mark.asyncio
    async def test_claim_next_job_updates_status_to_running(
        self, rollback_session_factory):
        """Should update job status to running when claimed."""
        run = await create_live20_run(rollback_session_factory, status="pending")
        service = JobQueueService(rollback_session_factory, Live20Run)

        await service.claim_next_job()

        updated = await get_run_by_id(rollback_session_factory, run.id)
        assert updated.status == "running"

    @pytest.mark.asyncio
    async def test_claim_next_job_sets_worker_id(
        self, rollback_session_factory):
        """Should set worker_id when claiming job."""
        run = await create_live20_run(rollback_session_factory, status="pending")
        service = JobQueueService(
            rollback_session_factory, Live20Run, worker_id="test-worker"
        )

        await service.claim_next_job()

        updated = await get_run_by_id(rollback_session_factory, run.id)
        assert updated.worker_id == "test-worker"

    @pytest.mark.asyncio
    async def test_claim_next_job_sets_claimed_at_and_heartbeat(
        self, rollback_session_factory):
        """Should set claimed_at and heartbeat_at timestamps."""
        run = await create_live20_run(rollback_session_factory, status="pending")
        service = JobQueueService(rollback_session_factory, Live20Run)

        before = datetime.now(timezone.utc)
        await service.claim_next_job()
        after = datetime.now(timezone.utc)

        updated = await get_run_by_id(rollback_session_factory, run.id)
        assert updated.claimed_at is not None
        assert updated.heartbeat_at is not None
        assert before <= updated.claimed_at <= after
        assert before <= updated.heartbeat_at <= after

    @pytest.mark.asyncio
    async def test_claim_next_job_respects_fifo_order(
        self, rollback_session_factory):
        """Should claim jobs in FIFO order (oldest first)."""
        run1 = await create_live20_run(rollback_session_factory, status="pending")
        run2 = await create_live20_run(rollback_session_factory, status="pending")
        run3 = await create_live20_run(rollback_session_factory, status="pending")

        service = JobQueueService(rollback_session_factory, Live20Run)

        claimed1 = await service.claim_next_job()
        claimed2 = await service.claim_next_job()
        claimed3 = await service.claim_next_job()

        assert claimed1.id == run1.id
        assert claimed2.id == run2.id
        assert claimed3.id == run3.id

    @pytest.mark.asyncio
    async def test_claim_next_job_skips_non_pending(
        self, rollback_session_factory):
        """Should only claim pending jobs, skipping running/completed/failed."""
        await create_live20_run(rollback_session_factory, status="running")
        await create_live20_run(rollback_session_factory, status="completed")
        await create_live20_run(rollback_session_factory, status="failed")
        pending_run = await create_live20_run(rollback_session_factory, status="pending")

        service = JobQueueService(rollback_session_factory, Live20Run)

        claimed = await service.claim_next_job()

        assert claimed is not None
        assert claimed.id == pending_run.id


@pytest.mark.unit
class TestIsCancelled:
    """Tests for is_cancelled method."""

    @pytest.mark.asyncio
    async def test_is_cancelled_returns_true_for_cancelled(
        self, rollback_session_factory):
        """Should return True when job status is cancelled."""
        run = await create_live20_run(rollback_session_factory, status="cancelled")
        service = JobQueueService(rollback_session_factory, Live20Run)

        result = await service.is_cancelled(run.id)

        assert result is True

    @pytest.mark.asyncio
    async def test_is_cancelled_returns_false_for_running(
        self, rollback_session_factory):
        """Should return False when job status is running."""
        run = await create_live20_run(rollback_session_factory, status="running")
        service = JobQueueService(rollback_session_factory, Live20Run)

        result = await service.is_cancelled(run.id)

        assert result is False

    @pytest.mark.asyncio
    async def test_is_cancelled_returns_false_for_pending(
        self, rollback_session_factory):
        """Should return False when job status is pending."""
        run = await create_live20_run(rollback_session_factory, status="pending")
        service = JobQueueService(rollback_session_factory, Live20Run)

        result = await service.is_cancelled(run.id)

        assert result is False

    @pytest.mark.asyncio
    async def test_is_cancelled_returns_false_for_completed(
        self, rollback_session_factory):
        """Should return False when job status is completed."""
        run = await create_live20_run(rollback_session_factory, status="completed")
        service = JobQueueService(rollback_session_factory, Live20Run)

        result = await service.is_cancelled(run.id)

        assert result is False

    @pytest.mark.asyncio
    async def test_is_cancelled_returns_false_for_nonexistent(
        self, rollback_session_factory):
        """Should return False for nonexistent job (no status found)."""
        service = JobQueueService(rollback_session_factory, Live20Run)

        result = await service.is_cancelled(999999)

        assert result is False


@pytest.mark.unit
class TestResetStrandedJobs:
    """Tests for reset_stranded_jobs method."""

    @pytest.mark.asyncio
    async def test_reset_stranded_jobs_resets_running_to_pending(
        self, rollback_session_factory):
        """Should reset all running jobs to pending."""
        run1 = await create_live20_run(rollback_session_factory, status="running")
        run2 = await create_live20_run(rollback_session_factory, status="running")

        service = JobQueueService(rollback_session_factory, Live20Run)
        count = await service.reset_stranded_jobs()

        assert count == 2

        updated1 = await get_run_by_id(rollback_session_factory, run1.id)
        updated2 = await get_run_by_id(rollback_session_factory, run2.id)

        assert updated1.status == "pending"
        assert updated2.status == "pending"

    @pytest.mark.asyncio
    async def test_reset_stranded_jobs_clears_worker_info(
        self, rollback_session_factory):
        """Should clear worker_id and claimed_at."""
        run = await create_live20_run(
            rollback_session_factory,
            status="running",
            worker_id="old-worker",
        )

        service = JobQueueService(rollback_session_factory, Live20Run)
        await service.reset_stranded_jobs()

        updated = await get_run_by_id(rollback_session_factory, run.id)
        assert updated.worker_id is None
        assert updated.claimed_at is None

    @pytest.mark.asyncio
    async def test_reset_stranded_jobs_does_not_increment_retry_count(
        self, rollback_session_factory):
        """Should NOT increment retry_count (server restart is not failure)."""
        run = await create_live20_run(
            rollback_session_factory, status="running", retry_count=1
        )

        service = JobQueueService(rollback_session_factory, Live20Run)
        await service.reset_stranded_jobs()

        updated = await get_run_by_id(rollback_session_factory, run.id)
        assert updated.retry_count == 1  # Unchanged!

    @pytest.mark.asyncio
    async def test_reset_stranded_jobs_sets_last_error_message(
        self, rollback_session_factory):
        """Should set informative last_error message."""
        run = await create_live20_run(rollback_session_factory, status="running")

        service = JobQueueService(rollback_session_factory, Live20Run)
        await service.reset_stranded_jobs()

        updated = await get_run_by_id(rollback_session_factory, run.id)
        assert "Server restarted" in updated.last_error

    @pytest.mark.asyncio
    async def test_reset_stranded_jobs_ignores_pending(
        self, rollback_session_factory):
        """Should not affect pending jobs."""
        run = await create_live20_run(rollback_session_factory, status="pending")

        service = JobQueueService(rollback_session_factory, Live20Run)
        count = await service.reset_stranded_jobs()

        assert count == 0

        updated = await get_run_by_id(rollback_session_factory, run.id)
        assert updated.status == "pending"

    @pytest.mark.asyncio
    async def test_reset_stranded_jobs_ignores_completed(
        self, rollback_session_factory):
        """Should not affect completed jobs."""
        run = await create_live20_run(rollback_session_factory, status="completed")

        service = JobQueueService(rollback_session_factory, Live20Run)
        count = await service.reset_stranded_jobs()

        assert count == 0

        updated = await get_run_by_id(rollback_session_factory, run.id)
        assert updated.status == "completed"

    @pytest.mark.asyncio
    async def test_reset_stranded_jobs_returns_zero_when_none(
        self, rollback_session_factory):
        """Should return 0 when no running jobs exist."""
        await create_live20_run(rollback_session_factory, status="pending")
        await create_live20_run(rollback_session_factory, status="completed")

        service = JobQueueService(rollback_session_factory, Live20Run)
        count = await service.reset_stranded_jobs()

        assert count == 0


@pytest.mark.unit
class TestUpdateHeartbeat:
    """Tests for update_heartbeat method."""

    @pytest.mark.asyncio
    async def test_update_heartbeat_updates_timestamp(
        self, rollback_session_factory):
        """Should update heartbeat_at timestamp."""
        old_time = datetime.now(timezone.utc) - timedelta(minutes=5)
        run = await create_live20_run(
            rollback_session_factory, status="running", heartbeat_at=old_time
        )

        service = JobQueueService(rollback_session_factory, Live20Run)

        before = datetime.now(timezone.utc)
        await service.update_heartbeat(run.id)
        after = datetime.now(timezone.utc)

        updated = await get_run_by_id(rollback_session_factory, run.id)
        assert updated.heartbeat_at >= before
        assert updated.heartbeat_at <= after


@pytest.mark.unit
class TestMarkCompleted:
    """Tests for mark_completed method."""

    @pytest.mark.asyncio
    async def test_mark_completed_updates_status(
        self, rollback_session_factory):
        """Should set status to completed."""
        run = await create_live20_run(rollback_session_factory, status="running")
        service = JobQueueService(rollback_session_factory, Live20Run)

        await service.mark_completed(run.id)

        updated = await get_run_by_id(rollback_session_factory, run.id)
        assert updated.status == "completed"

    @pytest.mark.asyncio
    async def test_mark_completed_updates_heartbeat(
        self, rollback_session_factory):
        """Should update heartbeat_at timestamp."""
        old_time = datetime.now(timezone.utc) - timedelta(minutes=5)
        run = await create_live20_run(
            rollback_session_factory, status="running", heartbeat_at=old_time
        )
        service = JobQueueService(rollback_session_factory, Live20Run)

        before = datetime.now(timezone.utc)
        await service.mark_completed(run.id)
        after = datetime.now(timezone.utc)

        updated = await get_run_by_id(rollback_session_factory, run.id)
        assert updated.heartbeat_at >= before
        assert updated.heartbeat_at <= after

    @pytest.mark.asyncio
    async def test_mark_completed_clears_last_error(
        self, rollback_session_factory):
        """Should clear last_error when job completes successfully.

        This is important for jobs that failed previously but succeeded on retry.
        The final state should not show stale error messages.
        """
        run = await create_live20_run(
            rollback_session_factory,
            status="running",
            last_error="Previous failure: connection timeout",
        )
        service = JobQueueService(rollback_session_factory, Live20Run)

        await service.mark_completed(run.id)

        updated = await get_run_by_id(rollback_session_factory, run.id)
        assert updated.last_error is None


@pytest.mark.unit
class TestMarkFailed:
    """Tests for mark_failed method."""

    @pytest.mark.asyncio
    async def test_mark_failed_increments_retry_count(
        self, rollback_session_factory):
        """Should increment retry_count when retries available."""
        run = await create_live20_run(
            rollback_session_factory, status="running", retry_count=0, max_retries=3
        )
        service = JobQueueService(rollback_session_factory, Live20Run)

        await service.mark_failed(run.id, "Test error")

        updated = await get_run_by_id(rollback_session_factory, run.id)
        assert updated.retry_count == 1

    @pytest.mark.asyncio
    async def test_mark_failed_resets_to_pending_for_retry(
        self, rollback_session_factory):
        """Should reset status to pending when retries available."""
        run = await create_live20_run(
            rollback_session_factory, status="running", retry_count=0, max_retries=3
        )
        service = JobQueueService(rollback_session_factory, Live20Run)

        await service.mark_failed(run.id, "Test error")

        updated = await get_run_by_id(rollback_session_factory, run.id)
        assert updated.status == "pending"

    @pytest.mark.asyncio
    async def test_mark_failed_clears_worker_info_for_retry(
        self, rollback_session_factory):
        """Should clear worker_id and claimed_at for retry."""
        run = await create_live20_run(
            rollback_session_factory,
            status="running",
            worker_id="test-worker",
            retry_count=0,
            max_retries=3,
        )
        service = JobQueueService(rollback_session_factory, Live20Run)

        await service.mark_failed(run.id, "Test error")

        updated = await get_run_by_id(rollback_session_factory, run.id)
        assert updated.worker_id is None
        assert updated.claimed_at is None

    @pytest.mark.asyncio
    async def test_mark_failed_sets_last_error(
        self, rollback_session_factory):
        """Should set last_error message."""
        run = await create_live20_run(rollback_session_factory, status="running")
        service = JobQueueService(rollback_session_factory, Live20Run)

        await service.mark_failed(run.id, "Connection timeout")

        updated = await get_run_by_id(rollback_session_factory, run.id)
        assert updated.last_error == "Connection timeout"

    @pytest.mark.asyncio
    async def test_mark_failed_sets_failed_after_max_retries(
        self, rollback_session_factory):
        """Should set status to failed when max_retries exceeded."""
        run = await create_live20_run(
            rollback_session_factory,
            status="running",
            retry_count=3,  # Already at max
            max_retries=3,
        )
        service = JobQueueService(rollback_session_factory, Live20Run)

        await service.mark_failed(run.id, "Final error")

        updated = await get_run_by_id(rollback_session_factory, run.id)
        assert updated.status == "failed"

    @pytest.mark.asyncio
    async def test_mark_failed_does_not_increment_past_max(
        self, rollback_session_factory):
        """Should not increment retry_count when already at max."""
        run = await create_live20_run(
            rollback_session_factory,
            status="running",
            retry_count=3,
            max_retries=3,
        )
        service = JobQueueService(rollback_session_factory, Live20Run)

        await service.mark_failed(run.id, "Final error")

        updated = await get_run_by_id(rollback_session_factory, run.id)
        assert updated.retry_count == 3  # Unchanged

    @pytest.mark.asyncio
    async def test_mark_failed_handles_nonexistent_job(
        self, rollback_session_factory):
        """Should handle nonexistent job gracefully (no error)."""
        service = JobQueueService(rollback_session_factory, Live20Run)

        # Should not raise
        await service.mark_failed(999999, "Test error")


@pytest.mark.unit
class TestResetStaleJobs:
    """Tests for reset_stale_jobs method."""

    @pytest.mark.asyncio
    async def test_reset_stale_jobs_resets_old_heartbeat(
        self, rollback_session_factory):
        """Should reset jobs with old heartbeat to pending."""
        stale_time = datetime.now(timezone.utc) - timedelta(
            seconds=STALE_JOB_THRESHOLD + 60
        )
        run = await create_live20_run(
            rollback_session_factory,
            status="running",
            heartbeat_at=stale_time,
            worker_id="stuck-worker",
        )

        service = JobQueueService(rollback_session_factory, Live20Run)
        count = await service.reset_stale_jobs()

        assert count == 1

        updated = await get_run_by_id(rollback_session_factory, run.id)
        assert updated.status == "pending"

    @pytest.mark.asyncio
    async def test_reset_stale_jobs_increments_retry_count(
        self, rollback_session_factory):
        """Should increment retry_count for stale jobs."""
        stale_time = datetime.now(timezone.utc) - timedelta(
            seconds=STALE_JOB_THRESHOLD + 60
        )
        run = await create_live20_run(
            rollback_session_factory,
            status="running",
            heartbeat_at=stale_time,
            retry_count=1,
        )

        service = JobQueueService(rollback_session_factory, Live20Run)
        await service.reset_stale_jobs()

        updated = await get_run_by_id(rollback_session_factory, run.id)
        assert updated.retry_count == 2

    @pytest.mark.asyncio
    async def test_reset_stale_jobs_clears_worker_info(
        self, rollback_session_factory):
        """Should clear worker_id and claimed_at."""
        stale_time = datetime.now(timezone.utc) - timedelta(
            seconds=STALE_JOB_THRESHOLD + 60
        )
        run = await create_live20_run(
            rollback_session_factory,
            status="running",
            heartbeat_at=stale_time,
            worker_id="stuck-worker",
        )

        service = JobQueueService(rollback_session_factory, Live20Run)
        await service.reset_stale_jobs()

        updated = await get_run_by_id(rollback_session_factory, run.id)
        assert updated.worker_id is None
        assert updated.claimed_at is None

    @pytest.mark.asyncio
    async def test_reset_stale_jobs_sets_last_error(
        self, rollback_session_factory):
        """Should set informative last_error message."""
        stale_time = datetime.now(timezone.utc) - timedelta(
            seconds=STALE_JOB_THRESHOLD + 60
        )
        run = await create_live20_run(
            rollback_session_factory,
            status="running",
            heartbeat_at=stale_time,
        )

        service = JobQueueService(rollback_session_factory, Live20Run)
        await service.reset_stale_jobs()

        updated = await get_run_by_id(rollback_session_factory, run.id)
        assert "stale" in updated.last_error.lower()
        assert str(STALE_JOB_THRESHOLD) in updated.last_error

    @pytest.mark.asyncio
    async def test_reset_stale_jobs_fails_after_max_retries(
        self, rollback_session_factory):
        """Should set status to failed when max_retries exceeded."""
        stale_time = datetime.now(timezone.utc) - timedelta(
            seconds=STALE_JOB_THRESHOLD + 60
        )
        run = await create_live20_run(
            rollback_session_factory,
            status="running",
            heartbeat_at=stale_time,
            retry_count=3,
            max_retries=3,
        )

        service = JobQueueService(rollback_session_factory, Live20Run)
        count = await service.reset_stale_jobs()

        # Should not count as "reset" since it was marked failed
        assert count == 0

        updated = await get_run_by_id(rollback_session_factory, run.id)
        assert updated.status == "failed"

    @pytest.mark.asyncio
    async def test_reset_stale_jobs_ignores_recent_heartbeat(
        self, rollback_session_factory):
        """Should not reset jobs with recent heartbeat."""
        recent_time = datetime.now(timezone.utc) - timedelta(seconds=30)  # 30s ago
        run = await create_live20_run(
            rollback_session_factory,
            status="running",
            heartbeat_at=recent_time,
        )

        service = JobQueueService(rollback_session_factory, Live20Run)
        count = await service.reset_stale_jobs()

        assert count == 0

        updated = await get_run_by_id(rollback_session_factory, run.id)
        assert updated.status == "running"

    @pytest.mark.asyncio
    async def test_reset_stale_jobs_ignores_pending(
        self, rollback_session_factory):
        """Should not affect pending jobs even with old heartbeat."""
        stale_time = datetime.now(timezone.utc) - timedelta(
            seconds=STALE_JOB_THRESHOLD + 60
        )
        run = await create_live20_run(
            rollback_session_factory,
            status="pending",
            heartbeat_at=stale_time,
        )

        service = JobQueueService(rollback_session_factory, Live20Run)
        count = await service.reset_stale_jobs()

        assert count == 0

        updated = await get_run_by_id(rollback_session_factory, run.id)
        assert updated.status == "pending"

    @pytest.mark.asyncio
    async def test_reset_stale_jobs_returns_count(
        self, rollback_session_factory):
        """Should return count of reset jobs."""
        stale_time = datetime.now(timezone.utc) - timedelta(
            seconds=STALE_JOB_THRESHOLD + 60
        )

        # Create 3 stale jobs with retries available
        await create_live20_run(
            rollback_session_factory,
            status="running",
            heartbeat_at=stale_time,
            retry_count=0,
        )
        await create_live20_run(
            rollback_session_factory,
            status="running",
            heartbeat_at=stale_time,
            retry_count=1,
        )
        await create_live20_run(
            rollback_session_factory,
            status="running",
            heartbeat_at=stale_time,
            retry_count=2,
        )

        service = JobQueueService(rollback_session_factory, Live20Run)
        count = await service.reset_stale_jobs()

        assert count == 3


@pytest.mark.unit
class TestConstantsExported:
    """Tests that constants are properly exported."""

    def test_heartbeat_interval_constant(self):
        """Should export HEARTBEAT_INTERVAL constant."""
        assert HEARTBEAT_INTERVAL == 30

    def test_stale_job_threshold_constant(self):
        """Should export STALE_JOB_THRESHOLD constant."""
        assert STALE_JOB_THRESHOLD == 300
