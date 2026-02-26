"""Comprehensive unit tests for technical indicators.

Tests cover mathematical accuracy, edge cases, and performance requirements.
"""


import numpy as np
import pytest

from app.indicators.technical import average_directional_index
from app.indicators.technical import bollinger_bands
from app.indicators.technical import bollinger_band_width
from app.indicators.technical import exponential_moving_average
from app.indicators.technical import percentile_rank
from app.indicators.technical import relative_strength_index
from app.indicators.technical import simple_moving_average
from app.indicators.technical import typical_price


class TestSimpleMovingAverage:
    """Test cases for Simple Moving Average (SMA)."""

    def test_sma_basic_calculation(self):
        """Test SMA with known values."""
        prices = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]
        sma_3 = simple_moving_average(prices, 3)

        # Expected: [NaN, NaN, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0]
        expected = [np.nan, np.nan, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0]

        # Check NaN values
        assert np.isnan(sma_3[0])
        assert np.isnan(sma_3[1])

        # Check calculated values
        np.testing.assert_array_almost_equal(sma_3[2:], expected[2:], decimal=6)

    def test_sma_single_period(self):
        """Test SMA with period of 1."""
        prices = [10.0, 20.0, 30.0]
        sma_1 = simple_moving_average(prices, 1)

        # Should return the same values as input
        np.testing.assert_array_equal(sma_1, prices)

    def test_sma_insufficient_data(self):
        """Test SMA when data length is less than period."""
        prices = [1.0, 2.0]
        sma_5 = simple_moving_average(prices, 5)

        # Should return all NaN
        assert np.all(np.isnan(sma_5))
        assert len(sma_5) == len(prices)

    def test_sma_empty_array(self):
        """Test SMA with empty array."""
        with pytest.raises(ValueError, match="Prices array cannot be empty"):
            simple_moving_average([], 5)

    def test_sma_invalid_period(self):
        """Test SMA with invalid period."""
        prices = [1.0, 2.0, 3.0]

        with pytest.raises(ValueError, match="Period must be greater than 0"):
            simple_moving_average(prices, 0)

        with pytest.raises(ValueError, match="Period must be greater than 0"):
            simple_moving_average(prices, -1)

    def test_sma_numpy_array_input(self):
        """Test SMA with numpy array input."""
        prices = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        sma_3 = simple_moving_average(prices, 3)

        expected = [np.nan, np.nan, 2.0, 3.0, 4.0]
        np.testing.assert_array_almost_equal(sma_3[2:], expected[2:], decimal=6)

    def test_sma_with_nans(self):
        """Test SMA handling of NaN values in input."""
        prices = [1.0, 2.0, np.nan, 4.0, 5.0]
        sma_3 = simple_moving_average(prices, 3)

        # NaN in input should propagate to output
        assert np.isnan(sma_3[0])  # Insufficient data
        assert np.isnan(sma_3[1])  # Insufficient data
        assert np.isnan(sma_3[2])  # Contains NaN in window


class TestExponentialMovingAverage:
    """Test cases for Exponential Moving Average (EMA)."""

    def test_ema_basic_calculation(self):
        """Test EMA with known values."""
        prices = [22.27, 22.19, 22.08, 22.17, 22.18, 22.13, 22.23, 22.43, 22.24, 22.29]
        ema_10 = exponential_moving_average(prices, 10)

        # First value should equal first price
        assert ema_10[0] == prices[0]

        # EMA should be responsive to price changes
        assert len(ema_10) == len(prices)
        assert not np.any(np.isnan(ema_10))

    def test_ema_alpha_calculation(self):
        """Test that EMA uses correct alpha value."""
        prices = [10.0, 12.0, 14.0]
        ema_2 = exponential_moving_average(prices, 2)

        # Alpha for period 2 should be 2/(2+1) = 0.6667
        expected_1 = 10.0  # First value
        expected_2 = 0.6667 * 12.0 + 0.3333 * 10.0  # ≈ 11.333
        expected_3 = 0.6667 * 14.0 + 0.3333 * expected_2  # ≈ 13.111

        np.testing.assert_almost_equal(ema_2[0], expected_1, decimal=3)
        np.testing.assert_almost_equal(ema_2[1], expected_2, decimal=3)
        np.testing.assert_almost_equal(ema_2[2], expected_3, decimal=3)

    def test_ema_single_value(self):
        """Test EMA with single value."""
        prices = [100.0]
        ema_5 = exponential_moving_average(prices, 5)

        assert len(ema_5) == 1
        assert ema_5[0] == 100.0

    def test_ema_invalid_inputs(self):
        """Test EMA with invalid inputs."""
        prices = [1.0, 2.0, 3.0]

        with pytest.raises(ValueError, match="Period must be greater than 0"):
            exponential_moving_average(prices, 0)

        with pytest.raises(ValueError, match="Prices array cannot be empty"):
            exponential_moving_average([], 5)


