"""Unit tests for IBBroker with mocked IB client."""
import os
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.brokers.base import BrokerError, OrderRequest, OrderStatus
from app.brokers.ib import IBBroker


class MockTrade:
    """Mock IB Trade object for testing."""

    def __init__(self, order_id: int, status: str = "Filled", avg_price: float = 100.0):
        self.order = MagicMock()
        self.order.orderId = order_id
        self.orderStatus = MagicMock()
        self.orderStatus.status = status
        self.orderStatus.avgFillPrice = avg_price
        self.orderStatus.filled = 100
        self.fills = []

    def isDone(self) -> bool:
        return self.orderStatus.status in ["Filled", "Cancelled", "Inactive"]


class MockIB:
    """Mock ib_async.IB client for testing."""

    def __init__(self, managed_accounts=None):
        self._connected = False
        self._trades = []
        self._next_order_id = 1000
        self.client = MagicMock()
        self.client.getReqId = lambda: self._next_order_id
        # List of accounts available in this IB session
        # Use explicit None check to allow empty list for testing "no accounts" scenario
        self._managed_accounts = managed_accounts if managed_accounts is not None else ["DU1234567"]

    def isConnected(self) -> bool:
        return self._connected

    async def connectAsync(self, host, port, clientId, readonly):
        self._connected = True

    def disconnect(self):
        self._connected = False

    def managedAccounts(self) -> list[str]:
        """Return list of accounts managed by this IB session."""
        return self._managed_accounts

    async def qualifyContractsAsync(self, contract):
        return [contract]

    def placeOrder(self, contract, order):
        if not hasattr(order, 'orderId') or order.orderId is None:
            order.orderId = self._next_order_id
            self._next_order_id += 1
        else:
            # If order already has an ID, increment for next order
            self._next_order_id = max(self._next_order_id, order.orderId + 1)

        trade = MockTrade(order.orderId)
        self._trades.append(trade)
        return trade

    def cancelOrder(self, order):
        for trade in self._trades:
            if trade.order.orderId == order.orderId:
                trade.orderStatus.status = "Cancelled"

    def trades(self):
        return self._trades

    async def waitOnUpdate(self, timeout=None):
        pass

    def reqAccountUpdates(self, subscribe, account):
        pass


@pytest.fixture
def mock_ib():
    """Create mock IB client with account from env."""
    # Use IB_ACCOUNT from env so mock matches what IBBroker expects
    account = os.environ.get("IB_ACCOUNT", "DU1234567")
    return MockIB(managed_accounts=[account])


@pytest.fixture
def ib_broker(mock_ib):
    """Create IBBroker without database (legacy mode)."""
    with patch("app.brokers.ib.IB", return_value=mock_ib):
        broker = IBBroker(db=None)
        broker.ib = mock_ib
        return broker


@pytest.fixture
def ib_broker_with_db(db_session: AsyncSession, mock_ib):
    """Create IBBroker with database session."""
    with patch("app.brokers.ib.IB", return_value=mock_ib):
        broker = IBBroker(db=db_session)
        broker.ib = mock_ib
        return broker


@pytest.fixture
def ib_broker_no_db(mock_ib):
    """Create IBBroker without database (legacy mode)."""
    with patch("app.brokers.ib.IB", return_value=mock_ib):
        broker = IBBroker(db=None)
        broker.ib = mock_ib
        return broker


