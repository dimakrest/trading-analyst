"""Integration tests for the cache-first data service.

Tests verify the complete data flow:
- Database cache with TTL validation based on last_fetched_at
- Market-aware freshness checking
- Cache Flow: Request → Freshness Check → Provider (if stale) → Store → Return

Coverage includes:
- Cache misses triggering provider fetch
- Cache hits returning data from database
- TTL expiration forcing fresh fetch
- Force refresh bypassing cache
- Cache sharing across different request types
- Multi-symbol cache isolation
- Concurrent request deduplication
- Double-check after lock (race condition)
- Incremental fetch start date
- Market-hours 5-minute TTL
"""
import asyncio
import time
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.stock import StockPrice
from app.providers.mock import MockMarketDataProvider
from app.repositories.stock_price import StockPriceRepository
from app.services.cache_service import CacheTTLConfig, MarketDataCache
from app.services.data_service import DataService


@pytest_asyncio.fixture
async def mock_provider():
    """Create mock provider with predictable data and call tracking."""
    provider = MockMarketDataProvider()
    # Wrap the fetch_price_data method to track calls
    original_fetch = provider.fetch_price_data
    provider.fetch_price_data = AsyncMock(wraps=original_fetch)
    return provider


@pytest_asyncio.fixture
async def stock_repository(db_session: AsyncSession):
    """Create stock price repository."""
    return StockPriceRepository(db_session)


@pytest_asyncio.fixture
async def cache_service(stock_repository: StockPriceRepository):
    """Create cache service with default configuration."""
    return MarketDataCache(stock_repository, CacheTTLConfig())


@pytest_asyncio.fixture
async def data_service(
    test_session_factory,
    mock_provider: MockMarketDataProvider,
):
    """Create data service with session factory."""
    return DataService(
        session_factory=test_session_factory,
        provider=mock_provider,
    )


# ============================================================================
# Test 1: Cache miss fetches and stores
# ============================================================================
@pytest.mark.asyncio
@pytest.mark.integration
async def test_cache_miss_fetches_and_stores(
    data_service: DataService,
    stock_repository: StockPriceRepository,
    mock_provider: MockMarketDataProvider,
    db_session: AsyncSession,
):
    """Verify first request misses cache and fetches from provider.

    Flow:
    1. First request for symbol should miss cache
    2. Should fetch from provider
    3. Should store in database
    4. Verify last_fetched_at is set
    5. Second immediate request should hit cache (no provider call)
    """
    symbol = "AAPL"
    start_date = datetime.now(timezone.utc) - timedelta(days=30)
    end_date = datetime.now(timezone.utc)
    interval = "1d"

    # First request - should miss cache
    result = await data_service.get_price_data(
        symbol=symbol,
        start_date=start_date,
        end_date=end_date,
        interval=interval,
    )

    # Verify provider was called
    assert mock_provider.fetch_price_data.call_count == 1, "Should call provider on cache miss"

    # Verify data returned
    assert len(result) > 0, "Should return price data"
    assert all(r.symbol == symbol for r in result), "All records should match symbol"

    # Verify data stored in database
    price_records = await stock_repository.get_price_data_by_date_range(
        symbol=symbol,
        start_date=start_date,
        end_date=end_date,
        interval=interval,
    )

    assert len(price_records) > 0, "Should have records in database"

    # Verify last_fetched_at is set and recent
    for record in price_records:
        assert record.last_fetched_at is not None, "last_fetched_at should be set"
        age = datetime.now(timezone.utc) - record.last_fetched_at
        assert age.total_seconds() < 5, "last_fetched_at should be very recent"

    # Reset mock for second request
    mock_provider.fetch_price_data.reset_mock()

    # Second request - should hit cache
    result2 = await data_service.get_price_data(
        symbol=symbol,
        start_date=start_date,
        end_date=end_date,
        interval=interval,
    )

    # Verify cache hit (no provider call)
    mock_provider.fetch_price_data.assert_not_called()
    assert len(result2) > 0, "Should return cached data"


