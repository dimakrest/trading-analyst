"""Arena simulation models for trading agent competitions.

This module defines models for:
- ArenaSimulation: Main simulation entity with configuration and state
- ArenaPosition: Trading positions within a simulation
- ArenaSnapshot: Daily portfolio snapshots for tracking progress
"""
from datetime import date
from datetime import datetime
from decimal import Decimal
from enum import Enum

from sqlalchemy import BigInteger
from sqlalchemy import Date
from sqlalchemy import DateTime
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import JSON
from sqlalchemy import Numeric
from sqlalchemy import String
from sqlalchemy import Text
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship

from app.models.base import Base


class SimulationStatus(str, Enum):
    """Simulation lifecycle states."""

    PENDING = "pending"  # Initial state, waiting for worker
    RUNNING = "running"  # Actively processing days
    PAUSED = "paused"  # User paused (can resume)
    COMPLETED = "completed"  # Finished all days
    CANCELLED = "cancelled"  # User cancelled
    FAILED = "failed"  # Error occurred


class PositionStatus(str, Enum):
    """Position lifecycle states."""

    PENDING = "pending"  # Signal generated, awaiting next day open
    OPEN = "open"  # Position is active
    CLOSED = "closed"  # Position has been closed


class ExitReason(str, Enum):
    """Why a position was closed."""

    STOP_HIT = "stop_hit"  # Trailing stop triggered
    SIMULATION_END = "simulation_end"  # Simulation ended, forced close
    INSUFFICIENT_CAPITAL = "insufficient_capital"  # Price > position size


class ArenaSimulation(Base):
    """Arena simulation run.

    Represents a complete simulation with configuration, state tracking,
    and relationships to positions and snapshots.
    """

    __tablename__ = "arena_simulations"

    # Configuration
    name: Mapped[str | None] = mapped_column(
        String(255), nullable=True, doc="Optional user-provided name"
    )
    # Stock list tracking (optional - null if manual entry)
    stock_list_id: Mapped[int | None] = mapped_column(
        Integer, nullable=True, doc="ID of stock list used, if any"
    )
    stock_list_name: Mapped[str | None] = mapped_column(
        String(255), nullable=True, doc="Name of stock list at time of creation"
    )
    symbols: Mapped[list] = mapped_column(
        JSON, nullable=False, doc="List of symbols to trade"
    )
    start_date: Mapped[date] = mapped_column(
        Date, nullable=False, doc="Simulation start date"
    )
    end_date: Mapped[date] = mapped_column(
        Date, nullable=False, doc="Simulation end date"
    )

    # Capital settings
    initial_capital: Mapped[Decimal] = mapped_column(
        Numeric(precision=12, scale=2),
        nullable=False,
        default=Decimal("10000"),
        doc="Starting capital",
    )
    position_size: Mapped[Decimal] = mapped_column(
        Numeric(precision=12, scale=2),
        nullable=False,
        default=Decimal("1000"),
        doc="Fixed position size per trade",
    )

    # Agent configuration
    agent_type: Mapped[str] = mapped_column(
        String(50), nullable=False, doc="Agent type: 'live20'"
    )
    agent_config: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
        doc="Agent-specific configuration (e.g., trailing_stop_pct)",
    )

    # State tracking
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=SimulationStatus.PENDING.value
    )
    current_day: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, doc="Current simulation day (0-indexed)"
    )
    total_days: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, doc="Total trading days in range"
    )

    # Job queue fields
    worker_id: Mapped[str | None] = mapped_column(
        String(50), nullable=True, doc="ID of worker processing this job"
    )
    claimed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, doc="When job was claimed"
    )
    heartbeat_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, doc="Last heartbeat from worker"
    )
    retry_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, doc="Number of retry attempts"
    )
    max_retries: Mapped[int] = mapped_column(
        Integer, nullable=False, default=3, doc="Maximum retry attempts"
    )
    last_error: Mapped[str | None] = mapped_column(
        Text, nullable=True, doc="Last error for retry tracking"
    )

    # Results (updated as simulation progresses)
    final_equity: Mapped[Decimal | None] = mapped_column(
        Numeric(precision=12, scale=2), nullable=True, doc="Final portfolio value"
    )
    total_return_pct: Mapped[Decimal | None] = mapped_column(
        Numeric(precision=8, scale=4), nullable=True, doc="Total return percentage"
    )
    total_trades: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, doc="Total number of closed trades"
    )
    winning_trades: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, doc="Number of profitable trades"
    )
    max_drawdown_pct: Mapped[Decimal | None] = mapped_column(
        Numeric(precision=8, scale=4), nullable=True, doc="Maximum drawdown percentage"
    )

    # Error tracking
    error_message: Mapped[str | None] = mapped_column(
        Text, nullable=True, doc="Error message if simulation failed"
    )

    # Relationships
    positions: Mapped[list["ArenaPosition"]] = relationship(
        "ArenaPosition",
        back_populates="simulation",
        cascade="all, delete-orphan",
        lazy="selectin",
        doc="Positions in this simulation",
    )
    snapshots: Mapped[list["ArenaSnapshot"]] = relationship(
        "ArenaSnapshot",
        back_populates="simulation",
        cascade="all, delete-orphan",
        lazy="selectin",
        doc="Daily snapshots for this simulation",
    )

    def __repr__(self) -> str:
        """String representation of ArenaSimulation."""
        return (
            f"<ArenaSimulation(id={self.id}, agent={self.agent_type}, "
            f"status={self.status}, day={self.current_day}/{self.total_days})>"
        )

    @property
    def win_rate(self) -> Decimal | None:
        """Calculate win rate as a percentage."""
        if self.total_trades == 0:
            return None
        return Decimal(self.winning_trades) / Decimal(self.total_trades) * 100

    @property
    def is_complete(self) -> bool:
        """Check if simulation has completed all days."""
        return self.status == SimulationStatus.COMPLETED.value

    @property
    def is_initialized(self) -> bool:
        """Check if simulation has been initialized.

        Initialization calculates trading days and preloads price data.
        A simulation is initialized when total_days > 0.
        """
        return self.total_days > 0


