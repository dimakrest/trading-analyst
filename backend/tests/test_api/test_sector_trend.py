"""Tests for sector trend analysis endpoint."""

import pytest
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

from httpx import AsyncClient

from app.constants.sectors import SECTOR_TO_ETF
from app.models.stock import StockPrice
from app.services.data_service import SymbolNotFoundError, APIError


@pytest.mark.asyncio
async def test_get_sector_trend_basic(async_client: AsyncClient):
    """Test that sector trend endpoint returns trend analysis for valid sector ETF."""
    # Arrange
    symbol = "XLK"  # Technology sector ETF

    # Act
    response = await async_client.get(f"/api/v1/stocks/{symbol}/sector-trend")

    # Assert
    assert response.status_code == 200
    data = response.json()
    assert data["sector_etf"] == symbol
    assert data["trend_direction"] in ["up", "down", "sideways"]
    assert data["ma20_position"] in ["above", "below"]
    assert data["ma50_position"] in ["above", "below"]
    assert isinstance(data["ma20_distance_pct"], float)
    assert isinstance(data["ma50_distance_pct"], float)
    assert isinstance(data["price_change_5d_pct"], float)
    assert isinstance(data["price_change_20d_pct"], float)


@pytest.mark.asyncio
async def test_get_sector_trend_all_valid_etfs(async_client: AsyncClient):
    """Test that endpoint works for all valid sector ETFs."""
    # Arrange - get all valid sector ETFs
    valid_etfs = list(SECTOR_TO_ETF.values())[:3]  # Test first 3 to avoid long test time

    # Act & Assert
    for etf in valid_etfs:
        response = await async_client.get(f"/api/v1/stocks/{etf}/sector-trend")
        assert response.status_code == 200
        data = response.json()
        assert data["sector_etf"] == etf


@pytest.mark.asyncio
async def test_get_sector_trend_invalid_etf(async_client: AsyncClient):
    """Test that endpoint rejects non-sector ETF symbols."""
    # Arrange
    symbol = "AAPL"  # Not a sector ETF

    # Act
    response = await async_client.get(f"/api/v1/stocks/{symbol}/sector-trend")

    # Assert
    assert response.status_code == 400
    assert "not a valid sector ETF" in response.json()["detail"]


@pytest.mark.asyncio
async def test_get_sector_trend_invalid_symbol_format(async_client: AsyncClient):
    """Test that endpoint rejects invalid symbol formats."""
    # Arrange
    symbol = "INVALID@SYMBOL"

    # Act
    response = await async_client.get(f"/api/v1/stocks/{symbol}/sector-trend")

    # Assert
    assert response.status_code == 400
    assert "Invalid symbol format" in response.json()["detail"]


@pytest.mark.asyncio
async def test_get_sector_trend_calculations(async_client: AsyncClient):
    """Test that trend calculations are reasonable."""
    # Arrange
    symbol = "XLE"  # Energy sector ETF

    # Act
    response = await async_client.get(f"/api/v1/stocks/{symbol}/sector-trend")

    # Assert
    assert response.status_code == 200
    data = response.json()

    # Distance percentages should be reasonable (within -50% to +50%)
    assert -50.0 <= data["ma20_distance_pct"] <= 50.0
    assert -50.0 <= data["ma50_distance_pct"] <= 50.0

    # Price changes should be reasonable (within -30% to +30% for 5-20 days)
    assert -30.0 <= data["price_change_5d_pct"] <= 30.0
    assert -30.0 <= data["price_change_20d_pct"] <= 30.0


@pytest.mark.asyncio
async def test_get_sector_trend_position_consistency(async_client: AsyncClient):
    """Test that position and distance percentage are consistent."""
    # Arrange
    symbol = "XLF"  # Financial sector ETF

    # Act
    response = await async_client.get(f"/api/v1/stocks/{symbol}/sector-trend")

    # Assert
    assert response.status_code == 200
    data = response.json()

    # If position is "above", distance should be >= 0
    # If position is "below", distance should be <= 0
    if data["ma20_position"] == "above":
        assert data["ma20_distance_pct"] >= -0.5  # Allow small negative due to AT threshold
    else:
        assert data["ma20_distance_pct"] <= 0.5

    if data["ma50_position"] == "above":
        assert data["ma50_distance_pct"] >= -0.5
    else:
        assert data["ma50_distance_pct"] <= 0.5


@pytest.mark.asyncio
async def test_get_sector_trend_trend_direction_mapping(async_client: AsyncClient):
    """Test that trend direction is correctly mapped from indicator values."""
    # Arrange
    symbol = "XLV"  # Healthcare sector ETF

    # Act
    response = await async_client.get(f"/api/v1/stocks/{symbol}/sector-trend")

    # Assert
    assert response.status_code == 200
    data = response.json()

    # Trend direction should match price change direction (loosely)
    # If 20-day price change is positive and significant, trend should likely be "up"
    if data["price_change_20d_pct"] > 2.0:
        # Strong upward movement should likely be "up" or "sideways"
        assert data["trend_direction"] in ["up", "sideways"]
    elif data["price_change_20d_pct"] < -2.0:
        # Strong downward movement should likely be "down" or "sideways"
        assert data["trend_direction"] in ["down", "sideways"]
    # Note: This is a loose check since trend detection uses threshold


