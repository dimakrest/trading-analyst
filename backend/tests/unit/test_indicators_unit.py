"""Comprehensive unit tests for technical indicators.

This module provides complete unit test coverage for all technical indicators
with property-based testing to validate mathematical properties and edge cases.
"""
import warnings

import numpy as np
import pytest
from hypothesis import assume
from hypothesis import given
from hypothesis import HealthCheck
from hypothesis import settings
from hypothesis import strategies as st

from app.indicators.technical import bollinger_bands
from app.indicators.technical import exponential_moving_average
from app.indicators.technical import relative_strength_index
from app.indicators.technical import simple_moving_average
from app.indicators.technical import typical_price


class TestSimpleMovingAverage:
    """Unit tests for Simple Moving Average (SMA)"""

    def test_sma_basic_calculation(self):
        """Test basic SMA calculation with known values"""
        prices = [1, 2, 3, 4, 5]
        period = 3

        sma = simple_moving_average(prices, period)

        expected = np.array([np.nan, np.nan, 2.0, 3.0, 4.0])
        np.testing.assert_array_equal(sma[:2], expected[:2])  # NaN values
        np.testing.assert_array_almost_equal(sma[2:], expected[2:])

    def test_sma_period_validation(self):
        """Test SMA period validation"""
        prices = [1, 2, 3, 4, 5]

        # Period must be > 0
        with pytest.raises(ValueError, match="Period must be greater than 0"):
            simple_moving_average(prices, 0)

        with pytest.raises(ValueError, match="Period must be greater than 0"):
            simple_moving_average(prices, -1)

    def test_sma_empty_prices(self):
        """Test SMA with empty prices array"""
        with pytest.raises(ValueError, match="Prices array cannot be empty"):
            simple_moving_average([], 5)

    def test_sma_insufficient_data(self):
        """Test SMA with insufficient data points"""
        prices = [1, 2]
        period = 5

        sma = simple_moving_average(prices, period)

        # Should return all NaN values
        assert len(sma) == 2
        assert np.all(np.isnan(sma))

    def test_sma_single_period(self):
        """Test SMA with period of 1"""
        prices = [10, 20, 30, 40, 50]
        period = 1

        sma = simple_moving_average(prices, period)

        # With period 1, SMA should equal original prices
        np.testing.assert_array_equal(sma, prices)

    def test_sma_numpy_input(self):
        """Test SMA with numpy array input"""
        prices = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        period = 3

        sma = simple_moving_average(prices, period)

        expected = np.array([np.nan, np.nan, 2.0, 3.0, 4.0])
        np.testing.assert_array_almost_equal(sma[2:], expected[2:])

    def test_sma_large_period(self):
        """Test SMA with period equal to data length"""
        prices = [1, 2, 3, 4, 5]
        period = 5

        sma = simple_moving_average(prices, period)

        # Only last value should be valid
        assert np.isnan(sma[0])
        assert np.isnan(sma[3])
        assert sma[4] == 3.0  # (1+2+3+4+5)/5

    def test_sma_constant_prices(self):
        """Test SMA with constant prices"""
        prices = [10.0] * 10
        period = 5

        sma = simple_moving_average(prices, period)

        # All valid SMA values should equal the constant price
        valid_sma = sma[~np.isnan(sma)]
        np.testing.assert_array_equal(valid_sma, [10.0] * len(valid_sma))

    @given(
        prices=st.lists(st.floats(min_value=1.0, max_value=1000.0), min_size=20, max_size=1000),
        period=st.integers(min_value=1, max_value=50),
    )
    @settings(max_examples=20, deadline=5000)
    def test_sma_properties(self, prices, period):
        """Property-based test for SMA mathematical properties"""
        assume(len(prices) >= period)

        sma = simple_moving_average(prices, period)

        # SMA should be same length as input
        assert len(sma) == len(prices)

        # First (period-1) values should be NaN
        assert np.all(np.isnan(sma[: period - 1]))

        # Valid SMA values should be within reasonable range of prices
        valid_sma = sma[~np.isnan(sma)]
        if len(valid_sma) > 0:
            min_price = min(prices)
            max_price = max(prices)
            assert np.all(valid_sma >= min_price * 0.99)  # Allow tiny floating point errors
            assert np.all(valid_sma <= max_price * 1.01)

    @given(
        base_price=st.floats(min_value=10.0, max_value=100.0),
        trend=st.floats(min_value=-0.1, max_value=0.1),
        length=st.integers(min_value=10, max_value=100),
        period=st.integers(min_value=2, max_value=10),
    )
    def test_sma_trend_following(self, base_price, trend, length, period):
        """Test that SMA follows price trends"""
        # Generate trending prices
        prices = [base_price + i * trend for i in range(length)]

        sma = simple_moving_average(prices, period)

        # In a strong trend, SMA should move in same direction
        valid_sma = sma[~np.isnan(sma)]
        if len(valid_sma) > 2:
            if trend > 0.01:  # Strong uptrend
                assert valid_sma[-1] > valid_sma[0]
            elif trend < -0.01:  # Strong downtrend
                assert valid_sma[-1] < valid_sma[0]


