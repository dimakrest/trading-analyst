"""Integration tests for PostgreSQL job queue crash recovery and retry scenarios.

These tests verify the complete behavior of the job queue system including:
1. Jobs survive server restart simulation (reset_stranded_jobs)
2. Jobs are retried on failure up to max_retries
3. Stale jobs are reset by the sweeper
4. Cancellation detection works correctly

All tests use the actual database (via test fixtures) to verify queue behavior
under realistic conditions.
"""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.models.live20_run import Live20Run
from app.services.job_queue_service import (
    JobQueueService,
    STALE_JOB_THRESHOLD,
)

# Mark all tests in this module as integration tests
pytestmark = pytest.mark.integration


async def create_live20_run(
    session_factory,
    status: str = "pending",
    retry_count: int = 0,
    max_retries: int = 3,
    heartbeat_at: datetime | None = None,
    worker_id: str | None = None,
    processed_count: int = 0,
) -> Live20Run:
    """Helper to create a Live20Run for testing."""
    async with session_factory() as session:
        run = Live20Run(
            status=status,
            symbol_count=5,
            long_count=0,
            no_setup_count=0,
            input_symbols=["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA"],
            retry_count=retry_count,
            max_retries=max_retries,
            heartbeat_at=heartbeat_at,
            worker_id=worker_id,
            processed_count=processed_count,
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


class TestJobSurvivesRestart:
    """Integration tests for job survival after simulated server restart."""

    @pytest.mark.asyncio
    async def test_pending_job_survives_restart(
        self, rollback_session_factory):
        """Test that pending jobs are picked up after simulated restart.

        Scenario:
        1. Create a pending job directly in the database
        2. Call reset_stranded_jobs() (simulating server restart)
        3. Verify job is still pending and ready for pickup
        """
        # Create a pending job
        run = await create_live20_run(rollback_session_factory, status="pending")

        # Simulate server restart by calling reset_stranded_jobs
        service = JobQueueService(rollback_session_factory, Live20Run)
        reset_count = await service.reset_stranded_jobs()

        # No running jobs, so nothing to reset
        assert reset_count == 0

        # Verify job is still pending
        updated_run = await get_run_by_id(rollback_session_factory, run.id)
        assert updated_run.status == "pending"

        # Verify job can be claimed
        claimed = await service.claim_next_job()
        assert claimed is not None
        assert claimed.id == run.id

    @pytest.mark.asyncio
    async def test_running_job_reset_on_restart(
        self, rollback_session_factory):
        """Test that running jobs are reset to pending after server restart.

        Scenario:
        1. Create a running job (simulating a job in progress when server crashed)
        2. Call reset_stranded_jobs() (simulating server restart)
        3. Verify job is reset to pending and ready for pickup
        """
        # Create a running job (simulating a job in progress before crash)
        run = await create_live20_run(
            rollback_session_factory,
            status="running",
            worker_id="old-worker",
            heartbeat_at=datetime.now(timezone.utc),
            processed_count=3,  # Partially completed
        )

        # Simulate server restart
        service = JobQueueService(rollback_session_factory, Live20Run)
        reset_count = await service.reset_stranded_jobs()

        # Should have reset 1 running job
        assert reset_count == 1

        # Verify job is reset to pending
        updated_run = await get_run_by_id(rollback_session_factory, run.id)
        assert updated_run.status == "pending"
        assert updated_run.worker_id is None
        assert updated_run.claimed_at is None
        # Progress should be preserved for resumption
        assert updated_run.processed_count == 3
        # Should have informative error message
        assert "Server restarted" in updated_run.last_error

    @pytest.mark.asyncio
    async def test_restart_does_not_increment_retry_count(
        self, rollback_session_factory):
        """Test that server restart does NOT increment retry_count.

        Server restart is process interruption, not a job failure.
        The job should be able to resume without consuming a retry.
        """
        original_retry_count = 1
        run = await create_live20_run(
            rollback_session_factory,
            status="running",
            retry_count=original_retry_count,
            max_retries=3,
        )

        service = JobQueueService(rollback_session_factory, Live20Run)
        await service.reset_stranded_jobs()

        updated_run = await get_run_by_id(rollback_session_factory, run.id)
        # Retry count should be unchanged
        assert updated_run.retry_count == original_retry_count

    @pytest.mark.asyncio
    async def test_multiple_running_jobs_all_reset(
        self, rollback_session_factory):
        """Test that multiple running jobs are all reset on restart."""
        # Create multiple running jobs
        run1 = await create_live20_run(
            rollback_session_factory, status="running", worker_id="worker-1"
        )
        run2 = await create_live20_run(
            rollback_session_factory, status="running", worker_id="worker-2"
        )
        run3 = await create_live20_run(
            rollback_session_factory, status="running", worker_id="worker-3"
        )

        service = JobQueueService(rollback_session_factory, Live20Run)
        reset_count = await service.reset_stranded_jobs()

        assert reset_count == 3

        # All jobs should be pending now
        for run_id in [run1.id, run2.id, run3.id]:
            updated = await get_run_by_id(rollback_session_factory, run_id)
            assert updated.status == "pending"
            assert updated.worker_id is None


class TestJobRetryOnFailure:
    """Integration tests for job retry behavior on failure."""

    @pytest.mark.asyncio
    async def test_job_retries_on_failure(
        self, rollback_session_factory):
        """Test that failed jobs are retried up to max_retries.

        Scenario:
        1. Create a job
        2. Claim it and set to running
        3. Call mark_failed() with an error
        4. Verify retry_count increments and status returns to pending
        5. Repeat until max_retries exceeded
        6. Verify final status is 'failed'
        """
        max_retries = 3
        run = await create_live20_run(
            rollback_session_factory,
            status="pending",
            retry_count=0,
            max_retries=max_retries,
        )

        service = JobQueueService(rollback_session_factory, Live20Run)

        # Retry loop
        for i in range(max_retries):
            # Claim the job
            claimed = await service.claim_next_job()
            assert claimed is not None
            assert claimed.id == run.id

            # Verify job is running
            current = await get_run_by_id(rollback_session_factory, run.id)
            assert current.status == "running"

            # Mark as failed (simulating an error during processing)
            await service.mark_failed(run.id, f"Error on attempt {i + 1}")

            # Verify job is reset for retry
            updated = await get_run_by_id(rollback_session_factory, run.id)
            assert updated.retry_count == i + 1
            assert updated.status == "pending"
            assert updated.last_error == f"Error on attempt {i + 1}"

        # Final failure - should now be at max_retries
        claimed = await service.claim_next_job()
        assert claimed is not None

        await service.mark_failed(run.id, "Final failure")

        # Verify job is permanently failed
        final = await get_run_by_id(rollback_session_factory, run.id)
        assert final.status == "failed"
        assert final.retry_count == max_retries  # Not incremented past max
        assert final.last_error == "Final failure"

    @pytest.mark.asyncio
    async def test_failed_job_preserves_progress(
        self, rollback_session_factory):
        """Test that job progress is preserved across retries."""
        run = await create_live20_run(
            rollback_session_factory,
            status="running",
            processed_count=3,
            retry_count=0,
            max_retries=3,
        )

        service = JobQueueService(rollback_session_factory, Live20Run)
        await service.mark_failed(run.id, "Temporary error")

        updated = await get_run_by_id(rollback_session_factory, run.id)
        # Progress should be preserved for resumption
        assert updated.processed_count == 3
        assert updated.status == "pending"


class TestStaleJobReset:
    """Integration tests for stale job detection and reset."""

    @pytest.mark.asyncio
    async def test_stale_job_reset(self, rollback_session_factory):
        """Test that stale jobs are reset by sweeper.

        Scenario:
        1. Create a running job with old heartbeat (> 5 minutes ago)
        2. Call reset_stale_jobs()
        3. Verify job is reset to pending
        """
        stale_time = datetime.now(timezone.utc) - timedelta(
            seconds=STALE_JOB_THRESHOLD + 60  # 6 minutes ago
        )
        run = await create_live20_run(
            rollback_session_factory,
            status="running",
            heartbeat_at=stale_time,
            worker_id="stuck-worker",
            retry_count=0,
            max_retries=3,
        )

        service = JobQueueService(rollback_session_factory, Live20Run)
        reset_count = await service.reset_stale_jobs()

        assert reset_count == 1

        updated = await get_run_by_id(rollback_session_factory, run.id)
        assert updated.status == "pending"
        assert updated.worker_id is None
        assert updated.retry_count == 1  # Stale detection increments retry
        assert "stale" in updated.last_error.lower()

    @pytest.mark.asyncio
    async def test_stale_job_fails_after_max_retries(
        self, rollback_session_factory):
        """Test that stale job is failed when max_retries is exhausted."""
        stale_time = datetime.now(timezone.utc) - timedelta(
            seconds=STALE_JOB_THRESHOLD + 60
        )
        run = await create_live20_run(
            rollback_session_factory,
            status="running",
            heartbeat_at=stale_time,
            retry_count=3,  # At max
            max_retries=3,
        )

        service = JobQueueService(rollback_session_factory, Live20Run)
        reset_count = await service.reset_stale_jobs()

        # Not counted as reset (marked as failed instead)
        assert reset_count == 0

        updated = await get_run_by_id(rollback_session_factory, run.id)
        assert updated.status == "failed"

    @pytest.mark.asyncio
    async def test_recent_heartbeat_not_stale(
        self, rollback_session_factory):
        """Test that jobs with recent heartbeat are not considered stale."""
        recent_time = datetime.now(timezone.utc) - timedelta(seconds=30)  # 30s ago
        run = await create_live20_run(
            rollback_session_factory,
            status="running",
            heartbeat_at=recent_time,
            worker_id="active-worker",
        )

        service = JobQueueService(rollback_session_factory, Live20Run)
        reset_count = await service.reset_stale_jobs()

        assert reset_count == 0

        # Job should still be running
        updated = await get_run_by_id(rollback_session_factory, run.id)
        assert updated.status == "running"
        assert updated.worker_id == "active-worker"


class TestCancellationCheck:
    """Integration tests for job cancellation detection."""

    @pytest.mark.asyncio
    async def test_is_cancelled_detects_cancelled_job(
        self, rollback_session_factory):
        """Test that is_cancelled() correctly detects cancelled jobs.

        Scenario:
        1. Create a pending job
        2. Verify is_cancelled returns False
        3. Update status to 'cancelled'
        4. Verify is_cancelled returns True
        """
        run = await create_live20_run(rollback_session_factory, status="pending")

        service = JobQueueService(rollback_session_factory, Live20Run)

        # Not cancelled initially
        assert await service.is_cancelled(run.id) is False

        # Update to cancelled directly in database (simulating user cancellation)
        async with rollback_session_factory() as session:
            result = await session.execute(
                select(Live20Run).where(Live20Run.id == run.id)
            )
            fetched_run = result.scalar_one()
            fetched_run.status = "cancelled"
            await session.commit()

        # Now should be cancelled
        assert await service.is_cancelled(run.id) is True

    @pytest.mark.asyncio
    async def test_is_cancelled_returns_false_for_running(
        self, rollback_session_factory):
        """Test that is_cancelled returns False for running jobs."""
        run = await create_live20_run(rollback_session_factory, status="running")

        service = JobQueueService(rollback_session_factory, Live20Run)
        assert await service.is_cancelled(run.id) is False

    @pytest.mark.asyncio
    async def test_is_cancelled_returns_false_for_completed(
        self, rollback_session_factory):
        """Test that is_cancelled returns False for completed jobs."""
        run = await create_live20_run(rollback_session_factory, status="completed")

        service = JobQueueService(rollback_session_factory, Live20Run)
        assert await service.is_cancelled(run.id) is False

    @pytest.mark.asyncio
    async def test_is_cancelled_returns_false_for_nonexistent(
        self, rollback_session_factory):
        """Test that is_cancelled returns False for nonexistent job."""
        service = JobQueueService(rollback_session_factory, Live20Run)
        assert await service.is_cancelled(999999) is False


class TestFullJobLifecycle:
    """Integration tests for complete job lifecycle scenarios."""

    @pytest.mark.asyncio
    async def test_full_job_success_flow(self, rollback_session_factory):
        """Test complete job lifecycle: create -> claim -> complete.

        This tests the happy path where a job is created, claimed by a worker,
        processed successfully, and marked as completed.
        """
        # 1. Create job
        run = await create_live20_run(rollback_session_factory, status="pending")
        assert run.id is not None
        assert run.status == "pending"

        # 2. Worker claims job
        service = JobQueueService(
            rollback_session_factory, Live20Run, worker_id="test-worker"
        )
        claimed = await service.claim_next_job()
        assert claimed.id == run.id

        # Verify claimed state
        claimed_run = await get_run_by_id(rollback_session_factory, run.id)
        assert claimed_run.status == "running"
        assert claimed_run.worker_id == "test-worker"
        assert claimed_run.claimed_at is not None
        assert claimed_run.heartbeat_at is not None

        # 3. Worker updates heartbeat during processing
        await service.update_heartbeat(run.id)
        heartbeat_run = await get_run_by_id(rollback_session_factory, run.id)
        assert heartbeat_run.heartbeat_at is not None

        # 4. Worker completes job
        await service.mark_completed(run.id)
        completed_run = await get_run_by_id(rollback_session_factory, run.id)
        assert completed_run.status == "completed"

    @pytest.mark.asyncio
    async def test_full_job_failure_and_retry_flow(
        self, rollback_session_factory):
        """Test job lifecycle with failure and successful retry.

        This tests the scenario where a job fails on first attempt,
        is retried, and succeeds on the second attempt.
        """
        run = await create_live20_run(
            rollback_session_factory, status="pending", max_retries=3
        )

        service = JobQueueService(rollback_session_factory, Live20Run)

        # First attempt - fails
        claimed = await service.claim_next_job()
        assert claimed.id == run.id
        await service.mark_failed(run.id, "Network error")

        first_fail = await get_run_by_id(rollback_session_factory, run.id)
        assert first_fail.status == "pending"
        assert first_fail.retry_count == 1

        # Second attempt - succeeds
        claimed = await service.claim_next_job()
        assert claimed.id == run.id
        await service.mark_completed(run.id)

        completed = await get_run_by_id(rollback_session_factory, run.id)
        assert completed.status == "completed"
        assert completed.retry_count == 1  # Still 1 from the failed attempt

    @pytest.mark.asyncio
    async def test_fifo_ordering_preserved_across_failures(
        self, rollback_session_factory):
        """Test that FIFO ordering is preserved when jobs fail and retry.

        When a job fails and is reset to pending, it should be picked up
        before newer pending jobs (maintains FIFO based on created_at).
        """
        # Create first job and set it to running (simulating it was picked up)
        run1 = await create_live20_run(rollback_session_factory, status="running")

        # Create second job as pending (newer)
        run2 = await create_live20_run(rollback_session_factory, status="pending")

        service = JobQueueService(rollback_session_factory, Live20Run)

        # Fail run1 - should be reset to pending
        await service.mark_failed(run1.id, "Error")

        # Claim next job - should get run1 (older) not run2 (newer)
        claimed = await service.claim_next_job()
        assert claimed.id == run1.id

        # Claim next - now should get run2
        claimed = await service.claim_next_job()
        assert claimed.id == run2.id
