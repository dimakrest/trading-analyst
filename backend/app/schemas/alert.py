"""Request/response schemas for the stock price alerts API.

Defines Pydantic models for creating, updating, and reading StockAlert and
AlertEvent records. Uses StrictBaseModel for request validation to enforce
strict contract between frontend and backend.
"""
from datetime import datetime
from typing import Literal

from pydantic import ConfigDict
from pydantic import Field
from pydantic import field_validator

from app.schemas.base import StrictBaseModel

# ---------------------------------------------------------------------------
# Valid MA periods enforced by the schema validator
# ---------------------------------------------------------------------------

VALID_MA_PERIODS: frozenset[int] = frozenset({20, 50, 150, 200})


# ---------------------------------------------------------------------------
# Alert configuration request schemas
# ---------------------------------------------------------------------------


class FibonacciConfigRequest(StrictBaseModel):
    """Configuration for a Fibonacci retracement alert.

    Controls which levels to watch, the price tolerance band, and the minimum
    swing size required to establish a valid structure.
    """

    levels: list[float] = Field(
        default=[38.2, 50.0, 61.8],
        description="Fibonacci levels to monitor (e.g. 38.2, 50.0, 61.8)",
    )
    tolerance_pct: float = Field(
        default=0.5,
        ge=0.0,
        le=5.0,
        description="Tolerance band around each level as a percentage (±%)",
    )
    min_swing_pct: float = Field(
        default=10.0,
        ge=1.0,
        le=50.0,
        description="Minimum swing size as a percentage to qualify as a valid structure",
    )


class MAConfigRequest(StrictBaseModel):
    """Configuration for a moving average touch alert.

    Fans out to one StockAlert per MA period when multiple periods are provided.
    """

    ma_periods: list[int] = Field(
        default=[200],
        min_length=1,
        description="MA periods to monitor. Each period creates a separate alert row.",
    )
    tolerance_pct: float = Field(
        default=0.5,
        ge=0.0,
        le=5.0,
        description="Tolerance band around the MA value as a percentage (±%)",
    )
    direction: Literal["above", "below", "both"] = Field(
        default="both",
        description="Which side of the MA to alert on",
    )

    @field_validator("ma_periods")
    @classmethod
    def validate_ma_periods(cls, v: list[int]) -> list[int]:
        """Reject MA periods that are not in the supported set."""
        for period in v:
            if period not in VALID_MA_PERIODS:
                raise ValueError(
                    f"Invalid MA period {period}. "
                    f"Valid periods: {sorted(VALID_MA_PERIODS)}"
                )
        return v


# ---------------------------------------------------------------------------
# Create / update request schemas
# ---------------------------------------------------------------------------


class CreateAlertRequest(StrictBaseModel):
    """Request body for POST /api/v1/alerts/.

    The config field is a discriminated union: FibonacciConfigRequest for
    fibonacci alerts and MAConfigRequest for moving_average alerts.
    """

    symbol: str = Field(
        ...,
        min_length=1,
        max_length=20,
        description="Stock ticker symbol (e.g. AAPL)",
    )
    alert_type: Literal["fibonacci", "moving_average"] = Field(
        ...,
        description="Alert type determines config schema and status lifecycle",
    )
    config: FibonacciConfigRequest | MAConfigRequest = Field(
        ...,
        description="Alert-type-specific configuration",
    )


class UpdateAlertRequest(StrictBaseModel):
    """Request body for PATCH /api/v1/alerts/{alert_id}.

    All fields are optional — only provided fields are applied.
    """

    config: FibonacciConfigRequest | MAConfigRequest | None = Field(
        default=None,
        description="New configuration to replace the existing one",
    )
    is_paused: bool | None = Field(
        default=None,
        description="Set to true to pause monitoring, false to resume",
    )


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class AlertResponse(StrictBaseModel):
    """Response schema for a single StockAlert record.

    Returned by POST (list), GET /{id}, PATCH /{id}, and as list items inside
    AlertListResponse.
    """

    id: int
    symbol: str
    alert_type: str
    status: str
    is_active: bool
    is_paused: bool
    config: dict
    computed_state: dict | None
    last_triggered_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AlertEventResponse(StrictBaseModel):
    """Response schema for a single AlertEvent record.

    price_at_event is stored as Decimal in the database but serialised as float
    here for JSON compatibility.
    """

    id: int
    alert_id: int
    event_type: str
    previous_status: str | None
    new_status: str
    price_at_event: float
    details: dict | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AlertListResponse(StrictBaseModel):
    """Paginated list response for GET /api/v1/alerts/."""

    items: list[AlertResponse]
    total: int


class AlertPriceDataResponse(StrictBaseModel):
    """Response schema for GET /api/v1/alerts/{alert_id}/price-data.

    Returns raw OHLCV data as a list of dicts for direct chart consumption by
    the frontend. The `days` field echoes the query parameter back so the client
    can detect truncation.
    """

    symbol: str
    alert_id: int
    data: list[dict]
    days: int
