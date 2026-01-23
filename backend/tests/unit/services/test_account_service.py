"""Unit tests for account service.

Tests account service's ability to fetch broker and data provider status,
handle connection states, and parse account information from IB connections.
Uses mocks to avoid real API calls and ensure deterministic test behavior.
"""
import math
from decimal import Decimal
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest

from app.schemas.account import AccountType
from app.schemas.account import ConnectionStatus
from app.services.account_service import AccountService


class MockAccountValue:
    """Mock IB AccountValue."""

    def __init__(self, account, tag, value, currency, model_code=""):
        self.account = account
        self.tag = tag
        self.value = value
        self.currency = currency
        self.modelCode = model_code


class MockPnL:
    """Mock IB PnL."""

    def __init__(self, unrealized=100.0, realized=50.0, daily=150.0):
        self.account = "DU1234567"
        self.modelCode = ""
        self.unrealizedPnL = unrealized
        self.realizedPnL = realized
        self.dailyPnL = daily


class TestAccountTypeDetection:
    """Test account type detection from ID prefix."""

    def test_paper_account_detected(self):
        """Paper accounts start with D."""
        service = AccountService(broker=None, data_provider=None)

        assert service._determine_account_type("DU1234567") == AccountType.PAPER
        assert service._determine_account_type("DF9876543") == AccountType.PAPER

    def test_live_account_detected(self):
        """Live accounts start with U."""
        service = AccountService(broker=None, data_provider=None)

        assert service._determine_account_type("U1234567") == AccountType.LIVE
        assert service._determine_account_type("U9876543") == AccountType.LIVE

    def test_unknown_account_type(self):
        """Unknown prefix returns UNKNOWN."""
        service = AccountService(broker=None, data_provider=None)

        assert service._determine_account_type("X1234567") == AccountType.UNKNOWN
        assert service._determine_account_type("") == AccountType.UNKNOWN
        assert service._determine_account_type(None) == AccountType.UNKNOWN


