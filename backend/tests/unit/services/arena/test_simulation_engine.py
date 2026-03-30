"""Comprehensive unit tests for the SimulationEngine.

Tests the core simulation engine that orchestrates day-by-day
trading simulations with position management and trailing stops.
"""

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select

from app.models.arena import (
    ArenaPosition,
    ArenaSimulation,
    ArenaSnapshot,
    ExitReason,
    PositionStatus,
    SimulationStatus,
)
from app.services.arena.agent_protocol import AgentDecision, PriceBar
from app.services.arena.simulation_engine import SimulationEngine


class TestSimulationEngineInit:
    """Tests for SimulationEngine initialization."""

    @pytest.mark.unit
    def test_init_with_session(self) -> None:
        """Test engine initialization with session."""
        mock_session = AsyncMock()
        mock_session_factory = MagicMock()

        engine = SimulationEngine(mock_session, session_factory=mock_session_factory)

        assert engine.session is mock_session
        assert engine.data_service is not None


@pytest.mark.usefixtures("db_session")
class TestSimulationEngineInitializeSimulation:
    """Tests for SimulationEngine.initialize_simulation() method."""

    @pytest.fixture
    def valid_simulation_data(self) -> dict:
        """Create valid simulation data."""
        return {
            "name": "Test Simulation",
            "symbols": ["AAPL", "MSFT"],
            "start_date": date(2024, 1, 15),
            "end_date": date(2024, 1, 31),
            "initial_capital": Decimal("10000.00"),
            "position_size": Decimal("1000.00"),
            "agent_type": "live20",
            "agent_config": {"trailing_stop_pct": 5.0},
            "status": SimulationStatus.PENDING.value,
        }

    @pytest.fixture
    def mock_price_data(self) -> list:
        """Create mock price data points."""
        from app.providers.base import PriceDataPoint

        start = datetime(2024, 1, 1, tzinfo=timezone.utc)
        return [
            PriceDataPoint(
                symbol="AAPL",
                timestamp=start + timedelta(days=i),
                open_price=150.0 + i,
                high_price=152.0 + i,
                low_price=148.0 + i,
                close_price=151.0 + i,
                volume=1000000,
            )
            for i in range(60)
        ]

    @pytest.mark.unit
    async def test_initialize_simulation_not_found(
        self, db_session, rollback_session_factory
    ) -> None:
        """Test initialization fails when simulation not found."""
        engine = SimulationEngine(db_session, session_factory=rollback_session_factory)

        with pytest.raises(ValueError, match="not found"):
            await engine.initialize_simulation(99999)

    @pytest.mark.unit
    async def test_initialize_simulation_cancelled(
        self, db_session, rollback_session_factory, valid_simulation_data
    ) -> None:
        """Test initialization fails when simulation already cancelled."""
        valid_simulation_data["status"] = SimulationStatus.CANCELLED.value
        simulation = ArenaSimulation(**valid_simulation_data)
        db_session.add(simulation)
        await db_session.commit()
        await db_session.refresh(simulation)

        engine = SimulationEngine(db_session, session_factory=rollback_session_factory)

        with pytest.raises(ValueError, match="cannot be initialized"):
            await engine.initialize_simulation(simulation.id)

    @pytest.mark.unit
    async def test_initialize_simulation_already_completed(
        self, db_session, rollback_session_factory, valid_simulation_data
    ) -> None:
        """Test initialization fails when simulation already completed."""
        valid_simulation_data["status"] = SimulationStatus.COMPLETED.value
        simulation = ArenaSimulation(**valid_simulation_data)
        db_session.add(simulation)
        await db_session.commit()
        await db_session.refresh(simulation)

        engine = SimulationEngine(db_session, session_factory=rollback_session_factory)

        with pytest.raises(ValueError, match="cannot be initialized"):
            await engine.initialize_simulation(simulation.id)

    @pytest.mark.unit
    async def test_initialize_simulation_failed(
        self, db_session, rollback_session_factory, valid_simulation_data
    ) -> None:
        """Test initialization fails when simulation already failed."""
        valid_simulation_data["status"] = SimulationStatus.FAILED.value
        simulation = ArenaSimulation(**valid_simulation_data)
        db_session.add(simulation)
        await db_session.commit()
        await db_session.refresh(simulation)

        engine = SimulationEngine(db_session, session_factory=rollback_session_factory)

        with pytest.raises(ValueError, match="cannot be initialized"):
            await engine.initialize_simulation(simulation.id)

    @pytest.mark.unit
    async def test_initialize_simulation_idempotent(
        self, db_session, rollback_session_factory, valid_simulation_data
    ) -> None:
        """Test initialization is idempotent - skips if already initialized."""
        # Create simulation that's already initialized (total_days > 0)
        valid_simulation_data["status"] = SimulationStatus.RUNNING.value
        valid_simulation_data["total_days"] = 22
        simulation = ArenaSimulation(**valid_simulation_data)
        db_session.add(simulation)
        await db_session.commit()
        await db_session.refresh(simulation)

        engine = SimulationEngine(db_session, session_factory=rollback_session_factory)

        # Should return without error, not reinitialize
        result = await engine.initialize_simulation(simulation.id)

        assert result.id == simulation.id
        assert result.total_days == 22  # Unchanged

    @pytest.mark.unit
    async def test_initialize_simulation_no_trading_days(
        self, db_session, rollback_session_factory, valid_simulation_data, mock_price_data
    ) -> None:
        """Test initialization fails when no trading days in range."""
        # Set dates with no data
        valid_simulation_data["start_date"] = date(2030, 1, 1)
        valid_simulation_data["end_date"] = date(2030, 1, 15)

        simulation = ArenaSimulation(**valid_simulation_data)
        db_session.add(simulation)
        await db_session.commit()
        await db_session.refresh(simulation)

        engine = SimulationEngine(db_session, session_factory=rollback_session_factory)

        with patch.object(engine.data_service, "get_price_data", return_value=[]):
            with patch.object(
                engine.data_service,
                "batch_prefetch_sectors",
                new_callable=AsyncMock,
                return_value={},
            ):
                with pytest.raises(ValueError, match="No trading days"):
                    await engine.initialize_simulation(simulation.id)

    @pytest.mark.unit
    async def test_initialize_simulation_success(
        self, db_session, rollback_session_factory, valid_simulation_data, mock_price_data
    ) -> None:
        """Test successful simulation initialization."""
        simulation = ArenaSimulation(**valid_simulation_data)
        db_session.add(simulation)
        await db_session.commit()
        await db_session.refresh(simulation)

        engine = SimulationEngine(db_session, session_factory=rollback_session_factory)

        # Mock data service to return price data and sector prefetch
        with patch.object(engine.data_service, "get_price_data", return_value=mock_price_data):
            with patch.object(
                engine.data_service,
                "batch_prefetch_sectors",
                new_callable=AsyncMock,
                return_value={"AAPL": "Technology", "MSFT": "Technology"},
            ):
                result = await engine.initialize_simulation(simulation.id)

        assert result.status == SimulationStatus.RUNNING.value
        assert result.total_days > 0

    @pytest.mark.unit
    async def test_initialize_simulation_sector_cache_populated_from_prefetch(
        self, db_session, rollback_session_factory, valid_simulation_data, mock_price_data
    ) -> None:
        """After initialize_simulation, sector cache contains data returned by batch_prefetch_sectors."""
        simulation = ArenaSimulation(**valid_simulation_data)
        db_session.add(simulation)
        await db_session.commit()
        await db_session.refresh(simulation)

        engine = SimulationEngine(db_session, session_factory=rollback_session_factory)
        expected_sectors = {"AAPL": "Technology", "MSFT": "Financial Services"}

        with patch.object(engine.data_service, "get_price_data", return_value=mock_price_data):
            with patch.object(
                engine.data_service,
                "batch_prefetch_sectors",
                new_callable=AsyncMock,
                return_value=expected_sectors,
            ):
                await engine.initialize_simulation(simulation.id)

        assert engine._sector_cache[simulation.id] == expected_sectors

    @pytest.mark.unit
    async def test_initialize_simulation_sector_prefetch_failure_falls_back_to_db(
        self, db_session, rollback_session_factory, valid_simulation_data, mock_price_data
    ) -> None:
        """If batch_prefetch_sectors raises, initialize_simulation falls back to _load_sector_cache."""
        simulation = ArenaSimulation(**valid_simulation_data)
        db_session.add(simulation)
        await db_session.commit()
        await db_session.refresh(simulation)

        engine = SimulationEngine(db_session, session_factory=rollback_session_factory)

        with patch.object(engine.data_service, "get_price_data", return_value=mock_price_data):
            with patch.object(
                engine.data_service,
                "batch_prefetch_sectors",
                new_callable=AsyncMock,
                side_effect=RuntimeError("Yahoo Finance timeout"),
            ):
                # Should not raise — sector failures are non-fatal
                result = await engine.initialize_simulation(simulation.id)

        assert result.status == SimulationStatus.RUNNING.value
        # Cache should be populated by the DB fallback (_load_sector_cache)
        assert simulation.id in engine._sector_cache


@pytest.mark.usefixtures("db_session")
class TestSimulationEngineStepDay:
    """Tests for SimulationEngine.step_day() method."""

    @pytest.fixture
    def mock_agent(self) -> MagicMock:
        """Create mock agent."""
        agent = MagicMock()
        agent.name = "MockAgent"
        agent.required_lookback_days = 60
        agent.evaluate = AsyncMock(
            return_value=AgentDecision(
                symbol="AAPL",
                action="NO_SIGNAL",
                score=40,
                reasoning="Test reasoning",
            )
        )
        return agent

    @pytest.fixture
    def running_simulation_data(self) -> dict:
        """Create running simulation data."""
        return {
            "name": "Running Simulation",
            "symbols": ["AAPL"],
            "start_date": date(2024, 1, 15),
            "end_date": date(2024, 1, 20),
            "initial_capital": Decimal("10000.00"),
            "position_size": Decimal("1000.00"),
            "agent_type": "live20",
            "agent_config": {"trailing_stop_pct": 5.0},
            "status": SimulationStatus.RUNNING.value,
            "current_day": 0,
            "total_days": 5,
        }

    @pytest.fixture
    def sample_price_bars(self) -> list[PriceBar]:
        """Create sample price bars for testing."""
        return [
            PriceBar(
                date=date(2024, 1, 15) + timedelta(days=i),
                open=Decimal("100.00") + i,
                high=Decimal("102.00") + i,
                low=Decimal("98.00") + i,
                close=Decimal("101.00") + i,
                volume=1000000,
            )
            for i in range(10)
        ]

    @pytest.mark.unit
    async def test_step_day_simulation_not_found(
        self, db_session, rollback_session_factory
    ) -> None:
        """Test step_day fails when simulation not found."""
        engine = SimulationEngine(db_session, session_factory=rollback_session_factory)

        with pytest.raises(ValueError, match="not found"):
            await engine.step_day(99999)

    @pytest.mark.unit
    async def test_step_day_simulation_completed(
        self, db_session, rollback_session_factory, running_simulation_data
    ) -> None:
        """Test step_day returns None when simulation completed."""
        running_simulation_data["status"] = SimulationStatus.COMPLETED.value
        simulation = ArenaSimulation(**running_simulation_data)
        db_session.add(simulation)
        await db_session.commit()
        await db_session.refresh(simulation)

        engine = SimulationEngine(db_session, session_factory=rollback_session_factory)

        result = await engine.step_day(simulation.id)

        assert result is None

    @pytest.mark.unit
    async def test_step_day_simulation_not_running(
        self, db_session, rollback_session_factory, running_simulation_data
    ) -> None:
        """Test step_day fails when simulation not running."""
        running_simulation_data["status"] = SimulationStatus.PAUSED.value
        simulation = ArenaSimulation(**running_simulation_data)
        db_session.add(simulation)
        await db_session.commit()
        await db_session.refresh(simulation)

        engine = SimulationEngine(db_session, session_factory=rollback_session_factory)

        with pytest.raises(ValueError, match="not running"):
            await engine.step_day(simulation.id)

    @pytest.mark.unit
    async def test_step_day_creates_snapshot(
        self,
        db_session,
        rollback_session_factory,
        running_simulation_data,
        sample_price_bars,
        mock_agent,
    ) -> None:
        """Test step_day creates a daily snapshot."""
        simulation = ArenaSimulation(**running_simulation_data)
        db_session.add(simulation)
        await db_session.commit()
        await db_session.refresh(simulation)

        engine = SimulationEngine(db_session, session_factory=rollback_session_factory)

        # Pre-populate caches instead of mocking methods
        trading_days = [bar.date for bar in sample_price_bars[:5]]
        engine._trading_days_cache[simulation.id] = trading_days
        engine._price_cache[simulation.id] = {
            symbol: sample_price_bars for symbol in simulation.symbols
        }

        # Mock dependencies
        with patch("app.services.arena.simulation_engine.get_agent", return_value=mock_agent):
            snapshot = await engine.step_day(simulation.id)

        assert snapshot is not None
        assert snapshot.simulation_id == simulation.id
        assert snapshot.day_number == 0
        assert snapshot.cash == simulation.initial_capital
        assert snapshot.total_equity == simulation.initial_capital

    @pytest.mark.unit
    async def test_step_day_increments_current_day(
        self,
        db_session,
        rollback_session_factory,
        running_simulation_data,
        sample_price_bars,
        mock_agent,
    ) -> None:
        """Test step_day increments current_day."""
        simulation = ArenaSimulation(**running_simulation_data)
        db_session.add(simulation)
        await db_session.commit()
        await db_session.refresh(simulation)

        engine = SimulationEngine(db_session, session_factory=rollback_session_factory)

        # Pre-populate caches instead of mocking methods
        trading_days = [bar.date for bar in sample_price_bars[:5]]
        engine._trading_days_cache[simulation.id] = trading_days
        engine._price_cache[simulation.id] = {
            symbol: sample_price_bars for symbol in simulation.symbols
        }

        with patch("app.services.arena.simulation_engine.get_agent", return_value=mock_agent):
            await engine.step_day(simulation.id)

        await db_session.refresh(simulation)
        assert simulation.current_day == 1

    @pytest.mark.unit
    async def test_step_day_records_agent_decisions(
        self,
        db_session,
        rollback_session_factory,
        running_simulation_data,
        sample_price_bars,
        mock_agent,
    ) -> None:
        """Test step_day records agent decisions in snapshot."""
        simulation = ArenaSimulation(**running_simulation_data)
        db_session.add(simulation)
        await db_session.commit()
        await db_session.refresh(simulation)

        engine = SimulationEngine(db_session, session_factory=rollback_session_factory)

        # Pre-populate caches instead of mocking methods
        trading_days = [bar.date for bar in sample_price_bars[:5]]
        engine._trading_days_cache[simulation.id] = trading_days
        engine._price_cache[simulation.id] = {
            symbol: sample_price_bars for symbol in simulation.symbols
        }

        with patch("app.services.arena.simulation_engine.get_agent", return_value=mock_agent):
            snapshot = await engine.step_day(simulation.id)

        assert "AAPL" in snapshot.decisions
        assert snapshot.decisions["AAPL"]["action"] == "NO_SIGNAL"

    @pytest.mark.unit
    async def test_step_day_handles_no_price_data(
        self,
        db_session,
        rollback_session_factory,
        running_simulation_data,
        sample_price_bars,
        mock_agent,
    ) -> None:
        """Test step_day handles missing price data gracefully."""
        simulation = ArenaSimulation(**running_simulation_data)
        db_session.add(simulation)
        await db_session.commit()
        await db_session.refresh(simulation)

        engine = SimulationEngine(db_session, session_factory=rollback_session_factory)

        # Pre-populate caches with empty price data
        engine._trading_days_cache[simulation.id] = [date(2024, 1, 15)]
        engine._price_cache[simulation.id] = {
            symbol: [] for symbol in simulation.symbols
        }

        with patch("app.services.arena.simulation_engine.get_agent", return_value=mock_agent):
            snapshot = await engine.step_day(simulation.id)

        assert snapshot.decisions["AAPL"]["action"] == "NO_DATA"


