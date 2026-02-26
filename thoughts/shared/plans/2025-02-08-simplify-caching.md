# Simplify Caching System - Implementation Plan

## Overview

Remove dead code, eliminate redundant DB queries, and simplify the caching system while preserving the valuable market-aware freshness logic. The core insight: **L1 cache is dead code** (recreated per-request), **cache hits trigger 3 identical DB queries** when only 1 is needed, and **`fetch_and_store_data()` exists only to be called by `get_price_data()`** — the split itself is the root cause of the redundancy.

## Current State Analysis

### Architecture
- **L1 (in-memory)**: `cachetools.TTLCache` in `MarketDataCache` — **dead code** (new instance per FastAPI request via `deps.py:206`, always starts empty)
- **L2 (database)**: PostgreSQL `stock_prices` table with `last_fetched_at` TTL validation
- **Smart freshness**: Market-hours-aware logic in `check_freshness_smart()` — **valuable, keep**
- **Function caching**: `@lru_cache` for settings and NYSE calendar — **appropriate, no changes**

### DB Query Redundancy (Cache Hit Path)

Current flow for `get_price_data()` on a **cache hit** — **3 identical DB queries**:

| Step | Method | DB Query | Data Used? |
|------|--------|----------|------------|
| 1 | `check_freshness_smart()` (line 265) | `get_price_data_by_date_range()` | Discarded |
| 2 | `cache.get()` → `get_cached_price_data()` (line 130) | `get_price_data_by_date_range()` | Discarded |
| 3 | `get_price_data()` (line 242) | `get_price_data_by_date_range()` | **Used** |

After simplification: **1 DB query** (data from freshness check returned directly).

### DB Write Redundancy (Cache Miss Path)

| Step | Method | Redundant? |
|------|--------|------------|
| 1 | `sync_price_data()` — sets `last_fetched_at` on upserted rows (line 696) | No |
| 2 | `cache.set()` → `update_last_fetched_at()` — updates ALL rows in range (line 172) | **Yes** — `sync_price_data()` already set it |

### Method Split Problem

`fetch_and_store_data()` has **exactly 1 production caller**: `get_price_data()` at line 233, which **discards the return value**. All other callers (56 occurrences) are tests asserting on implementation-detail stats dicts (`cache_hit`, `hit_type`, `inserted`, `updated`).

The split creates the redundancy: `fetch_and_store_data()` checks freshness and queries DB, then `get_price_data()` queries DB again because it threw away everything.

### Dead Code Inventory

| Code | Location | Why Dead |
|------|----------|----------|
| `TTLCache` L1 | `cache_service.py:72-76` | New instance per request, always empty |
| `cache.get()` | `cache_service.py:105-150` | L1 always misses, then re-queries DB redundantly |
| `cache.set()` | `cache_service.py:152-179` | L1 write wasted, `update_last_fetched_at` redundant |
| `cache.invalidate()` | `cache_service.py:181-203` | 0 production callers |
| `_get_l1_key()` | `cache_service.py:83-91` | Only for L1 |
| `_get_ttl_for_interval()` | `cache_service.py:93-103` | Only used by `get()` |
| `_record_to_point()` | `cache_service.py:406-416` | Only used by `get()` |
| `get_cached_price_data()` | `stock_price.py:892-928` | Only called by `cache.get()` |
| `update_last_fetched_at()` | `stock_price.py:930-957` | Only called by `cache.set()`, redundant with `sync_price_data()` |
| `CacheHitType` enum | `cache_service.py:21-25` | Only used by `cache.get()` return values |
| `fetch_and_store_data()` | `data_service.py:263-436` | Only production caller is `get_price_data()`, which discards return value |
| `cache_ttl_daily` | `config.py:98-101` | Only feeds `_get_ttl_for_interval()` |
| `cache_ttl_hourly` | `config.py:102-105` | Same |
| `cache_ttl_intraday` | `config.py:106-109` | Same |
| `cache_l1_size` | `config.py:112-115` | L1 removed |
| `cache_l1_ttl` | `config.py:116-119` | L1 removed |
| `cachetools` dependency | `pyproject.toml:47` | L1 removed |

