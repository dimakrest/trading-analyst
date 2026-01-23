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

        engine = SimulationEngine(mock_session)

        assert engine.session is mock_session
        assert engine.data_service is not None


@pytest.mark.usefixtures("clean_db")
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
    async def test_initialize_simulation_not_found(self, db_session) -> None:
        """Test initialization fails when simulation not found."""
        engine = SimulationEngine(db_session)

        with pytest.raises(ValueError, match="not found"):
            await engine.initialize_simulation(99999)

    @pytest.mark.unit
    async def test_initialize_simulation_cancelled(
        self, db_session, valid_simulation_data
    ) -> None:
        """Test initialization fails when simulation already cancelled."""
        valid_simulation_data["status"] = SimulationStatus.CANCELLED.value
        simulation = ArenaSimulation(**valid_simulation_data)
        db_session.add(simulation)
        await db_session.commit()
        await db_session.refresh(simulation)

        engine = SimulationEngine(db_session)

        with pytest.raises(ValueError, match="cannot be initialized"):
            await engine.initialize_simulation(simulation.id)

    @pytest.mark.unit
    async def test_initialize_simulation_already_completed(
        self, db_session, valid_simulation_data
    ) -> None:
        """Test initialization fails when simulation already completed."""
        valid_simulation_data["status"] = SimulationStatus.COMPLETED.value
        simulation = ArenaSimulation(**valid_simulation_data)
        db_session.add(simulation)
        await db_session.commit()
        await db_session.refresh(simulation)

        engine = SimulationEngine(db_session)

        with pytest.raises(ValueError, match="cannot be initialized"):
            await engine.initialize_simulation(simulation.id)

    @pytest.mark.unit
    async def test_initialize_simulation_failed(
        self, db_session, valid_simulation_data
    ) -> None:
        """Test initialization fails when simulation already failed."""
        valid_simulation_data["status"] = SimulationStatus.FAILED.value
        simulation = ArenaSimulation(**valid_simulation_data)
        db_session.add(simulation)
        await db_session.commit()
        await db_session.refresh(simulation)

        engine = SimulationEngine(db_session)

        with pytest.raises(ValueError, match="cannot be initialized"):
            await engine.initialize_simulation(simulation.id)

    @pytest.mark.unit
    async def test_initialize_simulation_idempotent(
        self, db_session, valid_simulation_data
    ) -> None:
        """Test initialization is idempotent - skips if already initialized."""
        # Create simulation that's already initialized (total_days > 0)
        valid_simulation_data["status"] = SimulationStatus.RUNNING.value
        valid_simulation_data["total_days"] = 22
        simulation = ArenaSimulation(**valid_simulation_data)
        db_session.add(simulation)
        await db_session.commit()
        await db_session.refresh(simulation)

        engine = SimulationEngine(db_session)

        # Should return without error, not reinitialize
        result = await engine.initialize_simulation(simulation.id)

        assert result.id == simulation.id
        assert result.total_days == 22  # Unchanged

    @pytest.mark.unit
    async def test_initialize_simulation_no_trading_days(
        self, db_session, valid_simulation_data, mock_price_data
    ) -> None:
        """Test initialization fails when no trading days in range."""
        # Set dates with no data
        valid_simulation_data["start_date"] = date(2030, 1, 1)
        valid_simulation_data["end_date"] = date(2030, 1, 15)

        simulation = ArenaSimulation(**valid_simulation_data)
        db_session.add(simulation)
        await db_session.commit()
        await db_session.refresh(simulation)

        engine = SimulationEngine(db_session)

        with patch.object(
            engine.data_service, "get_price_data", return_value=[]
        ):
            with pytest.raises(ValueError, match="No trading days"):
                await engine.initialize_simulation(simulation.id)

    @pytest.mark.unit
    async def test_initialize_simulation_success(
        self, db_session, valid_simulation_data, mock_price_data
    ) -> None:
        """Test successful simulation initialization."""
        simulation = ArenaSimulation(**valid_simulation_data)
        db_session.add(simulation)
        await db_session.commit()
        await db_session.refresh(simulation)

        engine = SimulationEngine(db_session)

        # Mock data service to return price data
        with patch.object(
            engine.data_service, "get_price_data", return_value=mock_price_data
        ):
            result = await engine.initialize_simulation(simulation.id)

        assert result.status == SimulationStatus.RUNNING.value
        assert result.total_days > 0


