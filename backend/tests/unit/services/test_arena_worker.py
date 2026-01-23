"""Tests for the ArenaWorker class.

Tests the worker that processes arena simulation jobs from the queue.
"""

import logging
from datetime import date, datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from sqlalchemy import text

from app.models.arena import ArenaSimulation, ArenaSnapshot, SimulationStatus
from app.services.arena.arena_worker import ArenaWorker
from app.services.job_queue_service import JobQueueService


@pytest_asyncio.fixture
async def clean_arena_tables(test_session_factory):
    """Clean arena tables before and after each test."""
    async with test_session_factory() as session:
        await session.execute(
            text(
                "TRUNCATE TABLE arena_snapshots, arena_positions, arena_simulations "
                "RESTART IDENTITY CASCADE"
            )
        )
        await session.commit()

    yield

    async with test_session_factory() as session:
        await session.execute(
            text(
                "TRUNCATE TABLE arena_snapshots, arena_positions, arena_simulations "
                "RESTART IDENTITY CASCADE"
            )
        )
        await session.commit()


async def create_arena_simulation(
    session_factory,
    status: str = SimulationStatus.PENDING.value,
    current_day: int = 0,
    total_days: int = 0,
) -> ArenaSimulation:
    """Helper to create an ArenaSimulation for testing."""
    async with session_factory() as session:
        simulation = ArenaSimulation(
            name="Test Simulation",
            symbols=["AAPL", "MSFT"],
            start_date=date(2024, 1, 15),
            end_date=date(2024, 1, 25),
            initial_capital=Decimal("10000.00"),
            position_size=Decimal("1000.00"),
            agent_type="live20",
            agent_config={"trailing_stop_pct": 5.0},
            status=status,
            current_day=current_day,
            total_days=total_days,
            retry_count=0,
            max_retries=3,
        )
        session.add(simulation)
        await session.commit()
        await session.refresh(simulation)
        return simulation


async def get_simulation_by_id(
    session_factory, simulation_id: int
) -> ArenaSimulation | None:
    """Helper to get an ArenaSimulation by ID."""
    from sqlalchemy import select

    async with session_factory() as session:
        result = await session.execute(
            select(ArenaSimulation).where(ArenaSimulation.id == simulation_id)
        )
        return result.scalar_one_or_none()


@pytest.fixture
def mock_queue_service():
    """Create a mock queue service."""
    service = MagicMock(spec=JobQueueService)
    service.worker_id = "arena-worker-test"
    service.is_cancelled = AsyncMock(return_value=False)
    return service


@pytest.fixture
def mock_simulation_engine():
    """Create a mock SimulationEngine."""
    mock = MagicMock()
    mock.initialize_simulation = AsyncMock()
    mock.step_day = AsyncMock()
    return mock


@pytest.fixture
def mock_snapshot():
    """Create a mock ArenaSnapshot."""
    snapshot = MagicMock(spec=ArenaSnapshot)
    snapshot.day_number = 0
    snapshot.total_equity = Decimal("10000.00")
    snapshot.cash = Decimal("10000.00")
    snapshot.positions_value = Decimal("0")
    return snapshot


def create_mock_engine_with_immediate_completion():
    """Create a mock SimulationEngine that immediately completes."""
    mock_engine = MagicMock()
    mock_engine.initialize_simulation = AsyncMock()
    mock_engine.step_day = AsyncMock(return_value=None)
    return mock_engine


