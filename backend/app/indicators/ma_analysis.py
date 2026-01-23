"""Moving average analysis for Trading Analyst.

Provides functions to analyze price position relative to moving averages and
detect moving average slope direction.

All functions analyze how price relates to a specified moving average and
measure the trend of the moving average itself.
"""

from dataclasses import dataclass
from enum import Enum

import numpy as np
from numpy.typing import NDArray

from app.indicators.technical import simple_moving_average


class PricePosition(str, Enum):
    """Price position relative to MA."""
    ABOVE = "above"
    BELOW = "below"
    AT = "at"  # Within 0.5% of MA


class MASlope(str, Enum):
    """Moving average slope direction."""
    RISING = "rising"
    FALLING = "falling"
    FLAT = "flat"


@dataclass
class MAAnalysis:
    """Result of moving average analysis."""
    price_position: PricePosition
    distance_pct: float  # e.g., +2.5 or -1.8
    ma_slope: MASlope
    ma_value: float


def analyze_ma_distance(
    closes: list[float] | NDArray[np.float64],
    period: int = 20,
    at_threshold_pct: float = 0.5,
    slope_threshold_pct: float = 0.5,
) -> MAAnalysis:
    """Analyze price position and distance from a moving average.

    Calculates how price relates to a moving average and measures the trend
    of the moving average itself. Returns position relative to MA (above/below/at),
    percentage distance, and MA slope direction.

    Args:
        closes: Array of closing prices
        period: MA period (default 20)
        at_threshold_pct: Percentage within which price is considered "at" MA (default 0.5%)
        slope_threshold_pct: Minimum % change in MA to consider it rising/falling (default 0.5%)

    Returns:
        MAAnalysis with position (ABOVE/BELOW/AT), distance percentage,
        MA slope (RISING/FALLING/FLAT), and MA value.

    Note:
        Returns default values (AT position, FLAT slope) if insufficient data.
        Requires at least period + 5 data points for meaningful analysis.
    """
    closes_array = np.array(closes, dtype=float)

    if len(closes_array) < period + 5:
        # Not enough data for meaningful analysis
        return MAAnalysis(
            price_position=PricePosition.AT,
            distance_pct=0.0,
            ma_slope=MASlope.FLAT,
            ma_value=closes_array[-1] if len(closes_array) > 0 else 0.0,
        )

    # Calculate MA
    ma = simple_moving_average(closes_array, period)
    current_ma = ma[-1]
    current_price = closes_array[-1]

    # Calculate distance percentage
    if current_ma == 0:
        distance_pct = 0.0
    else:
        distance_pct = ((current_price - current_ma) / current_ma) * 100

    # Determine position
    if abs(distance_pct) <= at_threshold_pct:
        position = PricePosition.AT
    elif distance_pct > 0:
        position = PricePosition.ABOVE
    else:
        position = PricePosition.BELOW

    # Calculate MA slope (compare MA from 5 days ago to current)
    ma_5_days_ago = ma[-6] if len(ma) >= 6 else ma[0]
    if ma_5_days_ago == 0:
        slope_pct = 0.0
    else:
        slope_pct = ((current_ma - ma_5_days_ago) / ma_5_days_ago) * 100

    if slope_pct > slope_threshold_pct:
        slope = MASlope.RISING
    elif slope_pct < -slope_threshold_pct:
        slope = MASlope.FALLING
    else:
        slope = MASlope.FLAT

    return MAAnalysis(
        price_position=position,
        distance_pct=round(distance_pct, 2),
        ma_slope=slope,
        ma_value=round(current_ma, 2),
    )
