from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import Field, field_validator, model_validator

from app.schemas.base import StrictBaseModel
from app.utils.validation import is_valid_symbol


class SetupDefinition(StrictBaseModel):
    """A single user-defined trading setup."""
    symbol: str = Field(..., description="Ticker symbol")
    entry_price: Decimal = Field(..., gt=0, description="Price level that triggers long entry")
    stop_loss_day1: Decimal = Field(..., gt=0, description="Fixed stop loss price for day 1")
    trailing_stop_pct: Decimal = Field(
        ..., gt=0, lt=100,
        description="Trailing stop % applied from day 2 onward"
    )
    start_date: date = Field(..., description="Earliest date setup becomes eligible")

    @field_validator("symbol", mode="before")
    @classmethod
    def normalize_symbol(cls, v: str) -> str:
        v = v.strip().upper()
        if not is_valid_symbol(v):
            raise ValueError(f"Invalid symbol format: {v}")
        return v

    @field_validator("stop_loss_day1")
    @classmethod
    def stop_below_entry(cls, v: Decimal, info) -> Decimal:
        entry = info.data.get("entry_price")
        if entry and v >= entry:
            raise ValueError("stop_loss_day1 must be below entry_price")
        return v


class RunSetupSimulationRequest(StrictBaseModel):
    """Request to run a setup simulation."""
    setups: list[SetupDefinition] = Field(..., min_length=1, max_length=50)
    end_date: date = Field(..., description="Simulation end date")

    @field_validator("end_date")
    @classmethod
    def end_date_not_future(cls, v: date) -> date:
        if v > date.today():
            raise ValueError("end_date cannot be in the future")
        return v

    @model_validator(mode="after")
    def validate_date_ranges(self) -> "RunSetupSimulationRequest":
        """Validate all setup start_dates are before end_date and date range is reasonable."""
        for i, setup in enumerate(self.setups):
            if setup.start_date >= self.end_date:
                raise ValueError(
                    f"Setup {i + 1} ({setup.symbol}): start_date must be before end_date"
                )
        # Enforce max 5-year date range to prevent excessive data fetches
        earliest_start = min(s.start_date for s in self.setups)
        days_span = (self.end_date - earliest_start).days
        if days_span > 365 * 5:
            raise ValueError(
                f"Date range too large ({days_span} days). Maximum is 5 years (1825 days)."
            )
        return self


# Exit reason as a typed literal for type safety
ExitReasonType = Literal["stop_day1", "trailing_stop", "simulation_end"]


class TradeResult(StrictBaseModel):
    """A single completed trade."""
    entry_date: date
    entry_price: Decimal
    exit_date: date
    exit_price: Decimal
    shares: int
    pnl: Decimal
    return_pct: Decimal
    exit_reason: ExitReasonType


class SetupResult(StrictBaseModel):
    """Results for a single setup."""
    symbol: str
    entry_price: Decimal
    stop_loss_day1: Decimal
    trailing_stop_pct: Decimal
    start_date: date
    times_triggered: int
    pnl: Decimal
    trades: list[TradeResult]


class SimulationSummary(StrictBaseModel):
    """Overall simulation metrics."""
    total_pnl: Decimal
    total_pnl_pct: Decimal  # relative to actual capital deployed
    total_capital_deployed: Decimal  # sum of (entry_price * shares) across all trades
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: Decimal | None  # None if 0 trades
    avg_gain: Decimal | None  # avg P&L of winners
    avg_loss: Decimal | None  # avg P&L of losers
    position_size: Decimal


class SetupSimulationResponse(StrictBaseModel):
    """Complete simulation results."""
    summary: SimulationSummary
    setups: list[SetupResult]
