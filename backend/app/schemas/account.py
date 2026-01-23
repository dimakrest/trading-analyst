"""Account status schemas for broker and data provider information."""
from decimal import Decimal
from enum import Enum

from pydantic import BaseModel

from app.schemas.base import StrictBaseModel


class AccountType(str, Enum):
    """Account type based on IB account ID prefix."""
    PAPER = "PAPER"
    LIVE = "LIVE"
    UNKNOWN = "UNKNOWN"


class ConnectionStatus(str, Enum):
    """Connection status."""
    CONNECTED = "CONNECTED"
    DISCONNECTED = "DISCONNECTED"


class BrokerStatusResponse(StrictBaseModel):
    """Broker connection status with account info."""
    connection_status: ConnectionStatus
    error_message: str | None = None

    # Account info (None if disconnected)
    account_id: str | None = None
    account_type: AccountType | None = None

    # Financial data (None if disconnected)
    net_liquidation: Decimal | None = None
    buying_power: Decimal | None = None
    unrealized_pnl: Decimal | None = None
    realized_pnl: Decimal | None = None
    daily_pnl: Decimal | None = None


class DataProviderStatusResponse(StrictBaseModel):
    """Data provider connection status (no account info)."""
    connection_status: ConnectionStatus
    error_message: str | None = None


class SystemStatusResponse(StrictBaseModel):
    """Combined status of broker and data provider connections."""
    broker: BrokerStatusResponse
    data_provider: DataProviderStatusResponse

    class Config:
        json_schema_extra = {
            "example": {
                "broker": {
                    "connection_status": "CONNECTED",
                    "error_message": None,
                    "account_id": "DU1234567",
                    "account_type": "PAPER",
                    "net_liquidation": "25000.00",
                    "buying_power": "50000.00",
                    "unrealized_pnl": "150.50",
                    "realized_pnl": "75.25",
                    "daily_pnl": "225.75"
                },
                "data_provider": {
                    "connection_status": "CONNECTED",
                    "error_message": None
                }
            }
        }
