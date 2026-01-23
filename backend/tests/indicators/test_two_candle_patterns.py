"""Tests for two-candle pattern detection."""

import numpy as np
import pytest

from app.indicators.two_candle_patterns import (
    TwoCandlePattern,
    TwoCandleAnalysis,
    analyze_two_candles,
    TWEEZER_TOLERANCE,
)


class TestPiercingLine:
    """Tests for Piercing Line pattern detection."""

    def test_piercing_line_detection(self):
        """Test basic piercing line detection."""
        # Day 1: Red candle (open high, close low)
        # Day 2: Green candle gaps down, closes above midpoint of day 1
        opens = [110, 95]  # Day 2 opens below day 1 close
        highs = [112, 107]
        lows = [98, 94]
        closes = [100, 106]  # Day 2 closes above midpoint (105) but below day 1 open

        result = analyze_two_candles(opens, highs, lows, closes)

        assert result.pattern == TwoCandlePattern.PIERCING_LINE
        assert result.aligned_for_long is True
        assert result.aligned_for_short is False
        assert "bullish reversal" in result.explanation.lower()

    def test_piercing_line_requires_close_above_midpoint(self):
        """Test that close must be above midpoint."""
        opens = [110, 95]
        highs = [112, 103]
        lows = [98, 94]
        closes = [100, 102]  # Below midpoint (105)

        result = analyze_two_candles(opens, highs, lows, closes)

        assert result.pattern != TwoCandlePattern.PIERCING_LINE

    def test_piercing_line_requires_close_below_first_open(self):
        """Test that close must be below first candle's open."""
        opens = [110, 95]
        highs = [112, 115]
        lows = [98, 94]
        closes = [100, 112]  # Closes above day 1 open (110) - this is engulfing, not piercing

        result = analyze_two_candles(opens, highs, lows, closes)

        assert result.pattern != TwoCandlePattern.PIERCING_LINE

    def test_piercing_line_requires_open_below_first_close(self):
        """Test that second candle must open below first close."""
        opens = [110, 101]  # Day 2 opens above day 1 close (100)
        highs = [112, 107]
        lows = [98, 100]
        closes = [100, 106]

        result = analyze_two_candles(opens, highs, lows, closes)

        assert result.pattern != TwoCandlePattern.PIERCING_LINE

    def test_piercing_line_requires_first_red_second_green(self):
        """Test that first candle must be red and second must be green."""
        # Both green candles
        opens = [100, 95]
        highs = [112, 107]
        lows = [98, 94]
        closes = [110, 106]  # First is green

        result = analyze_two_candles(opens, highs, lows, closes)

        assert result.pattern != TwoCandlePattern.PIERCING_LINE


class TestDarkCloudCover:
    """Tests for Dark Cloud Cover pattern detection."""

    def test_dark_cloud_cover_detection(self):
        """Test basic dark cloud cover detection."""
        # Day 1: Green candle
        # Day 2: Red candle gaps up, closes below midpoint of day 1
        opens = [100, 112]  # Day 2 opens above day 1 close
        highs = [111, 114]
        lows = [99, 103]
        closes = [110, 104]  # Day 2 closes below midpoint (105) but above day 1 open

        result = analyze_two_candles(opens, highs, lows, closes)

        assert result.pattern == TwoCandlePattern.DARK_CLOUD_COVER
        assert result.aligned_for_long is False
        assert result.aligned_for_short is True
        assert "bearish reversal" in result.explanation.lower()

    def test_dark_cloud_cover_requires_close_below_midpoint(self):
        """Test that close must be below midpoint."""
        opens = [100, 112]
        highs = [111, 114]
        lows = [99, 105]
        closes = [110, 107]  # Above midpoint (105)

        result = analyze_two_candles(opens, highs, lows, closes)

        assert result.pattern != TwoCandlePattern.DARK_CLOUD_COVER

    def test_dark_cloud_cover_requires_close_above_first_open(self):
        """Test that close must be above first candle's open."""
        opens = [100, 112]
        highs = [111, 114]
        lows = [99, 95]
        closes = [110, 98]  # Closes below day 1 open (100) - this is engulfing, not dark cloud

        result = analyze_two_candles(opens, highs, lows, closes)

        assert result.pattern != TwoCandlePattern.DARK_CLOUD_COVER

    def test_dark_cloud_cover_requires_open_above_first_close(self):
        """Test that second candle must open above first close."""
        opens = [100, 108]  # Day 2 opens below day 1 close (110)
        highs = [111, 112]
        lows = [99, 103]
        closes = [110, 104]

        result = analyze_two_candles(opens, highs, lows, closes)

        assert result.pattern != TwoCandlePattern.DARK_CLOUD_COVER

    def test_dark_cloud_cover_requires_first_green_second_red(self):
        """Test that first candle must be green and second must be red."""
        # Both red candles
        opens = [110, 112]
        highs = [111, 114]
        lows = [99, 103]
        closes = [100, 104]  # First is red

        result = analyze_two_candles(opens, highs, lows, closes)

        assert result.pattern != TwoCandlePattern.DARK_CLOUD_COVER


