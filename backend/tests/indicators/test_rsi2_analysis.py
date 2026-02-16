"""Tests for RSI-2 analysis."""

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.indicators.rsi2_analysis import (
    RSI2Analysis,
    analyze_rsi2,
    _score_for_long,
    _score_for_short,
)


class TestScoreForLong:
    """Tests for LONG (oversold) graduated scoring."""

    def test_extreme_panic_below_5(self):
        """Test RSI < 5 scores 20 points (extreme panic)."""
        assert _score_for_long(0.0) == 20
        assert _score_for_long(2.5) == 20
        assert _score_for_long(4.9) == 20

    def test_strong_oversold_5_to_15(self):
        """Test 5 ≤ RSI < 15 scores 15 points (strong oversold)."""
        assert _score_for_long(5.0) == 15
        assert _score_for_long(10.0) == 15
        assert _score_for_long(14.9) == 15

    def test_mildly_oversold_15_to_30(self):
        """Test 15 ≤ RSI < 30 scores 10 points (mildly oversold)."""
        assert _score_for_long(15.0) == 10
        assert _score_for_long(20.0) == 10
        assert _score_for_long(29.9) == 10

    def test_neutral_weak_30_to_50(self):
        """Test 30 ≤ RSI < 50 scores 5 points (neutral/weak)."""
        assert _score_for_long(30.0) == 5
        assert _score_for_long(40.0) == 5
        assert _score_for_long(49.9) == 5

    def test_not_oversold_above_50(self):
        """Test RSI ≥ 50 scores 0 points (not oversold)."""
        assert _score_for_long(50.0) == 0
        assert _score_for_long(75.0) == 0
        assert _score_for_long(100.0) == 0


class TestScoreForShort:
    """Tests for SHORT (overbought) graduated scoring."""

    def test_extreme_overbought_above_95(self):
        """Test RSI > 95 scores 20 points (extreme overbought)."""
        assert _score_for_short(95.1) == 20
        assert _score_for_short(97.5) == 20
        assert _score_for_short(100.0) == 20

    def test_strong_overbought_85_to_95(self):
        """Test 85 < RSI ≤ 95 scores 15 points (strong overbought)."""
        assert _score_for_short(85.1) == 15
        assert _score_for_short(90.0) == 15
        assert _score_for_short(95.0) == 15

    def test_mildly_overbought_70_to_85(self):
        """Test 70 < RSI ≤ 85 scores 10 points (mildly overbought)."""
        assert _score_for_short(70.1) == 10
        assert _score_for_short(77.5) == 10
        assert _score_for_short(85.0) == 10

    def test_neutral_weak_50_to_70(self):
        """Test 50 < RSI ≤ 70 scores 5 points (neutral/weak)."""
        assert _score_for_short(50.1) == 5
        assert _score_for_short(60.0) == 5
        assert _score_for_short(70.0) == 5

    def test_not_overbought_below_50(self):
        """Test RSI ≤ 50 scores 0 points (not overbought)."""
        assert _score_for_short(50.0) == 0
        assert _score_for_short(25.0) == 0
        assert _score_for_short(0.0) == 0


