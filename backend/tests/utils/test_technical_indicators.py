"""Unit tests for technical_indicators utility module."""
import numpy as np
import pandas as pd
import pytest

from app.utils.technical_indicators import (
    calculate_atr,
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
        # First value will be NaN (needs shift)
        assert pd.isna(atr.iloc[0])
        # After warmup period should have values
        assert not pd.isna(atr.iloc[14:]).any()

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
