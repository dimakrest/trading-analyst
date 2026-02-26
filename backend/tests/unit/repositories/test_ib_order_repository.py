"""Unit tests for IBOrderRepository."""
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ib_order import IBOrder, IBOrderStatus
from app.repositories.base import DuplicateError
from app.repositories.ib_order_repository import IBOrderRepository


@pytest.fixture
def ib_order_repo(db_session: AsyncSession) -> IBOrderRepository:
    """Create IBOrderRepository with test session."""
    return IBOrderRepository(db_session)


class TestIBOrderRepository:
    """Tests for IBOrderRepository."""

    @pytest.mark.asyncio
    async def test_create_order(self, ib_order_repo: IBOrderRepository):
        """Test creating a new IB order record."""
        order = await ib_order_repo.create_order(
            composite_order_id="IB-1001:1002",
            entry_order_id=1001,
            stop_order_id=1002,
            symbol="AAPL",
            quantity=100,
            stop_price=Decimal("145.00"),
            filled_price=Decimal("150.00"),
            status=IBOrderStatus.FILLED,
        )

        assert order.id is not None
        assert order.composite_order_id == "IB-1001:1002"
        assert order.entry_order_id == 1001
        assert order.stop_order_id == 1002
        assert order.symbol == "AAPL"
        assert order.quantity == 100
        assert order.filled_price == Decimal("150.00")
        assert order.stop_price == Decimal("145.00")
        assert order.status == IBOrderStatus.FILLED.value

    @pytest.mark.asyncio
    async def test_create_order_without_stop(self, ib_order_repo: IBOrderRepository):
        """Test creating order without stop order."""
        order = await ib_order_repo.create_order(
            composite_order_id="IB-1001:none",
            entry_order_id=1001,
            stop_order_id=None,
            symbol="MSFT",
            quantity=50,
            stop_price=Decimal("300.00"),
        )

        assert order.stop_order_id is None
        assert order.status == IBOrderStatus.PENDING.value

    @pytest.mark.asyncio
    async def test_get_by_composite_id(self, ib_order_repo: IBOrderRepository):
        """Test retrieving order by composite ID."""
        # Create order
        await ib_order_repo.create_order(
            composite_order_id="IB-2001:2002",
            entry_order_id=2001,
            stop_order_id=2002,
            symbol="GOOGL",
            quantity=25,
            stop_price=Decimal("140.00"),
        )

        # Retrieve by composite ID
        order = await ib_order_repo.get_by_composite_id("IB-2001:2002")

        assert order is not None
        assert order.entry_order_id == 2001
        assert order.symbol == "GOOGL"

    @pytest.mark.asyncio
    async def test_get_by_composite_id_not_found(self, ib_order_repo: IBOrderRepository):
        """Test retrieving non-existent order returns None."""
        order = await ib_order_repo.get_by_composite_id("IB-9999:9999")
        assert order is None

    @pytest.mark.asyncio
    async def test_update_status(self, ib_order_repo: IBOrderRepository):
        """Test updating order status."""
        # Create order
        await ib_order_repo.create_order(
            composite_order_id="IB-3001:3002",
            entry_order_id=3001,
            stop_order_id=3002,
            symbol="NVDA",
            quantity=10,
            stop_price=Decimal("400.00"),
            status=IBOrderStatus.PENDING,
        )

        # Update status
        updated = await ib_order_repo.update_status(
            "IB-3001:3002",
            IBOrderStatus.FILLED,
            filled_price=Decimal("425.00"),
        )

        assert updated is not None
        assert updated.status == IBOrderStatus.FILLED.value
        assert updated.filled_price == Decimal("425.00")

    @pytest.mark.asyncio
    async def test_update_status_not_found(self, ib_order_repo: IBOrderRepository):
        """Test updating non-existent order returns None."""
        updated = await ib_order_repo.update_status(
            "IB-9999:9999",
            IBOrderStatus.FILLED,
        )
        assert updated is None

    @pytest.mark.asyncio
    async def test_list_by_status(self, ib_order_repo: IBOrderRepository):
        """Test listing orders by status."""
        # Create multiple orders with different statuses
        await ib_order_repo.create_order(
            composite_order_id="IB-4001:4002",
            entry_order_id=4001,
            stop_order_id=4002,
            symbol="AAPL",
            quantity=100,
            stop_price=Decimal("145.00"),
            status=IBOrderStatus.FILLED,
        )
        await ib_order_repo.create_order(
            composite_order_id="IB-4003:4004",
            entry_order_id=4003,
            stop_order_id=4004,
            symbol="MSFT",
            quantity=50,
            stop_price=Decimal("300.00"),
            status=IBOrderStatus.PENDING,
        )

        # List filled orders
        filled_orders = await ib_order_repo.list_by_status(IBOrderStatus.FILLED)

        assert len(filled_orders) >= 1
        assert all(o.status == IBOrderStatus.FILLED.value for o in filled_orders)

    @pytest.mark.asyncio
    async def test_list_by_symbol(self, ib_order_repo: IBOrderRepository):
        """Test listing orders by symbol."""
        # Create orders for different symbols
        await ib_order_repo.create_order(
            composite_order_id="IB-5001:5002",
            entry_order_id=5001,
            stop_order_id=5002,
            symbol="TSLA",
            quantity=20,
            stop_price=Decimal("200.00"),
        )
        await ib_order_repo.create_order(
            composite_order_id="IB-5003:5004",
            entry_order_id=5003,
            stop_order_id=5004,
            symbol="TSLA",
            quantity=30,
            stop_price=Decimal("195.00"),
        )

        # List TSLA orders
        tsla_orders = await ib_order_repo.list_by_symbol("TSLA")

        assert len(tsla_orders) >= 2
        assert all(o.symbol == "TSLA" for o in tsla_orders)

    @pytest.mark.asyncio
    async def test_unique_composite_id_constraint(self, ib_order_repo: IBOrderRepository):
        """Test that duplicate composite IDs raise error."""
        await ib_order_repo.create_order(
            composite_order_id="IB-6001:6002",
            entry_order_id=6001,
            stop_order_id=6002,
            symbol="AMD",
            quantity=100,
            stop_price=Decimal("100.00"),
        )

        with pytest.raises(DuplicateError):
            await ib_order_repo.create_order(
                composite_order_id="IB-6001:6002",  # Duplicate!
                entry_order_id=6003,
                stop_order_id=6004,
                symbol="AMD",
                quantity=50,
                stop_price=Decimal("95.00"),
            )

    @pytest.mark.asyncio
    async def test_update_status_if_changed_success(self, ib_order_repo: IBOrderRepository):
        """Test atomic status update when expected status matches."""
        await ib_order_repo.create_order(
            composite_order_id="IB-7001:7002",
            entry_order_id=7001,
            stop_order_id=7002,
            symbol="GOOGL",
            quantity=15,
            stop_price=Decimal("150.00"),
            status=IBOrderStatus.PENDING,
        )

        # Update should succeed - expected status matches
        updated = await ib_order_repo.update_status_if_changed(
            "IB-7001:7002",
            IBOrderStatus.PENDING.value,
            IBOrderStatus.FILLED,
        )

        assert updated is True

        # Verify the status was updated
        order = await ib_order_repo.get_by_composite_id("IB-7001:7002")
        assert order.status == IBOrderStatus.FILLED.value

    @pytest.mark.asyncio
    async def test_update_status_if_changed_wrong_status(self, ib_order_repo: IBOrderRepository):
        """Test atomic status update fails when expected status doesn't match."""
        await ib_order_repo.create_order(
            composite_order_id="IB-7003:7004",
            entry_order_id=7003,
            stop_order_id=7004,
            symbol="META",
            quantity=20,
            stop_price=Decimal("300.00"),
            status=IBOrderStatus.FILLED,  # Already filled
        )

        # Update should fail - expected PENDING but actual is FILLED
        updated = await ib_order_repo.update_status_if_changed(
            "IB-7003:7004",
            IBOrderStatus.PENDING.value,  # Wrong expected status
            IBOrderStatus.CANCELLED,
        )

        assert updated is False

        # Verify the status was NOT updated
        order = await ib_order_repo.get_by_composite_id("IB-7003:7004")
        assert order.status == IBOrderStatus.FILLED.value  # Still FILLED

    @pytest.mark.asyncio
    async def test_update_status_if_changed_not_found(self, ib_order_repo: IBOrderRepository):
        """Test atomic status update returns False for non-existent order."""
        updated = await ib_order_repo.update_status_if_changed(
            "IB-9999:9998",
            IBOrderStatus.PENDING.value,
            IBOrderStatus.FILLED,
        )

        assert updated is False