class TestRelativeStrengthIndex:
    """Test cases for Relative Strength Index (RSI)."""

    def test_rsi_basic_calculation(self):
        """Test RSI with known values."""
        # Sample data that should produce predictable RSI
        prices = [
            44.0,
            44.34,
            44.09,
            44.15,
            43.61,
            44.33,
            44.83,
            45.85,
            46.08,
            45.89,
            46.03,
            46.83,
            47.69,
            46.49,
            46.26,
            47.09,
            46.66,
            46.80,
            46.23,
            46.99,
        ]

        rsi_14 = relative_strength_index(prices, 14)

        # First value should be NaN (no delta)
        assert np.isnan(rsi_14[0])

        # RSI values should be between 0 and 100
        valid_rsi = rsi_14[~np.isnan(rsi_14)]
        assert np.all(valid_rsi >= 0)
        assert np.all(valid_rsi <= 100)

        # Should have enough data for RSI calculation towards the end
        assert not np.isnan(rsi_14[-1])

    def test_rsi_all_gains(self):
        """Test RSI when all price changes are gains."""
        prices = [10.0, 11.0, 12.0, 13.0, 14.0, 15.0]
        rsi_4 = relative_strength_index(prices, 4)

        # When there are only gains, RSI should approach 100
        final_rsi = rsi_4[-1]
        assert final_rsi == 100.0

    def test_rsi_all_losses(self):
        """Test RSI when all price changes are losses."""
        prices = [15.0, 14.0, 13.0, 12.0, 11.0, 10.0]
        rsi_4 = relative_strength_index(prices, 4)

        # When there are only losses, RSI should approach 0
        final_rsi = rsi_4[-1]
        assert final_rsi == 0.0

    def test_rsi_insufficient_data(self):
        """Test RSI with insufficient data."""
        prices = [10.0]
        rsi_14 = relative_strength_index(prices, 14)

        assert len(rsi_14) == 1
        assert np.isnan(rsi_14[0])

    def test_rsi_invalid_inputs(self):
        """Test RSI with invalid inputs."""
        prices = [1.0, 2.0, 3.0]

        with pytest.raises(ValueError, match="Period must be greater than 0"):
            relative_strength_index(prices, 0)

        with pytest.raises(ValueError, match="Prices array cannot be empty"):
            relative_strength_index([], 14)


class TestBollingerBands:
    """Test cases for Bollinger Bands."""

    def test_bollinger_bands_basic(self):
        """Test Bollinger Bands with known values."""
        prices = [20.0, 21.0, 22.0, 23.0, 24.0, 25.0, 26.0, 27.0, 28.0, 29.0]
        upper, middle, lower = bollinger_bands(prices, 5, 2.0)

        # Middle band should be SMA
        expected_middle = simple_moving_average(prices, 5)
        np.testing.assert_array_equal(middle, expected_middle)

        # Check relationships
        valid_indices = ~np.isnan(upper)
        assert np.all(upper[valid_indices] > middle[valid_indices])
        assert np.all(lower[valid_indices] < middle[valid_indices])

        # Bands should be symmetric around middle
        band_width_upper = upper - middle
        band_width_lower = middle - lower
        np.testing.assert_array_almost_equal(
            band_width_upper[valid_indices], band_width_lower[valid_indices], decimal=10
        )

    def test_bollinger_bands_no_volatility(self):
        """Test Bollinger Bands with constant prices (no volatility)."""
        prices = [100.0] * 10
        upper, middle, lower = bollinger_bands(prices, 5, 2.0)

        # With no volatility, all bands should be equal
        valid_indices = ~np.isnan(upper)
        np.testing.assert_array_equal(upper[valid_indices], middle[valid_indices])
        np.testing.assert_array_equal(lower[valid_indices], middle[valid_indices])

    def test_bollinger_bands_invalid_inputs(self):
        """Test Bollinger Bands with invalid inputs."""
        prices = [1.0, 2.0, 3.0]

        with pytest.raises(ValueError, match="Period must be greater than 0"):
            bollinger_bands(prices, 0)

        with pytest.raises(
            ValueError, match="Standard deviation multiplier must be greater than 0"
        ):
            bollinger_bands(prices, 5, 0)

        with pytest.raises(ValueError, match="Prices array cannot be empty"):
            bollinger_bands([], 5)


