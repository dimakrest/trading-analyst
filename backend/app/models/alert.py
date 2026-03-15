"""Stock price alert models for monitoring symbols at key technical levels.

Models:
- StockAlert: An alert configuration tracking a symbol against a technical setup
- AlertEvent: An immutable audit log of state transitions for an alert
"""
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean
from sqlalchemy import DateTime
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import JSON
from sqlalchemy import Numeric
from sqlalchemy import String
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship

from app.models.base import Base


# Valid status values for each alert type
VALID_FIBONACCI_STATUSES: frozenset[str] = frozenset({
    "no_structure",
    "rallying",
    "pullback_started",
    "retracing",
    "at_level",
    "bouncing",
    "invalidated",
})

VALID_MA_STATUSES: frozenset[str] = frozenset({
    "above_ma",
    "approaching",
    "at_ma",
    "below_ma",
    "insufficient_data",
})


class StockAlert(Base):
    """A price alert monitoring a symbol against a technical setup.

    Supports two alert types:
    - fibonacci: Tracks price relative to a Fibonacci retracement structure
    - moving_average: Tracks price relative to a moving average

    The config field stores alert-type-specific configuration (e.g., anchor
    points for Fibonacci or MA period/type for moving average alerts).

    The computed_state field caches pre-computed values for frontend rendering,
    avoiding redundant calculations on every read.
    """

    __tablename__ = "stock_alerts"

    # Symbol and alert classification
    symbol: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True,
        doc="Stock ticker symbol (e.g., 'AAPL')",
    )
    alert_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True,
        doc="Alert type: 'fibonacci' or 'moving_average'",
    )

    # Lifecycle state
    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        index=True,
        doc=(
            "Current alert status. Fibonacci: no_structure/rallying/pullback_started/"
            "retracing/at_level/bouncing/invalidated. "
            "MA: above_ma/approaching/at_ma/below_ma/insufficient_data"
        ),
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
        doc="Whether this alert is actively being monitored",
    )
    is_paused: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
        doc="Whether monitoring is temporarily paused by the user",
    )

    # Alert-type-specific configuration (e.g., Fibonacci anchor prices, MA period)
    config: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
        doc="Alert-type-specific configuration parameters",
    )

    # Pre-computed rendering state for the frontend
    computed_state: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        doc="Pre-computed state values for frontend rendering (cached)",
    )

    # Timing
    last_triggered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="Timestamp of the most recent status transition that triggered a notification",
    )

    # Relationship to event log
    events: Mapped[list["AlertEvent"]] = relationship(
        "AlertEvent",
        back_populates="alert",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="AlertEvent.created_at",
        doc="Ordered audit log of state transitions for this alert",
    )

    def __repr__(self) -> str:
        """String representation of StockAlert."""
        return (
            f"<StockAlert(id={self.id}, symbol={self.symbol}, "
            f"type={self.alert_type}, status={self.status}, active={self.is_active})>"
        )

    @property
    def is_fibonacci(self) -> bool:
        """Check if this is a Fibonacci retracement alert."""
        return self.alert_type == "fibonacci"

    @property
    def is_moving_average(self) -> bool:
        """Check if this is a moving average alert."""
        return self.alert_type == "moving_average"

    @property
    def valid_statuses(self) -> frozenset[str]:
        """Return the set of valid status values for this alert's type."""
        if self.is_fibonacci:
            return VALID_FIBONACCI_STATUSES
        return VALID_MA_STATUSES


class AlertEvent(Base):
    """Immutable audit log entry recording a state transition on a StockAlert.

    Every status change is recorded as a new AlertEvent. Events are never
    updated or deleted — they form an append-only history of the alert's
    lifecycle.

    Event types:
    - level_hit: Price reached a key technical level
    - invalidated: Structure was invalidated (e.g., stop blown through)
    - re_anchored: Fibonacci anchor points were recalculated
    - status_change: General status transition not covered above
    """

    __tablename__ = "alert_events"

    # Link to parent alert
    alert_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("stock_alerts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="ID of the StockAlert this event belongs to",
    )

    # Event classification
    event_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        doc="Event type: 'level_hit', 'invalidated', 're_anchored', 'status_change'",
    )

    # State transition
    previous_status: Mapped[str | None] = mapped_column(
        String(30),
        nullable=True,
        doc="Alert status before this event (null for the initial creation event)",
    )
    new_status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        doc="Alert status after this event",
    )

    # Market context at the time of the event
    price_at_event: Mapped[Decimal] = mapped_column(
        Numeric(12, 4),
        nullable=False,
        doc="Market price of the symbol when this event occurred",
    )

    # Additional structured detail specific to the event type
    details: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        doc="Optional structured details specific to this event type",
    )

    # Relationship back to alert
    alert: Mapped["StockAlert"] = relationship(
        "StockAlert",
        back_populates="events",
    )

    def __repr__(self) -> str:
        """String representation of AlertEvent."""
        return (
            f"<AlertEvent(id={self.id}, alert_id={self.alert_id}, "
            f"type={self.event_type}, {self.previous_status} -> {self.new_status}, "
            f"price={self.price_at_event})>"
        )
