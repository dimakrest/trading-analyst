"""Integration tests for account status API against real IB broker.

These tests verify the account status feature works correctly with a real
Interactive Brokers TWS/Gateway connection. They test:
- API endpoint responses with real broker data
- AccountService integration with IBBroker and IBDataProvider
- Account type detection with real account IDs
- Connection error handling
- Data serialization of Decimal values

IMPORTANT: These tests require TWS/Gateway running on port 4002 (paper trading).
They are skipped by default - remove the skip marker to run manually.

Safety: Only query operations are performed. No orders are placed.
"""
import logging
from decimal import Decimal

import pytest
from httpx import AsyncClient

from app.brokers.ib import IBBroker
from app.core.config import get_settings
from app.main import app
from app.providers.ib_data import IBDataProvider
from app.schemas.account import AccountType
from app.schemas.account import ConnectionStatus
from app.services.account_service import AccountService

logger = logging.getLogger(__name__)


@pytest.fixture
async def ib_broker():
    """Create and connect IBBroker for integration tests.

    This fixture establishes a real connection to TWS/Gateway and
    ensures proper cleanup after tests complete.

    Yields:
        IBBroker: Connected broker instance (port 4002 - paper trading)
    """
    broker = IBBroker(db=None)  # No DB session needed for status queries
    await broker.connect()
    yield broker
    await broker.disconnect()


@pytest.fixture
async def ib_data_provider():
    """Create and connect IBDataProvider for integration tests.

    This fixture establishes a real connection to IB Gateway for data provider
    and ensures proper cleanup after tests complete.

    Yields:
        IBDataProvider: Connected data provider instance
    """
    provider = IBDataProvider()
    await provider.connect()
    yield provider
    await provider.disconnect()


@pytest.fixture
def account_service(ib_broker, ib_data_provider):
    """Create AccountService with real IB connections.

    Args:
        ib_broker: Connected IBBroker instance
        ib_data_provider: Connected IBDataProvider instance

    Returns:
        AccountService: Service with real broker and data provider
    """
    return AccountService(broker=ib_broker, data_provider=ib_data_provider)


