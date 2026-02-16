"""Arena simulation request/response schemas.

This module defines Pydantic schemas for the Trading Agent Arena API,
which manages simulation creation, status tracking, and result retrieval.
"""
from datetime import date
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import Field
from pydantic import field_validator

from app.core.config import get_settings
from app.schemas.base import StrictBaseModel


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

    @field_validator("symbols", mode="before")
    @classmethod
    def normalize_symbols(cls, v: list[str]) -> list[str]:
        """Normalize symbols to uppercase and strip whitespace."""
        if not v:
            return v
        return [s.strip().upper() for s in v if s and s.strip()]

    @field_validator("symbols")
    @classmethod
    def validate_symbols_count(cls, v: list[str]) -> list[str]:
        """Validate that symbols count doesn't exceed configured maximum."""
        settings = get_settings()
        max_symbols = settings.arena_max_symbols
        if len(v) > max_symbols:
            msg = f"Maximum {max_symbols} symbols allowed, got {len(v)}"
            raise ValueError(msg)
        return v

    @field_validator("end_date")
    @classmethod
    def validate_date_range(cls, v: date, info) -> date:
        """Validate that end_date is after start_date."""
        start_date = info.data.get("start_date")
        if start_date and v <= start_date:
            msg = "end_date must be after start_date"
            raise ValueError(msg)
        return v

    @field_validator("agent_type")
    @classmethod
    def validate_agent_type(cls, v: str) -> str:
        """Validate agent_type exists in registry."""
        from app.services.arena.agent_registry import AGENT_REGISTRY

        if v.lower() not in AGENT_REGISTRY:
            available = ", ".join(AGENT_REGISTRY.keys())
            msg = f"Unknown agent type: {v}. Available: {available}"
            raise ValueError(msg)
        return v.lower()


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
    status: str
    current_day: int
    total_days: int
    final_equity: Decimal | None = None
    total_return_pct: Decimal | None = None
    total_trades: int
    winning_trades: int
    max_drawdown_pct: Decimal | None = None
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
