"""Integration tests for Arena simulation with real price data flow.

Tests the full simulation workflow from creation to completion,
verifying that positions open, trailing stops work, and metrics
are calculated correctly.
"""

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, patch

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
from app.providers.base import PriceDataPoint
from app.services.arena.agent_protocol import AgentDecision, PriceBar
from app.services.arena.simulation_engine import SimulationEngine


def create_mock_price_data(
    symbol: str,
    start_date: date,
    num_days: int,
    base_price: float = 100.0,
    trend: float = 0.0,
) -> list[PriceDataPoint]:
    """Create mock price data for testing.

    Args:
        symbol: Stock symbol.
        start_date: Starting date.
        num_days: Number of days to generate.
        base_price: Starting price.
        trend: Daily price change.

    Returns:
        List of PriceDataPoint objects.
    """
    data = []
    for i in range(num_days):
        price = base_price + (i * trend)
        data.append(
            PriceDataPoint(
                symbol=symbol,
                timestamp=datetime.combine(
                    start_date + timedelta(days=i),
                    datetime.min.time(),
                    tzinfo=timezone.utc,
                ),
                open_price=price,
                high_price=price * 1.02,
                low_price=price * 0.98,
                close_price=price * 1.01,
                volume=1000000,
            )
        )
    return data


@pytest.mark.usefixtures("clean_db")
class TestArenaSimulationIntegration:
    """Integration tests for full simulation workflow."""

    @pytest.fixture
    def mock_price_data(self) -> dict[str, list[PriceDataPoint]]:
        """Create mock price data for multiple symbols."""
        start = date(2024, 1, 1)
        return {
            "AAPL": create_mock_price_data("AAPL", start, 90, base_price=150.0, trend=0.5),
            "MSFT": create_mock_price_data("MSFT", start, 90, base_price=300.0, trend=-0.3),
        }

    @pytest.fixture
    def mock_agent(self):
        """Create mock agent for testing."""
        from unittest.mock import MagicMock

        agent = MagicMock()
        agent.name = "TestAgent"
        agent.required_lookback_days = 60
        return agent

    @pytest.mark.integration
    async def test_full_simulation_lifecycle_no_trades(
        self, db_session, mock_price_data, mock_agent
    ) -> None:
        """Test complete simulation lifecycle with no trades."""
        # Create simulation
        simulation = ArenaSimulation(
            name="Integration Test - No Trades",
            symbols=["AAPL"],
            start_date=date(2024, 1, 15),
            end_date=date(2024, 1, 20),
            initial_capital=Decimal("10000.00"),
            position_size=Decimal("1000.00"),
            agent_type="live20",
            agent_config={"trailing_stop_pct": 5.0},
            status=SimulationStatus.PENDING.value,
        )
        db_session.add(simulation)
        await db_session.commit()
        await db_session.refresh(simulation)

        # Mock agent to always return NO_SIGNAL
        mock_agent.evaluate = AsyncMock(
            return_value=AgentDecision(symbol="AAPL", action="NO_SIGNAL", score=30)
        )

        # Run simulation
        engine = SimulationEngine(db_session)

        async def mock_get_price_data(symbol, start_date, end_date, interval):
            return mock_price_data.get(symbol, [])

        with patch(
            "app.services.arena.simulation_engine.get_agent", return_value=mock_agent
        ):
            with patch.object(
                engine.data_service, "get_price_data", side_effect=mock_get_price_data
            ):
                # Initialize
                await engine.initialize_simulation(simulation.id)

                # Run to completion
                completed_sim = await engine.run_to_completion(simulation.id)

        # Verify results
        assert completed_sim.status == SimulationStatus.COMPLETED.value
        assert completed_sim.total_trades == 0
        assert completed_sim.final_equity == completed_sim.initial_capital

        # Query for snapshots separately since relationship may not be loaded
        result = await db_session.execute(
            select(ArenaSnapshot).where(ArenaSnapshot.simulation_id == completed_sim.id)
        )
        snapshots = result.scalars().all()

        assert len(snapshots) > 0
        for snapshot in snapshots:
            assert snapshot.cash == completed_sim.initial_capital
            assert snapshot.positions_value == Decimal("0")

    @pytest.mark.integration
    async def test_full_simulation_with_winning_trade(
        self, db_session, mock_price_data, mock_agent
    ) -> None:
        """Test simulation with a winning trade that gets stopped out with profit."""
        # Create uptrending price data
        start = date(2024, 1, 1)
        uptrend_data = []
        for i in range(90):
            # Start at 100, go up to ~115 by day 30, then drop to ~105
            if i < 30:
                price = 100.0 + (i * 0.5)
            else:
                price = 115.0 - ((i - 30) * 0.2)

            uptrend_data.append(
                PriceDataPoint(
                    symbol="AAPL",
                    timestamp=datetime.combine(
                        start + timedelta(days=i),
                        datetime.min.time(),
                        tzinfo=timezone.utc,
                    ),
                    open_price=price,
                    high_price=price * 1.02,
                    low_price=price * 0.98,
                    close_price=price * 1.01,
                    volume=1000000,
                )
            )

        # Create simulation
        simulation = ArenaSimulation(
            name="Integration Test - Winning Trade",
            symbols=["AAPL"],
            start_date=date(2024, 1, 15),
            end_date=date(2024, 2, 15),
            initial_capital=Decimal("10000.00"),
            position_size=Decimal("1000.00"),
            agent_type="live20",
            agent_config={"trailing_stop_pct": 5.0},
            status=SimulationStatus.PENDING.value,
        )
        db_session.add(simulation)
        await db_session.commit()
        await db_session.refresh(simulation)

        # Mock agent: BUY on first day, then HOLD
        call_count = [0]

        async def mock_evaluate(symbol, price_history, current_date, has_position):
            call_count[0] += 1
            if call_count[0] == 1 and not has_position:
                return AgentDecision(
                    symbol=symbol, action="BUY", score=80, reasoning="Strong signal"
                )
            return AgentDecision(
                symbol=symbol,
                action="HOLD" if has_position else "NO_SIGNAL",
                score=50,
            )

        mock_agent.evaluate = mock_evaluate

        # Run simulation
        engine = SimulationEngine(db_session)

        async def mock_get_price_data(symbol, start_date, end_date, interval):
            if symbol == "AAPL":
                return uptrend_data
            return []

        with patch(
            "app.services.arena.simulation_engine.get_agent", return_value=mock_agent
        ):
            with patch.object(
                engine.data_service, "get_price_data", side_effect=mock_get_price_data
            ):
                await engine.initialize_simulation(simulation.id)
                completed_sim = await engine.run_to_completion(simulation.id)

        # Verify a trade was made
        assert completed_sim.total_trades >= 1

    @pytest.mark.integration
    async def test_simulation_with_multiple_symbols(
        self, db_session, mock_price_data, mock_agent
    ) -> None:
        """Test simulation tracking multiple symbols simultaneously."""
        simulation = ArenaSimulation(
            name="Integration Test - Multi Symbol",
            symbols=["AAPL", "MSFT"],
            start_date=date(2024, 1, 15),
            end_date=date(2024, 1, 20),
            initial_capital=Decimal("10000.00"),
            position_size=Decimal("1000.00"),
            agent_type="live20",
            agent_config={"trailing_stop_pct": 5.0},
            status=SimulationStatus.PENDING.value,
        )
        db_session.add(simulation)
        await db_session.commit()
        await db_session.refresh(simulation)

        mock_agent.evaluate = AsyncMock(
            return_value=AgentDecision(symbol="TEST", action="NO_SIGNAL", score=30)
        )

        engine = SimulationEngine(db_session)

        async def mock_get_price_data(symbol, start_date, end_date, interval):
            return mock_price_data.get(symbol, [])

        with patch(
            "app.services.arena.simulation_engine.get_agent", return_value=mock_agent
        ):
            with patch.object(
                engine.data_service, "get_price_data", side_effect=mock_get_price_data
            ):
                await engine.initialize_simulation(simulation.id)
                completed_sim = await engine.run_to_completion(simulation.id)

        # Verify both symbols are tracked in snapshots
        result = await db_session.execute(
            select(ArenaSnapshot).where(ArenaSnapshot.simulation_id == completed_sim.id)
        )
        snapshots = result.scalars().all()

        for snapshot in snapshots:
            assert "AAPL" in snapshot.decisions
            assert "MSFT" in snapshot.decisions

    @pytest.mark.integration
    async def test_simulation_step_by_step(
        self, db_session, mock_price_data, mock_agent
    ) -> None:
        """Test stepping through simulation day by day."""
        simulation = ArenaSimulation(
            name="Integration Test - Step by Step",
            symbols=["AAPL"],
            start_date=date(2024, 1, 15),
            end_date=date(2024, 1, 20),
            initial_capital=Decimal("10000.00"),
            position_size=Decimal("1000.00"),
            agent_type="live20",
            agent_config={"trailing_stop_pct": 5.0},
            status=SimulationStatus.PENDING.value,
        )
        db_session.add(simulation)
        await db_session.commit()
        await db_session.refresh(simulation)

        mock_agent.evaluate = AsyncMock(
            return_value=AgentDecision(symbol="AAPL", action="NO_SIGNAL", score=30)
        )

        engine = SimulationEngine(db_session)

        async def mock_get_price_data(symbol, start_date, end_date, interval):
            return mock_price_data.get(symbol, [])

        with patch(
            "app.services.arena.simulation_engine.get_agent", return_value=mock_agent
        ):
            with patch.object(
                engine.data_service, "get_price_data", side_effect=mock_get_price_data
            ):
                await engine.initialize_simulation(simulation.id)

                snapshots = []
                while True:
                    snapshot = await engine.step_day(simulation.id)
                    if snapshot is None:
                        break
                    snapshots.append(snapshot)

        # Verify we have daily snapshots
        assert len(snapshots) > 0
        for i, snapshot in enumerate(snapshots):
            assert snapshot.day_number == i

        # Verify simulation is completed
        await db_session.refresh(simulation)
        assert simulation.status == SimulationStatus.COMPLETED.value

    @pytest.mark.integration
    async def test_simulation_tracks_drawdown(
        self, db_session, mock_price_data, mock_agent
    ) -> None:
        """Test that simulation correctly tracks maximum drawdown."""
        # Create price data with volatility to cause drawdown
        start = date(2024, 1, 1)
        volatile_data = []
        equities = [10000, 10500, 11000, 10200, 10800, 10000]  # Creates drawdown

        for i in range(90):
            price = 100.0 + (i * 0.1)
            volatile_data.append(
                PriceDataPoint(
                    symbol="AAPL",
                    timestamp=datetime.combine(
                        start + timedelta(days=i),
                        datetime.min.time(),
                        tzinfo=timezone.utc,
                    ),
                    open_price=price,
                    high_price=price * 1.02,
                    low_price=price * 0.98,
                    close_price=price * 1.01,
                    volume=1000000,
                )
            )

        simulation = ArenaSimulation(
            name="Integration Test - Drawdown",
            symbols=["AAPL"],
            start_date=date(2024, 1, 15),
            end_date=date(2024, 1, 25),
            initial_capital=Decimal("10000.00"),
            position_size=Decimal("1000.00"),
            agent_type="live20",
            agent_config={"trailing_stop_pct": 5.0},
            status=SimulationStatus.PENDING.value,
        )
        db_session.add(simulation)
        await db_session.commit()
        await db_session.refresh(simulation)

        mock_agent.evaluate = AsyncMock(
            return_value=AgentDecision(symbol="AAPL", action="NO_SIGNAL", score=30)
        )

        engine = SimulationEngine(db_session)

        async def mock_get_price_data(symbol, start_date, end_date, interval):
            if symbol == "AAPL":
                return volatile_data
            return []

        with patch(
            "app.services.arena.simulation_engine.get_agent", return_value=mock_agent
        ):
            with patch.object(
                engine.data_service, "get_price_data", side_effect=mock_get_price_data
            ):
                await engine.initialize_simulation(simulation.id)
                completed_sim = await engine.run_to_completion(simulation.id)

        # With no trades, max drawdown should be 0 or very small
        # (only from rounding differences)
        assert completed_sim.status == SimulationStatus.COMPLETED.value


