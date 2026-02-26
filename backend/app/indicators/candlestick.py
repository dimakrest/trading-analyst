"""Candlestick pattern detection for Trading Analyst.

Detects common single-candle and two-candle patterns used in technical analysis.
All functions return pattern information for the most recent candle.
"""

from dataclasses import dataclass
from enum import Enum

import numpy as np
from numpy.typing import NDArray

# Small epsilon to handle flat candles (high == low) and avoid division by zero
FLAT_CANDLE_EPSILON = 0.0001


class CandlePattern(str, Enum):
    """Candlestick pattern types.

    Note: HANGING_MAN and INVERTED_HAMMER are context-aware patterns.
    Raw detection returns HAMMER/SHOOTING_STAR based on geometry alone.
    Use candlestick_interpretation module to get context-aware pattern names.
    """
    DOJI = "doji"
    HAMMER = "hammer"
    HANGING_MAN = "hanging_man"
    SHOOTING_STAR = "shooting_star"
    INVERTED_HAMMER = "inverted_hammer"
    ENGULFING_BULLISH = "engulfing_bullish"
    ENGULFING_BEARISH = "engulfing_bearish"
    MARUBOZU_BULLISH = "marubozu_bullish"
    MARUBOZU_BEARISH = "marubozu_bearish"
    SPINNING_TOP = "spinning_top"
    STANDARD = "standard"


class CandleType(str, Enum):
    """Candle color/type."""
    GREEN = "green"  # bullish - close > open
    RED = "red"      # bearish - close < open


class BodySize(str, Enum):
    """Candle body size classification."""
    LARGE = "large"
    MEDIUM = "medium"
    SMALL = "small"


@dataclass
class CandleAnalysis:
    """Result of candlestick pattern analysis.

    Attributes:
        raw_pattern: Shape-based pattern (geometry only, no trend context)
        candle_type: Candle color (green/red) based on close vs open
        body_size: Body size classification (large/medium/small)
        body_pct: Body as percentage of total range (0.0-1.0)
        upper_wick_pct: Upper wick as percentage of total range (0.0-1.0)
        lower_wick_pct: Lower wick as percentage of total range (0.0-1.0)
    """
    raw_pattern: CandlePattern
    candle_type: CandleType
    body_size: BodySize
    body_pct: float
    upper_wick_pct: float
    lower_wick_pct: float

    @property
    def pattern(self) -> CandlePattern:
        """Alias for raw_pattern for backward compatibility."""
        return self.raw_pattern


def analyze_candle(
    open_price: float,
    high: float,
    low: float,
    close: float,
    prev_open: float | None = None,
    prev_close: float | None = None,
    body_small_threshold: float = 0.1,  # body < 10% of range = small
    body_large_threshold: float = 0.6,  # body > 60% of range = large
    doji_threshold: float = 0.05,       # body < 5% of range = doji
    marubozu_threshold: float = 0.95,   # body > 95% of range = marubozu
) -> CandleAnalysis:
    """
    Analyze a single candlestick and detect its pattern.

    Args:
        open_price: Opening price
        high: High price
        low: Low price
        close: Closing price
        prev_open: Previous candle's open (for engulfing patterns)
        prev_close: Previous candle's close (for engulfing patterns)
        body_small_threshold: Body/range ratio below which body is "small"
        body_large_threshold: Body/range ratio above which body is "large"
        doji_threshold: Body/range ratio below which candle is a doji
        marubozu_threshold: Body/range ratio above which candle is marubozu

    Returns:
        CandleAnalysis with pattern, type, size, and percentages
    """
    # Calculate candle components
    total_range = high - low
    if total_range == 0:
        total_range = FLAT_CANDLE_EPSILON

    body = abs(close - open_price)
    body_pct = body / total_range

    # Determine candle type (green/red)
    candle_type = CandleType.GREEN if close >= open_price else CandleType.RED

    # Calculate wicks
    if candle_type == CandleType.GREEN:
        upper_wick = high - close
        lower_wick = open_price - low
    else:
        upper_wick = high - open_price
        lower_wick = close - low

    upper_wick_pct = upper_wick / total_range
    lower_wick_pct = lower_wick / total_range

    # Determine body size
    if body_pct < body_small_threshold:
        body_size = BodySize.SMALL
    elif body_pct > body_large_threshold:
        body_size = BodySize.LARGE
    else:
        body_size = BodySize.MEDIUM

    # Detect pattern
    pattern = _detect_pattern(
        body_pct=body_pct,
        upper_wick_pct=upper_wick_pct,
        lower_wick_pct=lower_wick_pct,
        candle_type=candle_type,
        prev_open=prev_open,
        prev_close=prev_close,
        open_price=open_price,
        close=close,
        doji_threshold=doji_threshold,
        marubozu_threshold=marubozu_threshold,
    )

    return CandleAnalysis(
        raw_pattern=pattern,
        candle_type=candle_type,
        body_size=body_size,
        body_pct=body_pct,
        upper_wick_pct=upper_wick_pct,
        lower_wick_pct=lower_wick_pct,
    )