@pytest.mark.asyncio
async def test_get_sector_trend_case_insensitive(async_client: AsyncClient):
    """Test that endpoint handles symbol case insensitively."""
    # Arrange
    symbols = ["xlk", "XLK", "xLk"]

    # Act & Assert
    for symbol in symbols:
        response = await async_client.get(f"/api/v1/stocks/{symbol}/sector-trend")
        assert response.status_code == 200
        data = response.json()
        assert data["sector_etf"] == "XLK"  # Should normalize to uppercase


@pytest.mark.asyncio
async def test_get_sector_trend_caching(async_client: AsyncClient, db_session):
    """Test that sector ETF price data is cached in stock_prices table."""
    # Arrange
    symbol = "XLK"

    # Act - First call
    response1 = await async_client.get(f"/api/v1/stocks/{symbol}/sector-trend")
    assert response1.status_code == 200

    # Check cache was populated
    from sqlalchemy import select
    result = await db_session.execute(
        select(StockPrice).where(StockPrice.symbol == symbol).limit(1)
    )
    cached_record = result.scalar_one_or_none()
    assert cached_record is not None
    assert cached_record.symbol == symbol

    # Act - Second call (should use cache)
    response2 = await async_client.get(f"/api/v1/stocks/{symbol}/sector-trend")
    assert response2.status_code == 200

    # Both calls should return the same data (using cached prices)
    assert response1.json() == response2.json()


@pytest.mark.asyncio
async def test_get_sector_trend_insufficient_data(async_client: AsyncClient):
    """Test error handling when insufficient price data is available."""
    # This test would require mocking the data service to return insufficient data
    # For now, we'll test with a known scenario where data might be limited

    # Arrange - Use a symbol that might have limited data (unlikely in production)
    # We'll mock this to simulate the scenario
    symbol = "XLK"

    with patch("app.api.v1.stocks.DataService.get_price_data") as mock_get_price_data:
        # Mock insufficient data (less than 25 days)
        mock_records = []
        base_date = datetime.now(UTC)
        for i in range(10):  # Only 10 days of data
            mock_record = StockPrice(
                symbol=symbol,
                timestamp=base_date - timedelta(days=i),
                open_price=100.0,
                high_price=101.0,
                low_price=99.0,
                close_price=100.5,
                volume=1000000,
                interval="1d",
            )
            mock_records.append(mock_record)

        mock_get_price_data.return_value = mock_records

        # Act
        response = await async_client.get(f"/api/v1/stocks/{symbol}/sector-trend")

        # Assert
        assert response.status_code == 400
        assert "Insufficient price data" in response.json()["detail"]


@pytest.mark.asyncio
async def test_get_sector_trend_symbol_not_found(async_client: AsyncClient):
    """Test error handling when sector ETF symbol is not found."""
    # Arrange - Mock data service to raise SymbolNotFoundError
    symbol = "XLK"

    with patch("app.api.v1.stocks.DataService.get_price_data") as mock_get_price_data:
        mock_get_price_data.side_effect = SymbolNotFoundError(f"Symbol '{symbol}' not found")

        # Act
        response = await async_client.get(f"/api/v1/stocks/{symbol}/sector-trend")

        # Assert
        assert response.status_code == 404
        assert symbol in response.json()["detail"]


@pytest.mark.asyncio
async def test_get_sector_trend_api_error(async_client: AsyncClient):
    """Test error handling when data provider is unavailable."""
    # Arrange - Mock data service to raise APIError
    symbol = "XLK"

    with patch("app.api.v1.stocks.DataService.get_price_data") as mock_get_price_data:
        mock_get_price_data.side_effect = APIError("Yahoo Finance API unavailable")

        # Act
        response = await async_client.get(f"/api/v1/stocks/{symbol}/sector-trend")

        # Assert
        assert response.status_code == 503
        assert "unavailable" in response.json()["detail"]


@pytest.mark.asyncio
async def test_get_sector_trend_response_schema(async_client: AsyncClient):
    """Test that response matches expected schema with all required fields."""
    # Arrange
    symbol = "XLK"

    # Act
    response = await async_client.get(f"/api/v1/stocks/{symbol}/sector-trend")

    # Assert
    assert response.status_code == 200
    data = response.json()

    # Check all required fields are present
    required_fields = [
        "sector_etf",
        "trend_direction",
        "ma20_position",
        "ma20_distance_pct",
        "ma50_position",
        "ma50_distance_pct",
        "price_change_5d_pct",
        "price_change_20d_pct",
    ]
    for field in required_fields:
        assert field in data, f"Missing required field: {field}"

    # Check types
    assert isinstance(data["sector_etf"], str)
    assert isinstance(data["trend_direction"], str)
    assert isinstance(data["ma20_position"], str)
    assert isinstance(data["ma20_distance_pct"], (int, float))
    assert isinstance(data["ma50_position"], str)
    assert isinstance(data["ma50_distance_pct"], (int, float))
    assert isinstance(data["price_change_5d_pct"], (int, float))
    assert isinstance(data["price_change_20d_pct"], (int, float))

    # Check Literal type constraints
    assert data["trend_direction"] in ["up", "down", "sideways"]
    assert data["ma20_position"] in ["above", "below"]
    assert data["ma50_position"] in ["above", "below"]