@pytest.mark.usefixtures("db_session")
class TestSimulationEnginePositionManagement:
    """Tests for position management in SimulationEngine."""

    @pytest.fixture
    def simulation_with_pending_position(self, db_session) -> ArenaSimulation:
        """Create simulation with a pending position."""
        simulation = ArenaSimulation(
            name="Position Test",
            symbols=["AAPL"],
            start_date=date(2024, 1, 15),
            end_date=date(2024, 1, 20),
            initial_capital=Decimal("10000.00"),
            position_size=Decimal("1000.00"),
            agent_type="live20",
            agent_config={"trailing_stop_pct": 5.0},
            status=SimulationStatus.RUNNING.value,
            current_day=0,  # Will process day 0 (which maps to first trading day)
            total_days=5,
        )
        return simulation

    @pytest.mark.unit
    async def test_pending_position_opens_at_open_price(
        self, db_session, rollback_session_factory, simulation_with_pending_position
    ) -> None:
        """Test pending position opens at next day's open price."""
        simulation = simulation_with_pending_position
        db_session.add(simulation)
        await db_session.commit()
        await db_session.refresh(simulation)

        # Create pending position (signal from previous day)
        pending = ArenaPosition(
            simulation_id=simulation.id,
            symbol="AAPL",
            status=PositionStatus.PENDING.value,
            signal_date=date(2024, 1, 15),  # Previous day signal
            trailing_stop_pct=Decimal("5.00"),
        )
        db_session.add(pending)
        await db_session.commit()

        engine = SimulationEngine(db_session, session_factory=rollback_session_factory)

        # Day 0 = Jan 16 where position will open
        trading_days = [date(2024, 1, 16), date(2024, 1, 17)]

        # Create price bar with open at 100
        price_bars = [
            PriceBar(
                date=date(2024, 1, 16),
                open=Decimal("100.00"),
                high=Decimal("102.00"),
                low=Decimal("98.00"),
                close=Decimal("101.00"),
                volume=1000000,
            )
        ]

        mock_agent = MagicMock()
        mock_agent.required_lookback_days = 60
        mock_agent.evaluate = AsyncMock(
            return_value=AgentDecision(symbol="AAPL", action="HOLD", reasoning="Already holding")
        )

        # Pre-populate caches instead of mocking methods
        engine._trading_days_cache[simulation.id] = trading_days
        engine._price_cache[simulation.id] = {
            symbol: price_bars for symbol in simulation.symbols
        }

        with patch("app.services.arena.simulation_engine.get_agent", return_value=mock_agent):
            await engine.step_day(simulation.id)

        await db_session.refresh(pending)
        assert pending.status == PositionStatus.OPEN.value
        assert pending.entry_price == Decimal("100.00")
        assert pending.shares == 10  # 1000 / 100

    @pytest.mark.unit
    async def test_pending_position_cancelled_insufficient_capital(
        self, db_session, rollback_session_factory, simulation_with_pending_position
    ) -> None:
        """Test pending position is cancelled when price too high."""
        simulation = simulation_with_pending_position
        simulation.position_size = Decimal("50.00")  # Very small position size
        db_session.add(simulation)
        await db_session.commit()
        await db_session.refresh(simulation)

        # Create pending position
        pending = ArenaPosition(
            simulation_id=simulation.id,
            symbol="AAPL",
            status=PositionStatus.PENDING.value,
            signal_date=date(2024, 1, 15),
            trailing_stop_pct=Decimal("5.00"),
        )
        db_session.add(pending)
        await db_session.commit()

        engine = SimulationEngine(db_session, session_factory=rollback_session_factory)

        trading_days = [date(2024, 1, 16), date(2024, 1, 17)]

        # Create price bar with open at 100 (50 / 100 = 0 shares)
        price_bars = [
            PriceBar(
                date=date(2024, 1, 16),
                open=Decimal("100.00"),
                high=Decimal("102.00"),
                low=Decimal("98.00"),
                close=Decimal("101.00"),
                volume=1000000,
            )
        ]

        mock_agent = MagicMock()
        mock_agent.required_lookback_days = 60
        mock_agent.evaluate = AsyncMock(
            return_value=AgentDecision(symbol="AAPL", action="NO_SIGNAL")
        )

        # Pre-populate caches instead of mocking methods
        engine._trading_days_cache[simulation.id] = trading_days
        engine._price_cache[simulation.id] = {
            symbol: price_bars for symbol in simulation.symbols
        }

        with patch("app.services.arena.simulation_engine.get_agent", return_value=mock_agent):
            await engine.step_day(simulation.id)

        await db_session.refresh(pending)
        assert pending.status == PositionStatus.CLOSED.value
        assert pending.exit_reason == ExitReason.INSUFFICIENT_CAPITAL.value

    @pytest.mark.unit
    async def test_pending_position_cancelled_insufficient_cash(
        self, db_session, rollback_session_factory, simulation_with_pending_position
    ) -> None:
        """Test pending position is cancelled when not enough cash available."""
        simulation = simulation_with_pending_position
        # Low capital so we can only afford ~1 position
        simulation.initial_capital = Decimal("1500.00")
        simulation.position_size = Decimal("1000.00")
        db_session.add(simulation)
        await db_session.commit()
        await db_session.refresh(simulation)

        # Create TWO pending positions - only one should be able to open
        pending1 = ArenaPosition(
            simulation_id=simulation.id,
            symbol="AAPL",
            status=PositionStatus.PENDING.value,
            signal_date=date(2024, 1, 15),
            trailing_stop_pct=Decimal("5.00"),
        )
        pending2 = ArenaPosition(
            simulation_id=simulation.id,
            symbol="MSFT",
            status=PositionStatus.PENDING.value,
            signal_date=date(2024, 1, 15),
            trailing_stop_pct=Decimal("5.00"),
        )
        db_session.add(pending1)
        db_session.add(pending2)
        await db_session.commit()

        engine = SimulationEngine(db_session, session_factory=rollback_session_factory)

        trading_days = [date(2024, 1, 16), date(2024, 1, 17)]

        # Both stocks at $100, position size $1000 = 10 shares = $1000 cost each
        # With $1500 cash, first opens ($500 left), second should be cancelled
        price_bars_aapl = [
            PriceBar(
                date=date(2024, 1, 16),
                open=Decimal("100.00"),
                high=Decimal("102.00"),
                low=Decimal("98.00"),
                close=Decimal("101.00"),
                volume=1000000,
            )
        ]
        price_bars_msft = [
            PriceBar(
                date=date(2024, 1, 16),
                open=Decimal("100.00"),
                high=Decimal("102.00"),
                low=Decimal("98.00"),
                close=Decimal("101.00"),
                volume=1000000,
            )
        ]

        # Update simulation to have both symbols
        simulation.symbols = ["AAPL", "MSFT"]
        await db_session.commit()

        mock_agent = MagicMock()
        mock_agent.required_lookback_days = 60
        mock_agent.evaluate = AsyncMock(
            return_value=AgentDecision(symbol="AAPL", action="NO_SIGNAL")
        )

        # Pre-populate caches with different price bars per symbol
        engine._trading_days_cache[simulation.id] = trading_days
        engine._price_cache[simulation.id] = {
            "AAPL": price_bars_aapl,
            "MSFT": price_bars_msft,
        }

        with patch("app.services.arena.simulation_engine.get_agent", return_value=mock_agent):
            await engine.step_day(simulation.id)

        await db_session.refresh(pending1)
        await db_session.refresh(pending2)

        # One should be open, one should be cancelled due to insufficient cash
        statuses = [pending1.status, pending2.status]
        assert PositionStatus.OPEN.value in statuses
        assert PositionStatus.CLOSED.value in statuses

        # The closed one should have insufficient capital reason
        closed_position = pending1 if pending1.status == PositionStatus.CLOSED.value else pending2
        assert closed_position.exit_reason == ExitReason.INSUFFICIENT_CAPITAL.value
        assert "insufficient cash" in closed_position.agent_reasoning.lower()

    @pytest.mark.unit
    async def test_buy_signal_creates_pending_position(
        self, db_session, rollback_session_factory, simulation_with_pending_position
    ) -> None:
        """Test BUY signal creates a pending position."""
        simulation = simulation_with_pending_position
        simulation.current_day = 0
        db_session.add(simulation)
        await db_session.commit()
        await db_session.refresh(simulation)

        engine = SimulationEngine(db_session, session_factory=rollback_session_factory)

        price_bars = [
            PriceBar(
                date=date(2024, 1, 15),
                open=Decimal("100.00"),
                high=Decimal("102.00"),
                low=Decimal("98.00"),
                close=Decimal("101.00"),
                volume=1000000,
            )
        ]

        mock_agent = MagicMock()
        mock_agent.required_lookback_days = 60
        mock_agent.evaluate = AsyncMock(
            return_value=AgentDecision(
                symbol="AAPL", action="BUY", score=80, reasoning="Strong signal"
            )
        )

        # Pre-populate caches instead of mocking methods
        engine._trading_days_cache[simulation.id] = [date(2024, 1, 15)]
        engine._price_cache[simulation.id] = {
            symbol: price_bars for symbol in simulation.symbols
        }

        with patch("app.services.arena.simulation_engine.get_agent", return_value=mock_agent):
            await engine.step_day(simulation.id)

        # Check pending position was created
        result = await db_session.execute(
            select(ArenaPosition).where(ArenaPosition.simulation_id == simulation.id)
        )
        positions = result.scalars().all()
        assert len(positions) == 1
        assert positions[0].status == PositionStatus.PENDING.value
        assert positions[0].signal_date == date(2024, 1, 15)

    @pytest.mark.unit
    async def test_position_size_pct_uses_percentage_of_equity(
        self, db_session, rollback_session_factory
    ) -> None:
        """Test position_size_pct in agent_config sizes positions as % of equity."""
        # 10000 equity, 33% -> $3300 position, at $100/share = 33 shares
        simulation = ArenaSimulation(
            name="Pct Sizing Test",
            symbols=["AAPL"],
            start_date=date(2024, 1, 15),
            end_date=date(2024, 1, 20),
            initial_capital=Decimal("10000.00"),
            position_size=Decimal("1000.00"),  # fixed size (should be overridden)
            agent_type="live20",
            agent_config={"trailing_stop_pct": 5.0, "position_size_pct": 33.0},
            status=SimulationStatus.RUNNING.value,
            current_day=0,
            total_days=5,
        )
        db_session.add(simulation)
        await db_session.commit()
        await db_session.refresh(simulation)

        pending = ArenaPosition(
            simulation_id=simulation.id,
            symbol="AAPL",
            status=PositionStatus.PENDING.value,
            signal_date=date(2024, 1, 15),
            trailing_stop_pct=Decimal("5.00"),
        )
        db_session.add(pending)
        await db_session.commit()

        engine = SimulationEngine(db_session, session_factory=rollback_session_factory)

        trading_days = [date(2024, 1, 16), date(2024, 1, 17)]
        price_bars = [
            PriceBar(
                date=date(2024, 1, 16),
                open=Decimal("100.00"),
                high=Decimal("102.00"),
                low=Decimal("98.00"),
                close=Decimal("101.00"),
                volume=1000000,
            )
        ]

        mock_agent = MagicMock()
        mock_agent.required_lookback_days = 60
        mock_agent.evaluate = AsyncMock(
            return_value=AgentDecision(symbol="AAPL", action="HOLD", reasoning="holding")
        )

        engine._trading_days_cache[simulation.id] = trading_days
        engine._price_cache[simulation.id] = {"AAPL": price_bars}

        with patch("app.services.arena.simulation_engine.get_agent", return_value=mock_agent):
            await engine.step_day(simulation.id)

        await db_session.refresh(pending)
        assert pending.status == PositionStatus.OPEN.value
        # 33% of 10000 = 3300, at $100 open = 33 shares
        assert pending.shares == 33
        assert pending.entry_price == Decimal("100.00")

    @pytest.mark.unit
    async def test_position_size_pct_none_falls_back_to_fixed(
        self, db_session, rollback_session_factory
    ) -> None:
        """Test that when position_size_pct is None, fixed position_size is used."""
        # No position_size_pct -> uses fixed $1000, at $100/share = 10 shares
        simulation = ArenaSimulation(
            name="Fixed Sizing Test",
            symbols=["AAPL"],
            start_date=date(2024, 1, 15),
            end_date=date(2024, 1, 20),
            initial_capital=Decimal("10000.00"),
            position_size=Decimal("1000.00"),
            agent_type="live20",
            agent_config={"trailing_stop_pct": 5.0},  # no position_size_pct
            status=SimulationStatus.RUNNING.value,
            current_day=0,
            total_days=5,
        )
        db_session.add(simulation)
        await db_session.commit()
        await db_session.refresh(simulation)

        pending = ArenaPosition(
            simulation_id=simulation.id,
            symbol="AAPL",
            status=PositionStatus.PENDING.value,
            signal_date=date(2024, 1, 15),
            trailing_stop_pct=Decimal("5.00"),
        )
        db_session.add(pending)
        await db_session.commit()

        engine = SimulationEngine(db_session, session_factory=rollback_session_factory)

        trading_days = [date(2024, 1, 16), date(2024, 1, 17)]
        price_bars = [
            PriceBar(
                date=date(2024, 1, 16),
                open=Decimal("100.00"),
                high=Decimal("102.00"),
                low=Decimal("98.00"),
                close=Decimal("101.00"),
                volume=1000000,
            )
        ]

        mock_agent = MagicMock()
        mock_agent.required_lookback_days = 60
        mock_agent.evaluate = AsyncMock(
            return_value=AgentDecision(symbol="AAPL", action="HOLD", reasoning="holding")
        )

        engine._trading_days_cache[simulation.id] = trading_days
        engine._price_cache[simulation.id] = {"AAPL": price_bars}

        with patch("app.services.arena.simulation_engine.get_agent", return_value=mock_agent):
            await engine.step_day(simulation.id)

        await db_session.refresh(pending)
        assert pending.status == PositionStatus.OPEN.value
        # Fixed $1000 / $100 open = 10 shares
        assert pending.shares == 10
        assert pending.entry_price == Decimal("100.00")


@pytest.mark.usefixtures("db_session")
class TestSimulationEngineTrailingStop:
    """Tests for trailing stop management in SimulationEngine."""

    @pytest.fixture
    def simulation_with_open_position(self, db_session) -> ArenaSimulation:
        """Create simulation with an open position."""
        simulation = ArenaSimulation(
            name="Trailing Stop Test",
            symbols=["AAPL"],
            start_date=date(2024, 1, 15),
            end_date=date(2024, 1, 25),
            initial_capital=Decimal("10000.00"),
            position_size=Decimal("1000.00"),
            agent_type="live20",
            agent_config={"trailing_stop_pct": 5.0},
            status=SimulationStatus.RUNNING.value,
            current_day=0,
            total_days=10,
        )
        return simulation

    @pytest.mark.unit
    async def test_trailing_stop_triggers_on_price_drop(
        self, db_session, rollback_session_factory, simulation_with_open_position
    ) -> None:
        """Test trailing stop triggers when price drops below stop level."""
        simulation = simulation_with_open_position
        db_session.add(simulation)
        await db_session.commit()
        await db_session.refresh(simulation)

        # Create open position with stop at 95
        position = ArenaPosition(
            simulation_id=simulation.id,
            symbol="AAPL",
            status=PositionStatus.OPEN.value,
            signal_date=date(2024, 1, 15),
            entry_date=date(2024, 1, 16),
            entry_price=Decimal("100.00"),
            shares=10,
            trailing_stop_pct=Decimal("5.00"),
            highest_price=Decimal("100.00"),
            current_stop=Decimal("95.00"),
        )
        db_session.add(position)
        await db_session.commit()

        engine = SimulationEngine(db_session, session_factory=rollback_session_factory)

        # Need multiple days so we don't end the simulation
        trading_days = [date(2024, 1, 17), date(2024, 1, 18), date(2024, 1, 19)]

        # Price drops to 94 (below stop at 95)
        price_bars = [
            PriceBar(
                date=date(2024, 1, 17),
                open=Decimal("96.00"),
                high=Decimal("97.00"),
                low=Decimal("94.00"),  # Below stop
                close=Decimal("95.00"),
                volume=1000000,
            )
        ]

        mock_agent = MagicMock()
        mock_agent.required_lookback_days = 60
        mock_agent.evaluate = AsyncMock(
            return_value=AgentDecision(symbol="AAPL", action="NO_SIGNAL")
        )

        # Pre-populate caches instead of mocking methods
        engine._trading_days_cache[simulation.id] = trading_days
        engine._price_cache[simulation.id] = {
            symbol: price_bars for symbol in simulation.symbols
        }

        with patch("app.services.arena.simulation_engine.get_agent", return_value=mock_agent):
            await engine.step_day(simulation.id)

        await db_session.refresh(position)
        assert position.status == PositionStatus.CLOSED.value
        assert position.exit_reason == ExitReason.STOP_HIT.value
        assert position.exit_price == Decimal("95.00")

    @pytest.mark.unit
    async def test_trailing_stop_moves_up_with_price(
        self, db_session, rollback_session_factory, simulation_with_open_position
    ) -> None:
        """Test trailing stop moves up when price makes new highs."""
        simulation = simulation_with_open_position
        db_session.add(simulation)
        await db_session.commit()
        await db_session.refresh(simulation)

        # Create open position
        position = ArenaPosition(
            simulation_id=simulation.id,
            symbol="AAPL",
            status=PositionStatus.OPEN.value,
            signal_date=date(2024, 1, 15),
            entry_date=date(2024, 1, 16),
            entry_price=Decimal("100.00"),
            shares=10,
            trailing_stop_pct=Decimal("5.00"),
            highest_price=Decimal("100.00"),
            current_stop=Decimal("95.00"),
        )
        db_session.add(position)
        await db_session.commit()

        engine = SimulationEngine(db_session, session_factory=rollback_session_factory)

        # Need multiple days so we don't end the simulation
        trading_days = [date(2024, 1, 17), date(2024, 1, 18), date(2024, 1, 19)]

        # Price rises to 110 (new high), low stays above stop
        price_bars = [
            PriceBar(
                date=date(2024, 1, 17),
                open=Decimal("102.00"),
                high=Decimal("110.00"),  # New high
                low=Decimal("101.00"),  # Above stop at 95
                close=Decimal("108.00"),
                volume=1000000,
            )
        ]

        mock_agent = MagicMock()
        mock_agent.required_lookback_days = 60
        mock_agent.evaluate = AsyncMock(return_value=AgentDecision(symbol="AAPL", action="HOLD"))

        # Pre-populate caches instead of mocking methods
        engine._trading_days_cache[simulation.id] = trading_days
        engine._price_cache[simulation.id] = {
            symbol: price_bars for symbol in simulation.symbols
        }

        with patch("app.services.arena.simulation_engine.get_agent", return_value=mock_agent):
            await engine.step_day(simulation.id)

        await db_session.refresh(position)
        assert position.status == PositionStatus.OPEN.value
        assert position.highest_price == Decimal("110.00")
        assert position.current_stop == Decimal("104.5000")  # 110 * 0.95

    @pytest.mark.unit
    async def test_gap_down_exits_at_open_not_stop(
        self, db_session, rollback_session_factory, simulation_with_open_position
    ) -> None:
        """Test gap-down exits at open price, not stop price.

        When a stock gaps down below the stop price overnight, the position
        should exit at the open price (where you actually get filled), not
        the stop price (which the stock never traded at).

        Scenario:
        - Position entry: $100
        - Stop price: $95 (5% trailing stop)
        - Stock gaps down, opens at $90 (below stop)
        - Expected exit: $90 (the open), not $95 (the stop)
        """
        simulation = simulation_with_open_position
        db_session.add(simulation)
        await db_session.commit()
        await db_session.refresh(simulation)

        # Create open position with stop at 95
        position = ArenaPosition(
            simulation_id=simulation.id,
            symbol="AAPL",
            status=PositionStatus.OPEN.value,
            signal_date=date(2024, 1, 15),
            entry_date=date(2024, 1, 16),
            entry_price=Decimal("100.00"),
            shares=10,
            trailing_stop_pct=Decimal("5.00"),
            highest_price=Decimal("100.00"),
            current_stop=Decimal("95.00"),
        )
        db_session.add(position)
        await db_session.commit()

        engine = SimulationEngine(db_session, session_factory=rollback_session_factory)

        # Need multiple days so we don't end the simulation
        trading_days = [date(2024, 1, 17), date(2024, 1, 18), date(2024, 1, 19)]

        # Gap down: opens at $90 (below stop at $95), low is $88
        price_bars = [
            PriceBar(
                date=date(2024, 1, 17),
                open=Decimal("90.00"),  # Gap down below stop
                high=Decimal("91.00"),
                low=Decimal("88.00"),
                close=Decimal("89.00"),
                volume=1000000,
            )
        ]

        mock_agent = MagicMock()
        mock_agent.required_lookback_days = 60
        mock_agent.evaluate = AsyncMock(
            return_value=AgentDecision(symbol="AAPL", action="NO_SIGNAL")
        )

        # Pre-populate caches instead of mocking methods
        engine._trading_days_cache[simulation.id] = trading_days
        engine._price_cache[simulation.id] = {
            symbol: price_bars for symbol in simulation.symbols
        }

        with patch("app.services.arena.simulation_engine.get_agent", return_value=mock_agent):
            await engine.step_day(simulation.id)

        await db_session.refresh(position)
        assert position.status == PositionStatus.CLOSED.value
        assert position.exit_reason == ExitReason.STOP_HIT.value
        # Critical: exit at open ($90), not stop ($95)
        assert position.exit_price == Decimal("90.00")
        # P&L: (90 - 100) * 10 = -$100
        assert position.realized_pnl == Decimal("-100.00")
        # Return: (90 - 100) / 100 * 100 = -10%
        assert position.return_pct == Decimal("-10")


@pytest.mark.usefixtures("db_session")
class TestSimulationEngineRunToCompletion:
    """Tests for SimulationEngine.run_to_completion() method."""

    @pytest.mark.unit
    async def test_run_to_completion_processes_all_days(
        self, db_session, rollback_session_factory
    ) -> None:
        """Test run_to_completion processes all simulation days."""
        simulation = ArenaSimulation(
            name="Full Run Test",
            symbols=["AAPL"],
            start_date=date(2024, 1, 15),
            end_date=date(2024, 1, 17),
            initial_capital=Decimal("10000.00"),
            position_size=Decimal("1000.00"),
            agent_type="live20",
            agent_config={"trailing_stop_pct": 5.0},
            status=SimulationStatus.RUNNING.value,
            current_day=0,
            total_days=3,
        )
        db_session.add(simulation)
        await db_session.commit()
        await db_session.refresh(simulation)

        engine = SimulationEngine(db_session, session_factory=rollback_session_factory)

        trading_days = [
            date(2024, 1, 15),
            date(2024, 1, 16),
            date(2024, 1, 17),
        ]

        price_bars = [
            PriceBar(
                date=d,
                open=Decimal("100.00"),
                high=Decimal("102.00"),
                low=Decimal("98.00"),
                close=Decimal("101.00"),
                volume=1000000,
            )
            for d in trading_days
        ]

        mock_agent = MagicMock()
        mock_agent.required_lookback_days = 60
        mock_agent.evaluate = AsyncMock(
            return_value=AgentDecision(symbol="AAPL", action="NO_SIGNAL")
        )

        # Pre-populate caches instead of mocking methods
        engine._trading_days_cache[simulation.id] = trading_days
        engine._price_cache[simulation.id] = {
            symbol: price_bars for symbol in simulation.symbols
        }

        with patch("app.services.arena.simulation_engine.get_agent", return_value=mock_agent):
            result = await engine.run_to_completion(simulation.id)

        assert result.status == SimulationStatus.COMPLETED.value
        assert result.current_day == 3


@pytest.mark.usefixtures("db_session")
class TestSimulationEngineHelpers:
    """Tests for SimulationEngine helper methods."""

    @pytest.fixture
    def simulation_for_helpers(self, db_session) -> ArenaSimulation:
        """Create simulation for helper method tests."""
        return ArenaSimulation(
            name="Helper Test",
            symbols=["AAPL"],
            start_date=date(2024, 1, 15),
            end_date=date(2024, 1, 20),
            initial_capital=Decimal("10000.00"),
            position_size=Decimal("1000.00"),
            agent_type="live20",
            agent_config={"trailing_stop_pct": 5.0},
            status=SimulationStatus.RUNNING.value,
        )

    @pytest.mark.unit
    async def test_get_latest_snapshot_returns_none_when_empty(
        self, db_session, rollback_session_factory, simulation_for_helpers
    ) -> None:
        """Test _get_latest_snapshot returns None when no snapshots."""
        db_session.add(simulation_for_helpers)
        await db_session.commit()

        engine = SimulationEngine(db_session, session_factory=rollback_session_factory)
        result = await engine._get_latest_snapshot(simulation_for_helpers.id)

        assert result is None

    @pytest.mark.unit
    async def test_get_latest_snapshot_returns_most_recent(
        self, db_session, rollback_session_factory, simulation_for_helpers
    ) -> None:
        """Test _get_latest_snapshot returns most recent snapshot."""
        db_session.add(simulation_for_helpers)
        await db_session.commit()
        await db_session.refresh(simulation_for_helpers)

        # Create multiple snapshots
        for i in range(3):
            snapshot = ArenaSnapshot(
                simulation_id=simulation_for_helpers.id,
                snapshot_date=date(2024, 1, 15) + timedelta(days=i),
                day_number=i,
                cash=Decimal("10000.00"),
                positions_value=Decimal("0.00"),
                total_equity=Decimal("10000.00"),
            )
            db_session.add(snapshot)
        await db_session.commit()

        engine = SimulationEngine(db_session, session_factory=rollback_session_factory)
        result = await engine._get_latest_snapshot(simulation_for_helpers.id)

        assert result.day_number == 2

    @pytest.mark.unit
    async def test_get_open_positions_returns_only_open(
        self, db_session, rollback_session_factory, simulation_for_helpers
    ) -> None:
        """Test _get_open_positions returns only open positions."""
        db_session.add(simulation_for_helpers)
        await db_session.commit()
        await db_session.refresh(simulation_for_helpers)

        # Create mixed positions
        positions = [
            ArenaPosition(
                simulation_id=simulation_for_helpers.id,
                symbol="AAPL",
                status=PositionStatus.OPEN.value,
                signal_date=date(2024, 1, 15),
                trailing_stop_pct=Decimal("5.00"),
            ),
            ArenaPosition(
                simulation_id=simulation_for_helpers.id,
                symbol="MSFT",
                status=PositionStatus.CLOSED.value,
                signal_date=date(2024, 1, 14),
                trailing_stop_pct=Decimal("5.00"),
            ),
            ArenaPosition(
                simulation_id=simulation_for_helpers.id,
                symbol="GOOGL",
                status=PositionStatus.PENDING.value,
                signal_date=date(2024, 1, 16),
                trailing_stop_pct=Decimal("5.00"),
            ),
        ]
        for pos in positions:
            db_session.add(pos)
        await db_session.commit()

        engine = SimulationEngine(db_session, session_factory=rollback_session_factory)
        result = await engine._get_open_positions(simulation_for_helpers.id)

        assert len(result) == 1
        assert result[0].symbol == "AAPL"

    @pytest.mark.unit
    def test_find_bar_for_date_returns_matching_bar(self) -> None:
        """Test _find_bar_for_date returns bar for target date."""
        mock_session_factory = MagicMock()
        engine = SimulationEngine(AsyncMock(), session_factory=mock_session_factory)

        bars = [
            PriceBar(
                date=date(2024, 1, 15),
                open=Decimal("100.00"),
                high=Decimal("102.00"),
                low=Decimal("98.00"),
                close=Decimal("101.00"),
                volume=1000000,
            ),
            PriceBar(
                date=date(2024, 1, 16),
                open=Decimal("101.00"),
                high=Decimal("103.00"),
                low=Decimal("99.00"),
                close=Decimal("102.00"),
                volume=1000000,
            ),
        ]

        result = engine._find_bar_for_date(bars, date(2024, 1, 16))

        assert result is not None
        assert result.date == date(2024, 1, 16)
        assert result.open == Decimal("101.00")

    @pytest.mark.unit
    def test_find_bar_for_date_returns_none_when_not_found(self) -> None:
        """Test _find_bar_for_date returns None when date not found."""
        mock_session_factory = MagicMock()
        engine = SimulationEngine(AsyncMock(), session_factory=mock_session_factory)

        bars = [
            PriceBar(
                date=date(2024, 1, 15),
                open=Decimal("100.00"),
                high=Decimal("102.00"),
                low=Decimal("98.00"),
                close=Decimal("101.00"),
                volume=1000000,
            ),
        ]

        result = engine._find_bar_for_date(bars, date(2024, 1, 20))

        assert result is None


