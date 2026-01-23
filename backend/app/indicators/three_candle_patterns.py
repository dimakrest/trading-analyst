"""Three-candle pattern detection and narrative generation.

Detects common 3-candle patterns and generates human-readable narratives.
Patterns include:
- Morning Star (bullish reversal)
- Evening Star (bearish reversal)
- Three White Soldiers (strong bullish)
- Three Black Crows (strong bearish)
- Three Inside Up/Down (consolidation breakout)
"""

from dataclasses import dataclass
from enum import Enum

import numpy as np
from numpy.typing import NDArray

from app.indicators.candlestick import analyze_candle, CandleAnalysis, CandleType, CandlePattern


# High Tight Flag pattern thresholds
# Minimum percentage gain on first candle to qualify as "strong move"
HIGH_TIGHT_FLAG_MIN_FIRST_CANDLE_GAIN = 0.03  # 3%
# Maximum body percentage for consolidation candles (small bodies indicate tight consolidation)
HIGH_TIGHT_FLAG_MAX_BODY_PCT = 0.3  # 30%


class ThreeCandlePattern(str, Enum):
    """Three-candle pattern types."""

    MORNING_STAR = "morning_star"  # Bullish reversal
    EVENING_STAR = "evening_star"  # Bearish reversal
    THREE_WHITE_SOLDIERS = "three_white_soldiers"  # Strong bullish
    THREE_BLACK_CROWS = "three_black_crows"  # Strong bearish
    THREE_INSIDE_UP = "three_inside_up"  # Bullish consolidation breakout
    THREE_INSIDE_DOWN = "three_inside_down"  # Bearish consolidation breakout
    HIGH_TIGHT_FLAG = "high_tight_flag"  # Bullish continuation
    NONE = "none"  # No specific pattern


@dataclass
class ThreeCandleAnalysis:
    """Result of three-candle pattern analysis."""

    pattern: ThreeCandlePattern
    candle_1: CandleAnalysis  # Setup candle
    candle_2: CandleAnalysis  # Trigger candle
    candle_3: CandleAnalysis  # Confirmation candle
    narrative: str  # Human-readable description


def analyze_three_candles(
    opens: list[float] | NDArray[np.float64],
    highs: list[float] | NDArray[np.float64],
    lows: list[float] | NDArray[np.float64],
    closes: list[float] | NDArray[np.float64],
    volumes: list[float] | NDArray[np.float64] | None = None,
) -> ThreeCandleAnalysis:
    """
    Analyze the last 3 candles and detect patterns.

    Args:
        opens: Array of opening prices (minimum 3 elements)
        highs: Array of high prices
        lows: Array of low prices
        closes: Array of closing prices
        volumes: Optional array of volumes for volume analysis

    Returns:
        ThreeCandleAnalysis with pattern, individual candle analysis, and narrative

    Raises:
        ValueError: If fewer than 3 candles provided
    """
    opens = np.array(opens, dtype=float)
    highs = np.array(highs, dtype=float)
    lows = np.array(lows, dtype=float)
    closes = np.array(closes, dtype=float)

    if len(opens) < 3:
        raise ValueError("Need at least 3 candles for analysis")

    # Analyze each of the last 3 candles
    candle_1 = analyze_candle(
        open_price=float(opens[-3]),
        high=float(highs[-3]),
        low=float(lows[-3]),
        close=float(closes[-3]),
    )
    candle_2 = analyze_candle(
        open_price=float(opens[-2]),
        high=float(highs[-2]),
        low=float(lows[-2]),
        close=float(closes[-2]),
        prev_open=float(opens[-3]),
        prev_close=float(closes[-3]),
    )
    candle_3 = analyze_candle(
        open_price=float(opens[-1]),
        high=float(highs[-1]),
        low=float(lows[-1]),
        close=float(closes[-1]),
        prev_open=float(opens[-2]),
        prev_close=float(closes[-2]),
    )

    # Detect 3-candle pattern
    pattern = _detect_three_candle_pattern(
        opens[-3:], highs[-3:], lows[-3:], closes[-3:], candle_1, candle_2, candle_3
    )

    # Generate narrative
    narrative = _generate_narrative(
        candle_1, candle_2, candle_3, pattern, volumes[-3:] if volumes is not None else None
    )

    return ThreeCandleAnalysis(
        pattern=pattern,
        candle_1=candle_1,
        candle_2=candle_2,
        candle_3=candle_3,
        narrative=narrative,
    )


