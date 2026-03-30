"""Arena simulation request/response schemas.

This module defines Pydantic schemas for the Trading Agent Arena API,
which manages simulation creation, status tracking, and result retrieval.
"""
from datetime import date
from datetime import datetime
from decimal import Decimal
from typing import Any
from typing import Literal

from pydantic import Field
from pydantic import field_validator
from pydantic import model_validator

from app.core.config import get_settings
from app.schemas.base import StrictBaseModel


# --- Shared validator functions (referenced by both request schemas) ---


def _normalize_symbols_value(v: Any) -> list[str]:
    """Normalize symbols to uppercase and strip whitespace."""
    if not v:
        return v
    return [s.strip().upper() for s in v if s and s.strip()]


def _validate_symbols_count_value(v: list[str]) -> list[str]:
    """Validate that symbols count doesn't exceed configured maximum."""
    settings = get_settings()
    max_symbols = settings.arena_max_symbols
    if len(v) > max_symbols:
        msg = f"Maximum {max_symbols} symbols allowed, got {len(v)}"
        raise ValueError(msg)
    return v


def _validate_date_range_value(v: date, info: Any) -> date:
    """Validate that end_date is after start_date."""
    start_date = info.data.get("start_date")
    if start_date and v <= start_date:
        msg = "end_date must be after start_date"
        raise ValueError(msg)
    return v


def _validate_agent_type_value(v: str) -> str:
    """Validate agent_type exists in registry."""
    from app.services.arena.agent_registry import AGENT_REGISTRY

    if v.lower() not in AGENT_REGISTRY:
        available = ", ".join(AGENT_REGISTRY.keys())
        msg = f"Unknown agent type: {v}. Available: {available}"
        raise ValueError(msg)
    return v.lower()


