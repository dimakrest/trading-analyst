"""Comprehensive unit tests for Arena models.

Tests model validation, constraints, properties, methods,
and relationships with comprehensive edge case coverage.
"""
from datetime import UTC
from datetime import date
from datetime import datetime
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models.arena import ArenaPosition
from app.models.arena import ArenaSimulation
from app.models.arena import ArenaSnapshot
from app.models.arena import ExitReason
from app.models.arena import PositionStatus
from app.models.arena import SimulationStatus


@pytest.fixture
def valid_simulation_data():
    """Valid simulation data for testing."""
    return {
        "name": "Test Simulation",
        "symbols": ["AAPL", "GOOGL", "MSFT"],
        "start_date": date(2024, 1, 1),
        "end_date": date(2024, 3, 31),
        "initial_capital": Decimal("10000.00"),
        "position_size": Decimal("1000.00"),
        "agent_type": "live20",
        "agent_config": {"trailing_stop_pct": 5.0},
    }


@pytest.fixture
def valid_position_data():
    """Valid position data for testing."""
    return {
        "symbol": "AAPL",
        "signal_date": date(2024, 1, 15),
        "trailing_stop_pct": Decimal("5.00"),
    }


@pytest.fixture
def valid_snapshot_data():
    """Valid snapshot data for testing."""
    return {
        "snapshot_date": date(2024, 1, 15),
        "day_number": 10,
        "cash": Decimal("8000.00"),
        "positions_value": Decimal("2500.00"),
        "total_equity": Decimal("10500.00"),
        "daily_pnl": Decimal("100.00"),
        "daily_return_pct": Decimal("0.96"),
        "cumulative_return_pct": Decimal("5.00"),
        "open_position_count": 2,
        "decisions": {"AAPL": {"action": "HOLD", "score": 75}},
    }


# =============================================================================
# ArenaSimulation Tests
# =============================================================================


