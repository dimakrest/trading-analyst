"""Unit tests for DataService smart cache freshness integration.

Tests the DataService's ability to use smart freshness checking to minimize
unnecessary API calls while ensuring users always see the latest available data.
"""
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.stock import StockPrice
from app.providers.base import PriceDataPoint, PriceDataRequest
from app.services.cache_service import FreshnessResult, MarketDataCache
from app.services.data_service import DataService


# Fixtures


@pytest.fixture
def mock_provider():
    """Create a mock market data provider."""
    provider = MagicMock()
    provider.provider_name = "MockProvider"

    # Mock fetch_price_data as async
    async def mock_fetch(request: PriceDataRequest):
        # Generate some mock price points
        points = []
        current = request.start_date
        while current <= request.end_date:
            points.append(
                PriceDataPoint(
                    symbol=request.symbol,
                    timestamp=current,
                    open_price=100.0,
                    high_price=105.0,
                    low_price=95.0,
                    close_price=102.0,
                    volume=1000000,
                )
            )
            current += timedelta(days=1)
        return points

    provider.fetch_price_data = AsyncMock(side_effect=mock_fetch)
    return provider


@pytest.fixture
def mock_repository():
    """Create a mock stock price repository."""
    repo = MagicMock()

    # Mock sync_price_data as async
    async def mock_sync(symbol, new_data, interval):
        return {
            "fetched": len(new_data),
            "stored": len(new_data),
            "updated": 0,
        }

    repo.sync_price_data = AsyncMock(side_effect=mock_sync)

    # Mock get_price_data_by_date_range as async
    # Default: return empty list (will be overridden in tests)
    repo.get_price_data_by_date_range = AsyncMock(return_value=[])

    return repo


@pytest.fixture
def mock_cache(mock_repository):
    """Create a mock market data cache."""
    cache = MagicMock(spec=MarketDataCache)
    cache.repository = mock_repository

    return cache


@pytest.fixture
def data_service(db_session: AsyncSession, mock_provider, mock_cache, mock_repository):
    """Create DataService instance for testing."""
    return DataService(
        session=db_session,
        provider=mock_provider,
        cache=mock_cache,
        repository=mock_repository,
    )


# Helper functions


def create_mock_stock_price(symbol: str, timestamp: datetime, index: int = 0) -> MagicMock:
    """Create a mock StockPrice database record."""
    mock_record = MagicMock(spec=StockPrice)
    mock_record.symbol = symbol
    mock_record.timestamp = timestamp
    mock_record.interval = "1d"
    mock_record.open_price = Decimal(str(100.0 + index))
    mock_record.high_price = Decimal(str(105.0 + index))
    mock_record.low_price = Decimal(str(95.0 + index))
    mock_record.close_price = Decimal(str(102.0 + index))
    mock_record.volume = 1000000 + (index * 1000)
    mock_record.last_fetched_at = datetime.now(timezone.utc)
    return mock_record


def create_freshness_result(
    is_fresh: bool,
    reason: str,
    market_status: str = "pre_market",
    last_data_date: date | None = None,
    last_complete_trading_day: date | None = None,
    fetch_start_date: date | None = None,
    cached_records: list[StockPrice] | None = None,
) -> FreshnessResult:
    """Create a FreshnessResult for testing."""
    if last_complete_trading_day is None:
        last_complete_trading_day = date.today() - timedelta(days=1)

    return FreshnessResult(
        is_fresh=is_fresh,
        reason=reason,
        market_status=market_status,
        recommended_ttl=86400 if is_fresh else 0,
        last_data_date=last_data_date,
        last_complete_trading_day=last_complete_trading_day,
        needs_fetch=not is_fresh,
        fetch_start_date=fetch_start_date,
        cached_records=cached_records,
    )


# Unit Tests - Smart Cache Hit


