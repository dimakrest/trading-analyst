# Improve DB Session Handling - Implementation Plan

## Overview

Refactor `DataService` to use a `session_factory` instead of a long-lived `session`, so that database connections are only held open during actual DB operations — not during external API calls (Yahoo Finance).

## Current State Analysis

### The Problem

When a request hits `DataService.get_price_data()`, a single database session is held open for the **entire flow**:

1. Cache freshness check (DB query) — `cache_service.py:117`
2. **Yahoo Finance API call (network I/O, 1-30+ seconds)** — `data_service.py:288`
3. Store results in DB — `data_service.py:292`
4. Read merged data from DB — `data_service.py:301`

The session is created by FastAPI dependency injection (`deps.py:182`) at request start and remains open until the request completes. During step 2, a database connection from the pool is held idle while waiting for an external network call.

### Why This Matters

- Database connections are a limited resource (`pool_size` + `max_overflow`)
- Yahoo Finance calls can take 1-30+ seconds (network latency, retries)
- Under concurrent load, connection pool can be exhausted
- The system handles **real money** — connection pool exhaustion causes request failures

### Key Discoveries

- **Provider layer is already clean**: `YahooFinanceProvider` (`providers/yahoo.py`) has zero DB dependencies — it's a pure API client
- **Session factory pattern already exists**: `get_session_factory()` in `database.py:77` and used by workers (`live20_worker.py:153`, `arena_worker.py:47`)
- **SQLAlchemy `expire_on_commit=False`** (`database.py:38`): Detached objects retain loaded scalar attributes after session close — safe for our use case
- **5 call sites create DataService**: `deps.py:196`, `live20_service.py:70`, `simulation_engine.py:60`, plus test files

### Affected Callers (Production Code)

| File | Line | Current Pattern |
|------|------|----------------|
| `app/core/deps.py` | 196 | `DataService(session=session, provider=..., cache=..., repository=...)` |
| `app/services/live20_service.py` | 70 | `DataService(session=session)` inside `async with session_factory()` |
| `app/services/arena/simulation_engine.py` | 60 | `DataService(session=session)` |

## Desired End State

- `DataService` accepts a `session_factory` callable instead of a `session` instance
- Each DB operation (cache check, store+read) opens and closes its own short-lived session
- Yahoo Finance API calls happen with **no database session open**
- The session factory pattern is consistent across API endpoints and background workers
- All existing tests pass (updated to use new interface)

### Verification

1. All tests pass: `pytest backend/tests/`
2. Manual test: Hit `/api/v1/stocks/AAPL/prices` — data returns correctly
3. Verify with logging: Session opens/closes are visible around DB ops, not around Yahoo fetch

## What We're NOT Doing

- **Not changing `MarketDataCache` or `StockPriceRepository` interfaces** — they still accept a session in their constructors. DataService creates them on-the-fly within session contexts.
- **Not changing the provider layer** — already clean
- **Not changing session pool configuration** — this is about connection lifecycle, not pool sizing
- **Not refactoring `SimulationEngine`** — it uses the session for many other DB operations beyond DataService. It will pass its existing session wrapped in a factory-like callable.

## Implementation Approach

The core change is in `DataService.__init__()` and `get_price_data()`:

**Before**: DataService receives a session and holds it for the full request lifecycle.
**After**: DataService receives a `session_factory` and creates short-lived sessions for each DB operation phase.

The flow becomes:
```
Session 1: cache check → close
           Yahoo fetch (no session)
Session 2: store data + read merged results → commit → close
```

---

## Phase 1: Refactor DataService

### Overview
Change `DataService` to accept `session_factory` instead of `session`. Create short-lived sessions for each DB operation phase.

### Changes Required:

#### 1. `backend/app/services/data_service.py`

**Change constructor signature**:

Replace current `__init__` (lines 88-120) with:

```python
def __init__(
    self,
    session_factory: Callable[[], AsyncContextManager[AsyncSession]] | None = None,
    provider: MarketDataProviderInterface | None = None,
    config: DataServiceConfig | None = None,
):
    """
    Initialize DataService with dependencies.

    Args:
        session_factory: Callable that returns an async context manager yielding
            a database session. Use async_sessionmaker or a custom factory.
            None for API-only mode (no caching/persistence).
        provider: Market data provider (defaults to Yahoo if None)
        config: Service configuration (uses defaults if None)
    """
    self._session_factory = session_factory
    self.provider = provider or YahooFinanceProvider()
    self.config = config or DataServiceConfig()
    self.logger = logger
    self._ttl_config = CacheTTLConfig()

    # Semaphore to limit concurrent requests
    self._semaphore = asyncio.Semaphore(self.config.max_concurrent_requests)
```

