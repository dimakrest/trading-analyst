"""Schemas for Live 20 API."""

from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import Field, field_serializer, model_validator

from app.schemas.base import StrictBaseModel


class SourceListItem(StrictBaseModel):
    """Reference to a stock list used as source for analysis."""

    id: int = Field(..., description="Stock list ID")
    name: str = Field(..., max_length=255, description="Stock list name at time of analysis")


class Live20ResultResponse(StrictBaseModel):
    """Response for a single Live 20 analysis result."""

    id: int
    stock: str
    created_at: datetime

    # Core results
    recommendation: str  # Maps to live20_direction: LONG, NO_SETUP
    confidence_score: int  # 0-100 score

    # Live 20 specific fields
    trend_direction: str | None = None
    trend_aligned: bool | None = None
    ma20_distance_pct: Decimal | None = None
    ma20_aligned: bool | None = None
    candle_pattern: str | None = None
    candle_bullish: bool | None = None  # True if close > open (green candle)
    candle_aligned: bool | None = None
    candle_explanation: str | None = None
    volume_aligned: bool | None = None
    volume_approach: str | None = None
    atr: Decimal | None = Field(
        None,
        description="Average True Range as percentage (e.g., 4.25 for 4.25%)",
        ge=0,
        le=100,
    )
    rvol: Decimal | None = Field(
        None, description="Relative volume ratio (today/yesterday) for conviction assessment"
    )
    cci_direction: str | None = None  # "rising", "falling", "flat"
    cci_value: Decimal | None = None
    cci_zone: str | None = None
    cci_aligned: bool | None = None
    scoring_algorithm: str | None = None  # "cci" or "rsi2"
    rsi2_value: Decimal | None = None
    rsi2_score: int | None = None
    criteria_aligned: int | None = None
    direction: str | None = None  # LONG, NO_SETUP
    sector_etf: str | None = None  # SPDR sector ETF symbol

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "examples": [
                {
                    "id": 1,
                    "stock": "AAPL",
                    "created_at": "2025-01-22T10:30:00",
                    "recommendation": "LONG",
                    "confidence_score": 80,
                    "trend_direction": "bearish",
                    "trend_aligned": True,
                    "ma20_distance_pct": "-3.25",
                    "ma20_aligned": True,
                    "candle_pattern": "bullish_engulfing",
                    "candle_bullish": True,
                    "candle_aligned": True,
                    "candle_explanation": "Strong bullish engulfing pattern indicating potential reversal",
                    "volume_aligned": True,
                    "volume_approach": "volume_confirmation",
                    "atr": 4.25,  # 4.25% of price
                    "rvol": 1.5,
                    "cci_direction": "rising",
                    "cci_value": "-125.50",
                    "cci_zone": "oversold",
                    "cci_aligned": True,
                    "criteria_aligned": 4,
                    "direction": "LONG"
                }
            ]
        }
    }

    @classmethod
    def from_recommendation(cls, rec: Any) -> "Live20ResultResponse":
        """Create from Recommendation model."""
        return cls(
            id=rec.id,
            stock=rec.stock,
            created_at=rec.created_at,
            recommendation=rec.live20_direction or "NO_SETUP",
            confidence_score=rec.confidence_score or 0,
            trend_direction=rec.live20_trend_direction,
            trend_aligned=rec.live20_trend_aligned,
            ma20_distance_pct=rec.live20_ma20_distance_pct,
            ma20_aligned=rec.live20_ma20_aligned,
            candle_pattern=rec.live20_candle_pattern,
            candle_bullish=rec.live20_candle_bullish,
            candle_aligned=rec.live20_candle_aligned,
            candle_explanation=rec.live20_candle_explanation,
            volume_aligned=rec.live20_volume_aligned,
            volume_approach=rec.live20_volume_approach,
            atr=rec.live20_atr,
            rvol=rec.live20_rvol,
            cci_direction=rec.live20_cci_direction,
            cci_value=rec.live20_cci_value,
            cci_zone=rec.live20_cci_zone,
            cci_aligned=rec.live20_cci_aligned,
            scoring_algorithm=rec.live20_scoring_algorithm,
            rsi2_value=rec.live20_rsi2_value,
            rsi2_score=rec.live20_rsi2_score,
            criteria_aligned=rec.live20_criteria_aligned,
            direction=rec.live20_direction,
            sector_etf=rec.live20_sector_etf,
        )

    @field_serializer(
        "ma20_distance_pct", "atr", "rvol", "cci_value", "rsi2_value", when_used="json"
    )
    def serialize_decimal_as_float(self, value: Decimal | None) -> float | None:
        """Serialize decimal fields as float for JSON."""
        return float(value) if value is not None else None