class TestHaramiPatterns:
    """Tests for Harami pattern detection."""

    def test_bullish_harami_detection(self):
        """Test bullish harami detection."""
        # Day 1: Large red candle
        # Day 2: Small green candle contained within day 1's body
        opens = [110, 102]
        highs = [112, 105]
        lows = [98, 101]
        closes = [100, 104]  # Small green inside large red

        result = analyze_two_candles(opens, highs, lows, closes)

        assert result.pattern == TwoCandlePattern.BULLISH_HARAMI
        assert result.aligned_for_long is True
        assert result.aligned_for_short is False

    def test_bearish_harami_detection(self):
        """Test bearish harami detection."""
        # Day 1: Large green candle
        # Day 2: Small red candle contained within day 1's body
        opens = [100, 108]
        highs = [112, 109]
        lows = [99, 104]
        closes = [110, 105]  # Small red inside large green

        result = analyze_two_candles(opens, highs, lows, closes)

        assert result.pattern == TwoCandlePattern.BEARISH_HARAMI
        assert result.aligned_for_long is False
        assert result.aligned_for_short is True

    def test_bullish_harami_requires_smaller_body(self):
        """Test that harami requires second body to be smaller."""
        # Day 2 body is larger than day 1
        opens = [110, 95]
        highs = [112, 115]
        lows = [98, 94]
        closes = [105, 110]  # Day 2 body (15) > Day 1 body (5)

        result = analyze_two_candles(opens, highs, lows, closes)

        assert result.pattern != TwoCandlePattern.BULLISH_HARAMI

    def test_bearish_harami_requires_smaller_body(self):
        """Test that bearish harami requires second body to be smaller."""
        # Day 2 body is larger than day 1
        opens = [100, 115]
        highs = [106, 116]
        lows = [99, 98]
        closes = [105, 100]  # Day 2 body (15) > Day 1 body (5)

        result = analyze_two_candles(opens, highs, lows, closes)

        assert result.pattern != TwoCandlePattern.BEARISH_HARAMI

    def test_bullish_harami_requires_body_inside(self):
        """Test that second candle body must be inside first candle body."""
        # Day 2 open is outside day 1 body
        opens = [110, 99]  # Opens below day 1 close (100)
        highs = [112, 105]
        lows = [98, 98]
        closes = [100, 104]

        result = analyze_two_candles(opens, highs, lows, closes)

        assert result.pattern != TwoCandlePattern.BULLISH_HARAMI

    def test_bearish_harami_requires_body_inside(self):
        """Test that second candle body must be inside first candle body."""
        # Day 2 open is outside day 1 body
        opens = [100, 112]  # Opens above day 1 close (110)
        highs = [112, 113]
        lows = [99, 104]
        closes = [110, 105]

        result = analyze_two_candles(opens, highs, lows, closes)

        assert result.pattern != TwoCandlePattern.BEARISH_HARAMI