@pytest.mark.asyncio
async def test_smart_cache_hit_returns_without_fetching(
    data_service: DataService,
    mock_provider,
    mock_cache,
):
    """Test that smart cache hit returns cached data without fetching from provider."""
    # Arrange: Create mock cached records
    cached_records = [
        create_mock_stock_price(
            "AAPL",
            datetime(2024, 12, 1, tzinfo=timezone.utc),
            0
        )
    ]

    # Mock smart freshness check to indicate fresh data with cached_records
    freshness = create_freshness_result(
        is_fresh=True,
        reason="Data covers up to last complete trading day",
        market_status="pre_market",
        last_data_date=date(2024, 12, 2),
        last_complete_trading_day=date(2024, 12, 2),
        cached_records=cached_records,
    )
    mock_cache.check_freshness_smart = AsyncMock(return_value=freshness)

    # Act: Fetch data
    result = await data_service.get_price_data(
        symbol="AAPL",
        start_date=datetime(2024, 11, 1, tzinfo=timezone.utc),
        end_date=datetime(2024, 12, 2, tzinfo=timezone.utc),
        interval="1d",
    )

    # Assert: Should return cached data without calling provider
    assert len(result) > 0
    assert all(isinstance(r, PriceDataPoint) for r in result)
    assert result[0].symbol == "AAPL"

    # Verify provider was NOT called
    mock_provider.fetch_price_data.assert_not_called()


@pytest.mark.asyncio
async def test_smart_cache_hit_during_market_hours(
    data_service: DataService,
    mock_provider,
    mock_cache,
):
    """Test smart cache hit during market hours with 5-minute TTL."""
    # Arrange: Create mock cached records
    cached_records = [
        create_mock_stock_price(
            "AAPL",
            datetime.now(timezone.utc),
            0
        )
    ]

    # Mock freshness check for market_open status
    freshness = create_freshness_result(
        is_fresh=True,
        reason="Data fresh within 5-minute TTL",
        market_status="market_open",
        last_data_date=date.today(),
        last_complete_trading_day=date.today() - timedelta(days=1),
        cached_records=cached_records,
    )
    mock_cache.check_freshness_smart = AsyncMock(return_value=freshness)

    # Act
    result = await data_service.get_price_data(
        symbol="AAPL",
        start_date=datetime.now(timezone.utc) - timedelta(days=1),
        end_date=datetime.now(timezone.utc),
        interval="1d",
    )

    # Assert: Should return cached data
    assert len(result) > 0
    assert result[0].symbol == "AAPL"
    mock_provider.fetch_price_data.assert_not_called()


# Unit Tests - Incremental Fetch


@pytest.mark.asyncio
async def test_incremental_fetch_uses_correct_start_date(
    data_service: DataService,
    mock_provider,
    mock_cache,
    mock_repository,
):
    """Test that incremental fetch uses the correct start date from freshness check."""
    # Arrange: Mock freshness to indicate need for incremental fetch
    freshness = create_freshness_result(
        is_fresh=False,
        reason="Missing data from 2024-12-03 to 2024-12-04",
        market_status="pre_market",
        last_data_date=date(2024, 12, 2),
        last_complete_trading_day=date(2024, 12, 4),
        fetch_start_date=date(2024, 12, 2),  # Incremental from here
    )
    mock_cache.check_freshness_smart = AsyncMock(return_value=freshness)

    # Mock repository to return merged data after fetch
    merged_records = [
        create_mock_stock_price("AAPL", datetime(2024, 12, i, tzinfo=timezone.utc), i)
        for i in range(1, 5)
    ]
    mock_repository.get_price_data_by_date_range = AsyncMock(return_value=merged_records)

    # Act: Request data from Nov 1 to Dec 4
    result = await data_service.get_price_data(
        symbol="AAPL",
        start_date=datetime(2024, 11, 1, tzinfo=timezone.utc),
        end_date=datetime(2024, 12, 4, tzinfo=timezone.utc),
        interval="1d",
    )

    # Assert: Provider should be called with incremental start date (Dec 2)
    assert len(result) > 0
    mock_provider.fetch_price_data.assert_called_once()

    call_args = mock_provider.fetch_price_data.call_args[0][0]
    assert isinstance(call_args, PriceDataRequest)
    assert call_args.symbol == "AAPL"
    assert call_args.start_date.date() == date(2024, 12, 2)  # Incremental start
    assert call_args.end_date.date() == date(2024, 12, 4)