class TestTypicalPrice:
    """Test cases for Typical Price."""

    def test_typical_price_calculation(self):
        """Test typical price calculation."""
        high = [102.0, 103.0, 104.0]
        low = [98.0, 99.0, 100.0]
        close = [100.0, 101.0, 102.0]

        tp = typical_price(high, low, close)

        expected = [(102 + 98 + 100) / 3, (103 + 99 + 101) / 3, (104 + 100 + 102) / 3]
        np.testing.assert_array_almost_equal(tp, expected, decimal=6)

    def test_typical_price_invalid_inputs(self):
        """Test typical price with invalid inputs."""
        high = [102.0, 103.0]
        low = [98.0]  # Different length
        close = [100.0, 101.0]

        with pytest.raises(ValueError, match="High, low, and close arrays must have same length"):
            typical_price(high, low, close)

        with pytest.raises(ValueError, match="Arrays cannot be empty"):
            typical_price([], [], [])


class TestPerformance:
    """Performance tests for indicators."""

    def test_indicator_performance(self):
        """Test that indicators meet performance requirements."""
        import time

        # Generate large dataset
        np.random.seed(42)
        size = 10000
        prices = np.random.random(size) * 100 + 100

        # Test SMA performance
        start_time = time.time()
        sma = simple_moving_average(prices, 50)
        sma_time = time.time() - start_time

        # Test EMA performance
        start_time = time.time()
        ema = exponential_moving_average(prices, 50)
        ema_time = time.time() - start_time

        # Test RSI performance
        start_time = time.time()
        rsi = relative_strength_index(prices, 14)
        rsi_time = time.time() - start_time

        # Performance should be under 10ms for each indicator (generous threshold)
        assert sma_time < 0.01, f"SMA took {sma_time:.4f}s, expected < 0.01s"
        assert ema_time < 0.01, f"EMA took {ema_time:.4f}s, expected < 0.01s"
        assert rsi_time < 0.01, f"RSI took {rsi_time:.4f}s, expected < 0.01s"

        # Verify results are sensible
        assert len(sma) == size
        assert len(ema) == size
        assert len(rsi) == size


class TestMathematicalAccuracy:
    """Test mathematical accuracy against known values."""

    def test_sma_accuracy(self):
        """Test SMA against hand-calculated values."""
        prices = [10.0, 12.0, 14.0, 16.0, 18.0]
        sma_3 = simple_moving_average(prices, 3)

        # Hand calculated:
        # Index 2: (10+12+14)/3 = 12.0
        # Index 3: (12+14+16)/3 = 14.0
        # Index 4: (14+16+18)/3 = 16.0

        expected = [np.nan, np.nan, 12.0, 14.0, 16.0]
        np.testing.assert_array_almost_equal(sma_3[2:], expected[2:], decimal=10)

    def test_ema_accuracy(self):
        """Test EMA against hand-calculated values."""
        prices = [10.0, 12.0, 14.0]
        ema_2 = exponential_moving_average(prices, 2)

        # Alpha = 2/(2+1) = 2/3 = 0.6667
        # EMA[0] = 10.0
        # EMA[1] = 0.6667 * 12 + 0.3333 * 10 = 8.0 + 3.333 = 11.333
        # EMA[2] = 0.6667 * 14 + 0.3333 * 11.333 = 9.333 + 3.778 = 13.111

        expected = [10.0, 11.333333, 13.111111]
        np.testing.assert_array_almost_equal(ema_2, expected, decimal=5)

    def test_bollinger_bands_accuracy(self):
        """Test Bollinger Bands against hand-calculated values."""
        prices = [10.0, 10.0, 10.0, 10.0, 10.0]  # No volatility
        upper, middle, lower = bollinger_bands(prices, 3, 2.0)

        # With no volatility, std = 0, so all bands should equal SMA
        # SMA for last 3 values: (10+10+10)/3 = 10.0

        assert not np.isnan(upper[4])
        assert not np.isnan(middle[4])
        assert not np.isnan(lower[4])

        assert upper[4] == 10.0
        assert middle[4] == 10.0
        assert lower[4] == 10.0


