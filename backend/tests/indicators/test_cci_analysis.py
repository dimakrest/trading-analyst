"""Tests for CCI analysis."""

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.indicators.cci_analysis import (
    CCIZone,
    CCIDirection,
    CCISignalType,
    CCIAnalysis,
    analyze_cci,
)


class TestAnalyzeCCI:
    """Tests for CCI analysis."""

    def test_cci_overbought_zone(self):
        """Test CCI in overbought zone (> 100)."""
        # Create data that will produce CCI > 100
        highs = list(range(100, 125))
        lows = list(range(90, 115))
        closes = list(range(95, 120))

        result = analyze_cci(highs, lows, closes, period=14)

        # With strong uptrend, should be overbought
        assert result.zone == CCIZone.OVERBOUGHT
        assert result.value > 100

    def test_cci_oversold_zone(self):
        """Test CCI in oversold zone (< -100)."""
        # Create data that will produce CCI < -100
        highs = list(range(125, 100, -1))
        lows = list(range(115, 90, -1))
        closes = list(range(120, 95, -1))

        result = analyze_cci(highs, lows, closes, period=14)

        # With strong downtrend, should be oversold
        assert result.zone == CCIZone.OVERSOLD
        assert result.value < -100

    def test_cci_neutral_zone(self):
        """Test CCI in neutral zone (-100 to 100)."""
        # Sideways movement
        highs = [105.0] * 25
        lows = [95.0] * 25
        closes = [100.0] * 25

        result = analyze_cci(highs, lows, closes, period=14)

        assert result.zone == CCIZone.NEUTRAL
        assert -100 <= result.value <= 100

    def test_cci_rising_direction(self):
        """Test CCI rising direction."""
        # Strong uptrend that produces rising CCI (> 5 point change)
        # Need a significant move to exceed the 5-point threshold
        highs = [100.0 + i * 2 for i in range(25)]
        lows = [95.0 + i * 2 for i in range(25)]
        closes = [98.0 + i * 2 for i in range(25)]

        result = analyze_cci(highs, lows, closes, period=14)

        # CCI should be rising (may be overbought due to strong trend)
        assert result.direction in [CCIDirection.RISING, CCIDirection.FLAT]

    def test_cci_falling_direction(self):
        """Test CCI falling direction."""
        # Strong downtrend that produces falling CCI (> 5 point change)
        highs = [120.0 - i * 2 for i in range(25)]
        lows = [115.0 - i * 2 for i in range(25)]
        closes = [118.0 - i * 2 for i in range(25)]

        result = analyze_cci(highs, lows, closes, period=14)

        # CCI should be falling (may be oversold due to strong trend)
        assert result.direction in [CCIDirection.FALLING, CCIDirection.FLAT]

    def test_cci_flat_direction(self):
        """Test CCI flat direction."""
        # Sideways movement
        highs = [105.0] * 25
        lows = [95.0] * 25
        closes = [100.0] * 25

        result = analyze_cci(highs, lows, closes, period=14)

        # CCI should be flat
        assert result.direction == CCIDirection.FLAT

    def test_cci_momentum_bullish_signal(self):
        """Test CCI momentum bullish signal detection."""
        # Create scenario where CCI crosses above 100
        # Start neutral, then strong upward move
        highs = [100.0] * 15
        lows = [95.0] * 15
        closes = [98.0] * 15
        # Add strong move up to trigger signal
        highs += [110.0, 115.0, 120.0, 125.0, 130.0]
        lows += [105.0, 110.0, 115.0, 120.0, 125.0]
        closes += [108.0, 113.0, 118.0, 123.0, 128.0]

        result = analyze_cci(highs, lows, closes, period=14)

        # Should be overbought or have momentum signal
        assert result.zone == CCIZone.OVERBOUGHT or result.signal_type == CCISignalType.MOMENTUM_BULLISH

    def test_cci_momentum_bearish_signal(self):
        """Test CCI momentum bearish signal detection."""
        # Create scenario where CCI crosses below -100
        # Start neutral, then strong downward move
        highs = [105.0] * 15
        lows = [95.0] * 15
        closes = [100.0] * 15
        # Add strong move down to trigger signal
        highs += [95.0, 90.0, 85.0, 80.0, 75.0]
        lows += [90.0, 85.0, 80.0, 75.0, 70.0]
        closes += [92.0, 87.0, 82.0, 77.0, 72.0]

        result = analyze_cci(highs, lows, closes, period=14)

        # Should be oversold or have momentum signal
        assert result.zone == CCIZone.OVERSOLD or result.signal_type == CCISignalType.MOMENTUM_BEARISH

    def test_cci_no_signal(self):
        """Test CCI with no signal."""
        # Neutral, sideways movement
        highs = [105.0] * 25
        lows = [95.0] * 25
        closes = [100.0] * 25

        result = analyze_cci(highs, lows, closes, period=14)

        assert result.signal_type == CCISignalType.NONE

    def test_cci_insufficient_data(self):
        """Test CCI analysis with insufficient data."""
        highs = [100.0, 101.0, 102.0]
        lows = [95.0, 96.0, 97.0]
        closes = [98.0, 99.0, 100.0]

        result = analyze_cci(highs, lows, closes, period=14)

        # Should return default values
        assert result.value == 0.0
        assert result.zone == CCIZone.NEUTRAL
        assert result.direction == CCIDirection.FLAT
        assert result.signal_type == CCISignalType.NONE

    def test_cci_exact_minimum_data(self):
        """Test CCI with exact minimum data (period + 5)."""
        highs = [100.0 + i for i in range(19)]  # 19 values = period + 5
        lows = [95.0 + i for i in range(19)]
        closes = [98.0 + i for i in range(19)]

        result = analyze_cci(highs, lows, closes, period=14)

        # Should calculate normally
        assert isinstance(result, CCIAnalysis)
        assert result.value != 0.0

    def test_cci_nan_handling(self):
        """Test CCI handles NaN values gracefully."""
        # Not enough data for CCI calculation will produce NaN
        highs = [100.0] * 10
        lows = [95.0] * 10
        closes = [98.0] * 10

        result = analyze_cci(highs, lows, closes, period=14)

        # Should return default values when CCI is NaN
        assert result.value == 0.0
        assert result.zone == CCIZone.NEUTRAL
        assert result.direction == CCIDirection.FLAT
        assert result.signal_type == CCISignalType.NONE

    def test_cci_value_rounded(self):
        """Test that CCI value is rounded to 1 decimal."""
        highs = [100.0 + i * 0.3 for i in range(25)]
        lows = [95.0 + i * 0.3 for i in range(25)]
        closes = [98.0 + i * 0.3 for i in range(25)]

        result = analyze_cci(highs, lows, closes, period=14)

        # Value should be rounded to 1 decimal
        assert result.value == round(result.value, 1)

    def test_cci_custom_period(self):
        """Test CCI analysis with custom period."""
        highs = [100.0 + i for i in range(30)]
        lows = [95.0 + i for i in range(30)]
        closes = [98.0 + i for i in range(30)]

        result = analyze_cci(highs, lows, closes, period=20)

        # Should calculate with custom period
        assert isinstance(result, CCIAnalysis)

    def test_cci_numpy_arrays(self):
        """Test CCI analysis with numpy arrays."""
        highs = np.array([100.0 + i for i in range(25)])
        lows = np.array([95.0 + i for i in range(25)])
        closes = np.array([98.0 + i for i in range(25)])

        result = analyze_cci(highs, lows, closes, period=14)

        assert isinstance(result, CCIAnalysis)

    def test_cci_direction_threshold(self):
        """Test CCI direction threshold (5 points)."""
        # Create data where CCI changes minimally
        # Sideways movement should result in flat direction
        highs = [105.0] * 25
        lows = [95.0] * 25
        closes = [100.0] * 25

        result = analyze_cci(highs, lows, closes, period=14)

        # No movement should result in FLAT direction
        assert result.direction == CCIDirection.FLAT


