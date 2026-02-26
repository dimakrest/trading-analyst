"""Tests for extended technical indicator functions (MACD, Stochastic, ADX, Support/Resistance)."""

import numpy as np
import pytest

from app.indicators.technical import (
    average_directional_index,
    macd,
    stochastic_oscillator,
    support_resistance_levels,
)


class TestMACD:
    """Tests for MACD indicator."""

    def test_macd_basic_calculation(self):
        """Test MACD returns three arrays of correct length."""
        prices = list(range(1, 51))  # 50 prices
        macd_line, signal_line, histogram = macd(prices)

        assert len(macd_line) == 50
        assert len(signal_line) == 50
        assert len(histogram) == 50

    def test_macd_uptrend_positive(self):
        """Test MACD is positive in uptrend."""
        # Strong uptrend
        prices = [100 + i * 2 for i in range(50)]
        macd_line, signal_line, histogram = macd(prices)

        # Latest MACD should be positive in uptrend
        assert not np.isnan(macd_line[-1])
        assert macd_line[-1] > 0

    def test_macd_downtrend_negative(self):
        """Test MACD is negative in downtrend."""
        # Strong downtrend
        prices = [200 - i * 2 for i in range(50)]
        macd_line, signal_line, histogram = macd(prices)

        assert not np.isnan(macd_line[-1])
        assert macd_line[-1] < 0

    def test_macd_histogram_calculation(self):
        """Test histogram is difference between MACD and signal."""
        prices = [100 + i * 1.5 for i in range(50)]
        macd_line, signal_line, histogram = macd(prices)

        # Histogram should be MACD - Signal
        for i in range(len(histogram)):
            if not np.isnan(histogram[i]):
                expected = macd_line[i] - signal_line[i]
                assert abs(histogram[i] - expected) < 1e-10

    def test_macd_invalid_zero_period(self):
        """Test MACD raises error for zero periods."""
        prices = [100.0] * 50

        with pytest.raises(ValueError, match="greater than 0"):
            macd(prices, fast_period=0)

        with pytest.raises(ValueError, match="greater than 0"):
            macd(prices, slow_period=0)

        with pytest.raises(ValueError, match="greater than 0"):
            macd(prices, signal_period=0)

    def test_macd_invalid_negative_period(self):
        """Test MACD raises error for negative periods."""
        prices = [100.0] * 50

        with pytest.raises(ValueError, match="greater than 0"):
            macd(prices, fast_period=-1)

    def test_macd_fast_period_must_be_less_than_slow(self):
        """Test MACD raises error when fast period >= slow period."""
        prices = [100.0] * 50

        with pytest.raises(ValueError, match="Fast period must be less"):
            macd(prices, fast_period=26, slow_period=12)

        with pytest.raises(ValueError, match="Fast period must be less"):
            macd(prices, fast_period=20, slow_period=20)

    def test_macd_empty_array(self):
        """Test MACD raises error for empty array."""
        with pytest.raises(ValueError, match="cannot be empty"):
            macd([])

    def test_macd_custom_periods(self):
        """Test MACD with custom periods."""
        prices = [100 + i for i in range(100)]
        macd_line, signal_line, histogram = macd(
            prices, fast_period=5, slow_period=10, signal_period=3
        )

        assert len(macd_line) == 100
        # Should have values earlier with shorter periods
        assert not np.isnan(macd_line[10])


