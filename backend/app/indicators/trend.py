"""Trend analysis for Trading Analyst.

Provides functions to detect price trends over various timeframes using
simple linear regression slope to determine trend direction.

All functions return trend direction for the most recent period based on
percentage change from start to end of the specified period.
"""

from enum import Enum

import numpy as np
from numpy.typing import NDArray


class TrendDirection(str, Enum):
    """Trend direction classification."""
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"


def detect_trend(
    closes: list[float] | NDArray[np.float64],
    period: int,
    threshold_pct: float = 1.0,
) -> TrendDirection:
    """Detect price trend over a given period.

    Analyzes the most recent period of price data and determines trend direction
    based on percentage change from start to end. A stock is considered trending
    if the price change exceeds the threshold percentage.

    Args:
        closes: Array of closing prices
        period: Number of days to analyze (e.g., 5 for weekly, 20 for monthly)
        threshold_pct: Minimum % change to consider a trend (default 1%)

    Returns:
        TrendDirection (BULLISH, BEARISH, or NEUTRAL)

    Raises:
        ValueError: If period is invalid or prices array is empty (returns NEUTRAL instead)
    """
    closes_array = np.array(closes, dtype=float)

    if len(closes_array) < period:
        return TrendDirection.NEUTRAL

    # Get the last 'period' closes
    recent_closes = closes_array[-period:]

    # Calculate percentage change from start to end of period
    start_price = recent_closes[0]
    end_price = recent_closes[-1]

    if start_price == 0:
        return TrendDirection.NEUTRAL

    pct_change = ((end_price - start_price) / start_price) * 100

    if pct_change > threshold_pct:
        return TrendDirection.BULLISH
    elif pct_change < -threshold_pct:
        return TrendDirection.BEARISH
    else:
        return TrendDirection.NEUTRAL


def detect_weekly_trend(
    closes: list[float] | NDArray[np.float64],
    threshold_pct: float = 1.0,
) -> TrendDirection:
    """Detect trend over the last 5 trading days (weekly).

    Args:
        closes: Array of closing prices
        threshold_pct: Minimum % change to consider a trend (default 1%)

    Returns:
        TrendDirection (BULLISH, BEARISH, or NEUTRAL)
    """
    return detect_trend(closes, period=5, threshold_pct=threshold_pct)


def detect_monthly_trend(
    closes: list[float] | NDArray[np.float64],
    threshold_pct: float = 2.0,
) -> TrendDirection:
    """Detect trend over the last 20 trading days (monthly).

    Args:
        closes: Array of closing prices
        threshold_pct: Minimum % change to consider a trend (default 2%)

    Returns:
        TrendDirection (BULLISH, BEARISH, or NEUTRAL)
    """
    return detect_trend(closes, period=20, threshold_pct=threshold_pct)