### Key Discoveries

- `cache.invalidate()` has **zero production callers** (`cache_service.py:181`) — only used in one test
- `check_freshness_smart()` already queries `get_price_data_by_date_range()` at line 265 but **discards the data** — it only uses it to check coverage dates
- `sync_price_data()` already sets `last_fetched_at` at line 696, making `update_last_fetched_at()` fully redundant
- `CacheTTLConfig` has 6 fields but only `market_hours_ttl` (300s) is actually used by the smart freshness logic
- `fetch_and_store_data()` return value (stats dict) is **never used** by `get_price_data()` (line 233 discards it)
- `fetch_and_store_data()` has **0 production callers** beyond `get_price_data()` — all 56 other callsites are tests

## Desired End State

- **Cache hit**: 1 DB query (down from 3)
- **Cache miss**: 2 DB queries + 1 write + 1 API call (down from 3 queries + 2 writes)
- **Single method** `get_price_data()` — no more `fetch_and_store_data()` indirection
- **~280 lines of dead code removed** across cache_service.py, stock_price.py, config.py, deps.py, data_service.py
- **1 dependency removed** (`cachetools`)
- **Smart freshness logic preserved** intact — no changes to market-awareness
- **Race condition protection preserved** — double-check locking pattern stays

## What We're NOT Doing

- Not changing the smart freshness logic (`check_freshness_smart()` business rules stay identical)
- Not changing the race condition protection (double-check locking stays)
- Not changing the `@lru_cache` usage for settings and NYSE calendar
- Not renaming `cache_service.py` — keep the file name to minimize diff churn (can do later)
- Not changing the database schema (`last_fetched_at` column stays, still set by `sync_price_data`)
- Not changing any API endpoint signatures

---

## Phase 1: Merge Methods and Eliminate Query Redundancy

### Overview
Merge `fetch_and_store_data()` into `get_price_data()`, add `cached_records` to `FreshnessResult` so the freshness check data is used directly, and remove `cache.get()` / `cache.set()` calls. Update affected tests in this phase.

### Changes Required:

#### 1. Add `cached_records` field to `FreshnessResult`
**File**: `backend/app/services/cache_service.py`
**Changes**: Add properly typed field to carry the data already loaded by the freshness check

```python
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.stock import StockPrice

@dataclass
class FreshnessResult:
    """Result of freshness check with market-aware logic."""
    is_fresh: bool
    reason: str
    market_status: str
    recommended_ttl: int
    last_data_date: date | None
    last_complete_trading_day: date
    needs_fetch: bool
    fetch_start_date: date | None
    cached_records: list[StockPrice] | None = None  # Records from freshness check DB query
```

#### 2. Populate `cached_records` in `check_freshness_smart()`
**File**: `backend/app/services/cache_service.py`
**Changes**: Pass `price_records` through in all `FreshnessResult` returns where `is_fresh=True`. The data is already loaded at line 265 — we just stop discarding it.

There are exactly **3** `is_fresh=True` return sites. Add `cached_records=price_records` to each:

| Line | Context | Change |
|------|---------|--------|
| 310 | Historical data covers requested range | Add `cached_records=price_records` |
| 356 | Market open, data fresh within 5-minute TTL | Add `cached_records=price_records` |
| 382 | Pre/after/closed, covers last complete trading day | Add `cached_records=price_records` |

All `is_fresh=False` returns keep the default `cached_records=None` (no change needed).

#### 3. Merge `fetch_and_store_data()` into `get_price_data()`
**File**: `backend/app/services/data_service.py`
**Changes**:
- Inline the cache check + provider fetch + DB store logic directly into `get_price_data()`
- On cache hit: convert `freshness.cached_records` directly to `PriceDataPoint` list and return (1 DB query)
- On cache miss: fetch from provider, store in DB, then read full range from DB for merged result (2 queries + 1 write)
- Remove `cache.get()` calls (lines 327-331, 373-378)
- Remove `cache.set()` call (lines 420-427)
- Delete `fetch_and_store_data()` method entirely
- Use `is not None` checks for `cached_records` (not truthiness — avoids silent empty-list edge case)