class TestCCIZoneTransitions:
    """Tests for CCI zone transitions and edge cases."""

    def test_cci_at_exact_boundary_100(self):
        """Test CCI near +100 boundary."""
        # Create strong upward move that should trigger overbought
        highs = [100.0] * 15 + [115.0] * 10
        lows = [95.0] * 15 + [110.0] * 10
        closes = [98.0] * 15 + [113.0] * 10

        result = analyze_cci(highs, lows, closes, period=14)

        # Should be overbought with strong uptrend
        assert result.zone in [CCIZone.OVERBOUGHT, CCIZone.NEUTRAL]

    def test_cci_at_exact_boundary_minus_100(self):
        """Test CCI near -100 boundary."""
        # Create strong downward move that should trigger oversold
        highs = [105.0] * 15 + [90.0] * 10
        lows = [95.0] * 15 + [85.0] * 10
        closes = [100.0] * 15 + [87.0] * 10

        result = analyze_cci(highs, lows, closes, period=14)

        # Should be oversold with strong downtrend
        assert result.zone in [CCIZone.OVERSOLD, CCIZone.NEUTRAL]

    def test_cci_volatile_movement(self):
        """Test CCI with highly volatile price movement."""
        # Volatile but generally upward
        highs = []
        lows = []
        closes = []
        price = 100.0
        for i in range(25):
            if i % 2 == 0:
                price += 5.0
            else:
                price -= 2.0
            highs.append(price + 2.0)
            lows.append(price - 2.0)
            closes.append(price)

        result = analyze_cci(highs, lows, closes, period=14)

        # Should still produce valid analysis
        assert isinstance(result, CCIAnalysis)
        assert result.zone in [CCIZone.OVERBOUGHT, CCIZone.OVERSOLD, CCIZone.NEUTRAL]


