"""Integration tests for the two-level cache architecture.

Tests verify the complete cache flow:
- L1 Cache: In-memory TTLCache (30 seconds, 200 symbols max)
- L2 Cache: Database with TTL validation based on last_fetched_at
- Cache Flow: Request → L1 → L2 → Provider → Store L2 → Store L1 → Return

Coverage includes:
- Cache misses triggering provider fetch
- L1 cache hits (fast in-memory)
- L2 cache hits (database)
- TTL expiration forcing fresh fetch
- Force refresh bypassing cache
- Cache sharing across different request types
- Cache statistics tracking
- Multi-symbol cache isolation
"""
import asyncio
import time
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import patch

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.stock import StockPrice
from app.providers.mock import MockMarketDataProvider
from app.repositories.stock_price import StockPriceRepository
from app.services.cache_service import CacheHitType, CacheTTLConfig, MarketDataCache
from app.services.data_service import DataService


@pytest_asyncio.fixture
async def mock_provider():
    """Create mock provider with predictable data."""
    return MockMarketDataProvider()


@pytest_asyncio.fixture
async def stock_repository(db_session: AsyncSession):
    """Create stock price repository."""
    return StockPriceRepository(db_session)


@pytest_asyncio.fixture
async def cache_service(stock_repository: StockPriceRepository):
    """Create cache service with short TTLs for testing."""
    ttl_config = CacheTTLConfig(
        daily=86400,      # 24 hours
        hourly=3600,      # 1 hour
        intraday=300,     # 5 minutes
        l1_ttl=30,        # 30 seconds
        l1_size=200,      # 200 symbols
    )
    return MarketDataCache(stock_repository, ttl_config)


@pytest_asyncio.fixture
async def data_service(
    db_session: AsyncSession,
    mock_provider: MockMarketDataProvider,
    cache_service: MarketDataCache,
    stock_repository: StockPriceRepository,
):
    """Create data service with cache enabled."""
    return DataService(
        session=db_session,
        provider=mock_provider,
        cache=cache_service,
        repository=stock_repository,
    )


# ============================================================================
# Test 1: Cache miss fetches and stores
# ============================================================================
@pytest.mark.asyncio
@pytest.mark.integration
async def test_cache_miss_fetches_and_stores(
    data_service: DataService,
    stock_repository: StockPriceRepository,
    db_session: AsyncSession,
):
    """Verify first request misses cache and fetches from provider.

    Flow:
    1. First request for symbol should miss L1 and L2 cache
    2. Should fetch from provider
    3. Should store in database (L2)
    4. Should populate L1 cache
    5. Verify last_fetched_at is set
    """
    symbol = "AAPL"
    start_date = datetime.now(timezone.utc) - timedelta(days=30)
    end_date = datetime.now(timezone.utc)
    interval = "1d"

    # First request - should miss cache
    stats = await data_service.fetch_and_store_data(
        symbol=symbol,
        start_date=start_date,
        end_date=end_date,
        interval=interval,
    )

    # Verify cache miss
    assert stats["cache_hit"] is False, "First request should miss cache"
    assert stats["inserted"] > 0, "Should insert new records on cache miss"

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

    # Verify L1 cache is populated (by making another request immediately)
    stats2 = await data_service.fetch_and_store_data(
        symbol=symbol,
        start_date=start_date,
        end_date=end_date,
        interval=interval,
    )

    assert stats2["cache_hit"] is True, "Second request should hit L1 cache"
    assert stats2["hit_type"] == CacheHitType.L1_HIT, "Should be L1 cache hit"


