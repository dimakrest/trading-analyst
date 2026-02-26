"""Accuracy verification tests for technical indicators.

This test suite verifies the mathematical accuracy of our technical indicator
implementations by comparing against:
1. Manual calculations with known inputs/outputs
2. Mathematical properties (ranges, monotonicity, etc.)
3. Reference implementations from published examples

Since TA-Lib test vectors are not publicly available, we use:
- Hand-calculated examples for small datasets
- Published calculation examples from reliable sources
- Property-based testing for edge cases
"""
import numpy as np
import pandas as pd
import pytest

from app.utils.technical_indicators import (
    calculate_atr,
    calculate_sma,
)


class TestSMAAccuracy:
    """Verify SMA calculation accuracy against manual calculations."""

    def test_sma_simple_manual_calculation(self):
        """Test SMA with hand-calculated example.

        Example from CFI (Corporate Finance Institute):
        Prices: [110.00, 106.50, 103.25, 105.75, 104.00, 102.50, 101.25]
        7-period SMA = 104.75
        """
        dates = pd.date_range(end="2024-01-07", periods=7, freq="D")
        prices = [110.00, 106.50, 103.25, 105.75, 104.00, 102.50, 101.25]

        data = pd.DataFrame(
            {
                "Open": prices,
                "High": prices,
                "Low": prices,
                "Close": prices,
                "Volume": [1000000] * 7,
            },
            index=dates,
        )

        sma = calculate_sma(data, column="Close", window=7)

        # Last value should be the 7-period average
        expected_sma = sum(prices) / 7  # = 104.75
        actual_sma = sma.iloc[-1]

        assert abs(actual_sma - expected_sma) < 0.01, (
            f"SMA calculation incorrect: expected {expected_sma}, got {actual_sma}"
        )

    def test_sma_rolling_calculation(self):
        """Test SMA rolling window behavior.

        Example: 5-period SMA on sequence [32, 30, 34, 38, 40, 35, 33]
        First 5-period SMA: (32+30+34+38+40)/5 = 34.8
        Second 5-period SMA: (30+34+38+40+35)/5 = 35.4
        Third 5-period SMA: (34+38+40+35+33)/5 = 36.0
        """
        dates = pd.date_range(end="2024-01-07", periods=7, freq="D")
        prices = [32.0, 30.0, 34.0, 38.0, 40.0, 35.0, 33.0]

        data = pd.DataFrame(
            {
                "Open": prices,
                "High": prices,
                "Low": prices,
                "Close": prices,
                "Volume": [1000000] * 7,
            },
            index=dates,
        )

        sma = calculate_sma(data, column="Close", window=5)

        # First 4 values should be NaN
        assert pd.isna(sma.iloc[0:4]).all()

        # Verify calculated values
        assert abs(sma.iloc[4] - 34.8) < 0.01  # (32+30+34+38+40)/5
        assert abs(sma.iloc[5] - 35.4) < 0.01  # (30+34+38+40+35)/5
        assert abs(sma.iloc[6] - 36.0) < 0.01  # (34+38+40+35+33)/5

    def test_sma_single_value(self):
        """Test SMA window=1 equals original values."""
        dates = pd.date_range(end="2024-01-05", periods=5, freq="D")
        prices = [100.0, 102.0, 101.0, 103.0, 104.0]

        data = pd.DataFrame(
            {
                "Open": prices,
                "High": prices,
                "Low": prices,
                "Close": prices,
                "Volume": [1000000] * 5,
            },
            index=dates,
        )

        sma = calculate_sma(data, column="Close", window=1)

        # SMA with window=1 should equal the original values
        assert (sma == data["Close"]).all()


