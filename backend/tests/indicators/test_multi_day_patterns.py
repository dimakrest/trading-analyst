"""Tests for multi-day pattern coordination."""

import numpy as np
import pytest

from app.indicators.multi_day_patterns import (
    PatternDuration,
    MultiDayPatternResult,
    THREE_CANDLE_ALIGNMENT,
    analyze_multi_day_patterns,
)
from app.indicators.three_candle_patterns import ThreeCandlePattern
from app.indicators.trend import TrendDirection


class TestPatternPriority:
    """Tests for pattern priority (3-day > 2-day > 1-day)."""

    def test_three_day_pattern_takes_priority(self):
        """Test that 3-day patterns are detected over 2-day and 1-day."""
        # Morning Star pattern (3-day)
        # Day 1: Red, Day 2: Doji, Day 3: Green closing above midpoint
        opens = [110, 97, 100]
        highs = [112, 98, 115]
        lows = [98, 96.5, 99]
        closes = [100, 97.3, 112]  # Day 3 closes above midpoint of Day 1 (105)

        result = analyze_multi_day_patterns(
            opens,
            highs,
            lows,
            closes,
            trend=TrendDirection.BEARISH,
        )

        assert result.pattern_name == "morning_star"
        assert result.duration == PatternDuration.THREE_DAY
        assert result.aligned_for_long is True

    def test_two_day_pattern_when_no_three_day(self):
        """Test that 2-day patterns are detected when no 3-day pattern exists."""
        # Piercing Line pattern (2-day) - no 3-day pattern
        opens = [100, 110, 95]  # Day 3 forms piercing line with Day 2
        highs = [101, 112, 107]
        lows = [99, 98, 94]
        closes = [100.5, 100, 106]  # Day 2 is red, Day 3 is green piercing

        result = analyze_multi_day_patterns(
            opens,
            highs,
            lows,
            closes,
            trend=TrendDirection.BEARISH,
        )

        assert result.pattern_name == "piercing_line"
        assert result.duration == PatternDuration.TWO_DAY
        assert result.aligned_for_long is True

    def test_one_day_pattern_when_no_multi_day(self):
        """Test that 1-day patterns are detected when no multi-day patterns exist."""
        # Unrelated candles that don't form 3-day or 2-day patterns
        # Last candle has hammer shape (long lower wick)
        opens = [100, 100, 100]
        highs = [102, 102, 101]
        lows = [98, 98, 90]
        closes = [101, 99, 100.5]

        result = analyze_multi_day_patterns(
            opens,
            highs,
            lows,
            closes,
            trend=TrendDirection.BEARISH,
        )

        # Should fall back to 1-day analysis (hammer)
        assert result.duration == PatternDuration.ONE_DAY

    def test_three_day_over_matching_two_day(self):
        """Test that 3-day takes priority even if 2-day pattern also matches."""
        # Three White Soldiers (3 consecutive green with higher closes)
        # The last 2 candles might also match a 2-day pattern, but 3-day wins
        opens = [100, 105, 110]
        highs = [106, 111, 118]
        lows = [99, 104, 109]
        closes = [105, 110, 117]  # All green, higher closes

        result = analyze_multi_day_patterns(
            opens,
            highs,
            lows,
            closes,
            trend=TrendDirection.BULLISH,
        )

        assert result.pattern_name == "three_white_soldiers"
        assert result.duration == PatternDuration.THREE_DAY