class TestAverageDirectionalIndex:
    """Test cases for Average Directional Index (ADX)."""

    def test_adx_basic_calculation(self):
        """Test ADX with sufficient data returns valid values."""
        # Generate enough data for ADX calculation (needs ~28 points for period 14)
        np.random.seed(42)
        n = 50
        base = 100.0

        # Simulate realistic price movements
        close = np.cumsum(np.random.randn(n) * 1) + base
        high = close + np.abs(np.random.randn(n) * 0.5)
        low = close - np.abs(np.random.randn(n) * 0.5)

        adx, plus_di, minus_di = average_directional_index(high, low, close, 14)

        # Check array lengths
        assert len(adx) == n
        assert len(plus_di) == n
        assert len(minus_di) == n

        # ADX should have valid values after warmup period (2*period - 1 = 27)
        assert not np.isnan(adx[-1]), "ADX should have valid value at end"
        assert not np.isnan(plus_di[-1]), "+DI should have valid value at end"
        assert not np.isnan(minus_di[-1]), "-DI should have valid value at end"

    def test_adx_values_in_valid_range(self):
        """Test that ADX, +DI, and -DI are in valid 0-100 range."""
        np.random.seed(123)
        n = 100

        close = np.cumsum(np.random.randn(n) * 2) + 150.0
        high = close + np.abs(np.random.randn(n) * 1.0)
        low = close - np.abs(np.random.randn(n) * 1.0)

        adx, plus_di, minus_di = average_directional_index(high, low, close, 14)

        # Get valid (non-NaN) values
        valid_adx = adx[~np.isnan(adx)]
        valid_plus_di = plus_di[~np.isnan(plus_di)]
        valid_minus_di = minus_di[~np.isnan(minus_di)]

        # All values should be between 0 and 100
        assert np.all(valid_adx >= 0), "ADX should be >= 0"
        assert np.all(valid_adx <= 100), "ADX should be <= 100"
        assert np.all(valid_plus_di >= 0), "+DI should be >= 0"
        assert np.all(valid_plus_di <= 100), "+DI should be <= 100"
        assert np.all(valid_minus_di >= 0), "-DI should be >= 0"
        assert np.all(valid_minus_di <= 100), "-DI should be <= 100"

    def test_adx_warmup_period(self):
        """Test that ADX respects warmup period requirements."""
        np.random.seed(42)
        n = 50
        period = 14

        close = np.cumsum(np.random.randn(n)) + 100.0
        high = close + 1.0
        low = close - 1.0

        adx, plus_di, minus_di = average_directional_index(high, low, close, period)

        # +DI/-DI warmup: period - 1 = 13 (first valid at index 13)
        # ADX warmup: 2*period - 2 = 26 (first valid at index 26)

        # Check +DI/-DI have NaN for first (period-1) values
        assert np.all(np.isnan(plus_di[: period - 1])), "+DI should be NaN before warmup"
        assert np.all(np.isnan(minus_di[: period - 1])), "-DI should be NaN before warmup"
        assert not np.isnan(plus_di[period - 1]), "+DI should be valid after warmup"
        assert not np.isnan(minus_di[period - 1]), "-DI should be valid after warmup"

        # Check ADX has NaN for first (2*period - 2) values
        adx_warmup = 2 * period - 2
        assert np.all(np.isnan(adx[:adx_warmup])), "ADX should be NaN before warmup"
        assert not np.isnan(adx[adx_warmup]), "ADX should be valid after warmup"

    def test_adx_insufficient_data(self):
        """Test ADX with insufficient data returns all NaN."""
        # Only 20 data points (need ~28 for ADX with period 14)
        n = 20
        close = np.arange(n, dtype=float) + 100.0
        high = close + 1.0
        low = close - 1.0

        adx, plus_di, minus_di = average_directional_index(high, low, close, 14)

        # ADX should be all NaN (not enough data for double smoothing)
        assert np.all(np.isnan(adx)), "ADX should be all NaN with insufficient data"

        # +DI/-DI should have some valid values (only need single smoothing)
        assert not np.all(np.isnan(plus_di)), "+DI should have some valid values"
        assert not np.all(np.isnan(minus_di)), "-DI should have some valid values"

    def test_adx_strong_uptrend(self):
        """Test ADX behavior in strong uptrend."""
        n = 60
        # Create strong uptrend
        close = np.linspace(100, 150, n)
        high = close + 1.0
        low = close - 0.5

        adx, plus_di, minus_di = average_directional_index(high, low, close, 14)

        valid_adx = adx[~np.isnan(adx)]
        valid_plus_di = plus_di[~np.isnan(plus_di)]
        valid_minus_di = minus_di[~np.isnan(minus_di)]

        # In uptrend, +DI should be greater than -DI
        # Compare at positions where both are valid
        adx_start = 2 * 14 - 2
        assert valid_plus_di[-1] > valid_minus_di[-1], "+DI should exceed -DI in uptrend"

        # ADX should indicate trend strength (higher values = stronger trend)
        assert valid_adx[-1] > 0, "ADX should be positive in trending market"

    def test_adx_strong_downtrend(self):
        """Test ADX behavior in strong downtrend."""
        n = 60
        # Create strong downtrend
        close = np.linspace(150, 100, n)
        high = close + 0.5
        low = close - 1.0

        adx, plus_di, minus_di = average_directional_index(high, low, close, 14)

        valid_plus_di = plus_di[~np.isnan(plus_di)]
        valid_minus_di = minus_di[~np.isnan(minus_di)]

        # In downtrend, -DI should be greater than +DI
        assert valid_minus_di[-1] > valid_plus_di[-1], "-DI should exceed +DI in downtrend"

    def test_adx_sideways_market(self):
        """Test ADX behavior in sideways/ranging market."""
        n = 100
        # Create sideways movement (oscillating)
        close = 100.0 + 5.0 * np.sin(np.linspace(0, 4 * np.pi, n))
        high = close + 1.0
        low = close - 1.0

        adx, plus_di, minus_di = average_directional_index(high, low, close, 14)

        valid_adx = adx[~np.isnan(adx)]

        # In sideways market, ADX should be relatively low (weak trend)
        # Typically ADX < 25 indicates weak/no trend
        assert valid_adx[-1] < 50, "ADX should be relatively low in sideways market"

    def test_adx_different_periods(self):
        """Test ADX with different period settings."""
        np.random.seed(42)
        n = 100

        close = np.cumsum(np.random.randn(n)) + 100.0
        high = close + np.abs(np.random.randn(n) * 0.5)
        low = close - np.abs(np.random.randn(n) * 0.5)

        # Test with different periods
        for period in [7, 14, 21]:
            adx, plus_di, minus_di = average_directional_index(high, low, close, period)

            # All should produce valid results
            valid_adx = adx[~np.isnan(adx)]
            assert len(valid_adx) > 0, f"ADX with period {period} should have valid values"

            # Values should be in valid range
            assert np.all(valid_adx >= 0) and np.all(valid_adx <= 100)

    def test_adx_constant_prices(self):
        """Test ADX with constant prices (no movement)."""
        n = 50
        close = np.full(n, 100.0)
        high = np.full(n, 101.0)
        low = np.full(n, 99.0)

        adx, plus_di, minus_di = average_directional_index(high, low, close, 14)

        # With no directional movement, +DM and -DM are 0
        # This leads to +DI = -DI = 0, and DX = 0
        valid_adx = adx[~np.isnan(adx)]

        # ADX should be 0 or very close to 0 with no directional movement
        if len(valid_adx) > 0:
            assert np.all(valid_adx < 1), "ADX should be ~0 with no directional movement"

    def test_adx_numpy_array_input(self):
        """Test ADX accepts numpy arrays as input."""
        n = 50
        high = np.random.rand(n) * 10 + 100
        low = high - np.random.rand(n) * 2
        close = (high + low) / 2

        # Should not raise any errors
        adx, plus_di, minus_di = average_directional_index(high, low, close, 14)

        assert isinstance(adx, np.ndarray)
        assert isinstance(plus_di, np.ndarray)
        assert isinstance(minus_di, np.ndarray)

    def test_adx_list_input(self):
        """Test ADX accepts Python lists as input."""
        n = 50
        np.random.seed(42)
        high = list(np.random.rand(n) * 10 + 100)
        low = list(np.array(high) - np.random.rand(n) * 2)
        close = list((np.array(high) + np.array(low)) / 2)

        # Should not raise any errors
        adx, plus_di, minus_di = average_directional_index(high, low, close, 14)

        assert isinstance(adx, np.ndarray)
        assert len(adx) == n

    def test_adx_empty_array(self):
        """Test ADX with empty arrays."""
        with pytest.raises(ValueError):
            average_directional_index([], [], [], 14)

    def test_adx_invalid_period(self):
        """Test ADX with invalid period."""
        high = [101.0, 102.0, 103.0]
        low = [99.0, 100.0, 101.0]
        close = [100.0, 101.0, 102.0]

        with pytest.raises(ValueError):
            average_directional_index(high, low, close, 0)

        with pytest.raises(ValueError):
            average_directional_index(high, low, close, -1)

    def test_adx_mismatched_lengths(self):
        """Test ADX with mismatched array lengths."""
        high = [101.0, 102.0, 103.0]
        low = [99.0, 100.0]  # Different length
        close = [100.0, 101.0, 102.0]

        with pytest.raises(ValueError):
            average_directional_index(high, low, close, 14)


