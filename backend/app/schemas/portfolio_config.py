"""Schemas for Portfolio Config API."""

from pydantic import Field, field_validator

from app.schemas.base import StrictBaseModel


def _validate_portfolio_strategy(value: str) -> str:
    """Validate portfolio strategy is registered."""
    from app.services.portfolio_selector import SELECTOR_REGISTRY

    if value not in SELECTOR_REGISTRY:
        available = ", ".join(SELECTOR_REGISTRY.keys())
        msg = f"Unknown portfolio strategy: {value}. Available: {available}"
        raise ValueError(msg)
    return value


def _normalize_and_validate_name(value: str) -> str:
    """Trim and validate non-empty portfolio setup names."""
    name = value.strip()
    if not name:
        raise ValueError("Name cannot be empty or whitespace")
    return name


class PortfolioConfigCreate(StrictBaseModel):
    """Request to create a new portfolio configuration."""

    name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Display name for the portfolio configuration",
    )
    portfolio_strategy: str = Field(
        default="none",
        description="Portfolio selection strategy key",
    )
    position_size: int = Field(
        default=1000,
        ge=1,
        description="Per-position dollar allocation used for simulations",
    )
    min_buy_score: int = Field(
        default=60,
        ge=5,
        le=100,
        description="Minimum score required for BUY decisions",
    )
    trailing_stop_pct: float = Field(
        default=5.0,
        gt=0,
        le=100,
        description="Trailing stop percentage used for simulations",
    )
    max_per_sector: int | None = Field(
        None,
        ge=1,
        description="Max concurrent positions per sector (None = unlimited)",
    )
    max_open_positions: int | None = Field(
        None,
        ge=1,
        description="Max total open positions (None = unlimited)",
    )

    @field_validator("portfolio_strategy")
    @classmethod
    def validate_portfolio_strategy(cls, value: str) -> str:
        return _validate_portfolio_strategy(value)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        return _normalize_and_validate_name(value)


class PortfolioConfigUpdate(StrictBaseModel):
    """Request to update an existing portfolio configuration."""

    name: str | None = Field(
        None,
        min_length=1,
        max_length=100,
        description="New display name",
    )
    portfolio_strategy: str | None = Field(
        None,
        description="New portfolio selection strategy key",
    )
    position_size: int | None = Field(
        None,
        ge=1,
        description="New per-position dollar allocation",
    )
    min_buy_score: int | None = Field(
        None,
        ge=5,
        le=100,
        description="New minimum score required for BUY decisions",
    )
    trailing_stop_pct: float | None = Field(
        None,
        gt=0,
        le=100,
        description="New trailing stop percentage used for simulations",
    )
    max_per_sector: int | None = Field(
        None,
        ge=1,
        description="New max concurrent positions per sector (None = unlimited)",
    )
    max_open_positions: int | None = Field(
        None,
        ge=1,
        description="New max total open positions (None = unlimited)",
    )

    @field_validator("portfolio_strategy")
    @classmethod
    def validate_portfolio_strategy(cls, value: str | None) -> str | None:
        if value is None:
            return value
        return _validate_portfolio_strategy(value)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str | None) -> str | None:
        if value is None:
            return value
        return _normalize_and_validate_name(value)


class PortfolioConfigResponse(StrictBaseModel):
    """Response containing a portfolio configuration."""

    id: int
    name: str
    portfolio_strategy: str
    position_size: int
    min_buy_score: int
    trailing_stop_pct: float
    max_per_sector: int | None
    max_open_positions: int | None

    model_config = {
        "from_attributes": True,
    }


class PortfolioConfigListResponse(StrictBaseModel):
    """Response containing a list of portfolio configurations."""

    items: list[PortfolioConfigResponse]
    total: int