```python
async def get_price_data(
    self,
    symbol: str,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    interval: str = "1d",
    force_refresh: bool = False,
) -> list[PriceDataPoint]:
    """
    Get price data with cache-first logic.

    Flow:
    1. Check freshness (market-aware) — returns cached data if fresh
    2. If stale: acquire lock, double-check, fetch from provider, store in DB
    3. Read full merged range from DB after store

    Race condition protection:
    - Per-cache-key locks prevent duplicate provider fetches
    - Double-check after lock acquisition catches concurrent populates
    """
    self._require_repository()

    # Normalize inputs
    symbol = symbol.upper().strip()
    if end_date is None:
        end_date = datetime.now(timezone.utc)
    if start_date is None:
        start_date = end_date - timedelta(days=get_settings().default_history_days)

    cache_key = f"{symbol}:{interval}:{start_date.date()}:{end_date.date()}"

    # Smart cache check (no lock needed)
    fetch_start = start_date
    if not force_refresh and self.cache:
        freshness = await self.cache.check_freshness_smart(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            interval=interval,
        )

        if freshness.is_fresh and freshness.cached_records is not None:
            self.logger.debug(
                f"Cache hit for {symbol}: {freshness.reason} "
                f"(market: {freshness.market_status})"
            )
            return [self._record_to_point(r) for r in freshness.cached_records]

        # Use incremental start date if available
        if freshness.fetch_start_date and freshness.fetch_start_date > start_date.date():
            fetch_start = datetime.combine(
                freshness.fetch_start_date,
                datetime.min.time(),
                tzinfo=timezone.utc,
            )
            self.logger.debug(
                f"Incremental fetch for {symbol}: {freshness.fetch_start_date} to {end_date.date()}"
            )

    # Cache miss — acquire lock for this cache key
    fetch_lock = await self._get_fetch_lock(cache_key)
    async with fetch_lock:
        # Double-check after lock (race condition protection)
        if not force_refresh and self.cache:
            freshness = await self.cache.check_freshness_smart(
                symbol=symbol,
                start_date=start_date,
                end_date=end_date,
                interval=interval,
            )

            if freshness.is_fresh and freshness.cached_records is not None:
                self.logger.debug(
                    f"Cache hit after lock for {symbol}: {freshness.reason} "
                    f"(market: {freshness.market_status})"
                )
                return [self._record_to_point(r) for r in freshness.cached_records]

            # Update fetch_start in case it changed
            if freshness.fetch_start_date and freshness.fetch_start_date > start_date.date():
                fetch_start = datetime.combine(
                    freshness.fetch_start_date,
                    datetime.min.time(),
                    tzinfo=timezone.utc,
                )

        # Fetch from provider
        request = PriceDataRequest(
            symbol=symbol,
            start_date=fetch_start,
            end_date=end_date,
            interval=interval,
        )
        price_points = await self.provider.fetch_price_data(request)

        # Store in database (sync_price_data already sets last_fetched_at)
        price_dicts = [self._point_to_dict(point, interval) for point in price_points]
        await self.repository.sync_price_data(
            symbol=symbol,
            new_data=price_dicts,
            interval=interval,
        )

        self.logger.info(f"Fetched and stored {len(price_points)} points for {symbol}")

    # Read full merged range from DB (includes both old + new data)
    price_records = await self.repository.get_price_data_by_date_range(
        symbol=symbol,
        start_date=start_date,
        end_date=end_date,
        interval=interval,
    )
    return [self._record_to_point(r) for r in price_records]
```

#### 4. Add `_record_to_point()` static method to `DataService`
**File**: `backend/app/services/data_service.py`
**Changes**: Add conversion method and replace the inline conversion at lines 250-261

