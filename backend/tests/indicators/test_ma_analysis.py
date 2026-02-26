"""Tests for moving average analysis."""

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.indicators.ma_analysis import (
    PricePosition,
    MASlope,
    MAAnalysis,
    analyze_ma_distance,
)


class TestAnalyzeMADistance:
    """Tests for MA distance analysis."""

    def test_price_above_ma(self):
        """Test price above moving average."""
        # Price trending up, currently above 20-day MA
        closes = list(range(100, 130))  # 100, 101, 102, ..., 129

        result = analyze_ma_distance(closes, period=20)

        assert result.price_position == PricePosition.ABOVE
        assert result.distance_pct > 0

    def test_price_below_ma(self):
        """Test price below moving average."""
        # Price trending down, currently below 20-day MA
        closes = list(range(130, 100, -1))  # 130, 129, 128, ..., 101

        result = analyze_ma_distance(closes, period=20)

        assert result.price_position == PricePosition.BELOW
        assert result.distance_pct < 0

    def test_price_at_ma(self):
        """Test price at moving average (within threshold)."""
        # Sideways movement around 100
        closes = [100.0] * 30

        result = analyze_ma_distance(closes, period=20, at_threshold_pct=0.5)

        assert result.price_position == PricePosition.AT
        assert abs(result.distance_pct) < 0.5

    def test_rising_ma_slope(self):
        """Test rising MA slope detection."""
        # Steady uptrend
        closes = [100.0 + i * 0.5 for i in range(30)]

        result = analyze_ma_distance(closes, period=20, slope_threshold_pct=0.5)

        assert result.ma_slope == MASlope.RISING

    def test_falling_ma_slope(self):
        """Test falling MA slope detection."""
        # Steady downtrend
        closes = [130.0 - i * 0.5 for i in range(30)]

        result = analyze_ma_distance(closes, period=20, slope_threshold_pct=0.5)

        assert result.ma_slope == MASlope.FALLING

    def test_flat_ma_slope(self):
        """Test flat MA slope detection."""
        # Sideways movement
        closes = [100.0] * 30

        result = analyze_ma_distance(closes, period=20, slope_threshold_pct=0.5)

        assert result.ma_slope == MASlope.FLAT

    def test_ma_value_calculation(self):
        """Test that MA value is calculated correctly."""
        closes = [100.0] * 30

        result = analyze_ma_distance(closes, period=20)

        # MA of constant values should equal the value
        assert abs(result.ma_value - 100.0) < 0.1

    def test_distance_percentage_calculation(self):
        """Test distance percentage calculation."""
        # Create enough data (period + 5 = 25 minimum)
        closes = list(range(100, 125))  # 25 values: 100-124
        closes[-1] = 115.5  # Set current price

        result = analyze_ma_distance(closes, period=20)

        # MA is calculated on last 20 values, distance is %age from current price to MA
        # Just verify it's positive (price above MA) and reasonable
        assert result.price_position == PricePosition.ABOVE
        assert 0 < result.distance_pct < 10  # Should be a few percent

    def test_insufficient_data(self):
        """Test handling of insufficient data."""
        closes = [100.0, 101.0, 102.0]

        result = analyze_ma_distance(closes, period=20)

        # Should return default values when data < period + 5
        assert result.price_position == PricePosition.AT
        assert result.distance_pct == 0.0
        assert result.ma_slope == MASlope.FLAT
        assert result.ma_value == closes[-1]

    def test_exact_minimum_data(self):
        """Test with exact minimum data (period + 5)."""
        closes = [100.0] * 25  # Exactly period + 5

        result = analyze_ma_distance(closes, period=20)

        # Should calculate normally
        assert isinstance(result, MAAnalysis)
        assert result.ma_value == 100.0

    def test_custom_thresholds(self):
        """Test custom threshold settings."""
        # Create enough data (25+ values)
        # Price ~1% above MA
        closes = [100.0] * 25  # Create baseline
        closes += [101.0] * 5  # Recent higher prices

        # With 0.5% threshold, should be ABOVE
        result1 = analyze_ma_distance(closes, period=20, at_threshold_pct=0.5)
        assert result1.price_position == PricePosition.ABOVE

        # With 2% threshold, should be AT
        result2 = analyze_ma_distance(closes, period=20, at_threshold_pct=2.0)
        assert result2.price_position == PricePosition.AT

    def test_slope_threshold_sensitivity(self):
        """Test slope threshold sensitivity."""
        # MA increases 0.75% over 5 days
        closes = [100.0 + i * 0.15 for i in range(30)]

        # With 0.5% threshold, should be RISING
        result1 = analyze_ma_distance(closes, period=20, slope_threshold_pct=0.5)
        assert result1.ma_slope == MASlope.RISING

        # With 1.0% threshold, should be FLAT
        result2 = analyze_ma_distance(closes, period=20, slope_threshold_pct=1.0)
        assert result2.ma_slope == MASlope.FLAT

    def test_zero_ma_value(self):
        """Test handling of zero MA value."""
        closes = [0.0] * 30

        result = analyze_ma_distance(closes, period=20)

        # Should handle gracefully without division by zero
        assert result.distance_pct == 0.0

    def test_numpy_array_input(self):
        """Test that numpy arrays work as input."""
        closes = np.array([100.0 + i * 0.5 for i in range(30)])

        result = analyze_ma_distance(closes, period=20)

        assert isinstance(result, MAAnalysis)
        assert result.ma_slope == MASlope.RISING

    def test_custom_period(self):
        """Test MA analysis with custom period."""
        # Create data with clear 10-day pattern
        closes = [100.0] * 15
        closes += [105.0] * 5

        result = analyze_ma_distance(closes, period=10)

        # Should calculate based on 10-day MA
        assert isinstance(result, MAAnalysis)

    def test_rounded_values(self):
        """Test that returned values are properly rounded."""
        closes = [100.123456] * 30

        result = analyze_ma_distance(closes, period=20)

        # distance_pct and ma_value should be rounded to 2 decimals
        assert result.distance_pct == round(result.distance_pct, 2)
        assert result.ma_value == round(result.ma_value, 2)

    def test_price_exactly_at_threshold(self):
        """Test price exactly at threshold boundary."""
        closes = [100.0] * 25
        closes[-1] = 100.5  # Exactly 0.5% above MA

        result = analyze_ma_distance(closes, period=20, at_threshold_pct=0.5)

        # At exactly the threshold, should be considered AT
        assert result.price_position == PricePosition.AT