@pytest.mark.skip(reason="Requires TWS/Gateway running - run manually")
class TestAccountStatusIntegration:
    """Integration tests for account status API against real IB broker.

    These tests connect to a real Interactive Brokers paper trading account
    and verify the account status API works correctly with real data.

    Prerequisites:
    - TWS/Gateway running on port 4002 (paper trading)
    - API connections enabled in TWS/Gateway settings
    - Valid paper trading account

    To run manually:
    1. Start TWS/Gateway on port 4002
    2. Remove @pytest.mark.skip decorator
    3. Run: docker exec trading_analyst_4_dev-backend-dev-1 pytest tests/integration/test_account_status_integration.py -v -x
    4. Restore @pytest.mark.skip decorator
    """

    @pytest.mark.asyncio
    async def test_get_broker_status_with_real_connection(self, account_service):
        """Test get_broker_status() with real IBBroker connection.

        Verifies:
        - Connection status is CONNECTED
        - Account ID is populated and matches IB format
        - Account type is correctly detected (PAPER for demo accounts)
        - Financial data is retrieved (net_liquidation, buying_power)
        - P&L data is retrieved (unrealized, realized, daily)
        - Decimal values are properly returned
        - No error message is present

        Args:
            account_service: Service with real IB broker connection
        """
        # Act: Get broker status from real connection
        result = await account_service.get_broker_status()

        # Assert: Basic connection info
        assert result.connection_status == ConnectionStatus.CONNECTED
        assert result.error_message is None

        # Assert: Account information
        assert result.account_id is not None
        assert len(result.account_id) > 0
        logger.info(f"Account ID: {result.account_id}")

        # Assert: Account type detection
        assert result.account_type is not None
        # Paper accounts typically start with 'D'
        if result.account_id.startswith('D'):
            assert result.account_type == AccountType.PAPER
        elif result.account_id.startswith('U'):
            assert result.account_type == AccountType.LIVE
        else:
            # Unknown format - still valid but log warning
            logger.warning(f"Unknown account ID format: {result.account_id}")

        # Assert: Financial data is retrieved
        assert result.net_liquidation is not None
        assert isinstance(result.net_liquidation, Decimal)
        assert result.net_liquidation > 0
        logger.info(f"Net Liquidation: {result.net_liquidation}")

        assert result.buying_power is not None
        assert isinstance(result.buying_power, Decimal)
        assert result.buying_power > 0
        logger.info(f"Buying Power: {result.buying_power}")

        # Assert: P&L data may be None if no positions/trades
        # Just verify they are Decimal or None
        if result.unrealized_pnl is not None:
            assert isinstance(result.unrealized_pnl, Decimal)
            logger.info(f"Unrealized P&L: {result.unrealized_pnl}")

        if result.realized_pnl is not None:
            assert isinstance(result.realized_pnl, Decimal)
            logger.info(f"Realized P&L: {result.realized_pnl}")

        if result.daily_pnl is not None:
            assert isinstance(result.daily_pnl, Decimal)
            logger.info(f"Daily P&L: {result.daily_pnl}")

    @pytest.mark.asyncio
    async def test_get_data_provider_status_with_real_connection(self, account_service):
        """Test get_data_provider_status() with real IBDataProvider connection.

        Verifies:
        - Connection status is CONNECTED
        - No error message is present
        - Data provider is successfully connected to IB Gateway

        Args:
            account_service: Service with real IB data provider connection
        """
        # Act: Get data provider status from real connection
        result = await account_service.get_data_provider_status()

        # Assert: Connection is established
        assert result.connection_status == ConnectionStatus.CONNECTED
        assert result.error_message is None

    @pytest.mark.asyncio
    async def test_get_system_status_with_real_connections(self, account_service):
        """Test get_system_status() with real broker and data provider.

        Verifies:
        - Both broker and data provider statuses are returned
        - Broker connection is CONNECTED with full account data
        - Data provider connection is CONNECTED
        - Response structure matches SystemStatusResponse schema

        Args:
            account_service: Service with real IB connections
        """
        # Act: Get combined system status
        result = await account_service.get_system_status()

        # Assert: Response structure
        assert result.broker is not None
        assert result.data_provider is not None

        # Assert: Broker status
        assert result.broker.connection_status == ConnectionStatus.CONNECTED
        assert result.broker.account_id is not None
        assert result.broker.account_type is not None
        assert result.broker.net_liquidation is not None
        assert result.broker.buying_power is not None

        # Assert: Data provider status
        assert result.data_provider.connection_status == ConnectionStatus.CONNECTED
        assert result.data_provider.error_message is None

    @pytest.mark.asyncio
    async def test_api_endpoint_with_real_broker(self):
        """Test GET /api/v1/account/status endpoint with real IB broker.

        This is an end-to-end test of the API endpoint against a real
        Interactive Brokers connection. It verifies:
        - Endpoint returns 200 OK
        - Response matches SystemStatusResponse schema
        - Broker connection status is CONNECTED
        - Account data is populated with real values
        - Data provider status is CONNECTED
        - Decimal values are properly serialized to JSON strings

        NOTE: This test directly connects to IB without FastAPI dependency
        overrides, so it uses the real IBBroker singleton.
        """
        settings = get_settings()

        # Verify we're configured for IB broker
        assert settings.broker_type == "ib", "broker_type must be 'ib' for this test"

        # Create async client for API testing
        async with AsyncClient(app=app, base_url="http://testserver") as client:
            # Act: Call the API endpoint
            response = await client.get("/api/v1/account/status")

            # Assert: HTTP response
            assert response.status_code == 200
            data = response.json()

            # Assert: Response structure
            assert "broker" in data
            assert "data_provider" in data

            # Assert: Broker status
            broker = data["broker"]
            assert broker["connection_status"] == "CONNECTED"
            assert broker["error_message"] is None
            assert broker["account_id"] is not None
            assert broker["account_type"] is not None

            # Assert: Financial data is present
            assert broker["net_liquidation"] is not None
            assert broker["buying_power"] is not None

            # Assert: Decimal serialization (JSON strings)
            # Verify they can be parsed back to Decimal
            net_liq = Decimal(broker["net_liquidation"])
            assert net_liq > 0

            buying_power = Decimal(broker["buying_power"])
            assert buying_power > 0

            # Assert: P&L fields (may be null)
            assert "unrealized_pnl" in broker
            assert "realized_pnl" in broker
            assert "daily_pnl" in broker

            # Assert: Data provider status
            data_provider = data["data_provider"]
            assert data_provider["connection_status"] == "CONNECTED"
            assert data_provider["error_message"] is None

            logger.info(f"API response: {data}")

    @pytest.mark.asyncio
    async def test_account_type_detection_with_real_account(self, account_service):
        """Test account type detection with real IB account ID.

        Verifies:
        - Paper accounts starting with 'D' are detected as PAPER
        - Live accounts starting with 'U' are detected as LIVE
        - Account type matches real account configuration

        Args:
            account_service: Service with real IB broker connection
        """
        # Act: Get broker status to retrieve real account ID
        result = await account_service.get_broker_status()

        # Assert: Account ID and type are set
        assert result.account_id is not None
        assert result.account_type is not None

        # Assert: Account type detection logic
        account_id = result.account_id
        account_type = result.account_type

        if account_id.startswith('D'):
            # Demo/Paper account
            assert account_type == AccountType.PAPER
            logger.info(f"Detected paper account: {account_id}")
        elif account_id.startswith('U'):
            # Live account
            assert account_type == AccountType.LIVE
            logger.info(f"Detected live account: {account_id}")
        else:
            # Unknown format
            assert account_type == AccountType.UNKNOWN
            logger.warning(f"Unknown account format: {account_id}")

    @pytest.mark.asyncio
    async def test_disconnected_broker_error_handling(self):
        """Test error handling when broker is not connected.

        Verifies:
        - Connection status is DISCONNECTED when not connected
        - Error message is populated
        - No account data is returned
        - Service handles disconnection gracefully
        """
        # Arrange: Create broker without connecting
        broker = IBBroker(db=None)
        # Note: We intentionally DON'T call await broker.connect()

        service = AccountService(broker=broker, data_provider=None)

        # Act: Try to get status from disconnected broker
        result = await service.get_broker_status()

        # Assert: Disconnected status
        assert result.connection_status == ConnectionStatus.DISCONNECTED
        assert result.error_message is not None
        assert "Not connected" in result.error_message or "not connected" in result.error_message.lower()

        # Assert: No account data when disconnected
        assert result.account_id is None
        assert result.account_type is None
        assert result.net_liquidation is None
        assert result.buying_power is None
        assert result.unrealized_pnl is None
        assert result.realized_pnl is None
        assert result.daily_pnl is None

    @pytest.mark.asyncio
    async def test_disconnected_data_provider_error_handling(self):
        """Test error handling when data provider is not connected.

        Verifies:
        - Connection status is DISCONNECTED when not connected
        - Error message is populated
        - Service handles disconnection gracefully
        """
        # Arrange: Create data provider without connecting
        provider = IBDataProvider()
        # Note: We intentionally DON'T call await provider.connect()

        service = AccountService(broker=None, data_provider=provider)

        # Act: Try to get status from disconnected provider
        result = await service.get_data_provider_status()

        # Assert: Disconnected status
        assert result.connection_status == ConnectionStatus.DISCONNECTED
        assert result.error_message is not None
        assert "not connected" in result.error_message.lower()

    @pytest.mark.asyncio
    async def test_none_broker_error_handling(self):
        """Test error handling when broker is None (not configured).

        Verifies:
        - Connection status is DISCONNECTED when broker is None
        - Error message indicates broker not configured
        - Service handles None broker gracefully
        """
        # Arrange: Create service with no broker
        service = AccountService(broker=None, data_provider=None)

        # Act: Get status with no broker configured
        result = await service.get_broker_status()

        # Assert: Disconnected with appropriate message
        assert result.connection_status == ConnectionStatus.DISCONNECTED
        assert result.error_message is not None
        assert "not configured" in result.error_message.lower()

    @pytest.mark.asyncio
    async def test_none_data_provider_error_handling(self):
        """Test error handling when data provider is None (not configured).

        Verifies:
        - Connection status is DISCONNECTED when provider is None
        - Error message indicates provider not configured
        - Service handles None provider gracefully
        """
        # Arrange: Create service with no data provider
        service = AccountService(broker=None, data_provider=None)

        # Act: Get status with no data provider configured
        result = await service.get_data_provider_status()

        # Assert: Disconnected with appropriate message
        assert result.connection_status == ConnectionStatus.DISCONNECTED
        assert result.error_message is not None
        assert "not configured" in result.error_message.lower()

    @pytest.mark.asyncio
    async def test_account_values_extraction(self, account_service):
        """Test extraction of specific account values from real IB data.

        Verifies:
        - Net Liquidation is extracted correctly
        - Buying Power is extracted correctly
        - Values are positive Decimals
        - USD currency is used for filtering

        Args:
            account_service: Service with real IB broker connection
        """
        # Act: Get broker status (triggers account values fetch)
        result = await account_service.get_broker_status()

        # Assert: Core account values are extracted
        assert result.net_liquidation is not None
        assert result.buying_power is not None

        # Assert: Values are reasonable (positive)
        assert result.net_liquidation > 0
        assert result.buying_power > 0

        # Assert: Buying power is typically >= net liquidation for margin accounts
        # (Can be 2x for RegT margin accounts)
        assert result.buying_power >= result.net_liquidation

    @pytest.mark.asyncio
    async def test_pnl_data_extraction(self, account_service):
        """Test extraction of P&L data from real IB broker.

        Verifies:
        - P&L values are Decimal or None (depending on positions)
        - NaN values from IB are properly handled (converted to None)
        - Data types are correct

        NOTE: P&L values may be None if account has no positions or trades.

        Args:
            account_service: Service with real IB broker connection
        """
        # Act: Get broker status (triggers P&L fetch)
        result = await account_service.get_broker_status()

        # Assert: P&L fields exist (may be None)
        assert hasattr(result, "unrealized_pnl")
        assert hasattr(result, "realized_pnl")
        assert hasattr(result, "daily_pnl")

        # Assert: If P&L values are present, they are Decimal
        if result.unrealized_pnl is not None:
            assert isinstance(result.unrealized_pnl, Decimal)

        if result.realized_pnl is not None:
            assert isinstance(result.realized_pnl, Decimal)

        if result.daily_pnl is not None:
            assert isinstance(result.daily_pnl, Decimal)

    @pytest.mark.asyncio
    async def test_account_status_json_serialization_format(self):
        """Verify Decimal fields serialize to string format for frontend.

        Pydantic serializes Decimal fields as strings by default, which is
        the expected format for frontend JavaScript consumption. This test
        documents and verifies this critical contract between backend and frontend.

        Frontend expects:
        - Decimal values as strings with decimal points (e.g., "25000.00")
        - Not as numbers (which would lose precision)
        - Valid Decimal format that can be parsed back

        This test uses the real API endpoint to verify end-to-end serialization.
        """
        settings = get_settings()

        # Verify we're configured for IB broker
        assert settings.broker_type == "ib", "broker_type must be 'ib' for this test"

        # Create async client for API testing
        async with AsyncClient(app=app, base_url="http://testserver") as client:
            # Act: Call the API endpoint
            response = await client.get("/api/v1/account/status")

            # Assert: HTTP response
            assert response.status_code == 200
            data = response.json()

            # Assert: Response structure
            assert "broker" in data
            broker = data["broker"]

            # Verify Decimal fields are serialized as strings with decimal point
            if broker["net_liquidation"] is not None:
                assert isinstance(broker["net_liquidation"], str), (
                    f"net_liquidation should be string, got {type(broker['net_liquidation'])}"
                )
                assert "." in broker["net_liquidation"], (
                    "net_liquidation should contain decimal point"
                )
                # Verify it's a valid decimal string
                net_liq = Decimal(broker["net_liquidation"])
                assert net_liq > 0

            if broker["buying_power"] is not None:
                assert isinstance(broker["buying_power"], str), (
                    f"buying_power should be string, got {type(broker['buying_power'])}"
                )
                assert "." in broker["buying_power"], (
                    "buying_power should contain decimal point"
                )
                # Verify it's a valid decimal string
                buying_power = Decimal(broker["buying_power"])
                assert buying_power > 0

            # Verify P&L fields (if present) are also strings
            if broker["unrealized_pnl"] is not None:
                assert isinstance(broker["unrealized_pnl"], str), (
                    f"unrealized_pnl should be string, got {type(broker['unrealized_pnl'])}"
                )
                assert "." in broker["unrealized_pnl"]
                Decimal(broker["unrealized_pnl"])  # Should not raise

            if broker["realized_pnl"] is not None:
                assert isinstance(broker["realized_pnl"], str), (
                    f"realized_pnl should be string, got {type(broker['realized_pnl'])}"
                )
                assert "." in broker["realized_pnl"]
                Decimal(broker["realized_pnl"])  # Should not raise

            if broker["daily_pnl"] is not None:
                assert isinstance(broker["daily_pnl"], str), (
                    f"daily_pnl should be string, got {type(broker['daily_pnl'])}"
                )
                assert "." in broker["daily_pnl"]
                Decimal(broker["daily_pnl"])  # Should not raise

            logger.info("Decimal JSON serialization verified: all fields are strings with decimal points")

    @pytest.mark.asyncio
    async def test_concurrent_status_queries(self, ib_broker, ib_data_provider):
        """Test concurrent status queries to verify thread safety.

        Verifies:
        - Multiple concurrent queries succeed
        - Results are consistent across queries
        - No race conditions or connection issues
        - Singleton connections handle concurrent access

        Args:
            ib_broker: Connected IBBroker instance
            ib_data_provider: Connected IBDataProvider instance
        """
        import asyncio

        # Arrange: Create service
        service = AccountService(broker=ib_broker, data_provider=ib_data_provider)

        # Act: Make 5 concurrent status queries
        tasks = [service.get_system_status() for _ in range(5)]
        results = await asyncio.gather(*tasks)

        # Assert: All queries succeeded
        assert len(results) == 5

        # Assert: Results are consistent
        first_result = results[0]
        for result in results[1:]:
            # Broker status should be consistent
            assert result.broker.connection_status == first_result.broker.connection_status
            assert result.broker.account_id == first_result.broker.account_id
            assert result.broker.account_type == first_result.broker.account_type

            # Data provider status should be consistent
            assert result.data_provider.connection_status == first_result.data_provider.connection_status

            # Financial values should be identical (same moment in time)
            assert result.broker.net_liquidation == first_result.broker.net_liquidation
            assert result.broker.buying_power == first_result.broker.buying_power