```python
@staticmethod
def _record_to_point(record: StockPrice) -> PriceDataPoint:
    """Convert StockPrice DB record to PriceDataPoint."""
    return PriceDataPoint(
        symbol=record.symbol,
        timestamp=record.timestamp,
        open_price=record.open_price,
        high_price=record.high_price,
        low_price=record.low_price,
        close_price=record.close_price,
        volume=record.volume,
    )
```

#### 5. Update docstrings
**File**: `backend/app/services/data_service.py`
**Changes**:
- Module docstring (lines 1-12): Remove "Two-level caching (L1 in-memory + L2 database)" references
- Class docstring (lines 50-62): Remove "two-level caching" and `fetch_and_store_data()` references

**File**: `backend/app/services/cache_service.py`
**Changes**:
- `MarketDataCache` class docstring (lines 53-62): Rewrite from "Two-level cache" to "Market-aware freshness checker"

#### 6. Update tests for merged method
**Files**:
- `backend/tests/unit/services/test_data_service.py`
- `backend/tests/test_services/test_data_service.py`
- `backend/tests/unit/api/v1/test_stocks_source_field.py`

**Changes**:
- Replace all `fetch_and_store_data()` calls with `get_price_data()` calls
- Replace stats dict assertions (`result["cache_hit"]`, `result["hit_type"]`, `result["inserted"]`) with **behavioral assertions**:
  - Cache hit: assert `provider.fetch_price_data` was NOT called
  - Cache miss: assert `provider.fetch_price_data` WAS called
  - Data correctness: assert returned `list[PriceDataPoint]` contains expected data
- Update mocks: `check_freshness_smart` returns `FreshnessResult` with `cached_records` field populated
- Remove mocks for `cache.get()` and `cache.set()` — these methods no longer exist
- Remove `CacheHitType` imports
- **Preserve error-handling tests** (these call `fetch_and_store_data()` and must be migrated to `get_price_data()`):
  - `test_provider_api_error` (test_data_service.py:423)
  - `test_repository_error_handling` (test_data_service.py:451)
  - `test_persistence_without_session_fails` (test_data_service.py:338)
- **Add empty provider response test**: verify that when `provider.fetch_price_data()` returns `[]`, `get_price_data()` stores nothing and returns whatever was already in DB (possibly `[]`)

**File**: `backend/tests/unit/api/v1/test_stocks_source_field.py` (specific mock strategy)

This file currently mocks `data_service.fetch_and_store_data` directly (line 98) to bypass the entire data flow. After the merge, the mock strategy changes fundamentally:
- **Remove**: `data_service.fetch_and_store_data = AsyncMock(return_value={...})` (line 98-105)
- **Replace with**: Mock `cache.check_freshness_smart` to return a `FreshnessResult(is_fresh=True, cached_records=[mock_records...])` so `get_price_data()` returns data without hitting the provider or DB
- The mock records should be `MagicMock(spec=StockPrice)` objects with the expected field values so `_record_to_point()` can convert them to `PriceDataPoint`

**File**: `backend/tests/integration/test_cache_integration.py`

**Changes**:
- Replace all `fetch_and_store_data()` calls with `get_price_data()` calls
- Replace stats dict assertions with behavioral assertions (provider call counts, returned data shape)
- Remove L1-specific tests (L1 hit, `CacheHitType.L1_HIT` assertions)
- Remove `cache.invalidate()` test (method will be removed in Phase 2)
- Concurrent request test (Test 11): verify only 1 `provider.fetch_price_data` call happened across 5 concurrent `get_price_data()` calls

**File**: `backend/tests/unit/test_cache_freshness.py` and `backend/tests/integration/test_smart_cache_freshness.py`

**Changes**: Add assertions that `cached_records` is populated when `is_fresh=True`

### Success Criteria:

