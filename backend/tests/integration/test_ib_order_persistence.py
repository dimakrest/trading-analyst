"""Integration tests for IB order persistence across restarts."""
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ib_order import IBOrderStatus
from app.repositories.ib_order_repository import IBOrderRepository


@pytest.mark.integration
class TestIBOrderPersistence:
    """Integration tests for order persistence."""

    @pytest.mark.asyncio
    async def test_order_survives_broker_restart(self, db_session: AsyncSession):
        """Test that orders can be queried after broker instance is recreated.

        Simulates service restart by creating new broker instance.
        """
        # Create order in first broker instance
        repo = IBOrderRepository(db_session)
        await repo.create_order(
            composite_order_id="IB-1001:1002",
            entry_order_id=1001,
            stop_order_id=1002,
            symbol="AAPL",
            quantity=100,
            stop_price=Decimal("145.00"),
            filled_price=Decimal("150.00"),
            status=IBOrderStatus.FILLED,
        )
        await db_session.commit()

        # Simulate restart: create new repository instance
        new_repo = IBOrderRepository(db_session)

        # Query order from "new session"
        order = await new_repo.get_by_composite_id("IB-1001:1002")

        assert order is not None
        assert order.symbol == "AAPL"
        assert order.quantity == 100
        assert order.filled_price == Decimal("150.00")
        assert order.status == IBOrderStatus.FILLED.value

    @pytest.mark.asyncio
    async def test_multiple_orders_persist(self, db_session: AsyncSession):
        """Test that multiple orders persist correctly."""
        repo = IBOrderRepository(db_session)

        # Create multiple orders
        for i in range(5):
            await repo.create_order(
                composite_order_id=f"IB-{1000+i}:{2000+i}",
                entry_order_id=1000 + i,
                stop_order_id=2000 + i,
                symbol="TSLA" if i % 2 == 0 else "AAPL",
                quantity=10 * (i + 1),
                stop_price=Decimal("200.00") - i,
            )

        await db_session.commit()

        # Verify all orders exist
        for i in range(5):
            order = await repo.get_by_composite_id(f"IB-{1000+i}:{2000+i}")
            assert order is not None
            assert order.quantity == 10 * (i + 1)