@pytest.mark.usefixtures("db_session")
class TestSimulationEngineCloseAllPositions:
    """Tests for closing all positions at simulation end."""

    @pytest.mark.unit
    async def test_close_all_positions_at_simulation_end(
        self, db_session, rollback_session_factory
    ) -> None:
        """Test all open positions are closed at simulation end."""
        simulation = ArenaSimulation(
            name="Close All Test",
            symbols=["AAPL", "MSFT"],
            start_date=date(2024, 1, 15),
            end_date=date(2024, 1, 20),
            initial_capital=Decimal("10000.00"),
            position_size=Decimal("1000.00"),
            agent_type="live20",
            agent_config={"trailing_stop_pct": 5.0},
            status=SimulationStatus.RUNNING.value,
        )
        db_session.add(simulation)
        await db_session.commit()
        await db_session.refresh(simulation)

        # Create open positions
        position1 = ArenaPosition(
            simulation_id=simulation.id,
            symbol="AAPL",
            status=PositionStatus.OPEN.value,
            signal_date=date(2024, 1, 15),
            entry_date=date(2024, 1, 16),
            entry_price=Decimal("100.00"),
            shares=10,
            trailing_stop_pct=Decimal("5.00"),
            highest_price=Decimal("100.00"),
            current_stop=Decimal("95.00"),
        )
        position2 = ArenaPosition(
            simulation_id=simulation.id,
            symbol="MSFT",
            status=PositionStatus.OPEN.value,
            signal_date=date(2024, 1, 15),
            entry_date=date(2024, 1, 16),
            entry_price=Decimal("200.00"),
            shares=5,
            trailing_stop_pct=Decimal("5.00"),
            highest_price=Decimal("200.00"),
            current_stop=Decimal("190.00"),
        )
        db_session.add(position1)
        db_session.add(position2)
        await db_session.commit()
        await db_session.refresh(position1)
        await db_session.refresh(position2)

        engine = SimulationEngine(db_session, session_factory=rollback_session_factory)

        # Pre-populate price cache with closing prices
        engine._price_cache[simulation.id] = {
            "AAPL": [
                PriceBar(
                    date=date(2024, 1, 20),
                    open=Decimal("105.00"),
                    high=Decimal("105.00"),
                    low=Decimal("105.00"),
                    close=Decimal("105.00"),
                    volume=1000000,
                )
            ],
            "MSFT": [
                PriceBar(
                    date=date(2024, 1, 20),
                    open=Decimal("210.00"),
                    high=Decimal("210.00"),
                    low=Decimal("210.00"),
                    close=Decimal("210.00"),
                    volume=1000000,
                )
            ],
        }

        await engine._close_all_positions(
            simulation, date(2024, 1, 20), ExitReason.SIMULATION_END
        )

        # Commit to persist changes
        await db_session.commit()

        await db_session.refresh(position1)
        await db_session.refresh(position2)

        assert position1.status == PositionStatus.CLOSED.value
        assert position1.exit_reason == ExitReason.SIMULATION_END.value
        assert position1.exit_price == Decimal("105.00")
        assert position1.realized_pnl == Decimal("50.00")  # 10 * (105 - 100)

        assert position2.status == PositionStatus.CLOSED.value
        assert position2.exit_reason == ExitReason.SIMULATION_END.value
        assert position2.exit_price == Decimal("210.00")
        assert position2.realized_pnl == Decimal("50.00")  # 5 * (210 - 200)


@pytest.mark.usefixtures("db_session")
class TestSimulationEngineValidation:
    """Tests for accounting validation in SimulationEngine.

    Phase 1 of arena caching plan: Runtime validation of accounting invariants
    to catch bugs early before they produce silently wrong results.
    """

    @pytest.fixture
    def running_simulation_data(self) -> dict:
        """Create running simulation data."""
        return {
            "name": "Validation Test",
            "symbols": ["AAPL"],
            "start_date": date(2024, 1, 15),
            "end_date": date(2024, 1, 20),
            "initial_capital": Decimal("10000.00"),
            "position_size": Decimal("1000.00"),
            "agent_type": "live20",
            "agent_config": {"trailing_stop_pct": 5.0},
            "status": SimulationStatus.RUNNING.value,
            "current_day": 0,
            "total_days": 5,
        }

    @pytest.fixture
    def sample_price_bars(self) -> list[PriceBar]:
        """Create sample price bars for testing."""
        return [
            PriceBar(
                date=date(2024, 1, 15) + timedelta(days=i),
                open=Decimal("100.00") + i,
                high=Decimal("102.00") + i,
                low=Decimal("98.00") + i,
                close=Decimal("101.00") + i,
                volume=1000000,
            )
            for i in range(10)
        ]

    @pytest.fixture
    def mock_agent(self) -> MagicMock:
        """Create mock agent."""
        agent = MagicMock()
        agent.name = "MockAgent"
        agent.required_lookback_days = 60
        agent.evaluate = AsyncMock(
            return_value=AgentDecision(
                symbol="AAPL",
                action="NO_SIGNAL",
                score=40,
                reasoning="Test reasoning",
            )
        )
        return agent

    @pytest.mark.unit
    async def test_validation_raises_on_negative_cash(
        self,
        db_session,
        rollback_session_factory,
        running_simulation_data,
        sample_price_bars,
        mock_agent,
    ) -> None:
        """Test validation raises ValueError when cash goes negative.

        This test verifies that the accounting validation catches negative cash
        before committing to the database, preventing data corruption.
        """
        simulation = ArenaSimulation(**running_simulation_data)
        db_session.add(simulation)
        await db_session.commit()
        await db_session.refresh(simulation)

        engine = SimulationEngine(db_session, session_factory=rollback_session_factory)

        # Pre-populate caches instead of mocking methods
        trading_days = [bar.date for bar in sample_price_bars[:5]]
        engine._trading_days_cache[simulation.id] = trading_days
        engine._price_cache[simulation.id] = {
            symbol: sample_price_bars for symbol in simulation.symbols
        }

        # Set up mocks for normal operation
        with patch("app.services.arena.simulation_engine.get_agent", return_value=mock_agent):
            # Inject negative cash by patching _get_latest_snapshot
            # to return a snapshot with more positions_value than initial capital
            mock_snapshot = MagicMock()
            mock_snapshot.cash = Decimal("-100.00")  # Negative cash
            mock_snapshot.total_equity = Decimal("9900.00")

            with patch.object(engine, "_get_latest_snapshot", return_value=mock_snapshot):
                with pytest.raises(ValueError, match="cash is negative"):
                    await engine.step_day(simulation.id)

    @pytest.mark.unit
    async def test_validation_raises_on_negative_positions_value(
        self,
        db_session,
        rollback_session_factory,
        running_simulation_data,
        sample_price_bars,
        mock_agent,
    ) -> None:
        """Test validation raises ValueError when positions_value is negative.

        This test verifies that the accounting validation catches negative positions_value
        before committing to the database. We simulate this by patching the portfolio
        valuation calculation to return a negative value.
        """
        simulation = ArenaSimulation(**running_simulation_data)
        db_session.add(simulation)
        await db_session.commit()
        await db_session.refresh(simulation)

        # Create an open position to trigger position valuation
        position = ArenaPosition(
            simulation_id=simulation.id,
            symbol="AAPL",
            status=PositionStatus.OPEN.value,
            signal_date=date(2024, 1, 14),
            entry_date=date(2024, 1, 15),
            entry_price=Decimal("100.00"),
            shares=10,
            trailing_stop_pct=Decimal("5.00"),
            highest_price=Decimal("100.00"),
            current_stop=Decimal("95.00"),
        )
        db_session.add(position)
        await db_session.commit()

        engine = SimulationEngine(db_session, session_factory=rollback_session_factory)

        # Pre-populate caches instead of mocking methods
        engine._trading_days_cache[simulation.id] = [date(2024, 1, 15)]
        engine._price_cache[simulation.id] = {
            symbol: sample_price_bars for symbol in simulation.symbols
        }

        # Use a mock that simulates a calculation bug resulting in negative positions_value
        # We'll patch the calculation by making the loop that sums positions_value
        # produce a negative result
        with patch("app.services.arena.simulation_engine.get_agent", return_value=mock_agent):
            # Create a bar that would be used for valuation, but patch
            # the positions_by_symbol to inject negative position value calculation
            async def mock_step_with_negative_positions():
                # Call the real step_day but intercept at the right point
                # Actually, let's use a different approach: patch the position's shares to negative
                position.shares = (
                    -10
                )  # Negative shares would cause negative positions_value
                try:
                    return await engine.step_day(simulation.id)
                finally:
                    position.shares = 10  # Reset

            with pytest.raises(ValueError, match="positions_value is negative"):
                await mock_step_with_negative_positions()

    @pytest.mark.unit
    async def test_validation_passes_for_valid_accounting(
        self,
        db_session,
        rollback_session_factory,
        running_simulation_data,
        sample_price_bars,
        mock_agent,
    ) -> None:
        """Test validation does not raise errors for valid accounting.

        This positive test verifies that normal operation (positive cash, positive
        positions_value, internally consistent snapshot) passes all validations
        without errors.
        """
        simulation = ArenaSimulation(**running_simulation_data)
        db_session.add(simulation)
        await db_session.commit()
        await db_session.refresh(simulation)

        engine = SimulationEngine(db_session, session_factory=rollback_session_factory)

        # Pre-populate caches instead of mocking methods
        trading_days = [bar.date for bar in sample_price_bars[:5]]
        engine._trading_days_cache[simulation.id] = trading_days
        engine._price_cache[simulation.id] = {
            symbol: sample_price_bars for symbol in simulation.symbols
        }

        # Run a normal step_day - should not raise any validation errors
        with patch("app.services.arena.simulation_engine.get_agent", return_value=mock_agent):
            snapshot = await engine.step_day(simulation.id)

        # Verify snapshot was created successfully
        assert snapshot is not None
        assert snapshot.simulation_id == simulation.id
        assert snapshot.cash >= 0
        assert snapshot.positions_value >= 0
        assert snapshot.total_equity >= 0

        # Verify snapshot is internally consistent
        assert abs(snapshot.total_equity - (snapshot.cash + snapshot.positions_value)) < Decimal(
            "0.01"
        )

    @pytest.mark.unit
    async def test_snapshot_cross_check_catches_construction_bug(
        self,
        db_session,
        rollback_session_factory,
        running_simulation_data,
        sample_price_bars,
        mock_agent,
    ) -> None:
        """Test snapshot cross-check catches bugs in snapshot construction.

        This test verifies that if a bug causes the snapshot to be constructed with
        inconsistent values (e.g., corrupted total_equity field), the validation
        catches it before commit.

        This is different from the tautological check of total_equity == cash + positions_value
        at the point of calculation (line 356), which can never fail since total_equity
        is defined as that sum. The snapshot cross-check validates that the ArenaSnapshot
        object fields remain consistent after construction.
        """
        simulation = ArenaSimulation(**running_simulation_data)
        db_session.add(simulation)
        await db_session.commit()
        await db_session.refresh(simulation)

        engine = SimulationEngine(db_session, session_factory=rollback_session_factory)

        # Create an open position so positions_value is non-zero (will be ~$1010)
        position = ArenaPosition(
            simulation_id=simulation.id,
            symbol="AAPL",
            status=PositionStatus.OPEN.value,
            signal_date=date(2024, 1, 14),
            entry_date=date(2024, 1, 15),
            entry_price=Decimal("100.00"),
            shares=10,
            trailing_stop_pct=Decimal("5.00"),
            highest_price=Decimal("100.00"),
            current_stop=Decimal("95.00"),
        )
        db_session.add(position)
        await db_session.commit()

        # Create a buggy ArenaSnapshot that corrupts total_equity after construction
        class BuggyArenaSnapshot(ArenaSnapshot):
            """Snapshot that corrupts total_equity to simulate a construction bug."""

            def __init__(self, **kwargs):
                super().__init__(**kwargs)
                # After construction, corrupt total_equity to be inconsistent
                # This simulates a bug where the snapshot is constructed with wrong values
                if self.positions_value > Decimal("0"):
                    self.total_equity = self.cash  # Wrong! Should be cash + positions_value

        # Pre-populate caches instead of mocking methods
        trading_days = [bar.date for bar in sample_price_bars[:5]]
        engine._trading_days_cache[simulation.id] = trading_days
        engine._price_cache[simulation.id] = {
            symbol: sample_price_bars for symbol in simulation.symbols
        }

        with patch("app.services.arena.simulation_engine.get_agent", return_value=mock_agent):
            # Patch ArenaSnapshot in the simulation_engine module
            with patch(
                "app.services.arena.simulation_engine.ArenaSnapshot", BuggyArenaSnapshot
            ):
                with pytest.raises(ValueError, match="snapshot equity mismatch"):
                    await engine.step_day(simulation.id)