class TestThreeDayPatterns:
    """Tests for 3-day pattern detection and alignment."""

    def test_morning_star_alignment(self):
        """Test Morning Star is aligned for LONG."""
        opens = [110, 97, 100]
        highs = [112, 98, 115]
        lows = [98, 96.5, 99]
        closes = [100, 97.3, 112]

        result = analyze_multi_day_patterns(
            opens,
            highs,
            lows,
            closes,
            trend=TrendDirection.BEARISH,
        )

        assert result.aligned_for_long is True
        assert "bullish reversal" in result.explanation.lower()

    def test_evening_star_alignment(self):
        """Test Evening Star is aligned for SHORT."""
        # Green -> Doji -> Red closing below midpoint of first
        opens = [100, 112, 110]
        highs = [112, 114, 112]
        lows = [99, 111, 97]
        closes = [110, 112.1, 98]

        result = analyze_multi_day_patterns(
            opens,
            highs,
            lows,
            closes,
            trend=TrendDirection.BULLISH,
        )

        assert result.pattern_name == "evening_star"
        assert result.aligned_for_long is False

    def test_high_tight_flag_not_aligned(self):
        """Test High Tight Flag is NOT aligned (continuation, not reversal)."""
        # Strong green (4% gain) followed by 2 small consolidation candles
        # Lows stay above first candle's low
        opens = [100, 104.2, 104.1]
        highs = [104.5, 104.5, 104.3]
        lows = [99.5, 103.5, 103.6]
        closes = [104, 104, 103.9]

        result = analyze_multi_day_patterns(
            opens,
            highs,
            lows,
            closes,
            trend=TrendDirection.BULLISH,
        )

        assert result.pattern_name == "high_tight_flag"
        assert result.aligned_for_long is False
        assert "continuation" in result.explanation.lower()

    def test_three_white_soldiers_alignment(self):
        """Test Three White Soldiers is aligned for LONG."""
        opens = [100, 105, 110]
        highs = [106, 111, 118]
        lows = [99, 104, 109]
        closes = [105, 110, 117]

        result = analyze_multi_day_patterns(
            opens,
            highs,
            lows,
            closes,
            trend=TrendDirection.BULLISH,
        )

        assert result.pattern_name == "three_white_soldiers"
        assert result.aligned_for_long is True

    def test_three_black_crows_alignment(self):
        """Test Three Black Crows is aligned for SHORT."""
        opens = [120, 115, 110]
        highs = [121, 116, 111]
        lows = [114, 109, 104]
        closes = [115, 110, 105]

        result = analyze_multi_day_patterns(
            opens,
            highs,
            lows,
            closes,
            trend=TrendDirection.BEARISH,
        )

        assert result.pattern_name == "three_black_crows"
        assert result.aligned_for_long is False

    def test_three_inside_up_alignment(self):
        """Test Three Inside Up is aligned for LONG."""
        # Day 1: Red candle
        # Day 2: Small green inside day 1
        # Day 3: Green breaks above day 1's open
        opens = [110, 102, 105]
        highs = [112, 105, 115]
        lows = [98, 101, 104]
        closes = [100, 104, 112]  # Day 3 closes above 110

        result = analyze_multi_day_patterns(
            opens,
            highs,
            lows,
            closes,
            trend=TrendDirection.BEARISH,
        )

        assert result.pattern_name == "three_inside_up"
        assert result.aligned_for_long is True

    def test_three_inside_down_alignment(self):
        """Test Three Inside Down is aligned for SHORT."""
        # Day 1: Green candle
        # Day 2: Small red inside day 1
        # Day 3: Red breaks below day 1's open
        opens = [100, 108, 105]
        highs = [112, 109, 106]
        lows = [99, 104, 94]
        closes = [110, 105, 95]  # Day 3 closes below 100

        result = analyze_multi_day_patterns(
            opens,
            highs,
            lows,
            closes,
            trend=TrendDirection.BULLISH,
        )

        assert result.pattern_name == "three_inside_down"
        assert result.aligned_for_long is False


