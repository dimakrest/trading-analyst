"""Two-candle pattern detection for Trading Analyst.

Detects classic two-day candlestick reversal patterns used in technical analysis.
Patterns include:
- Piercing Line (bullish reversal)
- Dark Cloud Cover (bearish reversal)
- Bullish Harami (bullish reversal)
- Bearish Harami (bearish reversal)
- Tweezer Bottoms (bullish reversal)
- Tweezer Tops (bearish reversal)

Note: Engulfing patterns are detected in candlestick.py as they share
the same detection flow with single-candle patterns.
"""

from dataclasses import dataclass
from enum import Enum

import numpy as np
from numpy.typing import NDArray


class TwoCandlePattern(str, Enum):
    """Two-candle pattern types."""

    PIERCING_LINE = "piercing_line"  # Bullish reversal
    DARK_CLOUD_COVER = "dark_cloud_cover"  # Bearish reversal
    BULLISH_HARAMI = "bullish_harami"  # Bullish reversal
    BEARISH_HARAMI = "bearish_harami"  # Bearish reversal
    TWEEZER_BOTTOMS = "tweezer_bottoms"  # Bullish reversal
    TWEEZER_TOPS = "tweezer_tops"  # Bearish reversal
    NONE = "none"  # No specific pattern


@dataclass
class TwoCandleAnalysis:
    """Result of two-candle pattern analysis."""

    pattern: TwoCandlePattern
    aligned_for_long: bool
    aligned_for_short: bool
    explanation: str


# Threshold for "close enough" lows/highs to be considered tweezers
TWEEZER_TOLERANCE = 0.002  # 0.2% tolerance


def analyze_two_candles(
    opens: list[float] | NDArray[np.float64],
    highs: list[float] | NDArray[np.float64],
    lows: list[float] | NDArray[np.float64],
    closes: list[float] | NDArray[np.float64],
) -> TwoCandleAnalysis:
    """
    Analyze the last 2 candles and detect patterns.

    Args:
        opens: Array of opening prices (minimum 2 elements)
        highs: Array of high prices
        lows: Array of low prices
        closes: Array of closing prices

    Returns:
        TwoCandleAnalysis with pattern and alignment

    Raises:
        ValueError: If fewer than 2 candles provided
    """
    opens = np.array(opens, dtype=float)
    highs = np.array(highs, dtype=float)
    lows = np.array(lows, dtype=float)
    closes = np.array(closes, dtype=float)

    if len(opens) < 2:
        raise ValueError("Need at least 2 candles for analysis")

    # Get last 2 candles
    o1, o2 = opens[-2], opens[-1]
    h1, h2 = highs[-2], highs[-1]
    l1, l2 = lows[-2], lows[-1]
    c1, c2 = closes[-2], closes[-1]

    # Determine candle colors
    is_c1_red = c1 < o1
    is_c1_green = c1 > o1
    is_c2_red = c2 < o2
    is_c2_green = c2 > o2

    # Calculate body midpoints
    c1_midpoint = (o1 + c1) / 2
    c1_body = abs(c1 - o1)
    c2_body = abs(c2 - o2)

    # Pattern detection in priority order (stronger signals checked first):
    # 1. Piercing Line / Dark Cloud Cover - strong reversal with midpoint penetration
    # 2. Harami - reversal with body containment (smaller body inside larger)
    # 3. Tweezers - weakest, only matches price levels without strong body relationships

    # 1. Piercing Line: Red -> Green that closes above midpoint of red
    if is_c1_red and is_c2_green:
        if o2 < c1 and c2 > c1_midpoint and c2 < o1:
            return TwoCandleAnalysis(
                pattern=TwoCandlePattern.PIERCING_LINE,
                aligned_for_long=True,
                aligned_for_short=False,
                explanation="Piercing Line (2-day) - bullish reversal, buyers pushed price above midpoint",
            )

    # 2. Dark Cloud Cover: Green -> Red that closes below midpoint of green
    if is_c1_green and is_c2_red:
        if o2 > c1 and c2 < c1_midpoint and c2 > o1:
            return TwoCandleAnalysis(
                pattern=TwoCandlePattern.DARK_CLOUD_COVER,
                aligned_for_long=False,
                aligned_for_short=True,
                explanation="Dark Cloud Cover (2-day) - bearish reversal, sellers pushed price below midpoint",
            )

    # 3. Bullish Harami: Large Red -> Small Green contained within red's body
    if is_c1_red and is_c2_green:
        if c2_body < c1_body:
            # Check if candle 2 is inside candle 1's body
            if o2 > c1 and o2 < o1 and c2 > c1 and c2 < o1:
                return TwoCandleAnalysis(
                    pattern=TwoCandlePattern.BULLISH_HARAMI,
                    aligned_for_long=True,
                    aligned_for_short=False,
                    explanation="Bullish Harami (2-day) - small green inside large red, potential reversal",
                )

    # 4. Bearish Harami: Large Green -> Small Red contained within green's body
    if is_c1_green and is_c2_red:
        if c2_body < c1_body:
            # Check if candle 2 is inside candle 1's body
            if o2 < c1 and o2 > o1 and c2 < c1 and c2 > o1:
                return TwoCandleAnalysis(
                    pattern=TwoCandlePattern.BEARISH_HARAMI,
                    aligned_for_long=False,
                    aligned_for_short=True,
                    explanation="Bearish Harami (2-day) - small red inside large green, potential reversal",
                )

    # 5. Tweezer Bottoms: Two candles with nearly identical lows
    # First should be red (selling), second should be green (buying)
    if is_c1_red and is_c2_green:
        low_diff = abs(l1 - l2) / l1 if l1 != 0 else 0
        if low_diff < TWEEZER_TOLERANCE:
            return TwoCandleAnalysis(
                pattern=TwoCandlePattern.TWEEZER_BOTTOMS,
                aligned_for_long=True,
                aligned_for_short=False,
                explanation="Tweezer Bottoms (2-day) - matching lows show strong support, bullish reversal",
            )

    # 6. Tweezer Tops: Two candles with nearly identical highs
    # First should be green (buying), second should be red (selling)
    if is_c1_green and is_c2_red:
        high_diff = abs(h1 - h2) / h1 if h1 != 0 else 0
        if high_diff < TWEEZER_TOLERANCE:
            return TwoCandleAnalysis(
                pattern=TwoCandlePattern.TWEEZER_TOPS,
                aligned_for_long=False,
                aligned_for_short=True,
                explanation="Tweezer Tops (2-day) - matching highs show strong resistance, bearish reversal",
            )

    return TwoCandleAnalysis(
        pattern=TwoCandlePattern.NONE,
        aligned_for_long=False,
        aligned_for_short=False,
        explanation="",
    )