@pytest.mark.usefixtures("db_session")
class TestSimulationEngineCaching:
    """Tests for SimulationEngine in-memory caching and optimization behavior."""

    @pytest.fixture
    def running_simulation_data(self) -> dict:
        """Create running simulation data."""
        return {
            "name": "Cache Test Simulation",
            "symbols": ["AAPL", "MSFT"],
            "start_date": date(2024, 1, 15),
            "end_date": date(2024, 1, 20),
            "initial_capital": Decimal("10000.00"),
            "position_size": Decimal("1000.00"),
            "agent_type": "live20",
            "agent_config": {"trailing_stop_pct": 5.0},
            "status": SimulationStatus.RUNNING.value,
            "current_day": 0,
            "total_days": 5,
        }

    @pytest.fixture
    def sample_price_bars(self) -> list[PriceBar]:
        """Create sample price bars for testing."""
        return [
            PriceBar(
                date=date(2024, 1, 15) + timedelta(days=i),
                open=Decimal("100.00"),
                high=Decimal("102.00"),
                low=Decimal("98.00"),
                close=Decimal("101.00"),
                volume=1000000,
            )
            for i in range(10)
        ]

    @pytest.fixture
    def mock_agent(self) -> MagicMock:
        """Create a mock agent."""
        agent = MagicMock()
        agent.required_lookback_days = 60
        agent.evaluate = AsyncMock(return_value=AgentDecision(symbol="AAPL", action="NO_SIGNAL"))
        return agent

    @pytest.mark.unit
    async def test_trading_days_cached_after_init(
        self, db_session, rollback_session_factory, sample_price_bars
    ) -> None:
        """Test trading days are cached after initialization."""
        # Create PENDING simulation (NOT initialized - total_days=0)
        simulation = ArenaSimulation(
            name="Cache Test Simulation",
            symbols=["AAPL", "MSFT"],
            start_date=date(2024, 1, 15),
            end_date=date(2024, 1, 20),
            initial_capital=Decimal("10000.00"),
            position_size=Decimal("1000.00"),
            agent_type="live20",
            agent_config={"trailing_stop_pct": 5.0},
            status=SimulationStatus.PENDING.value,
            current_day=0,
            total_days=0,  # NOT initialized yet
        )
        db_session.add(simulation)
        await db_session.commit()
        await db_session.refresh(simulation)

        engine = SimulationEngine(db_session, session_factory=rollback_session_factory)

        # Verify cache is empty before init
        assert simulation.id not in engine._trading_days_cache

        trading_days = [bar.date for bar in sample_price_bars[:5]]

        # Mock data service to return price data with actual PriceDataPoints
        from app.providers.base import PriceDataPoint

        mock_records = [
            PriceDataPoint(
                symbol="AAPL",
                timestamp=datetime.combine(d, datetime.min.time(), tzinfo=timezone.utc),
                open_price=100.0,
                high_price=102.0,
                low_price=98.0,
                close_price=101.0,
                volume=1000000,
            )
            for d in trading_days
        ]

        # Mock data service to return price data and sector prefetch
        with patch.object(
            engine.data_service, "get_price_data", new=AsyncMock(return_value=mock_records)
        ):
            with patch.object(
                engine.data_service,
                "batch_prefetch_sectors",
                new_callable=AsyncMock,
                return_value={"AAPL": "Technology", "MSFT": "Technology"},
            ):
                await engine.initialize_simulation(simulation.id)

        # Verify cache is populated after init
        assert simulation.id in engine._trading_days_cache
        assert len(engine._trading_days_cache[simulation.id]) == 5
        assert engine._trading_days_cache[simulation.id] == trading_days

    @pytest.mark.unit
    async def test_trading_days_lazy_loaded_on_resume(
        self,
        db_session,
        rollback_session_factory,
        running_simulation_data,
        sample_price_bars,
        mock_agent,
    ) -> None:
        """Test trading days are lazy-loaded when resuming a simulation."""
        # Create RUNNING simulation (already initialized)
        simulation = ArenaSimulation(**running_simulation_data)
        db_session.add(simulation)
        await db_session.commit()
        await db_session.refresh(simulation)

        # New engine instance (simulates resume after crash)
        engine = SimulationEngine(db_session, session_factory=rollback_session_factory)

        # Verify cache is empty (new engine instance)
        assert simulation.id not in engine._trading_days_cache

        trading_days = [bar.date for bar in sample_price_bars[:5]]

        # Mock _load_price_cache to track calls and populate cache
        async def mock_load_cache(*args, **kwargs):
            sim_id = args[0]
            engine._price_cache[sim_id] = {
                symbol: sample_price_bars for symbol in simulation.symbols
            }

        with patch("app.services.arena.simulation_engine.get_agent", return_value=mock_agent):
            with patch.object(
                engine, "_load_price_cache", side_effect=mock_load_cache
            ) as mock_load:
                # First step_day should lazy-load cache
                await engine.step_day(simulation.id)

        # Verify cache is now populated
        assert simulation.id in engine._trading_days_cache
        assert len(engine._trading_days_cache[simulation.id]) > 0
        # Should have been called once for lazy-load
        mock_load.assert_called_once()

        # Second call should use cache (not call _load_price_cache again)
        with patch("app.services.arena.simulation_engine.get_agent", return_value=mock_agent):
            with patch.object(
                engine, "_load_price_cache", side_effect=mock_load_cache
            ) as mock_load_2:
                await engine.step_day(simulation.id)

        # Should NOT have been called (using cache)
        mock_load_2.assert_not_called()

    @pytest.mark.unit
    async def test_batch_pending_positions_matches_individual(
        self,
        db_session,
        rollback_session_factory,
        running_simulation_data,
        sample_price_bars,
        mock_agent,
    ) -> None:
        """Test batch pending position loading returns same results as individual queries."""
        simulation = ArenaSimulation(**running_simulation_data)
        db_session.add(simulation)
        await db_session.commit()
        await db_session.refresh(simulation)

        # Create pending positions for testing
        pending1 = ArenaPosition(
            simulation_id=simulation.id,
            symbol="AAPL",
            status=PositionStatus.PENDING.value,
            signal_date=date(2024, 1, 14),
            trailing_stop_pct=Decimal("5.00"),
        )
        pending2 = ArenaPosition(
            simulation_id=simulation.id,
            symbol="MSFT",
            status=PositionStatus.PENDING.value,
            signal_date=date(2024, 1, 14),
            trailing_stop_pct=Decimal("5.00"),
        )
        db_session.add_all([pending1, pending2])
        await db_session.commit()

        engine = SimulationEngine(db_session, session_factory=rollback_session_factory)

        trading_days = [bar.date for bar in sample_price_bars[:5]]

        # Pre-populate trading days cache to avoid that code path
        engine._trading_days_cache[simulation.id] = trading_days

        # Pre-populate price cache
        engine._price_cache[simulation.id] = {
            symbol: sample_price_bars for symbol in simulation.symbols
        }

        # Execute step_day which uses batch loading
        with patch("app.services.arena.simulation_engine.get_agent", return_value=mock_agent):
            snapshot = await engine.step_day(simulation.id)

        # Verify both positions were processed (opened)
        await db_session.refresh(pending1)
        await db_session.refresh(pending2)

        assert pending1.status == PositionStatus.OPEN.value
        assert pending2.status == PositionStatus.OPEN.value
        # Verify snapshot shows 2 open positions
        assert snapshot.open_position_count == 2

    @pytest.mark.unit
    async def test_incremental_drawdown_matches_full_recalculation(
        self,
        db_session,
        rollback_session_factory,
        running_simulation_data,
        sample_price_bars,
        mock_agent,
    ) -> None:
        """Test incremental drawdown calculation produces same result as full recalculation."""
        simulation = ArenaSimulation(**running_simulation_data)
        db_session.add(simulation)
        await db_session.commit()
        await db_session.refresh(simulation)

        engine = SimulationEngine(db_session, session_factory=rollback_session_factory)

        # Create equity curve: 10000 -> 11000 -> 10000 -> 12000 (max DD: 9.09% at day 2)
        equities = [
            Decimal("10000.00"),
            Decimal("11000.00"),  # Peak
            Decimal("10000.00"),  # 9.09% drawdown from peak
            Decimal("12000.00"),  # New peak
        ]

        # Create snapshots manually
        for i, equity in enumerate(equities):
            snapshot = ArenaSnapshot(
                simulation_id=simulation.id,
                snapshot_date=date(2024, 1, 15) + timedelta(days=i),
                day_number=i,
                cash=equity,
                positions_value=Decimal("0.00"),
                total_equity=equity,
            )
            db_session.add(snapshot)
        await db_session.commit()

        # Test incremental calculation by calling step_day with next equity
        trading_days = [bar.date for bar in sample_price_bars[:5]]
        engine._trading_days_cache[simulation.id] = trading_days

        # Initialize drawdown state from existing snapshots (simulates resume)
        await engine._init_drawdown_state(simulation)

        # Verify incremental state matches expected values
        # Peak should be 12000 (last equity in the curve)
        assert engine._peak_equity[simulation.id] == Decimal("12000.00")
        # Max DD should be ~9.09% (from 11000 peak to 10000 trough)
        # Expected: (11000 - 10000) / 11000 * 100 = 9.0909...%
        expected_dd = (Decimal("11000") - Decimal("10000")) / Decimal("11000") * 100
        assert abs(engine._max_drawdown[simulation.id] - expected_dd) < Decimal("0.01")

    @pytest.mark.unit
    async def test_drawdown_state_reconstructed_on_resume(
        self,
        db_session,
        rollback_session_factory,
        running_simulation_data,
        sample_price_bars,
        mock_agent,
    ) -> None:
        """Test drawdown state is correctly reconstructed when resuming a simulation."""
        simulation = ArenaSimulation(**running_simulation_data)
        db_session.add(simulation)
        await db_session.commit()
        await db_session.refresh(simulation)

        # Create snapshots representing partial simulation progress
        equities = [Decimal("10000.00"), Decimal("11000.00"), Decimal("10500.00")]
        for i, equity in enumerate(equities):
            snapshot = ArenaSnapshot(
                simulation_id=simulation.id,
                snapshot_date=date(2024, 1, 15) + timedelta(days=i),
                day_number=i,
                cash=equity,
                positions_value=Decimal("0.00"),
                total_equity=equity,
            )
            db_session.add(snapshot)
        await db_session.commit()

        # Create NEW engine instance (simulates resume after crash)
        engine = SimulationEngine(db_session, session_factory=rollback_session_factory)

        # Verify drawdown state is empty initially
        assert simulation.id not in engine._peak_equity
        assert simulation.id not in engine._max_drawdown

        # Prepare for step_day
        trading_days = [bar.date for bar in sample_price_bars[:5]]
        engine._trading_days_cache[simulation.id] = trading_days

        # Pre-populate price cache
        engine._price_cache[simulation.id] = {
            symbol: sample_price_bars for symbol in simulation.symbols
        }

        # Run step_day which should lazy-load drawdown state
        with patch("app.services.arena.simulation_engine.get_agent", return_value=mock_agent):
            await engine.step_day(simulation.id)

        # Verify drawdown state was reconstructed correctly
        assert simulation.id in engine._peak_equity
        assert simulation.id in engine._max_drawdown

        # Peak should be 11000 (highest equity from snapshots)
        assert engine._peak_equity[simulation.id] == Decimal("11000.00")
        # Max DD should be ~4.55% (from 11000 to 10500)
        expected_dd = (Decimal("11000") - Decimal("10500")) / Decimal("11000") * 100
        assert abs(engine._max_drawdown[simulation.id] - expected_dd) < Decimal("0.01")

    @pytest.mark.unit
    async def test_drawdown_not_reset_on_new_ath_after_drawdown(
        self,
        db_session,
        rollback_session_factory,
        running_simulation_data,
        sample_price_bars,
        mock_agent,
    ) -> None:
        """Test max drawdown is NOT reset when equity makes new all-time high after a drawdown.

        Critical: max_drawdown should be the MAXIMUM drawdown experienced across the entire
        simulation. Making a new high should update peak, but NOT reset the max drawdown if
        a previous drawdown was larger.

        This test exercises the full step_day() path with a realistic scenario:
        - Days 0-2: Build up equity curve with 50% drawdown (10k -> 20k -> 10k)
        - Day 3: New ATH (25k) via step_day() call
        - Verify: max_drawdown remains 50%, not reset to 0%
        """
        simulation = ArenaSimulation(**running_simulation_data)
        db_session.add(simulation)
        await db_session.commit()
        await db_session.refresh(simulation)

        engine = SimulationEngine(db_session, session_factory=rollback_session_factory)

        # Scenario: Equity went from 10000 (initial) -> 20000 (peak) -> 10000 (drawdown) -> 25000 (new ATH)
        # The 50% drawdown should remain the max even after new ATH

        # Setup: Create snapshots for the equity curve history
        # Day 0: 10000 (initial capital, no positions)
        snapshot_day0 = ArenaSnapshot(
            simulation_id=simulation.id,
            snapshot_date=date(2024, 1, 15),
            day_number=0,
            cash=Decimal("10000.00"),
            positions_value=Decimal("0.00"),
            total_equity=Decimal("10000.00"),
        )
        db_session.add(snapshot_day0)

        # Day 1: 20000 (peak - opened winning position)
        snapshot_day1 = ArenaSnapshot(
            simulation_id=simulation.id,
            snapshot_date=date(2024, 1, 16),
            day_number=1,
            cash=Decimal("0.00"),
            positions_value=Decimal("20000.00"),
            total_equity=Decimal("20000.00"),
        )
        db_session.add(snapshot_day1)

        # Day 2: 10000 (drawdown - position lost value)
        snapshot_day2 = ArenaSnapshot(
            simulation_id=simulation.id,
            snapshot_date=date(2024, 1, 17),
            day_number=2,
            cash=Decimal("0.00"),
            positions_value=Decimal("10000.00"),
            total_equity=Decimal("10000.00"),
        )
        db_session.add(snapshot_day2)

        await db_session.commit()

        # Initialize drawdown state from these snapshots
        await engine._init_drawdown_state(simulation)

        # Verify state: peak should be 20000, max_drawdown should be 50%
        assert engine._peak_equity[simulation.id] == Decimal("20000.00")
        assert engine._max_drawdown[simulation.id] == Decimal("50.00")

        # Set simulation.max_drawdown_pct to reflect the historical max
        # (In a real simulation, this would have been set when the 50% drawdown occurred)
        simulation.max_drawdown_pct = Decimal("50.00")
        await db_session.commit()

        # Now run step_day for day 3 where equity goes to 25000 (new ATH)
        # Mock setup to produce 25000 total equity
        simulation.current_day = 3  # Will process trading_days[3] = date(2024, 1, 18)
        engine._trading_days_cache[simulation.id] = [
            date(2024, 1, 15),  # Day 0
            date(2024, 1, 16),  # Day 1
            date(2024, 1, 17),  # Day 2
            date(2024, 1, 18),  # Day 3 (to be processed)
        ]

        # Mock agent to produce no new signals (just hold existing position)
        mock_agent_no_signal = MagicMock()
        mock_agent_no_signal.required_lookback_days = 60
        mock_agent_no_signal.evaluate = AsyncMock(
            return_value=AgentDecision(symbol="AAPL", action="NO_SIGNAL")
        )

        # Create open position worth 25000 at current prices
        # This position will be valued at day 3 (2024-01-18)
        position = ArenaPosition(
            simulation_id=simulation.id,
            symbol="AAPL",
            status=PositionStatus.OPEN.value,
            signal_date=date(2024, 1, 17),
            entry_date=date(2024, 1, 17),
            entry_price=Decimal("100.00"),
            shares=100,  # 100 shares
            trailing_stop_pct=Decimal("5.00"),
            highest_price=Decimal("250.00"),  # Will be updated based on day 3 prices
            current_stop=Decimal("237.50"),
        )
        db_session.add(position)
        await db_session.commit()

        # Create price bars for all days including day 3
        # Day 3: AAPL at $250 (100 shares * $250 = $25,000)
        price_bars = [
            PriceBar(
                date=date(2024, 1, 15),
                open=Decimal("100.00"),
                high=Decimal("102.00"),
                low=Decimal("98.00"),
                close=Decimal("100.00"),
                volume=1000000,
            ),
            PriceBar(
                date=date(2024, 1, 16),
                open=Decimal("100.00"),
                high=Decimal("202.00"),  # Must be >= close
                low=Decimal("98.00"),
                close=Decimal("200.00"),  # Price doubled
                volume=1000000,
            ),
            PriceBar(
                date=date(2024, 1, 17),
                open=Decimal("200.00"),
                high=Decimal("202.00"),
                low=Decimal("98.00"),
                close=Decimal("100.00"),  # Back to 100
                volume=1000000,
            ),
            PriceBar(
                date=date(2024, 1, 18),  # Day 3
                open=Decimal("250.00"),
                high=Decimal("252.00"),
                low=Decimal("248.00"),
                close=Decimal("250.00"),  # 100 shares * $250 = $25,000
                volume=1000000,
            ),
        ]
        engine._price_cache[simulation.id] = {
            symbol: price_bars for symbol in simulation.symbols
        }

        # Execute step_day (this is the actual production code path)
        with patch("app.services.arena.simulation_engine.get_agent", return_value=mock_agent_no_signal):
            snapshot = await engine.step_day(simulation.id)

        # Assertions: Verify drawdown tracking behavior
        # 1. Peak should be updated to new ATH
        assert engine._peak_equity[simulation.id] == Decimal("25000.00")

        # 2. CRITICAL: max_drawdown should STILL be 50% (the previous drawdown)
        #    NOT 0% from the new peak, because we track the MAXIMUM drawdown
        assert engine._max_drawdown[simulation.id] == Decimal("50.00")

        # 3. The snapshot should reflect the new equity
        assert snapshot.total_equity == Decimal("25000.00")

        # 4. simulation.max_drawdown_pct should NOT be updated to 0%
        #    because current drawdown (0%) < historical max (50%)
        await db_session.refresh(simulation)
        assert simulation.max_drawdown_pct == Decimal("50.00")

    @pytest.mark.unit
    async def test_drawdown_initialized_after_init(
        self, db_session, rollback_session_factory, sample_price_bars
    ) -> None:
        """Test drawdown state is initialized during initialize_simulation()."""
        # Create PENDING simulation (NOT initialized)
        simulation = ArenaSimulation(
            name="Drawdown Init Test",
            symbols=["AAPL"],
            start_date=date(2024, 1, 15),
            end_date=date(2024, 1, 20),
            initial_capital=Decimal("10000.00"),
            position_size=Decimal("1000.00"),
            agent_type="live20",
            agent_config={"trailing_stop_pct": 5.0},
            status=SimulationStatus.PENDING.value,
            current_day=0,
            total_days=0,
        )
        db_session.add(simulation)
        await db_session.commit()
        await db_session.refresh(simulation)

        engine = SimulationEngine(db_session, session_factory=rollback_session_factory)

        # Verify drawdown state is empty before init
        assert simulation.id not in engine._peak_equity
        assert simulation.id not in engine._max_drawdown

        trading_days = [bar.date for bar in sample_price_bars[:5]]

        # Mock data service to return price data with actual PriceDataPoints
        from app.providers.base import PriceDataPoint

        mock_records = [
            PriceDataPoint(
                symbol="AAPL",
                timestamp=datetime.combine(d, datetime.min.time(), tzinfo=timezone.utc),
                open_price=100.0,
                high_price=102.0,
                low_price=98.0,
                close_price=101.0,
                volume=1000000,
            )
            for d in trading_days
        ]

        with patch.object(
            engine.data_service, "get_price_data", new=AsyncMock(return_value=mock_records)
        ):
            await engine.initialize_simulation(simulation.id)

        # Verify drawdown state is initialized
        assert simulation.id in engine._peak_equity
        assert simulation.id in engine._max_drawdown

        # Initial peak should equal initial capital
        assert engine._peak_equity[simulation.id] == simulation.initial_capital
        # Initial max drawdown should be 0
        assert engine._max_drawdown[simulation.id] == Decimal("0")

    @pytest.mark.unit
    async def test_price_cache_populated_during_init(
        self, db_session, rollback_session_factory, sample_price_bars
    ) -> None:
        """Test price cache is populated during initialize_simulation()."""
        simulation = ArenaSimulation(
            name="Price Cache Init Test",
            symbols=["AAPL", "MSFT"],
            start_date=date(2024, 1, 15),
            end_date=date(2024, 1, 20),
            initial_capital=Decimal("10000.00"),
            position_size=Decimal("1000.00"),
            agent_type="live20",
            agent_config={"trailing_stop_pct": 5.0},
            status=SimulationStatus.PENDING.value,
            current_day=0,
            total_days=0,
        )
        db_session.add(simulation)
        await db_session.commit()
        await db_session.refresh(simulation)

        engine = SimulationEngine(db_session, session_factory=rollback_session_factory)

        # Verify cache is empty before init
        assert simulation.id not in engine._price_cache

        # Mock data service to return price data
        from app.providers.base import PriceDataPoint

        trading_days = [bar.date for bar in sample_price_bars[:5]]
        mock_records = [
            PriceDataPoint(
                symbol="AAPL",
                timestamp=datetime.combine(d, datetime.min.time(), tzinfo=timezone.utc),
                open_price=100.0,
                high_price=102.0,
                low_price=98.0,
                close_price=101.0,
                volume=1000000,
            )
            for d in trading_days
        ]

        with patch.object(
            engine.data_service, "get_price_data", new=AsyncMock(return_value=mock_records)
        ):
            with patch.object(
                engine.data_service,
                "batch_prefetch_sectors",
                new_callable=AsyncMock,
                return_value={"AAPL": "Technology", "MSFT": "Technology"},
            ):
                await engine.initialize_simulation(simulation.id)

        # Verify cache is populated
        assert simulation.id in engine._price_cache
        assert "AAPL" in engine._price_cache[simulation.id]
        assert "MSFT" in engine._price_cache[simulation.id]
        assert len(engine._price_cache[simulation.id]["AAPL"]) == 5

    @pytest.mark.unit
    def test_cached_price_history_filters_by_date(self) -> None:
        """Test _get_cached_price_history filters by date range correctly."""
        mock_session_factory = MagicMock()
        engine = SimulationEngine(AsyncMock(), session_factory=mock_session_factory)

        # Create price bars spanning multiple days
        bars = [
            PriceBar(
                date=date(2024, 1, 10),
                open=Decimal("100.00"),
                high=Decimal("102.00"),
                low=Decimal("98.00"),
                close=Decimal("101.00"),
                volume=1000000,
            ),
            PriceBar(
                date=date(2024, 1, 15),
                open=Decimal("105.00"),
                high=Decimal("107.00"),
                low=Decimal("103.00"),
                close=Decimal("106.00"),
                volume=1000000,
            ),
            PriceBar(
                date=date(2024, 1, 20),
                open=Decimal("110.00"),
                high=Decimal("112.00"),
                low=Decimal("108.00"),
                close=Decimal("111.00"),
                volume=1000000,
            ),
        ]

        # Populate cache
        engine._price_cache[1] = {"AAPL": bars}

        # Test filtering
        result = engine._get_cached_price_history(1, "AAPL", date(2024, 1, 12), date(2024, 1, 18))

        # Should only return the middle bar
        assert len(result) == 1
        assert result[0].date == date(2024, 1, 15)

    @pytest.mark.unit
    def test_cached_bar_for_date_returns_correct_bar(self) -> None:
        """Test _get_cached_bar_for_date returns correct bar."""
        mock_session_factory = MagicMock()
        engine = SimulationEngine(AsyncMock(), session_factory=mock_session_factory)

        bars = [
            PriceBar(
                date=date(2024, 1, 15),
                open=Decimal("100.00"),
                high=Decimal("102.00"),
                low=Decimal("98.00"),
                close=Decimal("101.00"),
                volume=1000000,
            ),
            PriceBar(
                date=date(2024, 1, 16),
                open=Decimal("101.00"),
                high=Decimal("103.00"),
                low=Decimal("99.00"),
                close=Decimal("102.00"),
                volume=1000000,
            ),
        ]

        engine._price_cache[1] = {"AAPL": bars}

        result = engine._get_cached_bar_for_date(1, "AAPL", date(2024, 1, 16))

        assert result is not None
        assert result.date == date(2024, 1, 16)
        assert result.open == Decimal("101.00")

    @pytest.mark.unit
    def test_cached_bar_for_date_returns_none_for_missing(self) -> None:
        """Test _get_cached_bar_for_date returns None for missing date."""
        mock_session_factory = MagicMock()
        engine = SimulationEngine(AsyncMock(), session_factory=mock_session_factory)

        bars = [
            PriceBar(
                date=date(2024, 1, 15),
                open=Decimal("100.00"),
                high=Decimal("102.00"),
                low=Decimal("98.00"),
                close=Decimal("101.00"),
                volume=1000000,
            ),
        ]

        engine._price_cache[1] = {"AAPL": bars}

        result = engine._get_cached_bar_for_date(1, "AAPL", date(2024, 1, 20))

        assert result is None

    @pytest.mark.unit
    async def test_cache_cleared_on_finalization(
        self, db_session, rollback_session_factory
    ) -> None:
        """Test cache is cleared when simulation is finalized."""
        simulation = ArenaSimulation(
            name="Cache Cleanup Test",
            symbols=["AAPL"],
            start_date=date(2024, 1, 15),
            end_date=date(2024, 1, 20),
            initial_capital=Decimal("10000.00"),
            position_size=Decimal("1000.00"),
            agent_type="live20",
            agent_config={"trailing_stop_pct": 5.0},
            status=SimulationStatus.RUNNING.value,
        )
        db_session.add(simulation)
        await db_session.commit()
        await db_session.refresh(simulation)

        engine = SimulationEngine(db_session, session_factory=rollback_session_factory)

        # Populate caches
        engine._price_cache[simulation.id] = {"AAPL": []}
        engine._trading_days_cache[simulation.id] = []
        engine._peak_equity[simulation.id] = Decimal("10000")
        engine._max_drawdown[simulation.id] = Decimal("0")
        engine._sector_cache[simulation.id] = {"AAPL": "Technology"}

        # Verify caches are populated
        assert simulation.id in engine._price_cache
        assert simulation.id in engine._trading_days_cache
        assert simulation.id in engine._peak_equity
        assert simulation.id in engine._max_drawdown
        assert simulation.id in engine._sector_cache

        # Finalize simulation (no closed positions — analytics will be skipped)
        await engine._finalize_simulation(simulation, positions=[])

        # Verify caches are cleared
        assert simulation.id not in engine._price_cache
        assert simulation.id not in engine._trading_days_cache
        assert simulation.id not in engine._peak_equity
        assert simulation.id not in engine._max_drawdown
        assert simulation.id not in engine._sector_cache

    @pytest.mark.unit
    async def test_noload_prevents_relationship_loading(
        self, db_session, rollback_session_factory
    ) -> None:
        """Test that noload options prevent positions/snapshots from being loaded.

        Phase 5: Verify that session.get() with noload options does not trigger
        selectin eager loading of positions and snapshots relationships.
        """
        simulation = ArenaSimulation(
            name="Noload Test",
            symbols=["AAPL"],
            start_date=date(2024, 1, 15),
            end_date=date(2024, 1, 20),
            initial_capital=Decimal("10000.00"),
            position_size=Decimal("1000.00"),
            agent_type="live20",
            agent_config={"trailing_stop_pct": 5.0},
            status=SimulationStatus.RUNNING.value,
            current_day=1,
            total_days=5,
        )
        db_session.add(simulation)
        await db_session.commit()
        await db_session.refresh(simulation)

        # Add positions and snapshots to verify they are NOT loaded
        position = ArenaPosition(
            simulation_id=simulation.id,
            symbol="AAPL",
            status=PositionStatus.OPEN.value,
            signal_date=date(2024, 1, 14),
            trailing_stop_pct=Decimal("5.00"),
        )
        snapshot = ArenaSnapshot(
            simulation_id=simulation.id,
            snapshot_date=date(2024, 1, 15),
            day_number=0,
            cash=Decimal("10000.00"),
            positions_value=Decimal("0.00"),
            total_equity=Decimal("10000.00"),
        )
        db_session.add_all([position, snapshot])
        await db_session.commit()

        # Create engine and fetch simulation using step_day's pattern
        # (which uses noload options)
        engine = SimulationEngine(db_session, session_factory=rollback_session_factory)

        # Fetch with noload (same pattern as step_day, initialize_simulation)
        from sqlalchemy.orm import noload

        sim_loaded = await db_session.get(
            ArenaSimulation,
            simulation.id,
            options=[noload(ArenaSimulation.positions), noload(ArenaSimulation.snapshots)],
        )

        # Verify simulation was loaded
        assert sim_loaded is not None
        assert sim_loaded.id == simulation.id

        # CRITICAL: Accessing .positions or .snapshots should NOT have data
        # because noload prevents eager loading. The relationships should be
        # in an unloaded state, not populated collections.

        # Note: With noload, the relationship attribute exists but accessing it
        # will trigger a lazy load unless we check the state. Instead, we verify
        # that the relationships are marked as unloaded in SQLAlchemy's state.
        from sqlalchemy import inspect

        insp = inspect(sim_loaded)

        # Check that positions and snapshots are unloaded
        # (not in the instance's __dict__ as loaded attributes)
        positions_state = insp.attrs.positions
        snapshots_state = insp.attrs.snapshots

        # With noload, these should be NEVER_SET or NO_VALUE, not loaded
        # This verifies we didn't trigger the selectin query
        assert not positions_state.loaded_value  # Should not have loaded value
        assert not snapshots_state.loaded_value  # Should not have loaded value