class TestTweezerPatterns:
    """Tests for Tweezer pattern detection."""

    def test_tweezer_bottoms_detection(self):
        """Test tweezer bottoms detection."""
        # Two candles with matching lows, first red then green
        opens = [105, 100]
        highs = [107, 108]
        lows = [100, 100.1]  # Nearly identical lows (within 0.2% tolerance)
        closes = [101, 107]

        result = analyze_two_candles(opens, highs, lows, closes)

        assert result.pattern == TwoCandlePattern.TWEEZER_BOTTOMS
        assert result.aligned_for_long is True
        assert result.aligned_for_short is False

    def test_tweezer_tops_detection(self):
        """Test tweezer tops detection."""
        # Two candles with matching highs, first green then red
        # Must NOT match Dark Cloud Cover or Bearish Harami
        # Dark Cloud: o2 > c1 AND c2 < midpoint AND c2 > o1
        # Bearish Harami: c2_body < c1_body AND o2 < c1 AND o2 > o1 AND c2 < c1 AND c2 > o1
        # Solution: Make c2 <= o1 so it's NOT inside the first candle's body (avoids Harami)
        # and make o2 <= c1 so it doesn't match Dark Cloud
        opens = [100, 109]  # o2 < c1 (109 < 110), so not Dark Cloud
        highs = [110, 110.1]  # Nearly identical highs
        lows = [99, 95]
        closes = [110, 98]  # c2 < o1 (98 < 100), so not inside body (not Harami)

        result = analyze_two_candles(opens, highs, lows, closes)

        assert result.pattern == TwoCandlePattern.TWEEZER_TOPS
        assert result.aligned_for_long is False
        assert result.aligned_for_short is True

    def test_tweezer_bottoms_requires_tolerance(self):
        """Test that lows must be within tolerance."""
        opens = [105, 100]
        highs = [107, 108]
        lows = [100, 101]  # 1% difference, beyond 0.2% tolerance
        closes = [101, 107]

        result = analyze_two_candles(opens, highs, lows, closes)

        assert result.pattern != TwoCandlePattern.TWEEZER_BOTTOMS

    def test_tweezer_tops_requires_tolerance(self):
        """Test that highs must be within tolerance."""
        opens = [100, 110]
        highs = [110, 112]  # 1.8% difference, beyond 0.2% tolerance
        lows = [99, 102]
        closes = [109, 103]

        result = analyze_two_candles(opens, highs, lows, closes)

        assert result.pattern != TwoCandlePattern.TWEEZER_TOPS

    def test_tweezer_bottoms_requires_red_then_green(self):
        """Test that tweezer bottoms requires first red, second green."""
        # Both green
        opens = [100, 100]
        highs = [107, 108]
        lows = [99, 99.1]
        closes = [106, 107]

        result = analyze_two_candles(opens, highs, lows, closes)

        assert result.pattern != TwoCandlePattern.TWEEZER_BOTTOMS

    def test_tweezer_tops_requires_green_then_red(self):
        """Test that tweezer tops requires first green, second red."""
        # Both red
        opens = [110, 108]
        highs = [111, 111.1]
        lows = [102, 101]
        closes = [105, 102]

        result = analyze_two_candles(opens, highs, lows, closes)

        assert result.pattern != TwoCandlePattern.TWEEZER_TOPS

    def test_tweezer_bottoms_exact_match(self):
        """Test tweezer bottoms with exactly matching lows."""
        opens = [105, 100]
        highs = [107, 108]
        lows = [100, 100]  # Exactly matching lows
        closes = [101, 107]

        result = analyze_two_candles(opens, highs, lows, closes)

        assert result.pattern == TwoCandlePattern.TWEEZER_BOTTOMS

    def test_tweezer_tops_exact_match(self):
        """Test tweezer tops with exactly matching highs."""
        # Must NOT match Dark Cloud Cover or Bearish Harami
        # Make c2 <= o1 to avoid being inside first candle's body (no Harami)
        opens = [100, 109]
        highs = [110, 110]  # Exactly matching highs
        lows = [99, 95]
        closes = [110, 98]  # c2 < o1 (98 < 100), not inside body

        result = analyze_two_candles(opens, highs, lows, closes)

        assert result.pattern == TwoCandlePattern.TWEEZER_TOPS


class TestPatternPriority:
    """Tests for pattern detection priority."""

    def test_piercing_line_priority_over_tweezer_bottoms(self):
        """Test that piercing line is detected before tweezer bottoms when both match."""
        # This data matches piercing line and could match tweezer bottoms
        # but piercing line has higher priority
        opens = [110, 95]
        highs = [112, 107]
        lows = [98, 98]  # Matching lows
        closes = [100, 106]  # Also a piercing line

        result = analyze_two_candles(opens, highs, lows, closes)

        # Piercing line should be detected due to priority order
        assert result.pattern == TwoCandlePattern.PIERCING_LINE