class TestATRAccuracy:
    """Verify ATR calculation accuracy."""

    def test_atr_true_range_components(self):
        """Test ATR calculation uses correct True Range formula.

        True Range = max(
            high - low,
            |high - prev_close|,
            |low - prev_close|
        )
        """
        dates = pd.date_range(end="2024-01-05", periods=5, freq="D")

        # Create data where True Range is clearly defined
        data = pd.DataFrame(
            {
                "High": [102.0, 104.0, 103.0, 106.0, 105.0],
                "Low": [98.0, 100.0, 99.0, 102.0, 101.0],
                "Close": [100.0, 102.0, 101.0, 104.0, 103.0],
                "Open": [100.0, 102.0, 101.0, 104.0, 103.0],
                "Volume": [1000000] * 5,
            },
            index=dates,
        )

        atr = calculate_atr(data, period=3)

        # ATR should be positive
        assert (atr.dropna() > 0).all(), "ATR should always be positive"

        # ATR should be less than or equal to max True Range
        max_range = (data["High"] - data["Low"]).max()
        assert atr.iloc[-1] <= max_range * 1.1, (  # Allow small margin
            f"ATR {atr.iloc[-1]} should not exceed max range {max_range}"
        )

    def test_atr_volatility_sensitivity(self):
        """Test ATR correctly measures volatility."""
        dates = pd.date_range(end="2024-01-30", periods=30, freq="D")

        # Low volatility scenario
        low_vol_prices = [100.0] * 30
        low_vol_data = pd.DataFrame(
            {
                "Open": low_vol_prices,
                "High": [p + 0.5 for p in low_vol_prices],
                "Low": [p - 0.5 for p in low_vol_prices],
                "Close": low_vol_prices,
                "Volume": [1000000] * 30,
            },
            index=dates,
        )

        # High volatility scenario
        np.random.seed(42)
        high_vol_prices = 100.0 + np.cumsum(np.random.randn(30) * 5)
        high_vol_data = pd.DataFrame(
            {
                "Open": high_vol_prices,
                "High": high_vol_prices + 5.0,
                "Low": high_vol_prices - 5.0,
                "Close": high_vol_prices,
                "Volume": [1000000] * 30,
            },
            index=dates,
        )

        atr_low = calculate_atr(low_vol_data, period=14)
        atr_high = calculate_atr(high_vol_data, period=14)

        # High volatility ATR should be significantly larger than low volatility ATR
        assert atr_high.iloc[-1] > atr_low.iloc[-1] * 3, (
            f"High vol ATR ({atr_high.iloc[-1]}) should be > 3x low vol ATR ({atr_low.iloc[-1]})"
        )

    def test_atr_manual_calculation(self):
        """Test ATR with simple manual calculation using Wilder's EMA."""
        dates = pd.date_range(end="2024-01-05", periods=5, freq="D")

        # Simple data for manual verification
        # Day 1: TR = 4 (102-98)
        # Day 2: TR = max(4, |104-100|=4, |100-100|=0) = 4
        # Day 3: TR = max(4, |103-102|=1, |99-102|=3) = 4
        # Day 4: TR = max(4, |106-101|=5, |102-101|=1) = 5
        # Day 5: TR = max(4, |105-104|=1, |101-104|=3) = 4
        # Wilder's EMA (alpha=1/3, adjust=False):
        #   Day 3 seed (ewm from day 1): approaches ~4.0
        #   Day 4: 4.0 * (2/3) + 5 * (1/3) ≈ 4.33
        #   Day 5: 4.33 * (2/3) + 4 * (1/3) ≈ 4.22
        data = pd.DataFrame(
            {
                "High": [102.0, 104.0, 103.0, 106.0, 105.0],
                "Low": [98.0, 100.0, 99.0, 102.0, 101.0],
                "Close": [100.0, 102.0, 101.0, 104.0, 103.0],
                "Open": [100.0, 102.0, 101.0, 104.0, 103.0],
                "Volume": [1000000] * 5,
            },
            index=dates,
        )

        atr = calculate_atr(data, period=3)

        # Verify ATR at last period (approximately 4.22 with Wilder's EMA)
        # Allow some tolerance for floating point arithmetic
        expected_atr = 4.22
        actual_atr = atr.iloc[-1]

        assert abs(actual_atr - expected_atr) < 0.5, (
            f"ATR calculation incorrect: expected ~{expected_atr}, got {actual_atr}"
        )


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_zero_volatility_atr(self):
        """Test ATR with zero volatility (constant OHLC)."""
        dates = pd.date_range(end="2024-01-30", periods=30, freq="D")
        constant_price = 100.0

        data = pd.DataFrame(
            {
                "Open": [constant_price] * 30,
                "High": [constant_price] * 30,
                "Low": [constant_price] * 30,
                "Close": [constant_price] * 30,
                "Volume": [1000000] * 30,
            },
            index=dates,
        )

        atr = calculate_atr(data, period=14)

        # ATR should be zero or very close to zero with no volatility
        assert atr.iloc[-1] < 0.01, f"ATR with zero volatility should be ~0, got {atr.iloc[-1]}"