@pytest.mark.asyncio
async def test_full_fetch_when_no_cached_data(
    data_service: DataService,
    mock_provider,
    mock_cache,
    mock_repository,
):
    """Test full fetch when no cached data exists."""
    # Arrange: Mock freshness to indicate no cached data
    freshness = create_freshness_result(
        is_fresh=False,
        reason="No cached data",
        market_status="pre_market",
        last_data_date=None,
        last_complete_trading_day=date(2024, 12, 4),
        fetch_start_date=date(2024, 11, 1),  # Full range
    )
    mock_cache.check_freshness_smart = AsyncMock(return_value=freshness)

    # Mock repository to return data after fetch
    fetched_records = [
        create_mock_stock_price("AAPL", datetime(2024, 11, i, tzinfo=timezone.utc), i)
        for i in range(1, 5)
    ]
    mock_repository.get_price_data_by_date_range = AsyncMock(return_value=fetched_records)

    # Act
    result = await data_service.get_price_data(
        symbol="AAPL",
        start_date=datetime(2024, 11, 1, tzinfo=timezone.utc),
        end_date=datetime(2024, 12, 4, tzinfo=timezone.utc),
        interval="1d",
    )

    # Assert: Should fetch full range
    assert len(result) > 0
    mock_provider.fetch_price_data.assert_called_once()

    call_args = mock_provider.fetch_price_data.call_args[0][0]
    assert call_args.start_date.date() == date(2024, 11, 1)  # Full range from start
    assert call_args.end_date.date() == date(2024, 12, 4)


# Unit Tests - Force Refresh


@pytest.mark.asyncio
async def test_force_refresh_bypasses_smart_cache_check(
    data_service: DataService,
    mock_provider,
    mock_cache,
    mock_repository,
):
    """Test that force_refresh bypasses smart cache check entirely."""
    # Arrange: Mock repository to return data after fetch
    fetched_records = [
        create_mock_stock_price("AAPL", datetime(2024, 11, i, tzinfo=timezone.utc), i)
        for i in range(1, 5)
    ]
    mock_repository.get_price_data_by_date_range = AsyncMock(return_value=fetched_records)

    # Act: Use force_refresh=True
    result = await data_service.get_price_data(
        symbol="AAPL",
        start_date=datetime(2024, 11, 1, tzinfo=timezone.utc),
        end_date=datetime(2024, 12, 4, tzinfo=timezone.utc),
        interval="1d",
        force_refresh=True,
    )

    # Assert: Should fetch from provider without checking freshness
    assert len(result) > 0
    mock_provider.fetch_price_data.assert_called_once()

    # Verify freshness check was NOT called
    mock_cache.check_freshness_smart.assert_not_called()


# Unit Tests - Race Condition Protection


@pytest.mark.asyncio
async def test_double_check_after_lock_uses_smart_freshness(
    data_service: DataService,
    mock_provider,
    mock_cache,
):
    """Test that double-check after acquiring lock also uses smart freshness."""
    # Arrange: First check returns stale, second check (after lock) returns fresh with data
    freshness_stale = create_freshness_result(
        is_fresh=False,
        reason="Missing recent data",
        market_status="pre_market",
        last_data_date=date(2024, 12, 1),
        fetch_start_date=date(2024, 12, 1),
    )

    # Create cached records for fresh result
    cached_records = [
        create_mock_stock_price(
            "AAPL",
            datetime(2024, 12, 2, tzinfo=timezone.utc),
            0
        )
    ]

    freshness_fresh = create_freshness_result(
        is_fresh=True,
        reason="Data covers up to last complete trading day",
        market_status="pre_market",
        last_data_date=date(2024, 12, 2),
        cached_records=cached_records,
    )

    # Mock check_freshness_smart to return stale first, then fresh
    mock_cache.check_freshness_smart = AsyncMock(
        side_effect=[freshness_stale, freshness_fresh]
    )

    # Act
    result = await data_service.get_price_data(
        symbol="AAPL",
        start_date=datetime(2024, 11, 1, tzinfo=timezone.utc),
        end_date=datetime(2024, 12, 2, tzinfo=timezone.utc),
        interval="1d",
    )

    # Assert: Should return cached data (another request populated cache)
    assert len(result) > 0
    assert result[0].symbol == "AAPL"

    # Verify freshness was checked twice (before and after lock)
    assert mock_cache.check_freshness_smart.call_count == 2

    # Verify provider was NOT called (cache populated by another request)
    mock_provider.fetch_price_data.assert_not_called()