class TestTwoDayPatterns:
    """Tests for 2-day pattern detection through multi-day interface."""

    def test_piercing_line_via_multi_day(self):
        """Test Piercing Line detection."""
        # No 3-day pattern, but has 2-day piercing line
        opens = [105, 110, 95]
        highs = [106, 112, 107]
        lows = [104, 98, 94]
        closes = [105.5, 100, 106]  # Days 2-3 form piercing line

        result = analyze_multi_day_patterns(
            opens,
            highs,
            lows,
            closes,
            trend=TrendDirection.BEARISH,
        )

        assert result.pattern_name == "piercing_line"
        assert result.duration == PatternDuration.TWO_DAY
        assert result.aligned_for_long is True

    def test_dark_cloud_cover_via_multi_day(self):
        """Test Dark Cloud Cover detection."""
        # No 3-day pattern, but has 2-day dark cloud cover
        opens = [95, 100, 112]
        highs = [96, 111, 114]
        lows = [94, 99, 103]
        closes = [95.5, 110, 104]  # Days 2-3 form dark cloud cover

        result = analyze_multi_day_patterns(
            opens,
            highs,
            lows,
            closes,
            trend=TrendDirection.BULLISH,
        )

        assert result.pattern_name == "dark_cloud_cover"
        assert result.duration == PatternDuration.TWO_DAY
        assert result.aligned_for_long is False

    def test_bullish_harami_via_multi_day(self):
        """Test Bullish Harami detection."""
        # No 3-day pattern, but has 2-day bullish harami
        opens = [95, 110, 102]
        highs = [96, 112, 105]
        lows = [94, 98, 101]
        closes = [95.5, 100, 104]  # Days 2-3 form bullish harami

        result = analyze_multi_day_patterns(
            opens,
            highs,
            lows,
            closes,
            trend=TrendDirection.BEARISH,
        )

        assert result.pattern_name == "bullish_harami"
        assert result.duration == PatternDuration.TWO_DAY
        assert result.aligned_for_long is True

    def test_bearish_harami_via_multi_day(self):
        """Test Bearish Harami detection."""
        # No 3-day pattern, but has 2-day bearish harami
        opens = [105, 100, 108]
        highs = [106, 112, 109]
        lows = [104, 99, 104]
        closes = [105.5, 110, 105]  # Days 2-3 form bearish harami

        result = analyze_multi_day_patterns(
            opens,
            highs,
            lows,
            closes,
            trend=TrendDirection.BULLISH,
        )

        assert result.pattern_name == "bearish_harami"
        assert result.duration == PatternDuration.TWO_DAY
        assert result.aligned_for_long is False


class TestOneDayPatterns:
    """Tests for 1-day pattern fallback through multi-day interface."""

    def test_hammer_in_downtrend(self):
        """Test Hammer detection with context."""
        # Last candle has hammer shape (long lower wick, small body)
        opens = [100, 100, 100]
        highs = [103, 103, 102]
        lows = [97, 97, 90]
        closes = [102, 98, 101.5]

        result = analyze_multi_day_patterns(
            opens,
            highs,
            lows,
            closes,
            trend=TrendDirection.BEARISH,
        )

        assert result.duration == PatternDuration.ONE_DAY
        assert result.pattern_name == "hammer"
        assert result.aligned_for_long is True

    def test_shooting_star_in_uptrend(self):
        """Test Shooting Star detection with context."""
        # Last candle has shooting star shape (long upper wick, small body)
        opens = [100, 100, 101.5]
        highs = [103, 103, 112]
        lows = [97, 97, 100]
        closes = [102, 98, 100]

        result = analyze_multi_day_patterns(
            opens,
            highs,
            lows,
            closes,
            trend=TrendDirection.BULLISH,
        )

        assert result.duration == PatternDuration.ONE_DAY
        assert result.pattern_name == "shooting_star"
        assert result.aligned_for_long is False

    def test_doji_in_downtrend_aligned_for_long(self):
        """Test Doji in downtrend is aligned for LONG."""
        # Last candle is doji (open == close)
        opens = [100, 100, 100]
        highs = [101, 101, 105]
        lows = [99, 99, 95]
        closes = [100.5, 100.5, 100]

        result = analyze_multi_day_patterns(
            opens,
            highs,
            lows,
            closes,
            trend=TrendDirection.BEARISH,
        )

        assert result.duration == PatternDuration.ONE_DAY
        assert result.pattern_name == "doji"
        assert result.aligned_for_long is True

    def test_engulfing_bullish_via_one_day(self):
        """Test Bullish Engulfing detected through 1-day path."""
        # Last candle engulfs previous
        opens = [100, 100, 95]
        highs = [101, 101, 115]
        lows = [99, 99, 94]
        closes = [100.5, 97, 112]

        result = analyze_multi_day_patterns(
            opens,
            highs,
            lows,
            closes,
            trend=TrendDirection.BEARISH,
        )

        assert result.aligned_for_long is True