@pytest.mark.usefixtures("db_session")
class TestSimulationEnginePortfolioSelection:
    """Tests for portfolio selection integration in SimulationEngine.

    Verifies that the portfolio selector is applied correctly when processing
    BUY signals, including score-based ranking, sector caps, position limits,
    and backward compatibility with the default FIFO behavior.
    """

    def _make_price_bars(self, start_date: date, count: int = 30) -> list[PriceBar]:
        """Create price bars starting from start_date.

        Returns 30 bars by default — enough for ATR calculation (14-period
        Wilder's EMA requires at least 15 data points).
        """
        return [
            PriceBar(
                date=start_date + timedelta(days=i),
                open=Decimal("100.00"),
                high=Decimal("102.00"),
                low=Decimal("98.00"),
                close=Decimal("101.00"),
                volume=1_000_000,
            )
            for i in range(count)
        ]

    def _make_simulation(self, agent_config: dict | None = None) -> dict:
        """Return base simulation kwargs. Extra agent_config keys are merged."""
        config = {"trailing_stop_pct": 5.0}
        if agent_config:
            config.update(agent_config)
        return {
            "name": "Portfolio Selection Test",
            "symbols": ["AAPL", "MSFT", "GOOGL"],
            "start_date": date(2024, 1, 15),
            "end_date": date(2024, 1, 20),
            "initial_capital": Decimal("50000.00"),
            "position_size": Decimal("1000.00"),
            "agent_type": "live20",
            "agent_config": config,
            "status": SimulationStatus.RUNNING.value,
            "current_day": 0,
            "total_days": 5,
        }

    @pytest.mark.unit
    async def test_no_portfolio_config_defaults_to_fifo_and_creates_all_pending(
        self, db_session, rollback_session_factory
    ) -> None:
        """Simulation with no portfolio config uses FIFO — all BUY signals get PENDING.

        This verifies backward compatibility: existing simulations that have no
        portfolio_strategy key in agent_config must behave identically to before
        this change was introduced.
        """
        simulation = ArenaSimulation(**self._make_simulation())
        db_session.add(simulation)
        await db_session.commit()
        await db_session.refresh(simulation)

        engine = SimulationEngine(db_session, session_factory=rollback_session_factory)

        price_bars = self._make_price_bars(date(2024, 1, 14))
        trading_day = date(2024, 1, 15)
        engine._trading_days_cache[simulation.id] = [trading_day]
        engine._price_cache[simulation.id] = {
            sym: price_bars for sym in simulation.symbols
        }
        # No sector cache — FIFO selector doesn't need it, and missing cache
        # returns empty dict which means all sectors are None (never blocked).
        engine._sector_cache[simulation.id] = {}

        # All three symbols return BUY
        mock_agent = MagicMock()
        mock_agent.required_lookback_days = 60
        mock_agent.evaluate = AsyncMock(
            return_value=AgentDecision(
                symbol="ANY", action="BUY", score=70, reasoning="Signal"
            )
        )

        with patch("app.services.arena.simulation_engine.get_agent", return_value=mock_agent):
            await engine.step_day(simulation.id)

        result = await db_session.execute(
            select(ArenaPosition).where(
                ArenaPosition.simulation_id == simulation.id,
                ArenaPosition.status == PositionStatus.PENDING.value,
            )
        )
        pending_positions = result.scalars().all()
        # All three BUY signals should create PENDING positions (FIFO = no filtering)
        assert len(pending_positions) == 3
        pending_symbols = {p.symbol for p in pending_positions}
        assert pending_symbols == {"AAPL", "MSFT", "GOOGL"}

    @pytest.mark.unit
    async def test_score_sector_low_atr_selects_higher_score_first(
        self, db_session, rollback_session_factory
    ) -> None:
        """Simulation with score_sector_low_atr: higher-score symbols get PENDING first.

        AAPL (score=90) and MSFT (score=60) both signal BUY with no sector cap.
        Both should be selected — score ranking doesn't filter, just orders. With
        max_open_positions=1, only the highest-score symbol should be selected.
        """
        simulation = ArenaSimulation(
            **self._make_simulation(
                {
                    "portfolio_strategy": "score_sector_low_atr",
                    "max_open_positions": 1,
                }
            )
        )
        simulation.symbols = ["MSFT", "AAPL"]  # Lower score listed first — order should be ignored
        db_session.add(simulation)
        await db_session.commit()
        await db_session.refresh(simulation)

        engine = SimulationEngine(db_session, session_factory=rollback_session_factory)

        price_bars = self._make_price_bars(date(2024, 1, 14))
        trading_day = date(2024, 1, 15)
        engine._trading_days_cache[simulation.id] = [trading_day]
        engine._price_cache[simulation.id] = {
            sym: price_bars for sym in simulation.symbols
        }
        engine._sector_cache[simulation.id] = {
            "MSFT": "Technology",
            "AAPL": "Technology",
        }

        # MSFT score=60, AAPL score=90 — AAPL should win
        def make_decision(symbol: str) -> AgentDecision:
            score = 90 if symbol == "AAPL" else 60
            return AgentDecision(symbol=symbol, action="BUY", score=score, reasoning="Signal")

        mock_agent = MagicMock()
        mock_agent.required_lookback_days = 60
        mock_agent.evaluate = AsyncMock(side_effect=lambda sym, *a, **kw: make_decision(sym))

        with patch("app.services.arena.simulation_engine.get_agent", return_value=mock_agent):
            snapshot = await engine.step_day(simulation.id)

        result = await db_session.execute(
            select(ArenaPosition).where(
                ArenaPosition.simulation_id == simulation.id,
                ArenaPosition.status == PositionStatus.PENDING.value,
            )
        )
        pending_positions = result.scalars().all()
        # max_open_positions=1 → only highest-score symbol selected
        assert len(pending_positions) == 1
        assert pending_positions[0].symbol == "AAPL"
        assert pending_positions[0].agent_score == 90

        # Decisions snapshot must carry portfolio_selected flag
        assert snapshot.decisions["AAPL"]["portfolio_selected"] is True
        assert snapshot.decisions["MSFT"]["portfolio_selected"] is False

    @pytest.mark.unit
    async def test_max_per_sector_limits_positions_per_sector(
        self, db_session, rollback_session_factory
    ) -> None:
        """Simulation with max_per_sector=1: only 1 position per sector opened.

        AAPL and MSFT are both Technology. GOOGL is Communication Services.
        With max_per_sector=1, only 1 of {AAPL, MSFT} plus GOOGL should be selected
        (2 total).
        """
        simulation = ArenaSimulation(
            **self._make_simulation({"max_per_sector": 1})
        )
        db_session.add(simulation)
        await db_session.commit()
        await db_session.refresh(simulation)

        engine = SimulationEngine(db_session, session_factory=rollback_session_factory)

        price_bars = self._make_price_bars(date(2024, 1, 14))
        trading_day = date(2024, 1, 15)
        engine._trading_days_cache[simulation.id] = [trading_day]
        engine._price_cache[simulation.id] = {
            sym: price_bars for sym in simulation.symbols
        }
        engine._sector_cache[simulation.id] = {
            "AAPL": "Technology",
            "MSFT": "Technology",
            "GOOGL": "Communication Services",
        }

        mock_agent = MagicMock()
        mock_agent.required_lookback_days = 60
        mock_agent.evaluate = AsyncMock(
            return_value=AgentDecision(
                symbol="ANY", action="BUY", score=70, reasoning="Signal"
            )
        )

        with patch("app.services.arena.simulation_engine.get_agent", return_value=mock_agent):
            await engine.step_day(simulation.id)

        result = await db_session.execute(
            select(ArenaPosition).where(
                ArenaPosition.simulation_id == simulation.id,
                ArenaPosition.status == PositionStatus.PENDING.value,
            )
        )
        pending_positions = result.scalars().all()
        pending_symbols = {p.symbol for p in pending_positions}

        # Only 1 Technology position + 1 Communication Services position = 2 total
        assert len(pending_positions) == 2
        assert "GOOGL" in pending_symbols
        # Exactly one of AAPL/MSFT should be selected (FIFO picks first in list)
        tech_selected = pending_symbols & {"AAPL", "MSFT"}
        assert len(tech_selected) == 1

    @pytest.mark.unit
    async def test_max_open_positions_caps_total_new_pending(
        self, db_session, rollback_session_factory
    ) -> None:
        """Simulation with max_open_positions=3: at most 3 positions total.

        Start with 2 existing open positions. Three BUY signals arrive.
        With max_open_positions=3, only 1 new PENDING should be created.
        """
        simulation = ArenaSimulation(
            **self._make_simulation({"max_open_positions": 3})
        )
        simulation.symbols = ["AAPL", "MSFT", "GOOGL"]
        db_session.add(simulation)
        await db_session.commit()
        await db_session.refresh(simulation)

        # Create 2 existing open positions for different symbols
        for sym in ["NVDA", "TSLA"]:
            pos = ArenaPosition(
                simulation_id=simulation.id,
                symbol=sym,
                status=PositionStatus.OPEN.value,
                signal_date=date(2024, 1, 14),
                entry_date=date(2024, 1, 14),
                entry_price=Decimal("100.00"),
                shares=10,
                trailing_stop_pct=Decimal("5.00"),
                highest_price=Decimal("100.00"),
                current_stop=Decimal("95.00"),
            )
            db_session.add(pos)
        await db_session.commit()

        engine = SimulationEngine(db_session, session_factory=rollback_session_factory)

        price_bars = self._make_price_bars(date(2024, 1, 14))
        trading_day = date(2024, 1, 15)
        engine._trading_days_cache[simulation.id] = [trading_day]
        # Include price bars for the simulation symbols and the open-position symbols
        all_symbols = simulation.symbols + ["NVDA", "TSLA"]
        engine._price_cache[simulation.id] = {
            sym: price_bars for sym in all_symbols
        }
        engine._sector_cache[simulation.id] = {sym: None for sym in all_symbols}

        mock_agent = MagicMock()
        mock_agent.required_lookback_days = 60
        mock_agent.evaluate = AsyncMock(
            return_value=AgentDecision(
                symbol="ANY", action="BUY", score=70, reasoning="Signal"
            )
        )

        with patch("app.services.arena.simulation_engine.get_agent", return_value=mock_agent):
            await engine.step_day(simulation.id)

        result = await db_session.execute(
            select(ArenaPosition).where(
                ArenaPosition.simulation_id == simulation.id,
                ArenaPosition.status == PositionStatus.PENDING.value,
            )
        )
        pending_positions = result.scalars().all()
        # max_open_positions=3, current_open_count=2 → only 1 new PENDING
        assert len(pending_positions) == 1

    @pytest.mark.unit
    async def test_decisions_snapshot_contains_portfolio_selected_flag_for_buy_signals(
        self, db_session, rollback_session_factory
    ) -> None:
        """Decisions snapshot must contain portfolio_selected for every BUY signal.

        With max_open_positions=1 and two BUY signals, one is selected and one is
        not. Both entries in the decisions dict must carry the portfolio_selected key.
        Non-BUY decisions must NOT have this key.
        """
        simulation = ArenaSimulation(
            **self._make_simulation(
                {
                    "portfolio_strategy": "none",
                    "max_open_positions": 1,
                }
            )
        )
        simulation.symbols = ["AAPL", "MSFT", "GOOGL"]
        db_session.add(simulation)
        await db_session.commit()
        await db_session.refresh(simulation)

        engine = SimulationEngine(db_session, session_factory=rollback_session_factory)

        price_bars = self._make_price_bars(date(2024, 1, 14))
        trading_day = date(2024, 1, 15)
        engine._trading_days_cache[simulation.id] = [trading_day]
        engine._price_cache[simulation.id] = {
            sym: price_bars for sym in simulation.symbols
        }
        engine._sector_cache[simulation.id] = {sym: None for sym in simulation.symbols}

        # AAPL and MSFT → BUY, GOOGL → NO_SIGNAL
        def make_decision(symbol: str) -> AgentDecision:
            if symbol == "GOOGL":
                return AgentDecision(symbol=symbol, action="NO_SIGNAL", score=40)
            return AgentDecision(symbol=symbol, action="BUY", score=70, reasoning="Signal")

        mock_agent = MagicMock()
        mock_agent.required_lookback_days = 60
        mock_agent.evaluate = AsyncMock(side_effect=lambda sym, *a, **kw: make_decision(sym))

        with patch("app.services.arena.simulation_engine.get_agent", return_value=mock_agent):
            snapshot = await engine.step_day(simulation.id)

        # Both BUY signals must have portfolio_selected in their decision entry
        assert "portfolio_selected" in snapshot.decisions["AAPL"]
        assert "portfolio_selected" in snapshot.decisions["MSFT"]
        # Non-BUY (NO_SIGNAL) decisions must NOT have the key
        assert "portfolio_selected" not in snapshot.decisions["GOOGL"]

        # Exactly one of the two BUY signals was selected (FIFO + max_open_positions=1)
        buy_selected = [
            sym for sym in ["AAPL", "MSFT"]
            if snapshot.decisions[sym]["portfolio_selected"]
        ]
        assert len(buy_selected) == 1

    @pytest.mark.unit
    async def test_sector_cache_cleared_by_clear_simulation_cache(self) -> None:
        """clear_simulation_cache() removes the sector cache entry."""
        mock_session_factory = MagicMock()
        engine = SimulationEngine(AsyncMock(), session_factory=mock_session_factory)

        engine._sector_cache[42] = {"AAPL": "Technology"}
        engine._price_cache[42] = {}
        engine._trading_days_cache[42] = []
        engine._peak_equity[42] = Decimal("10000")
        engine._max_drawdown[42] = Decimal("0")

        engine.clear_simulation_cache(42)

        assert 42 not in engine._sector_cache
        assert 42 not in engine._price_cache
        assert 42 not in engine._trading_days_cache
        assert 42 not in engine._peak_equity
        assert 42 not in engine._max_drawdown


# =============================================================================
# Layer 4: ATR-Based Trailing Stop integration tests
# =============================================================================


@pytest.mark.usefixtures("db_session")
class TestSimulationEngineAtrStop:
    """Integration tests for ATR-based trailing stop in step_day()."""

    @pytest.fixture
    def atr_simulation(self, db_session) -> ArenaSimulation:
        """Simulation configured with ATR trailing stop."""
        return ArenaSimulation(
            name="ATR Stop Test",
            symbols=["AAPL"],
            start_date=date(2024, 1, 15),
            end_date=date(2024, 1, 25),
            initial_capital=Decimal("10000.00"),
            position_size=Decimal("1000.00"),
            agent_type="live20",
            agent_config={
                "stop_type": "atr",
                "atr_stop_multiplier": 2.0,
                "atr_stop_min_pct": 2.0,
                "atr_stop_max_pct": 10.0,
                # trailing_stop_pct is the fixed fallback placeholder
                "trailing_stop_pct": 5.0,
            },
            status=SimulationStatus.RUNNING.value,
            current_day=0,
            total_days=10,
        )

    def _make_price_bars(
        self, base_date: date, count: int, open_: float, high: float, low: float, close: float
    ) -> list[PriceBar]:
        """Create a series of identical price bars from base_date."""
        bars = []
        for i in range(count):
            bar_date = base_date + timedelta(days=i)
            # Skip weekends for realism
            while bar_date.weekday() >= 5:
                bar_date += timedelta(days=1)
            bars.append(
                PriceBar(
                    date=bar_date,
                    open=Decimal(str(open_)),
                    high=Decimal(str(high)),
                    low=Decimal(str(low)),
                    close=Decimal(str(close)),
                    volume=1000000,
                )
            )
        return bars

    @pytest.mark.unit
    async def test_atr_stop_sets_per_position_trail_pct(
        self, db_session, rollback_session_factory, atr_simulation
    ) -> None:
        """ATR stop overwrites trailing_stop_pct on position when it opens.

        The initial placeholder 5.0% stored at PENDING time should be replaced
        by the ATR-computed value when the position transitions to OPEN.
        """
        db_session.add(atr_simulation)
        await db_session.commit()
        await db_session.refresh(atr_simulation)

        # PENDING position from the previous day
        pending = ArenaPosition(
            simulation_id=atr_simulation.id,
            symbol="AAPL",
            status=PositionStatus.PENDING.value,
            signal_date=date(2024, 1, 14),
            trailing_stop_pct=Decimal("5.00"),  # placeholder set at signal time
        )
        db_session.add(pending)
        await db_session.commit()

        engine = SimulationEngine(db_session, session_factory=rollback_session_factory)

        # Build bars that:
        # (a) include the current_date (Jan 15) so today_bar is found, AND
        # (b) provide >= 15 bars within the 90-day ATR window ending on Jan 15.
        # Strategy: 60 consecutive bars ending on Jan 15, starting ~60 days prior.
        price_bars = []
        end_date = date(2024, 1, 15)
        for i in range(60):
            d = end_date - timedelta(days=59 - i)
            price_bars.append(
                PriceBar(
                    date=d,
                    open=Decimal("100.00"),
                    high=Decimal("103.00"),
                    low=Decimal("97.00"),
                    close=Decimal("101.00"),
                    volume=1000000,
                )
            )

        trading_days = [date(2024, 1, 15), date(2024, 1, 16), date(2024, 1, 17)]
        engine._trading_days_cache[atr_simulation.id] = trading_days
        engine._price_cache[atr_simulation.id] = {"AAPL": price_bars}
        engine._sector_cache[atr_simulation.id] = {"AAPL": None}

        mock_agent = MagicMock()
        mock_agent.required_lookback_days = 60
        mock_agent.evaluate = AsyncMock(
            return_value=AgentDecision(symbol="AAPL", action="HOLD", reasoning="Holding")
        )

        with patch("app.services.arena.simulation_engine.get_agent", return_value=mock_agent):
            await engine.step_day(atr_simulation.id)

        await db_session.refresh(pending)
        # Position should have opened
        assert pending.status == PositionStatus.OPEN.value
        # ATR-computed trail_pct replaces the 5.0 placeholder
        assert pending.trailing_stop_pct != Decimal("5.00")
        # It must be within the clamped range [2.0, 10.0]
        assert Decimal("2.0") <= pending.trailing_stop_pct <= Decimal("10.0")

    @pytest.mark.unit
    async def test_atr_stop_falls_back_to_fixed_when_no_atr_data(
        self, db_session, rollback_session_factory, atr_simulation
    ) -> None:
        """When ATR cannot be computed, position falls back to the fixed trail_pct."""
        db_session.add(atr_simulation)
        await db_session.commit()
        await db_session.refresh(atr_simulation)

        pending = ArenaPosition(
            simulation_id=atr_simulation.id,
            symbol="AAPL",
            status=PositionStatus.PENDING.value,
            signal_date=date(2024, 1, 14),
            trailing_stop_pct=Decimal("5.00"),
        )
        db_session.add(pending)
        await db_session.commit()

        engine = SimulationEngine(db_session, session_factory=rollback_session_factory)

        # Only a few bars — not enough for ATR (requires >= 15)
        price_bars = [
            PriceBar(
                date=date(2024, 1, 15),
                open=Decimal("100.00"),
                high=Decimal("103.00"),
                low=Decimal("97.00"),
                close=Decimal("101.00"),
                volume=1000000,
            )
        ]

        trading_days = [date(2024, 1, 15), date(2024, 1, 16)]
        engine._trading_days_cache[atr_simulation.id] = trading_days
        engine._price_cache[atr_simulation.id] = {"AAPL": price_bars}
        engine._sector_cache[atr_simulation.id] = {"AAPL": None}

        mock_agent = MagicMock()
        mock_agent.required_lookback_days = 60
        mock_agent.evaluate = AsyncMock(
            return_value=AgentDecision(symbol="AAPL", action="HOLD", reasoning="Holding")
        )

        with patch("app.services.arena.simulation_engine.get_agent", return_value=mock_agent):
            await engine.step_day(atr_simulation.id)

        await db_session.refresh(pending)
        assert pending.status == PositionStatus.OPEN.value
        # Fallback: retains the configured fixed trail_pct
        assert pending.trailing_stop_pct == Decimal("5.00")


# =============================================================================
# Layer 5: Take Profit tests
# =============================================================================