# ============================================================================
# Test 2: Cache hit returns fast without provider call
# ============================================================================
@pytest.mark.asyncio
@pytest.mark.integration
async def test_cache_hit_returns_fast(
    data_service: DataService,
    mock_provider: MockMarketDataProvider,
):
    """Verify cache hits are fast and don't hit provider.

    Flow:
    1. First request fetches and caches
    2. Second request returns from cache
    3. Should NOT hit provider again
    4. Response time should be reasonable (< 100ms for DB query)
    """
    symbol = "MSFT"
    start_date = datetime.now(timezone.utc) - timedelta(days=10)
    end_date = datetime.now(timezone.utc)
    interval = "1d"

    # First request - populates cache
    result1 = await data_service.get_price_data(
        symbol=symbol,
        start_date=start_date,
        end_date=end_date,
        interval=interval,
    )
    assert len(result1) > 0, "First request should return data"

    # Reset mock for tracking
    mock_provider.fetch_price_data.reset_mock()

    # Second request - should hit cache
    start_time = time.perf_counter()
    result2 = await data_service.get_price_data(
        symbol=symbol,
        start_date=start_date,
        end_date=end_date,
        interval=interval,
    )
    elapsed_ms = (time.perf_counter() - start_time) * 1000

    # Verify cache hit (no provider call)
    mock_provider.fetch_price_data.assert_not_called()
    assert len(result2) > 0, "Should return cached data"
    assert elapsed_ms < 100, f"Cache hit should be < 100ms, was {elapsed_ms:.2f}ms"


# ============================================================================
# Test 3: Cache persistence across service requests
# ============================================================================
@pytest.mark.asyncio
@pytest.mark.integration
async def test_cache_persistence(
    data_service: DataService,
    mock_provider: MockMarketDataProvider,
):
    """Verify cache persists in database across requests.

    Flow:
    1. First request fetches and caches
    2. Second request should hit cache
    3. Should NOT hit provider again
    """
    symbol = "GOOGL"
    start_date = datetime.now(timezone.utc) - timedelta(days=20)
    end_date = datetime.now(timezone.utc)
    interval = "1d"

    # First request - populates cache
    result1 = await data_service.get_price_data(
        symbol=symbol,
        start_date=start_date,
        end_date=end_date,
        interval=interval,
    )
    assert len(result1) > 0, "First request should return data"

    # Reset mock for tracking
    mock_provider.fetch_price_data.reset_mock()

    # Second request - should hit cache
    result2 = await data_service.get_price_data(
        symbol=symbol,
        start_date=start_date,
        end_date=end_date,
        interval=interval,
    )

    # Verify cache hit (no provider call)
    mock_provider.fetch_price_data.assert_not_called()
    assert len(result2) > 0, "Should return cached data"