class CreateSimulationRequest(StrictBaseModel):
    """Request to create a new arena simulation.

    Validates and normalizes input for simulation creation.
    """

    name: str | None = Field(
        default=None,
        max_length=255,
        description="Optional user-provided simulation name",
    )
    stock_list_id: int | None = Field(
        default=None,
        description="ID of stock list used to populate symbols (optional)",
    )
    stock_list_name: str | None = Field(
        default=None,
        max_length=255,
        description="Name of stock list at time of creation (optional)",
    )
    symbols: list[str] = Field(
        ...,
        min_length=1,
        description="List of stock symbols to trade",
    )
    start_date: date = Field(..., description="Simulation start date")
    end_date: date = Field(..., description="Simulation end date")
    initial_capital: Decimal = Field(
        default=Decimal("10000"),
        gt=0,
        description="Starting capital amount",
    )
    position_size: Decimal = Field(
        default=Decimal("1000"),
        gt=0,
        description="Fixed position size per trade",
    )
    agent_type: str = Field(
        default="live20",
        description="Agent type: 'live20'",
    )
    trailing_stop_pct: float = Field(
        default=5.0,
        gt=0,
        lt=100,
        description="Trailing stop percentage (e.g., 5.0 for 5%)",
    )
    min_buy_score: int = Field(
        default=60,
        ge=20,
        le=100,
        description="Minimum score (20-100) to generate BUY signal (default: 60 = 3/5 criteria aligned)",
    )
    agent_config_id: int | None = Field(
        None,
        description="ID of agent configuration to use. Overrides scoring_algorithm if provided.",
    )
    scoring_algorithm: Literal["cci", "rsi2"] = Field(
        default="cci",
        description="Scoring algorithm for momentum criterion: 'cci' (default) or 'rsi2'. Overridden by agent_config_id if provided.",
    )
    portfolio_strategy: str = Field(
        default="none",
        description="Portfolio selection strategy: 'none', 'score_sector_low_atr', 'score_sector_high_atr', 'score_sector_moderate_atr'",
    )
    max_per_sector: int | None = Field(
        default=None,
        ge=1,
        description="Max concurrent positions per sector (None = unlimited)",
    )
    max_open_positions: int | None = Field(
        default=None,
        ge=1,
        description="Max total open positions (None = unlimited)",
    )

    # --- Layer 4: ATR-Based Trailing Stops ---
    stop_type: str = Field(
        default="fixed",
        description=(
            "Trailing stop type: 'fixed' uses a fixed trailing_stop_pct, "
            "'atr' computes the trail distance as atr_stop_multiplier * ATR%."
        ),
    )
    atr_stop_multiplier: float = Field(
        default=2.0,
        gt=0,
        description="Multiplier applied to ATR% to compute trail distance (stop_type='atr').",
    )
    atr_stop_min_pct: float = Field(
        default=2.0,
        gt=0,
        lt=100,
        description="Minimum ATR-based trail percentage (floor, stop_type='atr').",
    )
    atr_stop_max_pct: float = Field(
        default=10.0,
        gt=0,
        lt=100,
        description="Maximum ATR-based trail percentage (ceiling, stop_type='atr').",
    )

    # --- Layer 5: Take Profit Rules ---
    take_profit_pct: float | None = Field(
        default=None,
        gt=0,
        lt=1000,
        description=(
            "Fixed take-profit target as a percentage return "
            "(e.g., 8.0 exits when position is up 8%). None = disabled."
        ),
    )
    take_profit_atr_mult: float | None = Field(
        default=None,
        gt=0,
        description=(
            "ATR-multiple take-profit target "
            "(e.g., 3.0 exits when return >= 3 * ATR%). None = disabled."
        ),
    )

    # --- Layer 6: Max Holding Period ---
    max_hold_days: int | None = Field(
        default=None,
        ge=1,
        description=(
            "Maximum number of trading days to hold a position before forced exit. "
            "None = disabled (hold indefinitely)."
        ),
    )

    max_hold_days_profit: int | None = Field(
        default=None,
        ge=1,
        description=(
            "Extended max hold for profitable positions (trading days). "
            "When set, profitable positions use this instead of max_hold_days. None = use max_hold_days for all."
        ),
    )

    # --- Layer 3: Percentage-Based Position Sizing ---
    position_size_pct: float | None = Field(
        default=None,
        gt=0,
        le=100,
        description=(
            "Position size as percentage of current equity (e.g., 33.0 = 33%). "
            "Overrides fixed position_size when set. None = use fixed position_size."
        ),
    )

    # --- Layer 3 (risk-based): Volatility-Adjusted Position Sizing ---
    sizing_mode: str = Field(
        default="fixed",
        description=(
            "Position sizing mode: 'fixed' uses position_size, "
            "'fixed_pct' uses position_size_pct % of equity, "
            "'risk_based' sizes so each trade risks risk_per_trade_pct% of equity."
        ),
    )
    risk_per_trade_pct: float = Field(
        default=2.5,
        gt=0,
        le=10,
        description="Base risk per trade as % of equity (sizing_mode='risk_based').",
    )
    win_streak_bonus_pct: float = Field(
        default=0.3,
        ge=0,
        le=2,
        description="Extra risk % per consecutive win (sizing_mode='risk_based').",
    )
    max_risk_pct: float = Field(
        default=4.0,
        gt=0,
        le=10,
        description="Maximum effective risk % per trade cap (sizing_mode='risk_based').",
    )

    # --- Layer 8: Breakeven & Profit Ratcheting ---
    breakeven_trigger_pct: float | None = Field(
        default=None,
        gt=0,
        lt=100,
        description="Move stop to entry price once position return exceeds this % (None=disabled)",
    )
    ratchet_trigger_pct: float | None = Field(
        default=None,
        gt=0,
        lt=100,
        description="Tighten trail once position return exceeds this % (None=disabled)",
    )
    ratchet_trail_pct: float | None = Field(
        default=None,
        gt=0,
        lt=100,
        description="Tighter trail % to use after ratchet trigger (used with ratchet_trigger_pct)",
    )

    # --- Layer 9: Portfolio Selector Tuning ---
    ma_sweet_spot_center: float = Field(
        default=8.5,
        gt=0,
        lt=50,
        description=(
            "MA20 distance sweet-spot center for EnrichedScoreSelector tiebreaking. "
            "Signals closest to this % below MA20 are preferred. Default: 8.5 (midpoint of 5-12% range)."
        ),
    )

    # --- Layer 7: Market Regime Filter ---
    regime_filter: bool = Field(
        default=False,
        description=(
            "Enable market regime filter. When True, adjusts max_open_positions "
            "dynamically based on whether the regime symbol is above or below its SMA."
        ),
    )
    regime_symbol: str = Field(
        default="SPY",
        max_length=10,
        pattern=r"^[A-Z]{1,5}$",
        description="Ticker used as market regime indicator (default: 'SPY').",
    )
    regime_sma_period: int = Field(
        default=20,
        ge=5,
        le=200,
        description=(
            "SMA period for regime detection. "
            "SPY close > SMA(period) = bull, SPY close < SMA(period) = bear."
        ),
    )
    regime_bull_max_positions: int | None = Field(
        default=None,
        ge=1,
        description=(
            "Max open positions in bull regime (regime symbol > SMA). "
            "None = use max_open_positions (or unlimited)."
        ),
    )
    regime_bear_max_positions: int = Field(
        default=1,
        ge=0,
        description=(
            "Max open positions in bear regime (regime symbol < SMA). "
            "0 = block all new entries."
        ),
    )

    # Shared validators — plain functions applied via field_validator(...)
    _normalize_symbols = field_validator("symbols", mode="before")(_normalize_symbols_value)
    _validate_symbols_count = field_validator("symbols")(_validate_symbols_count_value)
    _validate_date_range = field_validator("end_date")(_validate_date_range_value)
    _validate_agent_type = field_validator("agent_type")(_validate_agent_type_value)

    @field_validator("stop_type")
    @classmethod
    def validate_stop_type(cls, v: str) -> str:
        """Validate stop_type is a recognized value."""
        allowed = {"fixed", "atr"}
        if v not in allowed:
            msg = f"Unknown stop_type: {v!r}. Allowed: {', '.join(sorted(allowed))}"
            raise ValueError(msg)
        return v

    @field_validator("sizing_mode")
    @classmethod
    def validate_sizing_mode(cls, v: str) -> str:
        """Validate sizing_mode is a recognized value."""
        allowed = {"fixed", "fixed_pct", "risk_based"}
        if v not in allowed:
            msg = f"Unknown sizing_mode: {v!r}. Allowed: {', '.join(sorted(allowed))}"
            raise ValueError(msg)
        return v

    @field_validator("portfolio_strategy")
    @classmethod
    def validate_portfolio_strategy(cls, v: str) -> str:
        """Validate portfolio_strategy is a registered selector."""
        from app.services.portfolio_selector import SELECTOR_REGISTRY

        if v not in SELECTOR_REGISTRY:
            available = ", ".join(SELECTOR_REGISTRY.keys())
            msg = f"Unknown portfolio strategy: {v}. Available: {available}"
            raise ValueError(msg)
        return v

    @model_validator(mode="after")
    def validate_ratchet_pair(self) -> "CreateSimulationRequest":
        """Ensure ratchet_trigger_pct and ratchet_trail_pct are both set or both None."""
        if (self.ratchet_trigger_pct is None) != (self.ratchet_trail_pct is None):
            msg = "ratchet_trigger_pct and ratchet_trail_pct must both be set or both be None"
            raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def validate_sizing_stop_combination(self) -> "CreateSimulationRequest":
        """Ensure risk_based sizing is only used with ATR stops."""
        if self.sizing_mode == "risk_based" and self.stop_type != "atr":
            msg = "sizing_mode='risk_based' requires stop_type='atr'"
            raise ValueError(msg)
        return self