@pytest.mark.usefixtures("db_session")
class TestArenaSimulationModel:
    """Test ArenaSimulation model validation and functionality."""

    @pytest.fixture
    async def sample_simulation(self, db_session, valid_simulation_data):
        """Create a sample simulation record."""
        simulation = ArenaSimulation(**valid_simulation_data)
        db_session.add(simulation)
        await db_session.commit()
        await db_session.refresh(simulation)
        return simulation

    @pytest.mark.unit
    async def test_create_valid_simulation(self, db_session, valid_simulation_data):
        """Test creating a valid simulation record."""
        simulation = ArenaSimulation(**valid_simulation_data)
        db_session.add(simulation)
        await db_session.commit()
        await db_session.refresh(simulation)

        assert simulation.id is not None
        assert simulation.name == "Test Simulation"
        assert simulation.symbols == ["AAPL", "GOOGL", "MSFT"]
        assert simulation.start_date == date(2024, 1, 1)
        assert simulation.end_date == date(2024, 3, 31)
        assert simulation.initial_capital == Decimal("10000.00")
        assert simulation.position_size == Decimal("1000.00")
        assert simulation.agent_type == "live20"
        assert simulation.agent_config == {"trailing_stop_pct": 5.0}
        assert simulation.status == SimulationStatus.PENDING.value
        assert simulation.current_day == 0
        assert simulation.total_days == 0

    @pytest.mark.unit
    async def test_simulation_default_values(self, db_session):
        """Test default values are applied correctly."""
        minimal_data = {
            "symbols": ["AAPL"],
            "start_date": date(2024, 1, 1),
            "end_date": date(2024, 1, 31),
            "agent_type": "live20",
            "agent_config": {},
        }
        simulation = ArenaSimulation(**minimal_data)
        db_session.add(simulation)
        await db_session.commit()
        await db_session.refresh(simulation)

        assert simulation.initial_capital == Decimal("10000")
        assert simulation.position_size == Decimal("1000")
        assert simulation.status == SimulationStatus.PENDING.value
        assert simulation.current_day == 0
        assert simulation.total_days == 0
        assert simulation.retry_count == 0
        assert simulation.max_retries == 3
        assert simulation.total_trades == 0
        assert simulation.winning_trades == 0

    @pytest.mark.unit
    async def test_simulation_required_fields(self, db_session):
        """Test that required fields are properly validated."""
        # Missing symbols
        with pytest.raises(IntegrityError):
            simulation = ArenaSimulation(
                start_date=date(2024, 1, 1),
                end_date=date(2024, 1, 31),
                agent_type="live20",
                agent_config={},
            )
            db_session.add(simulation)
            await db_session.commit()
        await db_session.rollback()

    @pytest.mark.unit
    async def test_simulation_job_queue_fields(self, db_session, valid_simulation_data):
        """Test job queue fields work correctly."""
        simulation = ArenaSimulation(**valid_simulation_data)
        simulation.worker_id = "worker-123"
        simulation.claimed_at = datetime.now(UTC)
        simulation.heartbeat_at = datetime.now(UTC)
        simulation.retry_count = 1
        simulation.last_error = "Connection timeout"

        db_session.add(simulation)
        await db_session.commit()
        await db_session.refresh(simulation)

        assert simulation.worker_id == "worker-123"
        assert simulation.claimed_at is not None
        assert simulation.heartbeat_at is not None
        assert simulation.retry_count == 1
        assert simulation.last_error == "Connection timeout"

    @pytest.mark.unit
    async def test_simulation_results_fields(self, db_session, valid_simulation_data):
        """Test results fields work correctly."""
        simulation = ArenaSimulation(**valid_simulation_data)
        simulation.status = SimulationStatus.COMPLETED.value
        simulation.final_equity = Decimal("11500.00")
        simulation.total_return_pct = Decimal("15.0000")
        simulation.total_trades = 25
        simulation.winning_trades = 15
        simulation.max_drawdown_pct = Decimal("8.5000")

        db_session.add(simulation)
        await db_session.commit()
        await db_session.refresh(simulation)

        assert simulation.final_equity == Decimal("11500.00")
        assert simulation.total_return_pct == Decimal("15.0000")
        assert simulation.total_trades == 25
        assert simulation.winning_trades == 15
        assert simulation.max_drawdown_pct == Decimal("8.5000")

    @pytest.mark.unit
    async def test_simulation_win_rate_property(self, db_session, valid_simulation_data):
        """Test win_rate property calculation."""
        simulation = ArenaSimulation(**valid_simulation_data)
        simulation.total_trades = 20
        simulation.winning_trades = 12

        db_session.add(simulation)
        await db_session.commit()
        await db_session.refresh(simulation)

        assert simulation.win_rate == Decimal("60")

    @pytest.mark.unit
    async def test_simulation_win_rate_zero_trades(
        self, db_session, valid_simulation_data
    ):
        """Test win_rate returns None when no trades."""
        simulation = ArenaSimulation(**valid_simulation_data)
        simulation.total_trades = 0

        db_session.add(simulation)
        await db_session.commit()

        assert simulation.win_rate is None

    @pytest.mark.unit
    async def test_simulation_is_complete_property(
        self, db_session, valid_simulation_data
    ):
        """Test is_complete property."""
        simulation = ArenaSimulation(**valid_simulation_data)
        db_session.add(simulation)
        await db_session.commit()

        assert simulation.is_complete is False

        simulation.status = SimulationStatus.COMPLETED.value
        await db_session.commit()

        assert simulation.is_complete is True

    @pytest.mark.unit
    async def test_simulation_is_initialized_property(
        self, db_session, valid_simulation_data
    ):
        """Test is_initialized property.

        A simulation is initialized when total_days > 0, meaning
        trading days have been calculated during initialization.
        """
        simulation = ArenaSimulation(**valid_simulation_data)
        db_session.add(simulation)
        await db_session.commit()

        # total_days defaults to 0, so not initialized
        assert simulation.total_days == 0
        assert simulation.is_initialized is False

        # After initialization sets total_days
        simulation.total_days = 22
        await db_session.commit()

        assert simulation.is_initialized is True

    @pytest.mark.unit
    async def test_simulation_repr(self, sample_simulation):
        """Test string representation."""
        repr_str = repr(sample_simulation)

        assert "ArenaSimulation" in repr_str
        assert "live20" in repr_str
        assert "pending" in repr_str

    @pytest.mark.unit
    async def test_simulation_status_enum_values(self):
        """Test all simulation status enum values."""
        assert SimulationStatus.PENDING.value == "pending"
        assert SimulationStatus.RUNNING.value == "running"
        assert SimulationStatus.PAUSED.value == "paused"
        assert SimulationStatus.COMPLETED.value == "completed"
        assert SimulationStatus.CANCELLED.value == "cancelled"
        assert SimulationStatus.FAILED.value == "failed"