def _detect_three_candle_pattern(
    opens: NDArray[np.float64],
    highs: NDArray[np.float64],
    lows: NDArray[np.float64],
    closes: NDArray[np.float64],
    c1: CandleAnalysis,
    c2: CandleAnalysis,
    c3: CandleAnalysis,
) -> ThreeCandlePattern:
    """Detect specific three-candle patterns."""

    # Morning Star: Red -> Small/Doji (gap down) -> Green (closes above midpoint of first)
    if (
        c1.candle_type == CandleType.RED
        and c2.pattern in (CandlePattern.DOJI, CandlePattern.SPINNING_TOP)
        and c3.candle_type == CandleType.GREEN
    ):
        midpoint_c1 = (opens[0] + closes[0]) / 2
        if closes[2] > midpoint_c1:
            return ThreeCandlePattern.MORNING_STAR

    # Evening Star: Green -> Small/Doji (gap up) -> Red (closes below midpoint of first)
    if (
        c1.candle_type == CandleType.GREEN
        and c2.pattern in (CandlePattern.DOJI, CandlePattern.SPINNING_TOP)
        and c3.candle_type == CandleType.RED
    ):
        midpoint_c1 = (opens[0] + closes[0]) / 2
        if closes[2] < midpoint_c1:
            return ThreeCandlePattern.EVENING_STAR

    # Three White Soldiers: 3 consecutive green candles with higher closes
    if (
        c1.candle_type == CandleType.GREEN
        and c2.candle_type == CandleType.GREEN
        and c3.candle_type == CandleType.GREEN
        and closes[1] > closes[0]
        and closes[2] > closes[1]
    ):
        return ThreeCandlePattern.THREE_WHITE_SOLDIERS

    # Three Black Crows: 3 consecutive red candles with lower closes
    if (
        c1.candle_type == CandleType.RED
        and c2.candle_type == CandleType.RED
        and c3.candle_type == CandleType.RED
        and closes[1] < closes[0]
        and closes[2] < closes[1]
    ):
        return ThreeCandlePattern.THREE_BLACK_CROWS

    # Three Inside Up: Red -> Small green inside -> Green breaks above
    if (
        c1.candle_type == CandleType.RED
        and c2.candle_type == CandleType.GREEN
        and _is_inside_bar(opens, closes, 1)
        and c3.candle_type == CandleType.GREEN
        and closes[2] > opens[0]
    ):  # Breaks above first candle's open
        return ThreeCandlePattern.THREE_INSIDE_UP

    # Three Inside Down: Green -> Small red inside -> Red breaks below
    if (
        c1.candle_type == CandleType.GREEN
        and c2.candle_type == CandleType.RED
        and _is_inside_bar(opens, closes, 1)
        and c3.candle_type == CandleType.RED
        and closes[2] < opens[0]
    ):  # Breaks below first candle's open
        return ThreeCandlePattern.THREE_INSIDE_DOWN

    # High Tight Flag: Strong green -> 2 small consolidation candles
    first_change = (closes[0] - opens[0]) / opens[0] if opens[0] != 0 else 0
    if (
        first_change > HIGH_TIGHT_FLAG_MIN_FIRST_CANDLE_GAIN
        and c2.body_pct < HIGH_TIGHT_FLAG_MAX_BODY_PCT
        and c3.body_pct < HIGH_TIGHT_FLAG_MAX_BODY_PCT
        and lows[1] > lows[0]
        and lows[2] > lows[0]
    ):
        return ThreeCandlePattern.HIGH_TIGHT_FLAG

    return ThreeCandlePattern.NONE


def _is_inside_bar(opens: NDArray[np.float64], closes: NDArray[np.float64], idx: int) -> bool:
    """Check if candle at idx is an inside bar relative to previous candle."""
    if idx < 1:
        return False
    prev_high = max(opens[idx - 1], closes[idx - 1])
    prev_low = min(opens[idx - 1], closes[idx - 1])
    curr_high = max(opens[idx], closes[idx])
    curr_low = min(opens[idx], closes[idx])
    return curr_high <= prev_high and curr_low >= prev_low


