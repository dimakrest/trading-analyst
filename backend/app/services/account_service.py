"""Account status service for fetching broker and data provider status.

This service provides a unified interface for querying the connection status
and account information from both the trading broker and data provider.
It handles status checks for Interactive Brokers connections.
"""
import logging
import math
from decimal import Decimal

from app.brokers.ib import IBBroker
from app.core.config import get_settings
from app.providers.ib_data import IBDataProvider
from app.schemas.account import (
    AccountType,
    BrokerStatusResponse,
    ConnectionStatus,
    DataProviderStatusResponse,
    SystemStatusResponse,
)

logger = logging.getLogger(__name__)


class AccountService:
    """Service for fetching system status from IB connections.

    The account service queries connection status and account information
    from both the trading broker (IBBroker) and data provider (IBDataProvider).

    Key features:
    - Broker connection status with account info and P&L
    - Data provider connection status
    - Account type detection (paper vs live)
    - Graceful handling of disconnected or unconfigured services

    Example:
        >>> service = AccountService(broker=broker, data_provider=data_provider)
        >>> status = await service.get_system_status()
        >>> print(f"Broker: {status.broker.connection_status}")
    """

    def __init__(
        self,
        broker: IBBroker | None = None,
        data_provider: IBDataProvider | None = None,
    ):
        """Initialize with IB connections.

        Args:
            broker: IBBroker singleton instance (for trading + account info)
            data_provider: IBDataProvider singleton instance (for market data)
        """
        self.broker = broker
        self.data_provider = data_provider
        self.settings = get_settings()

    def _determine_account_type(self, account_id: str) -> AccountType:
        """Determine if account is paper or live based on ID prefix.

        IB paper accounts typically start with 'D' (e.g., DU1234567)
        Live accounts typically start with 'U' (e.g., U1234567)

        Args:
            account_id: IB account identifier

        Returns:
            AccountType: PAPER, LIVE, or UNKNOWN
        """
        if not account_id:
            return AccountType.UNKNOWN

        # Paper accounts start with 'D' (Demo)
        if account_id.startswith('D'):
            return AccountType.PAPER
        # Live accounts start with 'U'
        elif account_id.startswith('U'):
            return AccountType.LIVE
        else:
            return AccountType.UNKNOWN

    def _get_account_value(self, account_values: list, tag: str, currency: str = "USD") -> Decimal | None:
        """Extract specific account value by tag.

        Args:
            account_values: List of AccountValue from IB
            tag: Tag to search for (e.g., 'NetLiquidation')
            currency: Currency to filter by (default USD)

        Returns:
            Decimal value or None if not found
        """
        for av in account_values:
            if av.tag == tag and av.currency == currency:
                try:
                    return Decimal(av.value)
                except (ValueError, TypeError):
                    logger.warning(f"Invalid value for {tag}: {av.value}")
                    return None
        return None

    async def get_broker_status(self) -> BrokerStatusResponse:
        """Fetch broker connection status with account info.

        Returns:
            BrokerStatusResponse with connection status and account info
        """
        # Handle no broker configured
        if self.broker is None:
            return BrokerStatusResponse(
                connection_status=ConnectionStatus.DISCONNECTED, error_message="Broker not configured"
            )

        # Check connection via broker's IB instance
        if not self.broker.ib.isConnected():
            return BrokerStatusResponse(
                connection_status=ConnectionStatus.DISCONNECTED,
                error_message="Not connected to Interactive Brokers",
            )

        try:
            # Get account ID - must be explicitly configured for safety
            account_id = self.settings.ib_account
            if not account_id:
                logger.error(
                    "IB_ACCOUNT not configured in environment. "
                    "This is required to prevent accidental selection of wrong account "
                    "(e.g., LIVE instead of PAPER). Set IB_ACCOUNT in .env file."
                )
                return BrokerStatusResponse(
                    connection_status=ConnectionStatus.DISCONNECTED,
                    error_message="IB_ACCOUNT not configured - set in .env for safety"
                )

            # Request account values (blocking on first call, cached after)
            account_values = self.broker.ib.accountValues(account_id)

            # Extract key values
            net_liquidation = self._get_account_value(account_values, "NetLiquidation")
            buying_power = self._get_account_value(account_values, "BuyingPower")

            # Get P&L data
            pnl_list = self.broker.ib.pnl(account_id)
            unrealized_pnl = None
            realized_pnl = None
            daily_pnl = None

            if pnl_list:
                # Validate that we got exactly one P&L object per account
                # Multiple P&L objects would indicate a serious IB Gateway issue
                if len(pnl_list) != 1:
                    logger.error(
                        f"Unexpected P&L response for account {account_id}: "
                        f"expected 1 P&L object, got {len(pnl_list)}. "
                        f"This indicates an unexpected IB Gateway response. "
                        f"Returning None P&L values for graceful degradation."
                    )
                    # Return None values instead of crashing - UI handles None gracefully
                    unrealized_pnl = None
                    realized_pnl = None
                    daily_pnl = None
                else:
                    pnl = pnl_list[0]
                    # Check for NaN values (ib_async uses float('nan') for missing)
                    if not math.isnan(pnl.unrealizedPnL):
                        unrealized_pnl = Decimal(str(pnl.unrealizedPnL))
                    if not math.isnan(pnl.realizedPnL):
                        realized_pnl = Decimal(str(pnl.realizedPnL))
                    if not math.isnan(pnl.dailyPnL):
                        daily_pnl = Decimal(str(pnl.dailyPnL))

            return BrokerStatusResponse(
                connection_status=ConnectionStatus.CONNECTED,
                error_message=None,
                account_id=account_id,
                account_type=self._determine_account_type(account_id),
                net_liquidation=net_liquidation,
                buying_power=buying_power,
                unrealized_pnl=unrealized_pnl,
                realized_pnl=realized_pnl,
                daily_pnl=daily_pnl,
            )

        except Exception as e:
            logger.error(f"Error fetching broker status: {e}", exc_info=True)
            return BrokerStatusResponse(connection_status=ConnectionStatus.DISCONNECTED, error_message=str(e))

    async def get_data_provider_status(self) -> DataProviderStatusResponse:
        """Fetch data provider connection status.

        Returns:
            DataProviderStatusResponse with connection status only
        """
        # Handle no data provider configured
        if self.data_provider is None:
            return DataProviderStatusResponse(
                connection_status=ConnectionStatus.DISCONNECTED, error_message="Data provider not configured"
            )

        # Check connection via data provider's IB instance
        if not self.data_provider.ib.isConnected():
            return DataProviderStatusResponse(
                connection_status=ConnectionStatus.DISCONNECTED,
                error_message="Data provider not connected to IB Gateway",
            )

        return DataProviderStatusResponse(connection_status=ConnectionStatus.CONNECTED, error_message=None)

    async def get_system_status(self) -> SystemStatusResponse:
        """Fetch combined status of broker and data provider.

        Returns:
            SystemStatusResponse with both broker and data provider status
        """
        broker_status = await self.get_broker_status()
        data_provider_status = await self.get_data_provider_status()

        return SystemStatusResponse(broker=broker_status, data_provider=data_provider_status)
