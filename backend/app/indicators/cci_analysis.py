"""CCI analysis for Trading Analyst.

Provides enhanced Commodity Channel Index (CCI) analysis with zone detection,
direction tracking, and signal classification.

All functions analyze CCI values to identify overbought/oversold conditions
and generate trading signals based on momentum and reversal patterns.
"""

from dataclasses import dataclass
from enum import Enum

import numpy as np
from numpy.typing import NDArray

from app.indicators.technical import commodity_channel_index, detect_cci_signals


class CCIZone(str, Enum):
    """CCI zone classification."""
    OVERBOUGHT = "overbought"   # > 100
    OVERSOLD = "oversold"       # < -100
    NEUTRAL = "neutral"         # -100 to 100


class CCIDirection(str, Enum):
    """CCI direction."""
    RISING = "rising"
    FALLING = "falling"
    FLAT = "flat"


class CCISignalType(str, Enum):
    """CCI signal type."""
    MOMENTUM_BULLISH = "momentum_bullish"
    MOMENTUM_BEARISH = "momentum_bearish"
    REVERSAL_BUY = "reversal_buy"
    REVERSAL_SELL = "reversal_sell"
    NONE = "none"


@dataclass
class CCIAnalysis:
    """Result of CCI analysis."""
    value: float
    zone: CCIZone
    direction: CCIDirection
    signal_type: CCISignalType


def analyze_cci(
    highs: list[float] | NDArray[np.float64],
    lows: list[float] | NDArray[np.float64],
    closes: list[float] | NDArray[np.float64],
    period: int = 14,
) -> CCIAnalysis:
    """Perform comprehensive CCI analysis.

    Calculates the Commodity Channel Index and analyzes it across multiple
    dimensions: zone (overbought/oversold/neutral), direction (rising/falling/flat),
    and signal type (momentum or reversal).

    Args:
        highs: Array of high prices
        lows: Array of low prices
        closes: Array of closing prices
        period: CCI period (default 14)

    Returns:
        CCIAnalysis with value, zone, direction, and signal type.

    Note:
        Returns default values (NEUTRAL zone, FLAT direction, NONE signal)
        if insufficient data or CCI calculation results in NaN.
        Requires at least period + 5 data points for meaningful analysis.
    """
    highs_array = np.array(highs, dtype=float)
    lows_array = np.array(lows, dtype=float)
    closes_array = np.array(closes, dtype=float)

    min_length = period + 5
    if len(closes_array) < min_length:
        return CCIAnalysis(
            value=0.0,
            zone=CCIZone.NEUTRAL,
            direction=CCIDirection.FLAT,
            signal_type=CCISignalType.NONE,
        )

    # Calculate CCI
    cci = commodity_channel_index(highs_array, lows_array, closes_array, period)
    current_cci = cci[-1]
    prev_cci = cci[-2] if len(cci) >= 2 else current_cci

    # Handle NaN
    if np.isnan(current_cci):
        return CCIAnalysis(
            value=0.0,
            zone=CCIZone.NEUTRAL,
            direction=CCIDirection.FLAT,
            signal_type=CCISignalType.NONE,
        )

    # Determine zone
    if current_cci > 100:
        zone = CCIZone.OVERBOUGHT
    elif current_cci < -100:
        zone = CCIZone.OVERSOLD
    else:
        zone = CCIZone.NEUTRAL

    # Determine direction
    cci_change = current_cci - prev_cci
    if cci_change > 5:
        direction = CCIDirection.RISING
    elif cci_change < -5:
        direction = CCIDirection.FALLING
    else:
        direction = CCIDirection.FLAT

    # Get signal from existing function
    signals = detect_cci_signals(cci)
    latest_signal = signals[-1] if signals else None

    if latest_signal == "momentum_bullish":
        signal_type = CCISignalType.MOMENTUM_BULLISH
    elif latest_signal == "momentum_bearish":
        signal_type = CCISignalType.MOMENTUM_BEARISH
    elif latest_signal == "reversal_buy":
        signal_type = CCISignalType.REVERSAL_BUY
    elif latest_signal == "reversal_sell":
        signal_type = CCISignalType.REVERSAL_SELL
    else:
        signal_type = CCISignalType.NONE

    return CCIAnalysis(
        value=round(float(current_cci), 1),
        zone=zone,
        direction=direction,
        signal_type=signal_type,
    )
