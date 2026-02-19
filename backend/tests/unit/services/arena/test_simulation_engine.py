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

        # Mock data service to return price data
        with patch.object(engine.data_service, "get_price_data", return_value=mock_price_data):
            result = await engine.initialize_simulation(simulation.id)

        assert result.status == SimulationStatus.RUNNING.value
        assert result.total_days > 0


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

        # Mock data service to return price data
        with patch.object(
            engine.data_service, "get_price_data", new=AsyncMock(return_value=mock_records)
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