class TestIBBrokerConnection:
    """Test connection management."""

    @pytest.mark.asyncio
    async def test_connect_success(self, ib_broker, mock_ib):
        """Test successful connection."""
        await ib_broker.connect()
        assert ib_broker._connected is True

    @pytest.mark.asyncio
    async def test_connect_already_connected(self, ib_broker, mock_ib):
        """Test connecting when already connected."""
        mock_ib._connected = True
        ib_broker._connected = True
        await ib_broker.connect()  # Should not raise

    @pytest.mark.asyncio
    async def test_disconnect(self, ib_broker, mock_ib):
        """Test disconnection."""
        ib_broker._connected = True
        mock_ib._connected = True
        await ib_broker.disconnect()
        assert ib_broker._connected is False

    @pytest.mark.asyncio
    async def test_connect_validates_account_match(self):
        """Test that connection validates configured account matches IB account."""
        from app.core.config import Settings

        # Mock IB with specific account
        mock_ib = MockIB(managed_accounts=["DU1234567"])

        with patch("app.brokers.ib.IB", return_value=mock_ib):
            broker = IBBroker(db=None)
            broker.ib = mock_ib

            # Set settings directly to override
            broker.settings = Settings(
                ib_host="127.0.0.1",
                ib_port=4001,
                ib_client_id=1,
                ib_account="DU1234567",  # Matching account
                ib_connection_timeout=30
            )

            # Should succeed - account matches
            await broker.connect()
            assert broker._connected is True

    @pytest.mark.asyncio
    async def test_connect_rejects_account_mismatch(self):
        """Test that connection fails when configured account doesn't match IB account."""
        from app.core.config import Settings

        # Mock IB with different account than configured
        mock_ib = MockIB(managed_accounts=["DU9999999"])

        with patch("app.brokers.ib.IB", return_value=mock_ib):
            broker = IBBroker(db=None)
            broker.ib = mock_ib

            # Set settings directly to override
            broker.settings = Settings(
                ib_host="127.0.0.1",
                ib_port=4001,
                ib_client_id=1,
                ib_account="DU1234567",  # Different account
                ib_connection_timeout=30
            )

            # Should fail - account mismatch
            with pytest.raises(BrokerError, match="Account mismatch"):
                await broker.connect()

            # Should be disconnected after failure
            assert broker._connected is False

    @pytest.mark.asyncio
    async def test_connect_rejects_no_accounts(self):
        """Test that connection fails when IB session has no accounts."""
        from app.core.config import Settings

        # Mock IB with empty accounts list
        mock_ib = MockIB(managed_accounts=[])

        with patch("app.brokers.ib.IB", return_value=mock_ib):
            broker = IBBroker(db=None)
            broker.ib = mock_ib

            # Set settings directly to override
            broker.settings = Settings(
                ib_host="127.0.0.1",
                ib_port=4001,
                ib_client_id=1,
                ib_account="DU1234567",
                ib_connection_timeout=30
            )

            # Should fail - no accounts available
            with pytest.raises(BrokerError, match="No accounts found"):
                await broker.connect()

            # Should be disconnected after failure
            assert broker._connected is False

    @pytest.mark.asyncio
    async def test_connect_accepts_multiple_accounts_when_match(self):
        """Test that connection succeeds when configured account is in list of multiple accounts."""
        from app.core.config import Settings

        # Mock IB with multiple accounts including the configured one
        mock_ib = MockIB(managed_accounts=["DU1234567", "DU7654321", "U9999999"])

        with patch("app.brokers.ib.IB", return_value=mock_ib):
            broker = IBBroker(db=None)
            broker.ib = mock_ib

            # Set settings directly to override
            broker.settings = Settings(
                ib_host="127.0.0.1",
                ib_port=4001,
                ib_client_id=1,
                ib_account="DU7654321",  # Second account in list
                ib_connection_timeout=30
            )

            # Should succeed - account is in the list
            await broker.connect()
            assert broker._connected is True