class TestBollingerBandWidth:
    """Test cases for Bollinger Band Width (BBW)."""

    def test_bbw_calculation(self):
        """Test BBW is calculated correctly."""
        # Create prices that form known Bollinger Bands
        prices = [100.0] * 20 + [105.0, 110.0, 100.0, 95.0, 100.0]
        bbw = bollinger_band_width(prices, period=20)

        # First 19 values should be NaN (insufficient data)
        assert np.all(np.isnan(bbw[:19]))
        # After that, values should be non-negative (zero volatility gives zero BBW)
        assert np.all(bbw[19:] >= 0)
        # At least one value should be positive (after prices change)
        assert np.any(bbw[19:] > 0)

    def test_bbw_tight_vs_wide(self):
        """Test that tight prices produce lower BBW than wide prices."""
        # Tight range prices
        tight_prices = [100.0 + (i % 2) * 0.5 for i in range(50)]
        # Wide range prices
        wide_prices = [100.0 + (i % 2) * 10.0 for i in range(50)]

        tight_bbw = bollinger_band_width(tight_prices, period=20)
        wide_bbw = bollinger_band_width(wide_prices, period=20)

        # Last BBW value for tight should be lower than wide
        assert tight_bbw[-1] < wide_bbw[-1]

    def test_bbw_zero_volatility(self):
        """Test BBW with constant prices (zero volatility)."""
        prices = [100.0] * 30
        bbw = bollinger_band_width(prices, period=20)

        # With zero volatility, BBW should be 0
        valid_bbw = bbw[~np.isnan(bbw)]
        np.testing.assert_array_almost_equal(valid_bbw, np.zeros(len(valid_bbw)), decimal=10)

    def test_bbw_matches_bollinger_bands(self):
        """Test that BBW calculation matches manual calculation from bollinger_bands."""
        prices = [100.0 + i * 0.5 + (i % 3) * 2 for i in range(50)]
        bbw = bollinger_band_width(prices, period=20, std_dev=2.0)

        # Manual calculation
        upper, middle, lower = bollinger_bands(prices, period=20, std_dev=2.0)
        expected_bbw = np.where(middle != 0, (upper - lower) / middle, np.nan)

        np.testing.assert_array_almost_equal(bbw, expected_bbw, decimal=10)

    def test_bbw_numpy_array_input(self):
        """Test BBW with numpy array input."""
        prices = np.array([100.0 + i for i in range(30)])
        bbw = bollinger_band_width(prices, period=20)

        assert isinstance(bbw, np.ndarray)
        assert len(bbw) == len(prices)