@pytest.mark.unit
class TestArenaWorkerProcessJob:
    """Tests for the process_job method."""

    @pytest.mark.asyncio
    async def test_process_job_initializes_pending_simulation(
        self, test_session_factory, mock_queue_service, clean_arena_tables
    ):
        """Should initialize simulation when current_day=0 and total_days=0."""
        simulation = await create_arena_simulation(
            test_session_factory,
            status=SimulationStatus.RUNNING.value,
            current_day=0,
            total_days=0,
        )

        worker = ArenaWorker(test_session_factory, mock_queue_service)

        with patch(
            "app.services.arena.arena_worker.SimulationEngine"
        ) as MockEngine:
            mock_engine = MagicMock()
            # Mock initialize to update simulation state
            async def mock_init(sim_id):
                async with test_session_factory() as session:
                    sim = await session.get(ArenaSimulation, sim_id)
                    sim.total_days = 5
                    sim.status = SimulationStatus.RUNNING.value
                    await session.commit()

            mock_engine.initialize_simulation = AsyncMock(side_effect=mock_init)
            mock_engine.step_day = AsyncMock(return_value=None)  # Immediately complete
            MockEngine.return_value = mock_engine

            await worker.process_job(simulation)

            # Verify initialization was called
            mock_engine.initialize_simulation.assert_called_once_with(simulation.id)

    @pytest.mark.asyncio
    async def test_process_job_skips_initialization_for_resumed_simulation(
        self, test_session_factory, mock_queue_service, clean_arena_tables
    ):
        """Should skip initialization when simulation already has total_days set."""
        simulation = await create_arena_simulation(
            test_session_factory,
            status=SimulationStatus.RUNNING.value,
            current_day=2,  # Already at day 2
            total_days=5,   # Total days already set
        )

        worker = ArenaWorker(test_session_factory, mock_queue_service)

        with patch(
            "app.services.arena.arena_worker.SimulationEngine"
        ) as MockEngine:
            mock_engine = MagicMock()
            mock_engine.initialize_simulation = AsyncMock()
            mock_engine.step_day = AsyncMock(return_value=None)  # Immediately complete
            MockEngine.return_value = mock_engine

            await worker.process_job(simulation)

            # Verify initialization was NOT called (simulation already started)
            mock_engine.initialize_simulation.assert_not_called()

    @pytest.mark.asyncio
    async def test_process_job_checks_cancellation_before_each_day(
        self, test_session_factory, mock_queue_service, clean_arena_tables
    ):
        """Should check for cancellation before each day's processing."""
        simulation = await create_arena_simulation(
            test_session_factory,
            status=SimulationStatus.RUNNING.value,
            current_day=0,
            total_days=5,
        )

        # Return False twice, then True to simulate cancellation
        mock_queue_service.is_cancelled = AsyncMock(
            side_effect=[False, False, True]
        )

        worker = ArenaWorker(test_session_factory, mock_queue_service)

        with patch(
            "app.services.arena.arena_worker.SimulationEngine"
        ) as MockEngine:
            mock_engine = MagicMock()
            mock_engine.initialize_simulation = AsyncMock()

            # Create a mock snapshot that updates current_day
            step_count = [0]
            async def mock_step_day(sim_id):
                step_count[0] += 1
                # Update simulation state
                async with test_session_factory() as session:
                    sim = await session.get(ArenaSimulation, sim_id)
                    sim.current_day = step_count[0]
                    await session.commit()
                # Return mock snapshot
                mock_snapshot = MagicMock()
                mock_snapshot.total_equity = Decimal("10000.00")
                return mock_snapshot

            mock_engine.step_day = AsyncMock(side_effect=mock_step_day)
            MockEngine.return_value = mock_engine

            await worker.process_job(simulation)

        # Should have checked cancellation 3 times (False, False, True)
        assert mock_queue_service.is_cancelled.call_count == 3

    @pytest.mark.asyncio
    async def test_process_job_stops_on_cancellation(
        self, test_session_factory, mock_queue_service, clean_arena_tables
    ):
        """Should stop processing when simulation is cancelled."""
        simulation = await create_arena_simulation(
            test_session_factory,
            status=SimulationStatus.RUNNING.value,
            current_day=0,
            total_days=5,
        )

        # Cancel immediately
        mock_queue_service.is_cancelled = AsyncMock(return_value=True)

        worker = ArenaWorker(test_session_factory, mock_queue_service)

        with patch(
            "app.services.arena.arena_worker.SimulationEngine"
        ) as MockEngine:
            mock_engine = MagicMock()
            mock_engine.initialize_simulation = AsyncMock()
            mock_engine.step_day = AsyncMock()
            MockEngine.return_value = mock_engine

            await worker.process_job(simulation)

            # step_day should not be called due to immediate cancellation
            mock_engine.step_day.assert_not_called()

    @pytest.mark.asyncio
    async def test_process_job_completes_all_days(
        self, test_session_factory, mock_queue_service, clean_arena_tables
    ):
        """Should process all days until completion."""
        simulation = await create_arena_simulation(
            test_session_factory,
            status=SimulationStatus.RUNNING.value,
            current_day=0,
            total_days=3,
        )

        worker = ArenaWorker(test_session_factory, mock_queue_service)

        with patch(
            "app.services.arena.arena_worker.SimulationEngine"
        ) as MockEngine:
            mock_engine = MagicMock()
            mock_engine.initialize_simulation = AsyncMock()

            # Mock step_day to update current_day and eventually return None
            step_count = [0]
            async def mock_step_day(sim_id):
                step_count[0] += 1
                # Update simulation state
                async with test_session_factory() as session:
                    sim = await session.get(ArenaSimulation, sim_id)
                    sim.current_day = step_count[0]
                    await session.commit()

                if step_count[0] >= 3:
                    # Simulation complete
                    return None

                # Return mock snapshot
                mock_snapshot = MagicMock()
                mock_snapshot.total_equity = Decimal("10000.00")
                return mock_snapshot

            mock_engine.step_day = AsyncMock(side_effect=mock_step_day)
            MockEngine.return_value = mock_engine

            await worker.process_job(simulation)

            # Should have called step_day 3 times
            assert mock_engine.step_day.call_count == 3


