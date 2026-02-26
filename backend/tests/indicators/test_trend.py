"""Tests for trend analysis."""

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.indicators.trend import (
    TrendDirection,
    detect_trend,
    detect_weekly_trend,
    detect_monthly_trend,
)


class TestDetectTrend:
    """Tests for trend detection."""

    def test_bullish_trend(self):
        """Test bullish trend detection."""
        # Price increases from 100 to 110 over 5 days (10% increase)
        closes = [100.0, 102.0, 104.0, 106.0, 110.0]

        result = detect_trend(closes, period=5, threshold_pct=1.0)

        assert result == TrendDirection.BULLISH

    def test_bearish_trend(self):
        """Test bearish trend detection."""
        # Price decreases from 110 to 100 over 5 days (9% decrease)
        closes = [110.0, 108.0, 106.0, 104.0, 100.0]

        result = detect_trend(closes, period=5, threshold_pct=1.0)

        assert result == TrendDirection.BEARISH

    def test_neutral_trend_small_change(self):
        """Test neutral trend with small price change."""
        # Price barely changes (0.5% increase)
        closes = [100.0, 100.2, 100.1, 100.3, 100.5]

        result = detect_trend(closes, period=5, threshold_pct=1.0)

        assert result == TrendDirection.NEUTRAL

    def test_neutral_trend_sideways(self):
        """Test neutral trend with sideways movement."""
        # Price moves up and down but ends near start
        closes = [100.0, 102.0, 98.0, 103.0, 100.2]

        result = detect_trend(closes, period=5, threshold_pct=1.0)

        assert result == TrendDirection.NEUTRAL

    def test_threshold_sensitivity(self):
        """Test that threshold affects trend classification."""
        # 1.5% increase
        closes = [100.0, 100.5, 101.0, 101.2, 101.5]

        # With 1% threshold, should be bullish
        assert detect_trend(closes, period=5, threshold_pct=1.0) == TrendDirection.BULLISH

        # With 2% threshold, should be neutral
        assert detect_trend(closes, period=5, threshold_pct=2.0) == TrendDirection.NEUTRAL

    def test_insufficient_data(self):
        """Test trend detection with insufficient data."""
        closes = [100.0, 101.0, 102.0]

        result = detect_trend(closes, period=5, threshold_pct=1.0)

        # Should return neutral when data < period
        assert result == TrendDirection.NEUTRAL

    def test_exact_period_length(self):
        """Test trend detection with exact period length."""
        closes = [100.0, 102.0, 104.0, 106.0, 108.0]

        result = detect_trend(closes, period=5, threshold_pct=1.0)

        assert result == TrendDirection.BULLISH

    def test_more_data_than_period(self):
        """Test that only recent period is used."""
        # Old data is bearish, recent data is bullish
        closes = [120.0, 110.0, 100.0, 90.0, 80.0,  # Bearish start
                  100.0, 102.0, 104.0, 106.0, 110.0]  # Bullish end

        result = detect_trend(closes, period=5, threshold_pct=1.0)

        # Should only look at last 5 values (bullish)
        assert result == TrendDirection.BULLISH

    def test_zero_start_price(self):
        """Test handling of zero start price."""
        closes = [0.0, 1.0, 2.0, 3.0, 4.0]

        result = detect_trend(closes, period=5, threshold_pct=1.0)

        # Should return neutral to avoid division by zero
        assert result == TrendDirection.NEUTRAL

    def test_numpy_array_input(self):
        """Test that numpy arrays work as input."""
        closes = np.array([100.0, 102.0, 104.0, 106.0, 110.0])

        result = detect_trend(closes, period=5, threshold_pct=1.0)

        assert result == TrendDirection.BULLISH

    def test_large_period(self):
        """Test trend detection with larger period."""
        # Create 30 days of data with upward trend
        closes = [100.0 + i * 0.5 for i in range(30)]

        result = detect_trend(closes, period=20, threshold_pct=1.0)

        # 100 to 109.5 over 20 days = 9.5% increase
        assert result == TrendDirection.BULLISH