class CreateComparisonRequest(StrictBaseModel):
    """Request to create a multi-strategy comparison run.

    Creates one simulation per selected portfolio strategy, all sharing
    the same group_id and base configuration. Requires 2-4 strategies.
    """

    name: str | None = Field(
        default=None,
        max_length=255,
        description="Optional user-provided comparison name (strategy name appended automatically)",
    )
    stock_list_id: int | None = Field(
        default=None,
        description="ID of stock list used to populate symbols (optional)",
    )
    stock_list_name: str | None = Field(
        default=None,
        max_length=255,
        description="Name of stock list at time of creation (optional)",
    )
    symbols: list[str] = Field(
        ...,
        min_length=1,
        description="List of stock symbols to trade",
    )
    start_date: date = Field(..., description="Simulation start date")
    end_date: date = Field(..., description="Simulation end date")
    initial_capital: Decimal = Field(
        default=Decimal("10000"),
        gt=0,
        description="Starting capital amount",
    )
    position_size: Decimal = Field(
        default=Decimal("1000"),
        gt=0,
        description="Fixed position size per trade",
    )
    agent_type: str = Field(
        default="live20",
        description="Agent type: 'live20'",
    )
    trailing_stop_pct: float = Field(
        default=5.0,
        gt=0,
        lt=100,
        description="Trailing stop percentage (e.g., 5.0 for 5%)",
    )
    min_buy_score: int = Field(
        default=60,
        ge=20,
        le=100,
        description="Minimum score (20-100) to generate BUY signal",
    )
    agent_config_id: int | None = Field(
        None,
        description="ID of agent configuration to use. Overrides scoring_algorithm if provided.",
    )
    scoring_algorithm: Literal["cci", "rsi2"] = Field(
        default="cci",
        description="Scoring algorithm for momentum criterion: 'cci' (default) or 'rsi2'. Overridden by agent_config_id if provided.",
    )
    portfolio_strategies: list[str] = Field(
        ...,
        min_length=2,
        max_length=4,
        description="Portfolio strategies to compare (2-4 required). Each creates one simulation.",
    )
    max_per_sector: int | None = Field(
        default=None,
        ge=1,
        description="Max concurrent positions per sector (None = unlimited)",
    )
    max_open_positions: int | None = Field(
        default=None,
        ge=1,
        description="Max total open positions (None = unlimited)",
    )

    # --- Layer 3 (risk-based): Volatility-Adjusted Position Sizing ---
    sizing_mode: str = Field(
        default="fixed",
        description=(
            "Position sizing mode: 'fixed' uses position_size, "
            "'fixed_pct' uses position_size_pct % of equity, "
            "'risk_based' sizes so each trade risks risk_per_trade_pct% of equity."
        ),
    )
    risk_per_trade_pct: float = Field(
        default=2.5,
        gt=0,
        le=10,
        description="Base risk per trade as % of equity (sizing_mode='risk_based').",
    )
    win_streak_bonus_pct: float = Field(
        default=0.3,
        ge=0,
        le=2,
        description="Extra risk % per consecutive win (sizing_mode='risk_based').",
    )
    max_risk_pct: float = Field(
        default=4.0,
        gt=0,
        le=10,
        description="Maximum effective risk % per trade cap (sizing_mode='risk_based').",
    )

    # Shared validators — same standalone functions as CreateSimulationRequest
    _normalize_symbols = field_validator("symbols", mode="before")(_normalize_symbols_value)
    _validate_symbols_count = field_validator("symbols")(_validate_symbols_count_value)
    _validate_date_range = field_validator("end_date")(_validate_date_range_value)
    _validate_agent_type = field_validator("agent_type")(_validate_agent_type_value)

    @field_validator("portfolio_strategies")
    @classmethod
    def validate_strategies(cls, v: list[str]) -> list[str]:
        """Validate portfolio_strategies are registered and have no duplicates."""
        from app.services.portfolio_selector import SELECTOR_REGISTRY

        for strategy in v:
            if strategy not in SELECTOR_REGISTRY:
                available = ", ".join(SELECTOR_REGISTRY.keys())
                msg = f"Unknown strategy: {strategy}. Available: {available}"
                raise ValueError(msg)
        if len(v) != len(set(v)):
            msg = "Duplicate strategies are not allowed"
            raise ValueError(msg)
        return v