# ============================================================================
# Test 4: Cache miss when data doesn't cover last complete trading day
# ============================================================================
@pytest.mark.asyncio
@pytest.mark.integration
async def test_cache_miss_after_ttl_expires(
    data_service: DataService,
    stock_repository: StockPriceRepository,
    mock_provider: MockMarketDataProvider,
    db_session: AsyncSession,
):
    """Verify cache miss when data doesn't cover last complete trading day.

    The system checks whether cached data covers up to the last complete trading
    day. When cached data is incomplete (missing recent trading days), the system
    correctly fetches new data.

    Scenario: Cache has data through Dec 1, but it's now Dec 3 pre-market, so the
    last complete trading day is Dec 2. Cache should be considered stale.

    Flow:
    1. First request fetches data (cache miss)
    2. Delete recent data to simulate incomplete cache
    3. Second request should miss cache (data doesn't cover last complete day)
    4. Should fetch fresh data from provider
    """
    symbol = "TSLA"
    # Use fixed dates for deterministic testing
    # Simulate: We're on Tuesday Dec 3, 2024 at 8am ET (pre-market)
    # Last complete trading day should be Monday Dec 2, 2024
    tuesday_premarket = datetime(2024, 12, 3, 13, 0, tzinfo=timezone.utc)  # 8am ET
    monday = date(2024, 12, 2)

    start_date = datetime(2024, 11, 18, tzinfo=timezone.utc)  # 15 days before
    end_date = datetime(2024, 12, 3, tzinfo=timezone.utc)
    interval = "1d"

    # First request - populates cache
    result1 = await data_service.get_price_data(
        symbol=symbol,
        start_date=start_date,
        end_date=end_date,
        interval=interval,
    )
    assert len(result1) > 0, "First request should return data"

    # Delete data from Dec 2 onwards to simulate incomplete cache
    # This makes the cached data NOT cover the last complete trading day (Dec 2)
    from sqlalchemy import delete

    delete_stmt = (
        delete(StockPrice)
        .where(StockPrice.symbol == symbol.upper())
        .where(StockPrice.timestamp >= datetime(2024, 12, 2, tzinfo=timezone.utc))
    )
    await db_session.execute(delete_stmt)
    await db_session.commit()

    # Reset mock for tracking
    mock_provider.fetch_price_data.reset_mock()

    # Mock the market calendar class methods to simulate Tuesday pre-market
    # The cache should detect that data doesn't cover Monday (last complete trading day)
    with patch("app.services.cache_service.trading_calendar_service.get_market_status", return_value="pre_market"), \
         patch("app.services.cache_service.trading_calendar_service.get_last_complete_trading_day", return_value=monday), \
         patch("app.services.cache_service.trading_calendar_service.get_next_trading_day", return_value=date(2024, 12, 3)):

        # Second request - should miss cache because data is incomplete
        # (doesn't cover last complete trading day - Monday Dec 2)
        result2 = await data_service.get_price_data(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            interval=interval,
        )

    # Verify cache miss (provider was called)
    assert mock_provider.fetch_price_data.call_count == 1, "Incomplete cache should trigger provider fetch"

    # Verify data was refetched (last_fetched_at should be recent)
    price_records = await stock_repository.get_price_data_by_date_range(
        symbol=symbol,
        start_date=start_date,
        end_date=end_date,
        interval=interval,
    )

    assert len(price_records) > 0, "Should have price records after refetch"
    for record in price_records:
        age = datetime.now(timezone.utc) - record.last_fetched_at
        assert age.total_seconds() < 5, "last_fetched_at should be updated to recent time"


# ============================================================================
# Test 5: Force refresh bypasses cache
# ============================================================================
@pytest.mark.asyncio
@pytest.mark.integration
async def test_force_refresh_bypasses_cache(
    data_service: DataService,
    mock_provider: MockMarketDataProvider,
):
    """Verify force_refresh bypasses cache.

    Flow:
    1. First request fetches and caches
    2. Verify cache hit on second request
    3. force_refresh=True should bypass cache and fetch from provider
    4. Should update cache with fresh data
    """
    symbol = "NVDA"
    start_date = datetime.now(timezone.utc) - timedelta(days=10)
    end_date = datetime.now(timezone.utc)
    interval = "1d"

    # First request - populates cache
    result1 = await data_service.get_price_data(
        symbol=symbol,
        start_date=start_date,
        end_date=end_date,
        interval=interval,
    )
    assert len(result1) > 0, "First request should return data"

    # Reset mock for tracking
    mock_provider.fetch_price_data.reset_mock()

    # Verify cache is populated
    result2 = await data_service.get_price_data(
        symbol=symbol,
        start_date=start_date,
        end_date=end_date,
        interval=interval,
    )
    mock_provider.fetch_price_data.assert_not_called()

    # Force refresh - should bypass cache
    mock_provider.fetch_price_data.reset_mock()
    result3 = await data_service.get_price_data(
        symbol=symbol,
        start_date=start_date,
        end_date=end_date,
        interval=interval,
        force_refresh=True,
    )

    # Verify provider was called
    assert mock_provider.fetch_price_data.call_count == 1, "force_refresh should call provider"
    assert len(result3) > 0, "Should return fresh data"

    # Verify cache was updated (next request should hit cache)
    mock_provider.fetch_price_data.reset_mock()
    result4 = await data_service.get_price_data(
        symbol=symbol,
        start_date=start_date,
        end_date=end_date,
        interval=interval,
    )
    mock_provider.fetch_price_data.assert_not_called()