class Live20AnalyzeRequest(StrictBaseModel):
    """Request to analyze symbols with Live 20 mean reversion strategy.

    Supports both legacy single-list tracking (stock_list_id/stock_list_name)
    and new multi-list tracking (source_lists). Only one format can be used per request.
    """

    symbols: list[str] = Field(
        ...,
        min_length=1,
        max_length=500,
        description="List of stock symbols to analyze (max 500)",
    )
    stock_list_id: int | None = Field(
        None,
        description="DEPRECATED: Use source_lists instead. ID of stock list used as source, if any",
    )
    stock_list_name: str | None = Field(
        None,
        description="DEPRECATED: Use source_lists instead. Name of stock list at time of analysis, if any",
    )
    source_lists: list[SourceListItem] | None = Field(
        None,
        max_length=10,
        description="Array of source lists when multiple lists combined (max 10 lists)",
    )
    agent_config_id: int | None = Field(
        None,
        description="ID of agent configuration to use. If not provided, uses scoring_algorithm or defaults to CCI.",
    )
    scoring_algorithm: Literal["cci", "rsi2"] = Field(
        default="cci",
        description="Scoring algorithm for momentum criterion: 'cci' (default) or 'rsi2'. Overridden by agent_config_id if provided.",
    )

    @model_validator(mode="after")
    def validate_list_format(self) -> "Live20AnalyzeRequest":
        """Ensure only one list format is used.

        Validates that either legacy (stock_list_id/stock_list_name) OR
        new (source_lists) format is used, but not both simultaneously.

        Raises:
            ValueError: If both formats are provided in the same request
        """
        has_legacy = self.stock_list_id is not None or self.stock_list_name is not None
        has_new = self.source_lists is not None

        if has_legacy and has_new:
            raise ValueError(
                "Cannot specify both stock_list_id/stock_list_name and source_lists. "
                "Use source_lists for multi-list tracking or stock_list_id for backward compatibility."
            )

        return self


class Live20AnalyzeResponse(StrictBaseModel):
    """Response from Live 20 batch analysis.

    In async mode (status='pending'), this returns immediately with run_id.
    The worker processes symbols in the background and updates the run.
    Use GET /runs/{run_id} to check progress and get results.
    """

    run_id: int = Field(..., description="ID of the created run")
    status: str = Field(..., description="Run status: pending, running, completed, failed")
    total: int = Field(..., description="Total symbols to analyze")
    message: str | None = Field(None, description="Status message")


class Live20ResultsResponse(StrictBaseModel):
    """Response for listing Live 20 results with direction counts.

    Used by the GET /results endpoint to fetch historical Live 20 analyses
    with filtering and aggregation statistics.
    """

    results: list[Live20ResultResponse]
    total: int = Field(..., description="Number of results in this response")
    counts: dict = Field(
        ...,
        description="Direction counts: {long: int, no_setup: int}",
    )


class PortfolioRecommendRequest(StrictBaseModel):
    """Request to generate a portfolio recommendation from a live20 run.

    Filters qualifying signals by minimum score, then applies the chosen
    selection strategy (sector diversification + ATR preference).
    """

    min_score: int = Field(
        default=60,
        ge=5,
        le=100,
        description="Minimum confidence score to qualify (5-100)",
    )
    strategy: str = Field(
        default="score_sector_low_atr",
        description="Portfolio selection strategy name (e.g. 'score_sector_low_atr')",
    )
    max_per_sector: int | None = Field(
        default=2,
        ge=1,
        description="Max positions per sector (None = unlimited)",
    )
    max_positions: int | None = Field(
        default=None,
        ge=1,
        description="Max total positions selected (None = unlimited)",
    )
    directions: list[str] | None = Field(
        default=None,
        description="If provided, only include signals with these directions (e.g. ['LONG']). None = no filter.",
    )


class PortfolioRecommendItem(StrictBaseModel):
    """A single stock in the portfolio recommendation result."""

    symbol: str
    score: int
    direction: str | None
    sector: str | None
    atr_pct: float | None


class PortfolioRecommendResponse(StrictBaseModel):
    """Response for the portfolio recommendation endpoint.

    Contains the ordered list of recommended stocks along with
    metadata about the selection strategy and counts.
    """

    strategy: str = Field(..., description="Strategy name used for selection")
    strategy_description: str = Field(..., description="Human-readable strategy description")
    items: list[PortfolioRecommendItem] = Field(..., description="Ordered list of recommended stocks")
    total_qualifying: int = Field(..., description="Number of signals that met min_score before selection")
    total_selected: int = Field(..., description="Number of signals selected after applying strategy constraints")
