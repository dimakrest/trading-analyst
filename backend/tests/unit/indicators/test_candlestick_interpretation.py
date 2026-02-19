"""Tests for context-aware candlestick pattern interpretation."""

import pytest

from app.indicators.candlestick import (
    BodySize,
    CandleAnalysis,
    CandlePattern,
    CandleType,
)
from app.indicators.candlestick_interpretation import (
    PatternInterpretation,
    interpret_pattern_in_context,
)
from app.indicators.trend import TrendDirection


class TestInterpretPatternInContext:
    """Test suite for interpret_pattern_in_context function."""

    def test_hammer_in_downtrend_is_bullish(self):
        """Hammer in downtrend should be bullish reversal signal."""
        analysis = CandleAnalysis(
            raw_pattern=CandlePattern.HAMMER,
            candle_type=CandleType.GREEN,
            body_size=BodySize.SMALL,
            body_pct=0.2,
            upper_wick_pct=0.1,
            lower_wick_pct=0.7,
        )

        result = interpret_pattern_in_context(analysis, TrendDirection.BEARISH)

        assert result.interpreted_pattern == CandlePattern.HAMMER
        assert result.aligned_for_long is True
        assert "bullish reversal" in result.explanation.lower()

    def test_hammer_in_uptrend_becomes_hanging_man(self):
        """Hammer shape in uptrend should become Hanging Man (bearish)."""
        analysis = CandleAnalysis(
            raw_pattern=CandlePattern.HAMMER,
            candle_type=CandleType.RED,
            body_size=BodySize.SMALL,
            body_pct=0.2,
            upper_wick_pct=0.1,
            lower_wick_pct=0.7,
        )

        result = interpret_pattern_in_context(analysis, TrendDirection.BULLISH)

        assert result.interpreted_pattern == CandlePattern.HANGING_MAN
        assert result.aligned_for_long is False
        assert "bearish reversal" in result.explanation.lower()

    def test_shooting_star_in_uptrend_is_bearish(self):
        """Shooting Star in uptrend should be bearish reversal signal."""
        analysis = CandleAnalysis(
            raw_pattern=CandlePattern.SHOOTING_STAR,
            candle_type=CandleType.RED,
            body_size=BodySize.SMALL,
            body_pct=0.2,
            upper_wick_pct=0.7,
            lower_wick_pct=0.1,
        )

        result = interpret_pattern_in_context(analysis, TrendDirection.BULLISH)

        assert result.interpreted_pattern == CandlePattern.SHOOTING_STAR
        assert result.aligned_for_long is False
        assert "bearish reversal" in result.explanation.lower()

    def test_shooting_star_in_downtrend_becomes_inverted_hammer(self):
        """Shooting Star shape in downtrend should become Inverted Hammer (bullish)."""
        analysis = CandleAnalysis(
            raw_pattern=CandlePattern.SHOOTING_STAR,
            candle_type=CandleType.GREEN,
            body_size=BodySize.SMALL,
            body_pct=0.2,
            upper_wick_pct=0.7,
            lower_wick_pct=0.1,
        )

        result = interpret_pattern_in_context(analysis, TrendDirection.BEARISH)

        assert result.interpreted_pattern == CandlePattern.INVERTED_HAMMER
        assert result.aligned_for_long is True
        assert "bullish reversal" in result.explanation.lower()

    def test_doji_in_downtrend_aligns_for_long(self):
        """DOJI in downtrend should signal potential bullish reversal."""
        analysis = CandleAnalysis(
            raw_pattern=CandlePattern.DOJI,
            candle_type=CandleType.GREEN,
            body_size=BodySize.SMALL,
            body_pct=0.03,
            upper_wick_pct=0.4,
            lower_wick_pct=0.4,
        )

        result = interpret_pattern_in_context(analysis, TrendDirection.BEARISH)

        assert result.interpreted_pattern == CandlePattern.DOJI
        assert result.aligned_for_long is True

    def test_doji_in_uptrend_aligns_for_short(self):
        """DOJI in uptrend should signal potential bearish reversal."""
        analysis = CandleAnalysis(
            raw_pattern=CandlePattern.DOJI,
            candle_type=CandleType.RED,
            body_size=BodySize.SMALL,
            body_pct=0.03,
            upper_wick_pct=0.4,
            lower_wick_pct=0.4,
        )

        result = interpret_pattern_in_context(analysis, TrendDirection.BULLISH)

        assert result.interpreted_pattern == CandlePattern.DOJI
        assert result.aligned_for_long is False

    def test_doji_in_neutral_trend_not_aligned(self):
        """DOJI in neutral trend should not be aligned for either direction."""
        analysis = CandleAnalysis(
            raw_pattern=CandlePattern.DOJI,
            candle_type=CandleType.GREEN,
            body_size=BodySize.SMALL,
            body_pct=0.03,
            upper_wick_pct=0.4,
            lower_wick_pct=0.4,
        )

        result = interpret_pattern_in_context(analysis, TrendDirection.NEUTRAL)

        assert result.aligned_for_long is False

    def test_hammer_in_neutral_trend_weak_signal(self):
        """Hammer in neutral trend should be weak signal (not aligned)."""
        analysis = CandleAnalysis(
            raw_pattern=CandlePattern.HAMMER,
            candle_type=CandleType.GREEN,
            body_size=BodySize.SMALL,
            body_pct=0.2,
            upper_wick_pct=0.1,
            lower_wick_pct=0.7,
        )

        result = interpret_pattern_in_context(analysis, TrendDirection.NEUTRAL)

        assert result.aligned_for_long is False
        assert "weak signal" in result.explanation.lower()

    def test_engulfing_bullish_always_aligned_for_long(self):
        """Bullish Engulfing should always be aligned for LONG."""
        analysis = CandleAnalysis(
            raw_pattern=CandlePattern.ENGULFING_BULLISH,
            candle_type=CandleType.GREEN,
            body_size=BodySize.LARGE,
            body_pct=0.8,
            upper_wick_pct=0.1,
            lower_wick_pct=0.1,
        )

        # Should be aligned regardless of trend
        for trend in [TrendDirection.BEARISH, TrendDirection.BULLISH, TrendDirection.NEUTRAL]:
            result = interpret_pattern_in_context(analysis, trend)
            assert result.aligned_for_long is True

    def test_engulfing_bearish_always_aligned_for_short(self):
        """Bearish Engulfing should always be aligned for SHORT."""
        analysis = CandleAnalysis(
            raw_pattern=CandlePattern.ENGULFING_BEARISH,
            candle_type=CandleType.RED,
            body_size=BodySize.LARGE,
            body_pct=0.8,
            upper_wick_pct=0.1,
            lower_wick_pct=0.1,
        )

        # Should be aligned regardless of trend
        for trend in [TrendDirection.BEARISH, TrendDirection.BULLISH, TrendDirection.NEUTRAL]:
            result = interpret_pattern_in_context(analysis, trend)
            assert result.aligned_for_long is False

    def test_marubozu_not_aligned_for_mean_reversion(self):
        """Marubozu is continuation pattern, should not align for mean reversion."""
        bullish_marubozu = CandleAnalysis(
            raw_pattern=CandlePattern.MARUBOZU_BULLISH,
            candle_type=CandleType.GREEN,
            body_size=BodySize.LARGE,
            body_pct=0.98,
            upper_wick_pct=0.01,
            lower_wick_pct=0.01,
        )

        result = interpret_pattern_in_context(bullish_marubozu, TrendDirection.BEARISH)

        assert result.aligned_for_long is False
        assert "continuation" in result.explanation.lower()

    def test_explanation_includes_candle_color(self):
        """Explanation should mention candle color for context."""
        green_hammer = CandleAnalysis(
            raw_pattern=CandlePattern.HAMMER,
            candle_type=CandleType.GREEN,
            body_size=BodySize.SMALL,
            body_pct=0.2,
            upper_wick_pct=0.1,
            lower_wick_pct=0.7,
        )

        result = interpret_pattern_in_context(green_hammer, TrendDirection.BEARISH)

        assert "green" in result.explanation.lower()
