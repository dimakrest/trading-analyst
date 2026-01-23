"""Schemas for time-series technical indicators."""

from typing import Any

from pydantic import Field

from app.schemas.base import StrictBaseModel


class IndicatorData(StrictBaseModel):
    """Single data point with indicator values."""

    date: str = Field(..., description="Date in YYYY-MM-DD format")
    ma_20: float | None = Field(None, description="20-day Simple Moving Average")
    cci: float | None = Field(None, description="Commodity Channel Index (20-period)")
    cci_signal: str | None = Field(
        None,
        description="CCI signal: momentum_bullish, momentum_bearish, reversal_buy, reversal_sell"
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "date": "2025-12-06",
                    "ma_20": 175.42,
                    "cci": 125.67,
                    "cci_signal": "momentum_bullish"
                }
            ]
        }
    }


class IndicatorsResponse(StrictBaseModel):
    """Time-series indicators response."""

    symbol: str = Field(..., description="Stock symbol")
    data: list[IndicatorData] = Field(..., description="Indicator data points")
    total_records: int = Field(..., description="Total number of records")
    start_date: str = Field(..., description="Start date of data")
    end_date: str = Field(..., description="End date of data")
    interval: str = Field(default="1d", description="Data interval")
    indicators: list[str] = Field(..., description="List of indicators included")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "symbol": "AAPL",
                    "data": [
                        {
                            "date": "2025-12-04",
                            "ma_20": None,
                            "cci": None,
                            "cci_signal": None
                        },
                        {
                            "date": "2025-12-05",
                            "ma_20": 175.15,
                            "cci": 112.45,
                            "cci_signal": "momentum_bullish"
                        },
                        {
                            "date": "2025-12-06",
                            "ma_20": 175.42,
                            "cci": 125.67,
                            "cci_signal": "momentum_bullish"
                        }
                    ],
                    "total_records": 3,
                    "start_date": "2025-12-04",
                    "end_date": "2025-12-06",
                    "interval": "1d",
                    "indicators": ["MA-20", "CCI"]
                }
            ]
        }
    }


class IndicatorAnalysisResponse(StrictBaseModel):
    """Response for unified indicator analysis endpoint.

    Contains requested indicator analyses for agent decision-making.
    Each agent requests only the indicators it needs.
    """

    symbol: str = Field(..., description="Stock ticker symbol")
    analysis_date: str = Field(..., description="Date of analysis (YYYY-MM-DD)")
    indicators: dict[str, Any] = Field(
        ..., description="Calculated indicators (only those requested)"
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "symbol": "AAPL",
                    "analysis_date": "2025-01-15",
                    "indicators": {
                        "trend": {
                            "direction": "bearish",
                            "strength": -3.25,
                            "period_days": 10,
                        },
                        "cci": {
                            "value": -125.5,
                            "zone": "oversold",
                            "direction": "rising",
                            "aligned_for_long": True,
                            "aligned_for_short": False,
                        },
                    },
                }
            ]
        }
    }