class TestAnalyzeRSI2:
    """Tests for RSI-2 analysis function."""

    def test_rsi2_extreme_oversold(self):
        """Test RSI-2 with extreme oversold condition (< 5)."""
        # Create strong downtrend that produces very low RSI-2
        closes = [100.0] * 5 + [95.0, 90.0, 85.0, 80.0, 75.0]

        result = analyze_rsi2(closes)

        # Should be extremely low RSI-2
        assert result.value < 5.0
        assert result.long_score == 20
        assert result.short_score == 0

    def test_rsi2_strong_oversold_5_to_15(self):
        """Test RSI-2 in strong oversold range (5-15)."""
        # Moderate downtrend
        closes = [100.0] * 5 + [98.0, 96.0, 94.0, 92.0, 90.0]

        result = analyze_rsi2(closes)

        # Should be in oversold range
        if 5.0 <= result.value < 15.0:
            assert result.long_score == 15
        # Otherwise verify score matches value
        assert result.long_score == _score_for_long(result.value)

    def test_rsi2_mildly_oversold_15_to_30(self):
        """Test RSI-2 in mildly oversold range (15-30)."""
        # Mild downtrend
        closes = [100.0] * 5 + [99.5, 99.0, 98.5, 98.0, 97.5]

        result = analyze_rsi2(closes)

        # Verify score matches value range
        assert result.long_score == _score_for_long(result.value)
        assert result.short_score == _score_for_short(result.value)

    def test_rsi2_extreme_overbought(self):
        """Test RSI-2 with extreme overbought condition (> 95)."""
        # Create strong uptrend that produces very high RSI-2
        closes = [100.0] * 5 + [105.0, 110.0, 115.0, 120.0, 125.0]

        result = analyze_rsi2(closes)

        # Should be extremely high RSI-2
        assert result.value > 95.0
        assert result.long_score == 0
        assert result.short_score == 20

    def test_rsi2_strong_overbought_85_to_95(self):
        """Test RSI-2 in strong overbought range (85-95)."""
        # Strong uptrend
        closes = [100.0] * 5 + [102.0, 104.0, 106.0, 108.0, 110.0]

        result = analyze_rsi2(closes)

        # Verify score matches value
        assert result.short_score == _score_for_short(result.value)

    def test_rsi2_neutral_50(self):
        """Test RSI-2 at neutral (around 50)."""
        # Sideways movement (alternating up/down)
        closes = [100.0] * 5 + [101.0, 100.0, 101.0, 100.0, 101.0]

        result = analyze_rsi2(closes)

        # Should be around neutral
        # At exactly 50, long_score=5, short_score=0
        # Slight variation possible due to calculation
        assert 30.0 <= result.value <= 70.0

    def test_rsi2_uses_period_2(self):
        """Test that RSI-2 uses 2-period RSI (not default 14)."""
        # With 2-period RSI, recent changes matter more
        # Strong recent move should show extreme RSI
        closes = [100.0] * 10 + [80.0, 70.0]  # Sudden drop

        result = analyze_rsi2(closes)

        # With 2-period, this should be very low RSI
        # With 14-period, it would be less extreme
        assert result.value < 30.0  # Should be low due to recent drops
        assert result.long_score >= 10  # At least mildly oversold

    def test_rsi2_boundary_values(self):
        """Test RSI-2 scoring at exact boundary values."""
        # Test exact boundaries (5, 15, 30, 50, 70, 85, 95)
        boundaries = [
            (5.0, 15, 0),   # Exactly 5: LONG 15pts
            (15.0, 10, 0),  # Exactly 15: LONG 10pts
            (30.0, 5, 0),   # Exactly 30: LONG 5pts
            (50.0, 0, 0),   # Exactly 50: both 0pts
            (70.0, 0, 5),   # Exactly 70: SHORT 5pts
            (85.0, 0, 10),  # Exactly 85: SHORT 10pts
            (95.0, 0, 15),  # Exactly 95: SHORT 15pts
        ]

        for value, expected_long, expected_short in boundaries:
            assert _score_for_long(value) == expected_long, f"LONG score mismatch at RSI={value}"
            assert _score_for_short(value) == expected_short, f"SHORT score mismatch at RSI={value}"

    def test_rsi2_both_scores_populated(self):
        """Test that both long_score and short_score are always populated."""
        closes = [100.0] * 5 + [95.0, 90.0, 85.0, 80.0]

        result = analyze_rsi2(closes)

        # Both scores should be int, not None
        assert isinstance(result.long_score, int)
        assert isinstance(result.short_score, int)
        assert 0 <= result.long_score <= 20
        assert 0 <= result.short_score <= 20

    def test_rsi2_insufficient_data(self):
        """Test RSI-2 with insufficient data (< 5 bars)."""
        closes = [100.0, 101.0, 102.0]  # Only 3 bars

        result = analyze_rsi2(closes)

        # Should return default values
        assert result.value == 50.0
        assert result.long_score == 0
        assert result.short_score == 0

    def test_rsi2_exact_minimum_data(self):
        """Test RSI-2 with exact minimum data (5 bars)."""
        closes = [100.0, 101.0, 102.0, 101.0, 100.0]  # Exactly 5 bars

        result = analyze_rsi2(closes)

        # Should calculate normally
        assert isinstance(result, RSI2Analysis)
        # Value might vary, but should be valid
        assert 0.0 <= result.value <= 100.0

    def test_rsi2_nan_handling(self):
        """Test RSI-2 handles NaN gracefully."""
        # If RSI calculation returns NaN, should return default
        closes = [100.0] * 3  # Too little data

        result = analyze_rsi2(closes)

        assert result.value == 50.0
        assert result.long_score == 0
        assert result.short_score == 0

    def test_rsi2_value_rounded(self):
        """Test that RSI-2 value is rounded to 1 decimal."""
        closes = [100.0] * 5 + [99.7, 99.4, 99.1, 98.8, 98.5]

        result = analyze_rsi2(closes)

        # Value should be rounded to 1 decimal
        assert result.value == round(result.value, 1)

    def test_rsi2_numpy_arrays(self):
        """Test RSI-2 analysis with numpy arrays."""
        closes = np.array([100.0] * 5 + [95.0, 90.0, 85.0, 80.0])

        result = analyze_rsi2(closes)

        assert isinstance(result, RSI2Analysis)
        assert 0.0 <= result.value <= 100.0

    def test_rsi2_consistency_with_scoring_functions(self):
        """Test that RSI2Analysis scores match standalone scoring functions."""
        closes = [100.0] * 5 + [95.0, 92.0, 89.0, 86.0, 83.0]

        result = analyze_rsi2(closes)

        # Scores should match scoring functions
        assert result.long_score == _score_for_long(result.value)
        assert result.short_score == _score_for_short(result.value)