class PositionResponse(StrictBaseModel):
    """Response schema for a trading position.

    Represents a single position within an arena simulation.
    """

    id: int
    symbol: str
    status: str
    signal_date: date
    entry_date: date | None = None
    entry_price: Decimal | None = None
    shares: int | None = None
    highest_price: Decimal | None = None
    current_stop: Decimal | None = None
    exit_date: date | None = None
    exit_price: Decimal | None = None
    exit_reason: str | None = None
    realized_pnl: Decimal | None = None
    return_pct: Decimal | None = None
    agent_reasoning: str | None = None
    agent_score: int | None = None
    sector: str | None = None

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "examples": [
                {
                    "id": 1,
                    "symbol": "AAPL",
                    "status": "closed",
                    "signal_date": "2025-01-15",
                    "entry_date": "2025-01-16",
                    "entry_price": "175.50",
                    "shares": 57,
                    "highest_price": "182.30",
                    "current_stop": "173.18",
                    "exit_date": "2025-01-20",
                    "exit_price": "179.80",
                    "exit_reason": "target_reached",
                    "realized_pnl": "244.10",
                    "return_pct": "2.45",
                    "agent_reasoning": "Strong uptrend with bullish CCI and aligned volume",
                    "agent_score": 85
                }
            ]
        }
    }