#### Automated Verification:
- [x] All existing tests pass (with updated mocks/assertions)
- [x] Cache hit path: `provider.fetch_price_data` not called, data returned from 1 DB query
- [x] Cache miss path: `provider.fetch_price_data` called once, data stored and returned
- [x] No references to `fetch_and_store_data` in production code
- [x] Concurrent request test: only 1 provider call for 5 concurrent requests

#### Manual Verification:
- [ ] Start services with `./scripts/dc.sh up -d`
- [ ] Fetch price data for a symbol: `curl localhost:8093/api/v1/stocks/AAPL/prices`
- [ ] Fetch same data again — should be fast (cache hit, 1 DB query)
- [ ] Check backend logs confirm "Cache hit" on second request

**Implementation Note**: After completing this phase and all automated verification passes, pause for manual confirmation before proceeding to Phase 2.

---

## Phase 2: Remove Dead Code and Simplify Config

### Overview
Remove all L1 cache code, unused methods, the `cachetools` dependency, unused config fields, and simplify dependency injection. This is safe because Phase 1 already eliminated all callers of this code.

### Changes Required:

#### 1. Strip `MarketDataCache` to freshness-only
**File**: `backend/app/services/cache_service.py`
**Remove**:
- `from cachetools import TTLCache` (line 12)
- `CacheHitType` enum (lines 21-25)
- `__init__`: Remove `TTLCache` creation (lines 72-76), keep `repository` and `ttl_config`
- `_get_l1_key()` method (lines 83-91)
- `_get_ttl_for_interval()` method (lines 93-103)
- `get()` method (lines 105-150)
- `set()` method (lines 152-179)
- `invalidate()` method (lines 181-203)
- `_record_to_point()` method (lines 406-416)

**Keep**:
- `CacheTTLConfig` (simplified — see step 4)
- `FreshnessResult` (with `cached_records` field from Phase 1)
- `check_freshness_smart()` (unchanged business logic)

The `__init__` simplifies to:
```python
def __init__(self, repository: StockPriceRepository, ttl_config: CacheTTLConfig):
    self.repository = repository
    self.ttl_config = ttl_config
```

#### 2. Remove unused repository methods
**File**: `backend/app/repositories/stock_price.py`
**Remove**:
- `get_cached_price_data()` method (lines 892-928) — only caller was `cache.get()`
- `update_last_fetched_at()` method (lines 930-957) — only caller was `cache.set()`
- Comment `# ===== CACHE OPERATIONS =====` (line 890)

#### 3. Remove `cachetools` dependency
**File**: `backend/pyproject.toml`
**Remove**: `"cachetools==5.3.2"` from dependencies

**Run**: `cd backend && uv lock` to update lockfile

#### 4. Simplify `CacheTTLConfig`
**File**: `backend/app/services/cache_service.py`
**Changes**: Reduce to only the field that's actually used

```python
@dataclass
class CacheTTLConfig:
    """TTL configuration for market data freshness checks."""
    market_hours_ttl: int = 300  # 5 minutes during market hours
```

#### 5. Remove unused config settings
**File**: `backend/app/core/config.py`
**Remove** these fields from the `Settings` class:
- `cache_ttl_daily` (lines 98-101)
- `cache_ttl_hourly` (lines 102-105)
- `cache_ttl_intraday` (lines 106-109)
- `cache_l1_size` (lines 112-115)
- `cache_l1_ttl` (lines 116-119)

#### 6. Simplify dependency injection
**File**: `backend/app/core/deps.py`
**Changes**: Simplify `get_data_service()` cache creation

```python
async def get_data_service(
    session: AsyncSession = Depends(get_database_session),
    provider: MarketDataProviderInterface = Depends(get_market_data_provider),
) -> DataService:
    repository = StockPriceRepository(session)
    cache = MarketDataCache(repository, CacheTTLConfig())
    return DataService(
        session=session,
        provider=provider,
        cache=cache,
        repository=repository,
    )
```

#### 7. Simplify `DataService._create_default_cache()`
**File**: `backend/app/services/data_service.py`
**Changes**: Simplify the fallback cache creation