# ============================================================================
# Test 2: L1 cache hit returns fast
# ============================================================================
@pytest.mark.asyncio
@pytest.mark.integration
async def test_cache_hit_l1_returns_fast(
    data_service: DataService,
    mock_provider: MockMarketDataProvider,
):
    """Verify L1 cache hits are fast and don't hit provider.

    Flow:
    1. First request fetches and caches
    2. Second request (within L1 TTL) returns from L1
    3. Should NOT hit provider again
    4. Response time should be < 50ms
    """
    symbol = "MSFT"
    start_date = datetime.now(timezone.utc) - timedelta(days=10)
    end_date = datetime.now(timezone.utc)
    interval = "1d"

    # First request - populates cache
    stats1 = await data_service.fetch_and_store_data(
        symbol=symbol,
        start_date=start_date,
        end_date=end_date,
        interval=interval,
    )
    assert stats1["cache_hit"] is False, "First request should miss cache"

    # Track provider calls
    original_fetch = mock_provider.fetch_price_data
    call_count = 0

    async def tracked_fetch(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        return await original_fetch(*args, **kwargs)

    mock_provider.fetch_price_data = tracked_fetch

    # Second request - should hit L1 cache
    start_time = time.perf_counter()
    stats2 = await data_service.fetch_and_store_data(
        symbol=symbol,
        start_date=start_date,
        end_date=end_date,
        interval=interval,
    )
    elapsed_ms = (time.perf_counter() - start_time) * 1000

    assert stats2["cache_hit"] is True, "Second request should hit cache"
    assert stats2["hit_type"] == CacheHitType.L1_HIT, "Should be L1 cache hit"
    assert call_count == 0, "Should NOT call provider on L1 cache hit"
    assert elapsed_ms < 50, f"L1 cache hit should be < 50ms, was {elapsed_ms:.2f}ms"


# ============================================================================
# Test 3: L2 cache hit after L1 expires
# ============================================================================
@pytest.mark.asyncio
@pytest.mark.integration
async def test_cache_hit_l2_after_l1_expires(
    data_service: DataService,
    cache_service: MarketDataCache,
    mock_provider: MockMarketDataProvider,
):
    """Verify L2 cache hit after L1 expires.

    Flow:
    1. First request fetches and caches
    2. Clear L1 cache (simulate expiration)
    3. Second request should hit L2 (database)
    4. Should NOT hit provider again
    5. Should repopulate L1 cache
    """
    symbol = "GOOGL"
    start_date = datetime.now(timezone.utc) - timedelta(days=20)
    end_date = datetime.now(timezone.utc)
    interval = "1d"

    # First request - populates both caches
    stats1 = await data_service.fetch_and_store_data(
        symbol=symbol,
        start_date=start_date,
        end_date=end_date,
        interval=interval,
    )
    assert stats1["cache_hit"] is False, "First request should miss cache"

    # Track provider calls
    original_fetch = mock_provider.fetch_price_data
    call_count = 0

    async def tracked_fetch(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        return await original_fetch(*args, **kwargs)

    mock_provider.fetch_price_data = tracked_fetch

    # Clear L1 cache to simulate expiration
    cache_service.l1_cache.clear()

    # Second request - should hit L2 cache
    stats2 = await data_service.fetch_and_store_data(
        symbol=symbol,
        start_date=start_date,
        end_date=end_date,
        interval=interval,
    )

    assert stats2["cache_hit"] is True, "Second request should hit cache"
    assert stats2["hit_type"] == CacheHitType.L2_HIT, "Should be L2 cache hit"
    assert call_count == 0, "Should NOT call provider on L2 cache hit"

    # Verify L1 cache is repopulated
    stats3 = await data_service.fetch_and_store_data(
        symbol=symbol,
        start_date=start_date,
        end_date=end_date,
        interval=interval,
    )
    assert stats3["hit_type"] == CacheHitType.L1_HIT, "L1 cache should be repopulated"


# ============================================================================
# Test 4: Cache miss when data doesn't cover last complete trading day
# ============================================================================
@pytest.mark.asyncio
@pytest.mark.integration
async def test_cache_miss_after_ttl_expires(
    data_service: DataService,
    stock_repository: StockPriceRepository,
    cache_service: MarketDataCache,
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

    # First request - populates cache (no mocking needed for initial fetch)
    stats1 = await data_service.fetch_and_store_data(
        symbol=symbol,
        start_date=start_date,
        end_date=end_date,
        interval=interval,
    )
    assert stats1["cache_hit"] is False, "First request should miss cache"

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

    # Clear L1 cache
    cache_service.l1_cache.clear()

    # Mock the market calendar class methods to simulate Tuesday pre-market
    # The cache should detect that data doesn't cover Monday (last complete trading day)
    with patch("app.services.cache_service.trading_calendar_service.get_market_status", return_value="pre_market"), \
         patch("app.services.cache_service.trading_calendar_service.get_last_complete_trading_day", return_value=monday), \
         patch("app.services.cache_service.trading_calendar_service.get_next_trading_day", return_value=date(2024, 12, 3)):

        # Second request - should miss cache because data is incomplete
        # (doesn't cover last complete trading day - Monday Dec 2)
        stats2 = await data_service.fetch_and_store_data(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            interval=interval,
        )

    assert stats2["cache_hit"] is False, "Incomplete cache should be treated as miss"

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
    2. Second request with force_refresh=True should bypass cache
    3. Should fetch from provider even though cache has data
    4. Should update cache with fresh data
    """
    symbol = "NVDA"
    start_date = datetime.now(timezone.utc) - timedelta(days=10)
    end_date = datetime.now(timezone.utc)
    interval = "1d"

    # First request - populates cache
    stats1 = await data_service.fetch_and_store_data(
        symbol=symbol,
        start_date=start_date,
        end_date=end_date,
        interval=interval,
    )
    assert stats1["cache_hit"] is False, "First request should miss cache"

    # Verify cache is populated
    stats2 = await data_service.fetch_and_store_data(
        symbol=symbol,
        start_date=start_date,
        end_date=end_date,
        interval=interval,
    )
    assert stats2["cache_hit"] is True, "Cache should be populated"

    # Track provider calls
    original_fetch = mock_provider.fetch_price_data
    call_count = 0

    async def tracked_fetch(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        return await original_fetch(*args, **kwargs)

    mock_provider.fetch_price_data = tracked_fetch

    # Force refresh - should bypass cache
    stats3 = await data_service.fetch_and_store_data(
        symbol=symbol,
        start_date=start_date,
        end_date=end_date,
        interval=interval,
        force_refresh=True,
    )

    assert stats3["cache_hit"] is False, "force_refresh should bypass cache"
    assert call_count == 1, "force_refresh should call provider"

    # Verify cache was updated (next request should hit cache)
    mock_provider.fetch_price_data = original_fetch  # Reset tracker
    stats4 = await data_service.fetch_and_store_data(
        symbol=symbol,
        start_date=start_date,
        end_date=end_date,
        interval=interval,
    )
    assert stats4["cache_hit"] is True, "Cache should be updated after force_refresh"


# ============================================================================
# Test 6: Simulation and chart share cache
# ============================================================================
@pytest.mark.asyncio
@pytest.mark.integration
async def test_different_request_types_share_cache(
    data_service: DataService,
    mock_provider: MockMarketDataProvider,
):
    """Verify different request types share cache.

    Flow:
    1. First request type (fetches hourly data)
    2. Request chart data for same symbol/dates
    3. Should use cached data (no duplicate provider call)
    4. Verify only one provider call made
    """
    symbol = "AMD"
    start_date = datetime.now(timezone.utc) - timedelta(days=5)
    end_date = datetime.now(timezone.utc)
    interval = "1h"

    # Track provider calls
    original_fetch = mock_provider.fetch_price_data
    call_count = 0

    async def tracked_fetch(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        return await original_fetch(*args, **kwargs)

    mock_provider.fetch_price_data = tracked_fetch

    # First request - hourly data fetch
    stats1 = await data_service.fetch_and_store_data(
        symbol=symbol,
        start_date=start_date,
        end_date=end_date,
        interval=interval,
    )
    assert stats1["cache_hit"] is False, "First request should miss cache"
    assert call_count == 1, "Should call provider once"

    # Second request - simulates chart data request
    stats2 = await data_service.fetch_and_store_data(
        symbol=symbol,
        start_date=start_date,
        end_date=end_date,
        interval=interval,
    )
    assert stats2["cache_hit"] is True, "Chart request should use cached data"
    assert call_count == 1, "Should NOT call provider again (cache hit)"


# ============================================================================
# Test 7: Cache statistics tracking
# ============================================================================
@pytest.mark.asyncio
@pytest.mark.integration
async def test_cache_statistics_tracking(
    data_service: DataService,
    cache_service: MarketDataCache,
):
    """Verify cache statistics are tracked correctly.

    Flow:
    1. Make series of requests (mix of hits and misses)
    2. Verify cache statistics are correct (L1 hits, L2 hits, misses)
    3. Verify cache hit rate calculation
    """
    symbols = ["AAPL", "MSFT", "GOOGL"]
    start_date = datetime.now(timezone.utc) - timedelta(days=10)
    end_date = datetime.now(timezone.utc)
    interval = "1d"

    stats_list = []

    # Request 1: AAPL - miss
    stats = await data_service.fetch_and_store_data(
        symbol=symbols[0],
        start_date=start_date,
        end_date=end_date,
        interval=interval,
    )
    stats_list.append(stats)
    assert stats["cache_hit"] is False, "First AAPL request should miss"

    # Request 2: AAPL - L1 hit
    stats = await data_service.fetch_and_store_data(
        symbol=symbols[0],
        start_date=start_date,
        end_date=end_date,
        interval=interval,
    )
    stats_list.append(stats)
    assert stats["cache_hit"] is True, "Second AAPL request should hit L1"
    assert stats["hit_type"] == CacheHitType.L1_HIT

    # Request 3: MSFT - miss
    stats = await data_service.fetch_and_store_data(
        symbol=symbols[1],
        start_date=start_date,
        end_date=end_date,
        interval=interval,
    )
    stats_list.append(stats)
    assert stats["cache_hit"] is False, "First MSFT request should miss"

    # Request 4: MSFT - L1 hit
    stats = await data_service.fetch_and_store_data(
        symbol=symbols[1],
        start_date=start_date,
        end_date=end_date,
        interval=interval,
    )
    stats_list.append(stats)
    assert stats["cache_hit"] is True, "Second MSFT request should hit L1"
    assert stats["hit_type"] == CacheHitType.L1_HIT

    # Clear L1 cache
    cache_service.l1_cache.clear()

    # Request 5: AAPL - L2 hit (L1 cleared)
    stats = await data_service.fetch_and_store_data(
        symbol=symbols[0],
        start_date=start_date,
        end_date=end_date,
        interval=interval,
    )
    stats_list.append(stats)
    assert stats["cache_hit"] is True, "AAPL request should hit L2"
    assert stats["hit_type"] == CacheHitType.L2_HIT

    # Request 6: GOOGL - miss
    stats = await data_service.fetch_and_store_data(
        symbol=symbols[2],
        start_date=start_date,
        end_date=end_date,
        interval=interval,
    )
    stats_list.append(stats)
    assert stats["cache_hit"] is False, "First GOOGL request should miss"

    # Calculate statistics
    total_requests = len(stats_list)
    cache_hits = sum(1 for s in stats_list if s["cache_hit"])
    l1_hits = sum(1 for s in stats_list if s.get("hit_type") == CacheHitType.L1_HIT)
    l2_hits = sum(1 for s in stats_list if s.get("hit_type") == CacheHitType.L2_HIT)
    misses = sum(1 for s in stats_list if not s["cache_hit"])
    hit_rate = (cache_hits / total_requests) * 100

    assert total_requests == 6, "Should have 6 total requests"
    assert cache_hits == 3, "Should have 3 cache hits"
    assert l1_hits == 2, "Should have 2 L1 hits"
    assert l2_hits == 1, "Should have 1 L2 hit"
    assert misses == 3, "Should have 3 cache misses"
    assert hit_rate == 50.0, "Cache hit rate should be 50%"


# ============================================================================
# Test 8: Multiple symbols cache isolation
# ============================================================================
@pytest.mark.asyncio
@pytest.mark.integration
async def test_multiple_symbols_cache_isolation(
    data_service: DataService,
    stock_repository: StockPriceRepository,
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
    stats1 = await data_service.fetch_and_store_data(
        symbol=symbols[0],
        start_date=start_date,
        end_date=end_date,
        interval=interval,
    )
    assert stats1["cache_hit"] is False, "First AAPL request should miss"

    # Fetch MSFT
    stats2 = await data_service.fetch_and_store_data(
        symbol=symbols[1],
        start_date=start_date,
        end_date=end_date,
        interval=interval,
    )
    assert stats2["cache_hit"] is False, "First MSFT request should miss (different symbol)"

    # Verify AAPL cache still works
    stats3 = await data_service.fetch_and_store_data(
        symbol=symbols[0],
        start_date=start_date,
        end_date=end_date,
        interval=interval,
    )
    assert stats3["cache_hit"] is True, "AAPL cache should still be valid"

    # Verify MSFT cache works
    stats4 = await data_service.fetch_and_store_data(
        symbol=symbols[1],
        start_date=start_date,
        end_date=end_date,
        interval=interval,
    )
    assert stats4["cache_hit"] is True, "MSFT cache should be valid"

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
# Test 9: Cache invalidation
# ============================================================================
@pytest.mark.asyncio
@pytest.mark.integration
async def test_cache_invalidation(
    data_service: DataService,
    cache_service: MarketDataCache,
    mock_provider: MockMarketDataProvider,
):
    """Verify cache invalidation clears L1 cache for a symbol.

    Flow:
    1. Fetch data for symbol (populates L1 cache)
    2. Invalidate cache for symbol
    3. Next request should miss L1 but hit L2
    """
    symbol = "INTC"
    start_date = datetime.now(timezone.utc) - timedelta(days=10)
    end_date = datetime.now(timezone.utc)
    interval = "1d"

    # First request - populates cache
    stats1 = await data_service.fetch_and_store_data(
        symbol=symbol,
        start_date=start_date,
        end_date=end_date,
        interval=interval,
    )
    assert stats1["cache_hit"] is False, "First request should miss cache"

    # Second request - should hit L1
    stats2 = await data_service.fetch_and_store_data(
        symbol=symbol,
        start_date=start_date,
        end_date=end_date,
        interval=interval,
    )
    assert stats2["cache_hit"] is True, "Second request should hit L1"
    assert stats2["hit_type"] == CacheHitType.L1_HIT

    # Invalidate cache
    cache_service.invalidate(symbol)

    # Third request - should miss L1 but hit L2
    stats3 = await data_service.fetch_and_store_data(
        symbol=symbol,
        start_date=start_date,
        end_date=end_date,
        interval=interval,
    )
    assert stats3["cache_hit"] is True, "Should hit L2 after L1 invalidation"
    assert stats3["hit_type"] == CacheHitType.L2_HIT, "Should be L2 hit after invalidation"


# ============================================================================
# Test 10: Different intervals have separate cache entries
# ============================================================================
@pytest.mark.asyncio
@pytest.mark.integration
async def test_different_intervals_cache_isolation(
    data_service: DataService,
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
    stats1 = await data_service.fetch_and_store_data(
        symbol=symbol,
        start_date=start_date,
        end_date=end_date,
        interval="1d",
    )
    assert stats1["cache_hit"] is False, "First 1d request should miss"

    # Fetch hourly data (same symbol/dates, different interval)
    stats2 = await data_service.fetch_and_store_data(
        symbol=symbol,
        start_date=start_date,
        end_date=end_date,
        interval="1h",
    )
    assert stats2["cache_hit"] is False, "First 1h request should miss (different interval)"

    # Verify daily cache still works
    stats3 = await data_service.fetch_and_store_data(
        symbol=symbol,
        start_date=start_date,
        end_date=end_date,
        interval="1d",
    )
    assert stats3["cache_hit"] is True, "1d cache should still be valid"

    # Verify hourly cache works
    stats4 = await data_service.fetch_and_store_data(
        symbol=symbol,
        start_date=start_date,
        end_date=end_date,
        interval="1h",
    )
    assert stats4["cache_hit"] is True, "1h cache should be valid"


# ============================================================================
# Test 11: Concurrent requests for same symbol don't duplicate API calls
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
    4. Should have 1 cache miss (first request) and 4 cache hits (others wait for first)
    5. All requests should succeed

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
        data_service.fetch_and_store_data(symbol, start_date, end_date, interval)
        for _ in range(5)
    ]

    # Execute all tasks concurrently
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Verify no errors (especially no IntegrityError)
    errors = [r for r in results if isinstance(r, Exception)]
    assert len(errors) == 0, f"No errors expected, got: {errors}"

    # Verify only 1 provider call (race condition prevented)
    assert call_count == 1, f"Expected 1 provider call, got {call_count}"

    # Count cache misses (only first request should miss)
    cache_misses = sum(1 for r in results if not r.get("cache_hit", False))
    assert cache_misses == 1, f"Expected 1 cache miss, got {cache_misses}"

    # Verify cache hits (4 requests should wait and get cached data)
    cache_hits = sum(1 for r in results if r.get("cache_hit", False))
    assert cache_hits == 4, f"Expected 4 cache hits, got {cache_hits}"

    # Verify all requests succeeded (returned dict with expected keys)
    for r in results:
        assert isinstance(r, dict), "All requests should return dict"
        assert "cache_hit" in r, "All results should have cache_hit key"

    # Log statistics for debugging
    total_inserted = sum(r.get("inserted", 0) for r in results)
    total_updated = sum(r.get("updated", 0) for r in results)

    # Should have inserted records only once (from first request)
    assert total_inserted > 0, "Should have inserted records"
    # Other requests hit cache, so total inserts should be from only 1 request
    assert total_inserted == results[0].get("inserted", 0), "Only first request should insert"
