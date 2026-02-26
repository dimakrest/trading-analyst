"""Tests for technical indicators endpoint."""

import pytest
from datetime import UTC, datetime, timedelta

from httpx import AsyncClient


@pytest.mark.asyncio
async def test_get_stock_indicators_basic(async_client: AsyncClient):
    """Test that indicators endpoint returns MA-20 and CCI data."""
    # Arrange
    symbol = "AAPL"
    end_date = datetime.now(UTC)
    start_date = end_date - timedelta(days=90)  # 90 days for reliable indicators

    # Act
    response = await async_client.get(
        f"/api/v1/stocks/{symbol}/indicators",
        params={
            "start_date": start_date.strftime("%Y-%m-%d"),
            "end_date": end_date.strftime("%Y-%m-%d"),
        },
    )

    # Assert
    assert response.status_code == 200
    data = response.json()
    assert data["symbol"] == symbol
    assert "data" in data
    assert len(data["data"]) > 0
    assert data["indicators"] == ["MA-20", "CCI"]
    assert data["interval"] == "1d"

    # Check structure of indicator data
    for point in data["data"]:
        assert "date" in point
        assert "ma_20" in point
        assert "cci" in point
        assert "cci_signal" in point


@pytest.mark.asyncio
async def test_get_stock_indicators_calculations(async_client: AsyncClient):
    """Test that indicators are calculated correctly after warmup period."""
    # Arrange
    symbol = "AAPL"
    end_date = datetime.now(UTC)
    start_date = end_date - timedelta(days=60)

    # Act
    response = await async_client.get(
        f"/api/v1/stocks/{symbol}/indicators",
        params={
            "start_date": start_date.strftime("%Y-%m-%d"),
            "end_date": end_date.strftime("%Y-%m-%d"),
        },
    )

    # Assert
    assert response.status_code == 200
    data = response.json()

    # First 19 records should have null MA-20 and CCI (warmup period)
    for i in range(min(19, len(data["data"]))):
        assert data["data"][i]["ma_20"] is None
        assert data["data"][i]["cci"] is None

    # Day 20 onwards should have calculated values
    if len(data["data"]) >= 20:
        for i in range(19, len(data["data"])):
            assert data["data"][i]["ma_20"] is not None
            assert isinstance(data["data"][i]["ma_20"], float)
            assert data["data"][i]["cci"] is not None
            assert isinstance(data["data"][i]["cci"], float)


@pytest.mark.asyncio
async def test_get_stock_indicators_period_parameter(async_client: AsyncClient):
    """Test indicators endpoint with period parameter."""
    # Arrange
    symbol = "AAPL"

    # Act
    response = await async_client.get(
        f"/api/v1/stocks/{symbol}/indicators",
        params={"period": "3mo"},
    )

    # Assert
    assert response.status_code == 200
    data = response.json()
    assert data["symbol"] == symbol
    assert len(data["data"]) > 0


@pytest.mark.asyncio
async def test_get_stock_indicators_invalid_symbol(async_client: AsyncClient):
    """Test indicators endpoint with invalid symbol."""
    # Arrange
    symbol = "INVALID_SYMBOL_THAT_DOES_NOT_EXIST_12345"

    # Act
    response = await async_client.get(
        f"/api/v1/stocks/{symbol}/indicators",
        params={"period": "1mo"},
    )

    # Assert - Invalid format returns 400
    assert response.status_code == 400
    assert "invalid" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_get_stock_indicators_cci_signals(async_client: AsyncClient):
    """Test that CCI signals are detected correctly."""
    # Arrange
    symbol = "AAPL"
    end_date = datetime.now(UTC)
    start_date = end_date - timedelta(days=90)

    # Act
    response = await async_client.get(
        f"/api/v1/stocks/{symbol}/indicators",
        params={
            "start_date": start_date.strftime("%Y-%m-%d"),
            "end_date": end_date.strftime("%Y-%m-%d"),
        },
    )

    # Assert
    assert response.status_code == 200
    data = response.json()

    # Check that cci_signal field exists and has valid values
    valid_signals = {None, "momentum_bullish", "momentum_bearish", "reversal_buy", "reversal_sell"}
    for point in data["data"]:
        assert point["cci_signal"] in valid_signals


@pytest.mark.asyncio
async def test_get_stock_indicators_intraday_interval(async_client: AsyncClient):
    """Test indicators endpoint with intraday interval."""
    # Arrange
    symbol = "AAPL"

    # Act
    response = await async_client.get(
        f"/api/v1/stocks/{symbol}/indicators",
        params={"period": "5d", "interval": "15m"},
    )

    # Assert
    assert response.status_code == 200
    data = response.json()
    assert data["symbol"] == symbol
    assert data["interval"] == "15m"
    assert len(data["data"]) > 0

    # For intraday intervals, dates should include timestamps
    if len(data["data"]) > 0:
        first_date = data["data"][0]["date"]
        assert "T" in first_date, "Intraday data should include timestamp"
