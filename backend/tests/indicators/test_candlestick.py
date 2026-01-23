"""Tests for candlestick pattern detection."""

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.indicators.candlestick import (
    CandlePattern,
    CandleType,
    BodySize,
    CandleAnalysis,
    analyze_candle,
    analyze_latest_candle,
)


class TestAnalyzeCandle:
    """Tests for single candle analysis."""

    def test_doji_pattern(self):
        """Test doji pattern detection."""
        # Doji: very small body (< 5% of range)
        result = analyze_candle(
            open_price=100.0,
            high=105.0,
            low=95.0,
            close=100.2,  # 0.2 body, 10 range = 2% body
        )

        assert result.pattern == CandlePattern.DOJI
        assert result.body_pct < 0.05

    def test_hammer_pattern(self):
        """Test hammer pattern detection."""
        # Hammer: small body at top, long lower wick
        result = analyze_candle(
            open_price=103.0,
            high=105.0,
            low=95.0,
            close=104.0,  # Small body at top
        )

        assert result.pattern == CandlePattern.HAMMER
        assert result.lower_wick_pct > 0.5
        assert result.upper_wick_pct < 0.15

    def test_shooting_star_pattern(self):
        """Test shooting star pattern detection."""
        # Shooting star: small body at bottom, long upper wick
        result = analyze_candle(
            open_price=96.0,
            high=105.0,
            low=95.0,
            close=95.5,  # Small body at bottom
        )

        assert result.pattern == CandlePattern.SHOOTING_STAR
        assert result.upper_wick_pct > 0.5
        assert result.lower_wick_pct < 0.15

    def test_marubozu_bullish_pattern(self):
        """Test bullish marubozu pattern detection."""
        # Marubozu: very large body (> 95% of range), minimal wicks
        result = analyze_candle(
            open_price=95.0,
            high=105.0,
            low=94.8,
            close=104.8,  # Large green body
        )

        assert result.pattern == CandlePattern.MARUBOZU_BULLISH
        assert result.candle_type == CandleType.GREEN
        assert result.body_pct > 0.95

    def test_marubozu_bearish_pattern(self):
        """Test bearish marubozu pattern detection."""
        # Marubozu: very large body (> 95% of range), minimal wicks
        result = analyze_candle(
            open_price=105.0,
            high=105.2,
            low=95.2,
            close=95.0,  # Large red body
        )

        assert result.pattern == CandlePattern.MARUBOZU_BEARISH
        assert result.candle_type == CandleType.RED
        assert result.body_pct > 0.95

    def test_spinning_top_pattern(self):
        """Test spinning top pattern detection."""
        # Spinning top: small body with wicks on both sides
        result = analyze_candle(
            open_price=99.0,
            high=105.0,
            low=95.0,
            close=101.0,  # Small body in middle
        )

        assert result.pattern == CandlePattern.SPINNING_TOP
        assert result.body_pct < 0.25
        assert result.upper_wick_pct > 0.25
        assert result.lower_wick_pct > 0.25

    def test_engulfing_bullish_pattern(self):
        """Test bullish engulfing pattern detection."""
        # Bullish engulfing: prev red, current green and larger
        result = analyze_candle(
            open_price=95.0,
            high=105.0,
            low=94.0,
            close=104.0,
            prev_open=101.0,  # Prev was red
            prev_close=99.0,
        )

        assert result.pattern == CandlePattern.ENGULFING_BULLISH
        assert result.candle_type == CandleType.GREEN

    def test_engulfing_bearish_pattern(self):
        """Test bearish engulfing pattern detection."""
        # Bearish engulfing: prev green, current red and larger
        result = analyze_candle(
            open_price=105.0,
            high=106.0,
            low=94.0,
            close=95.0,
            prev_open=99.0,  # Prev was green
            prev_close=101.0,
        )

        assert result.pattern == CandlePattern.ENGULFING_BEARISH
        assert result.candle_type == CandleType.RED

    def test_standard_candle(self):
        """Test standard candle (no special pattern)."""
        result = analyze_candle(
            open_price=100.0,
            high=103.0,
            low=98.0,
            close=102.0,  # Normal candle
        )

        assert result.pattern == CandlePattern.STANDARD

    def test_green_candle_type(self):
        """Test green candle type detection."""
        result = analyze_candle(
            open_price=100.0,
            high=105.0,
            low=95.0,
            close=103.0,
        )

        assert result.candle_type == CandleType.GREEN

    def test_red_candle_type(self):
        """Test red candle type detection."""
        result = analyze_candle(
            open_price=103.0,
            high=105.0,
            low=95.0,
            close=100.0,
        )

        assert result.candle_type == CandleType.RED

    def test_body_size_classification(self):
        """Test body size classification."""
        # Small body (< 10% of range)
        small = analyze_candle(
            open_price=100.0,
            high=105.0,
            low=95.0,
            close=100.8,  # 0.8 body, 10 range = 8%
        )
        assert small.body_size == BodySize.SMALL

        # Medium body (10-60% of range)
        medium = analyze_candle(
            open_price=100.0,
            high=105.0,
            low=95.0,
            close=103.0,  # 3 body, 10 range = 30%
        )
        assert medium.body_size == BodySize.MEDIUM

        # Large body (> 60% of range)
        large = analyze_candle(
            open_price=95.0,
            high=105.0,
            low=95.0,
            close=102.0,  # 7 body, 10 range = 70%
        )
        assert large.body_size == BodySize.LARGE

    def test_zero_range_handling(self):
        """Test handling of zero range candle."""
        # If high == low, should avoid division by zero
        result = analyze_candle(
            open_price=100.0,
            high=100.0,
            low=100.0,
            close=100.0,
        )

        # Should handle gracefully, not raise error
        assert isinstance(result, CandleAnalysis)

    def test_wick_percentages(self):
        """Test wick percentage calculations."""
        # Green candle: upper wick = high - close, lower wick = open - low
        result = analyze_candle(
            open_price=96.0,
            high=105.0,
            low=95.0,
            close=104.0,
        )

        expected_upper_wick_pct = (105.0 - 104.0) / (105.0 - 95.0)
        expected_lower_wick_pct = (96.0 - 95.0) / (105.0 - 95.0)

        assert abs(result.upper_wick_pct - expected_upper_wick_pct) < 0.01
        assert abs(result.lower_wick_pct - expected_lower_wick_pct) < 0.01


