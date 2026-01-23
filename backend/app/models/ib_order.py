"""IB Order model for persisting order mappings across restarts."""
from decimal import Decimal
from enum import Enum

from sqlalchemy import BigInteger, CheckConstraint, Index, Numeric, String, desc
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class IBOrderStatus(str, Enum):
    """Status of an IB order pair (entry + stop)."""
    PENDING = "PENDING"      # Entry order submitted, awaiting fill
    FILLED = "FILLED"        # Entry filled, stop is active
    CANCELLED = "CANCELLED"  # Order was cancelled
    REJECTED = "REJECTED"    # Order was rejected by broker
    STOPPED = "STOPPED"      # Stop order was triggered


class IBOrder(Base):
    """Persisted IB order mapping.

    Stores the mapping between our composite order ID and the individual
    IB order IDs for entry and stop orders. This allows order status
    queries to work across service restarts.
    """

    __tablename__ = "ib_orders"

    # Composite order ID (e.g., "IB-123:456")
    composite_order_id: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        unique=True,
        index=True,
        doc="Composite order ID returned to caller (e.g., 'IB-123:456')"
    )

    # Individual IB order IDs
    entry_order_id: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        doc="IB order ID for the entry (market) order"
    )

    stop_order_id: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
        doc="IB order ID for the stop order (null if no stop)"
    )

    # Order details
    symbol: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        doc="Stock symbol (e.g., 'AAPL')"
    )

    quantity: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        doc="Number of shares"
    )

    filled_price: Mapped[Decimal | None] = mapped_column(
        Numeric(precision=12, scale=4),
        nullable=True,
        doc="Price at which entry order filled"
    )

    stop_price: Mapped[Decimal] = mapped_column(
        Numeric(precision=12, scale=4),
        nullable=False,
        doc="Stop loss price"
    )

    # Status tracking
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=IBOrderStatus.PENDING.value,
        doc="Current status of the order pair"
    )

    # Constraints and indexes
    __table_args__ = (
        CheckConstraint(
            f"status IN ('{IBOrderStatus.PENDING.value}', '{IBOrderStatus.FILLED.value}', "
            f"'{IBOrderStatus.CANCELLED.value}', '{IBOrderStatus.REJECTED.value}', "
            f"'{IBOrderStatus.STOPPED.value}')",
            name="ck_ib_orders_valid_status"
        ),
        CheckConstraint(
            "quantity > 0",
            name="ck_ib_orders_positive_quantity"
        ),
        Index("ix_ib_orders_symbol", "symbol"),
        Index("ix_ib_orders_status", "status"),
        Index("ix_ib_orders_created_at_desc", desc("created_at")),
    )

    def __repr__(self) -> str:
        return f"<IBOrder(id={self.id}, composite_id='{self.composite_order_id}', status='{self.status}')>"
