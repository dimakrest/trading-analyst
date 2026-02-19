"""Context-aware candlestick pattern interpretation.

Interprets candlestick patterns considering trend direction to provide
accurate trading signal names and alignment information.
"""

from dataclasses import dataclass

from app.indicators.candlestick import CandleAnalysis, CandlePattern, CandleType
from app.indicators.trend import TrendDirection


@dataclass
class PatternInterpretation:
    """Context-aware interpretation of a candlestick pattern.

    Attributes:
        raw_pattern: Original shape-based pattern (geometry only)
        interpreted_pattern: Context-aware pattern name (considers trend)
        aligned_for_long: Whether pattern supports LONG mean reversion setup
        explanation: Human-readable explanation for UI tooltips
    """

    raw_pattern: CandlePattern
    interpreted_pattern: CandlePattern
    aligned_for_long: bool
    explanation: str


def interpret_pattern_in_context(
    analysis: CandleAnalysis,
    trend: TrendDirection,
) -> PatternInterpretation:
    """Interpret a candlestick pattern considering trend context.

    Context-Aware Pattern Naming:
        - Hammer shape in DOWNTREND = "Hammer" (bullish reversal)
        - Hammer shape in UPTREND = "Hanging Man" (bearish reversal)
        - Shooting Star shape in UPTREND = "Shooting Star" (bearish reversal)
        - Shooting Star shape in DOWNTREND = "Inverted Hammer" (bullish reversal)

    DOJI Interpretation:
        - DOJI in DOWNTREND = potential bullish reversal (aligned for LONG)
        - DOJI in UPTREND = potential bearish reversal (aligned for SHORT)
        - DOJI in NEUTRAL = no clear signal (not aligned)

    Args:
        analysis: Raw candlestick analysis from analyze_candle()
        trend: Current trend direction (10-day trend for Live 20)

    Returns:
        PatternInterpretation with context-aware pattern name and alignment
    """
    raw_pattern = analysis.raw_pattern
    candle_color = "green" if analysis.candle_type == CandleType.GREEN else "red"

    # Default: keep raw pattern
    interpreted_pattern = raw_pattern
    aligned_for_long = False
    explanation = ""

    # Handle each pattern type with context
    if raw_pattern == CandlePattern.HAMMER:
        if trend == TrendDirection.BEARISH:
            # Hammer in downtrend = bullish reversal signal
            interpreted_pattern = CandlePattern.HAMMER
            aligned_for_long = True
            explanation = f"Hammer ({candle_color}) in downtrend - bullish reversal signal"
        elif trend == TrendDirection.BULLISH:
            # Hammer shape in uptrend = Hanging Man (bearish)
            interpreted_pattern = CandlePattern.HANGING_MAN
            explanation = f"Hanging Man ({candle_color}) in uptrend - bearish reversal signal"
        else:
            # Neutral trend - pattern less meaningful
            interpreted_pattern = CandlePattern.HAMMER
            explanation = f"Hammer ({candle_color}) in neutral trend - weak signal"

    elif raw_pattern == CandlePattern.SHOOTING_STAR:
        if trend == TrendDirection.BULLISH:
            # Shooting star in uptrend = bearish reversal signal
            interpreted_pattern = CandlePattern.SHOOTING_STAR
            explanation = f"Shooting Star ({candle_color}) in uptrend - bearish reversal signal"
        elif trend == TrendDirection.BEARISH:
            # Shooting star shape in downtrend = Inverted Hammer (bullish)
            interpreted_pattern = CandlePattern.INVERTED_HAMMER
            aligned_for_long = True
            explanation = f"Inverted Hammer ({candle_color}) in downtrend - bullish reversal signal"
        else:
            # Neutral trend - pattern less meaningful
            interpreted_pattern = CandlePattern.SHOOTING_STAR
            explanation = f"Shooting Star ({candle_color}) in neutral trend - weak signal"

    elif raw_pattern == CandlePattern.DOJI:
        # DOJI signals potential reversal based on trend
        if trend == TrendDirection.BEARISH:
            aligned_for_long = True
            explanation = f"Doji in downtrend - indecision, potential bullish reversal"
        elif trend == TrendDirection.BULLISH:
            explanation = f"Doji in uptrend - indecision, potential bearish reversal"
        else:
            explanation = f"Doji in neutral trend - indecision, no clear signal"

    elif raw_pattern == CandlePattern.ENGULFING_BULLISH:
        aligned_for_long = True
        explanation = f"Bullish Engulfing - strong bullish reversal signal"

    elif raw_pattern == CandlePattern.ENGULFING_BEARISH:
        explanation = f"Bearish Engulfing - strong bearish reversal signal"

    elif raw_pattern == CandlePattern.MARUBOZU_BULLISH:
        # Marubozu is continuation, not reversal - not aligned for mean reversion
        explanation = f"Bullish Marubozu - strong buying pressure, continuation"

    elif raw_pattern == CandlePattern.MARUBOZU_BEARISH:
        # Marubozu is continuation, not reversal - not aligned for mean reversion
        explanation = f"Bearish Marubozu - strong selling pressure, continuation"

    elif raw_pattern == CandlePattern.SPINNING_TOP:
        # Spinning top is indecision like doji, but weaker signal
        if trend == TrendDirection.BEARISH:
            explanation = f"Spinning Top in downtrend - indecision, weak bullish potential"
        elif trend == TrendDirection.BULLISH:
            explanation = f"Spinning Top in uptrend - indecision, weak bearish potential"
        else:
            explanation = f"Spinning Top - market indecision"

    else:  # STANDARD
        explanation = f"Standard candle ({candle_color}) - no significant pattern"

    return PatternInterpretation(
        raw_pattern=raw_pattern,
        interpreted_pattern=interpreted_pattern,
        aligned_for_long=aligned_for_long,
        explanation=explanation,
    )