@pytest.mark.unit
class TestArenaWorkerLogging:
    """Tests for ArenaWorker logging."""

    @pytest.mark.asyncio
    async def test_logs_simulation_start(
        self, test_session_factory, mock_queue_service, clean_arena_tables, caplog
    ):
        """Should log simulation start with current progress."""
        caplog.set_level(logging.INFO)

        simulation = await create_arena_simulation(
            test_session_factory,
            status=SimulationStatus.RUNNING.value,
            current_day=2,
            total_days=5,
        )

        worker = ArenaWorker(test_session_factory, mock_queue_service)

        with patch(
            "app.services.arena.arena_worker.SimulationEngine"
        ) as MockEngine:
            mock_engine = MagicMock()
            mock_engine.step_day = AsyncMock(return_value=None)
            MockEngine.return_value = mock_engine

            await worker.process_job(simulation)

        log_messages = [record.message for record in caplog.records]
        # Should log something about starting at day 2/5
        assert any("day 2/5" in msg for msg in log_messages)

    @pytest.mark.asyncio
    async def test_logs_cancellation(
        self, test_session_factory, mock_queue_service, clean_arena_tables, caplog
    ):
        """Should log when simulation is cancelled."""
        caplog.set_level(logging.INFO)

        simulation = await create_arena_simulation(
            test_session_factory,
            status=SimulationStatus.RUNNING.value,
            current_day=0,
            total_days=5,
        )

        mock_queue_service.is_cancelled = AsyncMock(return_value=True)

        worker = ArenaWorker(test_session_factory, mock_queue_service)

        with patch(
            "app.services.arena.arena_worker.SimulationEngine"
        ) as MockEngine:
            mock_engine = MagicMock()
            MockEngine.return_value = mock_engine

            await worker.process_job(simulation)

        log_messages = [record.message for record in caplog.records]
        assert any("cancelled" in msg.lower() for msg in log_messages)

    @pytest.mark.asyncio
    async def test_logs_initialization(
        self, test_session_factory, mock_queue_service, clean_arena_tables, caplog
    ):
        """Should log when simulation is initialized."""
        caplog.set_level(logging.INFO)

        simulation = await create_arena_simulation(
            test_session_factory,
            status=SimulationStatus.RUNNING.value,
            current_day=0,
            total_days=0,  # Not yet initialized
        )

        worker = ArenaWorker(test_session_factory, mock_queue_service)

        with patch(
            "app.services.arena.arena_worker.SimulationEngine"
        ) as MockEngine:
            mock_engine = MagicMock()

            async def mock_init(sim_id):
                async with test_session_factory() as session:
                    sim = await session.get(ArenaSimulation, sim_id)
                    sim.total_days = 10
                    await session.commit()

            mock_engine.initialize_simulation = AsyncMock(side_effect=mock_init)
            mock_engine.step_day = AsyncMock(return_value=None)
            MockEngine.return_value = mock_engine

            await worker.process_job(simulation)

        log_messages = [record.message for record in caplog.records]
        # Should log initialization
        assert any("initializing" in msg.lower() for msg in log_messages)
        assert any("10 trading days" in msg for msg in log_messages)