class TestStochasticOscillator:
    """Tests for Stochastic Oscillator."""

    def test_stochastic_basic_calculation(self):
        """Test Stochastic returns two arrays of correct length."""
        high = [110, 112, 115, 113, 116, 118, 120, 119, 121, 123, 125, 124, 126, 128, 130]
        low = [100, 102, 105, 103, 106, 108, 110, 109, 111, 113, 115, 114, 116, 118, 120]
        close = [105, 108, 110, 108, 112, 114, 115, 114, 117, 119, 121, 120, 122, 124, 126]

        k, d = stochastic_oscillator(high, low, close)

        assert len(k) == 15
        assert len(d) == 15

    def test_stochastic_range(self):
        """Test Stochastic %K is in 0-100 range."""
        high = [110 + i for i in range(20)]
        low = [100 + i for i in range(20)]
        close = [105 + i for i in range(20)]

        k, d = stochastic_oscillator(high, low, close)

        # Check non-NaN values are in range
        valid_k = k[~np.isnan(k)]
        assert all(0 <= v <= 100 for v in valid_k)

    def test_stochastic_overbought(self):
        """Test Stochastic shows overbought at highs."""
        # Price at top of range
        high = [100.0] * 20
        low = [90.0] * 20
        close = [99.0] * 20  # Close near high

        k, d = stochastic_oscillator(high, low, close)

        # Should be near 100 (overbought)
        assert k[-1] > 80

    def test_stochastic_oversold(self):
        """Test Stochastic shows oversold at lows."""
        # Price at bottom of range
        high = [100.0] * 20
        low = [90.0] * 20
        close = [91.0] * 20  # Close near low

        k, d = stochastic_oscillator(high, low, close)

        # Should be near 0 (oversold)
        assert k[-1] < 20

    def test_stochastic_neutral_no_range(self):
        """Test Stochastic returns 50 when no price range."""
        # Constant prices (high = low)
        high = [100.0] * 20
        low = [100.0] * 20
        close = [100.0] * 20

        k, d = stochastic_oscillator(high, low, close)

        # Should be 50 (neutral) when no range
        assert k[-1] == 50

    def test_stochastic_invalid_different_lengths(self):
        """Test Stochastic raises error for different length arrays."""
        with pytest.raises(ValueError, match="same length"):
            stochastic_oscillator([100, 101], [90], [95, 96])

    def test_stochastic_invalid_empty_arrays(self):
        """Test Stochastic raises error for empty arrays."""
        with pytest.raises(ValueError, match="cannot be empty"):
            stochastic_oscillator([], [], [])

    def test_stochastic_invalid_zero_period(self):
        """Test Stochastic raises error for zero periods."""
        with pytest.raises(ValueError, match="greater than 0"):
            stochastic_oscillator([100], [90], [95], k_period=0)

        with pytest.raises(ValueError, match="greater than 0"):
            stochastic_oscillator([100], [90], [95], d_period=0)

    def test_stochastic_warmup_period(self):
        """Test Stochastic has correct warmup period with NaN values."""
        high = [110 + i for i in range(20)]
        low = [100 + i for i in range(20)]
        close = [105 + i for i in range(20)]

        k, d = stochastic_oscillator(high, low, close, k_period=14, d_period=3)

        # First 13 values (k_period - 1) should be NaN
        assert all(np.isnan(k[i]) for i in range(13))
        # From index 13, k should have values
        assert not np.isnan(k[13])


class TestADX:
    """Tests for Average Directional Index."""

    def test_adx_basic_calculation(self):
        """Test ADX returns three arrays of correct length."""
        n = 50
        np.random.seed(42)
        high = [100 + i + np.random.uniform(0, 2) for i in range(n)]
        low = [98 + i + np.random.uniform(0, 1) for i in range(n)]
        close = [99 + i + np.random.uniform(0, 1) for i in range(n)]

        adx, plus_di, minus_di = average_directional_index(high, low, close)

        assert len(adx) == n
        assert len(plus_di) == n
        assert len(minus_di) == n

    def test_adx_range(self):
        """Test ADX values are in 0-100 range."""
        n = 50
        high = [100 + i * 2 for i in range(n)]
        low = [98 + i * 2 for i in range(n)]
        close = [99 + i * 2 for i in range(n)]

        adx, plus_di, minus_di = average_directional_index(high, low, close)

        # Check non-NaN values are in valid range
        valid_adx = adx[~np.isnan(adx)]
        if len(valid_adx) > 0:
            assert all(0 <= v <= 100 for v in valid_adx)

    def test_adx_strong_uptrend_plus_di_greater(self):
        """Test +DI > -DI in strong uptrend."""
        n = 50
        # Strong consistent uptrend
        high = [100 + i * 3 for i in range(n)]
        low = [98 + i * 3 for i in range(n)]
        close = [99 + i * 3 for i in range(n)]

        adx, plus_di, minus_di = average_directional_index(high, low, close)

        # In uptrend, +DI should be greater than -DI
        if not np.isnan(plus_di[-1]) and not np.isnan(minus_di[-1]):
            assert plus_di[-1] > minus_di[-1]

    def test_adx_strong_downtrend_minus_di_greater(self):
        """Test -DI > +DI in strong downtrend."""
        n = 50
        # Strong consistent downtrend
        high = [200 - i * 3 for i in range(n)]
        low = [198 - i * 3 for i in range(n)]
        close = [199 - i * 3 for i in range(n)]

        adx, plus_di, minus_di = average_directional_index(high, low, close)

        # In downtrend, -DI should be greater than +DI
        if not np.isnan(plus_di[-1]) and not np.isnan(minus_di[-1]):
            assert minus_di[-1] > plus_di[-1]

    def test_adx_invalid_different_lengths(self):
        """Test ADX raises error for different length arrays."""
        with pytest.raises(ValueError, match="same length"):
            average_directional_index([100, 101], [90], [95, 96])

    def test_adx_invalid_empty_arrays(self):
        """Test ADX raises error for empty arrays."""
        with pytest.raises(ValueError, match="cannot be empty"):
            average_directional_index([], [], [])

    def test_adx_invalid_zero_period(self):
        """Test ADX raises error for zero period."""
        with pytest.raises(ValueError, match="greater than 0"):
            average_directional_index([100], [90], [95], period=0)

    def test_adx_invalid_negative_period(self):
        """Test ADX raises error for negative period."""
        with pytest.raises(ValueError, match="greater than 0"):
            average_directional_index([100], [90], [95], period=-5)

    def test_adx_warmup_period(self):
        """Test ADX has correct warmup period."""
        n = 50
        high = [100 + i for i in range(n)]
        low = [98 + i for i in range(n)]
        close = [99 + i for i in range(n)]

        adx, plus_di, minus_di = average_directional_index(high, low, close, period=14)

        # First 13 values (period - 1) should be NaN for DI
        assert all(np.isnan(plus_di[i]) for i in range(13))