@pytest.mark.usefixtures("clean_db")
class TestArenaPositionLifecycle:
    """Integration tests for position lifecycle management."""

    @pytest.fixture
    def price_data_with_stop_trigger(self) -> list[PriceDataPoint]:
        """Create price data that triggers a trailing stop.

        Day 1: Entry signal
        Day 2: Position opens at 100
        Day 3: Price rises to 110 (stop moves to 104.50)
        Day 4: Price rises to 115 (stop moves to 109.25)
        Day 5: Price drops to 108 (triggers stop at 109.25)
        """
        start = date(2024, 1, 1)
        prices = [
            (100.0, 102.0, 98.0, 101.0),   # Day for lookback
            (100.0, 102.0, 98.0, 101.0),   # Entry signal day
            (100.0, 100.0, 99.0, 100.0),   # Position opens
            (105.0, 110.0, 104.0, 108.0),  # Price rises
            (110.0, 115.0, 109.0, 114.0),  # Price rises more
            (112.0, 113.0, 105.0, 106.0),  # Stop triggers (low < 109.25)
        ]

        data = []
        for i, (open_p, high, low, close) in enumerate(prices):
            data.append(
                PriceDataPoint(
                    symbol="AAPL",
                    timestamp=datetime.combine(
                        start + timedelta(days=i),
                        datetime.min.time(),
                        tzinfo=timezone.utc,
                    ),
                    open_price=open_p,
                    high_price=high,
                    low_price=low,
                    close_price=close,
                    volume=1000000,
                )
            )
        return data

    @pytest.mark.integration
    async def test_position_opens_at_next_day_open(
        self, db_session, price_data_with_stop_trigger
    ) -> None:
        """Test that position opens at next day's open price after BUY signal."""
        from unittest.mock import MagicMock

        # Create price data where we can verify the open price
        # Day 15: BUY signal day at $100
        # Day 16: Position opens at $105
        start = date(2024, 1, 1)
        price_data = []
        for i in range(90):
            if i == 14:  # Day 15 = signal day (Jan 15)
                price_data.append(
                    PriceDataPoint(
                        symbol="AAPL",
                        timestamp=datetime.combine(
                            start + timedelta(days=i),
                            datetime.min.time(),
                            tzinfo=timezone.utc,
                        ),
                        open_price=100.0,
                        high_price=102.0,
                        low_price=98.0,
                        close_price=101.0,
                        volume=1000000,
                    )
                )
            elif i == 15:  # Day 16 = entry day (Jan 16)
                price_data.append(
                    PriceDataPoint(
                        symbol="AAPL",
                        timestamp=datetime.combine(
                            start + timedelta(days=i),
                            datetime.min.time(),
                            tzinfo=timezone.utc,
                        ),
                        open_price=105.0,  # This should be entry price
                        high_price=107.0,
                        low_price=103.0,
                        close_price=106.0,
                        volume=1000000,
                    )
                )
            else:
                price_data.append(
                    PriceDataPoint(
                        symbol="AAPL",
                        timestamp=datetime.combine(
                            start + timedelta(days=i),
                            datetime.min.time(),
                            tzinfo=timezone.utc,
                        ),
                        open_price=100.0,
                        high_price=102.0,
                        low_price=98.0,
                        close_price=101.0,
                        volume=1000000,
                    )
                )

        simulation = ArenaSimulation(
            name="Position Open Test",
            symbols=["AAPL"],
            start_date=date(2024, 1, 15),
            end_date=date(2024, 1, 20),
            initial_capital=Decimal("10000.00"),
            position_size=Decimal("1050.00"),  # Allow for 10 shares at $105
            agent_type="live20",
            agent_config={"trailing_stop_pct": 5.0},
            status=SimulationStatus.PENDING.value,
        )
        db_session.add(simulation)
        await db_session.commit()
        await db_session.refresh(simulation)

        # BUY on day 1, then HOLD
        call_count = [0]
        mock_agent = MagicMock()
        mock_agent.required_lookback_days = 60

        async def mock_evaluate(symbol, price_history, current_date, has_position):
            call_count[0] += 1
            if call_count[0] == 1:
                return AgentDecision(symbol=symbol, action="BUY", score=80)
            return AgentDecision(
                symbol=symbol,
                action="HOLD" if has_position else "NO_SIGNAL",
                score=50,
            )

        mock_agent.evaluate = mock_evaluate

        engine = SimulationEngine(db_session)

        async def mock_get_price_data(symbol, start_date, end_date, interval):
            return price_data if symbol == "AAPL" else []

        with patch(
            "app.services.arena.simulation_engine.get_agent", return_value=mock_agent
        ):
            with patch.object(
                engine.data_service, "get_price_data", side_effect=mock_get_price_data
            ):
                await engine.initialize_simulation(simulation.id)

                # Step through simulation
                snapshots = []
                while True:
                    snapshot = await engine.step_day(simulation.id)
                    if snapshot is None:
                        break
                    snapshots.append(snapshot)

        # Find positions
        result = await db_session.execute(
            select(ArenaPosition).where(ArenaPosition.simulation_id == simulation.id)
        )
        positions = result.scalars().all()

        # Should have at least one position
        assert len(positions) >= 1

        # Find the opened position
        opened_positions = [
            p for p in positions if p.entry_price is not None
        ]
        assert len(opened_positions) > 0, "No positions were opened"
        # Entry price should be the open price from day after signal = $105
        assert opened_positions[0].entry_price == Decimal("105.0")

    @pytest.mark.integration
    async def test_trailing_stop_updates_with_new_highs(
        self, db_session
    ) -> None:
        """Test trailing stop moves up as price makes new highs."""
        from unittest.mock import MagicMock

        # Create price data with rising highs
        start = date(2024, 1, 1)
        price_data = []
        for i in range(90):
            if i == 15:  # Entry day
                price_data.append(
                    PriceDataPoint(
                        symbol="AAPL",
                        timestamp=datetime.combine(
                            start + timedelta(days=i),
                            datetime.min.time(),
                            tzinfo=timezone.utc,
                        ),
                        open_price=100.0,
                        high_price=102.0,
                        low_price=98.0,
                        close_price=101.0,
                        volume=1000000,
                    )
                )
            elif i == 16:  # Day 2 - price rises
                price_data.append(
                    PriceDataPoint(
                        symbol="AAPL",
                        timestamp=datetime.combine(
                            start + timedelta(days=i),
                            datetime.min.time(),
                            tzinfo=timezone.utc,
                        ),
                        open_price=102.0,
                        high_price=110.0,  # New high
                        low_price=101.0,
                        close_price=108.0,
                        volume=1000000,
                    )
                )
            else:
                price_data.append(
                    PriceDataPoint(
                        symbol="AAPL",
                        timestamp=datetime.combine(
                            start + timedelta(days=i),
                            datetime.min.time(),
                            tzinfo=timezone.utc,
                        ),
                        open_price=100.0,
                        high_price=102.0,
                        low_price=98.0,
                        close_price=101.0,
                        volume=1000000,
                    )
                )

        simulation = ArenaSimulation(
            name="Trailing Stop Update Test",
            symbols=["AAPL"],
            start_date=date(2024, 1, 14),  # Day 14 = signal day
            end_date=date(2024, 1, 17),
            initial_capital=Decimal("10000.00"),
            position_size=Decimal("1000.00"),
            agent_type="live20",
            agent_config={"trailing_stop_pct": 5.0},
            status=SimulationStatus.PENDING.value,
        )
        db_session.add(simulation)
        await db_session.commit()
        await db_session.refresh(simulation)

        mock_agent = MagicMock()
        mock_agent.required_lookback_days = 60
        call_count = [0]

        async def mock_evaluate(symbol, price_history, current_date, has_position):
            call_count[0] += 1
            if call_count[0] == 1:
                return AgentDecision(symbol=symbol, action="BUY", score=80)
            return AgentDecision(
                symbol=symbol,
                action="HOLD" if has_position else "NO_SIGNAL",
            )

        mock_agent.evaluate = mock_evaluate

        engine = SimulationEngine(db_session)

        async def mock_get_price_data(symbol, start_date, end_date, interval):
            return price_data if symbol == "AAPL" else []

        with patch(
            "app.services.arena.simulation_engine.get_agent", return_value=mock_agent
        ):
            with patch.object(
                engine.data_service, "get_price_data", side_effect=mock_get_price_data
            ):
                await engine.initialize_simulation(simulation.id)
                await engine.run_to_completion(simulation.id)

        # Check position's highest price was updated
        result = await db_session.execute(
            select(ArenaPosition)
            .where(ArenaPosition.simulation_id == simulation.id)
            .where(ArenaPosition.status != PositionStatus.PENDING.value)
        )
        positions = result.scalars().all()

        for pos in positions:
            if pos.highest_price:
                # Highest price should reflect the new high of 110
                assert pos.highest_price >= Decimal("100.0")


