"""Integration tests for IBBroker against paper trading.

These tests require TWS/Gateway running with API enabled on port 7497.
They are skipped by default - remove the skip marker to run manually.
"""
from decimal import Decimal

import pytest

from app.brokers.base import OrderRequest, OrderStatus
from app.brokers.ib import IBBroker


@pytest.fixture
async def ib_broker():
    """Create and connect IBBroker for integration tests."""
    broker = IBBroker()
    await broker.connect()
    yield broker
    await broker.disconnect()


@pytest.mark.skip(reason="Requires TWS/Gateway running - run manually")
class TestIBBrokerIntegration:
    """Integration tests against paper trading."""

    @pytest.mark.asyncio
    async def test_connection(self, ib_broker):
        """Test connection to TWS/Gateway."""
        assert ib_broker._connected is True

    @pytest.mark.asyncio
    async def test_place_and_query_order(self, ib_broker):
        """Test placing and querying an order.

        WARNING: This will place a real paper trading order!
        """
        request = OrderRequest(
            ticker="AAPL",
            quantity=1,  # Minimal quantity
            order_type="MARKET",
            stop_loss_price=Decimal("100.00"),  # Low stop for safety
        )

        # Place order
        result = await ib_broker.place_order(request)

        assert result.order_id.startswith("IB-")
        assert result.status in [OrderStatus.FILLED, OrderStatus.PENDING]

        if result.status == OrderStatus.FILLED:
            assert result.filled_price is not None
            assert result.filled_quantity == 1

        # Query status
        status = await ib_broker.get_order_status(result.order_id)
        assert status.order_id == result.order_id

    @pytest.mark.asyncio
    async def test_cancel_stop_order(self, ib_broker):
        """Test cancelling the stop order after entry fills.

        WARNING: This will place a real paper trading order!
        """
        request = OrderRequest(
            ticker="AAPL",
            quantity=1,
            order_type="MARKET",
            stop_loss_price=Decimal("100.00"),
        )

        result = await ib_broker.place_order(request)

        if result.status == OrderStatus.FILLED:
            # Cancel (should cancel stop order)
            cancelled = await ib_broker.cancel_order(result.order_id)
            assert cancelled is True
