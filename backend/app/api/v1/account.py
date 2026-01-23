"""Account status API endpoints."""
import logging
from decimal import Decimal

from fastapi import APIRouter
from fastapi import Depends
from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import get_settings
from app.core.deps import get_account_service
from app.schemas.account import (
    AccountType,
    BrokerStatusResponse,
    ConnectionStatus,
    DataProviderStatusResponse,
    SystemStatusResponse,
)
from app.services.account_service import AccountService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/account", tags=["account"])

# Rate limiting configuration
# Frontend polls every 30 seconds (POLLING_INTERVAL), 2-3 users = ~6 req/min normal load
# Allow 60/min for headroom during page refreshes and multiple tabs
ACCOUNT_STATUS_RATE_LIMIT = "60/minute"

# Initialize rate limiter (same as in main.py)
import os
if os.getenv("ENVIRONMENT") == "test":
    limiter = Limiter(key_func=get_remote_address, enabled=False)
else:
    limiter = Limiter(key_func=get_remote_address)


@router.get(
    "/status",
    response_model=SystemStatusResponse,
    summary="Get System Status",
    description="Returns broker connection status, account information, "
    "and data provider connectivity status. Includes account balance, "
    "buying power, and profit/loss information.",
    operation_id="get_system_status",
    responses={
        500: {"description": "Internal Server Error"},
        503: {"description": "Broker or data provider connection unavailable"},
    }
)
@limiter.limit(ACCOUNT_STATUS_RATE_LIMIT)
async def get_system_status(
    request: Request, service: AccountService = Depends(get_account_service)
) -> SystemStatusResponse:
    """Get current system status (broker + data provider).

    Returns connection status for both the trading broker and data provider:
    - Broker status: Connection, account info, balance, P&L
    - Data provider status: Connection only (no account info)

    When using mock broker, returns simulated broker data with mock data provider.
    When using IB broker, returns live data from Interactive Brokers.

    Returns:
        SystemStatusResponse: Combined broker and data provider status
    """
    settings = get_settings()

    # Handle mock broker case
    if settings.broker_type == "mock":
        return SystemStatusResponse(
            broker=BrokerStatusResponse(
                connection_status=ConnectionStatus.CONNECTED,
                error_message=None,
                account_id="MOCK-PAPER",
                account_type=AccountType.PAPER,
                net_liquidation=Decimal(str(settings.account_balance)),
                buying_power=Decimal(str(settings.account_balance)) * 2,
                unrealized_pnl=None,
                realized_pnl=None,
                daily_pnl=None,
            ),
            data_provider=DataProviderStatusResponse(
                connection_status=ConnectionStatus.CONNECTED,
                error_message=None,
            ),
        )

    # Get status from both connections via service
    return await service.get_system_status()