class TestDetectWeeklyTrend:
    """Tests for weekly trend detection."""

    def test_weekly_bullish_trend(self):
        """Test weekly bullish trend (5 days)."""
        closes = [100.0, 101.0, 102.0, 103.0, 105.0]

        result = detect_weekly_trend(closes, threshold_pct=1.0)

        assert result == TrendDirection.BULLISH

    def test_weekly_bearish_trend(self):
        """Test weekly bearish trend (5 days)."""
        closes = [105.0, 103.0, 102.0, 101.0, 100.0]

        result = detect_weekly_trend(closes, threshold_pct=1.0)

        assert result == TrendDirection.BEARISH

    def test_weekly_neutral_trend(self):
        """Test weekly neutral trend."""
        closes = [100.0, 101.0, 99.0, 101.0, 100.5]

        result = detect_weekly_trend(closes, threshold_pct=1.0)

        assert result == TrendDirection.NEUTRAL

    def test_weekly_custom_threshold(self):
        """Test weekly trend with custom threshold."""
        closes = [100.0, 101.0, 102.0, 102.5, 103.0]  # 3% increase

        # With 2% threshold, should be bullish
        assert detect_weekly_trend(closes, threshold_pct=2.0) == TrendDirection.BULLISH

        # With 5% threshold, should be neutral
        assert detect_weekly_trend(closes, threshold_pct=5.0) == TrendDirection.NEUTRAL


class TestDetectMonthlyTrend:
    """Tests for monthly trend detection."""

    def test_monthly_bullish_trend(self):
        """Test monthly bullish trend (20 days)."""
        # 5% increase over 20 days
        closes = [100.0 + i * 0.25 for i in range(20)]

        result = detect_monthly_trend(closes, threshold_pct=2.0)

        assert result == TrendDirection.BULLISH

    def test_monthly_bearish_trend(self):
        """Test monthly bearish trend (20 days)."""
        # 5% decrease over 20 days
        closes = [105.0 - i * 0.25 for i in range(20)]

        result = detect_monthly_trend(closes, threshold_pct=2.0)

        assert result == TrendDirection.BEARISH

    def test_monthly_neutral_trend(self):
        """Test monthly neutral trend."""
        # Sideways movement
        closes = [100.0] * 20

        result = detect_monthly_trend(closes, threshold_pct=2.0)

        assert result == TrendDirection.NEUTRAL

    def test_monthly_custom_threshold(self):
        """Test monthly trend with custom threshold."""
        # Create 3% increase over 20 days
        closes = [100.0 + i * 0.15 for i in range(20)]

        # With 2% threshold, should be bullish
        assert detect_monthly_trend(closes, threshold_pct=2.0) == TrendDirection.BULLISH

        # With 5% threshold, should be neutral
        assert detect_monthly_trend(closes, threshold_pct=5.0) == TrendDirection.NEUTRAL

    def test_monthly_insufficient_data(self):
        """Test monthly trend with insufficient data."""
        closes = [100.0, 101.0, 102.0]

        result = detect_monthly_trend(closes, threshold_pct=2.0)

        # Should return neutral when data < 20
        assert result == TrendDirection.NEUTRAL


class TestTrendProperties:
    """Property-based tests for trend detection."""

    @given(
        st.lists(
            st.floats(min_value=50.0, max_value=150.0),
            min_size=10,
            max_size=50,
        )
    )
    @settings(max_examples=50, deadline=1000)
    def test_trend_always_returns_valid_direction(self, closes):
        """Test that trend detection always returns a valid direction."""
        if len(closes) >= 5:
            result = detect_trend(closes, period=5, threshold_pct=1.0)

            # Should always return one of the three trend directions
            assert result in [
                TrendDirection.BULLISH,
                TrendDirection.BEARISH,
                TrendDirection.NEUTRAL,
            ]

    @given(st.floats(min_value=0.1, max_value=10.0))
    @settings(max_examples=30, deadline=1000)
    def test_threshold_consistency(self, threshold):
        """Test that higher thresholds produce same or more neutral results."""
        closes = [100.0, 102.0, 103.0, 105.0, 106.0]  # Moderate uptrend

        low_threshold_result = detect_trend(closes, period=5, threshold_pct=threshold)
        high_threshold_result = detect_trend(
            closes, period=5, threshold_pct=threshold * 2
        )

        # If low threshold says neutral, high threshold should also say neutral
        if low_threshold_result == TrendDirection.NEUTRAL:
            assert high_threshold_result == TrendDirection.NEUTRAL

    def test_empty_array(self):
        """Test trend detection with empty array."""
        result = detect_trend([], period=5, threshold_pct=1.0)

        assert result == TrendDirection.NEUTRAL

    def test_single_value(self):
        """Test trend detection with single value."""
        result = detect_trend([100.0], period=5, threshold_pct=1.0)

        assert result == TrendDirection.NEUTRAL