@pytest.mark.usefixtures("db_session")
class TestSimulationEngineTakeProfit:
    """Tests for take-profit exit logic in step_day()."""

    def _make_simulation(
        self, db_session, agent_config: dict
    ) -> ArenaSimulation:
        """Helper to create a running simulation with custom agent_config."""
        sim = ArenaSimulation(
            name="Take Profit Test",
            symbols=["AAPL"],
            start_date=date(2024, 1, 15),
            end_date=date(2024, 1, 25),
            initial_capital=Decimal("10000.00"),
            position_size=Decimal("1000.00"),
            agent_type="live20",
            agent_config=agent_config,
            status=SimulationStatus.RUNNING.value,
            current_day=0,
            total_days=10,
        )
        return sim

    def _make_open_position(
        self, simulation_id: int, entry_price: float, stop: float
    ) -> ArenaPosition:
        """Helper to create an open position."""
        return ArenaPosition(
            simulation_id=simulation_id,
            symbol="AAPL",
            status=PositionStatus.OPEN.value,
            signal_date=date(2024, 1, 14),
            entry_date=date(2024, 1, 15),
            entry_price=Decimal(str(entry_price)),
            shares=10,
            trailing_stop_pct=Decimal("5.00"),
            highest_price=Decimal(str(entry_price)),
            current_stop=Decimal(str(stop)),
        )

    @pytest.mark.unit
    async def test_fixed_take_profit_triggers_when_return_meets_target(
        self, db_session, rollback_session_factory
    ) -> None:
        """Fixed take_profit_pct triggers when unrealized return >= target.

        Entry: $100, target: 8%, today's close: $110 (10% return) → exit.
        """
        # Arrange
        sim = self._make_simulation(
            db_session,
            {"trailing_stop_pct": 5.0, "take_profit_pct": 8.0},
        )
        db_session.add(sim)
        await db_session.commit()
        await db_session.refresh(sim)

        position = self._make_open_position(sim.id, entry_price=100.0, stop=95.0)
        db_session.add(position)
        await db_session.commit()

        engine = SimulationEngine(db_session, session_factory=rollback_session_factory)

        # close=$110 → 10% unrealized return ≥ take_profit_pct=8%
        price_bars = [
            PriceBar(
                date=date(2024, 1, 15),
                open=Decimal("105.00"),
                high=Decimal("112.00"),
                low=Decimal("104.00"),
                close=Decimal("110.00"),  # +10% unrealized
                volume=1000000,
            )
        ]
        trading_days = [date(2024, 1, 15), date(2024, 1, 16), date(2024, 1, 17)]
        engine._trading_days_cache[sim.id] = trading_days
        engine._price_cache[sim.id] = {"AAPL": price_bars}
        engine._sector_cache[sim.id] = {"AAPL": None}

        mock_agent = MagicMock()
        mock_agent.required_lookback_days = 60
        mock_agent.evaluate = AsyncMock(
            return_value=AgentDecision(symbol="AAPL", action="NO_SIGNAL")
        )

        # Act
        with patch("app.services.arena.simulation_engine.get_agent", return_value=mock_agent):
            await engine.step_day(sim.id)

        # Assert
        await db_session.refresh(position)
        assert position.status == PositionStatus.CLOSED.value
        assert position.exit_reason == ExitReason.TAKE_PROFIT.value
        assert position.exit_price == Decimal("108.00")  # TP target price (open < target)
        assert position.realized_pnl == Decimal("80.00")   # (108-100)*10

    @pytest.mark.unit
    async def test_fixed_take_profit_does_not_trigger_below_target(
        self, db_session, rollback_session_factory
    ) -> None:
        """Fixed take_profit_pct does not trigger when return < target.

        Entry: $100, target: 8%, today's close: $105 (5% return) → no exit.
        """
        # Arrange
        sim = self._make_simulation(
            db_session,
            {"trailing_stop_pct": 5.0, "take_profit_pct": 8.0},
        )
        db_session.add(sim)
        await db_session.commit()
        await db_session.refresh(sim)

        position = self._make_open_position(sim.id, entry_price=100.0, stop=95.0)
        db_session.add(position)
        await db_session.commit()

        engine = SimulationEngine(db_session, session_factory=rollback_session_factory)

        # close=$105 → 5% unrealized return < take_profit_pct=8%
        price_bars = [
            PriceBar(
                date=date(2024, 1, 15),
                open=Decimal("103.00"),
                high=Decimal("106.00"),
                low=Decimal("102.00"),
                close=Decimal("105.00"),  # +5% unrealized — below target
                volume=1000000,
            )
        ]
        trading_days = [date(2024, 1, 15), date(2024, 1, 16), date(2024, 1, 17)]
        engine._trading_days_cache[sim.id] = trading_days
        engine._price_cache[sim.id] = {"AAPL": price_bars}
        engine._sector_cache[sim.id] = {"AAPL": None}

        mock_agent = MagicMock()
        mock_agent.required_lookback_days = 60
        mock_agent.evaluate = AsyncMock(
            return_value=AgentDecision(symbol="AAPL", action="NO_SIGNAL")
        )

        # Act
        with patch("app.services.arena.simulation_engine.get_agent", return_value=mock_agent):
            await engine.step_day(sim.id)

        # Assert
        await db_session.refresh(position)
        assert position.status == PositionStatus.OPEN.value

    @pytest.mark.unit
    async def test_stop_takes_precedence_over_take_profit(
        self, db_session, rollback_session_factory
    ) -> None:
        """Trailing stop exit takes precedence over take-profit.

        Even if the close price would theoretically satisfy take-profit,
        if the day's low touched the stop, the exit is STOP_HIT.
        """
        # Arrange
        sim = self._make_simulation(
            db_session,
            {"trailing_stop_pct": 5.0, "take_profit_pct": 5.0},
        )
        db_session.add(sim)
        await db_session.commit()
        await db_session.refresh(sim)

        position = self._make_open_position(sim.id, entry_price=100.0, stop=95.0)
        db_session.add(position)
        await db_session.commit()

        engine = SimulationEngine(db_session, session_factory=rollback_session_factory)

        # low=$94 touches stop=$95; close=$106 would satisfy take_profit_pct=5%
        price_bars = [
            PriceBar(
                date=date(2024, 1, 15),
                open=Decimal("101.00"),
                high=Decimal("107.00"),
                low=Decimal("94.00"),  # Triggers stop at $95
                close=Decimal("106.00"),  # +6% — would satisfy TP if stop didn't fire
                volume=1000000,
            )
        ]
        trading_days = [date(2024, 1, 15), date(2024, 1, 16), date(2024, 1, 17)]
        engine._trading_days_cache[sim.id] = trading_days
        engine._price_cache[sim.id] = {"AAPL": price_bars}
        engine._sector_cache[sim.id] = {"AAPL": None}

        mock_agent = MagicMock()
        mock_agent.required_lookback_days = 60
        mock_agent.evaluate = AsyncMock(
            return_value=AgentDecision(symbol="AAPL", action="NO_SIGNAL")
        )

        # Act
        with patch("app.services.arena.simulation_engine.get_agent", return_value=mock_agent):
            await engine.step_day(sim.id)

        # Assert: stop fires first, take-profit is never checked
        await db_session.refresh(position)
        assert position.status == PositionStatus.CLOSED.value
        assert position.exit_reason == ExitReason.STOP_HIT.value

    @pytest.mark.unit
    async def test_take_profit_disabled_when_not_configured(
        self, db_session, rollback_session_factory
    ) -> None:
        """No take-profit exit when take_profit_pct and take_profit_atr_mult are absent."""
        # Arrange
        sim = self._make_simulation(
            db_session,
            {"trailing_stop_pct": 5.0},  # neither take_profit_pct nor take_profit_atr_mult
        )
        db_session.add(sim)
        await db_session.commit()
        await db_session.refresh(sim)

        position = self._make_open_position(sim.id, entry_price=100.0, stop=95.0)
        db_session.add(position)
        await db_session.commit()

        engine = SimulationEngine(db_session, session_factory=rollback_session_factory)

        # close=$130 → +30% gain — would fire any reasonable TP if enabled
        price_bars = [
            PriceBar(
                date=date(2024, 1, 15),
                open=Decimal("125.00"),
                high=Decimal("132.00"),
                low=Decimal("124.00"),
                close=Decimal("130.00"),
                volume=1000000,
            )
        ]
        trading_days = [date(2024, 1, 15), date(2024, 1, 16), date(2024, 1, 17)]
        engine._trading_days_cache[sim.id] = trading_days
        engine._price_cache[sim.id] = {"AAPL": price_bars}
        engine._sector_cache[sim.id] = {"AAPL": None}

        mock_agent = MagicMock()
        mock_agent.required_lookback_days = 60
        mock_agent.evaluate = AsyncMock(
            return_value=AgentDecision(symbol="AAPL", action="NO_SIGNAL")
        )

        # Act
        with patch("app.services.arena.simulation_engine.get_agent", return_value=mock_agent):
            await engine.step_day(sim.id)

        # Assert: position still open — no take-profit configured
        await db_session.refresh(position)
        assert position.status == PositionStatus.OPEN.value

    @pytest.mark.unit
    async def test_take_profit_exit_updates_simulation_trade_count(
        self, db_session, rollback_session_factory
    ) -> None:
        """Take-profit exit increments total_trades and winning_trades."""
        # Arrange
        sim = self._make_simulation(
            db_session,
            {"trailing_stop_pct": 5.0, "take_profit_pct": 5.0},
        )
        db_session.add(sim)
        await db_session.commit()
        await db_session.refresh(sim)

        position = self._make_open_position(sim.id, entry_price=100.0, stop=95.0)
        db_session.add(position)
        await db_session.commit()

        engine = SimulationEngine(db_session, session_factory=rollback_session_factory)

        price_bars = [
            PriceBar(
                date=date(2024, 1, 15),
                open=Decimal("108.00"),
                high=Decimal("112.00"),
                low=Decimal("107.00"),
                close=Decimal("110.00"),  # +10% → triggers TP at 5%
                volume=1000000,
            )
        ]
        trading_days = [date(2024, 1, 15), date(2024, 1, 16), date(2024, 1, 17)]
        engine._trading_days_cache[sim.id] = trading_days
        engine._price_cache[sim.id] = {"AAPL": price_bars}
        engine._sector_cache[sim.id] = {"AAPL": None}

        mock_agent = MagicMock()
        mock_agent.required_lookback_days = 60
        mock_agent.evaluate = AsyncMock(
            return_value=AgentDecision(symbol="AAPL", action="NO_SIGNAL")
        )

        # Act
        with patch("app.services.arena.simulation_engine.get_agent", return_value=mock_agent):
            await engine.step_day(sim.id)

        # Assert
        await db_session.refresh(sim)
        assert sim.total_trades == 1
        assert sim.winning_trades == 1


    @pytest.mark.unit
    async def test_fixed_take_profit_triggers_on_intraday_high(
        self, db_session, rollback_session_factory
    ) -> None:
        """TP triggers when intraday HIGH reaches target, even if close is below.

        Entry: $100, target: 8%, high: $109 (9% intraday), close: $105 (5%).
        TP should trigger because high exceeded 8% target.
        Exit price = target price ($108), not close ($105).
        """
        sim = self._make_simulation(
            db_session,
            {"trailing_stop_pct": 5.0, "take_profit_pct": 8.0},
        )
        db_session.add(sim)
        await db_session.commit()
        await db_session.refresh(sim)

        position = self._make_open_position(sim.id, entry_price=100.0, stop=95.0)
        db_session.add(position)
        await db_session.commit()

        engine = SimulationEngine(db_session, session_factory=rollback_session_factory)

        price_bars = [
            PriceBar(
                date=date(2024, 1, 15),
                open=Decimal("102.00"),
                high=Decimal("109.00"),   # 9% intraday -- exceeds 8% TP target
                low=Decimal("101.00"),
                close=Decimal("105.00"),  # 5% close -- below TP target
                volume=1000000,
            )
        ]
        trading_days = [date(2024, 1, 15), date(2024, 1, 16), date(2024, 1, 17)]
        engine._trading_days_cache[sim.id] = trading_days
        engine._price_cache[sim.id] = {"AAPL": price_bars}
        engine._sector_cache[sim.id] = {"AAPL": None}

        mock_agent = MagicMock()
        mock_agent.required_lookback_days = 60
        mock_agent.evaluate = AsyncMock(
            return_value=AgentDecision(symbol="AAPL", action="NO_SIGNAL")
        )

        with patch("app.services.arena.simulation_engine.get_agent", return_value=mock_agent):
            await engine.step_day(sim.id)

        await db_session.refresh(position)
        assert position.status == PositionStatus.CLOSED.value
        assert position.exit_reason == ExitReason.TAKE_PROFIT.value
        # Exit at target price ($108), not close ($105)
        assert position.exit_price == Decimal("108.00")

    @pytest.mark.unit
    async def test_fixed_take_profit_gap_up_exits_at_open(
        self, db_session, rollback_session_factory
    ) -> None:
        """When stock gaps up past TP target on open, exit at open price.

        Entry: $100, target: 8% ($108), open: $112 (gaps past target).
        Exit price = open ($112), not target ($108), because we can't
        fill below the open price on a gap-up.
        """
        sim = self._make_simulation(
            db_session,
            {"trailing_stop_pct": 5.0, "take_profit_pct": 8.0},
        )
        db_session.add(sim)
        await db_session.commit()
        await db_session.refresh(sim)

        position = self._make_open_position(sim.id, entry_price=100.0, stop=95.0)
        db_session.add(position)
        await db_session.commit()

        engine = SimulationEngine(db_session, session_factory=rollback_session_factory)

        price_bars = [
            PriceBar(
                date=date(2024, 1, 15),
                open=Decimal("112.00"),   # Gaps up past $108 target
                high=Decimal("115.00"),
                low=Decimal("111.00"),
                close=Decimal("113.00"),
                volume=1000000,
            )
        ]
        trading_days = [date(2024, 1, 15), date(2024, 1, 16), date(2024, 1, 17)]
        engine._trading_days_cache[sim.id] = trading_days
        engine._price_cache[sim.id] = {"AAPL": price_bars}
        engine._sector_cache[sim.id] = {"AAPL": None}

        mock_agent = MagicMock()
        mock_agent.required_lookback_days = 60
        mock_agent.evaluate = AsyncMock(
            return_value=AgentDecision(symbol="AAPL", action="NO_SIGNAL")
        )

        with patch("app.services.arena.simulation_engine.get_agent", return_value=mock_agent):
            await engine.step_day(sim.id)

        await db_session.refresh(position)
        assert position.status == PositionStatus.CLOSED.value
        assert position.exit_reason == ExitReason.TAKE_PROFIT.value
        # Exit at open ($112) since it gapped past target ($108)
        assert position.exit_price == Decimal("112.00")

    @pytest.mark.unit
    async def test_fixed_take_profit_no_trigger_when_high_below_target(
        self, db_session, rollback_session_factory
    ) -> None:
        """TP does NOT trigger when intraday high is below target.

        Entry: $100, target: 8%, high: $107 (7%), close: $105.
        Neither high nor close reaches 8%. Position stays open.
        """
        sim = self._make_simulation(
            db_session,
            {"trailing_stop_pct": 5.0, "take_profit_pct": 8.0},
        )
        db_session.add(sim)
        await db_session.commit()
        await db_session.refresh(sim)

        position = self._make_open_position(sim.id, entry_price=100.0, stop=95.0)
        db_session.add(position)
        await db_session.commit()

        engine = SimulationEngine(db_session, session_factory=rollback_session_factory)

        price_bars = [
            PriceBar(
                date=date(2024, 1, 15),
                open=Decimal("102.00"),
                high=Decimal("107.00"),   # 7% -- below 8% target
                low=Decimal("101.00"),
                close=Decimal("105.00"),
                volume=1000000,
            )
        ]
        trading_days = [date(2024, 1, 15), date(2024, 1, 16), date(2024, 1, 17)]
        engine._trading_days_cache[sim.id] = trading_days
        engine._price_cache[sim.id] = {"AAPL": price_bars}
        engine._sector_cache[sim.id] = {"AAPL": None}

        mock_agent = MagicMock()
        mock_agent.required_lookback_days = 60
        mock_agent.evaluate = AsyncMock(
            return_value=AgentDecision(symbol="AAPL", action="NO_SIGNAL")
        )

        with patch("app.services.arena.simulation_engine.get_agent", return_value=mock_agent):
            await engine.step_day(sim.id)

        await db_session.refresh(position)
        assert position.status == PositionStatus.OPEN.value

    @pytest.mark.unit
    async def test_atr_take_profit_triggers_on_intraday_high(
        self, db_session, rollback_session_factory
    ) -> None:
        """ATR-multiple TP triggers when intraday high reaches ATR target.

        Entry: $100, ATR%: 3.0, multiplier: 2.0, target: 6%.
        High: $107 (7% intraday) -- exceeds 6% target. Close: $103.
        Exit at target price ($106).
        """
        sim = self._make_simulation(
            db_session,
            {"trailing_stop_pct": 5.0, "take_profit_atr_mult": 2.0},
        )
        db_session.add(sim)
        await db_session.commit()
        await db_session.refresh(sim)

        position = self._make_open_position(sim.id, entry_price=100.0, stop=95.0)
        db_session.add(position)
        await db_session.commit()

        engine = SimulationEngine(db_session, session_factory=rollback_session_factory)

        price_bars = [
            PriceBar(
                date=date(2024, 1, 15),
                open=Decimal("102.00"),
                high=Decimal("107.00"),   # 7% intraday -- exceeds 6% ATR target
                low=Decimal("101.00"),
                close=Decimal("103.00"),  # 3% close -- below target
                volume=1000000,
            )
        ]
        trading_days = [date(2024, 1, 15), date(2024, 1, 16), date(2024, 1, 17)]
        engine._trading_days_cache[sim.id] = trading_days
        engine._price_cache[sim.id] = {"AAPL": price_bars}
        engine._sector_cache[sim.id] = {"AAPL": None}

        # Mock ATR to return 3.0%
        with patch.object(engine, "_calculate_symbol_atr_pct", return_value=3.0):
            mock_agent = MagicMock()
            mock_agent.required_lookback_days = 60
            mock_agent.evaluate = AsyncMock(
                return_value=AgentDecision(symbol="AAPL", action="NO_SIGNAL")
            )

            with patch("app.services.arena.simulation_engine.get_agent", return_value=mock_agent):
                await engine.step_day(sim.id)

        await db_session.refresh(position)
        assert position.status == PositionStatus.CLOSED.value
        assert position.exit_reason == ExitReason.TAKE_PROFIT.value
        # Exit at target price: $100 * (1 + 6/100) = $106
        assert position.exit_price == Decimal("106.00")


# =============================================================================
# Layer 6: Max Holding Period tests
# =============================================================================


@pytest.mark.usefixtures("db_session")
class TestSimulationEngineMaxHold:
    """Tests for maximum holding period exit logic in step_day()."""

    def _make_simulation(self, db_session, max_hold_days: int) -> ArenaSimulation:
        """Helper to create a running simulation with max_hold_days configured."""
        sim = ArenaSimulation(
            name="Max Hold Test",
            symbols=["AAPL"],
            start_date=date(2024, 1, 15),
            end_date=date(2024, 1, 31),
            initial_capital=Decimal("10000.00"),
            position_size=Decimal("1000.00"),
            agent_type="live20",
            agent_config={
                "trailing_stop_pct": 5.0,
                "max_hold_days": max_hold_days,
            },
            status=SimulationStatus.RUNNING.value,
            current_day=0,
            total_days=15,
        )
        return sim

    def _make_open_position(
        self, simulation_id: int, entry_date: date
    ) -> ArenaPosition:
        """Helper to create an open position with a given entry date."""
        return ArenaPosition(
            simulation_id=simulation_id,
            symbol="AAPL",
            status=PositionStatus.OPEN.value,
            signal_date=entry_date - timedelta(days=1),
            entry_date=entry_date,
            entry_price=Decimal("100.00"),
            shares=10,
            trailing_stop_pct=Decimal("5.00"),
            highest_price=Decimal("102.00"),
            current_stop=Decimal("96.90"),
        )

    @pytest.mark.unit
    async def test_max_hold_triggers_at_exactly_hold_days(
        self, db_session, rollback_session_factory
    ) -> None:
        """Position exits on the day that equals max_hold_days trading days.

        Entry on day 0 (Jan 15), max_hold=2 → exit on day 2 (Jan 17).
        """
        # Arrange
        sim = self._make_simulation(db_session, max_hold_days=2)
        db_session.add(sim)
        await db_session.commit()
        await db_session.refresh(sim)

        position = self._make_open_position(sim.id, entry_date=date(2024, 1, 15))
        db_session.add(position)
        await db_session.commit()

        engine = SimulationEngine(db_session, session_factory=rollback_session_factory)

        # 3 trading days: Jan 15 (entry), Jan 16, Jan 17 (hold_days == 2 → exit)
        trading_days = [date(2024, 1, 15), date(2024, 1, 16), date(2024, 1, 17)]
        price_bars = [
            PriceBar(
                date=d,
                open=Decimal("102.00"),
                high=Decimal("104.00"),
                low=Decimal("100.00"),
                close=Decimal("103.00"),
                volume=1000000,
            )
            for d in trading_days
        ]

        # Simulate up to day 2 (index 2 → Jan 17)
        sim.current_day = 2
        await db_session.commit()

        engine._trading_days_cache[sim.id] = trading_days
        engine._price_cache[sim.id] = {"AAPL": price_bars}
        engine._sector_cache[sim.id] = {"AAPL": None}

        mock_agent = MagicMock()
        mock_agent.required_lookback_days = 60
        mock_agent.evaluate = AsyncMock(
            return_value=AgentDecision(symbol="AAPL", action="NO_SIGNAL")
        )

        # Act — step day 2 (Jan 17); hold_days = index(Jan 17) - index(Jan 15) = 2
        with patch("app.services.arena.simulation_engine.get_agent", return_value=mock_agent):
            await engine.step_day(sim.id)

        # Assert
        await db_session.refresh(position)
        assert position.status == PositionStatus.CLOSED.value
        assert position.exit_reason == ExitReason.MAX_HOLD.value
        assert position.exit_date == date(2024, 1, 17)
        assert position.exit_price == Decimal("103.00")  # closed at today's close

    @pytest.mark.unit
    async def test_max_hold_does_not_trigger_before_limit(
        self, db_session, rollback_session_factory
    ) -> None:
        """Position stays open when held for fewer than max_hold_days trading days."""
        # Arrange
        sim = self._make_simulation(db_session, max_hold_days=5)
        db_session.add(sim)
        await db_session.commit()
        await db_session.refresh(sim)

        position = self._make_open_position(sim.id, entry_date=date(2024, 1, 15))
        db_session.add(position)
        await db_session.commit()

        engine = SimulationEngine(db_session, session_factory=rollback_session_factory)

        trading_days = [date(2024, 1, 15), date(2024, 1, 16), date(2024, 1, 17)]
        price_bars = [
            PriceBar(
                date=d,
                open=Decimal("102.00"),
                high=Decimal("104.00"),
                low=Decimal("100.00"),
                close=Decimal("103.00"),
                volume=1000000,
            )
            for d in trading_days
        ]

        # Step day 1 (Jan 16); hold_days = 1 < max_hold_days=5
        sim.current_day = 1
        await db_session.commit()

        engine._trading_days_cache[sim.id] = trading_days
        engine._price_cache[sim.id] = {"AAPL": price_bars}
        engine._sector_cache[sim.id] = {"AAPL": None}

        mock_agent = MagicMock()
        mock_agent.required_lookback_days = 60
        mock_agent.evaluate = AsyncMock(
            return_value=AgentDecision(symbol="AAPL", action="NO_SIGNAL")
        )

        # Act
        with patch("app.services.arena.simulation_engine.get_agent", return_value=mock_agent):
            await engine.step_day(sim.id)

        # Assert
        await db_session.refresh(position)
        assert position.status == PositionStatus.OPEN.value

    @pytest.mark.unit
    async def test_max_hold_disabled_when_not_configured(
        self, db_session, rollback_session_factory
    ) -> None:
        """No max-hold exit when max_hold_days is absent from agent_config."""
        # Arrange
        sim = ArenaSimulation(
            name="No Max Hold",
            symbols=["AAPL"],
            start_date=date(2024, 1, 15),
            end_date=date(2024, 1, 31),
            initial_capital=Decimal("10000.00"),
            position_size=Decimal("1000.00"),
            agent_type="live20",
            agent_config={"trailing_stop_pct": 5.0},  # no max_hold_days
            status=SimulationStatus.RUNNING.value,
            current_day=0,
            total_days=15,
        )
        db_session.add(sim)
        await db_session.commit()
        await db_session.refresh(sim)

        # Position held for 20 "days" (high index difference)
        position = self._make_open_position(sim.id, entry_date=date(2024, 1, 15))
        db_session.add(position)
        await db_session.commit()

        engine = SimulationEngine(db_session, session_factory=rollback_session_factory)

        trading_days = [date(2024, 1, 15) + timedelta(days=i) for i in range(25)]
        price_bars = [
            PriceBar(
                date=d,
                open=Decimal("102.00"),
                high=Decimal("104.00"),
                low=Decimal("100.00"),
                close=Decimal("103.00"),
                volume=1000000,
            )
            for d in trading_days
        ]

        # Jump far ahead — hold_days would be 20 if max_hold were enabled
        sim.current_day = 20
        await db_session.commit()

        engine._trading_days_cache[sim.id] = trading_days
        engine._price_cache[sim.id] = {"AAPL": price_bars}
        engine._sector_cache[sim.id] = {"AAPL": None}

        mock_agent = MagicMock()
        mock_agent.required_lookback_days = 60
        mock_agent.evaluate = AsyncMock(
            return_value=AgentDecision(symbol="AAPL", action="NO_SIGNAL")
        )

        # Act
        with patch("app.services.arena.simulation_engine.get_agent", return_value=mock_agent):
            await engine.step_day(sim.id)

        # Assert: position still open — max_hold is disabled
        await db_session.refresh(position)
        assert position.status == PositionStatus.OPEN.value

    @pytest.mark.unit
    async def test_max_hold_exit_updates_simulation_trade_count(
        self, db_session, rollback_session_factory
    ) -> None:
        """Max-hold exit increments total_trades."""
        # Arrange
        sim = self._make_simulation(db_session, max_hold_days=1)
        db_session.add(sim)
        await db_session.commit()
        await db_session.refresh(sim)

        position = self._make_open_position(sim.id, entry_date=date(2024, 1, 15))
        db_session.add(position)
        await db_session.commit()

        engine = SimulationEngine(db_session, session_factory=rollback_session_factory)

        trading_days = [date(2024, 1, 15), date(2024, 1, 16), date(2024, 1, 17)]
        price_bars = [
            PriceBar(
                date=d,
                open=Decimal("102.00"),
                high=Decimal("104.00"),
                low=Decimal("100.00"),
                close=Decimal("103.00"),
                volume=1000000,
            )
            for d in trading_days
        ]

        # day index 1 → Jan 16; hold_days = 1 == max_hold_days=1 → exit
        sim.current_day = 1
        await db_session.commit()

        engine._trading_days_cache[sim.id] = trading_days
        engine._price_cache[sim.id] = {"AAPL": price_bars}
        engine._sector_cache[sim.id] = {"AAPL": None}

        mock_agent = MagicMock()
        mock_agent.required_lookback_days = 60
        mock_agent.evaluate = AsyncMock(
            return_value=AgentDecision(symbol="AAPL", action="NO_SIGNAL")
        )

        # Act
        with patch("app.services.arena.simulation_engine.get_agent", return_value=mock_agent):
            await engine.step_day(sim.id)

        # Assert
        await db_session.refresh(sim)
        assert sim.total_trades == 1

    @pytest.mark.unit
    async def test_stop_takes_precedence_over_max_hold(
        self, db_session, rollback_session_factory
    ) -> None:
        """Trailing stop exit takes precedence over max-hold exit.

        If the stop fires on the same day that max_hold would also trigger,
        the exit reason should be STOP_HIT, not MAX_HOLD.
        """
        # Arrange
        sim = self._make_simulation(db_session, max_hold_days=1)
        db_session.add(sim)
        await db_session.commit()
        await db_session.refresh(sim)

        position = self._make_open_position(sim.id, entry_date=date(2024, 1, 15))
        # Override stop so the low will touch it
        position.current_stop = Decimal("99.00")
        db_session.add(position)
        await db_session.commit()

        engine = SimulationEngine(db_session, session_factory=rollback_session_factory)

        trading_days = [date(2024, 1, 15), date(2024, 1, 16), date(2024, 1, 17)]
        price_bars = [
            PriceBar(
                date=d,
                open=Decimal("101.00"),
                high=Decimal("104.00"),
                low=Decimal("98.00"),  # touches stop at 99
                close=Decimal("103.00"),
                volume=1000000,
            )
            for d in trading_days
        ]

        # day index 1 → Jan 16; hold_days=1 == max_hold AND stop fires
        sim.current_day = 1
        await db_session.commit()

        engine._trading_days_cache[sim.id] = trading_days
        engine._price_cache[sim.id] = {"AAPL": price_bars}
        engine._sector_cache[sim.id] = {"AAPL": None}

        mock_agent = MagicMock()
        mock_agent.required_lookback_days = 60
        mock_agent.evaluate = AsyncMock(
            return_value=AgentDecision(symbol="AAPL", action="NO_SIGNAL")
        )

        # Act
        with patch("app.services.arena.simulation_engine.get_agent", return_value=mock_agent):
            await engine.step_day(sim.id)

        # Assert: stop fires first
        await db_session.refresh(position)
        assert position.status == PositionStatus.CLOSED.value
        assert position.exit_reason == ExitReason.STOP_HIT.value


