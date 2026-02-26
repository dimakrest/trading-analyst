"""Tests for three-candle pattern detection."""

import numpy as np
import pytest

from app.indicators.three_candle_patterns import (
    ThreeCandlePattern,
    analyze_three_candles,
)


class TestThreeCandlePatterns:
    def test_morning_star_detection(self):
        """Test Morning Star pattern detection."""
        # Red -> Doji -> Green
        # First candle: large red, second: small doji (NOT inside), third: green closing above midpoint
        opens = [110, 97, 100]
        highs = [112, 98, 115]
        lows = [98, 96.5, 99]
        closes = [100, 97.3, 112]  # Green closes above midpoint of first (105)

        result = analyze_three_candles(opens, highs, lows, closes)
        assert result.pattern == ThreeCandlePattern.MORNING_STAR

    def test_evening_star_detection(self):
        """Test Evening Star pattern detection."""
        # Green -> Doji -> Red
        # First candle: large green, second: small doji, third: red closing below midpoint
        opens = [100, 112, 111.5]
        highs = [112, 113, 112]
        lows = [98, 111.5, 95]
        closes = [110, 112.2, 98]  # Red closes below midpoint of first (105)

        result = analyze_three_candles(opens, highs, lows, closes)
        assert result.pattern == ThreeCandlePattern.EVENING_STAR

    def test_three_white_soldiers(self):
        """Test Three White Soldiers pattern detection."""
        # 3 consecutive green candles with higher closes
        opens = [100, 105, 110]
        highs = [106, 111, 116]
        lows = [99, 104, 109]
        closes = [105, 110, 115]

        result = analyze_three_candles(opens, highs, lows, closes)
        assert result.pattern == ThreeCandlePattern.THREE_WHITE_SOLDIERS

    def test_three_black_crows(self):
        """Test Three Black Crows pattern detection."""
        # 3 consecutive red candles with lower closes
        opens = [115, 110, 105]
        highs = [116, 111, 106]
        lows = [109, 104, 99]
        closes = [110, 105, 100]

        result = analyze_three_candles(opens, highs, lows, closes)
        assert result.pattern == ThreeCandlePattern.THREE_BLACK_CROWS

    def test_high_tight_flag(self):
        """Test High Tight Flag pattern detection."""
        # Strong green (>3%) followed by 2 small consolidation candles
        # First candle must be strong green, then 2 small candles with low body_pct
        opens = [100, 105, 104.8]
        highs = [105.5, 105.3, 105.2]
        lows = [100, 104.7, 104.5]
        closes = [105, 105.1, 104.9]  # 5% move, then small candles holding above first low

        result = analyze_three_candles(opens, highs, lows, closes)
        assert result.pattern == ThreeCandlePattern.HIGH_TIGHT_FLAG

    def test_narrative_generation(self):
        """Test that narrative is generated."""
        opens = [100, 101, 102]
        highs = [105, 106, 107]
        lows = [99, 100, 101]
        closes = [104, 105, 106]

        result = analyze_three_candles(opens, highs, lows, closes)
        assert result.narrative is not None
        assert len(result.narrative) > 0
        assert "Candle 1" in result.narrative
        assert "Candle 2" in result.narrative
        assert "Candle 3" in result.narrative

    def test_insufficient_data_raises(self):
        """Test that insufficient data raises ValueError."""
        with pytest.raises(ValueError, match="at least 3 candles"):
            analyze_three_candles([100, 101], [105, 106], [99, 100], [104, 105])

    def test_volume_context_in_narrative(self):
        """Test volume context is added to narrative."""
        opens = [100, 101, 102]
        highs = [105, 106, 107]
        lows = [99, 100, 101]
        closes = [104, 105, 106]
        volumes = [1000, 1000, 2000]  # High volume on last candle

        result = analyze_three_candles(opens, highs, lows, closes, volumes)
        assert "volume" in result.narrative.lower() or "Volume" in result.narrative

    def test_three_inside_up_detection(self):
        """Test Three Inside Up pattern detection."""
        # Red -> Small green inside -> Green breaks above
        opens = [110, 105, 106]
        highs = [112, 108, 115]
        lows = [102, 104, 105]
        closes = [104, 107, 112]  # Last green breaks above first candle's open (110)

        result = analyze_three_candles(opens, highs, lows, closes)
        assert result.pattern == ThreeCandlePattern.THREE_INSIDE_UP

    def test_three_inside_down_detection(self):
        """Test Three Inside Down pattern detection."""
        # Green -> Small red inside -> Red breaks below
        opens = [100, 108, 107]
        highs = [110, 109, 108]
        lows = [99, 106, 95]
        closes = [109, 107, 98]  # Last red breaks below first candle's open (100)

        result = analyze_three_candles(opens, highs, lows, closes)
        assert result.pattern == ThreeCandlePattern.THREE_INSIDE_DOWN

    def test_no_pattern_returns_none(self):
        """Test that random candles return NONE pattern."""
        # Random pattern that doesn't match any specific pattern
        # Mix of green and red without consecutive pattern
        opens = [100, 103, 102]
        highs = [105, 106, 107]
        lows = [99, 101, 100]
        closes = [103, 102, 105]  # Green, Red, Green - no specific pattern

        result = analyze_three_candles(opens, highs, lows, closes)
        assert result.pattern == ThreeCandlePattern.NONE

    def test_candle_analysis_populated(self):
        """Test that individual candle analysis is populated."""
        opens = [100, 101, 102]
        highs = [105, 106, 107]
        lows = [99, 100, 101]
        closes = [104, 105, 106]

        result = analyze_three_candles(opens, highs, lows, closes)

        # All three candle analyses should be populated
        assert result.candle_1 is not None
        assert result.candle_2 is not None
        assert result.candle_3 is not None

        # Each should have pattern information
        assert result.candle_1.pattern is not None
        assert result.candle_2.pattern is not None
        assert result.candle_3.pattern is not None

    def test_accepts_numpy_arrays(self):
        """Test that function accepts numpy arrays."""
        opens = np.array([100, 101, 102], dtype=float)
        highs = np.array([105, 106, 107], dtype=float)
        lows = np.array([99, 100, 101], dtype=float)
        closes = np.array([104, 105, 106], dtype=float)

        result = analyze_three_candles(opens, highs, lows, closes)
        assert result is not None
        assert result.pattern is not None

    def test_volume_low_detection(self):
        """Test that low volume is detected in narrative."""
        opens = [100, 101, 102]
        highs = [105, 106, 107]
        lows = [99, 100, 101]
        closes = [104, 105, 106]
        volumes = [2000, 2000, 800]  # Low volume on last candle

        result = analyze_three_candles(opens, highs, lows, closes, volumes)
        assert "volume" in result.narrative.lower() or "Volume" in result.narrative
        assert "low" in result.narrative.lower() or "weak" in result.narrative.lower()

    def test_pattern_interpretations_included(self):
        """Test that pattern-specific interpretations are included in narrative."""
        # Test Three White Soldiers
        opens = [100, 105, 110]
        highs = [106, 111, 116]
        lows = [99, 104, 109]
        closes = [105, 110, 115]

        result = analyze_three_candles(opens, highs, lows, closes)
        assert result.pattern == ThreeCandlePattern.THREE_WHITE_SOLDIERS
        assert "THREE WHITE SOLDIERS" in result.narrative
        assert "bullish" in result.narrative.lower() or "Buyers" in result.narrative