# =============================================================================
# ArenaPosition Tests
# =============================================================================


@pytest.mark.usefixtures("db_session")
class TestArenaPositionModel:
    """Test ArenaPosition model validation and functionality."""

    @pytest.fixture
    async def parent_simulation(self, db_session, valid_simulation_data):
        """Create a parent simulation for positions."""
        simulation = ArenaSimulation(**valid_simulation_data)
        db_session.add(simulation)
        await db_session.commit()
        await db_session.refresh(simulation)
        return simulation

    @pytest.fixture
    async def sample_position(
        self, db_session, parent_simulation, valid_position_data
    ):
        """Create a sample position record."""
        position = ArenaPosition(
            simulation_id=parent_simulation.id, **valid_position_data
        )
        db_session.add(position)
        await db_session.commit()
        await db_session.refresh(position)
        return position

    @pytest.mark.unit
    async def test_create_valid_position(
        self, db_session, parent_simulation, valid_position_data
    ):
        """Test creating a valid position record."""
        position = ArenaPosition(
            simulation_id=parent_simulation.id, **valid_position_data
        )
        db_session.add(position)
        await db_session.commit()
        await db_session.refresh(position)

        assert position.id is not None
        assert position.simulation_id == parent_simulation.id
        assert position.symbol == "AAPL"
        assert position.signal_date == date(2024, 1, 15)
        assert position.trailing_stop_pct == Decimal("5.00")
        assert position.status == PositionStatus.PENDING.value

    @pytest.mark.unit
    async def test_position_entry_fields(
        self, db_session, parent_simulation, valid_position_data
    ):
        """Test entry fields work correctly."""
        position = ArenaPosition(
            simulation_id=parent_simulation.id,
            **valid_position_data,
            entry_date=date(2024, 1, 16),
            entry_price=Decimal("185.5000"),
            shares=54,
            status=PositionStatus.OPEN.value,
        )
        db_session.add(position)
        await db_session.commit()
        await db_session.refresh(position)

        assert position.entry_date == date(2024, 1, 16)
        assert position.entry_price == Decimal("185.5000")
        assert position.shares == 54

    @pytest.mark.unit
    async def test_position_trailing_stop_fields(
        self, db_session, parent_simulation, valid_position_data
    ):
        """Test trailing stop fields work correctly."""
        position = ArenaPosition(
            simulation_id=parent_simulation.id,
            **valid_position_data,
            entry_price=Decimal("185.00"),
            highest_price=Decimal("195.00"),
            current_stop=Decimal("185.25"),
        )
        db_session.add(position)
        await db_session.commit()
        await db_session.refresh(position)

        assert position.highest_price == Decimal("195.00")
        assert position.current_stop == Decimal("185.25")

    @pytest.mark.unit
    async def test_position_exit_fields(
        self, db_session, parent_simulation, valid_position_data
    ):
        """Test exit fields work correctly."""
        position = ArenaPosition(
            simulation_id=parent_simulation.id,
            **valid_position_data,
            entry_date=date(2024, 1, 16),
            entry_price=Decimal("185.00"),
            shares=54,
            exit_date=date(2024, 2, 1),
            exit_price=Decimal("195.00"),
            exit_reason=ExitReason.STOP_HIT.value,
            realized_pnl=Decimal("540.00"),
            return_pct=Decimal("5.4054"),
            status=PositionStatus.CLOSED.value,
        )
        db_session.add(position)
        await db_session.commit()
        await db_session.refresh(position)

        assert position.exit_date == date(2024, 2, 1)
        assert position.exit_price == Decimal("195.00")
        assert position.exit_reason == ExitReason.STOP_HIT.value
        assert position.realized_pnl == Decimal("540.00")
        assert position.return_pct == Decimal("5.4054")

    @pytest.mark.unit
    async def test_position_agent_metadata(
        self, db_session, parent_simulation, valid_position_data
    ):
        """Test agent metadata fields work correctly."""
        position = ArenaPosition(
            simulation_id=parent_simulation.id,
            **valid_position_data,
            agent_reasoning="Strong mean reversion signal with volume confirmation",
            agent_score=75,
        )
        db_session.add(position)
        await db_session.commit()
        await db_session.refresh(position)

        assert "mean reversion" in position.agent_reasoning
        assert position.agent_score == 75

    @pytest.mark.unit
    async def test_position_is_open_property(self, sample_position):
        """Test is_open property."""
        assert sample_position.is_open is False

        sample_position.status = PositionStatus.OPEN.value
        assert sample_position.is_open is True

    @pytest.mark.unit
    async def test_position_is_closed_property(self, sample_position):
        """Test is_closed property."""
        assert sample_position.is_closed is False

        sample_position.status = PositionStatus.CLOSED.value
        assert sample_position.is_closed is True

    @pytest.mark.unit
    async def test_position_is_profitable_property(
        self, db_session, parent_simulation, valid_position_data
    ):
        """Test is_profitable property."""
        position = ArenaPosition(
            simulation_id=parent_simulation.id, **valid_position_data
        )

        # No realized_pnl yet
        assert position.is_profitable is None

        # Profitable position
        position.realized_pnl = Decimal("100.00")
        assert position.is_profitable is True

        # Losing position
        position.realized_pnl = Decimal("-50.00")
        assert position.is_profitable is False

        # Breakeven
        position.realized_pnl = Decimal("0.00")
        assert position.is_profitable is False

    @pytest.mark.unit
    async def test_position_calculate_pnl(
        self, db_session, parent_simulation, valid_position_data
    ):
        """Test calculate_pnl method."""
        position = ArenaPosition(
            simulation_id=parent_simulation.id,
            **valid_position_data,
            entry_price=Decimal("100.00"),
            shares=50,
        )

        # Profitable trade
        pnl = position.calculate_pnl(Decimal("110.00"))
        assert pnl == Decimal("500.00")

        # Losing trade
        pnl = position.calculate_pnl(Decimal("95.00"))
        assert pnl == Decimal("-250.00")

    @pytest.mark.unit
    async def test_position_calculate_pnl_no_entry(
        self, db_session, parent_simulation, valid_position_data
    ):
        """Test calculate_pnl returns 0 when no entry price."""
        position = ArenaPosition(
            simulation_id=parent_simulation.id, **valid_position_data
        )

        pnl = position.calculate_pnl(Decimal("110.00"))
        assert pnl == Decimal("0")

    @pytest.mark.unit
    async def test_position_calculate_return_pct(
        self, db_session, parent_simulation, valid_position_data
    ):
        """Test calculate_return_pct method."""
        position = ArenaPosition(
            simulation_id=parent_simulation.id,
            **valid_position_data,
            entry_price=Decimal("100.00"),
            shares=50,
        )

        # 10% gain
        return_pct = position.calculate_return_pct(Decimal("110.00"))
        assert return_pct == Decimal("10")

        # 5% loss
        return_pct = position.calculate_return_pct(Decimal("95.00"))
        assert return_pct == Decimal("-5")

    @pytest.mark.unit
    async def test_position_calculate_return_pct_no_entry(
        self, db_session, parent_simulation, valid_position_data
    ):
        """Test calculate_return_pct returns 0 when no entry price."""
        position = ArenaPosition(
            simulation_id=parent_simulation.id, **valid_position_data
        )

        return_pct = position.calculate_return_pct(Decimal("110.00"))
        assert return_pct == Decimal("0")

    @pytest.mark.unit
    async def test_position_repr(self, sample_position):
        """Test string representation."""
        repr_str = repr(sample_position)

        assert "ArenaPosition" in repr_str
        assert "AAPL" in repr_str
        assert "pending" in repr_str

    @pytest.mark.unit
    async def test_position_foreign_key_constraint(self, db_session, valid_position_data):
        """Test foreign key constraint on simulation_id."""
        # Non-existent simulation_id
        position = ArenaPosition(
            simulation_id=99999,  # Invalid ID
            **valid_position_data,
        )
        db_session.add(position)

        with pytest.raises(IntegrityError):
            await db_session.commit()

        await db_session.rollback()

    @pytest.mark.unit
    async def test_position_status_enum_values(self):
        """Test all position status enum values."""
        assert PositionStatus.PENDING.value == "pending"
        assert PositionStatus.OPEN.value == "open"
        assert PositionStatus.CLOSED.value == "closed"

    @pytest.mark.unit
    async def test_exit_reason_enum_values(self):
        """Test all exit reason enum values."""
        assert ExitReason.STOP_HIT.value == "stop_hit"
        assert ExitReason.SIMULATION_END.value == "simulation_end"
        assert ExitReason.INSUFFICIENT_CAPITAL.value == "insufficient_capital"


