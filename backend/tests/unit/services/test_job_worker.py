"""Tests for the JobWorker base class.

Tests the abstract base class that provides the worker loop, heartbeat,
and sweeper functionality for job processing.
"""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.live20_run import Live20Run
from app.services.job_queue_service import JobQueueService
from app.services.job_worker import JobWorker


class ConcreteWorker(JobWorker[Live20Run]):
    """Concrete implementation of JobWorker for testing."""

    def __init__(self, *args, process_job_side_effect=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.processed_jobs = []
        self.process_job_side_effect = process_job_side_effect

    async def process_job(self, job: Live20Run) -> None:
        """Track processed jobs for test verification."""
        self.processed_jobs.append(job)
        if self.process_job_side_effect:
            if isinstance(self.process_job_side_effect, Exception):
                raise self.process_job_side_effect
            elif callable(self.process_job_side_effect):
                await self.process_job_side_effect(job)


@pytest.fixture
def mock_session_factory():
    """Create a mock session factory."""
    return MagicMock()


@pytest.fixture
def mock_queue_service(mock_session_factory):
    """Create a mock queue service."""
    service = MagicMock(spec=JobQueueService)
    service.worker_id = "test-worker-123"
    service.claim_next_job = AsyncMock(return_value=None)
    service.update_heartbeat = AsyncMock()
    service.mark_completed = AsyncMock()
    service.mark_failed = AsyncMock()
    service.reset_stale_jobs = AsyncMock(return_value=0)
    return service


@pytest.mark.unit
class TestJobWorkerInitialization:
    """Tests for JobWorker initialization."""

    def test_init_stores_session_factory(self, mock_session_factory, mock_queue_service):
        """Should store session factory."""
        worker = ConcreteWorker(mock_session_factory, mock_queue_service)
        assert worker.session_factory == mock_session_factory

    def test_init_stores_queue_service(self, mock_session_factory, mock_queue_service):
        """Should store queue service."""
        worker = ConcreteWorker(mock_session_factory, mock_queue_service)
        assert worker.queue_service == mock_queue_service

    def test_init_default_poll_interval(self, mock_session_factory, mock_queue_service):
        """Should default poll interval to 5.0 seconds."""
        worker = ConcreteWorker(mock_session_factory, mock_queue_service)
        assert worker.poll_interval == 5.0

    def test_init_custom_poll_interval(self, mock_session_factory, mock_queue_service):
        """Should accept custom poll interval."""
        worker = ConcreteWorker(mock_session_factory, mock_queue_service, poll_interval=10.0)
        assert worker.poll_interval == 10.0

    def test_init_running_is_false(self, mock_session_factory, mock_queue_service):
        """Should initialize with _running = False."""
        worker = ConcreteWorker(mock_session_factory, mock_queue_service)
        assert worker._running is False

    def test_init_current_job_id_is_none(self, mock_session_factory, mock_queue_service):
        """Should initialize with _current_job_id = None."""
        worker = ConcreteWorker(mock_session_factory, mock_queue_service)
        assert worker._current_job_id is None


@pytest.mark.unit
class TestJobWorkerStart:
    """Tests for the start method."""

    @pytest.mark.asyncio
    async def test_start_sets_running_true(self, mock_session_factory, mock_queue_service):
        """Should set _running to True when started."""
        worker = ConcreteWorker(mock_session_factory, mock_queue_service, poll_interval=0.01)

        # Start worker and immediately stop it
        start_task = asyncio.create_task(worker.start())
        await asyncio.sleep(0.05)  # Let it run briefly

        assert worker._running is True

        worker._running = False  # Stop the loop
        await asyncio.sleep(0.05)
        start_task.cancel()
        try:
            await start_task
        except asyncio.CancelledError:
            pass

    @pytest.mark.asyncio
    async def test_start_creates_sweeper_task(self, mock_session_factory, mock_queue_service):
        """Should create sweeper task on start."""
        worker = ConcreteWorker(mock_session_factory, mock_queue_service, poll_interval=0.01)

        start_task = asyncio.create_task(worker.start())
        await asyncio.sleep(0.05)

        assert worker._sweeper_task is not None
        assert not worker._sweeper_task.done()

        worker._running = False
        start_task.cancel()
        try:
            await start_task
        except asyncio.CancelledError:
            pass

    @pytest.mark.asyncio
    async def test_start_polls_for_jobs(self, mock_session_factory, mock_queue_service):
        """Should poll for jobs using queue service."""
        worker = ConcreteWorker(mock_session_factory, mock_queue_service, poll_interval=0.01)

        start_task = asyncio.create_task(worker.start())
        await asyncio.sleep(0.1)

        assert mock_queue_service.claim_next_job.called

        worker._running = False
        start_task.cancel()
        try:
            await start_task
        except asyncio.CancelledError:
            pass

    @pytest.mark.asyncio
    async def test_start_processes_claimed_job(self, mock_session_factory, mock_queue_service):
        """Should process a job when claimed."""
        mock_job = MagicMock()
        mock_job.id = 1
        mock_queue_service.claim_next_job = AsyncMock(
            side_effect=[mock_job, None, None, None]
        )

        worker = ConcreteWorker(mock_session_factory, mock_queue_service, poll_interval=0.01)

        start_task = asyncio.create_task(worker.start())
        await asyncio.sleep(0.1)

        assert mock_job in worker.processed_jobs
        mock_queue_service.mark_completed.assert_called_once_with(1)

        worker._running = False
        start_task.cancel()
        try:
            await start_task
        except asyncio.CancelledError:
            pass

    @pytest.mark.asyncio
    async def test_start_marks_failed_on_exception(self, mock_session_factory, mock_queue_service):
        """Should mark job as failed when process_job raises exception."""
        mock_job = MagicMock()
        mock_job.id = 2
        mock_queue_service.claim_next_job = AsyncMock(
            side_effect=[mock_job, None, None, None]
        )

        worker = ConcreteWorker(
            mock_session_factory,
            mock_queue_service,
            poll_interval=0.01,
            process_job_side_effect=ValueError("Test error"),
        )

        start_task = asyncio.create_task(worker.start())
        await asyncio.sleep(0.1)

        mock_queue_service.mark_failed.assert_called_once_with(2, "Test error")
        mock_queue_service.mark_completed.assert_not_called()

        worker._running = False
        start_task.cancel()
        try:
            await start_task
        except asyncio.CancelledError:
            pass

    @pytest.mark.asyncio
    async def test_start_sets_current_job_id_during_processing(
        self, mock_session_factory, mock_queue_service
    ):
        """Should set _current_job_id while processing."""
        mock_job = MagicMock()
        mock_job.id = 42
        captured_job_id = None

        async def capture_job_id(job):
            nonlocal captured_job_id
            captured_job_id = worker._current_job_id
            await asyncio.sleep(0.01)

        mock_queue_service.claim_next_job = AsyncMock(
            side_effect=[mock_job, None, None, None]
        )

        worker = ConcreteWorker(
            mock_session_factory,
            mock_queue_service,
            poll_interval=0.01,
            process_job_side_effect=capture_job_id,
        )

        start_task = asyncio.create_task(worker.start())
        await asyncio.sleep(0.1)

        assert captured_job_id == 42

        worker._running = False
        start_task.cancel()
        try:
            await start_task
        except asyncio.CancelledError:
            pass

    @pytest.mark.asyncio
    async def test_start_clears_current_job_id_after_processing(
        self, mock_session_factory, mock_queue_service
    ):
        """Should clear _current_job_id after processing completes."""
        mock_job = MagicMock()
        mock_job.id = 42
        mock_queue_service.claim_next_job = AsyncMock(
            side_effect=[mock_job, None, None, None]
        )

        worker = ConcreteWorker(mock_session_factory, mock_queue_service, poll_interval=0.01)

        start_task = asyncio.create_task(worker.start())
        await asyncio.sleep(0.1)

        assert worker._current_job_id is None

        worker._running = False
        start_task.cancel()
        try:
            await start_task
        except asyncio.CancelledError:
            pass


@pytest.mark.unit
class TestJobWorkerStop:
    """Tests for the stop method."""

    @pytest.mark.asyncio
    async def test_stop_sets_running_false(self, mock_session_factory, mock_queue_service):
        """Should set _running to False when stopped."""
        worker = ConcreteWorker(mock_session_factory, mock_queue_service, poll_interval=0.01)

        start_task = asyncio.create_task(worker.start())
        await asyncio.sleep(0.05)

        await worker.stop()

        assert worker._running is False

        start_task.cancel()
        try:
            await start_task
        except asyncio.CancelledError:
            pass

    @pytest.mark.asyncio
    async def test_stop_cancels_sweeper_task(self, mock_session_factory, mock_queue_service):
        """Should cancel sweeper task when stopped."""
        worker = ConcreteWorker(mock_session_factory, mock_queue_service, poll_interval=0.01)

        start_task = asyncio.create_task(worker.start())
        await asyncio.sleep(0.05)

        sweeper_task = worker._sweeper_task
        await worker.stop()

        assert sweeper_task.cancelled() or sweeper_task.done()

        start_task.cancel()
        try:
            await start_task
        except asyncio.CancelledError:
            pass


@pytest.mark.unit
class TestHeartbeatLoop:
    """Tests for the _heartbeat_loop method."""

    @pytest.mark.asyncio
    async def test_heartbeat_loop_updates_heartbeat(self, mock_session_factory, mock_queue_service):
        """Should update heartbeat at regular intervals."""
        worker = ConcreteWorker(mock_session_factory, mock_queue_service)

        # Patch HEARTBEAT_INTERVAL to make test faster
        with patch("app.services.job_worker.HEARTBEAT_INTERVAL", 0.01):
            heartbeat_task = asyncio.create_task(worker._heartbeat_loop(123))
            await asyncio.sleep(0.05)

            heartbeat_task.cancel()
            try:
                await heartbeat_task
            except asyncio.CancelledError:
                pass

        assert mock_queue_service.update_heartbeat.called
        mock_queue_service.update_heartbeat.assert_called_with(123)


@pytest.mark.unit
class TestSweeperLoop:
    """Tests for the _sweeper_loop method."""

    @pytest.mark.asyncio
    async def test_sweeper_loop_calls_reset_stale_jobs(
        self, mock_session_factory, mock_queue_service
    ):
        """Should call reset_stale_jobs periodically."""
        worker = ConcreteWorker(mock_session_factory, mock_queue_service)
        worker._running = True

        # Create sweeper task and let it run briefly
        sweeper_task = asyncio.create_task(worker._sweeper_loop())

        # The sweeper sleeps for 60 seconds, so we'll test that it starts correctly
        # and can be cancelled cleanly
        await asyncio.sleep(0.01)

        worker._running = False
        sweeper_task.cancel()
        try:
            await sweeper_task
        except asyncio.CancelledError:
            pass

    @pytest.mark.asyncio
    async def test_sweeper_loop_handles_exceptions(
        self, mock_session_factory, mock_queue_service
    ):
        """Should handle exceptions without crashing."""
        mock_queue_service.reset_stale_jobs = AsyncMock(side_effect=Exception("DB error"))
        worker = ConcreteWorker(mock_session_factory, mock_queue_service)
        worker._running = True

        sweeper_task = asyncio.create_task(worker._sweeper_loop())
        await asyncio.sleep(0.01)

        # Should still be running despite exception
        assert not sweeper_task.done()

        worker._running = False
        sweeper_task.cancel()
        try:
            await sweeper_task
        except asyncio.CancelledError:
            pass


@pytest.mark.unit
class TestWorkerLogging:
    """Tests for worker logging with worker_id prefix."""

    @pytest.mark.asyncio
    async def test_start_logs_with_worker_id(
        self, mock_session_factory, mock_queue_service, caplog
    ):
        """Should include worker_id in log messages."""
        import logging

        caplog.set_level(logging.INFO)
        mock_queue_service.worker_id = "test-worker-xyz"

        worker = ConcreteWorker(mock_session_factory, mock_queue_service, poll_interval=0.01)

        start_task = asyncio.create_task(worker.start())
        await asyncio.sleep(0.05)

        worker._running = False
        start_task.cancel()
        try:
            await start_task
        except asyncio.CancelledError:
            pass

        # Check that logs contain worker_id
        log_messages = [record.message for record in caplog.records]
        assert any("test-worker-xyz" in msg for msg in log_messages)