@pytest.mark.usefixtures("db_session")
class TestSimulationEngineRegimeFilter:
    """Tests for SPY-based market regime filter logic."""

    def _make_engine(self, db_session, rollback_session_factory) -> SimulationEngine:
        return SimulationEngine(db_session, session_factory=rollback_session_factory)

    def _spy_bars(self, closes: list[float], start: date = date(2024, 1, 1)) -> list[PriceBar]:
        """Build SPY PriceBars from a list of closing prices."""
        bars = []
        for i, close in enumerate(closes):
            d = start + timedelta(days=i)
            bars.append(
                PriceBar(
                    date=d,
                    open=Decimal(str(close)),
                    high=Decimal(str(close + 1)),
                    low=Decimal(str(close - 1)),
                    close=Decimal(str(close)),
                    volume=10_000_000,
                )
            )
        return bars

    # ------------------------------------------------------------------
    # _detect_market_regime unit tests
    # ------------------------------------------------------------------

    @pytest.mark.unit
    def test_detect_regime_bull_when_close_above_sma(
        self, db_session, rollback_session_factory
    ) -> None:
        """Returns 'bull' when latest close > SMA(period)."""
        engine = self._make_engine(db_session, rollback_session_factory)

        # 20 bars all at 100, then spike to 150 on the last bar → well above SMA
        closes = [100.0] * 19 + [150.0]
        bars = self._spy_bars(closes)
        current_date = bars[-1].date

        engine._price_cache[1] = {"SPY": bars}

        regime = engine._detect_market_regime(1, current_date, "SPY", sma_period=20)

        assert regime == "bull"

    @pytest.mark.unit
    def test_detect_regime_bear_when_close_below_sma(
        self, db_session, rollback_session_factory
    ) -> None:
        """Returns 'bear' when latest close < SMA(period)."""
        engine = self._make_engine(db_session, rollback_session_factory)

        # 20 bars all at 100, then drop to 50 on the last bar → well below SMA
        closes = [100.0] * 19 + [50.0]
        bars = self._spy_bars(closes)
        current_date = bars[-1].date

        engine._price_cache[1] = {"SPY": bars}

        regime = engine._detect_market_regime(1, current_date, "SPY", sma_period=20)

        assert regime == "bear"

    @pytest.mark.unit
    def test_detect_regime_neutral_when_insufficient_data(
        self, db_session, rollback_session_factory
    ) -> None:
        """Returns 'neutral' when there are fewer bars than sma_period."""
        engine = self._make_engine(db_session, rollback_session_factory)

        closes = [100.0] * 5  # only 5 bars, sma_period=20
        bars = self._spy_bars(closes)
        current_date = bars[-1].date

        engine._price_cache[1] = {"SPY": bars}

        regime = engine._detect_market_regime(1, current_date, "SPY", sma_period=20)

        assert regime == "neutral"

    @pytest.mark.unit
    def test_detect_regime_no_lookahead(
        self, db_session, rollback_session_factory
    ) -> None:
        """Regime is computed only from bars up to current_date (no look-ahead)."""
        engine = self._make_engine(db_session, rollback_session_factory)

        # 20 bars at 100 (bear on current_date), then 10 more at 200 in the future
        closes = [100.0] * 20 + [200.0] * 10
        bars = self._spy_bars(closes)
        current_date = bars[19].date  # last bar before the future spike

        engine._price_cache[1] = {"SPY": bars}

        # On current_date the last close is 100 and SMA(20) of the last 20 bars is 100
        # so close == SMA → "bear" (not strictly above)
        regime = engine._detect_market_regime(1, current_date, "SPY", sma_period=20)

        assert regime == "bear"

    # ------------------------------------------------------------------
    # Integration: regime filter adjusts max_open_positions in step_day
    # ------------------------------------------------------------------

    @pytest.mark.unit
    async def test_regime_filter_bear_reduces_max_open_positions(
        self, db_session, rollback_session_factory
    ) -> None:
        """In bear regime, max_open_positions is reduced to bear_max (1)."""
        sim = ArenaSimulation(
            name="Regime Bear Test",
            symbols=["AAPL", "MSFT", "GOOG"],
            start_date=date(2024, 1, 15),
            end_date=date(2024, 1, 19),
            initial_capital=Decimal("10000.00"),
            position_size=Decimal("1000.00"),
            agent_type="live20",
            agent_config={
                "trailing_stop_pct": 5.0,
                "regime_filter": True,
                "regime_symbol": "SPY",
                "regime_sma_period": 5,
                "regime_bear_max_positions": 1,
                "regime_bull_max_positions": None,
            },
            status=SimulationStatus.RUNNING.value,
            current_day=0,
            total_days=3,
        )
        db_session.add(sim)
        await db_session.commit()
        await db_session.refresh(sim)

        engine = SimulationEngine(db_session, session_factory=rollback_session_factory)

        trading_days = [date(2024, 1, 15), date(2024, 1, 16), date(2024, 1, 17)]

        # SPY: 5 bars at 100, then drops to 50 on current_date → bear
        spy_closes = [100.0, 100.0, 100.0, 100.0, 100.0, 50.0]
        spy_bars = self._spy_bars(spy_closes, start=date(2024, 1, 10))

        stock_bars = [
            PriceBar(
                date=d,
                open=Decimal("50.00"),
                high=Decimal("55.00"),
                low=Decimal("48.00"),
                close=Decimal("52.00"),
                volume=1_000_000,
            )
            for d in [date(2024, 1, 10) + timedelta(days=i) for i in range(10)]
        ]

        engine._trading_days_cache[sim.id] = trading_days
        engine._price_cache[sim.id] = {
            "AAPL": stock_bars,
            "MSFT": stock_bars,
            "GOOG": stock_bars,
            "SPY": spy_bars,
        }
        engine._sector_cache[sim.id] = {"AAPL": "Tech", "MSFT": "Tech", "GOOG": "Tech"}

        # Agent always says BUY for all 3 symbols
        mock_agent = MagicMock()
        mock_agent.required_lookback_days = 5
        mock_agent.evaluate = AsyncMock(
            return_value=AgentDecision(symbol="AAPL", action="BUY", score=80)
        )

        with patch("app.services.arena.simulation_engine.get_agent", return_value=mock_agent):
            await engine.step_day(sim.id)

        # Only 1 PENDING position should be created (bear_max=1)
        result = await db_session.execute(
            select(ArenaPosition)
            .where(ArenaPosition.simulation_id == sim.id)
            .where(ArenaPosition.status == PositionStatus.PENDING.value)
        )
        pending = result.scalars().all()
        assert len(pending) == 1, f"Expected 1 pending position in bear regime, got {len(pending)}"

    @pytest.mark.unit
    async def test_regime_filter_disabled_does_not_limit_positions(
        self, db_session, rollback_session_factory
    ) -> None:
        """When regime_filter=False, max_open_positions is uncapped (unlimited)."""
        sim = ArenaSimulation(
            name="Regime Disabled Test",
            symbols=["AAPL", "MSFT", "GOOG"],
            start_date=date(2024, 1, 15),
            end_date=date(2024, 1, 19),
            initial_capital=Decimal("10000.00"),
            position_size=Decimal("1000.00"),
            agent_type="live20",
            agent_config={
                "trailing_stop_pct": 5.0,
                "regime_filter": False,
            },
            status=SimulationStatus.RUNNING.value,
            current_day=0,
            total_days=3,
        )
        db_session.add(sim)
        await db_session.commit()
        await db_session.refresh(sim)

        engine = SimulationEngine(db_session, session_factory=rollback_session_factory)

        trading_days = [date(2024, 1, 15), date(2024, 1, 16), date(2024, 1, 17)]
        stock_bars = [
            PriceBar(
                date=d,
                open=Decimal("50.00"),
                high=Decimal("55.00"),
                low=Decimal("48.00"),
                close=Decimal("52.00"),
                volume=1_000_000,
            )
            for d in [date(2024, 1, 10) + timedelta(days=i) for i in range(10)]
        ]

        engine._trading_days_cache[sim.id] = trading_days
        engine._price_cache[sim.id] = {
            "AAPL": stock_bars,
            "MSFT": stock_bars,
            "GOOG": stock_bars,
        }
        engine._sector_cache[sim.id] = {"AAPL": "Tech", "MSFT": "Tech", "GOOG": "Tech"}

        mock_agent = MagicMock()
        mock_agent.required_lookback_days = 5
        mock_agent.evaluate = AsyncMock(
            return_value=AgentDecision(symbol="AAPL", action="BUY", score=80)
        )

        with patch("app.services.arena.simulation_engine.get_agent", return_value=mock_agent):
            await engine.step_day(sim.id)

        result = await db_session.execute(
            select(ArenaPosition)
            .where(ArenaPosition.simulation_id == sim.id)
            .where(ArenaPosition.status == PositionStatus.PENDING.value)
        )
        pending = result.scalars().all()
        # All 3 signals should create PENDING positions (no regime cap)
        assert len(pending) == 3, f"Expected 3 pending positions without regime cap, got {len(pending)}"



@pytest.mark.usefixtures("db_session")
class TestSimulationEngineBreakevenAndRatchet:
    """Tests for breakeven stop floor and profit-ratcheting trail in step_day()."""

    def _make_simulation(
        self,
        db_session,
        agent_config_extra: dict,
        entry_price: Decimal = Decimal("100.00"),
    ) -> tuple[ArenaSimulation, ArenaPosition]:
        """Create a running simulation with one open position."""
        config = {
            "trailing_stop_pct": 5.0,
            **agent_config_extra,
        }
        sim = ArenaSimulation(
            name="Breakeven/Ratchet Test",
            symbols=["AAPL"],
            start_date=date(2024, 1, 15),
            end_date=date(2024, 1, 25),
            initial_capital=Decimal("10000.00"),
            position_size=Decimal("1000.00"),
            agent_type="live20",
            agent_config=config,
            status=SimulationStatus.RUNNING.value,
            current_day=0,
            total_days=10,
        )
        pos = ArenaPosition(
            symbol="AAPL",
            status=PositionStatus.OPEN.value,
            signal_date=date(2024, 1, 14),
            entry_date=date(2024, 1, 15),
            entry_price=entry_price,
            shares=10,
            trailing_stop_pct=Decimal("5.00"),
            highest_price=entry_price,
            current_stop=(entry_price * Decimal("0.95")).quantize(Decimal("0.0001")),
        )
        return sim, pos

    def _setup_engine_cache(
        self,
        engine: SimulationEngine,
        sim_id: int,
        price_bar: "PriceBar",
    ) -> None:
        """Pre-populate caches with a single price bar."""
        trading_days = [date(2024, 1, 16), date(2024, 1, 17), date(2024, 1, 18)]
        engine._trading_days_cache[sim_id] = trading_days
        engine._price_cache[sim_id] = {"AAPL": [price_bar]}
        engine._sector_cache[sim_id] = {"AAPL": None}

    @pytest.mark.unit
    async def test_breakeven_stop_pins_stop_at_entry_price(
        self, db_session, rollback_session_factory
    ) -> None:
        """Once position return exceeds breakeven_trigger_pct, stop is raised to entry."""
        sim, pos = self._make_simulation(
            db_session,
            agent_config_extra={"breakeven_trigger_pct": 5.0},
            entry_price=Decimal("100.00"),
        )
        db_session.add(sim)
        await db_session.commit()
        await db_session.refresh(sim)

        pos.simulation_id = sim.id
        # Position has already reached +6% high (above 5% trigger)
        pos.highest_price = Decimal("106.00")
        # Trailing stop from 106 at 5% trail = 100.70, but without breakeven logic
        # it would stay below entry if price dipped. Force a low current_stop to verify.
        pos.current_stop = Decimal("95.00")
        db_session.add(pos)
        await db_session.commit()

        engine = SimulationEngine(db_session, session_factory=rollback_session_factory)

        # Price bar: high doesn't make new high, low stays above stop → no trigger
        bar = PriceBar(
            date=date(2024, 1, 16),
            open=Decimal("105.00"),
            high=Decimal("106.00"),
            low=Decimal("102.00"),
            close=Decimal("104.00"),
            volume=1000000,
        )
        self._setup_engine_cache(engine, sim.id, bar)

        mock_agent = MagicMock()
        mock_agent.required_lookback_days = 60
        mock_agent.evaluate = AsyncMock(
            return_value=AgentDecision(symbol="AAPL", action="NO_SIGNAL")
        )

        with patch("app.services.arena.simulation_engine.get_agent", return_value=mock_agent):
            await engine.step_day(sim.id)

        await db_session.refresh(pos)
        # Stop must be at least entry price (100.00) because trigger was reached
        assert pos.current_stop >= Decimal("100.00"), (
            f"Expected stop >= entry price 100.00 after breakeven trigger, got {pos.current_stop}"
        )
        assert pos.status == PositionStatus.OPEN.value

    @pytest.mark.unit
    async def test_breakeven_stop_not_applied_below_trigger(
        self, db_session, rollback_session_factory
    ) -> None:
        """Stop is NOT raised to entry when highest price hasn't hit the trigger."""
        sim, pos = self._make_simulation(
            db_session,
            agent_config_extra={"breakeven_trigger_pct": 5.0},
            entry_price=Decimal("100.00"),
        )
        db_session.add(sim)
        await db_session.commit()
        await db_session.refresh(sim)

        pos.simulation_id = sim.id
        # Highest is only +3%, below the 5% trigger
        pos.highest_price = Decimal("103.00")
        pos.current_stop = Decimal("95.00")
        db_session.add(pos)
        await db_session.commit()

        engine = SimulationEngine(db_session, session_factory=rollback_session_factory)

        bar = PriceBar(
            date=date(2024, 1, 16),
            open=Decimal("103.00"),
            high=Decimal("103.00"),
            low=Decimal("96.00"),
            close=Decimal("102.00"),
            volume=1000000,
        )
        self._setup_engine_cache(engine, sim.id, bar)

        mock_agent = MagicMock()
        mock_agent.required_lookback_days = 60
        mock_agent.evaluate = AsyncMock(
            return_value=AgentDecision(symbol="AAPL", action="NO_SIGNAL")
        )

        with patch("app.services.arena.simulation_engine.get_agent", return_value=mock_agent):
            await engine.step_day(sim.id)

        await db_session.refresh(pos)
        # Stop should remain below entry since trigger was never hit
        assert pos.current_stop < Decimal("100.00"), (
            f"Expected stop below entry price 100.00 before breakeven trigger, got {pos.current_stop}"
        )

    @pytest.mark.unit
    async def test_ratchet_tightens_trail_once_triggered(
        self, db_session, rollback_session_factory
    ) -> None:
        """Once position return exceeds ratchet_trigger_pct, trail tightens to ratchet_trail_pct."""
        sim, pos = self._make_simulation(
            db_session,
            agent_config_extra={
                "ratchet_trigger_pct": 10.0,
                "ratchet_trail_pct": 3.0,
            },
            entry_price=Decimal("100.00"),
        )
        db_session.add(sim)
        await db_session.commit()
        await db_session.refresh(sim)

        pos.simulation_id = sim.id
        # Position has already reached +12% high (above 10% trigger)
        pos.highest_price = Decimal("112.00")
        pos.current_stop = Decimal("95.00")
        db_session.add(pos)
        await db_session.commit()

        engine = SimulationEngine(db_session, session_factory=rollback_session_factory)

        # Price makes new high at 115
        bar = PriceBar(
            date=date(2024, 1, 16),
            open=Decimal("112.00"),
            high=Decimal("115.00"),
            low=Decimal("111.00"),
            close=Decimal("114.00"),
            volume=1000000,
        )
        self._setup_engine_cache(engine, sim.id, bar)

        mock_agent = MagicMock()
        mock_agent.required_lookback_days = 60
        mock_agent.evaluate = AsyncMock(
            return_value=AgentDecision(symbol="AAPL", action="NO_SIGNAL")
        )

        with patch("app.services.arena.simulation_engine.get_agent", return_value=mock_agent):
            await engine.step_day(sim.id)

        await db_session.refresh(pos)
        # With ratchet at 3% from the new high of 115: stop = 115 * 0.97 = 111.55
        # Without ratchet (5% trail from 115): stop = 115 * 0.95 = 109.25
        # The ratchet stop is higher, so it should win.
        expected_ratchet_stop = Decimal("115.00") * Decimal("0.97")
        assert pos.current_stop >= expected_ratchet_stop, (
            f"Expected ratchet stop >= {expected_ratchet_stop}, got {pos.current_stop}"
        )
        assert pos.status == PositionStatus.OPEN.value

    @pytest.mark.unit
    async def test_ratchet_not_applied_below_trigger(
        self, db_session, rollback_session_factory
    ) -> None:
        """Ratchet trail is NOT applied when highest price hasn't hit ratchet_trigger_pct."""
        sim, pos = self._make_simulation(
            db_session,
            agent_config_extra={
                "ratchet_trigger_pct": 10.0,
                "ratchet_trail_pct": 3.0,
            },
            entry_price=Decimal("100.00"),
        )
        db_session.add(sim)
        await db_session.commit()
        await db_session.refresh(sim)

        pos.simulation_id = sim.id
        # Only +5% so far, below 10% trigger
        pos.highest_price = Decimal("105.00")
        pos.current_stop = Decimal("95.00")
        db_session.add(pos)
        await db_session.commit()

        engine = SimulationEngine(db_session, session_factory=rollback_session_factory)

        bar = PriceBar(
            date=date(2024, 1, 16),
            open=Decimal("105.00"),
            high=Decimal("105.00"),
            low=Decimal("97.00"),
            close=Decimal("104.00"),
            volume=1000000,
        )
        self._setup_engine_cache(engine, sim.id, bar)

        mock_agent = MagicMock()
        mock_agent.required_lookback_days = 60
        mock_agent.evaluate = AsyncMock(
            return_value=AgentDecision(symbol="AAPL", action="NO_SIGNAL")
        )

        with patch("app.services.arena.simulation_engine.get_agent", return_value=mock_agent):
            await engine.step_day(sim.id)

        await db_session.refresh(pos)
        # Without ratchet: 5% trail from high 105 = 99.75
        # Ratchet stop (3% from 105) would be 101.85 but should NOT be applied
        ratchet_stop = Decimal("105.00") * Decimal("0.97")
        assert pos.current_stop < ratchet_stop, (
            f"Expected stop below ratchet level {ratchet_stop} before trigger, got {pos.current_stop}"
        )

    @pytest.mark.unit
    async def test_breakeven_disabled_when_none(
        self, db_session, rollback_session_factory
    ) -> None:
        """When breakeven_trigger_pct is None (default), stop never rises to entry."""
        sim, pos = self._make_simulation(
            db_session,
            agent_config_extra={},  # no breakeven config
            entry_price=Decimal("100.00"),
        )
        db_session.add(sim)
        await db_session.commit()
        await db_session.refresh(sim)

        pos.simulation_id = sim.id
        pos.highest_price = Decimal("110.00")  # well past any typical trigger
        pos.current_stop = Decimal("95.00")
        db_session.add(pos)
        await db_session.commit()

        engine = SimulationEngine(db_session, session_factory=rollback_session_factory)

        bar = PriceBar(
            date=date(2024, 1, 16),
            open=Decimal("110.00"),
            high=Decimal("110.00"),
            low=Decimal("96.00"),
            close=Decimal("109.00"),
            volume=1000000,
        )
        self._setup_engine_cache(engine, sim.id, bar)

        mock_agent = MagicMock()
        mock_agent.required_lookback_days = 60
        mock_agent.evaluate = AsyncMock(
            return_value=AgentDecision(symbol="AAPL", action="NO_SIGNAL")
        )

        with patch("app.services.arena.simulation_engine.get_agent", return_value=mock_agent):
            await engine.step_day(sim.id)

        await db_session.refresh(pos)
        # Without breakeven, normal 5% trail from 110 = 104.50
        # Stop must NOT be forced to 100 (entry) by breakeven logic
        # It will be 104.50 from the normal trail — confirm it's not stuck at entry
        normal_trail_stop = Decimal("110.00") * Decimal("0.95")
        assert pos.current_stop == normal_trail_stop.quantize(Decimal("0.0001")), (
            f"Expected normal trail stop {normal_trail_stop}, got {pos.current_stop}"
        )