class TestExponentialMovingAverage:
    """Unit tests for Exponential Moving Average (EMA)"""

    def test_ema_basic_calculation(self):
        """Test basic EMA calculation"""
        prices = [10, 20, 30, 40, 50]
        period = 3

        ema = exponential_moving_average(prices, period)

        # First value should equal first price
        assert ema[0] == 10
        # EMA should be monotonically increasing for increasing prices
        assert ema[1] > ema[0]
        assert ema[2] > ema[1]

    def test_ema_period_validation(self):
        """Test EMA period validation"""
        prices = [1, 2, 3, 4, 5]

        with pytest.raises(ValueError, match="Period must be greater than 0"):
            exponential_moving_average(prices, 0)

        with pytest.raises(ValueError, match="Period must be greater than 0"):
            exponential_moving_average(prices, -1)

    def test_ema_empty_prices(self):
        """Test EMA with empty prices array"""
        with pytest.raises(ValueError, match="Prices array cannot be empty"):
            exponential_moving_average([], 5)

    def test_ema_single_price(self):
        """Test EMA with single price"""
        prices = [100.0]
        period = 5

        ema = exponential_moving_average(prices, period)

        assert len(ema) == 1
        assert ema[0] == 100.0

    def test_ema_constant_prices(self):
        """Test EMA with constant prices"""
        constant_price = 25.0
        prices = [constant_price] * 10
        period = 5

        ema = exponential_moving_average(prices, period)

        # All EMA values should equal the constant price
        np.testing.assert_array_almost_equal(ema, [constant_price] * 10)

    def test_ema_responsiveness(self):
        """Test that EMA is more responsive than SMA"""
        # Price jump scenario
        prices = [10] * 10 + [20] * 10
        period = 5

        ema = exponential_moving_average(prices, period)
        sma = simple_moving_average(prices, period)

        # After price jump, EMA should react faster
        jump_index = 12  # A few periods after the jump
        ema_change = ema[jump_index] - ema[9]  # Change from before jump
        sma_change = sma[jump_index] - sma[9]

        assert ema_change > sma_change  # EMA should change more

    @given(
        prices=st.lists(st.floats(min_value=1.0, max_value=1000.0), min_size=5, max_size=100),
        period=st.integers(min_value=1, max_value=20),
    )
    @settings(max_examples=20, deadline=5000)
    def test_ema_properties(self, prices, period):
        """Property-based test for EMA mathematical properties"""
        ema = exponential_moving_average(prices, period)

        # EMA should be same length as input
        assert len(ema) == len(prices)

        # First value should equal first price
        assert ema[0] == prices[0]

        # No NaN values in EMA
        assert not np.any(np.isnan(ema))

        # EMA values should be within extended range of prices
        min_price = min(prices)
        max_price = max(prices)
        assert np.all(ema >= min_price * 0.9)
        assert np.all(ema <= max_price * 1.1)

    def test_ema_alpha_calculation(self):
        """Test EMA alpha (smoothing factor) calculation"""
        period = 10
        expected_alpha = 2.0 / (period + 1)

        prices = [10, 15]  # Simple two-point calculation
        ema = exponential_moving_average(prices, period)

        # Manually calculate expected second EMA value
        expected_ema_1 = expected_alpha * prices[1] + (1 - expected_alpha) * prices[0]

        np.testing.assert_almost_equal(ema[1], expected_ema_1)


