# Arena Sector Data Backfill Implementation Plan

## Overview

The arena simulation engine's `_load_sector_cache` is read-only from `stock_sectors` — it never calls Yahoo Finance. Symbols not previously fetched via Live20 or the stocks API will always show as "Unknown" in sector breakdowns. This plan adds batch sector pre-population so all arena symbols get real sector data, both for existing simulations (via the detail endpoint) and for future simulation runs (via init).

## Current State Analysis

### Root Cause
`_load_sector_cache` (`simulation_engine.py:661-681`) issues a single `SELECT symbol, sector FROM stock_sectors WHERE symbol IN (...)` query and stores `None` for any symbol not in the table. No Yahoo API calls are ever made during a simulation run or when fetching analytics.

### Key Discoveries
- `DataService.get_sector_etf(symbol, session)` (`data_service.py:182-238`) already handles the full fetch-and-cache flow: DB check → Yahoo API call → upsert into `stock_sectors`
- It's called from only two places: `live20_service.py:122` and `stocks.py:397` (stocks info endpoint)
- The detail endpoint (`arena.py:307-315`) does the same DB-only read as `_load_sector_cache`
- No background jobs or batch prefetch exists for sector data
- `stock_sectors` has a unique index on `symbol`, and `get_sector_etf` uses `ON CONFLICT DO UPDATE` — safe to call concurrently for different symbols
- `DataService` stores `self._session_factory` at init (`data_service.py:109`) — used by `get_price_data` and other methods to create independent sessions for concurrent work
- `SimulationEngine` already has `self.data_service` (`simulation_engine.py:71`), constructed internally from `session_factory`

### What's Missing
A mechanism to call `DataService.get_sector_etf()` for unknown symbols in bulk, with concurrency control to respect Yahoo's rate limits.

## Desired End State

1. Viewing any arena simulation detail (new or existing) should show real sector data for all symbols that have been traded — not "Unknown" for the majority
2. New simulation runs should have sector data pre-loaded before `step_day()` starts (important for sector concentration enforcement in the selector)
3. Sector fetch failures are non-fatal: any symbol that fails stays "Unknown"

## What We're NOT Doing

- Changing `_load_sector_cache` — it stays as a fast DB-only read; the prefetch just ensures the DB has data before that read happens
- Adding scheduled background jobs or Celery tasks
- Changing the `stock_sectors` schema
- Modifying the frontend

---

## Phase 1: Add `DataService.batch_prefetch_sectors()`

### Overview
Add a method to `DataService` that accepts a list of symbols, identifies which are missing from `stock_sectors`, and fetches them concurrently from Yahoo Finance with a semaphore (max 5 concurrent) to avoid rate limiting. Returns a `dict[str, str | None]` mapping symbol → sector name (the Yahoo human-readable name, not the ETF symbol).

### Concurrency Design

**Critical constraint**: SQLAlchemy's `AsyncSession` is not safe for concurrent use across asyncio tasks. Each concurrent `fetch_one` task must use its own independent session via `self._session_factory`, matching the established codebase pattern used by `_load_price_cache` (`simulation_engine.py:654`) and `live20_service.py:124`.

**Pattern**: Each `fetch_one` task opens `async with self._session_factory() as session:` for the Yahoo fetch + DB upsert. After all tasks complete, one bulk SELECT on the caller's session builds the return dict.

### Changes Required

#### 1. `backend/app/services/data_service.py`

**After** the existing `get_sector_etf()` method (line ~238), add:

```python
async def batch_prefetch_sectors(
    self,
    symbols: list[str],
    session: AsyncSession,
    max_concurrency: int = 5,
) -> dict[str, str | None]:
    """Fetch and cache sector data for all symbols missing from stock_sectors.

    Queries DB for existing entries first, then fetches Yahoo data only for
    symbols not yet cached. Each concurrent fetch uses its own DB session
    (AsyncSession is not task-safe for concurrent use).

    Args:
        symbols: Stock symbols to prefetch (will be deduped and uppercased)
        session: Caller's database session (used for initial/final reads only)
        max_concurrency: Max concurrent Yahoo API calls (default 5)

    Returns:
        Dict mapping symbol → sector name (Yahoo human-readable, e.g. "Technology")
        Symbols that fail or have no sector return None.
    """
    if not symbols:
        return {}

    symbols = list({s.upper().strip() for s in symbols})

    # Load what we already have in DB
    result = await session.execute(
        select(StockSector.symbol, StockSector.sector)
        .where(StockSector.symbol.in_(symbols))
    )
    existing = {row.symbol: row.sector for row in result.all()}

    missing = [s for s in symbols if s not in existing]

    if missing:
        self.logger.info(
            f"Prefetching sector data for {len(missing)} symbols "
            f"({len(existing)} already cached)"
        )
        semaphore = asyncio.Semaphore(max_concurrency)

        async def fetch_one(symbol: str) -> tuple[str, bool]:
            """Fetch sector for one symbol using its own session."""
            async with semaphore:
                try:
                    async with self._session_factory() as task_session:
                        await self.get_sector_etf(symbol, task_session)
                        await task_session.commit()
                    return symbol, True
                except Exception as e:
                    self.logger.warning(
                        f"Sector prefetch failed for {symbol}: {e}"
                    )
                    return symbol, False

        await asyncio.gather(*[fetch_one(s) for s in missing])

        # Single bulk read to pick up all newly inserted sectors
        result = await session.execute(
            select(StockSector.symbol, StockSector.sector)
            .where(StockSector.symbol.in_(symbols))
        )
        existing = {row.symbol: row.sector for row in result.all()}

    return {s: existing.get(s) for s in symbols}
```

**Import**: Add `import asyncio` at top of `data_service.py` if not already present.

### Success Criteria