class TestPercentileRank:
    """Test cases for Percentile Rank."""

    def test_percentile_basic(self):
        """Test percentile calculation."""
        # Create ascending values
        values = list(range(100))
        percentiles = percentile_rank(values, lookback=90)

        # First 89 values should be NaN
        assert np.all(np.isnan(percentiles[:89]))
        # Last value (99) should be near 100th percentile
        assert percentiles[-1] > 95

    def test_percentile_lowest_value(self):
        """Test that the lowest value gets near 0 percentile."""
        values = list(range(100, 0, -1))  # Descending
        percentiles = percentile_rank(values, lookback=90)

        # Last value (1) should be near 0th percentile
        assert percentiles[-1] < 5

    def test_percentile_middle_value(self):
        """Test that middle value gets near 50th percentile."""
        # Create values where last value is in the middle
        values = [float(i) for i in range(50)] + [25.0]  # Last value is middle
        percentiles = percentile_rank(values, lookback=50)

        # Last value should be near 50th percentile
        assert 40 < percentiles[-1] < 60

    def test_percentile_with_duplicates(self):
        """Test percentile calculation with duplicate values."""
        values = [100.0] * 100
        percentiles = percentile_rank(values, lookback=90)

        # All values are equal, so percentile should be 0 (none are below current)
        valid_percentiles = percentiles[~np.isnan(percentiles)]
        np.testing.assert_array_almost_equal(valid_percentiles, np.zeros(len(valid_percentiles)))

    def test_percentile_with_nans(self):
        """Test percentile calculation handles NaN values."""
        values = [float(i) for i in range(100)]
        values[50] = np.nan  # Insert NaN
        percentiles = percentile_rank(values, lookback=90)

        # Should handle NaN gracefully
        # At position 89, window has 1 NaN, but should still calculate
        assert not np.isnan(percentiles[89])

    def test_percentile_insufficient_valid_data(self):
        """Test percentile with insufficient valid data."""
        # Window with too many NaN values
        values = [np.nan] * 40 + [float(i) for i in range(60)]
        percentiles = percentile_rank(values, lookback=90)

        # Early positions should be NaN (window has too many NaN values)
        # Position 89 has window from 0-89, which is 40 NaN + 50 valid = 50 valid (>= 45 threshold)
        assert not np.isnan(percentiles[89])

    def test_percentile_different_lookback(self):
        """Test percentile with different lookback periods."""
        values = [float(i) for i in range(200)]

        for lookback in [30, 60, 90]:
            percentiles = percentile_rank(values, lookback=lookback)

            # First (lookback-1) values should be NaN
            assert np.all(np.isnan(percentiles[:lookback-1]))
            # Last value should be high percentile (ascending data)
            assert percentiles[-1] > 95

    def test_percentile_numpy_array_input(self):
        """Test percentile with numpy array input."""
        values = np.arange(100, dtype=float)
        percentiles = percentile_rank(values, lookback=90)

        assert isinstance(percentiles, np.ndarray)
        assert len(percentiles) == len(values)

    def test_percentile_single_value_in_window(self):
        """Test percentile with minimum lookback."""
        values = [float(i) for i in range(20)]
        percentiles = percentile_rank(values, lookback=2)

        # First value is NaN (insufficient data)
        assert np.isnan(percentiles[0])
        # Second value onward should have valid percentiles
        assert not np.isnan(percentiles[1])