# ============================================================================
# Test 6: Different request types share cache
# ============================================================================
@pytest.mark.asyncio
@pytest.mark.integration
async def test_different_request_types_share_cache(
    data_service: DataService,
    mock_provider: MockMarketDataProvider,
):
    """Verify different request types share cache.

    Flow:
    1. First request fetches hourly data
    2. Second request for same symbol/dates/interval
    3. Should use cached data (no duplicate provider call)
    4. Verify only one provider call made
    """
    symbol = "AMD"
    start_date = datetime.now(timezone.utc) - timedelta(days=5)
    end_date = datetime.now(timezone.utc)
    interval = "1h"

    # First request - hourly data fetch
    result1 = await data_service.get_price_data(
        symbol=symbol,
        start_date=start_date,
        end_date=end_date,
        interval=interval,
    )
    assert len(result1) > 0, "First request should return data"
    assert mock_provider.fetch_price_data.call_count == 1, "Should call provider once"

    # Reset mock for tracking
    mock_provider.fetch_price_data.reset_mock()

    # Second request - same parameters
    result2 = await data_service.get_price_data(
        symbol=symbol,
        start_date=start_date,
        end_date=end_date,
        interval=interval,
    )

    # Verify cache hit
    mock_provider.fetch_price_data.assert_not_called()
    assert len(result2) > 0, "Should return cached data"


# ============================================================================
# Test 7: Multiple symbol requests with cache behavior
# ============================================================================
@pytest.mark.asyncio
@pytest.mark.integration
async def test_multiple_symbol_cache_behavior(
    data_service: DataService,
    mock_provider: MockMarketDataProvider,
):
    """Verify cache behavior across multiple symbols.

    Flow:
    1. Make series of requests for different symbols
    2. Verify cache hits and misses based on provider calls
    """
    symbols = ["AAPL", "MSFT", "GOOGL"]
    start_date = datetime.now(timezone.utc) - timedelta(days=10)
    end_date = datetime.now(timezone.utc)
    interval = "1d"

    provider_calls = []

    # Request 1: AAPL - miss
    result = await data_service.get_price_data(
        symbol=symbols[0],
        start_date=start_date,
        end_date=end_date,
        interval=interval,
    )
    provider_calls.append(mock_provider.fetch_price_data.call_count)
    assert len(result) > 0, "First AAPL request should return data"

    # Request 2: AAPL - hit
    mock_provider.fetch_price_data.reset_mock()
    result = await data_service.get_price_data(
        symbol=symbols[0],
        start_date=start_date,
        end_date=end_date,
        interval=interval,
    )
    mock_provider.fetch_price_data.assert_not_called()

    # Request 3: MSFT - miss
    mock_provider.fetch_price_data.reset_mock()
    result = await data_service.get_price_data(
        symbol=symbols[1],
        start_date=start_date,
        end_date=end_date,
        interval=interval,
    )
    assert mock_provider.fetch_price_data.call_count == 1, "First MSFT request should call provider"

    # Request 4: MSFT - hit
    mock_provider.fetch_price_data.reset_mock()
    result = await data_service.get_price_data(
        symbol=symbols[1],
        start_date=start_date,
        end_date=end_date,
        interval=interval,
    )
    mock_provider.fetch_price_data.assert_not_called()

    # Request 5: GOOGL - miss
    mock_provider.fetch_price_data.reset_mock()
    result = await data_service.get_price_data(
        symbol=symbols[2],
        start_date=start_date,
        end_date=end_date,
        interval=interval,
    )
    assert mock_provider.fetch_price_data.call_count == 1, "First GOOGL request should call provider"


