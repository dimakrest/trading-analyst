"""Unit tests for technical_indicators utility module."""
import numpy as np
import pandas as pd
import pytest

from app.utils.technical_indicators import (
    calculate_atr,
    calculate_atr_percentage,
    calculate_sma,
)


@pytest.fixture
def sample_price_data():
    """Create sample OHLCV data for testing."""
    # Create 250 days of data (enough for SMA 200 + buffer)
    dates = pd.date_range(end="2024-01-01", periods=250, freq="D")
    np.random.seed(42)

    # Generate realistic price data
    base_price = 100.0
    prices = base_price + np.cumsum(np.random.randn(250) * 2)
    # Ensure positive prices
    prices = np.maximum(prices, 50.0)

    data = pd.DataFrame(
        {
            "Open": prices * 0.99,
            "High": prices * 1.02,
            "Low": prices * 0.98,
            "Close": prices,
            "Volume": np.random.randint(1_000_000, 10_000_000, 250),
        },
        index=dates,
    )
    return data


@pytest.fixture
def multiindex_data(sample_price_data):
    """Create data with MultiIndex columns (simulating yfinance output)."""
    data = sample_price_data.copy()
    data.columns = pd.MultiIndex.from_product([data.columns, ["AAPL"]])
    return data


class TestCalculateSMA:
    """Tests for calculate_sma function."""

    def test_calculate_sma_50(self, sample_price_data):
        """Test SMA 50 calculation returns correct length."""
        sma = calculate_sma(sample_price_data, column="Close", window=50)

        assert len(sma) == len(sample_price_data)
        # First 49 values should be NaN
        assert pd.isna(sma.iloc[:49]).all()
        # From index 49 onwards should have values
        assert not pd.isna(sma.iloc[49:]).any()

    def test_calculate_sma_200(self, sample_price_data):
        """Test SMA 200 calculation returns correct length."""
        sma = calculate_sma(sample_price_data, column="Close", window=200)

        assert len(sma) == len(sample_price_data)
        # First 199 values should be NaN
        assert pd.isna(sma.iloc[:199]).all()
        # From index 199 onwards should have values
        assert not pd.isna(sma.iloc[199:]).any()

    def test_calculate_sma_custom_column(self, sample_price_data):
        """Test SMA calculation on different column."""
        sma = calculate_sma(sample_price_data, column="High", window=20)

        assert len(sma) == len(sample_price_data)
        assert not pd.isna(sma.iloc[19:]).any()

    def test_calculate_sma_values_reasonable(self, sample_price_data):
        """Test that SMA values are within reasonable range of actual prices."""
        sma = calculate_sma(sample_price_data, column="Close", window=50)
        latest_sma = sma.iloc[-1]
        latest_price = sample_price_data["Close"].iloc[-1]

        # SMA should be within 20% of current price (reasonable for 50-period window)
        assert 0.8 * latest_price <= latest_sma <= 1.2 * latest_price


class TestCalculateATR:
    """Tests for calculate_atr function."""

    def test_calculate_atr_14(self, sample_price_data):
        """Test ATR 14 calculation returns correct length."""
        atr = calculate_atr(sample_price_data, period=14)

        assert len(atr) == len(sample_price_data)
        # Wilder's EMA computes from first value — no NaN warmup period
        assert not pd.isna(atr.iloc[0])
        # All values should be non-NaN
        assert not pd.isna(atr).any()

    def test_calculate_atr_positive(self, sample_price_data):
        """Test that ATR values are always positive."""
        atr = calculate_atr(sample_price_data, period=14)

        valid_atr = atr.dropna()
        assert (valid_atr >= 0).all()

    def test_calculate_atr_reasonable_values(self, sample_price_data):
        """Test that ATR values are reasonable relative to price range."""
        atr = calculate_atr(sample_price_data, period=14)
        latest_atr = atr.iloc[-1]

        # Get typical price range
        typical_range = (
            sample_price_data["High"].iloc[-14:] - sample_price_data["Low"].iloc[-14:]
        ).mean()

        # ATR should be similar to average range (within reasonable bounds)
        assert 0.5 * typical_range <= latest_atr <= 2.0 * typical_range


class TestCalculateAtrPercentage:
    """Tests for calculate_atr_percentage standalone function."""

    def test_basic_calculation(self):
        """Test ATR percentage with known values."""
        closes = [100.0] * 20
        highs = [101.0] * 20
        lows = [99.0] * 20

        result = calculate_atr_percentage(highs, lows, closes)
        assert result is not None
        assert result == pytest.approx(2.0, rel=0.1)  # $2 ATR / $100 = 2%

    def test_insufficient_data_returns_none(self):
        """Test returns None with insufficient data."""
        closes = [100.0] * 10  # Less than period + 1 = 15
        highs = [101.0] * 10
        lows = [99.0] * 10

        result = calculate_atr_percentage(highs, lows, closes)
        assert result is None

    def test_different_price_ranges(self):
        """Test percentage is correct across price ranges."""
        # $5 stock with $0.25 range = 5%
        result = calculate_atr_percentage(
            highs=[5.125] * 20, lows=[4.875] * 20, closes=[5.0] * 20
        )
        assert result is not None
        assert result == pytest.approx(5.0, rel=0.1)

    def test_uses_latest_close_as_denominator(self):
        """Test that latest close is used, not any other price."""
        # Prices trend from 100 to 109.5
        closes = [100.0 + i * 0.5 for i in range(20)]
        highs = [c + 1.0 for c in closes]
        lows = [c - 1.0 for c in closes]

        result = calculate_atr_percentage(highs, lows, closes)
        assert result is not None
        # ATR ~$2 (range is consistently $2), latest close is 109.5
        # So ~2/109.5 * 100 ≈ 1.83%
        assert result == pytest.approx(2.0 / 109.5 * 100, rel=0.15)

    def test_zero_price_returns_none(self):
        """Test returns None for zero price."""
        result = calculate_atr_percentage(
            highs=[0.0] * 20, lows=[0.0] * 20, closes=[0.0] * 20
        )
        assert result is None

    def test_price_override_parameter(self):
        """Test that price_override changes the denominator."""
        closes = [100.0] * 20
        highs = [101.0] * 20
        lows = [99.0] * 20

        # Default: uses closes[-1] = 100.0
        result_default = calculate_atr_percentage(highs, lows, closes)
        assert result_default is not None
        assert result_default == pytest.approx(2.0, rel=0.1)  # $2 / $100 = 2%

        # Override: uses custom price = 102.0 (e.g., entry price)
        result_override = calculate_atr_percentage(
            highs, lows, closes, price_override=102.0
        )
        assert result_override is not None
        assert result_override == pytest.approx(1.96, rel=0.1)  # $2 / $102 ≈ 1.96%

        # Results should differ when override is used
        assert result_default != result_override