class TestRSI2AnalysisProperties:
    """Property-based tests for RSI-2 analysis."""

    @given(
        st.lists(
            st.floats(min_value=50.0, max_value=150.0),
            min_size=10,
            max_size=100,
        )
    )
    @settings(max_examples=30, deadline=2000)
    def test_rsi2_always_returns_valid_result(self, closes):
        """Test that RSI-2 analysis always returns valid result."""
        result = analyze_rsi2(closes)

        # Should always return valid values
        assert isinstance(result, RSI2Analysis)
        assert 0.0 <= result.value <= 100.0
        assert 0 <= result.long_score <= 20
        assert 0 <= result.short_score <= 20
        assert result.long_score in [0, 5, 10, 15, 20]
        assert result.short_score in [0, 5, 10, 15, 20]

    @given(
        st.lists(
            st.floats(min_value=50.0, max_value=150.0),
            min_size=10,
            max_size=100,
        )
    )
    @settings(max_examples=30, deadline=2000)
    def test_rsi2_scores_mutually_exclusive(self, closes):
        """Test that LONG and SHORT scores are mutually exclusive (mostly)."""
        result = analyze_rsi2(closes)

        # At most one score should be non-zero (except at boundary 50)
        # At RSI=50, both can be 0
        if result.value < 50.0:
            # Oversold side: LONG score > 0, SHORT score = 0
            assert result.short_score == 0
        elif result.value > 50.0:
            # Overbought side: SHORT score > 0, LONG score = 0
            assert result.long_score == 0
        else:
            # Exactly 50: both should be 0
            assert result.long_score == 0
            assert result.short_score == 0

    def test_rsi2_empty_array(self):
        """Test RSI-2 analysis with empty array."""
        result = analyze_rsi2([])

        # Should return default values
        assert result.value == 50.0
        assert result.long_score == 0
        assert result.short_score == 0


class TestRSI2GraduatedScoring:
    """Tests specifically for graduated scoring behavior."""

    def test_graduated_scoring_vs_binary(self):
        """Test that RSI-2 provides more granular scores than binary CCI."""
        # RSI-2 can score 0, 5, 10, 15, or 20
        # CCI would be 0 or 20 (binary aligned/not-aligned)

        # Various RSI values that should produce different scores
        test_cases = [
            (2.0, 20),   # Extreme
            (10.0, 15),  # Strong
            (20.0, 10),  # Mild
            (40.0, 5),   # Weak
            (60.0, 0),   # None
        ]

        for rsi_val, expected_score in test_cases:
            assert _score_for_long(rsi_val) == expected_score

    def test_all_five_score_levels_achievable(self):
        """Test that all 5 score levels (0, 5, 10, 15, 20) are achievable."""
        # LONG side
        assert _score_for_long(2.0) == 20
        assert _score_for_long(10.0) == 15
        assert _score_for_long(20.0) == 10
        assert _score_for_long(40.0) == 5
        assert _score_for_long(60.0) == 0

        # SHORT side
        assert _score_for_short(97.0) == 20
        assert _score_for_short(90.0) == 15
        assert _score_for_short(75.0) == 10
        assert _score_for_short(60.0) == 5
        assert _score_for_short(40.0) == 0