class TestRelativeStrengthIndex:
    """Unit tests for Relative Strength Index (RSI)"""

    def test_rsi_basic_calculation(self):
        """Test basic RSI calculation with known scenario"""
        # Prices with clear upward momentum
        prices = [44, 44.34, 44.09, 44.15, 43.61, 44.33, 44.83, 45.12, 45.43, 45.58]
        period = 6

        rsi = relative_strength_index(prices, period)

        # RSI should be between 0 and 100
        valid_rsi = rsi[~np.isnan(rsi)]
        assert np.all(valid_rsi >= 0)
        assert np.all(valid_rsi <= 100)

        # For upward trend, RSI should be > 50
        if len(valid_rsi) > 0:
            assert valid_rsi[-1] > 50  # Latest RSI should indicate bullish momentum

    def test_rsi_period_validation(self):
        """Test RSI period validation"""
        prices = [1, 2, 3, 4, 5]

        with pytest.raises(ValueError, match="Period must be greater than 0"):
            relative_strength_index(prices, 0)

        with pytest.raises(ValueError, match="Period must be greater than 0"):
            relative_strength_index(prices, -1)

    def test_rsi_empty_prices(self):
        """Test RSI with empty prices array"""
        with pytest.raises(ValueError, match="Prices array cannot be empty"):
            relative_strength_index([])

    def test_rsi_insufficient_data(self):
        """Test RSI with insufficient data"""
        prices = [100]  # Single price
        rsi = relative_strength_index(prices)

        assert len(rsi) == 1
        assert np.isnan(rsi[0])

    def test_rsi_all_gains(self):
        """Test RSI with all positive price changes"""
        prices = [10, 11, 12, 13, 14, 15, 16, 17, 18, 19]  # All increasing
        period = 5

        rsi = relative_strength_index(prices, period)

        # With all gains, RSI should approach 100
        valid_rsi = rsi[~np.isnan(rsi)]
        if len(valid_rsi) > 0:
            assert valid_rsi[-1] > 90  # Should be very high

    def test_rsi_all_losses(self):
        """Test RSI with all negative price changes"""
        prices = [20, 19, 18, 17, 16, 15, 14, 13, 12, 11]  # All decreasing
        period = 5

        rsi = relative_strength_index(prices, period)

        # With all losses, RSI should approach 0
        valid_rsi = rsi[~np.isnan(rsi)]
        if len(valid_rsi) > 0:
            assert valid_rsi[-1] < 10  # Should be very low

    def test_rsi_oscillating_prices(self):
        """Test RSI with oscillating prices"""
        prices = [50, 55, 50, 55, 50, 55, 50, 55, 50, 55]  # Alternating
        period = 4

        rsi = relative_strength_index(prices, period)

        # With equal gains and losses, RSI should be around 50
        valid_rsi = rsi[~np.isnan(rsi)]
        if len(valid_rsi) > 0:
            assert 40 <= valid_rsi[-1] <= 60  # Should be near neutral

    @given(
        prices=st.lists(st.floats(min_value=1.0, max_value=1000.0), min_size=20, max_size=100),
        period=st.integers(min_value=2, max_value=20),
    )
    @settings(max_examples=20, deadline=5000)
    def test_rsi_properties(self, prices, period):
        """Property-based test for RSI mathematical properties"""
        rsi = relative_strength_index(prices, period)

        # RSI should be same length as input
        assert len(rsi) == len(prices)

        # All valid RSI values should be between 0 and 100
        valid_rsi = rsi[~np.isnan(rsi)]
        assert np.all(valid_rsi >= 0)
        assert np.all(valid_rsi <= 100)

        # First value should always be NaN (no prior change available)
        assert np.isnan(rsi[0])