class SnapshotResponse(StrictBaseModel):
    """Response schema for a daily portfolio snapshot.

    Captures portfolio state at end of each trading day.
    """

    id: int
    snapshot_date: date
    day_number: int
    cash: Decimal
    positions_value: Decimal
    total_equity: Decimal
    daily_pnl: Decimal
    daily_return_pct: Decimal
    cumulative_return_pct: Decimal
    open_position_count: int
    decisions: dict

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "examples": [
                {
                    "id": 1,
                    "snapshot_date": "2025-01-15",
                    "day_number": 1,
                    "cash": "9000.00",
                    "positions_value": "1050.00",
                    "total_equity": "10050.00",
                    "daily_pnl": "50.00",
                    "daily_return_pct": "0.50",
                    "cumulative_return_pct": "0.50",
                    "open_position_count": 1,
                    "decisions": {
                        "signals_evaluated": 5,
                        "positions_opened": 1,
                        "positions_closed": 0
                    }
                }
            ]
        }
    }


class SimulationResponse(StrictBaseModel):
    """Response schema for a simulation summary.

    Contains simulation configuration, state, and performance metrics.
    """

    id: int
    name: str | None = None
    stock_list_id: int | None = None
    stock_list_name: str | None = None
    symbols: list[str]
    start_date: date
    end_date: date
    initial_capital: Decimal
    position_size: Decimal
    agent_type: str
    trailing_stop_pct: Decimal | None = None
    min_buy_score: int | None = None
    scoring_algorithm: str | None = None
    volume_score: int | None = None
    candle_pattern_score: int | None = None
    cci_score: int | None = None
    ma20_distance_score: int | None = None
    portfolio_strategy: str | None = None
    max_per_sector: int | None = None
    max_open_positions: int | None = None
    sizing_mode: str | None = None
    group_id: str | None = None
    status: str
    current_day: int
    total_days: int
    final_equity: Decimal | None = None
    total_return_pct: Decimal | None = None
    total_trades: int
    winning_trades: int
    max_drawdown_pct: Decimal | None = None
    avg_hold_days: Decimal | None = None
    avg_win_pnl: Decimal | None = None
    avg_loss_pnl: Decimal | None = None
    profit_factor: Decimal | None = None
    sharpe_ratio: Decimal | None = None
    total_realized_pnl: Decimal | None = None
    created_at: str  # ISO datetime string

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "examples": [
                {
                    "id": 1,
                    "name": "Tech Momentum Test",
                    "stock_list_id": 1,
                    "stock_list_name": "Tech Stocks",
                    "symbols": ["AAPL", "MSFT", "GOOGL", "AMZN", "META"],
                    "start_date": "2025-01-01",
                    "end_date": "2025-03-31",
                    "initial_capital": "10000.00",
                    "position_size": "1000.00",
                    "agent_type": "live20",
                    "trailing_stop_pct": "5.0",
                    "min_buy_score": 60,
                    "status": "completed",
                    "current_day": 90,
                    "total_days": 90,
                    "final_equity": "10850.00",
                    "total_return_pct": "8.50",
                    "total_trades": 15,
                    "winning_trades": 10,
                    "max_drawdown_pct": "-2.30",
                    "created_at": "2025-01-22T10:30:00"
                }
            ]
        }
    }

    @field_validator("created_at", mode="before")
    @classmethod
    def serialize_datetime(cls, v: datetime | str) -> str:
        """Convert datetime to ISO format string."""
        if isinstance(v, datetime):
            return v.isoformat()
        return v


