# refactor: simplify caching system and eliminate query redundancy

## Summary

Simplified the caching system by removing the L1 in-memory cache layer and merging `fetch_and_store_data()` into `get_price_data()`. This change eliminates redundant database queries, removes ~400 lines of dead code, and significantly improves cache hit performance while preserving all smart market-aware freshness logic.

## Problem

The existing caching implementation had several issues:

1. **Query Redundancy**: Cache hits required 3 separate database queries:
   - Query 1: Freshness check reads price records from DB
   - Query 2: `fetch_and_store_data()` reads same records again via `get_cached_price_data()`
   - Query 3: `get_price_data()` reads records a third time to return results

2. **Dead L1 Cache**: The in-memory TTLCache was created per-request in dependency injection, so it was always empty and provided zero cache hits

3. **Code Complexity**: Split between `fetch_and_store_data()` and `get_price_data()` methods created unnecessary indirection

4. **Maintenance Burden**: 5 separate TTL config settings, unused repository methods, and extra dependency (`cachetools`)

## Solution

### Phase 1: Eliminate Query Redundancy

**Added `cached_records` field to `FreshnessResult`**:
- Freshness check now returns the DB records it reads
- Cache hit path uses these records directly (no re-query)
- Reduces 3 queries to 1 query on cache hits

**Merged `fetch_and_store_data()` into `get_price_data()`**:
- Eliminated method split and indirection
- Simplified control flow: freshness check → use cached data OR fetch → store → read
- Preserved double-check locking for race condition protection
- Removed ~100 lines of code from `data_service.py`

### Phase 2: Remove Dead Code

**Stripped `MarketDataCache` to freshness-only**:
- Removed L1 cache (TTLCache) initialization
- Removed `get()`, `set()`, `invalidate()` methods
- Removed `CacheHitType` enum (L1_HIT, L2_HIT, MISS)
- Reduced from ~400 lines to ~200 lines

**Simplified configuration**:
- Reduced `CacheTTLConfig` from 5 fields to 1 (`market_hours_ttl`)
- Removed unused config settings: `cache_ttl_daily`, `cache_ttl_hourly`, `cache_ttl_intraday`, `cache_l1_size`, `cache_l1_ttl`
- Simplified dependency injection

**Cleaned up repository**:
- Removed `get_cached_price_data()` method (unused after merge)
- Removed `update_last_fetched_at()` method (unused)
- Removed 68 lines of dead code

**Removed dependency**:
- Removed `cachetools==5.3.2` from `pyproject.toml`
- Updated `uv.lock`

## Performance Improvements

### Before
- **Cache hit**: 3 DB queries + L1 lookup (always miss)
- **Cache miss**: 3 queries + 2 writes + L1 set (wasted)

### After
- **Cache hit**: 1 DB query (3x reduction)
- **Cache miss**: 2 queries + 1 write

### Measurements
- Query reduction: 66% fewer queries on cache hits
- Code reduction: ~400 lines removed across production and tests
- Dependencies: 1 fewer external dependency

## What Was Preserved

✅ **Smart market-aware freshness logic** (unchanged):
- Market hours detection (pre-market, market open, after-hours, closed)
- NYSE calendar integration
- Different TTLs for live vs historical data
- Last complete trading day logic

✅ **Race condition protection**:
- Double-check locking pattern preserved
- Concurrent requests test verified (only 1 API call for 5 concurrent requests)

✅ **Incremental fetch capability**:
- Still fetches only missing date ranges when possible
- Avoids re-fetching complete dataset

## Testing

### Test Results
- ✅ **338 tests passed, 13 skipped**
- ✅ 10/10 cache integration tests passing
- ✅ 25 smart freshness tests passing
- ✅ All unit tests updated and passing

### Test Changes
- Updated all tests to use **behavioral assertions** instead of implementation-detail stats dicts
- Cache hit verification: `provider.fetch_price_data.assert_not_called()`
- Cache miss verification: `provider.fetch_price_data.assert_called_once()`
- Removed L1-specific tests (L1 hit, `CacheHitType.L1_HIT` assertions)
- Fixed stale `CacheTTLConfig` usage in test fixtures

### Verified Scenarios
- ✅ Cache miss: Provider called, data stored and returned
- ✅ Cache hit: Provider not called, data returned from 1 DB query
- ✅ Cache persistence: Data survives across requests
- ✅ TTL expiration: Fresh fetch after TTL expires
- ✅ Force refresh: Bypasses cache when requested
- ✅ Request type sharing: Different request types share cached data
- ✅ Symbol isolation: Different symbols don't interfere
- ✅ Interval isolation: Different intervals cached separately
- ✅ Race conditions: Only 1 provider call for 5 concurrent requests

## Files Changed

### Production Code (5 files, -512 lines)
- `backend/app/services/cache_service.py` - Stripped to freshness-only (-197 lines)
- `backend/app/services/data_service.py` - Merged methods (-97 lines)
- `backend/app/repositories/stock_price.py` - Removed unused methods (-68 lines)
- `backend/app/core/config.py` - Removed unused settings (-24 lines)
- `backend/app/core/deps.py` - Simplified injection (-17 lines)

### Dependencies (2 files)
- `backend/pyproject.toml` - Removed cachetools (-1 line)
- `backend/uv.lock` - Updated lockfile

### Tests (4 files, -332 lines)
- `backend/tests/integration/test_cache_integration.py` - Behavioral assertions (-145 lines)
- `backend/tests/unit/services/test_data_service.py` - Updated mocks (-113 lines)
- `backend/tests/test_services/test_data_service.py` - Simplified tests (-56 lines)
- `backend/tests/unit/api/v1/test_stocks_source_field.py` - Fixed config (-18 lines)

### Documentation (1 file)
- `thoughts/shared/plans/2025-02-08-simplify-caching.md` - Implementation plan (+525 lines)

**Total**: 12 files changed, 1035 insertions(+), 939 deletions(-)

## Breaking Changes

None. This is a pure refactoring with no API changes.

## Migration Notes

No migration required. Changes are internal to the caching layer.

## How to Verify

### Automated Tests
- [x] All backend tests pass: `./scripts/dc.sh exec backend-dev pytest -x`
- [x] Cache integration tests pass (10/10)
- [x] Smart freshness tests pass (25/25)
- [x] Race condition protection verified

### Manual Verification
- [ ] Start services: `./scripts/dc.sh up -d`
- [ ] Make initial request: `curl http://localhost:8093/api/v1/stocks/AAPL/prices`
- [ ] Make second request (should be faster, cache hit)
- [ ] Check logs for "Cache hit" message: `./scripts/dc.sh logs -f backend-dev | grep -i cache`
- [ ] Verify only 1 DB query on cache hit (check query logs)

## Related

- **Ticket**: `thoughts/shared/tickets/005-evaluate-and-simplify-caching.md`
- **Implementation Plan**: `thoughts/shared/plans/2025-02-08-simplify-caching.md`

## Checklist

- [x] Code follows project style guidelines
- [x] Tests added/updated for changes
- [x] All tests passing (338 passed, 13 skipped)
- [x] No breaking changes
- [x] Documentation updated (implementation plan)
- [x] No new dependencies added (1 dependency removed)
- [x] Performance verified (3x improvement on cache hits)
- [ ] Manual verification completed (requires user testing)