def _detect_pattern(
    body_pct: float,
    upper_wick_pct: float,
    lower_wick_pct: float,
    candle_type: CandleType,
    prev_open: float | None,
    prev_close: float | None,
    open_price: float,
    close: float,
    doji_threshold: float,
    marubozu_threshold: float,
) -> CandlePattern:
    """Detect the candlestick pattern based on proportions."""

    # 1. Doji - very small body
    if body_pct < doji_threshold:
        return CandlePattern.DOJI

    # 2. Marubozu - very large body, minimal wicks
    if body_pct > marubozu_threshold:
        if candle_type == CandleType.GREEN:
            return CandlePattern.MARUBOZU_BULLISH
        else:
            return CandlePattern.MARUBOZU_BEARISH

    # 3. Spinning Top - small body with significant wicks on both sides
    if body_pct < 0.25 and upper_wick_pct > 0.25 and lower_wick_pct > 0.25:
        return CandlePattern.SPINNING_TOP

    # 4. Hammer - small body at top, long lower wick (bullish reversal)
    if body_pct < 0.35 and lower_wick_pct > 0.5 and upper_wick_pct < 0.15:
        return CandlePattern.HAMMER

    # 5. Shooting Star - small body at bottom, long upper wick (bearish reversal)
    if body_pct < 0.35 and upper_wick_pct > 0.5 and lower_wick_pct < 0.15:
        return CandlePattern.SHOOTING_STAR

    # 6. Engulfing patterns - require previous candle data
    if prev_open is not None and prev_close is not None:
        prev_body = abs(prev_close - prev_open)
        curr_body = abs(close - open_price)

        # Current body must be larger than previous
        if curr_body > prev_body:
            # Bullish engulfing: prev was red, current is green, current engulfs prev
            if prev_close < prev_open:  # prev was red
                if candle_type == CandleType.GREEN:
                    if open_price <= prev_close and close >= prev_open:
                        return CandlePattern.ENGULFING_BULLISH

            # Bearish engulfing: prev was green, current is red, current engulfs prev
            if prev_close > prev_open:  # prev was green
                if candle_type == CandleType.RED:
                    if open_price >= prev_close and close <= prev_open:
                        return CandlePattern.ENGULFING_BEARISH

    # Default to standard candle
    return CandlePattern.STANDARD


def analyze_latest_candle(
    opens: list[float] | NDArray[np.float64],
    highs: list[float] | NDArray[np.float64],
    lows: list[float] | NDArray[np.float64],
    closes: list[float] | NDArray[np.float64],
) -> CandleAnalysis:
    """
    Analyze the most recent candle in a price series.

    Args:
        opens: Array of opening prices
        highs: Array of high prices
        lows: Array of low prices
        closes: Array of closing prices

    Returns:
        CandleAnalysis for the most recent candle
    """
    opens = np.array(opens, dtype=float)
    highs = np.array(highs, dtype=float)
    lows = np.array(lows, dtype=float)
    closes = np.array(closes, dtype=float)

    if len(opens) < 1:
        raise ValueError("Need at least 1 candle for analysis")

    # Get previous candle data if available
    prev_open = float(opens[-2]) if len(opens) >= 2 else None
    prev_close = float(closes[-2]) if len(closes) >= 2 else None

    return analyze_candle(
        open_price=float(opens[-1]),
        high=float(highs[-1]),
        low=float(lows[-1]),
        close=float(closes[-1]),
        prev_open=prev_open,
        prev_close=prev_close,
    )