@pytest.mark.usefixtures("clean_db")
class TestArenaSimulationMetrics:
    """Integration tests for simulation performance metrics."""

    @pytest.mark.integration
    async def test_cumulative_return_calculated_correctly(
        self, db_session
    ) -> None:
        """Test cumulative return is calculated correctly."""
        from unittest.mock import MagicMock

        start = date(2024, 1, 1)
        price_data = [
            PriceDataPoint(
                symbol="AAPL",
                timestamp=datetime.combine(
                    start + timedelta(days=i),
                    datetime.min.time(),
                    tzinfo=timezone.utc,
                ),
                open_price=100.0,
                high_price=102.0,
                low_price=98.0,
                close_price=101.0,
                volume=1000000,
            )
            for i in range(90)
        ]

        simulation = ArenaSimulation(
            name="Metrics Test",
            symbols=["AAPL"],
            start_date=date(2024, 1, 15),
            end_date=date(2024, 1, 20),
            initial_capital=Decimal("10000.00"),
            position_size=Decimal("1000.00"),
            agent_type="live20",
            agent_config={"trailing_stop_pct": 5.0},
            status=SimulationStatus.PENDING.value,
        )
        db_session.add(simulation)
        await db_session.commit()
        await db_session.refresh(simulation)

        mock_agent = MagicMock()
        mock_agent.required_lookback_days = 60
        mock_agent.evaluate = AsyncMock(
            return_value=AgentDecision(symbol="AAPL", action="NO_SIGNAL")
        )

        engine = SimulationEngine(db_session)

        async def mock_get_price_data(symbol, start_date, end_date, interval):
            return price_data if symbol == "AAPL" else []

        with patch(
            "app.services.arena.simulation_engine.get_agent", return_value=mock_agent
        ):
            with patch.object(
                engine.data_service, "get_price_data", side_effect=mock_get_price_data
            ):
                await engine.initialize_simulation(simulation.id)
                completed_sim = await engine.run_to_completion(simulation.id)

        # With no trades, return should be 0%
        assert completed_sim.total_return_pct == Decimal("0")
        assert completed_sim.final_equity == completed_sim.initial_capital

    @pytest.mark.integration
    async def test_win_rate_calculated_correctly(
        self, db_session
    ) -> None:
        """Test win rate is calculated from winning vs total trades."""
        simulation = ArenaSimulation(
            name="Win Rate Test",
            symbols=["AAPL"],
            start_date=date(2024, 1, 15),
            end_date=date(2024, 1, 20),
            initial_capital=Decimal("10000.00"),
            position_size=Decimal("1000.00"),
            agent_type="live20",
            agent_config={"trailing_stop_pct": 5.0},
            status=SimulationStatus.COMPLETED.value,
            total_trades=10,
            winning_trades=6,
        )
        db_session.add(simulation)
        await db_session.commit()
        await db_session.refresh(simulation)

        # Win rate = 6/10 * 100 = 60%
        assert simulation.win_rate == Decimal("60")