class TestGetBrokerStatus:
    """Test broker status retrieval."""

    @pytest.mark.asyncio
    async def test_no_broker_returns_error(self):
        """When broker is None, return error status."""
        service = AccountService(broker=None, data_provider=None)
        result = await service.get_broker_status()

        assert result.connection_status == ConnectionStatus.DISCONNECTED
        assert result.error_message == "Broker not configured"
        assert result.account_id is None

    @pytest.mark.asyncio
    async def test_disconnected_returns_error(self):
        """When broker IB is disconnected, return error status."""
        mock_broker = MagicMock()
        mock_broker.ib.isConnected.return_value = False

        service = AccountService(broker=mock_broker, data_provider=None)
        result = await service.get_broker_status()

        assert result.connection_status == ConnectionStatus.DISCONNECTED
        assert result.error_message is not None
        assert result.account_id is None

    @pytest.mark.asyncio
    async def test_connected_returns_account_data(self):
        """When connected with configured account, return account data."""
        mock_broker = MagicMock()
        mock_broker.ib.isConnected.return_value = True
        mock_broker.ib.accountValues.return_value = [
            MockAccountValue("DU1234567", "NetLiquidation", "25000.00", "USD"),
            MockAccountValue("DU1234567", "BuyingPower", "50000.00", "USD"),
        ]
        mock_broker.ib.pnl.return_value = [MockPnL()]

        with patch("app.services.account_service.get_settings") as mock_settings:
            mock_settings.return_value.ib_account = "DU1234567"
            service = AccountService(broker=mock_broker, data_provider=None)
            result = await service.get_broker_status()

        assert result.connection_status == ConnectionStatus.CONNECTED
        assert result.account_id == "DU1234567"
        assert result.account_type == AccountType.PAPER
        assert result.net_liquidation == Decimal("25000.00")
        assert result.buying_power == Decimal("50000.00")
        assert result.unrealized_pnl == Decimal("100.0")
        assert result.realized_pnl == Decimal("50.0")

    @pytest.mark.asyncio
    async def test_no_account_configured_returns_error(self):
        """When IB_ACCOUNT not configured, return error for safety."""
        mock_broker = MagicMock()
        mock_broker.ib.isConnected.return_value = True

        with patch("app.services.account_service.get_settings") as mock_settings:
            mock_settings.return_value.ib_account = None
            service = AccountService(broker=mock_broker, data_provider=None)
            result = await service.get_broker_status()

        assert result.connection_status == ConnectionStatus.DISCONNECTED
        assert "IB_ACCOUNT not configured" in result.error_message

    @pytest.mark.asyncio
    async def test_uses_configured_account_when_provided(self):
        """When ib_account is configured, use that specific account."""
        mock_broker = MagicMock()
        mock_broker.ib.isConnected.return_value = True
        mock_broker.ib.accountValues.return_value = [
            MockAccountValue("DU2222222", "NetLiquidation", "30000.00", "USD"),
        ]
        mock_broker.ib.pnl.return_value = []

        with patch("app.services.account_service.get_settings") as mock_settings:
            mock_settings.return_value.ib_account = "DU2222222"
            service = AccountService(broker=mock_broker, data_provider=None)
            result = await service.get_broker_status()

        assert result.connection_status == ConnectionStatus.CONNECTED
        assert result.account_id == "DU2222222"
        # Verify accountValues was called with configured account
        mock_broker.ib.accountValues.assert_called_once_with("DU2222222")

    @pytest.mark.asyncio
    async def test_handles_nan_pnl_values(self):
        """When P&L values are NaN, return None instead of crashing."""
        mock_broker = MagicMock()
        mock_broker.ib.isConnected.return_value = True
        mock_broker.ib.accountValues.return_value = []
        mock_pnl = MockPnL(unrealized=float("nan"), realized=float("nan"), daily=float("nan"))
        mock_broker.ib.pnl.return_value = [mock_pnl]

        with patch("app.services.account_service.get_settings") as mock_settings:
            mock_settings.return_value.ib_account = "DU1234567"
            service = AccountService(broker=mock_broker, data_provider=None)
            result = await service.get_broker_status()

        assert result.connection_status == ConnectionStatus.CONNECTED
        assert result.unrealized_pnl is None
        assert result.realized_pnl is None
        assert result.daily_pnl is None

    @pytest.mark.asyncio
    async def test_exception_during_fetch_returns_error(self):
        """When exception occurs during fetch, return error status."""
        mock_broker = MagicMock()
        mock_broker.ib.isConnected.return_value = True
        mock_broker.ib.accountValues.side_effect = Exception("Connection lost")

        with patch("app.services.account_service.get_settings") as mock_settings:
            mock_settings.return_value.ib_account = "DU1234567"
            service = AccountService(broker=mock_broker, data_provider=None)
            result = await service.get_broker_status()

        assert result.connection_status == ConnectionStatus.DISCONNECTED
        assert "Connection lost" in result.error_message

    @pytest.mark.asyncio
    async def test_extracts_decimal_values_correctly(self):
        """Account values are extracted and converted to Decimal."""
        mock_broker = MagicMock()
        mock_broker.ib.isConnected.return_value = True
        mock_broker.ib.accountValues.return_value = [
            MockAccountValue("DU1234567", "NetLiquidation", "12345.67", "USD"),
            MockAccountValue("DU1234567", "BuyingPower", "24691.34", "USD"),
            MockAccountValue("DU1234567", "NetLiquidation", "10000.00", "EUR"),  # Different currency
        ]
        mock_broker.ib.pnl.return_value = []

        with patch("app.services.account_service.get_settings") as mock_settings:
            mock_settings.return_value.ib_account = "DU1234567"
            service = AccountService(broker=mock_broker, data_provider=None)
            result = await service.get_broker_status()

        assert result.net_liquidation == Decimal("12345.67")
        assert result.buying_power == Decimal("24691.34")
        assert isinstance(result.net_liquidation, Decimal)
        assert isinstance(result.buying_power, Decimal)

    @pytest.mark.asyncio
    async def test_handles_invalid_account_value_format(self):
        """Invalid account value format returns error.

        When Decimal conversion fails, exception handler returns DISCONNECTED status.
        """
        mock_broker = MagicMock()
        mock_broker.ib.isConnected.return_value = True
        mock_broker.ib.accountValues.return_value = [
            MockAccountValue("DU1234567", "NetLiquidation", "INVALID", "USD"),
        ]
        mock_broker.ib.pnl.return_value = []

        with patch("app.services.account_service.get_settings") as mock_settings:
            mock_settings.return_value.ib_account = "DU1234567"
            service = AccountService(broker=mock_broker, data_provider=None)
            result = await service.get_broker_status()

        assert result.connection_status == ConnectionStatus.DISCONNECTED
        assert result.error_message is not None

    @pytest.mark.asyncio
    async def test_handles_multiple_pnl_objects_gracefully(self):
        """Gracefully handles unexpected multiple P&L objects from IB Gateway.

        This is a critical data integrity check - when IB Gateway returns
        unexpected data structure, we log an error and return None P&L values
        rather than crashing. This allows the UI to display last known values
        or placeholders while maintaining system stability.
        """
        mock_broker = MagicMock()
        mock_broker.ib.isConnected.return_value = True
        mock_broker.ib.accountValues.return_value = [
            MockAccountValue("DU1234567", "NetLiquidation", "25000.00", "USD"),
        ]
        # Simulate unexpected IB Gateway response with multiple P&L objects
        mock_broker.ib.pnl.return_value = [
            MockPnL(unrealized=100.0, realized=50.0, daily=150.0),
            MockPnL(unrealized=200.0, realized=75.0, daily=275.0),  # Unexpected second object
        ]

        with patch("app.services.account_service.get_settings") as mock_settings:
            mock_settings.return_value.ib_account = "DU1234567"
            service = AccountService(broker=mock_broker, data_provider=None)

            # System should handle gracefully without crashing
            result = await service.get_broker_status()

            # Verify graceful degradation - connection stays up, P&L is None
            assert result.connection_status == ConnectionStatus.CONNECTED
            assert result.error_message is None
            # Account data should still be present
            assert result.account_id == "DU1234567"
            assert result.net_liquidation == Decimal("25000.00")
            # P&L should be None due to invalid response
            assert result.unrealized_pnl is None
            assert result.realized_pnl is None
            assert result.daily_pnl is None