class TestEdgeCases:
    """Edge case tests."""

    def test_minimum_data_for_full_analysis(self):
        """Test with exactly 3 candles."""
        opens = [110, 97, 100]
        highs = [112, 98, 115]
        lows = [98, 96.5, 99]
        closes = [100, 97.3, 112]

        result = analyze_multi_day_patterns(
            opens,
            highs,
            lows,
            closes,
            trend=TrendDirection.BEARISH,
        )

        assert result.pattern_name == "morning_star"

    def test_two_candles_skips_three_day(self):
        """Test with only 2 candles skips 3-day detection."""
        opens = [110, 95]
        highs = [112, 107]
        lows = [98, 94]
        closes = [100, 106]

        result = analyze_multi_day_patterns(
            opens,
            highs,
            lows,
            closes,
            trend=TrendDirection.BEARISH,
        )

        assert result.pattern_name == "piercing_line"
        assert result.duration == PatternDuration.TWO_DAY

    def test_one_candle_only_single_day(self):
        """Test with only 1 candle uses single-day analysis."""
        opens = [100]
        highs = [101]
        lows = [90]  # Hammer shape
        closes = [100.5]

        result = analyze_multi_day_patterns(
            opens,
            highs,
            lows,
            closes,
            trend=TrendDirection.BEARISH,
        )

        assert result.duration == PatternDuration.ONE_DAY

    def test_empty_data_returns_insufficient_data(self):
        """Test with empty arrays returns no data result."""
        result = analyze_multi_day_patterns(
            [],
            [],
            [],
            [],
            trend=TrendDirection.NEUTRAL,
        )

        assert result.pattern_name == "none"
        assert result.duration == PatternDuration.ONE_DAY
        assert result.aligned_for_long is False
        assert "Insufficient data" in result.explanation

    def test_accepts_numpy_arrays(self):
        """Test that numpy arrays are accepted."""
        opens = np.array([110, 97, 100])
        highs = np.array([112, 98, 115])
        lows = np.array([98, 96.5, 99])
        closes = np.array([100, 97.3, 112])

        result = analyze_multi_day_patterns(
            opens,
            highs,
            lows,
            closes,
            trend=TrendDirection.BEARISH,
        )

        assert result.pattern_name == "morning_star"
        assert result.duration == PatternDuration.THREE_DAY

    def test_longer_arrays_use_last_candles(self):
        """Test that longer arrays correctly use last N candles."""
        # First 5 candles are noise, last 3 form morning star
        opens = [100, 101, 102, 103, 110, 97, 100]
        highs = [101, 102, 103, 104, 112, 98, 115]
        lows = [99, 100, 101, 102, 98, 96.5, 99]
        closes = [100.5, 101.5, 102.5, 103.5, 100, 97.3, 112]

        result = analyze_multi_day_patterns(
            opens,
            highs,
            lows,
            closes,
            trend=TrendDirection.BEARISH,
        )

        assert result.pattern_name == "morning_star"
        assert result.duration == PatternDuration.THREE_DAY


class TestPatternDurationEnum:
    """Tests for PatternDuration enum."""

    def test_enum_values(self):
        """Test that enum has correct string values."""
        assert PatternDuration.ONE_DAY.value == "1-day"
        assert PatternDuration.TWO_DAY.value == "2-day"
        assert PatternDuration.THREE_DAY.value == "3-day"

    def test_enum_is_string(self):
        """Test that enum values work as strings."""
        assert PatternDuration.ONE_DAY == "1-day"
        assert PatternDuration.TWO_DAY == "2-day"
        assert PatternDuration.THREE_DAY == "3-day"


class TestMultiDayPatternResultDataclass:
    """Tests for MultiDayPatternResult dataclass."""

    def test_dataclass_fields(self):
        """Test that dataclass has all expected fields."""
        result = MultiDayPatternResult(
            pattern_name="morning_star",
            duration=PatternDuration.THREE_DAY,
            aligned_for_long=True,
            explanation="Morning Star (3-day) - classic bullish reversal",
        )

        assert result.pattern_name == "morning_star"
        assert result.duration == PatternDuration.THREE_DAY
        assert result.aligned_for_long is True
        assert "Morning Star" in result.explanation