# =============================================================================
# ArenaSnapshot Tests
# =============================================================================


@pytest.mark.usefixtures("db_session")
class TestArenaSnapshotModel:
    """Test ArenaSnapshot model validation and functionality."""

    @pytest.fixture
    async def parent_simulation(self, db_session, valid_simulation_data):
        """Create a parent simulation for snapshots."""
        simulation = ArenaSimulation(**valid_simulation_data)
        db_session.add(simulation)
        await db_session.commit()
        await db_session.refresh(simulation)
        return simulation

    @pytest.fixture
    async def sample_snapshot(
        self, db_session, parent_simulation, valid_snapshot_data
    ):
        """Create a sample snapshot record."""
        snapshot = ArenaSnapshot(
            simulation_id=parent_simulation.id, **valid_snapshot_data
        )
        db_session.add(snapshot)
        await db_session.commit()
        await db_session.refresh(snapshot)
        return snapshot

    @pytest.mark.unit
    async def test_create_valid_snapshot(
        self, db_session, parent_simulation, valid_snapshot_data
    ):
        """Test creating a valid snapshot record."""
        snapshot = ArenaSnapshot(
            simulation_id=parent_simulation.id, **valid_snapshot_data
        )
        db_session.add(snapshot)
        await db_session.commit()
        await db_session.refresh(snapshot)

        assert snapshot.id is not None
        assert snapshot.simulation_id == parent_simulation.id
        assert snapshot.snapshot_date == date(2024, 1, 15)
        assert snapshot.day_number == 10
        assert snapshot.cash == Decimal("8000.00")
        assert snapshot.positions_value == Decimal("2500.00")
        assert snapshot.total_equity == Decimal("10500.00")
        assert snapshot.daily_pnl == Decimal("100.00")
        assert snapshot.daily_return_pct == Decimal("0.96")
        assert snapshot.cumulative_return_pct == Decimal("5.00")
        assert snapshot.open_position_count == 2
        assert snapshot.decisions == {"AAPL": {"action": "HOLD", "score": 75}}

    @pytest.mark.unit
    async def test_snapshot_default_values(self, db_session, parent_simulation):
        """Test default values are applied correctly."""
        minimal_data = {
            "simulation_id": parent_simulation.id,
            "snapshot_date": date(2024, 1, 15),
            "day_number": 10,
            "cash": Decimal("8000.00"),
            "positions_value": Decimal("2000.00"),
            "total_equity": Decimal("10000.00"),
        }
        snapshot = ArenaSnapshot(**minimal_data)
        db_session.add(snapshot)
        await db_session.commit()
        await db_session.refresh(snapshot)

        assert snapshot.daily_pnl == Decimal("0")
        assert snapshot.daily_return_pct == Decimal("0")
        assert snapshot.cumulative_return_pct == Decimal("0")
        assert snapshot.open_position_count == 0
        assert snapshot.decisions == {}

    @pytest.mark.unit
    async def test_snapshot_is_up_day_property(self, sample_snapshot):
        """Test is_up_day property."""
        # Sample has positive daily_pnl
        assert sample_snapshot.is_up_day is True

        # Negative day
        sample_snapshot.daily_pnl = Decimal("-50.00")
        assert sample_snapshot.is_up_day is False

        # Zero day
        sample_snapshot.daily_pnl = Decimal("0.00")
        assert sample_snapshot.is_up_day is False

    @pytest.mark.unit
    async def test_snapshot_repr(self, sample_snapshot):
        """Test string representation."""
        repr_str = repr(sample_snapshot)

        assert "ArenaSnapshot" in repr_str
        assert "2024-01-15" in repr_str
        assert "10" in repr_str  # day number

    @pytest.mark.unit
    async def test_snapshot_foreign_key_constraint(self, db_session, valid_snapshot_data):
        """Test foreign key constraint on simulation_id."""
        snapshot = ArenaSnapshot(
            simulation_id=99999,  # Invalid ID
            **valid_snapshot_data,
        )
        db_session.add(snapshot)

        with pytest.raises(IntegrityError):
            await db_session.commit()

        await db_session.rollback()

    @pytest.mark.unit
    async def test_snapshot_decisions_json(
        self, db_session, parent_simulation, valid_snapshot_data
    ):
        """Test complex decisions JSON structure."""
        complex_decisions = {
            "AAPL": {"action": "BUY", "score": 85, "reasoning": "Strong reversal"},
            "GOOGL": {"action": "NO_SIGNAL", "score": 40, "reasoning": "Weak setup"},
            "MSFT": {"action": "HOLD", "score": 60, "reasoning": "Existing position"},
        }
        snapshot = ArenaSnapshot(
            simulation_id=parent_simulation.id,
            **{**valid_snapshot_data, "decisions": complex_decisions},
        )
        db_session.add(snapshot)
        await db_session.commit()
        await db_session.refresh(snapshot)

        assert snapshot.decisions == complex_decisions
        assert snapshot.decisions["AAPL"]["action"] == "BUY"


