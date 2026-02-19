"""Tests for volume analysis."""

import numpy as np
import pytest
from hypothesis import given, settings

from app.indicators.volume import (
    VolumeApproach,
    VolumeSignalAnalysis,
    calculate_volume_vs_previous_day,
    detect_volume_signal,
)


class TestCalculateVolumeVsPreviousDay:
    """Tests for volume vs previous day calculation."""

    def test_volume_increase_from_previous_day(self):
        """Test current volume increased from previous day."""
        # Previous day: 1000, current day: 1500 = +50%
        volumes = [1000.0, 1500.0]

        result = calculate_volume_vs_previous_day(volumes)

        assert abs(result - 50.0) < 0.01

    def test_volume_decrease_from_previous_day(self):
        """Test current volume decreased from previous day."""
        # Previous day: 1000, current day: 800 = -20%
        volumes = [1000.0, 800.0]

        result = calculate_volume_vs_previous_day(volumes)

        assert abs(result - (-20.0)) < 0.01

    def test_volume_unchanged_from_previous_day(self):
        """Test current volume unchanged from previous day."""
        # Previous day: 1000, current day: 1000 = 0%
        volumes = [1000.0, 1000.0]

        result = calculate_volume_vs_previous_day(volumes)

        assert abs(result - 0.0) < 0.01

    def test_volume_doubled(self):
        """Test current volume doubled from previous day."""
        # Previous day: 1000, current day: 2000 = +100%
        volumes = [1000.0, 2000.0]

        result = calculate_volume_vs_previous_day(volumes)

        assert abs(result - 100.0) < 0.01

    def test_volume_halved(self):
        """Test current volume halved from previous day."""
        # Previous day: 1000, current day: 500 = -50%
        volumes = [1000.0, 500.0]

        result = calculate_volume_vs_previous_day(volumes)

        assert abs(result - (-50.0)) < 0.01

    def test_insufficient_data_single_value(self):
        """Test volume vs previous day with single value."""
        volumes = [1000.0]

        result = calculate_volume_vs_previous_day(volumes)

        # Should return 0.0 when data < 2
        assert result == 0.0

    def test_insufficient_data_empty(self):
        """Test volume vs previous day with empty array."""
        volumes = []

        result = calculate_volume_vs_previous_day(volumes)

        # Should return 0.0 when no data
        assert result == 0.0

    def test_zero_previous_volume(self):
        """Test handling of zero previous volume."""
        # Previous day: 0, current day: 100
        volumes = [0.0, 100.0]

        result = calculate_volume_vs_previous_day(volumes)

        # Should return 0.0 to avoid division by zero
        assert result == 0.0

    def test_zero_current_volume(self):
        """Test handling of zero current volume."""
        # Previous day: 100, current day: 0 = -100%
        volumes = [100.0, 0.0]

        result = calculate_volume_vs_previous_day(volumes)

        assert abs(result - (-100.0)) < 0.01

    def test_numpy_array_input(self):
        """Test that numpy arrays work as input."""
        volumes = np.array([1000.0, 1500.0])

        result = calculate_volume_vs_previous_day(volumes)

        assert abs(result - 50.0) < 0.01

    def test_longer_array(self):
        """Test with longer array - should only use last 2 values."""
        # Should only compare last 2: 800 -> 1200 = +50%
        volumes = [500.0, 600.0, 700.0, 800.0, 1200.0]

        result = calculate_volume_vs_previous_day(volumes)

        assert abs(result - 50.0) < 0.01

    def test_real_world_scenario(self):
        """Test with realistic volume values."""
        # Previous day: 2.5M, current day: 3.2M = +28%
        volumes = [2500000.0, 3200000.0]

        result = calculate_volume_vs_previous_day(volumes)

        assert abs(result - 28.0) < 0.01

    def test_small_increase(self):
        """Test small percentage increase."""
        # Previous day: 1000, current day: 1005 = +0.5%
        volumes = [1000.0, 1005.0]

        result = calculate_volume_vs_previous_day(volumes)

        assert abs(result - 0.5) < 0.01

    def test_small_decrease(self):
        """Test small percentage decrease."""
        # Previous day: 1000, current day: 995 = -0.5%
        volumes = [1000.0, 995.0]

        result = calculate_volume_vs_previous_day(volumes)

        assert abs(result - (-0.5)) < 0.01