#### Automated Verification
- [ ] Unit test: `batch_prefetch_sectors([])` returns `{}`
- [ ] Unit test: all symbols already in DB → no Yahoo calls made
- [ ] Unit test: mixed hit/miss → Yahoo called only for missing symbols
- [ ] Unit test: Yahoo failure for one symbol → others still return correctly
- [ ] Unit test: each concurrent fetch uses its own session (not the caller's)

#### Manual Verification
- [ ] Call `batch_prefetch_sectors` for known symbols from a Python shell, verify DB is populated

**Implementation Note**: After completing Phase 1 and tests pass, pause for manual confirmation before Phase 2.

---

## Phase 2: Backfill on Detail Endpoint

### Overview
Modify `GET /arena/simulations/{id}` to call `batch_prefetch_sectors()` for symbols missing from `stock_sectors` before building the sector_map. This fixes analytics for ALL existing simulations retroactively.

### Changes Required

#### 1. `backend/app/api/v1/arena.py` — Add `data_service` dependency

The `get_simulation` endpoint (`arena.py:281-284`) currently only injects `session`. Add `data_service` to the signature:

```python
# Before:
async def get_simulation(
    simulation_id: int,
    session: AsyncSession = Depends(get_db_session),
) -> SimulationDetailResponse:

# After:
async def get_simulation(
    simulation_id: int,
    session: AsyncSession = Depends(get_db_session),
    data_service: DataService = Depends(get_data_service),
) -> SimulationDetailResponse:
```

**Note**: `get_data_service` and `DataService` are already imported in `arena.py` (lines 17 and 33).

#### 2. `backend/app/api/v1/arena.py` (lines ~307-315) — Replace sector_map build

```python
# Before (read-only):
sector_map: dict[str, str | None] = {}
if simulation.positions:
    symbols = list({pos.symbol for pos in simulation.positions})
    sector_result = await session.execute(
        select(StockSector.symbol, StockSector.sector)
        .where(StockSector.symbol.in_(symbols))
    )
    sector_map = {row.symbol: row.sector for row in sector_result.all()}
```

```python
# After (prefetch missing, then read):
sector_map: dict[str, str | None] = {}
if simulation.positions:
    symbols = list({pos.symbol for pos in simulation.positions})
    sector_map = await data_service.batch_prefetch_sectors(symbols, session)
```

**Note**: `batch_prefetch_sectors` returns the full `{symbol: sector_name}` dict directly, so the downstream code (`sector_map.get(pos.symbol)`) is unchanged.

### Success Criteria

#### Automated Verification
- [ ] Existing integration test for `GET /simulations/{id}` still passes
- [ ] New test: endpoint returns non-null sectors for symbols that have Yahoo data

#### Manual Verification
- [ ] Open simulation #18 in the UI, reload — sector breakdown shows real sectors instead of mostly "Unknown"
- [ ] First load fetches from Yahoo (check backend logs for "Prefetching sector data...")
- [ ] Second load is instant (all cached in DB)

**Implementation Note**: After completing Phase 2 and manual verification passes, pause before Phase 3.

---

## Phase 3: Prefetch on Simulation Initialization

### Overview
Modify `initialize_simulation()` to call `batch_prefetch_sectors()` after `_load_sector_cache()`. This ensures that for NEW simulation runs, the sector cache is populated with real data before `step_day()` uses it for sector concentration enforcement. `_load_sector_cache` is then re-called (or `_sector_cache` is updated in place) so the in-memory cache reflects the freshly fetched data.

### Changes Required

#### 1. `backend/app/services/arena/simulation_engine.py` (around line 136)

**Dependency**: `self.data_service` is already available — `SimulationEngine.__init__` creates it at line 71: `self.data_service = DataService(session_factory=session_factory)`.

```python
# Before:
await self._load_sector_cache(simulation.id, simulation.symbols)

# After:
# Prefetch any missing sector data from Yahoo Finance (non-blocking on failure)
try:
    sector_name_map = await self.data_service.batch_prefetch_sectors(
        simulation.symbols, self.session
    )
    # Directly populate cache with freshly fetched data
    self._sector_cache[simulation.id] = sector_name_map
    missing_count = sum(1 for v in sector_name_map.values() if v is None)
    if missing_count:
        logger.info(
            f"Simulation {simulation.id}: {missing_count}/{len(simulation.symbols)} "
            f"symbols have no sector data after prefetch"
        )
except Exception as e:
    logger.warning(f"Sector prefetch failed for simulation {simulation.id}: {e}")
    # Fall back to DB-only load
    await self._load_sector_cache(simulation.id, simulation.symbols)
```

### Success Criteria

#### Automated Verification
- [ ] Existing simulation engine tests still pass
- [ ] New test: after `initialize_simulation()`, `_sector_cache` contains non-null sectors for symbols with Yahoo data

#### Manual Verification
- [ ] Start a new simulation run with fresh symbols, verify sector breakdown is populated from the first step
- [ ] Backend logs show "Prefetching sector data for N symbols" during init

---

## Testing Strategy

### Unit Tests

**`tests/unit/services/test_data_service.py`** (or equivalent):
- `test_batch_prefetch_sectors_empty_list`: Returns `{}`
- `test_batch_prefetch_sectors_all_cached`: All symbols in DB → 0 Yahoo calls, returns sector map
- `test_batch_prefetch_sectors_all_missing`: No symbols in DB → Yahoo called for all, DB populated
- `test_batch_prefetch_sectors_mixed`: Some cached, some missing → Yahoo called only for missing
- `test_batch_prefetch_sectors_partial_failure`: One Yahoo call raises, others succeed → partial results, no exception raised
- `test_batch_prefetch_sectors_uses_independent_sessions`: Verify each concurrent fetch creates its own session via `_session_factory`, not the caller's session

### Integration Tests

**`tests/integration/api/test_arena.py`** (or equivalent):
- `test_get_simulation_detail_enriches_sector_data`: Simulation with positions missing from `stock_sectors` → after GET, sectors are populated
- `test_get_simulation_detail_sectors_cached_on_second_call`: Second GET is faster (no Yahoo calls in logs)

### Manual Testing Steps
1. Find a simulation with mostly "Unknown" sectors in the breakdown (e.g., simulation #18)
2. Open the simulation detail page
3. Verify the sector breakdown now shows real sector names and percentages
4. Reload the page — should be instant (no Yahoo calls)
5. Check backend logs confirm "Prefetching sector data" appeared on first load only

## References

- Original context: arena simulation `_load_sector_cache` is DB-only
- `DataService.get_sector_etf`: `backend/app/services/data_service.py:182`
- `_load_sector_cache`: `backend/app/services/arena/simulation_engine.py:661`
- Detail endpoint sector build: `backend/app/api/v1/arena.py:307`
- `stock_sectors` model: `backend/app/models/stock_sector.py`
- Session factory pattern: `backend/app/core/database.py:77-101`

## Review Changelog

**2026-02-22 — Post Gemini review:**
- **CRITICAL fix**: Restructured `batch_prefetch_sectors` to use `self._session_factory()` per concurrent task instead of sharing the caller's `AsyncSession` (SQLAlchemy `AsyncSession` is not task-safe for concurrent use). Single bulk SELECT after gather replaces per-symbol re-reads.
- **IMPORTANT fix**: Explicitly documented that `get_simulation` endpoint needs `data_service: DataService = Depends(get_data_service)` added to its signature (it's not currently injected).
- **IMPORTANT fix**: Eliminated N+1 re-read pattern — one bulk SELECT after all `get_sector_etf` calls complete instead of N individual queries.
- **MINOR**: Confirmed `SimulationEngine.data_service` already exists at `simulation_engine.py:71`.