# Unit Tests - Edge Cases


@pytest.mark.asyncio
async def test_incremental_fetch_start_date_not_before_requested_start(
    data_service: DataService,
    mock_provider,
    mock_cache,
    mock_repository,
):
    """Test that incremental fetch only applies if fetch_start_date > requested start_date."""
    # Arrange: fetch_start_date is BEFORE requested start_date (shouldn't use it)
    freshness = create_freshness_result(
        is_fresh=False,
        reason="Need to fetch",
        market_status="pre_market",
        last_data_date=date(2024, 10, 15),
        fetch_start_date=date(2024, 10, 15),  # Before requested start (Nov 1)
    )
    mock_cache.check_freshness_smart = AsyncMock(return_value=freshness)

    # Mock repository to return data after fetch
    fetched_records = [
        create_mock_stock_price("AAPL", datetime(2024, 11, i, tzinfo=timezone.utc), i)
        for i in range(1, 5)
    ]
    mock_repository.get_price_data_by_date_range = AsyncMock(return_value=fetched_records)

    # Act: Request from Nov 1
    result = await data_service.get_price_data(
        symbol="AAPL",
        start_date=datetime(2024, 11, 1, tzinfo=timezone.utc),
        end_date=datetime(2024, 12, 4, tzinfo=timezone.utc),
        interval="1d",
    )

    # Assert: Should use requested start_date, not fetch_start_date
    call_args = mock_provider.fetch_price_data.call_args[0][0]
    assert call_args.start_date.date() == date(2024, 11, 1)  # Original start


@pytest.mark.asyncio
async def test_smart_cache_with_after_hours_status(
    data_service: DataService,
    mock_provider,
    mock_cache,
):
    """Test smart cache behavior during after-hours."""
    # Arrange: Create mock cached records
    cached_records = [
        create_mock_stock_price(
            "AAPL",
            datetime.now(timezone.utc),
            0
        )
    ]

    # After-hours with complete data for today
    freshness = create_freshness_result(
        is_fresh=True,
        reason="Data covers up to last complete trading day (including today)",
        market_status="after_hours",
        last_data_date=date.today(),
        last_complete_trading_day=date.today(),
        cached_records=cached_records,
    )
    mock_cache.check_freshness_smart = AsyncMock(return_value=freshness)

    # Act
    result = await data_service.get_price_data(
        symbol="AAPL",
        start_date=datetime.now(timezone.utc) - timedelta(days=30),
        end_date=datetime.now(timezone.utc),
        interval="1d",
    )

    # Assert: Should use cache (data is complete for today after close)
    assert len(result) > 0
    assert result[0].symbol == "AAPL"
    mock_provider.fetch_price_data.assert_not_called()


@pytest.mark.asyncio
async def test_weekend_status_with_friday_data(
    data_service: DataService,
    mock_provider,
    mock_cache,
):
    """Test smart cache on weekend when Friday's data is complete."""
    # Arrange: Weekend (Saturday) with Friday's data
    friday = date(2024, 12, 6)  # Assuming this is a Friday
    saturday = date(2024, 12, 7)

    # Create mock cached records
    cached_records = [
        create_mock_stock_price(
            "AAPL",
            datetime.combine(friday, datetime.min.time(), tzinfo=timezone.utc),
            0
        )
    ]

    freshness = create_freshness_result(
        is_fresh=True,
        reason=f"Data covers up to last complete trading day ({friday})",
        market_status="closed",
        last_data_date=friday,
        last_complete_trading_day=friday,
        cached_records=cached_records,
    )
    mock_cache.check_freshness_smart = AsyncMock(return_value=freshness)

    # Act: Request on Saturday
    result = await data_service.get_price_data(
        symbol="AAPL",
        start_date=datetime.combine(
            saturday - timedelta(days=30),
            datetime.min.time(),
            tzinfo=timezone.utc
        ),
        end_date=datetime.combine(saturday, datetime.min.time(), tzinfo=timezone.utc),
        interval="1d",
    )

    # Assert: Should use cache (Friday is last complete trading day)
    assert len(result) > 0
    assert result[0].symbol == "AAPL"
    mock_provider.fetch_price_data.assert_not_called()
