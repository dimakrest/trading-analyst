"""Database model for Live 20 simulation runs."""

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Integer, JSON, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.recommendation import Recommendation


class Live20RunStatus(str, Enum):
    """Status of a Live20 run."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


class Live20Run(Base):
    """Persisted Live 20 simulation run.

    Tracks Live 20 mean reversion analysis execution with symbol breakdown.
    Each run represents a single batch of symbols analyzed for mean reversion setups.
    """

    __tablename__ = "live20_runs"

    # Run status for queue management
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending", doc="Run status"
    )

    # Symbol tracking
    symbol_count: Mapped[int] = mapped_column(
        Integer, nullable=False, doc="Total number of symbols analyzed"
    )
    long_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, doc="Number of LONG setups"
    )
    short_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, doc="Number of SHORT setups"
    )
    no_setup_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, doc="Number of NO_SETUP results"
    )

    # Store input symbols for reference: ["AAPL", "MSFT", "GOOGL"]
    input_symbols: Mapped[list] = mapped_column(
        JSON, nullable=False, doc="List of symbols analyzed in this run"
    )

    # Stock list tracking (optional - null if manual entry)
    stock_list_id: Mapped[int | None] = mapped_column(
        Integer, nullable=True, doc="ID of stock list used, if any"
    )
    stock_list_name: Mapped[str | None] = mapped_column(
        String(255), nullable=True, doc="Name of stock list at time of analysis"
    )

    # Multi-list tracking (for combined list analysis)
    source_lists: Mapped[list[dict] | None] = mapped_column(
        JSONB,
        nullable=True,
        doc="Array of source lists when multiple lists combined: [{id: int, name: str}, ...]",
    )

    # Pricing strategy configuration
    strategy_config: Mapped[dict | None] = mapped_column(
        JSON, nullable=True, doc="Pricing strategy configuration used for this run"
    )

    # Queue management columns for PostgreSQL-based job queue
    worker_id: Mapped[str | None] = mapped_column(
        String(50), nullable=True, doc="ID of worker processing this run"
    )
    claimed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, doc="When run was claimed by worker"
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
        Text, nullable=True, doc="Last error message (for retry tracking)"
    )
    processed_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, doc="Number of symbols processed (for resume)"
    )
    # Failed symbols tracking: {"AAPL": "Data unavailable", "MSFT": "Rate limited"}
    failed_symbols: Mapped[dict | None] = mapped_column(
        JSON, nullable=True, doc="Dict of failed symbols with error messages"
    )

    # Relationship to recommendations
    recommendations: Mapped[list["Recommendation"]] = relationship(
        "Recommendation",
        back_populates="live20_run",
        foreign_keys="Recommendation.live20_run_id",
        lazy="selectin",
        doc="Recommendations created during this run",
    )

    def __repr__(self) -> str:
        """String representation of Live20Run."""
        return (
            f"<Live20Run(id={self.id}, status={self.status}, symbol_count={self.symbol_count}, "
            f"long={self.long_count}, short={self.short_count})>"
        )