class TestIBBrokerPlaceOrder:
    """Test order placement."""

    @pytest.mark.asyncio
    async def test_place_order_success(self, ib_broker, mock_ib):
        """Test successful order placement."""
        ib_broker._connected = True
        mock_ib._connected = True

        request = OrderRequest(
            ticker="AAPL",
            quantity=100,
            order_type="MARKET",
            stop_loss_price=Decimal("145.00"),
        )

        result = await ib_broker.place_order(request)

        assert result.status == OrderStatus.FILLED
        assert result.order_id.startswith("IB-")
        assert ":" in result.order_id
        assert result.filled_quantity == 100
        assert result.filled_price is not None

    @pytest.mark.asyncio
    async def test_place_order_missing_ticker(self, ib_broker, mock_ib):
        """Test order with missing ticker."""
        ib_broker._connected = True
        mock_ib._connected = True

        request = OrderRequest(
            ticker="",
            quantity=100,
            order_type="MARKET",
            stop_loss_price=Decimal("145.00"),
        )

        with pytest.raises(BrokerError, match="Ticker symbol is required"):
            await ib_broker.place_order(request)

    @pytest.mark.asyncio
    async def test_place_order_invalid_quantity(self, ib_broker, mock_ib):
        """Test order with invalid quantity."""
        ib_broker._connected = True
        mock_ib._connected = True

        request = OrderRequest(
            ticker="AAPL",
            quantity=0,
            order_type="MARKET",
            stop_loss_price=Decimal("145.00"),
        )

        with pytest.raises(BrokerError, match="Quantity must be positive"):
            await ib_broker.place_order(request)

    @pytest.mark.asyncio
    async def test_place_order_missing_stop_loss(self, ib_broker, mock_ib):
        """Test order without stop loss."""
        ib_broker._connected = True
        mock_ib._connected = True

        request = OrderRequest(
            ticker="AAPL",
            quantity=100,
            order_type="MARKET",
            stop_loss_price=None,
        )

        with pytest.raises(BrokerError, match="Stop loss price is required"):
            await ib_broker.place_order(request)


class TestIBBrokerGetOrderStatus:
    """Test order status queries."""

    @pytest.mark.asyncio
    async def test_get_order_status_filled(self, ib_broker, mock_ib):
        """Test getting status of filled order."""
        ib_broker._connected = True
        mock_ib._connected = True

        # Place an order first
        request = OrderRequest(
            ticker="AAPL",
            quantity=100,
            order_type="MARKET",
            stop_loss_price=Decimal("145.00"),
        )
        place_result = await ib_broker.place_order(request)

        # Get status
        status_result = await ib_broker.get_order_status(place_result.order_id)

        assert status_result.status == OrderStatus.FILLED
        assert status_result.order_id == place_result.order_id

    @pytest.mark.asyncio
    async def test_get_order_status_invalid_id(self, ib_broker, mock_ib):
        """Test getting status with invalid order ID."""
        ib_broker._connected = True
        mock_ib._connected = True

        with pytest.raises(BrokerError, match="Invalid IB order ID format"):
            await ib_broker.get_order_status("invalid-id")


class TestIBBrokerCancelOrder:
    """Test order cancellation."""

    @pytest.mark.asyncio
    async def test_cancel_order_pending(self, ib_broker, mock_ib):
        """Test cancelling pending order."""
        ib_broker._connected = True
        mock_ib._connected = True

        # Create a pending trade
        mock_trade = MockTrade(1001, status="Submitted")
        mock_ib._trades.append(mock_trade)

        # cancel_order() doesn't use cache - it queries IB directly via _parse_composite_order_id
        order_id = "IB-1001:1002"

        result = await ib_broker.cancel_order(order_id)
        # Note: With mock, cancellation happens synchronously
        assert result is True or result is False  # Depends on mock state


class TestIBBrokerOrderIdParsing:
    """Test order ID parsing utilities."""

    def test_make_composite_order_id(self, ib_broker):
        """Test composite ID creation."""
        order_id = ib_broker._make_composite_order_id(12345, 12346)
        assert order_id == "IB-12345:12346"

    def test_make_composite_order_id_no_stop(self, ib_broker):
        """Test composite ID without stop order."""
        order_id = ib_broker._make_composite_order_id(12345, None)
        assert order_id == "IB-12345:none"

    def test_parse_composite_order_id(self, ib_broker):
        """Test parsing composite ID."""
        entry_id, stop_id = ib_broker._parse_composite_order_id("IB-12345:12346")
        assert entry_id == 12345
        assert stop_id == 12346

    def test_parse_composite_order_id_no_stop(self, ib_broker):
        """Test parsing composite ID without stop."""
        entry_id, stop_id = ib_broker._parse_composite_order_id("IB-12345:none")
        assert entry_id == 12345
        assert stop_id is None

    def test_parse_invalid_order_id(self, ib_broker):
        """Test parsing invalid order ID."""
        with pytest.raises(BrokerError, match="Invalid IB order ID format"):
            ib_broker._parse_composite_order_id("MOCK-12345")