# =============================================================================
# Relationship Tests
# =============================================================================


@pytest.mark.usefixtures("db_session")
class TestArenaRelationships:
    """Test relationships between Arena models."""

    @pytest.fixture
    async def simulation_with_data(
        self, db_session, valid_simulation_data, valid_position_data, valid_snapshot_data
    ):
        """Create a simulation with positions and snapshots."""
        simulation = ArenaSimulation(**valid_simulation_data)
        db_session.add(simulation)
        await db_session.commit()
        await db_session.refresh(simulation)

        # Add positions
        position1 = ArenaPosition(
            simulation_id=simulation.id,
            symbol="AAPL",
            signal_date=date(2024, 1, 15),
            trailing_stop_pct=Decimal("5.00"),
        )
        position2 = ArenaPosition(
            simulation_id=simulation.id,
            symbol="GOOGL",
            signal_date=date(2024, 1, 20),
            trailing_stop_pct=Decimal("5.00"),
        )
        db_session.add_all([position1, position2])

        # Add snapshots
        snapshot1 = ArenaSnapshot(
            simulation_id=simulation.id, **valid_snapshot_data
        )
        snapshot2 = ArenaSnapshot(
            simulation_id=simulation.id,
            snapshot_date=date(2024, 1, 16),
            day_number=11,
            cash=Decimal("7000.00"),
            positions_value=Decimal("3500.00"),
            total_equity=Decimal("10500.00"),
        )
        db_session.add_all([snapshot1, snapshot2])

        await db_session.commit()
        await db_session.refresh(simulation)

        return simulation

    @pytest.mark.unit
    async def test_simulation_positions_relationship(self, simulation_with_data):
        """Test simulation.positions relationship."""
        assert len(simulation_with_data.positions) == 2
        symbols = {p.symbol for p in simulation_with_data.positions}
        assert symbols == {"AAPL", "GOOGL"}

    @pytest.mark.unit
    async def test_simulation_snapshots_relationship(self, simulation_with_data):
        """Test simulation.snapshots relationship."""
        assert len(simulation_with_data.snapshots) == 2
        day_numbers = {s.day_number for s in simulation_with_data.snapshots}
        assert day_numbers == {10, 11}

    @pytest.mark.unit
    async def test_position_simulation_relationship(self, simulation_with_data):
        """Test position.simulation relationship."""
        position = simulation_with_data.positions[0]
        assert position.simulation is not None
        assert position.simulation.id == simulation_with_data.id

    @pytest.mark.unit
    async def test_snapshot_simulation_relationship(self, simulation_with_data):
        """Test snapshot.simulation relationship."""
        snapshot = simulation_with_data.snapshots[0]
        assert snapshot.simulation is not None
        assert snapshot.simulation.id == simulation_with_data.id

    @pytest.mark.unit
    async def test_cascade_delete_positions(self, db_session, simulation_with_data):
        """Test positions are deleted when simulation is deleted."""
        simulation_id = simulation_with_data.id

        # Delete simulation
        await db_session.delete(simulation_with_data)
        await db_session.commit()

        # Verify positions are also deleted
        result = await db_session.execute(
            select(ArenaPosition).where(ArenaPosition.simulation_id == simulation_id)
        )
        positions = result.scalars().all()
        assert len(positions) == 0

    @pytest.mark.unit
    async def test_cascade_delete_snapshots(self, db_session, simulation_with_data):
        """Test snapshots are deleted when simulation is deleted."""
        simulation_id = simulation_with_data.id

        # Delete simulation
        await db_session.delete(simulation_with_data)
        await db_session.commit()

        # Verify snapshots are also deleted
        result = await db_session.execute(
            select(ArenaSnapshot).where(ArenaSnapshot.simulation_id == simulation_id)
        )
        snapshots = result.scalars().all()
        assert len(snapshots) == 0