class TestGetDataProviderStatus:
    """Test data provider status retrieval."""

    @pytest.mark.asyncio
    async def test_no_data_provider_returns_error(self):
        """When data provider is None, return error status."""
        service = AccountService(broker=None, data_provider=None)
        result = await service.get_data_provider_status()

        assert result.connection_status == ConnectionStatus.DISCONNECTED
        assert result.error_message == "Data provider not configured"

    @pytest.mark.asyncio
    async def test_disconnected_returns_error(self):
        """When data provider IB is disconnected, return error status."""
        mock_data_provider = MagicMock()
        mock_data_provider.ib.isConnected.return_value = False

        service = AccountService(broker=None, data_provider=mock_data_provider)
        result = await service.get_data_provider_status()

        assert result.connection_status == ConnectionStatus.DISCONNECTED
        assert "not connected" in result.error_message.lower()

    @pytest.mark.asyncio
    async def test_connected_returns_success(self):
        """When connected, return success status."""
        mock_data_provider = MagicMock()
        mock_data_provider.ib.isConnected.return_value = True

        service = AccountService(broker=None, data_provider=mock_data_provider)
        result = await service.get_data_provider_status()

        assert result.connection_status == ConnectionStatus.CONNECTED
        assert result.error_message is None


class TestGetSystemStatus:
    """Test combined system status retrieval."""

    @pytest.mark.asyncio
    async def test_returns_both_statuses(self):
        """Returns combined broker and data provider status."""
        mock_broker = MagicMock()
        mock_broker.ib.isConnected.return_value = True
        mock_broker.ib.accountValues.return_value = []
        mock_broker.ib.pnl.return_value = []

        mock_data_provider = MagicMock()
        mock_data_provider.ib.isConnected.return_value = True

        with patch("app.services.account_service.get_settings") as mock_settings:
            mock_settings.return_value.ib_account = "DU1234567"
            service = AccountService(broker=mock_broker, data_provider=mock_data_provider)
            result = await service.get_system_status()

        assert result.broker.connection_status == ConnectionStatus.CONNECTED
        assert result.data_provider.connection_status == ConnectionStatus.CONNECTED

    @pytest.mark.asyncio
    async def test_handles_broker_error_independently(self):
        """When broker errors, data provider status is still returned."""
        mock_broker = MagicMock()
        mock_broker.ib.isConnected.return_value = False

        mock_data_provider = MagicMock()
        mock_data_provider.ib.isConnected.return_value = True

        service = AccountService(broker=mock_broker, data_provider=mock_data_provider)
        result = await service.get_system_status()

        # Broker should be disconnected
        assert result.broker.connection_status == ConnectionStatus.DISCONNECTED
        # Data provider should still be connected
        assert result.data_provider.connection_status == ConnectionStatus.CONNECTED

    @pytest.mark.asyncio
    async def test_handles_data_provider_error_independently(self):
        """When data provider errors, broker status is still returned."""
        mock_broker = MagicMock()
        mock_broker.ib.isConnected.return_value = True
        mock_broker.ib.accountValues.return_value = []
        mock_broker.ib.pnl.return_value = []

        mock_data_provider = MagicMock()
        mock_data_provider.ib.isConnected.return_value = False

        with patch("app.services.account_service.get_settings") as mock_settings:
            mock_settings.return_value.ib_account = "DU1234567"
            service = AccountService(broker=mock_broker, data_provider=mock_data_provider)
            result = await service.get_system_status()

        # Broker should be connected
        assert result.broker.connection_status == ConnectionStatus.CONNECTED
        # Data provider should be disconnected
        assert result.data_provider.connection_status == ConnectionStatus.DISCONNECTED

    @pytest.mark.asyncio
    async def test_both_disconnected(self):
        """When both are disconnected, return disconnected for both."""
        mock_broker = MagicMock()
        mock_broker.ib.isConnected.return_value = False

        mock_data_provider = MagicMock()
        mock_data_provider.ib.isConnected.return_value = False

        service = AccountService(broker=mock_broker, data_provider=mock_data_provider)
        result = await service.get_system_status()

        assert result.broker.connection_status == ConnectionStatus.DISCONNECTED
        assert result.data_provider.connection_status == ConnectionStatus.DISCONNECTED