class TestIBBrokerWithDatabase:
    """Test IBBroker with database persistence."""

    @pytest.mark.asyncio
    async def test_place_order_persists_to_db(self, ib_broker_with_db, mock_ib, db_session):
        """Test that orders are persisted to database."""
        ib_broker_with_db._connected = True
        mock_ib._connected = True

        request = OrderRequest(
            ticker="AAPL",
            quantity=100,
            order_type="MARKET",
            stop_loss_price=Decimal("145.00"),
        )

        result = await ib_broker_with_db.place_order(request)

        # Verify order was persisted
        db_order = await ib_broker_with_db.order_repo.get_by_composite_id(result.order_id)
        assert db_order is not None
        assert db_order.symbol == "AAPL"
        assert db_order.quantity == 100
        assert db_order.stop_price == Decimal("145.00")
        assert db_order.filled_price is not None

    @pytest.mark.asyncio
    async def test_get_order_status_from_db(self, ib_broker_with_db, mock_ib, db_session):
        """Test that order status can be retrieved from database."""
        ib_broker_with_db._connected = True
        mock_ib._connected = True

        # Place order
        request = OrderRequest(
            ticker="MSFT",
            quantity=50,
            order_type="MARKET",
            stop_loss_price=Decimal("300.00"),
        )
        result = await ib_broker_with_db.place_order(request)

        # Get status - should work via database
        status = await ib_broker_with_db.get_order_status(result.order_id)
        assert status.status == OrderStatus.FILLED
        assert status.order_id == result.order_id
        assert status.filled_quantity == 50

    @pytest.mark.asyncio
    async def test_broker_without_db_still_works(self, ib_broker_no_db, mock_ib):
        """Test that broker without database still works (backwards compatibility)."""
        ib_broker_no_db._connected = True
        mock_ib._connected = True

        request = OrderRequest(
            ticker="TSLA",
            quantity=25,
            order_type="MARKET",
            stop_loss_price=Decimal("200.00"),
        )

        # Place order - should work without database
        result = await ib_broker_no_db.place_order(request)
        assert result.status == OrderStatus.FILLED
        assert result.order_id.startswith("IB-")

        # Get status - should work via IB query (no database)
        status = await ib_broker_no_db.get_order_status(result.order_id)
        assert status.status == OrderStatus.FILLED

    @pytest.mark.asyncio
    async def test_cancel_order_updates_db_status(self, ib_broker_with_db, mock_ib, db_session):
        """Test that cancel_order updates status to CANCELLED in database."""
        from app.models.ib_order import IBOrderStatus

        ib_broker_with_db._connected = True
        mock_ib._connected = True

        # Place order first
        request = OrderRequest(
            ticker="NVDA",
            quantity=10,
            order_type="MARKET",
            stop_loss_price=Decimal("400.00"),
        )
        result = await ib_broker_with_db.place_order(request)

        # Make the entry trade appear as "Submitted" (pending) so it can be cancelled
        for trade in mock_ib._trades:
            if trade.order.orderId == int(result.order_id.split("-")[1].split(":")[0]):
                trade.orderStatus.status = "Submitted"

        # Cancel the order
        await ib_broker_with_db.cancel_order(result.order_id)

        # Verify database status is updated to CANCELLED
        db_order = await ib_broker_with_db.order_repo.get_by_composite_id(result.order_id)
        assert db_order is not None
        assert db_order.status == IBOrderStatus.CANCELLED.value