# =============================================================================
# Edge Case Tests
# =============================================================================


@pytest.mark.usefixtures("db_session")
class TestArenaEdgeCases:
    """Test edge cases and error conditions."""

    @pytest.mark.unit
    async def test_simulation_empty_symbols_list(self, db_session, valid_simulation_data):
        """Test simulation with empty symbols list."""
        valid_simulation_data["symbols"] = []
        simulation = ArenaSimulation(**valid_simulation_data)
        db_session.add(simulation)
        await db_session.commit()

        assert simulation.symbols == []

    @pytest.mark.unit
    async def test_simulation_large_symbol_list(self, db_session, valid_simulation_data):
        """Test simulation with many symbols."""
        valid_simulation_data["symbols"] = [f"SYM{i}" for i in range(100)]
        simulation = ArenaSimulation(**valid_simulation_data)
        db_session.add(simulation)
        await db_session.commit()

        assert len(simulation.symbols) == 100

    @pytest.mark.unit
    async def test_simulation_complex_agent_config(
        self, db_session, valid_simulation_data
    ):
        """Test simulation with complex agent config."""
        valid_simulation_data["agent_config"] = {
            "trailing_stop_pct": 5.0,
            "min_score": 60,
            "lookback_days": 60,
            "criteria_weights": {
                "trend": 20,
                "ma_distance": 20,
                "candle_pattern": 20,
                "volume": 20,
                "cci": 20,
            },
        }
        simulation = ArenaSimulation(**valid_simulation_data)
        db_session.add(simulation)
        await db_session.commit()

        assert simulation.agent_config["criteria_weights"]["trend"] == 20

    @pytest.mark.unit
    async def test_position_decimal_precision(self, db_session, valid_simulation_data):
        """Test position with high precision decimals."""
        simulation = ArenaSimulation(**valid_simulation_data)
        db_session.add(simulation)
        await db_session.commit()

        position = ArenaPosition(
            simulation_id=simulation.id,
            symbol="AAPL",
            signal_date=date(2024, 1, 15),
            trailing_stop_pct=Decimal("5.75"),
            entry_price=Decimal("185.2567"),
            highest_price=Decimal("195.9999"),
            current_stop=Decimal("186.1499"),
        )
        db_session.add(position)
        await db_session.commit()
        await db_session.refresh(position)

        assert position.entry_price == Decimal("185.2567")
        assert position.highest_price == Decimal("195.9999")

    @pytest.mark.unit
    async def test_snapshot_large_equity_values(self, db_session, valid_simulation_data):
        """Test snapshot with large equity values."""
        simulation = ArenaSimulation(**valid_simulation_data)
        db_session.add(simulation)
        await db_session.commit()

        snapshot = ArenaSnapshot(
            simulation_id=simulation.id,
            snapshot_date=date(2024, 1, 15),
            day_number=10,
            cash=Decimal("9999999999.99"),
            positions_value=Decimal("9999999999.99"),
            total_equity=Decimal("9999999999.99"),
        )
        db_session.add(snapshot)
        await db_session.commit()
        await db_session.refresh(snapshot)

        assert snapshot.total_equity == Decimal("9999999999.99")

    @pytest.mark.unit
    async def test_simulation_error_message_long_text(
        self, db_session, valid_simulation_data
    ):
        """Test simulation with long error message."""
        simulation = ArenaSimulation(**valid_simulation_data)
        simulation.status = SimulationStatus.FAILED.value
        simulation.error_message = "Error " * 500  # Long error message

        db_session.add(simulation)
        await db_session.commit()

        assert len(simulation.error_message) > 1000
