"""Repository for IB order persistence operations."""
import logging
from decimal import Decimal

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ib_order import IBOrder, IBOrderStatus
from app.repositories.base import BaseRepository

logger = logging.getLogger(__name__)


class IBOrderRepository(BaseRepository[IBOrder]):
    """Repository for IB order data access operations."""

    def __init__(self, session: AsyncSession):
        """Initialize IB order repository with database session."""
        super().__init__(IBOrder, session)
        self.logger = logger

    async def create_order(
        self,
        composite_order_id: str,
        entry_order_id: int,
        stop_order_id: int | None,
        symbol: str,
        quantity: int,
        stop_price: Decimal,
        filled_price: Decimal | None = None,
        status: IBOrderStatus = IBOrderStatus.PENDING,
    ) -> IBOrder:
        """Create a new IB order record."""
        return await super().create(
            composite_order_id=composite_order_id,
            entry_order_id=entry_order_id,
            stop_order_id=stop_order_id,
            symbol=symbol,
            quantity=quantity,
            stop_price=stop_price,
            filled_price=filled_price,
            status=status.value,
        )

    async def get_by_composite_id(self, composite_order_id: str) -> IBOrder | None:
        """Get order by composite order ID."""
        query = select(IBOrder).where(
            IBOrder.composite_order_id == composite_order_id,
            IBOrder.deleted_at.is_(None),
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def update_status(
        self,
        composite_order_id: str,
        status: IBOrderStatus,
        filled_price: Decimal | None = None,
    ) -> IBOrder | None:
        """Update order status and optionally fill price."""
        order = await self.get_by_composite_id(composite_order_id)
        if not order:
            return None

        order.status = status.value
        if filled_price is not None:
            order.filled_price = filled_price

        await self.session.flush()
        await self.session.refresh(order)

        self.logger.info(f"Updated IBOrder {composite_order_id} to status {status.value}")
        return order

    async def update_status_if_changed(
        self,
        composite_order_id: str,
        expected_status: str,
        new_status: IBOrderStatus,
    ) -> bool:
        """Atomically update order status only if current status matches expected.

        This is a compare-and-swap operation that prevents race conditions
        when multiple requests try to update the same order simultaneously.

        Args:
            composite_order_id: The composite order ID
            expected_status: Current status value (only update if this matches)
            new_status: New status to set

        Returns:
            True if update was performed, False if status didn't match
        """
        stmt = (
            update(IBOrder)
            .where(
                IBOrder.composite_order_id == composite_order_id,
                IBOrder.status == expected_status,
                IBOrder.deleted_at.is_(None),
            )
            .values(status=new_status.value)
        )
        result = await self.session.execute(stmt)
        await self.session.flush()

        updated = result.rowcount > 0
        if updated:
            self.logger.info(
                f"Updated IBOrder {composite_order_id} from {expected_status} to {new_status.value}"
            )
        return updated

    async def list_by_status(
        self,
        status: IBOrderStatus,
        limit: int = 100,
    ) -> list[IBOrder]:
        """List orders by status."""
        return await super().list(
            filters={"status": status.value},
            order_by="created_at",
            order_desc=True,
            limit=limit,
        )

    async def list_by_symbol(
        self,
        symbol: str,
        limit: int = 100,
    ) -> list[IBOrder]:
        """List orders for a specific symbol."""
        return await super().list(
            filters={"symbol": symbol.upper()},
            order_by="created_at",
            order_desc=True,
            limit=limit,
        )