@pytest.mark.unit
class TestArenaWorkerResumeCapability:
    """Tests for resume capability from partial completion."""

    @pytest.mark.asyncio
    async def test_resume_continues_from_current_day(
        self, test_session_factory, mock_queue_service, clean_arena_tables
    ):
        """Should continue processing from current_day on resume."""
        # Simulate a simulation that was interrupted at day 3 of 5
        simulation = await create_arena_simulation(
            test_session_factory,
            status=SimulationStatus.RUNNING.value,
            current_day=3,
            total_days=5,
        )

        worker = ArenaWorker(test_session_factory, mock_queue_service)
        processed_days = []

        with patch(
            "app.services.arena.arena_worker.SimulationEngine"
        ) as MockEngine:
            mock_engine = MagicMock()
            mock_engine.initialize_simulation = AsyncMock()

            async def mock_step_day(sim_id):
                # Track which day we're processing
                async with test_session_factory() as session:
                    sim = await session.get(ArenaSimulation, sim_id)
                    processed_days.append(sim.current_day)
                    sim.current_day += 1
                    await session.commit()

                # Return None when complete
                if len(processed_days) >= 2:  # Days 3 and 4
                    return None

                mock_snapshot = MagicMock()
                mock_snapshot.total_equity = Decimal("10000.00")
                return mock_snapshot

            mock_engine.step_day = AsyncMock(side_effect=mock_step_day)
            MockEngine.return_value = mock_engine

            await worker.process_job(simulation)

        # Should have processed days 3 and 4 (not 0, 1, 2)
        assert 3 in processed_days
        # Initialization should NOT have been called (total_days > 0)
        mock_engine.initialize_simulation.assert_not_called()

    @pytest.mark.asyncio
    async def test_resume_does_not_reinitialize(
        self, test_session_factory, mock_queue_service, clean_arena_tables
    ):
        """Should not re-initialize a partially completed simulation."""
        simulation = await create_arena_simulation(
            test_session_factory,
            status=SimulationStatus.RUNNING.value,
            current_day=2,
            total_days=5,  # Already initialized
        )

        worker = ArenaWorker(test_session_factory, mock_queue_service)

        with patch(
            "app.services.arena.arena_worker.SimulationEngine"
        ) as MockEngine:
            mock_engine = MagicMock()
            mock_engine.initialize_simulation = AsyncMock()
            mock_engine.step_day = AsyncMock(return_value=None)
            MockEngine.return_value = mock_engine

            await worker.process_job(simulation)

            # Should NOT call initialize since total_days > 0
            mock_engine.initialize_simulation.assert_not_called()


@pytest.mark.unit
class TestArenaWorkerEdgeCases:
    """Tests for edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_handles_empty_simulation(
        self, test_session_factory, mock_queue_service, clean_arena_tables
    ):
        """Should handle simulation with no trading days."""
        simulation = await create_arena_simulation(
            test_session_factory,
            status=SimulationStatus.RUNNING.value,
            current_day=0,
            total_days=0,
        )

        worker = ArenaWorker(test_session_factory, mock_queue_service)

        with patch(
            "app.services.arena.arena_worker.SimulationEngine"
        ) as MockEngine:
            mock_engine = MagicMock()

            # Initialize sets total_days to 0 (no trading days in range)
            async def mock_init(sim_id):
                async with test_session_factory() as session:
                    sim = await session.get(ArenaSimulation, sim_id)
                    sim.total_days = 0  # No trading days!
                    await session.commit()

            mock_engine.initialize_simulation = AsyncMock(side_effect=mock_init)
            mock_engine.step_day = AsyncMock(return_value=None)
            MockEngine.return_value = mock_engine

            # Should not raise
            await worker.process_job(simulation)

            # step_day should not be called (current_day=0 >= total_days=0)
            mock_engine.step_day.assert_not_called()

    @pytest.mark.asyncio
    async def test_simulation_already_at_final_day(
        self, test_session_factory, mock_queue_service, clean_arena_tables
    ):
        """Should handle simulation already at the final day."""
        simulation = await create_arena_simulation(
            test_session_factory,
            status=SimulationStatus.RUNNING.value,
            current_day=5,
            total_days=5,  # At the end
        )

        worker = ArenaWorker(test_session_factory, mock_queue_service)

        with patch(
            "app.services.arena.arena_worker.SimulationEngine"
        ) as MockEngine:
            mock_engine = MagicMock()
            mock_engine.initialize_simulation = AsyncMock()
            mock_engine.step_day = AsyncMock()
            MockEngine.return_value = mock_engine

            await worker.process_job(simulation)

            # step_day should not be called (current_day >= total_days)
            mock_engine.step_day.assert_not_called()