class TestEdgeCases:
    """Edge case tests."""

    def test_insufficient_data_raises_error(self):
        """Test that fewer than 2 candles raises ValueError."""
        with pytest.raises(ValueError, match="at least 2 candles"):
            analyze_two_candles([100], [105], [99], [104])

    def test_empty_data_raises_error(self):
        """Test that empty data raises ValueError."""
        with pytest.raises(ValueError, match="at least 2 candles"):
            analyze_two_candles([], [], [], [])

    def test_no_pattern_returns_none(self):
        """Test that non-matching candles return NONE."""
        opens = [100, 102]
        highs = [105, 107]
        lows = [99, 101]
        closes = [104, 106]  # Two green candles, no reversal pattern

        result = analyze_two_candles(opens, highs, lows, closes)

        assert result.pattern == TwoCandlePattern.NONE
        assert result.aligned_for_long is False
        assert result.aligned_for_short is False
        assert result.explanation == ""

    def test_accepts_numpy_arrays(self):
        """Test that numpy arrays are accepted."""
        opens = np.array([110, 95])
        highs = np.array([112, 107])
        lows = np.array([98, 94])
        closes = np.array([100, 106])

        result = analyze_two_candles(opens, highs, lows, closes)

        assert result.pattern == TwoCandlePattern.PIERCING_LINE

    def test_accepts_longer_arrays(self):
        """Test that arrays longer than 2 use only last 2 candles."""
        # First 3 candles are noise, last 2 form piercing line
        opens = [100, 101, 110, 95]
        highs = [105, 106, 112, 107]
        lows = [99, 100, 98, 94]
        closes = [104, 105, 100, 106]

        result = analyze_two_candles(opens, highs, lows, closes)

        assert result.pattern == TwoCandlePattern.PIERCING_LINE

    def test_doji_candles_no_pattern(self):
        """Test that doji candles (close == open) don't trigger patterns incorrectly."""
        # Doji candles - neither red nor green
        opens = [100, 100]
        highs = [105, 105]
        lows = [95, 95]
        closes = [100, 100]  # Both doji

        result = analyze_two_candles(opens, highs, lows, closes)

        assert result.pattern == TwoCandlePattern.NONE

    def test_zero_low_handling(self):
        """Test handling of zero low price (edge case for tweezer calculation)."""
        # This shouldn't happen in real data but tests division handling
        opens = [10, 5]
        highs = [12, 8]
        lows = [0, 0.001]  # Near-zero lows
        closes = [5, 7]  # Red then green

        # Should not crash
        result = analyze_two_candles(opens, highs, lows, closes)
        assert result is not None

    def test_zero_high_handling(self):
        """Test handling of zero high price (edge case for tweezer calculation)."""
        opens = [5, 10]
        highs = [0, 0.001]  # Near-zero highs (unrealistic but test coverage)
        lows = [3, 2]
        closes = [8, 5]  # Green then red

        # Should not crash
        result = analyze_two_candles(opens, highs, lows, closes)
        assert result is not None


class TestTwoCandleAnalysisDataclass:
    """Tests for TwoCandleAnalysis dataclass."""

    def test_dataclass_fields(self):
        """Test that dataclass has all expected fields."""
        analysis = TwoCandleAnalysis(
            pattern=TwoCandlePattern.PIERCING_LINE,
            aligned_for_long=True,
            aligned_for_short=False,
            explanation="Test explanation",
        )

        assert analysis.pattern == TwoCandlePattern.PIERCING_LINE
        assert analysis.aligned_for_long is True
        assert analysis.aligned_for_short is False
        assert analysis.explanation == "Test explanation"


class TestTwoCandlePatternEnum:
    """Tests for TwoCandlePattern enum."""

    def test_enum_values(self):
        """Test that enum has correct string values."""
        assert TwoCandlePattern.PIERCING_LINE.value == "piercing_line"
        assert TwoCandlePattern.DARK_CLOUD_COVER.value == "dark_cloud_cover"
        assert TwoCandlePattern.BULLISH_HARAMI.value == "bullish_harami"
        assert TwoCandlePattern.BEARISH_HARAMI.value == "bearish_harami"
        assert TwoCandlePattern.TWEEZER_BOTTOMS.value == "tweezer_bottoms"
        assert TwoCandlePattern.TWEEZER_TOPS.value == "tweezer_tops"
        assert TwoCandlePattern.NONE.value == "none"

    def test_enum_is_string(self):
        """Test that enum values work as strings via .value."""
        assert TwoCandlePattern.PIERCING_LINE.value == "piercing_line"
        # String comparison with == works due to str inheritance
        assert TwoCandlePattern.PIERCING_LINE == "piercing_line"


class TestConstants:
    """Tests for module constants."""

    def test_tweezer_tolerance_value(self):
        """Test that TWEEZER_TOLERANCE has expected value."""
        assert TWEEZER_TOLERANCE == 0.002
        assert TWEEZER_TOLERANCE == 0.2 / 100  # 0.2%