Remove: `session`, `cache`, `repository` constructor params and instance variables.
Remove: `_create_default_cache()` method.

**Update `_require_repository` → `_require_session_factory`**:

```python
def _require_session_factory(self) -> None:
    """Ensure session_factory is available for database operations.

    Raises:
        RuntimeError: If session_factory was not provided during initialization
    """
    if self._session_factory is None:
        raise RuntimeError(
            "Session factory required for this operation. "
            "Initialize DataService with a session_factory to use persistence features."
        )
```

**Refactor `get_price_data`** (lines 180-307):

The key change is splitting DB operations into short-lived session contexts:

```python
async def get_price_data(
    self,
    symbol: str,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    interval: str = "1d",
    force_refresh: bool = False,
) -> list[PriceDataPoint]:
    """Get price data with cache-first logic.

    Sessions are opened only for DB operations and closed before external API calls.
    """
    self._require_session_factory()

    # Normalize inputs
    symbol = symbol.upper().strip()
    if end_date is None:
        end_date = datetime.now(timezone.utc)
    if start_date is None:
        start_date = end_date - timedelta(days=get_settings().default_history_days)

    cache_key = f"{symbol}:{interval}:{start_date.date()}:{end_date.date()}"

    # --- Phase 1: Cache check (short-lived session) ---
    fetch_start = start_date
    if not force_refresh:
        async with self._session_factory() as session:
            repo = StockPriceRepository(session)
            cache = MarketDataCache(repo, self._ttl_config)
            freshness = await cache.check_freshness_smart(
                symbol=symbol,
                start_date=start_date,
                end_date=end_date,
                interval=interval,
            )
        # Session closed here — objects detached but scalar attrs accessible

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

    # --- Phase 2: Lock + double-check + fetch + store ---
    fetch_lock = await self._get_fetch_lock(cache_key)
    async with fetch_lock:
        # Double-check after lock (short-lived session)
        if not force_refresh:
            async with self._session_factory() as session:
                repo = StockPriceRepository(session)
                cache = MarketDataCache(repo, self._ttl_config)
                freshness = await cache.check_freshness_smart(
                    symbol=symbol,
                    start_date=start_date,
                    end_date=end_date,
                    interval=interval,
                )
            # Session closed here

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

        # --- Yahoo fetch (NO session open!) ---
        request = PriceDataRequest(
            symbol=symbol,
            start_date=fetch_start,
            end_date=end_date,
            interval=interval,
        )
        price_points = await self.provider.fetch_price_data(request)

        # --- Phase 3: Store + read (short-lived session) ---
        price_dicts = [self._point_to_dict(point, interval) for point in price_points]
        async with self._session_factory() as session:
            repo = StockPriceRepository(session)
            await repo.sync_price_data(
                symbol=symbol,
                new_data=price_dicts,
                interval=interval,
            )
            await session.commit()

            self.logger.info(f"Fetched and stored {len(price_points)} points for {symbol}")

            # Read full merged range from DB (includes both old + new data)
            price_records = await repo.get_price_data_by_date_range(
                symbol=symbol,
                start_date=start_date,
                end_date=end_date,
                interval=interval,
            )
            result = [self._record_to_point(r) for r in price_records]
        # Session closed here

    return result
```

**Update imports** at top of file:

Add:
```python
from collections.abc import Callable
from contextlib import asynccontextmanager
from typing import Any, AsyncContextManager
```

Remove:
```python
from sqlalchemy.ext.asyncio import AsyncSession
```