```python
def _create_default_cache(self) -> MarketDataCache:
    """Create cache with default configuration."""
    return MarketDataCache(self.repository, CacheTTLConfig())
```

Remove imports of unused config fields if any.

#### 8. Update tests for removed code
**Changes**:
- Remove any remaining test references to `CacheHitType`, `cache.get`, `cache.set`, `cache.invalidate`, `get_cached_price_data`, `update_last_fetched_at`
- Remove any tests that specifically test L1 cache behavior
- Verify no import errors from removed code

### Success Criteria:

#### Automated Verification:
- [x] All tests pass
- [x] `cachetools` not in `uv.lock`
- [x] No references to `TTLCache`, `CacheHitType`, `get_cached_price_data`, `update_last_fetched_at`, `fetch_and_store_data` in production code
- [x] No references to removed config keys (`cache_ttl_daily`, `cache_ttl_hourly`, `cache_ttl_intraday`, `cache_l1_size`, `cache_l1_ttl`) in production code
- [x] Application starts cleanly with `./scripts/dc.sh up -d`

#### Manual Verification:
- [ ] Full end-to-end test: fetch data, verify cache hit, verify no regressions

**Implementation Note**: After completing this phase and all automated verification passes, pause for manual confirmation.

---

## Testing Strategy

### Unit Tests:
- Freshness logic: All existing `test_cache_freshness.py` tests stay (logic unchanged) + new `cached_records` assertions
- DataService: All tests call `get_price_data()` and verify behavior (provider called/not called, correct data returned)
- Config: Verify removed settings don't cause import errors

### Integration Tests:
- Cache flow: Verify 1 DB query on hit (provider not called), 2 on miss (provider called once)
- Race condition: Verify double-check locking still prevents duplicate API calls — 5 concurrent `get_price_data()` calls produce exactly 1 `provider.fetch_price_data` call
- Incremental fetch: Verify partial-range fetch + DB read merges correctly

### Behavioral Assertion Pattern:
Tests should verify **what happened**, not internal stats:

```python
# BEFORE (testing implementation details):
stats = await data_service.fetch_and_store_data("AAPL", ...)
assert stats["cache_hit"] is True
assert stats["hit_type"] == CacheHitType.L1_HIT

# AFTER (testing behavior):
result = await data_service.get_price_data("AAPL", ...)
assert len(result) > 0
assert all(isinstance(r, PriceDataPoint) for r in result)
mock_provider.fetch_price_data.assert_not_called()  # Cache hit = no provider call
```

### Manual Testing Steps:
1. Start services: `./scripts/dc.sh up -d`
2. Fetch AAPL daily data: `curl http://localhost:8093/api/v1/stocks/AAPL/prices`
3. Fetch again immediately — should see "Cache hit" in logs
4. Wait 5+ minutes during market hours, fetch again — should re-fetch
5. Fetch a different symbol to verify no cross-contamination

## Performance Impact Summary

| Scenario | Before | After | Improvement |
|----------|--------|-------|-------------|
| Cache hit (common) | 3 DB queries | 1 DB query | **3x fewer queries** |
| Cache miss | 3 queries + 2 writes | 2 queries + 1 write | **1 fewer query + 1 fewer write** |
| Race condition hit | 4 DB queries | 2 DB queries | **2x fewer queries** |
| Code lines (cache + data svc) | ~600 lines | ~320 lines | **~280 lines removed** |
| Dependencies | cachetools + stdlib | stdlib only | **1 fewer dependency** |
| Public methods | 2 (`get_price_data` + `fetch_and_store_data`) | 1 (`get_price_data`) | **Simpler API** |

## References

- Original ticket: `thoughts/shared/tickets/005-evaluate-and-simplify-caching.md`
- Cache service: `backend/app/services/cache_service.py`
- Data service: `backend/app/services/data_service.py`
- Repository: `backend/app/repositories/stock_price.py`
- Config: `backend/app/core/config.py`
- Deps: `backend/app/core/deps.py`