class ArenaPosition(Base):
    """Trading position within a simulation.

    Tracks the complete lifecycle of a position from signal to exit.
    """

    __tablename__ = "arena_positions"

    # Link to simulation
    simulation_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("arena_simulations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="ID of the parent simulation",
    )

    # Position details
    symbol: Mapped[str] = mapped_column(String(10), nullable=False, doc="Stock symbol")
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=PositionStatus.PENDING.value
    )

    # Entry
    signal_date: Mapped[date] = mapped_column(
        Date, nullable=False, doc="Date when agent signaled entry"
    )
    entry_date: Mapped[date | None] = mapped_column(
        Date, nullable=True, doc="Date when position opened (signal_date + 1)"
    )
    entry_price: Mapped[Decimal | None] = mapped_column(
        Numeric(precision=12, scale=4), nullable=True, doc="Entry price (next day open)"
    )
    shares: Mapped[int | None] = mapped_column(
        Integer, nullable=True, doc="Number of shares"
    )

    # Trailing stop
    trailing_stop_pct: Mapped[Decimal] = mapped_column(
        Numeric(precision=5, scale=2),
        nullable=False,
        doc="Trailing stop percentage (e.g., 5.00 for 5%)",
    )
    highest_price: Mapped[Decimal | None] = mapped_column(
        Numeric(precision=12, scale=4),
        nullable=True,
        doc="Highest price since entry (for trailing stop)",
    )
    current_stop: Mapped[Decimal | None] = mapped_column(
        Numeric(precision=12, scale=4),
        nullable=True,
        doc="Current stop price (highest * (1 - trail_pct))",
    )

    # Exit
    exit_date: Mapped[date | None] = mapped_column(
        Date, nullable=True, doc="Date when position was closed"
    )
    exit_price: Mapped[Decimal | None] = mapped_column(
        Numeric(precision=12, scale=4), nullable=True, doc="Exit price"
    )
    exit_reason: Mapped[str | None] = mapped_column(
        String(30), nullable=True, doc="Reason for closing position"
    )

    # P&L
    realized_pnl: Mapped[Decimal | None] = mapped_column(
        Numeric(precision=12, scale=2), nullable=True, doc="Realized profit/loss"
    )
    return_pct: Mapped[Decimal | None] = mapped_column(
        Numeric(precision=8, scale=4), nullable=True, doc="Return percentage"
    )

    # Agent decision metadata
    agent_reasoning: Mapped[str | None] = mapped_column(
        Text, nullable=True, doc="Agent's reasoning for the trade"
    )
    agent_score: Mapped[int | None] = mapped_column(
        Integer, nullable=True, doc="Agent's confidence score"
    )

    # Relationship
    simulation: Mapped["ArenaSimulation"] = relationship(
        "ArenaSimulation", back_populates="positions"
    )

    def __repr__(self) -> str:
        """String representation of ArenaPosition."""
        return (
            f"<ArenaPosition(id={self.id}, symbol={self.symbol}, "
            f"status={self.status}, pnl={self.realized_pnl})>"
        )

    @property
    def is_open(self) -> bool:
        """Check if position is currently open."""
        return self.status == PositionStatus.OPEN.value

    @property
    def is_closed(self) -> bool:
        """Check if position is closed."""
        return self.status == PositionStatus.CLOSED.value

    @property
    def is_profitable(self) -> bool | None:
        """Check if position is profitable (None if not closed)."""
        if self.realized_pnl is None:
            return None
        return self.realized_pnl > 0

    def calculate_pnl(self, exit_price: Decimal) -> Decimal:
        """Calculate P&L for a given exit price.

        Args:
            exit_price: Price at which to calculate P&L

        Returns:
            Calculated profit/loss
        """
        if self.entry_price is None or self.shares is None:
            return Decimal("0")
        return (exit_price - self.entry_price) * self.shares

    def calculate_return_pct(self, exit_price: Decimal) -> Decimal:
        """Calculate return percentage for a given exit price.

        Args:
            exit_price: Price at which to calculate return

        Returns:
            Return percentage
        """
        if self.entry_price is None or self.entry_price == 0:
            return Decimal("0")
        return ((exit_price - self.entry_price) / self.entry_price) * 100