class TestBollingerBands:
    """Unit tests for Bollinger Bands"""

    def test_bollinger_bands_basic_calculation(self):
        """Test basic Bollinger Bands calculation"""
        prices = [20, 21, 22, 23, 24, 25, 26, 27, 28, 29]
        period = 5
        std_dev = 2.0

        upper, middle, lower = bollinger_bands(prices, period, std_dev)

        # All arrays should be same length
        assert len(upper) == len(middle) == len(lower) == len(prices)

        # Middle band should be SMA
        expected_middle = simple_moving_average(prices, period)
        np.testing.assert_array_almost_equal(middle, expected_middle)

        # Upper band should be above middle, lower band below (where valid)
        valid_indices = ~np.isnan(middle)
        if np.any(valid_indices):
            assert np.all(upper[valid_indices] >= middle[valid_indices])
            assert np.all(lower[valid_indices] <= middle[valid_indices])

    def test_bollinger_bands_parameter_validation(self):
        """Test parameter validation for Bollinger Bands"""
        prices = [20, 21, 22, 23, 24]

        # Period validation
        with pytest.raises(ValueError, match="Period must be greater than 0"):
            bollinger_bands(prices, 0)

        # Standard deviation validation
        with pytest.raises(
            ValueError, match="Standard deviation multiplier must be greater than 0"
        ):
            bollinger_bands(prices, 5, 0)

        # Empty prices validation
        with pytest.raises(ValueError, match="Prices array cannot be empty"):
            bollinger_bands([])

    def test_bollinger_bands_width(self):
        """Test Bollinger Bands width calculation"""
        # High volatility scenario
        volatile_prices = [10, 20, 5, 25, 8, 22, 12, 18, 15, 30]
        period = 5
        std_dev = 2.0

        upper_volatile, middle_volatile, lower_volatile = bollinger_bands(
            volatile_prices, period, std_dev
        )

        # Low volatility scenario
        stable_prices = [20, 20.1, 19.9, 20.05, 19.95, 20.02, 19.98, 20.01, 19.99, 20.0]

        upper_stable, middle_stable, lower_stable = bollinger_bands(stable_prices, period, std_dev)

        # Volatile prices should have wider bands
        valid_volatile = ~np.isnan(upper_volatile)
        valid_stable = ~np.isnan(upper_stable)

        if np.any(valid_volatile) and np.any(valid_stable):
            volatile_width = np.mean(
                upper_volatile[valid_volatile] - lower_volatile[valid_volatile]
            )
            stable_width = np.mean(upper_stable[valid_stable] - lower_stable[valid_stable])

            assert volatile_width > stable_width

    def test_bollinger_bands_squeeze(self):
        """Test Bollinger Bands squeeze (low volatility)"""
        # Very stable prices
        prices = [100.0] * 20  # Constant prices
        period = 10
        std_dev = 2.0

        upper, middle, lower = bollinger_bands(prices, period, std_dev)

        # With zero standard deviation, upper and lower should equal middle
        valid_indices = ~np.isnan(middle)
        if np.any(valid_indices):
            np.testing.assert_array_almost_equal(upper[valid_indices], middle[valid_indices])
            np.testing.assert_array_almost_equal(lower[valid_indices], middle[valid_indices])

    @given(
        prices=st.lists(st.floats(min_value=1.0, max_value=1000.0), min_size=10, max_size=100),
        period=st.integers(min_value=2, max_value=20),
        std_dev=st.floats(min_value=0.5, max_value=3.0),
    )
    @settings(max_examples=20, deadline=5000)
    def test_bollinger_bands_properties(self, prices, period, std_dev):
        """Property-based test for Bollinger Bands mathematical properties"""
        assume(len(prices) >= period)

        upper, middle, lower = bollinger_bands(prices, period, std_dev)

        # All arrays should be same length
        assert len(upper) == len(middle) == len(lower) == len(prices)

        # Where bands are valid, upper >= middle >= lower
        valid_indices = ~np.isnan(middle)
        if np.any(valid_indices):
            assert np.all(upper[valid_indices] >= middle[valid_indices])
            assert np.all(middle[valid_indices] >= lower[valid_indices])


class TestTypicalPrice:
    """Unit tests for Typical Price"""

    def test_typical_price_basic_calculation(self):
        """Test basic typical price calculation"""
        high = [102, 103, 104]
        low = [98, 99, 100]
        close = [100, 101, 102]

        tp = typical_price(high, low, close)

        # Manual calculation
        expected = np.array([(102 + 98 + 100) / 3, (103 + 99 + 101) / 3, (104 + 100 + 102) / 3])

        np.testing.assert_array_almost_equal(tp, expected)

    def test_typical_price_parameter_validation(self):
        """Test typical price parameter validation"""
        high = [102, 103, 104]
        low = [98, 99, 100]
        close = [100, 101]  # Different length

        # Mismatched lengths
        with pytest.raises(ValueError, match="High, low, and close arrays must have same length"):
            typical_price(high, low, close)

        # Empty arrays
        with pytest.raises(ValueError, match="Arrays cannot be empty"):
            typical_price([], [], [])

    def test_typical_price_numpy_input(self):
        """Test typical price with numpy array input"""
        high = np.array([102.0, 103.0, 104.0])
        low = np.array([98.0, 99.0, 100.0])
        close = np.array([100.0, 101.0, 102.0])

        tp = typical_price(high, low, close)

        assert isinstance(tp, np.ndarray)
        assert len(tp) == 3

    @given(
        high=st.lists(st.floats(min_value=100.0, max_value=200.0), min_size=1, max_size=100),
        close=st.lists(st.floats(min_value=90.0, max_value=190.0), min_size=1, max_size=100),
        low=st.lists(st.floats(min_value=80.0, max_value=180.0), min_size=1, max_size=100),
    )
    @settings(max_examples=20, deadline=5000, suppress_health_check=[HealthCheck.filter_too_much])
    def test_typical_price_properties(self, high, low, close):
        """Property-based test for typical price mathematical properties"""
        assume(len(high) == len(low) == len(close))

        # Ensure high >= close >= low for valid OHLC data
        valid_data = []
        for h, l, c in zip(high, low, close, strict=False):
            if l <= c <= h:  # Valid OHLC relationship
                valid_data.append((h, l, c))

        if not valid_data:
            return  # Skip if no valid data

        h_vals, l_vals, c_vals = zip(*valid_data, strict=False)

        tp = typical_price(list(h_vals), list(l_vals), list(c_vals))

        # Typical price should equal (high + low + close) / 3
        expected = (np.array(h_vals) + np.array(l_vals) + np.array(c_vals)) / 3
        np.testing.assert_array_almost_equal(tp, expected)

        # Typical price should be between low and high (with small tolerance for floating point)
        assert np.all(tp >= np.array(l_vals) - 1e-10)
        assert np.all(tp <= np.array(h_vals) + 1e-10)