@pytest.mark.usefixtures("clean_db")
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
    async def test_step_day_simulation_not_found(self, db_session) -> None:
        """Test step_day fails when simulation not found."""
        engine = SimulationEngine(db_session)

        with pytest.raises(ValueError, match="not found"):
            await engine.step_day(99999)

    @pytest.mark.unit
    async def test_step_day_simulation_completed(
        self, db_session, running_simulation_data
    ) -> None:
        """Test step_day returns None when simulation completed."""
        running_simulation_data["status"] = SimulationStatus.COMPLETED.value
        simulation = ArenaSimulation(**running_simulation_data)
        db_session.add(simulation)
        await db_session.commit()
        await db_session.refresh(simulation)

        engine = SimulationEngine(db_session)

        result = await engine.step_day(simulation.id)

        assert result is None

    @pytest.mark.unit
    async def test_step_day_simulation_not_running(
        self, db_session, running_simulation_data
    ) -> None:
        """Test step_day fails when simulation not running."""
        running_simulation_data["status"] = SimulationStatus.PAUSED.value
        simulation = ArenaSimulation(**running_simulation_data)
        db_session.add(simulation)
        await db_session.commit()
        await db_session.refresh(simulation)

        engine = SimulationEngine(db_session)

        with pytest.raises(ValueError, match="not running"):
            await engine.step_day(simulation.id)

    @pytest.mark.unit
    async def test_step_day_creates_snapshot(
        self, db_session, running_simulation_data, sample_price_bars, mock_agent
    ) -> None:
        """Test step_day creates a daily snapshot."""
        simulation = ArenaSimulation(**running_simulation_data)
        db_session.add(simulation)
        await db_session.commit()
        await db_session.refresh(simulation)

        engine = SimulationEngine(db_session)

        # Mock dependencies
        with patch(
            "app.services.arena.simulation_engine.get_agent", return_value=mock_agent
        ):
            with patch.object(
                engine, "_get_trading_days", return_value=[bar.date for bar in sample_price_bars[:5]]
            ):
                with patch.object(
                    engine, "_get_price_history", return_value=sample_price_bars
                ):
                    snapshot = await engine.step_day(simulation.id)

        assert snapshot is not None
        assert snapshot.simulation_id == simulation.id
        assert snapshot.day_number == 0
        assert snapshot.cash == simulation.initial_capital
        assert snapshot.total_equity == simulation.initial_capital

    @pytest.mark.unit
    async def test_step_day_increments_current_day(
        self, db_session, running_simulation_data, sample_price_bars, mock_agent
    ) -> None:
        """Test step_day increments current_day."""
        simulation = ArenaSimulation(**running_simulation_data)
        db_session.add(simulation)
        await db_session.commit()
        await db_session.refresh(simulation)

        engine = SimulationEngine(db_session)

        with patch(
            "app.services.arena.simulation_engine.get_agent", return_value=mock_agent
        ):
            with patch.object(
                engine, "_get_trading_days", return_value=[bar.date for bar in sample_price_bars[:5]]
            ):
                with patch.object(
                    engine, "_get_price_history", return_value=sample_price_bars
                ):
                    await engine.step_day(simulation.id)

        await db_session.refresh(simulation)
        assert simulation.current_day == 1

    @pytest.mark.unit
    async def test_step_day_records_agent_decisions(
        self, db_session, running_simulation_data, sample_price_bars, mock_agent
    ) -> None:
        """Test step_day records agent decisions in snapshot."""
        simulation = ArenaSimulation(**running_simulation_data)
        db_session.add(simulation)
        await db_session.commit()
        await db_session.refresh(simulation)

        engine = SimulationEngine(db_session)

        with patch(
            "app.services.arena.simulation_engine.get_agent", return_value=mock_agent
        ):
            with patch.object(
                engine, "_get_trading_days", return_value=[bar.date for bar in sample_price_bars[:5]]
            ):
                with patch.object(
                    engine, "_get_price_history", return_value=sample_price_bars
                ):
                    snapshot = await engine.step_day(simulation.id)

        assert "AAPL" in snapshot.decisions
        assert snapshot.decisions["AAPL"]["action"] == "NO_SIGNAL"

    @pytest.mark.unit
    async def test_step_day_handles_no_price_data(
        self, db_session, running_simulation_data, sample_price_bars, mock_agent
    ) -> None:
        """Test step_day handles missing price data gracefully."""
        simulation = ArenaSimulation(**running_simulation_data)
        db_session.add(simulation)
        await db_session.commit()
        await db_session.refresh(simulation)

        engine = SimulationEngine(db_session)

        with patch(
            "app.services.arena.simulation_engine.get_agent", return_value=mock_agent
        ):
            with patch.object(
                engine, "_get_trading_days", return_value=[date(2024, 1, 15)]
            ):
                with patch.object(
                    engine, "_get_price_history", return_value=[]
                ):
                    snapshot = await engine.step_day(simulation.id)

        assert snapshot.decisions["AAPL"]["action"] == "NO_DATA"