class TestMAAnalysisEdgeCases:
    """Tests for edge cases in MA analysis."""

    def test_volatile_prices(self):
        """Test MA analysis with volatile prices."""
        # Highly volatile but generally upward
        closes = [100.0]
        for i in range(1, 30):
            # Alternate between up and down, but trending up
            if i % 2 == 0:
                closes.append(closes[-1] + 3.0)
            else:
                closes.append(closes[-1] - 1.0)

        result = analyze_ma_distance(closes, period=20)

        # Should still calculate position and slope
        assert result.price_position in [
            PricePosition.ABOVE,
            PricePosition.BELOW,
            PricePosition.AT,
        ]
        assert result.ma_slope in [MASlope.RISING, MASlope.FALLING, MASlope.FLAT]

    def test_recent_trend_reversal(self):
        """Test MA analysis after recent trend reversal."""
        # Long uptrend, then recent reversal
        closes = [100.0 + i for i in range(20)]  # Uptrend to 119
        closes += [119.0 - i for i in range(10)]  # Recent downtrend

        result = analyze_ma_distance(closes, period=20)

        # MA should still be rising (long uptrend), but price may be near/below it
        assert isinstance(result, MAAnalysis)

    def test_gap_up(self):
        """Test MA analysis after gap up."""
        closes = [100.0] * 25
        closes += [110.0] * 5  # Sudden gap up

        result = analyze_ma_distance(closes, period=20)

        # Price should be significantly above MA
        assert result.price_position == PricePosition.ABOVE
        assert result.distance_pct > 5.0


class TestMAAnalysisProperties:
    """Property-based tests for MA analysis."""

    @given(
        st.lists(
            st.floats(min_value=50.0, max_value=150.0),
            min_size=30,
            max_size=100,
        )
    )
    @settings(max_examples=30, deadline=2000)
    def test_ma_analysis_always_returns_valid_result(self, closes):
        """Test that MA analysis always returns valid result."""
        if len(closes) >= 25:
            result = analyze_ma_distance(closes, period=20)

            # Should always return valid enum values
            assert result.price_position in [
                PricePosition.ABOVE,
                PricePosition.BELOW,
                PricePosition.AT,
            ]
            assert result.ma_slope in [MASlope.RISING, MASlope.FALLING, MASlope.FLAT]
            # MA value should be reasonable
            assert result.ma_value > 0

    def test_empty_array(self):
        """Test MA analysis with empty array."""
        result = analyze_ma_distance([], period=20)

        # Should return default values
        assert result.price_position == PricePosition.AT
        assert result.distance_pct == 0.0
        assert result.ma_slope == MASlope.FLAT

    def test_single_value(self):
        """Test MA analysis with single value."""
        result = analyze_ma_distance([100.0], period=20)

        # Should return default values with ma_value = current price
        assert result.price_position == PricePosition.AT
        assert result.ma_value == 100.0