class TestIndicatorEdgeCases:
    """Test edge cases across all indicators"""

    def test_nan_input_handling(self):
        """Test how indicators handle NaN inputs"""
        prices_with_nan = [10.0, np.nan, 12.0, 13.0, 14.0]

        # SMA should handle NaN gracefully
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            sma = simple_moving_average(prices_with_nan, 3)
            # Result may contain NaN, but shouldn't crash

        # EMA should handle NaN gracefully
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            ema = exponential_moving_average(prices_with_nan, 3)
            # Result may contain NaN, but shouldn't crash

    def test_infinite_input_handling(self):
        """Test how indicators handle infinite inputs"""
        prices_with_inf = [10.0, np.inf, 12.0, 13.0, 14.0]

        # Should handle infinite values gracefully
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            try:
                sma = simple_moving_average(prices_with_inf, 3)
                # May contain inf, but shouldn't crash
            except (ValueError, OverflowError):
                pass  # Acceptable to raise these errors

    def test_very_small_numbers(self):
        """Test indicators with very small numbers"""
        tiny_prices = [1e-10, 2e-10, 3e-10, 4e-10, 5e-10]

        sma = simple_moving_average(tiny_prices, 3)
        assert not np.any(np.isnan(sma[2:]))  # Should calculate properly

        ema = exponential_moving_average(tiny_prices, 3)
        assert not np.any(np.isnan(ema))  # Should calculate properly

    def test_very_large_numbers(self):
        """Test indicators with very large numbers"""
        large_prices = [1e10, 2e10, 3e10, 4e10, 5e10]

        sma = simple_moving_average(large_prices, 3)
        assert not np.any(np.isnan(sma[2:]))  # Should calculate properly

        ema = exponential_moving_average(large_prices, 3)
        assert not np.any(np.isnan(ema))  # Should calculate properly

    def test_single_value_arrays(self):
        """Test indicators with single value arrays"""
        single_price = [100.0]

        # SMA with single value
        sma = simple_moving_average(single_price, 1)
        assert sma[0] == 100.0

        # EMA with single value
        ema = exponential_moving_average(single_price, 1)
        assert ema[0] == 100.0

        # RSI with single value
        rsi = relative_strength_index(single_price)
        assert np.isnan(rsi[0])  # No change available

    def test_extreme_periods(self):
        """Test indicators with extreme period values"""
        prices = list(range(1, 101))  # 100 prices

        # Very large period (equal to data length)
        sma_large = simple_moving_average(prices, 100)
        assert not np.isnan(sma_large[-1])  # Last value should be valid

        # Period of 1
        sma_one = simple_moving_average(prices, 1)
        np.testing.assert_array_equal(sma_one, prices)  # Should equal input


class TestIndicatorPerformance:
    """Performance tests for indicators"""

    def test_large_dataset_performance(self):
        """Test indicator performance with large datasets"""
        import time

        # Generate large dataset
        large_prices = list(range(1, 10001))  # 10,000 prices

        start_time = time.time()
        sma = simple_moving_average(large_prices, 50)
        sma_time = time.time() - start_time

        start_time = time.time()
        ema = exponential_moving_average(large_prices, 50)
        ema_time = time.time() - start_time

        # Should complete within reasonable time
        assert sma_time < 1.0  # 1 second max
        assert ema_time < 1.0  # 1 second max

        # Results should be valid
        assert len(sma) == 10000
        assert len(ema) == 10000

    def test_memory_efficiency(self):
        """Test that indicators don't use excessive memory"""
        # This is a basic test - in production you might use memory profiling tools
        prices = list(range(1, 1001))  # 1,000 prices

        # Multiple indicator calculations shouldn't cause memory issues
        for _ in range(100):
            sma = simple_moving_average(prices, 20)
            ema = exponential_moving_average(prices, 20)
            rsi = relative_strength_index(prices, 14)

            # Verify results are as expected
            assert len(sma) == 1000
            assert len(ema) == 1000
            assert len(rsi) == 1000