class TestSupportResistance:
    """Tests for Support/Resistance levels."""

    def test_support_resistance_basic(self):
        """Test S/R returns correct structure."""
        high = [105, 108, 110, 107, 112]
        low = [100, 103, 105, 102, 107]
        close = [103, 106, 108, 105, 110]

        support, resistance, pivot = support_resistance_levels(high, low, close)

        assert len(support) == 3
        assert len(resistance) == 3
        assert pivot is not None

    def test_support_resistance_pivot_calculation(self):
        """Test pivot point is (H + L + C) / 3."""
        high = [110]
        low = [90]
        close = [100]

        support, resistance, pivot = support_resistance_levels(high, low, close)

        # Pivot should be (110 + 90 + 100) / 3 = 100
        assert abs(pivot - 100) < 0.01

    def test_support_resistance_ordering(self):
        """Test S/R levels are properly ordered."""
        high = [110]
        low = [90]
        close = [100]

        support, resistance, pivot = support_resistance_levels(high, low, close)

        # Support levels should be below pivot
        assert all(s < pivot for s in support if s is not None)

        # Resistance levels should be above pivot
        assert all(r > pivot for r in resistance if r is not None)

    def test_support_resistance_s1_r1_closest(self):
        """Test S1/R1 are closest to pivot."""
        high = [110]
        low = [90]
        close = [100]

        support, resistance, pivot = support_resistance_levels(high, low, close)

        # S1 should be closest to pivot (highest support)
        assert support[0] > support[1] > support[2]

        # R1 should be closest to pivot (lowest resistance)
        assert resistance[0] < resistance[1] < resistance[2]

    def test_support_resistance_empty_input(self):
        """Test S/R handles empty input gracefully."""
        support, resistance, pivot = support_resistance_levels([], [], [])

        assert support == [None, None, None]
        assert resistance == [None, None, None]
        assert pivot is None

    def test_support_resistance_custom_num_levels(self):
        """Test S/R with custom number of levels."""
        high = [110]
        low = [90]
        close = [100]

        support, resistance, pivot = support_resistance_levels(high, low, close, num_levels=2)

        assert len(support) == 2
        assert len(resistance) == 2

    def test_support_resistance_uses_latest_candle(self):
        """Test S/R uses most recent candle for calculation."""
        # Different candles
        high = [100, 110, 120]
        low = [90, 100, 110]
        close = [95, 105, 115]

        support, resistance, pivot = support_resistance_levels(high, low, close)

        # Should use last candle: (120 + 110 + 115) / 3 = 115
        expected_pivot = (120 + 110 + 115) / 3
        assert abs(pivot - expected_pivot) < 0.01

    def test_support_resistance_formulas(self):
        """Test S/R level formulas are correct."""
        h, l, c = 110, 90, 100
        high = [h]
        low = [l]
        close = [c]

        support, resistance, pivot = support_resistance_levels(high, low, close)

        pp = (h + l + c) / 3  # 100

        # R1 = (2 * PP) - L = 200 - 90 = 110
        expected_r1 = (2 * pp) - l
        assert abs(resistance[0] - expected_r1) < 0.01

        # S1 = (2 * PP) - H = 200 - 110 = 90
        expected_s1 = (2 * pp) - h
        assert abs(support[0] - expected_s1) < 0.01

        # R2 = PP + (H - L) = 100 + 20 = 120
        expected_r2 = pp + (h - l)
        assert abs(resistance[1] - expected_r2) < 0.01

        # S2 = PP - (H - L) = 100 - 20 = 80
        expected_s2 = pp - (h - l)
        assert abs(support[1] - expected_s2) < 0.01