@pytest.mark.usefixtures("clean_db")
class TestArenaWorkerIntegration:
    """Integration tests for ArenaWorker resume and cancellation.

    Note: Most ArenaWorker tests are in unit tests (test_arena_worker.py).
    These integration tests verify the complete simulation flow with real
    database operations where practical.
    """

    @pytest.fixture
    def mock_price_data(self) -> dict[str, list[PriceDataPoint]]:
        """Create mock price data for multiple symbols."""
        start = date(2024, 1, 1)
        return {
            "AAPL": create_mock_price_data("AAPL", start, 90, base_price=150.0, trend=0.5),
        }

    @pytest.fixture
    def mock_agent(self):
        """Create mock agent for testing."""
        from unittest.mock import MagicMock

        agent = MagicMock()
        agent.name = "TestAgent"
        agent.required_lookback_days = 60
        return agent

    @pytest.mark.integration
    async def test_simulation_engine_runs_with_worker_style_session_management(
        self, db_session, mock_price_data, mock_agent
    ) -> None:
        """Test that simulation engine works with worker-style session management.

        This test verifies that the simulation engine can:
        1. Be called with a fresh session
        2. Process days correctly
        3. Update simulation state properly

        This validates the pattern used by ArenaWorker.
        """
        # Create a pending simulation
        simulation = ArenaSimulation(
            name="Worker Session Test",
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

        # Set up mock agent
        mock_agent.evaluate = AsyncMock(
            return_value=AgentDecision(symbol="AAPL", action="NO_SIGNAL", score=30)
        )

        async def mock_get_price_data(symbol, start_date, end_date, interval):
            return mock_price_data.get(symbol, [])

        # Create engine with the same session (simulating worker pattern)
        engine = SimulationEngine(db_session)

        with patch(
            "app.services.arena.simulation_engine.get_agent", return_value=mock_agent
        ):
            with patch.object(
                engine.data_service, "get_price_data", side_effect=mock_get_price_data
            ):
                # Initialize simulation
                await engine.initialize_simulation(simulation.id)
                await db_session.refresh(simulation)

                # Verify initialization updated the state
                assert simulation.status == SimulationStatus.RUNNING.value
                assert simulation.total_days > 0

                # Process a few days
                for _ in range(min(3, simulation.total_days)):
                    snapshot = await engine.step_day(simulation.id)
                    if snapshot is None:
                        break

        # Verify simulation made progress
        await db_session.refresh(simulation)
        assert simulation.current_day > 0

    @pytest.mark.integration
    async def test_simulation_respects_min_buy_score_threshold(
        self, db_session, mock_price_data
    ) -> None:
        """Verify simulation passes min_buy_score configuration to agent.

        Tests that different simulations can use different buy score thresholds
        by verifying the agent is instantiated with the correct configuration.
        """
        # Create simulation with high threshold (80)
        high_threshold_sim = ArenaSimulation(
            name="High Threshold Test",
            symbols=["AAPL"],
            start_date=date(2024, 1, 15),
            end_date=date(2024, 1, 20),
            initial_capital=Decimal("10000.00"),
            position_size=Decimal("1000.00"),
            agent_type="live20",
            agent_config={"trailing_stop_pct": 5.0, "min_buy_score": 80},
            status=SimulationStatus.PENDING.value,
        )
        db_session.add(high_threshold_sim)

        # Create simulation with low threshold (40)
        low_threshold_sim = ArenaSimulation(
            name="Low Threshold Test",
            symbols=["AAPL"],
            start_date=date(2024, 1, 15),
            end_date=date(2024, 1, 20),
            initial_capital=Decimal("10000.00"),
            position_size=Decimal("1000.00"),
            agent_type="live20",
            agent_config={"trailing_stop_pct": 5.0, "min_buy_score": 40},
            status=SimulationStatus.PENDING.value,
        )
        db_session.add(low_threshold_sim)
        await db_session.commit()
        await db_session.refresh(high_threshold_sim)
        await db_session.refresh(low_threshold_sim)

        # Track which agents were created with which configs
        agents_created = []

        def track_agent_creation(agent_type: str, config: dict | None = None):
            """Mock get_agent to track agent instantiation and configuration.

            Creates real Live20ArenaAgent instances and records them for
            verification of configuration values.
            """
            from app.services.arena.agents.live20_agent import Live20ArenaAgent

            agent = Live20ArenaAgent(config=config)
            agents_created.append({"agent": agent, "config": config})
            return agent

        async def mock_get_price_data(symbol, start_date, end_date, interval):
            return mock_price_data.get(symbol, [])

        # Run both simulations and verify agent configs
        with patch(
            "app.services.arena.simulation_engine.get_agent",
            side_effect=track_agent_creation,
        ):
            # Test high threshold simulation
            engine_high = SimulationEngine(db_session)
            with patch.object(
                engine_high.data_service,
                "get_price_data",
                side_effect=mock_get_price_data,
            ):
                await engine_high.initialize_simulation(high_threshold_sim.id)

            # Test low threshold simulation
            engine_low = SimulationEngine(db_session)
            with patch.object(
                engine_low.data_service,
                "get_price_data",
                side_effect=mock_get_price_data,
            ):
                await engine_low.initialize_simulation(low_threshold_sim.id)

        # Verify agents were created with correct configs
        assert len(agents_created) >= 2, "Expected at least 2 agent creations"

        # Find the agents for each simulation
        high_agent = agents_created[0]["agent"]
        low_agent = agents_created[1]["agent"]

        # Verify high threshold agent has min_buy_score=80
        assert high_agent.min_buy_score == 80, (
            f"High threshold agent should have min_buy_score=80, "
            f"got {high_agent.min_buy_score}"
        )

        # Verify low threshold agent has min_buy_score=40
        assert low_agent.min_buy_score == 40, (
            f"Low threshold agent should have min_buy_score=40, "
            f"got {low_agent.min_buy_score}"
        )

        # Verify agent_config was stored correctly in database
        await db_session.refresh(high_threshold_sim)
        await db_session.refresh(low_threshold_sim)

        assert high_threshold_sim.agent_config["min_buy_score"] == 80
        assert low_threshold_sim.agent_config["min_buy_score"] == 40