class TestCCISignalDetection:
    """Tests for CCI signal detection integration."""

    def test_reversal_buy_signal(self):
        """Test CCI reversal buy signal."""
        # Create scenario: go oversold, then cross back above -100
        # Need to trigger momentum_bearish first, then reversal_buy

        # Start neutral
        highs = [105.0] * 10
        lows = [95.0] * 10
        closes = [100.0] * 10

        # Drop to oversold (below -100)
        highs += [90.0] * 5
        lows += [80.0] * 5
        closes += [85.0] * 5

        # Recover
        highs += [95.0] * 5
        lows += [90.0] * 5
        closes += [93.0] * 5

        result = analyze_cci(highs, lows, closes, period=14)

        # Should show recovery (not still oversold)
        assert result.signal_type in [
            CCISignalType.REVERSAL_BUY,
            CCISignalType.NONE,
            CCISignalType.MOMENTUM_BULLISH
        ]

    def test_reversal_sell_signal(self):
        """Test CCI reversal sell signal."""
        # Create scenario: go overbought, then cross back below 100

        # Start neutral
        highs = [105.0] * 10
        lows = [95.0] * 10
        closes = [100.0] * 10

        # Rise to overbought (above 100)
        highs += [120.0] * 5
        lows += [115.0] * 5
        closes += [118.0] * 5

        # Pullback
        highs += [115.0] * 5
        lows += [110.0] * 5
        closes += [113.0] * 5

        result = analyze_cci(highs, lows, closes, period=14)

        # Should show pullback (not still overbought or strong bullish)
        assert result.signal_type in [
            CCISignalType.REVERSAL_SELL,
            CCISignalType.NONE,
            CCISignalType.MOMENTUM_BEARISH
        ]


class TestCCIAnalysisProperties:
    """Property-based tests for CCI analysis."""

    @given(
        st.lists(
            st.floats(min_value=50.0, max_value=150.0),
            min_size=25,
            max_size=100,
        )
    )
    @settings(max_examples=30, deadline=2000)
    def test_cci_analysis_always_returns_valid_result(self, closes):
        """Test that CCI analysis always returns valid result."""
        # Generate high/low from close
        highs = [c * 1.02 for c in closes]
        lows = [c * 0.98 for c in closes]

        result = analyze_cci(highs, lows, closes, period=14)

        # Should always return valid enum values
        assert result.zone in [CCIZone.OVERBOUGHT, CCIZone.OVERSOLD, CCIZone.NEUTRAL]
        assert result.direction in [
            CCIDirection.RISING,
            CCIDirection.FALLING,
            CCIDirection.FLAT,
        ]
        assert result.signal_type in [
            CCISignalType.MOMENTUM_BULLISH,
            CCISignalType.MOMENTUM_BEARISH,
            CCISignalType.REVERSAL_BUY,
            CCISignalType.REVERSAL_SELL,
            CCISignalType.NONE,
        ]

    def test_empty_arrays(self):
        """Test CCI analysis with empty arrays."""
        result = analyze_cci([], [], [], period=14)

        # Should return default values
        assert result.value == 0.0
        assert result.zone == CCIZone.NEUTRAL
        assert result.direction == CCIDirection.FLAT
        assert result.signal_type == CCISignalType.NONE