class TestDetectVolumeSignal:
    """Tests for Volume Signal detection (today vs yesterday comparison)."""

    def test_long_aligned_higher_volume_green_candle(self):
        """Test LONG aligned: higher volume + green candle."""
        opens = [100.0, 98.0]  # Yesterday open, today open
        closes = [99.0, 100.0]  # Yesterday close, today close (GREEN)
        volumes = [1000000.0, 1500000.0]  # Yesterday, today (1.5x)

        result = detect_volume_signal(opens, closes, volumes)

        assert result.aligned_for_long is True
        assert result.rvol == 1.5
        assert "buyers stepping in" in result.description.lower()

    def test_not_aligned_higher_volume_red_candle(self):
        """Test not aligned for LONG: higher volume + red candle."""
        opens = [100.0, 102.0]  # Yesterday open, today open
        closes = [101.0, 100.0]  # Yesterday close, today close (RED)
        volumes = [1000000.0, 1500000.0]  # 1.5x volume

        result = detect_volume_signal(opens, closes, volumes)

        assert result.aligned_for_long is False
        assert result.rvol == 1.5
        assert "sellers stepping in" in result.description.lower()

    def test_not_aligned_lower_volume_green_candle(self):
        """Test not aligned: lower volume (no conviction) even with green candle."""
        opens = [100.0, 98.0]
        closes = [99.0, 100.0]  # GREEN candle
        volumes = [1500000.0, 1000000.0]  # Lower volume (0.67x)

        result = detect_volume_signal(opens, closes, volumes)

        assert result.aligned_for_long is False
        assert result.rvol == 0.67
        assert "no volume conviction" in result.description.lower()

    def test_not_aligned_lower_volume_red_candle(self):
        """Test not aligned: lower volume (no conviction) even with red candle."""
        opens = [100.0, 102.0]
        closes = [101.0, 100.0]  # RED candle
        volumes = [1500000.0, 1000000.0]  # Lower volume

        result = detect_volume_signal(opens, closes, volumes)

        assert result.aligned_for_long is False

    def test_not_aligned_equal_volume(self):
        """Test not aligned: equal volume (no conviction)."""
        opens = [100.0, 98.0]
        closes = [99.0, 100.0]  # GREEN candle
        volumes = [1000000.0, 1000000.0]  # Equal volume (1.0x)

        result = detect_volume_signal(opens, closes, volumes)

        assert result.aligned_for_long is False
        assert result.rvol == 1.0

    def test_not_aligned_doji_candle(self):
        """Test not aligned: doji candle (open == close) even with higher volume."""
        opens = [100.0, 100.0]
        closes = [99.0, 100.0]  # DOJI (open == close)
        volumes = [1000000.0, 1500000.0]  # Higher volume

        result = detect_volume_signal(opens, closes, volumes)

        # Neither green nor red
        assert result.aligned_for_long is False

    def test_insufficient_data(self):
        """Test with insufficient data (single day)."""
        opens = [100.0]
        closes = [99.0]
        volumes = [1000000.0]

        result = detect_volume_signal(opens, closes, volumes)

        assert result.aligned_for_long is False
        assert "insufficient" in result.description.lower()

    def test_zero_yesterday_volume(self):
        """Test handling of zero yesterday volume."""
        opens = [100.0, 98.0]
        closes = [99.0, 100.0]
        volumes = [0.0, 1000000.0]

        result = detect_volume_signal(opens, closes, volumes)

        # Should handle gracefully (rvol = 1.0)
        assert result.rvol == 1.0

    def test_numpy_array_input(self):
        """Test with numpy array input."""
        opens = np.array([100.0, 98.0])
        closes = np.array([99.0, 100.0])
        volumes = np.array([1000000.0, 1500000.0])

        result = detect_volume_signal(opens, closes, volumes)

        assert result.aligned_for_long is True
        assert result.rvol == 1.5

    def test_longer_data_uses_last_two_days(self):
        """Test that only last 2 days are used for comparison."""
        opens = [100.0, 101.0, 102.0, 103.0, 98.0]  # Last: 98
        closes = [101.0, 102.0, 103.0, 104.0, 100.0]  # Last: 100 (GREEN)
        volumes = [500000.0, 600000.0, 700000.0, 800000.0, 1200000.0]  # 800K -> 1.2M = 1.5x

        result = detect_volume_signal(opens, closes, volumes)

        assert result.aligned_for_long is True
        assert result.rvol == 1.5

    def test_volume_ratio_formatting(self):
        """Test volume ratio is rounded to 2 decimal places."""
        opens = [100.0, 98.0]
        closes = [99.0, 100.0]
        volumes = [1000000.0, 1234567.0]  # 1.234567x

        result = detect_volume_signal(opens, closes, volumes)

        assert result.rvol == 1.23  # Rounded to 2 decimal places