def _generate_narrative(
    c1: CandleAnalysis,
    c2: CandleAnalysis,
    c3: CandleAnalysis,
    pattern: ThreeCandlePattern,
    volumes: NDArray[np.float64] | None,
) -> str:
    """Generate human-readable narrative for the 3-candle sequence."""

    # Helper to describe a single candle
    def describe_candle(c: CandleAnalysis, position: str) -> str:
        color = "Green" if c.candle_type == CandleType.GREEN else "Red"

        # Pattern-specific descriptions
        if c.pattern == CandlePattern.DOJI:
            return f"{position}: Doji (indecision, buyers and sellers balanced)"
        elif c.pattern == CandlePattern.HAMMER:
            return f"{position}: Hammer ({color}, buyers rejected lower prices)"
        elif c.pattern == CandlePattern.SHOOTING_STAR:
            return f"{position}: Shooting Star ({color}, sellers rejected higher prices)"
        elif c.pattern == CandlePattern.SPINNING_TOP:
            return (
                f"{position}: Spinning Top ({color}, small body with wicks both ways - uncertainty)"
            )
        elif c.pattern == CandlePattern.MARUBOZU_BULLISH:
            return f"{position}: Strong Green Marubozu (pure buying pressure, no wicks)"
        elif c.pattern == CandlePattern.MARUBOZU_BEARISH:
            return f"{position}: Strong Red Marubozu (pure selling pressure, no wicks)"
        elif c.pattern == CandlePattern.ENGULFING_BULLISH:
            return f"{position}: Bullish Engulfing (buyers overwhelmed previous sellers)"
        elif c.pattern == CandlePattern.ENGULFING_BEARISH:
            return f"{position}: Bearish Engulfing (sellers overwhelmed previous buyers)"
        else:
            size = c.body_size.value
            return f"{position}: {size.capitalize()} {color} candle"

    # Build narrative parts
    parts = [
        describe_candle(c1, "Candle 1 (Setup)"),
        describe_candle(c2, "Candle 2 (Trigger)"),
        describe_candle(c3, "Candle 3 (Current)"),
    ]

    # Add pattern interpretation if detected
    pattern_interpretations = {
        ThreeCandlePattern.MORNING_STAR: "Pattern: MORNING STAR - Classic bullish reversal. The downtrend paused (doji), then buyers took control.",
        ThreeCandlePattern.EVENING_STAR: "Pattern: EVENING STAR - Classic bearish reversal. The uptrend paused (doji), then sellers took control.",
        ThreeCandlePattern.THREE_WHITE_SOLDIERS: "Pattern: THREE WHITE SOLDIERS - Strong bullish momentum. Buyers are in firm control.",
        ThreeCandlePattern.THREE_BLACK_CROWS: "Pattern: THREE BLACK CROWS - Strong bearish momentum. Sellers are in firm control.",
        ThreeCandlePattern.THREE_INSIDE_UP: "Pattern: THREE INSIDE UP - Bullish breakout from consolidation. Compression released upward.",
        ThreeCandlePattern.THREE_INSIDE_DOWN: "Pattern: THREE INSIDE DOWN - Bearish breakout from consolidation. Compression released downward.",
        ThreeCandlePattern.HIGH_TIGHT_FLAG: "Pattern: HIGH TIGHT FLAG - Bullish continuation. Strong move followed by tight consolidation. Energy is coiling.",
    }

    if pattern != ThreeCandlePattern.NONE:
        parts.append(pattern_interpretations[pattern])

    # Add volume context if available
    if volumes is not None and len(volumes) >= 3:
        avg_vol = np.mean(volumes[:2])
        if avg_vol > 0:
            vol_ratio = volumes[-1] / avg_vol
            if vol_ratio > 1.5:
                parts.append(
                    f"Volume: Current candle has {vol_ratio:.1f}x average volume - strong conviction."
                )
            elif vol_ratio < 0.5:
                parts.append(
                    f"Volume: Current candle has low volume ({vol_ratio:.1f}x average) - weak conviction."
                )

    return " | ".join(parts)