@pytest.mark.usefixtures("clean_db")
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
        self, db_session, simulation_with_pending_position
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

        engine = SimulationEngine(db_session)

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
            return_value=AgentDecision(
                symbol="AAPL", action="HOLD", reasoning="Already holding"
            )
        )

        with patch(
            "app.services.arena.simulation_engine.get_agent", return_value=mock_agent
        ):
            with patch.object(
                engine, "_get_trading_days", return_value=trading_days
            ):
                with patch.object(
                    engine, "_get_price_history", return_value=price_bars
                ):
                    await engine.step_day(simulation.id)

        await db_session.refresh(pending)
        assert pending.status == PositionStatus.OPEN.value
        assert pending.entry_price == Decimal("100.00")
        assert pending.shares == 10  # 1000 / 100

    @pytest.mark.unit
    async def test_pending_position_cancelled_insufficient_capital(
        self, db_session, simulation_with_pending_position
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

        engine = SimulationEngine(db_session)

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

        with patch(
            "app.services.arena.simulation_engine.get_agent", return_value=mock_agent
        ):
            with patch.object(
                engine, "_get_trading_days", return_value=trading_days
            ):
                with patch.object(
                    engine, "_get_price_history", return_value=price_bars
                ):
                    await engine.step_day(simulation.id)

        await db_session.refresh(pending)
        assert pending.status == PositionStatus.CLOSED.value
        assert pending.exit_reason == ExitReason.INSUFFICIENT_CAPITAL.value

    @pytest.mark.unit
    async def test_pending_position_cancelled_insufficient_cash(
        self, db_session, simulation_with_pending_position
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

        engine = SimulationEngine(db_session)

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

        async def mock_get_price_history(symbol, start, end):
            if symbol == "AAPL":
                return price_bars_aapl
            return price_bars_msft

        with patch(
            "app.services.arena.simulation_engine.get_agent", return_value=mock_agent
        ):
            with patch.object(
                engine, "_get_trading_days", return_value=trading_days
            ):
                with patch.object(
                    engine, "_get_price_history", side_effect=mock_get_price_history
                ):
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
        self, db_session, simulation_with_pending_position
    ) -> None:
        """Test BUY signal creates a pending position."""
        simulation = simulation_with_pending_position
        simulation.current_day = 0
        db_session.add(simulation)
        await db_session.commit()
        await db_session.refresh(simulation)

        engine = SimulationEngine(db_session)

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

        with patch(
            "app.services.arena.simulation_engine.get_agent", return_value=mock_agent
        ):
            with patch.object(
                engine, "_get_trading_days", return_value=[date(2024, 1, 15)]
            ):
                with patch.object(
                    engine, "_get_price_history", return_value=price_bars
                ):
                    await engine.step_day(simulation.id)

        # Check pending position was created
        result = await db_session.execute(
            select(ArenaPosition).where(ArenaPosition.simulation_id == simulation.id)
        )
        positions = result.scalars().all()
        assert len(positions) == 1
        assert positions[0].status == PositionStatus.PENDING.value
        assert positions[0].signal_date == date(2024, 1, 15)


@pytest.mark.usefixtures("clean_db")
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
        self, db_session, simulation_with_open_position
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

        engine = SimulationEngine(db_session)

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

        with patch(
            "app.services.arena.simulation_engine.get_agent", return_value=mock_agent
        ):
            with patch.object(
                engine, "_get_trading_days", return_value=trading_days
            ):
                with patch.object(
                    engine, "_get_price_history", return_value=price_bars
                ):
                    await engine.step_day(simulation.id)

        await db_session.refresh(position)
        assert position.status == PositionStatus.CLOSED.value
        assert position.exit_reason == ExitReason.STOP_HIT.value
        assert position.exit_price == Decimal("95.00")

    @pytest.mark.unit
    async def test_trailing_stop_moves_up_with_price(
        self, db_session, simulation_with_open_position
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

        engine = SimulationEngine(db_session)

        # Need multiple days so we don't end the simulation
        trading_days = [date(2024, 1, 17), date(2024, 1, 18), date(2024, 1, 19)]

        # Price rises to 110 (new high), low stays above stop
        price_bars = [
            PriceBar(
                date=date(2024, 1, 17),
                open=Decimal("102.00"),
                high=Decimal("110.00"),  # New high
                low=Decimal("101.00"),   # Above stop at 95
                close=Decimal("108.00"),
                volume=1000000,
            )
        ]

        mock_agent = MagicMock()
        mock_agent.required_lookback_days = 60
        mock_agent.evaluate = AsyncMock(
            return_value=AgentDecision(symbol="AAPL", action="HOLD")
        )

        with patch(
            "app.services.arena.simulation_engine.get_agent", return_value=mock_agent
        ):
            with patch.object(
                engine, "_get_trading_days", return_value=trading_days
            ):
                with patch.object(
                    engine, "_get_price_history", return_value=price_bars
                ):
                    await engine.step_day(simulation.id)

        await db_session.refresh(position)
        assert position.status == PositionStatus.OPEN.value
        assert position.highest_price == Decimal("110.00")
        assert position.current_stop == Decimal("104.5000")  # 110 * 0.95

    @pytest.mark.unit
    async def test_gap_down_exits_at_open_not_stop(
        self, db_session, simulation_with_open_position
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

        engine = SimulationEngine(db_session)

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

        with patch(
            "app.services.arena.simulation_engine.get_agent", return_value=mock_agent
        ):
            with patch.object(
                engine, "_get_trading_days", return_value=trading_days
            ):
                with patch.object(
                    engine, "_get_price_history", return_value=price_bars
                ):
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


@pytest.mark.usefixtures("clean_db")
class TestSimulationEngineRunToCompletion:
    """Tests for SimulationEngine.run_to_completion() method."""

    @pytest.mark.unit
    async def test_run_to_completion_processes_all_days(self, db_session) -> None:
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

        engine = SimulationEngine(db_session)

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

        with patch(
            "app.services.arena.simulation_engine.get_agent", return_value=mock_agent
        ):
            with patch.object(engine, "_get_trading_days", return_value=trading_days):
                with patch.object(
                    engine, "_get_price_history", return_value=price_bars
                ):
                    result = await engine.run_to_completion(simulation.id)

        assert result.status == SimulationStatus.COMPLETED.value
        assert result.current_day == 3


@pytest.mark.usefixtures("clean_db")
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
        self, db_session, simulation_for_helpers
    ) -> None:
        """Test _get_latest_snapshot returns None when no snapshots."""
        db_session.add(simulation_for_helpers)
        await db_session.commit()

        engine = SimulationEngine(db_session)
        result = await engine._get_latest_snapshot(simulation_for_helpers.id)

        assert result is None

    @pytest.mark.unit
    async def test_get_latest_snapshot_returns_most_recent(
        self, db_session, simulation_for_helpers
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

        engine = SimulationEngine(db_session)
        result = await engine._get_latest_snapshot(simulation_for_helpers.id)

        assert result.day_number == 2

    @pytest.mark.unit
    async def test_get_open_positions_returns_only_open(
        self, db_session, simulation_for_helpers
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

        engine = SimulationEngine(db_session)
        result = await engine._get_open_positions(simulation_for_helpers.id)

        assert len(result) == 1
        assert result[0].symbol == "AAPL"

    @pytest.mark.unit
    async def test_get_pending_position_returns_pending(
        self, db_session, simulation_for_helpers
    ) -> None:
        """Test _get_pending_position returns pending position for symbol."""
        db_session.add(simulation_for_helpers)
        await db_session.commit()
        await db_session.refresh(simulation_for_helpers)

        pending = ArenaPosition(
            simulation_id=simulation_for_helpers.id,
            symbol="AAPL",
            status=PositionStatus.PENDING.value,
            signal_date=date(2024, 1, 15),
            trailing_stop_pct=Decimal("5.00"),
        )
        db_session.add(pending)
        await db_session.commit()

        engine = SimulationEngine(db_session)
        result = await engine._get_pending_position(
            simulation_for_helpers.id, "AAPL"
        )

        assert result is not None
        assert result.symbol == "AAPL"

    @pytest.mark.unit
    async def test_get_pending_position_returns_none_for_other_symbol(
        self, db_session, simulation_for_helpers
    ) -> None:
        """Test _get_pending_position returns None for non-pending symbol."""
        db_session.add(simulation_for_helpers)
        await db_session.commit()
        await db_session.refresh(simulation_for_helpers)

        pending = ArenaPosition(
            simulation_id=simulation_for_helpers.id,
            symbol="AAPL",
            status=PositionStatus.PENDING.value,
            signal_date=date(2024, 1, 15),
            trailing_stop_pct=Decimal("5.00"),
        )
        db_session.add(pending)
        await db_session.commit()

        engine = SimulationEngine(db_session)
        result = await engine._get_pending_position(
            simulation_for_helpers.id, "MSFT"
        )

        assert result is None

    @pytest.mark.unit
    def test_find_bar_for_date_returns_matching_bar(self) -> None:
        """Test _find_bar_for_date returns bar for target date."""
        engine = SimulationEngine(AsyncMock())

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
        engine = SimulationEngine(AsyncMock())

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


@pytest.mark.usefixtures("clean_db")
class TestSimulationEngineMaxDrawdown:
    """Tests for max drawdown calculation."""

    @pytest.mark.unit
    async def test_update_max_drawdown_with_single_snapshot(
        self, db_session
    ) -> None:
        """Test max drawdown not updated with only one snapshot."""
        simulation = ArenaSimulation(
            name="Drawdown Test",
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

        snapshot = ArenaSnapshot(
            simulation_id=simulation.id,
            snapshot_date=date(2024, 1, 15),
            day_number=0,
            cash=Decimal("10000.00"),
            positions_value=Decimal("0.00"),
            total_equity=Decimal("10000.00"),
        )
        db_session.add(snapshot)
        await db_session.commit()

        engine = SimulationEngine(db_session)
        await engine._update_max_drawdown(simulation)

        assert simulation.max_drawdown_pct is None

    @pytest.mark.unit
    async def test_update_max_drawdown_calculates_correctly(
        self, db_session
    ) -> None:
        """Test max drawdown calculates correctly with equity curve."""
        simulation = ArenaSimulation(
            name="Drawdown Test",
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

        # Create equity curve: 10000 -> 11000 -> 10000 (9.09% drawdown)
        equities = [
            Decimal("10000.00"),
            Decimal("11000.00"),  # Peak
            Decimal("10000.00"),  # Drawdown
        ]
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

        engine = SimulationEngine(db_session)
        await engine._update_max_drawdown(simulation)

        # Max drawdown: (11000 - 10000) / 11000 * 100 = 9.09%
        assert simulation.max_drawdown_pct is not None
        assert abs(simulation.max_drawdown_pct - Decimal("9.0909")) < Decimal("0.01")


@pytest.mark.usefixtures("clean_db")
class TestSimulationEngineCloseAllPositions:
    """Tests for closing all positions at simulation end."""

    @pytest.mark.unit
    async def test_close_all_positions_at_simulation_end(
        self, db_session
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

        engine = SimulationEngine(db_session)

        # Mock price bars for close - use coroutine mock
        async def mock_get_bar(symbol: str, target_date: date):
            prices = {"AAPL": Decimal("105.00"), "MSFT": Decimal("210.00")}
            return PriceBar(
                date=target_date,
                open=prices[symbol],
                high=prices[symbol],
                low=prices[symbol],
                close=prices[symbol],
                volume=1000000,
            )

        with patch.object(engine, "_get_bar_for_date", side_effect=mock_get_bar):
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