class TestAnalyzeLatestCandle:
    """Tests for analyzing latest candle in a series."""

    def test_analyze_latest_single_candle(self):
        """Test analyzing latest candle with single candle."""
        opens = [100.0]
        highs = [105.0]
        lows = [95.0]
        closes = [103.0]

        result = analyze_latest_candle(opens, highs, lows, closes)

        assert result.candle_type == CandleType.GREEN
        assert isinstance(result, CandleAnalysis)

    def test_analyze_latest_multiple_candles(self):
        """Test analyzing latest candle with multiple candles."""
        opens = [100.0, 102.0, 101.0]
        highs = [105.0, 106.0, 107.0]
        lows = [95.0, 96.0, 97.0]
        closes = [103.0, 104.0, 99.0]  # Last one is red

        result = analyze_latest_candle(opens, highs, lows, closes)

        # Should analyze the last candle
        assert result.candle_type == CandleType.RED

    def test_analyze_latest_with_engulfing(self):
        """Test that analyze_latest_candle can detect engulfing patterns."""
        # Previous candle: red (102 -> 100)
        # Current candle: green (98 -> 104) - bullish engulfing
        opens = [102.0, 98.0]
        highs = [103.0, 105.0]
        lows = [99.0, 97.0]
        closes = [100.0, 104.0]

        result = analyze_latest_candle(opens, highs, lows, closes)

        assert result.pattern == CandlePattern.ENGULFING_BULLISH

    def test_analyze_latest_empty_array(self):
        """Test error handling with empty arrays."""
        with pytest.raises(ValueError, match="Need at least 1 candle"):
            analyze_latest_candle([], [], [], [])

    def test_analyze_latest_numpy_arrays(self):
        """Test that analyze_latest_candle works with numpy arrays."""
        opens = np.array([100.0, 102.0])
        highs = np.array([105.0, 106.0])
        lows = np.array([95.0, 96.0])
        closes = np.array([103.0, 104.0])

        result = analyze_latest_candle(opens, highs, lows, closes)

        assert isinstance(result, CandleAnalysis)


class TestCandlePatternProperties:
    """Property-based tests for candle analysis."""

    @given(
        st.floats(min_value=90.0, max_value=110.0),
        st.floats(min_value=90.0, max_value=110.0),
    )
    @settings(max_examples=50, deadline=1000)
    def test_body_percentage_range(self, open_price, close):
        """Test that body percentage is always between 0 and 1."""
        high = max(open_price, close) + 5.0
        low = min(open_price, close) - 5.0

        result = analyze_candle(
            open_price=open_price,
            high=high,
            low=low,
            close=close,
        )

        assert 0.0 <= result.body_pct <= 1.0

    @given(
        st.floats(min_value=90.0, max_value=110.0),
        st.floats(min_value=90.0, max_value=110.0),
    )
    @settings(max_examples=50, deadline=1000)
    def test_wick_percentages_sum_valid(self, open_price, close):
        """Test that body + upper wick + lower wick approximately equals 1."""
        high = max(open_price, close) + 5.0
        low = min(open_price, close) - 5.0

        result = analyze_candle(
            open_price=open_price,
            high=high,
            low=low,
            close=close,
        )

        # Body + wicks should sum to approximately 1 (total range)
        total = result.body_pct + result.upper_wick_pct + result.lower_wick_pct
        assert abs(total - 1.0) < 0.01
