"""Tests for CCI indicator calculation and signal detection."""

import numpy as np
import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

from app.indicators.technical import commodity_channel_index, detect_cci_signals


class TestCommodityChannelIndex:
    """Tests for CCI calculation."""

    def test_cci_basic_calculation(self):
        """Test CCI calculation with known values."""
        # Use a simple dataset where we can verify the calculation
        high = [10.0, 11.0, 12.0, 13.0, 14.0] * 4  # 20 values
        low = [8.0, 9.0, 10.0, 11.0, 12.0] * 4
        close = [9.0, 10.0, 11.0, 12.0, 13.0] * 4

        cci = commodity_channel_index(high, low, close, period=5)

        # First 4 values should be NaN (period - 1)
        assert np.all(np.isnan(cci[:4]))
        # Rest should have values
        assert not np.any(np.isnan(cci[4:]))

    def test_cci_period_validation(self):
        """Test CCI period validation."""
        high = [10, 11, 12]
        low = [8, 9, 10]
        close = [9, 10, 11]

        with pytest.raises(ValueError, match="Period must be greater than 0"):
            commodity_channel_index(high, low, close, period=0)

        with pytest.raises(ValueError, match="Period must be greater than 0"):
            commodity_channel_index(high, low, close, period=-1)

    def test_cci_length_validation(self):
        """Test CCI array length validation."""
        high = [10, 11]
        low = [8, 9]
        close = [9, 10, 11]  # Different length

        with pytest.raises(ValueError, match="must have same length"):
            commodity_channel_index(high, low, close, period=2)

    def test_cci_insufficient_data(self):
        """Test CCI with insufficient data points."""
        high = [10, 11, 12]
        low = [8, 9, 10]
        close = [9, 10, 11]

        cci = commodity_channel_index(high, low, close, period=5)

        # All values should be NaN when data < period
        assert np.all(np.isnan(cci))

    def test_cci_output_length(self):
        """Test that CCI output length matches input length."""
        high = list(range(100, 150))
        low = list(range(90, 140))
        close = list(range(95, 145))

        cci = commodity_channel_index(high, low, close, period=20)

        assert len(cci) == 50

    def test_cci_constant_prices_returns_zero(self):
        """Test CCI with constant prices returns 0 (no deviation)."""
        high = [100.0] * 25
        low = [100.0] * 25
        close = [100.0] * 25

        cci = commodity_channel_index(high, low, close, period=20)

        # With constant prices, CCI should be 0 (no deviation from mean)
        valid_values = cci[~np.isnan(cci)]
        assert np.allclose(valid_values, 0, atol=0.001)

    @given(
        st.lists(
            st.floats(min_value=50.0, max_value=150.0),
            min_size=30,
            max_size=100,
        )
    )
    @settings(max_examples=20, deadline=5000)
    def test_cci_properties(self, close_prices):
        """Property-based test for CCI mathematical properties."""
        assume(len(close_prices) >= 20)

        # Generate high/low from close
        high = [p * 1.02 for p in close_prices]
        low = [p * 0.98 for p in close_prices]

        cci = commodity_channel_index(high, low, close_prices, period=20)

        # Output length matches input
        assert len(cci) == len(close_prices)

        # First period-1 values are NaN
        assert np.all(np.isnan(cci[:19]))


class TestCCISignalDetection:
    """Tests for CCI signal detection."""

    def test_momentum_bullish_signal(self):
        """Test momentum bullish signal detection."""
        # CCI crosses above +100
        cci_values = [50, 80, 95, 105, 110]

        signals = detect_cci_signals(cci_values)

        assert signals[3] == "momentum_bullish"  # 95 -> 105 crosses +100

    def test_momentum_bearish_signal(self):
        """Test momentum bearish signal detection."""
        # CCI crosses below -100
        cci_values = [-50, -80, -95, -105, -110]

        signals = detect_cci_signals(cci_values)

        assert signals[3] == "momentum_bearish"  # -95 -> -105 crosses -100

    def test_reversal_buy_signal(self):
        """Test reversal buy signal detection."""
        # CCI goes below -100, then crosses back up
        cci_values = [-80, -110, -120, -105, -95]

        signals = detect_cci_signals(cci_values)

        assert signals[1] == "momentum_bearish"  # Enters oversold
        assert signals[4] == "reversal_buy"  # -105 -> -95 crosses back above -100

    def test_reversal_sell_signal(self):
        """Test reversal sell signal detection."""
        # CCI goes above +100, then crosses back down
        cci_values = [80, 110, 120, 105, 95]

        signals = detect_cci_signals(cci_values)

        assert signals[1] == "momentum_bullish"  # Enters overbought
        assert signals[4] == "reversal_sell"  # 105 -> 95 crosses back below +100

    def test_no_signal_in_neutral_zone(self):
        """Test no signals when CCI stays in neutral zone."""
        cci_values = [0, 20, -30, 50, -40, 60]

        signals = detect_cci_signals(cci_values)

        assert all(s is None for s in signals)

    def test_handles_nan_values(self):
        """Test signal detection handles NaN values."""
        cci_values = [np.nan, np.nan, 50, 105, 110]

        signals = detect_cci_signals(cci_values)

        assert signals[0] is None
        assert signals[1] is None
        assert signals[3] == "momentum_bullish"

    def test_empty_array(self):
        """Test signal detection with empty array."""
        signals = detect_cci_signals([])
        assert signals == []

    def test_single_value(self):
        """Test signal detection with single value."""
        signals = detect_cci_signals([100])
        assert signals == [None]

    def test_gap_move_between_extremes(self):
        """Test signal detection when CCI gaps from one extreme to another.

        This tests that territory flags are properly reset when CCI jumps
        directly from overbought to oversold (or vice versa).
        """
        # Scenario: CCI goes above 100, then gaps below -100, then recovers
        cci_values = [50, 110, -110, -50, 50, 110, 95]
        #             0   1     2     3    4   5    6
        # 1: momentum_bullish (crosses above 100)
        # 2: momentum_bearish (crosses below -100) - flag reset should happen
        # 3: reversal_buy (crosses above -100)
        # 5: momentum_bullish (crosses above 100 again)
        # 6: reversal_sell (crosses below 100)

        signals = detect_cci_signals(cci_values)

        assert signals[1] == "momentum_bullish"  # 50 -> 110
        assert signals[2] == "momentum_bearish"  # 110 -> -110
        assert signals[3] == "reversal_buy"      # -110 -> -50
        assert signals[5] == "momentum_bullish"  # 50 -> 110
        assert signals[6] == "reversal_sell"     # 110 -> 95