# ============================================================================
# Test 8: Multiple symbols cache isolation
# ============================================================================
@pytest.mark.asyncio
@pytest.mark.integration
async def test_multiple_symbols_cache_isolation(
    data_service: DataService,
    stock_repository: StockPriceRepository,
    mock_provider: MockMarketDataProvider,
):
    """Verify each symbol has isolated cache entry.

    Flow:
    1. Fetch data for AAPL (caches)
    2. Fetch data for MSFT (separate cache entry)
    3. Verify each symbol has its own cache entry
    4. Verify no cross-contamination
    """
    symbols = ["AAPL", "MSFT"]
    start_date = datetime.now(timezone.utc) - timedelta(days=10)
    end_date = datetime.now(timezone.utc)
    interval = "1d"

    # Fetch AAPL
    result1 = await data_service.get_price_data(
        symbol=symbols[0],
        start_date=start_date,
        end_date=end_date,
        interval=interval,
    )
    assert len(result1) > 0, "First AAPL request should return data"
    assert mock_provider.fetch_price_data.call_count == 1, "Should call provider for AAPL"

    # Fetch MSFT
    mock_provider.fetch_price_data.reset_mock()
    result2 = await data_service.get_price_data(
        symbol=symbols[1],
        start_date=start_date,
        end_date=end_date,
        interval=interval,
    )
    assert len(result2) > 0, "First MSFT request should return data"
    assert mock_provider.fetch_price_data.call_count == 1, "Should call provider for MSFT (different symbol)"

    # Verify AAPL cache still works
    mock_provider.fetch_price_data.reset_mock()
    result3 = await data_service.get_price_data(
        symbol=symbols[0],
        start_date=start_date,
        end_date=end_date,
        interval=interval,
    )
    mock_provider.fetch_price_data.assert_not_called()

    # Verify MSFT cache works
    mock_provider.fetch_price_data.reset_mock()
    result4 = await data_service.get_price_data(
        symbol=symbols[1],
        start_date=start_date,
        end_date=end_date,
        interval=interval,
    )
    mock_provider.fetch_price_data.assert_not_called()

    # Verify database has separate records
    aapl_records = await stock_repository.get_price_data_by_date_range(
        symbol=symbols[0],
        start_date=start_date,
        end_date=end_date,
        interval=interval,
    )

    msft_records = await stock_repository.get_price_data_by_date_range(
        symbol=symbols[1],
        start_date=start_date,
        end_date=end_date,
        interval=interval,
    )

    # Verify no cross-contamination
    assert all(r.symbol == symbols[0] for r in aapl_records), "AAPL records should only have AAPL symbol"
    assert all(r.symbol == symbols[1] for r in msft_records), "MSFT records should only have MSFT symbol"
    assert len(aapl_records) > 0, "Should have AAPL records"
    assert len(msft_records) > 0, "Should have MSFT records"

    # Verify records are different (different timestamps or prices)
    aapl_timestamps = {r.timestamp for r in aapl_records}
    msft_timestamps = {r.timestamp for r in msft_records}
    # Timestamps should be the same (same date range), but verify symbols are different
    assert aapl_timestamps == msft_timestamps, "Should have same timestamps for same date range"

    # Verify different symbols in database
    all_symbols = {r.symbol for r in aapl_records + msft_records}
    assert all_symbols == {symbols[0], symbols[1]}, "Should have both symbols in database"


# ============================================================================
# Test 9: Different intervals have separate cache entries
# ============================================================================
@pytest.mark.asyncio
@pytest.mark.integration
async def test_different_intervals_cache_isolation(
    data_service: DataService,
    mock_provider: MockMarketDataProvider,
):
    """Verify different intervals have separate cache entries.

    Flow:
    1. Fetch daily data for symbol
    2. Fetch hourly data for same symbol/dates
    3. Should have separate cache entries
    4. Both should cache independently
    """
    symbol = "META"
    start_date = datetime.now(timezone.utc) - timedelta(days=5)
    end_date = datetime.now(timezone.utc)

    # Fetch daily data
    result1 = await data_service.get_price_data(
        symbol=symbol,
        start_date=start_date,
        end_date=end_date,
        interval="1d",
    )
    assert len(result1) > 0, "First 1d request should return data"
    assert mock_provider.fetch_price_data.call_count == 1, "Should call provider for 1d"

    # Fetch hourly data (same symbol/dates, different interval)
    mock_provider.fetch_price_data.reset_mock()
    result2 = await data_service.get_price_data(
        symbol=symbol,
        start_date=start_date,
        end_date=end_date,
        interval="1h",
    )
    assert len(result2) > 0, "First 1h request should return data"
    assert mock_provider.fetch_price_data.call_count == 1, "Should call provider for 1h (different interval)"

    # Verify daily cache still works
    mock_provider.fetch_price_data.reset_mock()
    result3 = await data_service.get_price_data(
        symbol=symbol,
        start_date=start_date,
        end_date=end_date,
        interval="1d",
    )
    mock_provider.fetch_price_data.assert_not_called()

    # Verify hourly cache works
    mock_provider.fetch_price_data.reset_mock()
    result4 = await data_service.get_price_data(
        symbol=symbol,
        start_date=start_date,
        end_date=end_date,
        interval="1h",
    )
    mock_provider.fetch_price_data.assert_not_called()