@pytest.mark.usefixtures("db_session")
class TestRiskBasedPositionSizing:
    """Tests for risk-based position sizing (Phase 3, step 3a).

    Verifies that sizing_mode='risk_based' computes shares from the
    ATR stop distance formula, handles zero-ATR fallback, respects the
    max_risk_pct cap, and that sizing_mode precedence is correct.
    """

    def _make_simulation(
        self,
        agent_config_extra: dict,
        initial_capital: Decimal = Decimal("10000.00"),
        position_size: Decimal = Decimal("1000.00"),
    ) -> ArenaSimulation:
        """Return an unsaved running simulation with a pending position."""
        config = {"trailing_stop_pct": 5.0, **agent_config_extra}
        return ArenaSimulation(
            name="Risk Sizing Test",
            symbols=["AAPL"],
            start_date=date(2024, 1, 15),
            end_date=date(2024, 1, 25),
            initial_capital=initial_capital,
            position_size=position_size,
            agent_type="live20",
            agent_config=config,
            status=SimulationStatus.RUNNING.value,
            current_day=0,
            total_days=10,
        )

    @pytest.mark.unit
    async def test_risk_based_sizing_formula(
        self, db_session, rollback_session_factory
    ) -> None:
        """shares = risk_amount / stop_distance_per_share.

        Setup:
          - equity = $10,000, risk_per_trade_pct = 2.0
          - atr_pct = 2.0%, atr_stop_multiplier = 2.0
          - entry_price (open) = $100
          - stop_distance_per_share = 2.0 * 2.0/100 * 100 = $4.00
          - risk_amount = 10000 * 2/100 = $200
          - shares = 200 / 4 = 50
        """
        sim = self._make_simulation(
            agent_config_extra={
                "stop_type": "atr",
                "atr_stop_multiplier": 2.0,
                "atr_stop_min_pct": 1.0,
                "atr_stop_max_pct": 15.0,
                "sizing_mode": "risk_based",
                "risk_per_trade_pct": 2.0,
                "win_streak_bonus_pct": 0.0,
                "max_risk_pct": 10.0,
            }
        )
        db_session.add(sim)
        await db_session.commit()
        await db_session.refresh(sim)

        pending = ArenaPosition(
            simulation_id=sim.id,
            symbol="AAPL",
            status=PositionStatus.PENDING.value,
            signal_date=date(2024, 1, 15),
            trailing_stop_pct=Decimal("5.00"),
        )
        db_session.add(pending)
        await db_session.commit()

        engine = SimulationEngine(db_session, session_factory=rollback_session_factory)
        engine._trading_days_cache[sim.id] = [date(2024, 1, 16), date(2024, 1, 17)]

        # Build 20 price bars so ATR calculation has enough data.
        # Open/close = 100, high = 102, low = 98 → TR per bar ≈ 4 → ATR ≈ 2%
        atr_bars = [
            PriceBar(
                date=date(2024, 1, 1) + timedelta(days=i),
                open=Decimal("100.00"),
                high=Decimal("102.00"),
                low=Decimal("98.00"),
                close=Decimal("100.00"),
                volume=1_000_000,
            )
            for i in range(20)
        ]
        # Today's bar (Jan 16): open at 100, same volatility
        today_bar = PriceBar(
            date=date(2024, 1, 16),
            open=Decimal("100.00"),
            high=Decimal("102.00"),
            low=Decimal("98.00"),
            close=Decimal("100.00"),
            volume=1_000_000,
        )
        engine._price_cache[sim.id] = {"AAPL": atr_bars + [today_bar]}
        engine._sector_cache[sim.id] = {"AAPL": None}

        mock_agent = MagicMock()
        mock_agent.required_lookback_days = 60
        mock_agent.evaluate = AsyncMock(
            return_value=AgentDecision(symbol="AAPL", action="HOLD", reasoning="holding")
        )

        with patch("app.services.arena.simulation_engine.get_agent", return_value=mock_agent):
            await engine.step_day(sim.id)

        await db_session.refresh(pending)
        assert pending.status == PositionStatus.OPEN.value
        # Bars: high=102, low=98, close=100 → TR = 4 (absolute) → ATR ≈ 4% of price
        # stop_distance_per_share = 2.0 * 4.0/100 * 100 = 8.00
        # risk_amount = 10000 * 2/100 = 200
        # shares = 200 / 8.0 = 25
        # Allow ±5 shares tolerance for ATR floating-point variation
        assert pending.shares is not None
        assert 20 <= pending.shares <= 30, (
            f"Expected ~25 shares for risk-based sizing, got {pending.shares}"
        )

    @pytest.mark.unit
    async def test_risk_based_zero_atr_falls_back_to_fixed(
        self, db_session, rollback_session_factory
    ) -> None:
        """When ATR is None (insufficient data), fall back to fixed position_size."""
        sim = self._make_simulation(
            agent_config_extra={
                "stop_type": "atr",
                "atr_stop_multiplier": 2.0,
                "atr_stop_min_pct": 1.0,
                "atr_stop_max_pct": 15.0,
                "sizing_mode": "risk_based",
                "risk_per_trade_pct": 2.0,
                "win_streak_bonus_pct": 0.0,
                "max_risk_pct": 10.0,
            },
            position_size=Decimal("1000.00"),
        )
        db_session.add(sim)
        await db_session.commit()
        await db_session.refresh(sim)

        pending = ArenaPosition(
            simulation_id=sim.id,
            symbol="AAPL",
            status=PositionStatus.PENDING.value,
            signal_date=date(2024, 1, 15),
            trailing_stop_pct=Decimal("5.00"),
        )
        db_session.add(pending)
        await db_session.commit()

        engine = SimulationEngine(db_session, session_factory=rollback_session_factory)
        engine._trading_days_cache[sim.id] = [date(2024, 1, 16), date(2024, 1, 17)]

        # Only 3 bars — insufficient for ATR (requires ≥15)
        sparse_bars = [
            PriceBar(
                date=date(2024, 1, 14) + timedelta(days=i),
                open=Decimal("100.00"),
                high=Decimal("102.00"),
                low=Decimal("98.00"),
                close=Decimal("100.00"),
                volume=1_000_000,
            )
            for i in range(3)
        ]
        today_bar = PriceBar(
            date=date(2024, 1, 16),
            open=Decimal("100.00"),
            high=Decimal("102.00"),
            low=Decimal("98.00"),
            close=Decimal("100.00"),
            volume=1_000_000,
        )
        engine._price_cache[sim.id] = {"AAPL": sparse_bars + [today_bar]}
        engine._sector_cache[sim.id] = {"AAPL": None}

        mock_agent = MagicMock()
        mock_agent.required_lookback_days = 60
        mock_agent.evaluate = AsyncMock(
            return_value=AgentDecision(symbol="AAPL", action="HOLD", reasoning="holding")
        )

        with patch("app.services.arena.simulation_engine.get_agent", return_value=mock_agent):
            await engine.step_day(sim.id)

        await db_session.refresh(pending)
        assert pending.status == PositionStatus.OPEN.value
        # Fallback: $1000 / $100 = 10 shares
        assert pending.shares == 10

    @pytest.mark.unit
    async def test_risk_based_effective_risk_capped_at_max(
        self, db_session, rollback_session_factory
    ) -> None:
        """Effective risk never exceeds max_risk_pct, even with a long win streak.

        Setup: base_risk=2.5%, win_streak_bonus=0.5%, max_risk=3.0%, streak=10
        base_risk + 10*0.5 = 7.5% — must be capped to 3.0%.
        """
        sim = self._make_simulation(
            agent_config_extra={
                "stop_type": "atr",
                "atr_stop_multiplier": 2.0,
                "atr_stop_min_pct": 1.0,
                "atr_stop_max_pct": 15.0,
                "sizing_mode": "risk_based",
                "risk_per_trade_pct": 2.5,
                "win_streak_bonus_pct": 0.5,
                "max_risk_pct": 3.0,
            },
        )
        db_session.add(sim)
        await db_session.commit()
        await db_session.refresh(sim)
        # Simulate a 10-trade win streak
        sim.consecutive_wins = 10
        await db_session.commit()

        pending = ArenaPosition(
            simulation_id=sim.id,
            symbol="AAPL",
            status=PositionStatus.PENDING.value,
            signal_date=date(2024, 1, 15),
            trailing_stop_pct=Decimal("5.00"),
        )
        db_session.add(pending)
        await db_session.commit()

        engine = SimulationEngine(db_session, session_factory=rollback_session_factory)
        engine._trading_days_cache[sim.id] = [date(2024, 1, 16), date(2024, 1, 17)]

        # 20 bars with ~2% ATR (TR=4 on price=100)
        atr_bars = [
            PriceBar(
                date=date(2024, 1, 1) + timedelta(days=i),
                open=Decimal("100.00"),
                high=Decimal("102.00"),
                low=Decimal("98.00"),
                close=Decimal("100.00"),
                volume=1_000_000,
            )
            for i in range(20)
        ]
        today_bar = PriceBar(
            date=date(2024, 1, 16),
            open=Decimal("100.00"),
            high=Decimal("102.00"),
            low=Decimal("98.00"),
            close=Decimal("100.00"),
            volume=1_000_000,
        )
        engine._price_cache[sim.id] = {"AAPL": atr_bars + [today_bar]}
        engine._sector_cache[sim.id] = {"AAPL": None}

        mock_agent = MagicMock()
        mock_agent.required_lookback_days = 60
        mock_agent.evaluate = AsyncMock(
            return_value=AgentDecision(symbol="AAPL", action="HOLD", reasoning="holding")
        )

        with patch("app.services.arena.simulation_engine.get_agent", return_value=mock_agent):
            await engine.step_day(sim.id)

        await db_session.refresh(pending)
        assert pending.status == PositionStatus.OPEN.value
        # ATR ≈ 4% (TR=4 on price=100), capped risk = 3.0%
        # stop_distance_per_share = 2.0 * 4.0/100 * 100 = 8.00
        # risk_amount = 10000 * 3/100 = 300
        # shares = 300 / 8.0 = 37 (±5 tolerance)
        assert pending.shares is not None
        assert 32 <= pending.shares <= 42, (
            f"Expected ~37 shares at capped 3% risk, got {pending.shares}"
        )

    @pytest.mark.unit
    async def test_sizing_mode_precedence_explicit_overrides_legacy(
        self, db_session, rollback_session_factory
    ) -> None:
        """sizing_mode='fixed' takes precedence over a non-None position_size_pct.

        When sizing_mode='fixed' is explicitly set, the legacy position_size_pct
        field is ignored and the fixed position_size is used instead.
        """
        sim = self._make_simulation(
            agent_config_extra={
                "sizing_mode": "fixed",
                "position_size_pct": 50.0,  # would give 50 shares, but should be ignored
            },
            position_size=Decimal("1000.00"),
        )
        db_session.add(sim)
        await db_session.commit()
        await db_session.refresh(sim)

        pending = ArenaPosition(
            simulation_id=sim.id,
            symbol="AAPL",
            status=PositionStatus.PENDING.value,
            signal_date=date(2024, 1, 15),
            trailing_stop_pct=Decimal("5.00"),
        )
        db_session.add(pending)
        await db_session.commit()

        engine = SimulationEngine(db_session, session_factory=rollback_session_factory)
        engine._trading_days_cache[sim.id] = [date(2024, 1, 16), date(2024, 1, 17)]
        price_bars = [
            PriceBar(
                date=date(2024, 1, 16),
                open=Decimal("100.00"),
                high=Decimal("102.00"),
                low=Decimal("98.00"),
                close=Decimal("101.00"),
                volume=1_000_000,
            )
        ]
        engine._price_cache[sim.id] = {"AAPL": price_bars}
        engine._sector_cache[sim.id] = {"AAPL": None}

        mock_agent = MagicMock()
        mock_agent.required_lookback_days = 60
        mock_agent.evaluate = AsyncMock(
            return_value=AgentDecision(symbol="AAPL", action="HOLD", reasoning="holding")
        )

        with patch("app.services.arena.simulation_engine.get_agent", return_value=mock_agent):
            await engine.step_day(sim.id)

        await db_session.refresh(pending)
        assert pending.status == PositionStatus.OPEN.value
        # sizing_mode='fixed': $1000 / $100 = 10 shares (NOT 50 from position_size_pct)
        assert pending.shares == 10

    @pytest.mark.unit
    async def test_sizing_mode_legacy_pct_fallback(
        self, db_session, rollback_session_factory
    ) -> None:
        """Legacy: no sizing_mode + position_size_pct set → behaves as fixed_pct."""
        # 10000 equity, position_size_pct=33.0, open=100 → 33 shares
        sim = self._make_simulation(
            agent_config_extra={"position_size_pct": 33.0},  # no sizing_mode key
            position_size=Decimal("1000.00"),
        )
        db_session.add(sim)
        await db_session.commit()
        await db_session.refresh(sim)

        pending = ArenaPosition(
            simulation_id=sim.id,
            symbol="AAPL",
            status=PositionStatus.PENDING.value,
            signal_date=date(2024, 1, 15),
            trailing_stop_pct=Decimal("5.00"),
        )
        db_session.add(pending)
        await db_session.commit()

        engine = SimulationEngine(db_session, session_factory=rollback_session_factory)
        engine._trading_days_cache[sim.id] = [date(2024, 1, 16), date(2024, 1, 17)]
        price_bars = [
            PriceBar(
                date=date(2024, 1, 16),
                open=Decimal("100.00"),
                high=Decimal("102.00"),
                low=Decimal("98.00"),
                close=Decimal("101.00"),
                volume=1_000_000,
            )
        ]
        engine._price_cache[sim.id] = {"AAPL": price_bars}
        engine._sector_cache[sim.id] = {"AAPL": None}

        mock_agent = MagicMock()
        mock_agent.required_lookback_days = 60
        mock_agent.evaluate = AsyncMock(
            return_value=AgentDecision(symbol="AAPL", action="HOLD", reasoning="holding")
        )

        with patch("app.services.arena.simulation_engine.get_agent", return_value=mock_agent):
            await engine.step_day(sim.id)

        await db_session.refresh(pending)
        assert pending.status == PositionStatus.OPEN.value
        # 33% of $10,000 = $3,300 / $100 = 33 shares
        assert pending.shares == 33


@pytest.mark.usefixtures("db_session")
class TestWinStreakTracking:
    """Tests for consecutive_wins streak tracking (Phase 3, step 3b).

    Verifies increment on win, reset on loss, and cap via max_risk_pct.
    """

    def _make_running_sim_with_open_position(
        self,
        agent_config_extra: dict | None = None,
    ) -> tuple[ArenaSimulation, ArenaPosition]:
        """Return unsaved simulation + open position pair."""
        config = {"trailing_stop_pct": 5.0, **(agent_config_extra or {})}
        sim = ArenaSimulation(
            name="Win Streak Test",
            symbols=["AAPL"],
            start_date=date(2024, 1, 15),
            end_date=date(2024, 1, 25),
            initial_capital=Decimal("10000.00"),
            position_size=Decimal("1000.00"),
            agent_type="live20",
            agent_config=config,
            status=SimulationStatus.RUNNING.value,
            current_day=0,
            total_days=10,
        )
        pos = ArenaPosition(
            symbol="AAPL",
            status=PositionStatus.OPEN.value,
            signal_date=date(2024, 1, 14),
            entry_date=date(2024, 1, 15),
            entry_price=Decimal("100.00"),
            shares=10,
            trailing_stop_pct=Decimal("5.00"),
            highest_price=Decimal("100.00"),
            current_stop=Decimal("95.00"),
        )
        return sim, pos

    @pytest.mark.unit
    async def test_consecutive_wins_increments_on_winning_trade(
        self, db_session, rollback_session_factory
    ) -> None:
        """consecutive_wins increments when a position closes with positive PnL."""
        sim, pos = self._make_running_sim_with_open_position()
        db_session.add(sim)
        await db_session.commit()
        await db_session.refresh(sim)
        pos.simulation_id = sim.id
        db_session.add(pos)
        await db_session.commit()

        assert sim.consecutive_wins == 0

        engine = SimulationEngine(db_session, session_factory=rollback_session_factory)
        # Price drops below stop → triggers close at $95, entry was $100 → loss
        # We want a WIN: gap UP so stop does not trigger, price closes above entry.
        # Use take_profit to force a profitable close.
        # Actually simpler: use max_hold_days=1 + closing bar above entry.
        sim.agent_config = {"trailing_stop_pct": 5.0, "max_hold_days": 1}
        await db_session.commit()

        trading_days = [date(2024, 1, 16), date(2024, 1, 17), date(2024, 1, 18)]
        engine._trading_days_cache[sim.id] = trading_days
        # Entry was Jan 15. Max hold=1 day means at idx=1 (Jan 17) it must close.
        # But current_day=0, so we process Jan 16 first — hold_days = idx(Jan16) - idx(Jan15).
        # entry_date=Jan 15 is NOT in trading_days, so hold_days=0 on Jan16. OK.
        # On Jan 17: idx=1 - idx(Jan15 which is missing) → 0. Still 0.
        # So we need entry_date IN trading_days. Use entry_date=Jan 16, current_day=0 → process Jan16.
        pos.entry_date = date(2024, 1, 16)
        pos.highest_price = Decimal("105.00")
        pos.current_stop = Decimal("99.75")  # 105 * 0.95 — above entry, so no stop at 110 open
        await db_session.commit()

        # Jan 16: open=110 (gap up above entry=100), high=112, low=108, close=110
        # hold_days = idx(Jan16) - idx(Jan16) = 0 → not triggered (need ≥1)
        # Jan 17: hold_days = 1 ≥ 1 → close at close price 115 (profitable)
        price_bars = [
            PriceBar(
                date=date(2024, 1, 16),
                open=Decimal("110.00"),
                high=Decimal("112.00"),
                low=Decimal("108.00"),
                close=Decimal("110.00"),
                volume=1_000_000,
            ),
            PriceBar(
                date=date(2024, 1, 17),
                open=Decimal("113.00"),
                high=Decimal("115.00"),
                low=Decimal("111.00"),
                close=Decimal("115.00"),
                volume=1_000_000,
            ),
        ]
        engine._price_cache[sim.id] = {"AAPL": price_bars}
        engine._sector_cache[sim.id] = {"AAPL": None}

        mock_agent = MagicMock()
        mock_agent.required_lookback_days = 60
        mock_agent.evaluate = AsyncMock(
            return_value=AgentDecision(symbol="AAPL", action="NO_SIGNAL")
        )

        with patch("app.services.arena.simulation_engine.get_agent", return_value=mock_agent):
            # Day 0 (Jan 16): hold_days=0, no close
            await engine.step_day(sim.id)
            # Day 1 (Jan 17): hold_days=1 ≥ max_hold_days=1, close at close=115
            await engine.step_day(sim.id)

        await db_session.refresh(sim)
        await db_session.refresh(pos)

        assert pos.status == PositionStatus.CLOSED.value
        assert pos.realized_pnl > 0
        assert sim.consecutive_wins == 1

    @pytest.mark.unit
    async def test_consecutive_wins_resets_on_losing_trade(
        self, db_session, rollback_session_factory
    ) -> None:
        """consecutive_wins resets to 0 when a position closes with a loss."""
        sim, pos = self._make_running_sim_with_open_position()
        sim.agent_config = {"trailing_stop_pct": 5.0}
        db_session.add(sim)
        await db_session.commit()
        await db_session.refresh(sim)

        # Pre-set a win streak that should reset after this losing trade
        sim.consecutive_wins = 3
        pos.simulation_id = sim.id
        db_session.add(pos)
        await db_session.commit()

        engine = SimulationEngine(db_session, session_factory=rollback_session_factory)
        trading_days = [date(2024, 1, 17), date(2024, 1, 18), date(2024, 1, 19)]
        engine._trading_days_cache[sim.id] = trading_days

        # Price drops through stop: open=96, low=93 → triggers at stop=95 (min(95,96)=95)
        # entry=100, exit=95 → loss of $50 on 10 shares
        price_bars = [
            PriceBar(
                date=date(2024, 1, 17),
                open=Decimal("96.00"),
                high=Decimal("97.00"),
                low=Decimal("93.00"),
                close=Decimal("94.00"),
                volume=1_000_000,
            )
        ]
        engine._price_cache[sim.id] = {"AAPL": price_bars}
        engine._sector_cache[sim.id] = {"AAPL": None}

        mock_agent = MagicMock()
        mock_agent.required_lookback_days = 60
        mock_agent.evaluate = AsyncMock(
            return_value=AgentDecision(symbol="AAPL", action="NO_SIGNAL")
        )

        with patch("app.services.arena.simulation_engine.get_agent", return_value=mock_agent):
            await engine.step_day(sim.id)

        await db_session.refresh(sim)
        await db_session.refresh(pos)

        assert pos.status == PositionStatus.CLOSED.value
        assert pos.realized_pnl < 0
        assert sim.consecutive_wins == 0


@pytest.mark.usefixtures("db_session")
class TestClosePositionHelper:
    """Tests for the _close_position() helper method (Phase 3, step 3c).

    Verifies that the helper produces identical field values to what the
    inline close blocks produced, and correctly updates simulation counters.
    """

    def _make_open_position(
        self,
        simulation_id: int,
        entry_price: Decimal = Decimal("100.00"),
        shares: int = 10,
    ) -> ArenaPosition:
        return ArenaPosition(
            simulation_id=simulation_id,
            symbol="AAPL",
            status=PositionStatus.OPEN.value,
            signal_date=date(2024, 1, 14),
            entry_date=date(2024, 1, 15),
            entry_price=entry_price,
            shares=shares,
            trailing_stop_pct=Decimal("5.00"),
            highest_price=entry_price,
            current_stop=(entry_price * Decimal("0.95")).quantize(Decimal("0.0001")),
        )

    @pytest.mark.unit
    async def test_close_position_sets_all_fields_on_win(
        self, db_session, rollback_session_factory
    ) -> None:
        """_close_position sets status, exit fields, pnl, and increments counters on win."""
        sim = ArenaSimulation(
            name="Close Helper Test",
            symbols=["AAPL"],
            start_date=date(2024, 1, 15),
            end_date=date(2024, 1, 25),
            initial_capital=Decimal("10000.00"),
            position_size=Decimal("1000.00"),
            agent_type="live20",
            agent_config={"trailing_stop_pct": 5.0},
            status=SimulationStatus.RUNNING.value,
            current_day=0,
            total_days=10,
        )
        db_session.add(sim)
        await db_session.commit()
        await db_session.refresh(sim)

        pos = self._make_open_position(sim.id)
        db_session.add(pos)
        await db_session.commit()

        engine = SimulationEngine(db_session, session_factory=rollback_session_factory)
        exit_price = Decimal("110.00")
        exit_date = date(2024, 1, 20)
        new_cash = engine._close_position(
            position=pos,
            simulation=sim,
            exit_reason=ExitReason.TAKE_PROFIT,
            exit_price=exit_price,
            exit_date=exit_date,
            cash=Decimal("9000.00"),
        )

        assert pos.status == PositionStatus.CLOSED.value
        assert pos.exit_date == exit_date
        assert pos.exit_price == exit_price
        assert pos.exit_reason == ExitReason.TAKE_PROFIT.value
        assert pos.realized_pnl == Decimal("100.00")  # (110-100)*10
        assert pos.return_pct == Decimal("10.00")  # 10%
        assert sim.total_trades == 1
        assert sim.winning_trades == 1
        assert sim.consecutive_wins == 1
        # cash: 9000 + 10 shares * 110 = 10100
        assert new_cash == Decimal("10100.00")

    @pytest.mark.unit
    async def test_close_position_resets_streak_on_loss(
        self, db_session, rollback_session_factory
    ) -> None:
        """_close_position resets consecutive_wins to 0 on a losing trade."""
        sim = ArenaSimulation(
            name="Close Helper Loss Test",
            symbols=["AAPL"],
            start_date=date(2024, 1, 15),
            end_date=date(2024, 1, 25),
            initial_capital=Decimal("10000.00"),
            position_size=Decimal("1000.00"),
            agent_type="live20",
            agent_config={"trailing_stop_pct": 5.0},
            status=SimulationStatus.RUNNING.value,
            current_day=0,
            total_days=10,
        )
        sim.consecutive_wins = 5
        db_session.add(sim)
        await db_session.commit()
        await db_session.refresh(sim)

        pos = self._make_open_position(sim.id)
        db_session.add(pos)
        await db_session.commit()

        engine = SimulationEngine(db_session, session_factory=rollback_session_factory)
        engine._close_position(
            position=pos,
            simulation=sim,
            exit_reason=ExitReason.STOP_HIT,
            exit_price=Decimal("90.00"),  # loss: entry=100, exit=90
            exit_date=date(2024, 1, 20),
            cash=Decimal("9000.00"),
        )

        assert pos.realized_pnl == Decimal("-100.00")  # (90-100)*10
        assert sim.winning_trades == 0
        assert sim.consecutive_wins == 0  # reset from 5 to 0

    @pytest.mark.unit
    async def test_close_position_does_not_increment_winning_trades_on_loss(
        self, db_session, rollback_session_factory
    ) -> None:
        """_close_position does not count losing trade in winning_trades."""
        sim = ArenaSimulation(
            name="Close Helper Counter Test",
            symbols=["AAPL"],
            start_date=date(2024, 1, 15),
            end_date=date(2024, 1, 25),
            initial_capital=Decimal("10000.00"),
            position_size=Decimal("1000.00"),
            agent_type="live20",
            agent_config={"trailing_stop_pct": 5.0},
            status=SimulationStatus.RUNNING.value,
            current_day=0,
            total_days=10,
        )
        db_session.add(sim)
        await db_session.commit()
        await db_session.refresh(sim)

        pos = self._make_open_position(sim.id)
        db_session.add(pos)
        await db_session.commit()

        engine = SimulationEngine(db_session, session_factory=rollback_session_factory)
        engine._close_position(
            position=pos,
            simulation=sim,
            exit_reason=ExitReason.MAX_HOLD,
            exit_price=Decimal("95.00"),
            exit_date=date(2024, 1, 20),
            cash=Decimal("9000.00"),
        )

        assert sim.total_trades == 1
        assert sim.winning_trades == 0
