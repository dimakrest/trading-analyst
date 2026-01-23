"""Multi-day pattern coordination for Trading Analyst.

Provides unified interface for detecting patterns across 1, 2, and 3-day
timeframes. Implements priority logic: 3-day > 2-day > 1-day based on
research showing multi-day patterns have higher reliability.
"""

from dataclasses import dataclass
from enum import Enum

import numpy as np
from numpy.typing import NDArray

from app.indicators.candlestick import analyze_latest_candle
from app.indicators.candlestick_interpretation import interpret_pattern_in_context
from app.indicators.three_candle_patterns import (
    ThreeCandlePattern,
    analyze_three_candles,
)
from app.indicators.trend import TrendDirection
from app.indicators.two_candle_patterns import (
    TwoCandlePattern,
    analyze_two_candles,
)


class PatternDuration(str, Enum):
    """Duration classification for candlestick patterns."""

    ONE_DAY = "1-day"
    TWO_DAY = "2-day"
    THREE_DAY = "3-day"


@dataclass
class MultiDayPatternResult:
    """Result of multi-day pattern analysis.

    Attributes:
        pattern_name: Human-readable pattern name (e.g., "morning_star", "hammer")
        duration: Pattern duration (1-day, 2-day, 3-day)
        aligned_for_long: Whether pattern supports LONG mean reversion setup
        aligned_for_short: Whether pattern supports SHORT mean reversion setup
        explanation: Human-readable explanation for UI tooltips
    """

    pattern_name: str
    duration: PatternDuration
    aligned_for_long: bool
    aligned_for_short: bool
    explanation: str


# Mapping of 3-candle patterns to alignment
THREE_CANDLE_ALIGNMENT = {
    ThreeCandlePattern.MORNING_STAR: (True, False, "Morning Star (3-day) - classic bullish reversal"),
    ThreeCandlePattern.EVENING_STAR: (False, True, "Evening Star (3-day) - classic bearish reversal"),
    ThreeCandlePattern.THREE_WHITE_SOLDIERS: (True, False, "Three White Soldiers (3-day) - strong bullish momentum"),
    ThreeCandlePattern.THREE_BLACK_CROWS: (False, True, "Three Black Crows (3-day) - strong bearish momentum"),
    ThreeCandlePattern.THREE_INSIDE_UP: (True, False, "Three Inside Up (3-day) - bullish breakout from consolidation"),
    ThreeCandlePattern.THREE_INSIDE_DOWN: (False, True, "Three Inside Down (3-day) - bearish breakout from consolidation"),
    # HIGH_TIGHT_FLAG is bullish continuation, NOT reversal - don't align for mean reversion
    ThreeCandlePattern.HIGH_TIGHT_FLAG: (False, False, "High Tight Flag (3-day) - bullish continuation, not reversal"),
}


def analyze_multi_day_patterns(
    opens: list[float] | NDArray[np.float64],
    highs: list[float] | NDArray[np.float64],
    lows: list[float] | NDArray[np.float64],
    closes: list[float] | NDArray[np.float64],
    trend: TrendDirection,
) -> MultiDayPatternResult:
    """
    Analyze price data for multi-day candlestick patterns.

    Priority: 3-day > 2-day > 1-day (based on research showing multi-day
    patterns have higher reliability due to built-in confirmation).

    Args:
        opens: Array of opening prices (minimum 3 elements for full analysis)
        highs: Array of high prices
        lows: Array of low prices
        closes: Array of closing prices
        trend: Current trend direction for context-aware interpretation

    Returns:
        MultiDayPatternResult with the strongest pattern found
    """
    opens = np.array(opens, dtype=float)
    highs = np.array(highs, dtype=float)
    lows = np.array(lows, dtype=float)
    closes = np.array(closes, dtype=float)

    # 1. Try 3-day patterns first (highest priority)
    if len(opens) >= 3:
        three_day = analyze_three_candles(opens, highs, lows, closes)
        if three_day.pattern != ThreeCandlePattern.NONE:
            aligned_long, aligned_short, explanation = THREE_CANDLE_ALIGNMENT.get(
                three_day.pattern,
                (False, False, f"{three_day.pattern.value} (3-day)"),
            )
            return MultiDayPatternResult(
                pattern_name=three_day.pattern.value,
                duration=PatternDuration.THREE_DAY,
                aligned_for_long=aligned_long,
                aligned_for_short=aligned_short,
                explanation=explanation,
            )

    # 2. Try 2-day patterns (medium priority)
    if len(opens) >= 2:
        two_day = analyze_two_candles(opens, highs, lows, closes)
        if two_day.pattern != TwoCandlePattern.NONE:
            return MultiDayPatternResult(
                pattern_name=two_day.pattern.value,
                duration=PatternDuration.TWO_DAY,
                aligned_for_long=two_day.aligned_for_long,
                aligned_for_short=two_day.aligned_for_short,
                explanation=two_day.explanation,
            )

    # 3. Fall back to 1-day patterns (lowest priority)
    if len(opens) >= 1:
        single_day = analyze_latest_candle(opens, highs, lows, closes)
        interpretation = interpret_pattern_in_context(single_day, trend)

        return MultiDayPatternResult(
            pattern_name=interpretation.interpreted_pattern.value,
            duration=PatternDuration.ONE_DAY,
            aligned_for_long=interpretation.aligned_for_long,
            aligned_for_short=interpretation.aligned_for_short,
            explanation=interpretation.explanation,
        )

    # No data
    return MultiDayPatternResult(
        pattern_name="none",
        duration=PatternDuration.ONE_DAY,
        aligned_for_long=False,
        aligned_for_short=False,
        explanation="Insufficient data for pattern analysis",
    )