(AsyncSession is no longer directly used in DataService — it's hidden behind the factory.)

### Success Criteria:

#### Automated Verification:
- [x] `DataService` no longer holds `self.session`
- [x] `get_price_data()` opens/closes sessions around DB operations only
- [x] Yahoo fetch happens with no session open

**Implementation Note**: After completing this phase, proceed to Phase 2 before running tests (callers need updating first).

---

## Phase 2: Update Dependency Injection

### Overview
Update `get_data_service` in `deps.py` to pass `session_factory` instead of `session`.

### Changes Required:

#### 1. `backend/app/core/deps.py`

**Replace `get_data_service`** (lines 181-201):

```python
async def get_data_service(
    session_factory: async_sessionmaker[AsyncSession] = Depends(get_session_factory),
    provider: MarketDataProviderInterface = Depends(get_market_data_provider),
) -> DataService:
    """Get DataService with injected dependencies.

    Dependencies:
    - session_factory: Factory for creating short-lived database sessions
    - provider: Market data provider (Yahoo, Mock, etc.)

    Sessions are created internally by DataService for each DB operation,
    ensuring connections are not held during external API calls.
    """
    return DataService(
        session_factory=session_factory,
        provider=provider,
    )
```

This is simpler than before — no manual repository/cache creation in the dependency.

**Remove unused imports** (if no longer needed elsewhere in file):
- Remove `StockPriceRepository` import (line 25) if unused
- Remove `CacheTTLConfig, MarketDataCache` import (line 26) if unused
- Keep `get_db_session` import — still used by `DatabaseSession` type alias and `get_database_session`

**Add import** (if not already present):
```python
from sqlalchemy.ext.asyncio import async_sessionmaker
```

Add import for `get_session_factory`:
```python
from app.core.database import get_db_session, get_session_factory
```

### Success Criteria:

#### Automated Verification:
- [x] `get_data_service` injects `session_factory` via `Depends(get_session_factory)`
- [x] No more manual repository/cache creation in dependency
- [x] All API endpoints using `Depends(get_data_service)` automatically get the new behavior

---

## Phase 3: Update All Callers

### Overview
Update `Live20Service` and `SimulationEngine` to use the new `DataService(session_factory=...)` pattern.

### Changes Required:

#### 1. `backend/app/services/live20_service.py`

**Update `_analyze_symbol`** (lines 57-onwards):

The session was previously created at the top of the method and used for both DataService and saving the recommendation. Now DataService manages its own sessions, and we create a separate short-lived session for saving the recommendation.

```python
async def _analyze_symbol(self, symbol: str, pricing_config: PricingConfig) -> Live20Result:
    """Analyze a single symbol and save result."""
    try:
        # Validate symbol
        if not symbol or len(symbol) > 10:
            return Live20Result(
                symbol=symbol,
                status="error",
                error_message=f"Invalid symbol: {symbol}",
            )

        # DataService manages its own sessions internally
        data_service = DataService(session_factory=self.session_factory)

        # Fetch price data (60 days for MA20 + buffer)
        # Session opened/closed internally by DataService
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=60)

        price_records = await data_service.get_price_data(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            interval="1d",
        )

        if not price_records or len(price_records) < 25:
            return Live20Result(
                symbol=symbol,
                status="error",
                error_message=f"Insufficient data ({len(price_records) if price_records else 0} records)",
            )

        # ... existing analysis logic (unchanged) ...

        # Save recommendation in its own short-lived session
        async with self.session_factory() as session:
            session.add(recommendation)
            await session.commit()
            await session.refresh(recommendation)

        return Live20Result(
            symbol=symbol,
            status="success",
            recommendation=recommendation,
        )
    except Exception as e:
        # ... existing error handling ...
```

The key change: remove the outer `async with self.session_factory() as session:` that wrapped the entire method. Instead, DataService manages its own sessions, and the recommendation save gets its own session.

#### 2. `backend/app/services/arena/simulation_engine.py`

**Update `__init__`** (lines 53-60):

`SimulationEngine` already has a session for its own DB operations (loading simulations, managing positions, etc.). It needs to pass a session factory to DataService rather than the session directly.

The simplest approach: accept a `session_factory` alongside the session, or create a factory-like wrapper.

Since `ArenaWorker` already has `self.session_factory` (`arena_worker.py:47` uses it), we can pass it through to `SimulationEngine`:

**Option: Pass `session_factory` to SimulationEngine**:

```python
class SimulationEngine:
    def __init__(
        self,
        session: AsyncSession,
        session_factory: async_sessionmaker[AsyncSession] | None = None,
    ) -> None:
        self.session = session
        self.data_service = DataService(session_factory=session_factory)
```

**Update `ArenaWorker.process_job`** to pass session_factory:

```python
# In arena_worker.py, line 47-48:
async with self.session_factory() as session:
    engine = SimulationEngine(session, session_factory=self.session_factory)
```

### Success Criteria:

#### Automated Verification:
- [x] `Live20Service._analyze_symbol` no longer wraps entire method in session context
- [x] `SimulationEngine` passes session_factory to DataService
- [x] No caller passes `session=` to DataService anymore

#### Manual Verification:
- [ ] Live20 analysis completes successfully
- [ ] Arena simulation completes successfully

**Implementation Note**: After completing this phase and all automated verification passes, pause for manual confirmation before proceeding to Phase 4.

---

## Phase 4: Update Tests

### Overview
Update all test files that create `DataService` instances to use the new `session_factory` parameter.

### Changes Required:

#### Test Files to Update:

1. **`backend/tests/unit/services/test_data_service.py`** (line 86)
2. **`backend/tests/test_services/test_data_service.py`** (lines 114, 125, 142, 363, 381, 435, 500, 560, 586)
3. **`backend/tests/integration/test_cache_integration.py`** (line 65)
4. **`backend/tests/unit/api/v1/test_stocks_source_field.py`** (line 102)

#### General Pattern for Unit Tests (mock-based):

**Before**:
```python
service = DataService(
    session=mock_session,
    provider=mock_provider,
    cache=mock_cache,
    repository=mock_repository,
)
```

**After**:
```python
# Create a mock session factory that returns a mock session context
mock_session_factory = AsyncMock()
mock_session_context = AsyncMock()
mock_session_context.__aenter__ = AsyncMock(return_value=mock_session)
mock_session_context.__aexit__ = AsyncMock(return_value=False)
mock_session_factory.return_value = mock_session_context

service = DataService(
    session_factory=mock_session_factory,
    provider=mock_provider,
)
```

Since `DataService` now creates `StockPriceRepository` and `MarketDataCache` internally, unit tests need to mock at a different level. Two approaches:

**Approach A** (Recommended): Patch `StockPriceRepository` and `MarketDataCache` classes:
```python
@patch("app.services.data_service.MarketDataCache")
@patch("app.services.data_service.StockPriceRepository")
async def test_cache_hit(self, MockRepo, MockCache, ...):
    MockCache.return_value.check_freshness_smart = AsyncMock(return_value=freshness)
    ...
```

**Approach B**: Use a real `async_sessionmaker` with a mock session for integration-like tests.

The exact approach depends on what each test is verifying. Cache behavior tests should use Approach A (patch). Integration tests should use the real session factory from the `db_session` fixture.

#### Integration Tests (`test_cache_integration.py`):

The integration test fixture creates `DataService` with a real session. It needs to wrap the `db_session` in a factory:

```python
@pytest_asyncio.fixture
async def data_service(
    test_session_factory,  # Already exists in conftest.py
    mock_provider: MockMarketDataProvider,
):
    """Create data service with session factory."""
    return DataService(
        session_factory=test_session_factory,
        provider=mock_provider,
    )
```

Note: The `test_session_factory` fixture already exists at `conftest.py:124`.

#### API-only mode tests:

Tests that use `DataService(session=None, ...)` become:
```python
service = DataService(session_factory=None, provider=mock_provider, config=config)
```

### Success Criteria:

#### Automated Verification:
- [x] All unit tests pass: `pytest backend/tests/unit/ -v`
- [x] All service tests pass: `pytest backend/tests/test_services/ -v`
- [x] All integration tests pass: `pytest backend/tests/integration/ -v`
- [x] Full test suite passes: `pytest backend/tests/` (1225 passed, 19 skipped)

#### Manual Verification:
- [ ] Start the app: `./scripts/dc.sh up -d`
- [ ] Hit `GET /api/v1/stocks/AAPL/prices` — returns valid data
- [ ] Hit `GET /api/v1/indicators/AAPL/sma` — returns valid data
- [ ] Run a Live20 analysis — completes successfully

---

## Testing Strategy

### Unit Tests:
- Cache hit returns data without opening session for Yahoo fetch
- Cache miss opens session for check, closes, fetches Yahoo, opens session for store+read
- Force refresh skips cache check session entirely
- Double-check after lock uses its own session
- API-only mode (session_factory=None) raises RuntimeError on get_price_data

### Integration Tests:
- Full flow with real DB: cache miss → Yahoo (mock) → store → read
- Concurrent requests for same symbol don't duplicate API calls
- Session not held during mock provider delay (can verify with logging)

### Regression:
- All existing test scenarios must continue to pass with updated fixtures

## Risk Assessment

### Low Risk:
- **Detached objects**: SQLAlchemy `expire_on_commit=False` ensures loaded scalar attributes remain accessible after session close. All our access patterns use scalar columns only (no lazy relationships).
- **Lock correctness**: The asyncio.Lock is held across session boundaries, which is correct — it prevents duplicate Yahoo fetches regardless of session lifecycle.

### Medium Risk:
- **Transaction boundaries**: Store + read now happen in their own transaction. Previously they shared the request-level transaction. Since `sync_price_data` uses UPSERT (atomic), and the read follows the commit, this is safe.
- **Test refactoring**: Many tests mock `session`, `cache`, and `repository` directly on `DataService`. These need to be reworked to patch at the class level or use factory mocks.

## References

- Original ticket: `thoughts/shared/tickets/004-improve-db-session-handling.md`
- GitHub Issue: [#4](https://github.com/dimakrest/trading-analyst/issues/4)
- Related: Cache simplification PR (#9) — recently merged, simplified the cache layer we're modifying