class ArenaSnapshot(Base):
    """Daily snapshot of portfolio state.

    Captures the complete portfolio state at the end of each trading day.
    """

    __tablename__ = "arena_snapshots"

    # Link to simulation
    simulation_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("arena_simulations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="ID of the parent simulation",
    )

    # Snapshot date
    snapshot_date: Mapped[date] = mapped_column(
        Date, nullable=False, doc="Date of this snapshot"
    )
    day_number: Mapped[int] = mapped_column(
        Integer, nullable=False, doc="Day number in simulation (0-indexed)"
    )

    # Portfolio state
    cash: Mapped[Decimal] = mapped_column(
        Numeric(precision=12, scale=2), nullable=False, doc="Available cash"
    )
    positions_value: Mapped[Decimal] = mapped_column(
        Numeric(precision=12, scale=2),
        nullable=False,
        doc="Market value of open positions",
    )
    total_equity: Mapped[Decimal] = mapped_column(
        Numeric(precision=12, scale=2), nullable=False, doc="Total portfolio value"
    )

    # Daily metrics
    daily_pnl: Mapped[Decimal] = mapped_column(
        Numeric(precision=12, scale=2),
        nullable=False,
        default=Decimal("0"),
        doc="Daily profit/loss",
    )
    daily_return_pct: Mapped[Decimal] = mapped_column(
        Numeric(precision=8, scale=4),
        nullable=False,
        default=Decimal("0"),
        doc="Daily return percentage",
    )
    cumulative_return_pct: Mapped[Decimal] = mapped_column(
        Numeric(precision=8, scale=4),
        nullable=False,
        default=Decimal("0"),
        doc="Cumulative return since start",
    )

    # Position counts
    open_position_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, doc="Number of open positions"
    )

    # Agent decisions for this day
    decisions: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
        doc="Agent decisions: {symbol: {action, score, reasoning}}",
    )

    # Relationship
    simulation: Mapped["ArenaSimulation"] = relationship(
        "ArenaSimulation", back_populates="snapshots"
    )

    def __repr__(self) -> str:
        """String representation of ArenaSnapshot."""
        return (
            f"<ArenaSnapshot(id={self.id}, date={self.snapshot_date}, "
            f"day={self.day_number}, equity={self.total_equity})>"
        )

    @property
    def is_up_day(self) -> bool:
        """Check if this was a profitable day."""
        return self.daily_pnl > 0