# ============================================================================
# Test 10: Concurrent requests for same symbol don't duplicate API calls
# ============================================================================
@pytest.mark.asyncio
@pytest.mark.integration
async def test_concurrent_requests_same_symbol_no_duplicates(
    data_service: DataService,
    mock_provider: MockMarketDataProvider,
):
    """Verify concurrent requests don't duplicate API calls or cause errors.

    Race condition test:
    1. Fire 5 concurrent requests for SAME symbol/interval/dates
    2. Should only trigger 1 provider call (double-check locking)
    3. Should not raise IntegrityError from duplicate inserts
    4. All requests should succeed and return data

    This tests the fix for Issue #3 (race condition in concurrent cache writes).
    """
    symbol = "RACE"
    start_date = datetime.now(timezone.utc) - timedelta(days=10)
    end_date = datetime.now(timezone.utc)
    interval = "1d"

    # Track provider calls
    call_count = 0
    original_fetch = mock_provider.fetch_price_data

    async def tracked_fetch(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        # Increase race window to make race condition more likely without fix
        await asyncio.sleep(0.05)
        return await original_fetch(*args, **kwargs)

    mock_provider.fetch_price_data = tracked_fetch

    # Fire 5 concurrent requests for SAME symbol/interval/dates
    tasks = [
        data_service.get_price_data(symbol, start_date, end_date, interval)
        for _ in range(5)
    ]

    # Execute all tasks concurrently
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Verify no errors (especially no IntegrityError)
    errors = [r for r in results if isinstance(r, Exception)]
    assert len(errors) == 0, f"No errors expected, got: {errors}"

    # Verify only 1 provider call (race condition prevented)
    assert call_count == 1, f"Expected 1 provider call, got {call_count}"

    # Verify all requests succeeded (returned list of PriceDataPoint)
    for r in results:
        assert isinstance(r, list), "All requests should return list"
        assert len(r) > 0, "All results should have data"
        assert all(hasattr(point, 'symbol') for point in r), "All results should be PriceDataPoint"


# ============================================================================
# Test 11: Double-check after lock detects fresh data
# ============================================================================
@pytest.mark.asyncio
@pytest.mark.integration
async def test_double_check_after_lock_returns_cached(
    data_service: DataService,
    mock_provider: MockMarketDataProvider,
):
    """Verify double-check after lock returns cached data without re-fetching.

    Race condition scenario:
    1. Request A and B both see stale cache
    2. Request A acquires lock, fetches, stores, releases lock
    3. Request B acquires lock, double-checks, finds fresh data → returns cache
    4. Provider should only be called once total

    This explicitly tests the double-check code path at data_service.py:249-267.
    """
    symbol = "DBLCHK"
    start_date = datetime.now(timezone.utc) - timedelta(days=10)
    end_date = datetime.now(timezone.utc)
    interval = "1d"

    # Track call count and add delay to widen the race window
    call_count = 0
    original_fetch = mock_provider.fetch_price_data

    async def slow_fetch(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        await asyncio.sleep(0.1)  # Slow fetch to widen race window
        return await original_fetch(*args, **kwargs)

    mock_provider.fetch_price_data = slow_fetch

    # Clear any existing lock for this cache key
    cache_key = f"{symbol}:{interval}:{start_date.date()}:{end_date.date()}"
    DataService._fetch_locks.pop(cache_key, None)

    # Fire 3 concurrent requests — first enters lock and fetches,
    # others wait for lock then double-check finds fresh cache
    tasks = [
        data_service.get_price_data(symbol, start_date, end_date, interval)
        for _ in range(3)
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Verify no errors
    errors = [r for r in results if isinstance(r, Exception)]
    assert len(errors) == 0, f"No errors expected, got: {errors}"

    # KEY ASSERTION: Provider called exactly once.
    # The other requests hit the double-check-after-lock path and returned cache.
    assert call_count == 1, (
        f"Expected exactly 1 provider call (double-check should return cache), got {call_count}"
    )

    # All requests should return data
    for r in results:
        assert isinstance(r, list) and len(r) > 0, "All requests should return data"


# ============================================================================
# Test 12: Incremental fetch uses correct start date
# ============================================================================
@pytest.mark.asyncio
@pytest.mark.integration
async def test_incremental_fetch_uses_correct_start_date(
    data_service: DataService,
    mock_provider: MockMarketDataProvider,
    db_session: AsyncSession,
):
    """Verify incremental fetch starts from the gap, not from the beginning.

    Tests data_service.py:235-244 — when cache has partial data, fetch_start_date
    is set so only missing data is fetched.

    Flow:
    1. Populate cache with data for a date range
    2. Delete recent data to simulate incomplete cache
    3. Mock market calendar so freshness check returns stale with fetch_start_date
    4. Request data — provider should be called with start_date near the gap
    """
    symbol = "INCR"
    # Use fixed dates for deterministic testing
    start_date = datetime(2024, 11, 1, tzinfo=timezone.utc)
    end_date = datetime(2024, 11, 20, tzinfo=timezone.utc)
    interval = "1d"

    # Step 1: Populate cache with full range
    result1 = await data_service.get_price_data(
        symbol=symbol,
        start_date=start_date,
        end_date=end_date,
        interval=interval,
    )
    assert len(result1) > 0, "First request should return data"
    assert mock_provider.fetch_price_data.call_count == 1

    # Step 2: Delete data from Nov 10 onward to simulate incomplete cache
    from sqlalchemy import delete
    delete_stmt = (
        delete(StockPrice)
        .where(StockPrice.symbol == symbol.upper())
        .where(StockPrice.timestamp >= datetime(2024, 11, 10, tzinfo=timezone.utc))
    )
    await db_session.execute(delete_stmt)
    await db_session.commit()

    # Step 3: Reset provider mock and wrap to capture call args
    original_fetch = mock_provider.fetch_price_data
    mock_provider.fetch_price_data = AsyncMock(wraps=original_fetch)

    # Clear lock so we don't get a stale double-check
    cache_key = f"{symbol}:{interval}:{start_date.date()}:{end_date.date()}"
    DataService._fetch_locks.pop(cache_key, None)

    # Mock market calendar to make the freshness check return stale
    # Last complete day = Nov 19 (a trading day), current status = "closed"
    with patch("app.services.cache_service.trading_calendar_service.get_market_status", return_value="closed"), \
         patch("app.services.cache_service.trading_calendar_service.get_last_complete_trading_day", return_value=date(2024, 11, 19)), \
         patch("app.services.cache_service.trading_calendar_service.get_next_trading_day", return_value=date(2024, 11, 11)):

        # Step 4: Request data — should detect gap and do incremental fetch
        result2 = await data_service.get_price_data(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            interval=interval,
        )

    # Verify provider was called
    assert mock_provider.fetch_price_data.call_count == 1, "Should call provider for missing data"

    # Verify the fetch request used an incremental start date (not Nov 1)
    call_args = mock_provider.fetch_price_data.call_args
    fetch_request = call_args[0][0]  # First positional arg is PriceDataRequest
    # The fetch_start should be around Nov 9 (last_data_date from cache)
    # not Nov 1 (the original start_date)
    assert fetch_request.start_date.date() >= date(2024, 11, 5), (
        f"Incremental fetch should start near the gap, not from {start_date.date()}. "
        f"Got start_date={fetch_request.start_date.date()}"
    )
    assert fetch_request.start_date.date() < date(2024, 11, 15), (
        f"Incremental fetch should start before Nov 15. Got {fetch_request.start_date.date()}"
    )


# ============================================================================
# Test 13: Market-hours 5-minute TTL
# ============================================================================
@pytest.mark.asyncio
@pytest.mark.integration
async def test_market_hours_ttl_freshness(
    data_service: DataService,
    mock_provider: MockMarketDataProvider,
    db_session: AsyncSession,
):
    """Verify market-hours TTL: fresh within 5 min, stale after 5 min.

    Tests cache_service.py:188-230 — during market_open, cache is fresh if
    last_fetched_at is within 5 minutes, stale if older.

    Flow:
    1. Populate cache for today's symbol
    2. Mock market status as market_open with today as a trading day
    3. Verify cache hit when last_fetched_at is recent (< 5 min)
    4. Backdate last_fetched_at to 6 min ago
    5. Verify cache miss (provider called)
    """
    symbol = "TTLTEST"
    now = datetime.now(timezone.utc)
    today = now.date()
    start_date = now - timedelta(days=5)
    end_date = now
    interval = "1d"

    # Step 1: Populate cache
    result1 = await data_service.get_price_data(
        symbol=symbol,
        start_date=start_date,
        end_date=end_date,
        interval=interval,
    )
    assert len(result1) > 0, "First request should return data"
    assert mock_provider.fetch_price_data.call_count == 1

    # Reset provider mock
    mock_provider.fetch_price_data.reset_mock()

    # Clear lock to avoid stale state
    cache_key = f"{symbol}:{interval}:{start_date.date()}:{end_date.date()}"
    DataService._fetch_locks.pop(cache_key, None)

    # Step 2: Mock market as open with today as a trading day
    market_patches = {
        "app.services.cache_service.trading_calendar_service.get_market_status": "market_open",
        "app.services.cache_service.trading_calendar_service.get_last_complete_trading_day": today - timedelta(days=1),
        "app.services.cache_service.trading_calendar_service.is_trading_day": lambda d: True,
        "app.services.cache_service.trading_calendar_service.get_first_trading_day_on_or_after": lambda d: d,
    }

    with patch(
        "app.services.cache_service.trading_calendar_service.get_market_status",
        return_value="market_open",
    ), patch(
        "app.services.cache_service.trading_calendar_service.get_last_complete_trading_day",
        return_value=today - timedelta(days=1),
    ), patch(
        "app.services.cache_service.trading_calendar_service.is_trading_day",
        return_value=True,
    ), patch(
        "app.services.cache_service.trading_calendar_service.get_first_trading_day_on_or_after",
        side_effect=lambda d: d,
    ):
        # Step 3: Cache should be fresh — last_fetched_at is very recent (just populated)
        result2 = await data_service.get_price_data(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            interval=interval,
        )
        mock_provider.fetch_price_data.assert_not_called()
        assert len(result2) > 0, "Should return cached data (fresh TTL)"

        # Step 4: Backdate last_fetched_at to 6 minutes ago (outside 5-min TTL)
        six_minutes_ago = now - timedelta(minutes=6)
        update_stmt = (
            update(StockPrice)
            .where(StockPrice.symbol == symbol.upper())
            .where(StockPrice.interval == interval)
            .values(last_fetched_at=six_minutes_ago)
        )
        await db_session.execute(update_stmt)
        await db_session.commit()

        # Clear lock again
        DataService._fetch_locks.pop(cache_key, None)

        # Step 5: Cache should be stale — TTL expired
        result3 = await data_service.get_price_data(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            interval=interval,
        )
        assert mock_provider.fetch_price_data.call_count == 1, (
            "Should call provider after TTL expired during market hours"
        )
        assert len(result3) > 0, "Should return fresh data after TTL expiry"