class SimulationListResponse(StrictBaseModel):
    """Paginated response for simulation list."""

    items: list[SimulationResponse]
    total: int = Field(..., description="Total number of simulations")
    has_more: bool = Field(..., description="Whether more simulations exist beyond current page")


class SimulationDetailResponse(StrictBaseModel):
    """Response schema for detailed simulation view.

    Includes simulation summary plus all positions and snapshots.
    """

    simulation: SimulationResponse
    positions: list[PositionResponse]
    snapshots: list[SnapshotResponse]

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "simulation": {
                        "id": 1,
                        "name": "Tech Momentum Test",
                        "stock_list_id": 1,
                        "stock_list_name": "Tech Stocks",
                        "symbols": ["AAPL", "MSFT", "GOOGL"],
                        "start_date": "2025-01-01",
                        "end_date": "2025-01-31",
                        "initial_capital": "10000.00",
                        "position_size": "1000.00",
                        "agent_type": "live20",
                        "trailing_stop_pct": "5.0",
                        "min_buy_score": 60,
                        "status": "completed",
                        "current_day": 31,
                        "total_days": 31,
                        "final_equity": "10350.00",
                        "total_return_pct": "3.50",
                        "total_trades": 5,
                        "winning_trades": 3,
                        "max_drawdown_pct": "-1.20",
                        "created_at": "2025-01-22T10:30:00"
                    },
                    "positions": [
                        {
                            "id": 1,
                            "symbol": "AAPL",
                            "status": "closed",
                            "signal_date": "2025-01-15",
                            "entry_date": "2025-01-16",
                            "entry_price": "175.50",
                            "shares": 57,
                            "exit_date": "2025-01-20",
                            "exit_price": "179.80",
                            "exit_reason": "target_reached",
                            "realized_pnl": "244.10",
                            "return_pct": "2.45",
                            "agent_score": 85
                        }
                    ],
                    "snapshots": [
                        {
                            "id": 1,
                            "snapshot_date": "2025-01-15",
                            "day_number": 1,
                            "cash": "9000.00",
                            "positions_value": "1050.00",
                            "total_equity": "10050.00",
                            "daily_pnl": "50.00",
                            "daily_return_pct": "0.50",
                            "cumulative_return_pct": "0.50",
                            "open_position_count": 1,
                            "decisions": {"signals_evaluated": 3, "positions_opened": 1}
                        }
                    ]
                }
            ]
        }
    }


class AgentInfo(StrictBaseModel):
    """Information about an available arena agent.

    Used in list_agents endpoint to describe agent capabilities and requirements.
    """

    type: str
    name: str
    required_lookback_days: int

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "type": "live20",
                    "name": "Live 20 Mean Reversion",
                    "required_lookback_days": 40
                }
            ]
        }
    }


class PortfolioStrategyInfo(StrictBaseModel):
    """Information about an available portfolio selection strategy.

    Used in list_portfolio_strategies endpoint.
    """

    name: str
    description: str


class ComparisonResponse(StrictBaseModel):
    """Response for a multi-strategy comparison group.

    Groups all simulations that share a common group_id, created together
    via POST /comparisons. Used for both creation response and polling.
    """

    group_id: str
    simulations: list[SimulationResponse]


class BenchmarkDataPoint(StrictBaseModel):
    """A single data point in the benchmark price series.

    Used by the benchmark endpoint to return normalized cumulative return
    data for SPY or QQQ over a simulation's date range.
    """

    date: date
    close: Decimal
    cumulative_return_pct: Decimal


class EquityCurvePoint(StrictBaseModel):
    """A single point in an equity curve time series."""

    snapshot_date: date
    total_equity: Decimal


class SimulationEquityCurve(StrictBaseModel):
    """Equity curve for a single simulation."""

    simulation_id: int
    portfolio_strategy: str | None = None
    snapshots: list[EquityCurvePoint]


class ComparisonEquityCurvesResponse(StrictBaseModel):
    """Lightweight equity curves for all simulations in a comparison group."""

    group_id: str
    simulations: list[SimulationEquityCurve]