class TestThreeCandleAlignmentMapping:
    """Tests for THREE_CANDLE_ALIGNMENT constant."""

    def test_all_patterns_have_alignment(self):
        """Test that all 3-candle patterns have alignment defined."""
        for pattern in ThreeCandlePattern:
            if pattern != ThreeCandlePattern.NONE:
                assert pattern in THREE_CANDLE_ALIGNMENT, f"Missing alignment for {pattern}"

    def test_alignment_tuple_structure(self):
        """Test that alignment tuples have correct structure."""
        for pattern, alignment in THREE_CANDLE_ALIGNMENT.items():
            assert len(alignment) == 2, f"Alignment for {pattern} should have 2 elements"
            assert isinstance(alignment[0], bool), f"aligned_for_long for {pattern} should be bool"
            assert isinstance(alignment[1], str), f"explanation for {pattern} should be str"

    def test_bullish_patterns_align_for_long(self):
        """Test that bullish reversal patterns align for LONG."""
        bullish_patterns = [
            ThreeCandlePattern.MORNING_STAR,
            ThreeCandlePattern.THREE_WHITE_SOLDIERS,
            ThreeCandlePattern.THREE_INSIDE_UP,
        ]
        for pattern in bullish_patterns:
            aligned_long, _ = THREE_CANDLE_ALIGNMENT[pattern]
            assert aligned_long is True, f"{pattern} should be aligned for LONG"

    def test_bearish_patterns_align_for_short(self):
        """Test that bearish reversal patterns are not aligned for LONG."""
        bearish_patterns = [
            ThreeCandlePattern.EVENING_STAR,
            ThreeCandlePattern.THREE_BLACK_CROWS,
            ThreeCandlePattern.THREE_INSIDE_DOWN,
        ]
        for pattern in bearish_patterns:
            aligned_long, _ = THREE_CANDLE_ALIGNMENT[pattern]
            assert aligned_long is False, f"{pattern} should NOT be aligned for LONG"

    def test_continuation_patterns_not_aligned(self):
        """Test that continuation patterns are not aligned for mean reversion."""
        continuation_patterns = [
            ThreeCandlePattern.HIGH_TIGHT_FLAG,
        ]
        for pattern in continuation_patterns:
            aligned_long, _ = THREE_CANDLE_ALIGNMENT[pattern]
            assert aligned_long is False, f"{pattern} should NOT be aligned for LONG"


class TestTrendContextPropagation:
    """Tests for trend context propagation to 1-day patterns."""

    def test_hammer_in_downtrend_is_bullish(self):
        """Test that hammer in downtrend is interpreted as bullish reversal."""
        # Last candle has hammer shape (long lower wick, small body)
        opens = [100, 100, 100]
        highs = [103, 103, 102]
        lows = [97, 97, 90]
        closes = [102, 98, 101.5]

        result = analyze_multi_day_patterns(
            opens,
            highs,
            lows,
            closes,
            trend=TrendDirection.BEARISH,
        )

        assert result.aligned_for_long is True
        assert "downtrend" in result.explanation.lower()

    def test_hammer_in_uptrend_is_hanging_man(self):
        """Test that hammer shape in uptrend becomes hanging man (bearish)."""
        # Same hammer shape, but in uptrend context becomes hanging man
        opens = [100, 100, 100]
        highs = [103, 103, 102]
        lows = [97, 97, 90]
        closes = [102, 98, 101.5]

        result = analyze_multi_day_patterns(
            opens,
            highs,
            lows,
            closes,
            trend=TrendDirection.BULLISH,
        )

        # In uptrend, hammer shape becomes hanging man (bearish)
        assert result.pattern_name == "hanging_man"
        assert result.aligned_for_long is False

    def test_shooting_star_in_uptrend_is_bearish(self):
        """Test that shooting star in uptrend is interpreted as bearish reversal."""
        # Last candle has shooting star shape (long upper wick, small body)
        opens = [100, 100, 101.5]
        highs = [103, 103, 112]
        lows = [97, 97, 100]
        closes = [102, 98, 100]

        result = analyze_multi_day_patterns(
            opens,
            highs,
            lows,
            closes,
            trend=TrendDirection.BULLISH,
        )

        assert result.aligned_for_long is False
        assert "uptrend" in result.explanation.lower()

    def test_shooting_star_in_downtrend_is_inverted_hammer(self):
        """Test that shooting star shape in downtrend becomes inverted hammer (bullish)."""
        # Same shooting star shape, but in downtrend context becomes inverted hammer
        opens = [100, 100, 101.5]
        highs = [103, 103, 112]
        lows = [97, 97, 100]
        closes = [102, 98, 100]

        result = analyze_multi_day_patterns(
            opens,
            highs,
            lows,
            closes,
            trend=TrendDirection.BEARISH,
        )

        # In downtrend, shooting star shape becomes inverted hammer (bullish)
        assert result.pattern_name == "inverted_hammer"
        assert result.aligned_for_long is True

