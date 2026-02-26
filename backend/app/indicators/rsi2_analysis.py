"""RSI-2 analysis for Trading Analyst.

Provides 2-period RSI analysis with graduated scoring for mean-reversion
setups. RSI-2 is specifically designed for oversold bounce detection.
"""
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from app.indicators.technical import relative_strength_index


@dataclass
class RSI2Analysis:
    """Result of RSI-2 analysis.

    Contains the raw RSI-2 value and pre-computed graduated score
    for LONG (oversold) direction.
    """

    value: float  # Raw RSI-2 value (0-100)
    long_score: int  # Graduated score for LONG direction (0, 5, 10, 15, or 20)


def _score_for_long(rsi_value: float) -> int:
    """Graduated RSI-2 score for LONG (oversold) direction.

    | RSI-2 Value  | Points | Rationale                          |
    |--------------|--------|------------------------------------|
    | RSI < 5      | 20 pts | Extreme panic. Max snap-back prob. |
    | 5 ≤ RSI < 15 | 15 pts | Strong oversold. Standard entry.   |
    | 15 ≤ RSI < 30| 10 pts | Mildly oversold. Weak signal.      |
    | 30 ≤ RSI < 50| 5 pts  | Neutral/Weak. Dead money.          |
    | RSI ≥ 50     | 0 pts  | Not oversold. DO NOT BUY.          |
    """
    if rsi_value < 5:
        return 20
    elif rsi_value < 15:
        return 15
    elif rsi_value < 30:
        return 10
    elif rsi_value < 50:
        return 5
    else:
        return 0


def analyze_rsi2(
    closes: list[float] | NDArray[np.float64],
) -> RSI2Analysis:
    """Perform RSI-2 analysis with graduated scoring.

    Uses 2-period RSI for mean-reversion signal detection.
    Returns LONG score for oversold detection.

    Args:
        closes: Closing prices (oldest to newest)

    Returns:
        RSI2Analysis with value and long_score
    """
    closes_array = np.array(closes, dtype=float)

    min_length = 5  # period=2 + 3 buffer
    if len(closes_array) < min_length:
        return RSI2Analysis(value=50.0, long_score=0)

    rsi = relative_strength_index(closes_array, period=2)
    current_rsi = rsi[-1]

    if np.isnan(current_rsi):
        return RSI2Analysis(value=50.0, long_score=0)

    current_rsi = float(current_rsi)

    return RSI2Analysis(
        value=round(current_rsi, 1),
        long_score=_score_for_long(current_rsi),
    )
