# Stock Price Alerts - Implementation Plan

## Overview

Build a stock monitoring system with two alert types (Fibonacci Retracement and Moving Average Touch), a monitoring dashboard, stock detail views with charts, and browser Web Notifications. The backend service computes state periodically; the frontend renders pre-computed state.

This is a new feature module -- no existing alert infrastructure exists. The Fibonacci swing detection and level computation must be built from scratch. The Moving Average alert can reuse the existing `analyze_ma_distance()` indicator (`backend/app/indicators/ma_analysis.py:42`).

## Current State

**What exists today:**

- **Chart component** (`frontend/src/components/organisms/CandlestickChart/CandlestickChart.tsx:23-31`): TradingView Lightweight Charts v5 with `priceLines` and `markers` props. MA20 line already rendered as `LineSeries` (line 105-112). Supports multiple panes.
- **Chart types** (`frontend/src/types/chart.ts:4-23`): `ChartPriceLine` and `ChartMarker` interfaces -- reusable for Fibonacci levels and swing markers.
- **MA analysis** (`backend/app/indicators/ma_analysis.py:42-117`): `analyze_ma_distance(closes, period, at_threshold_pct)` returns `MAAnalysis` with `price_position` (ABOVE/BELOW/AT), `distance_pct`, `ma_slope`, `ma_value`. Supports any period.
- **SMA utility** (`backend/app/indicators/technical.py`): `simple_moving_average(prices, period)` -- numpy-based.
- **Data service** (`backend/app/services/data_service.py:308`): `get_price_data(symbol, start_date, end_date, interval)` with cache-first logic. Constructor: `DataService(session_factory, provider)` -- `session_factory` is an `async_sessionmaker`, `provider` is a `MarketDataProviderInterface`.
- **Background workers** (`backend/app/main.py:134-205`): `asyncio.create_task()` pattern in `lifespan()` for long-running workers. Workers use `JobWorker` base class, but the alert monitor needs a simpler periodic loop (not a job queue worker).
- **Toast notifications** (`frontend/src/components/ui/sonner.tsx`, mounted at `frontend/src/App.tsx:59`): Sonner toast library for in-app notifications.
- **Routing** (`frontend/src/App.tsx:42-52`): React Router with 9 existing routes.
- **Navigation** (`frontend/src/components/layouts/navigationConfig.ts:17-43`): `NAV_ITEMS` array with 5 items. First 3 go to mobile bottom tabs; rest go to "More" sheet.
- **Table pattern** (`frontend/src/components/organisms/CandlestickChart/` and `StockListsTable.tsx`): shadcn Table components with loading skeleton, error state, empty state.
- **Badge component** (`frontend/src/components/ui/badge.tsx`): cva-based with variants. Custom colors applied via className.
- **API client** (`frontend/src/lib/apiClient.ts`): Shared axios instance at `baseURL: '/api'`.
- **DB base model** (`backend/app/models/base.py:15`): `Base` class with `id`, `created_at`, `updated_at`, `deleted_at`, `notes`, `soft_delete()`.
- **Schemas** (`backend/app/schemas/base.py:5`): `StrictBaseModel` with `extra="forbid"`.
- **Config** (`backend/app/core/config.py:10`): Pydantic `Settings` class.
- **DI** (`backend/app/core/deps.py:179-195`): `get_data_service` builds `DataService(session_factory=session_factory, provider=provider)`.

**What does NOT exist:**

- No Fibonacci retracement indicator or swing detection logic
- No alert/monitor database tables
- No alert API endpoints
- No alert dashboard or detail view pages
- No Web Notifications integration
- No periodic monitoring service (only job queue workers exist)

## Desired End State

1. **Dashboard page** at `/alerts` showing one row per alert (not per stock). Fibonacci alerts show swing range, retracement depth, next level, and Fibonacci-specific status badges. MA alerts show MA value, distance, and MA-specific status badges. Sortable/filterable by status. Persistent banner when Web Notifications are granted reminding user to keep tab open.

2. **Stock detail view** at `/alerts/:alertId` with candlestick chart showing Fibonacci levels as horizontal price lines, swing high/low as markers, MA lines as `LineSeries` overlays, and an info panel with current state and alert history.

3. **Backend alert monitoring service** running as an `asyncio.Task` in lifespan (not a job queue worker). Periodically fetches price data, computes Fibonacci and MA state, persists computed state, and generates alert events when status transitions occur. Per-alert error isolation ensures one failing alert does not crash the cycle.

4. **Browser Web Notifications** requested on first alert creation, fired on actionable status transitions, with in-app sonner toast as fallback. Guarded against unsupported browsers.

5. **Two alert types** with full lifecycle management:
   - **Fibonacci Retracement**: Automatic swing detection, level calculation, status tracking (no_structure -> rallying -> pullback_started -> retracing -> at_level -> bouncing -> invalidated), auto-re-anchoring.
   - **Moving Average Touch**: Leverages existing `analyze_ma_distance()`, status tracking (above_ma -> approaching -> at_ma -> below_ma).

## What We're NOT Doing

- **Real-time streaming**: The monitor runs on a fixed polling interval (configurable, default 5 minutes). No WebSocket push.
- **Email/SMS notifications**: Only browser Web Notifications and in-app toasts.
- **Intraday alerts**: Uses daily price data only. No intraday bar detection.
- **Complex swing detection algorithms**: Use a simple N-bar lookback algorithm for swing highs/lows. No fractal analysis or ML-based detection.
- **User authentication per alert**: All alerts are shared across the user context (single user ID = 1, per `backend/app/core/deps.py:73-91`).
- **Mobile push notifications**: Out of scope -- browser notifications only.
- **Alert sharing or collaboration**: Not needed for 2-3 user local-first deployment.
- **Manual recomputation endpoint**: No `POST /compute` endpoint in v1 -- it creates a write race with the monitor service and is not in the ticket's success criteria. Can be added later with row-level locking if needed.
- **Service worker for notifications**: No service worker in v1. `pushState` + `popstate` handles in-app navigation on click. Service worker deferred.

## Implementation Phases

### Phase 1: Database Models and Migrations ✅

**Goal**: Create the database schema for alerts and alert events.

**New files:**
- `backend/app/models/alert.py` -- `StockAlert` and `AlertEvent` models
- `backend/alembic/versions/YYYYMMDD_HHMM-<hash>_add_stock_alerts.py` -- migration

**`StockAlert` model fields:**

```
id                  (from Base)
symbol              String(20), not null, indexed
alert_type          String(20), not null  ("fibonacci" or "moving_average")
status              String(30), not null  (fibonacci: no_structure/rallying/pullback_started/retracing/at_level/bouncing/invalidated; ma: above_ma/approaching/at_ma/below_ma)
is_active           Boolean, default True
is_paused           Boolean, default False
config              JSON, not null  (alert-type-specific configuration)
computed_state      JSON, nullable  (pre-computed state for frontend rendering)
last_triggered_at   DateTime, nullable
created_at          (from Base)
updated_at          (from Base)
deleted_at          (from Base)
notes               (from Base)
```

**`config` JSON structure by alert type:**

Fibonacci:
```json
{
  "levels": [38.2, 50.0, 61.8],
  "tolerance_pct": 0.5,
  "min_swing_pct": 10.0
}
```

Moving Average:
```json
{
  "ma_period": 200,
  "tolerance_pct": 0.5,
  "direction": "both"
}
```

**MA row-per-period fan-out:** Per the ticket ("each MA creates a separate alert row"), `MAConfigRequest.ma_periods` is a list but the API fans out: one `POST /alerts/` with `ma_periods: [50, 200]` creates **two** separate `StockAlert` rows, each with a single `ma_period` in its config. The `StockAlert.config` JSON stores a single `ma_period: int` (not a list). The `MAComputedState` stores state for that single period. The API response for creation returns a list of the created alerts. This keeps the DB model simple (one alert = one period = one status) and matches the dashboard's one-row-per-alert design.

**`computed_state` JSON structure by alert type:**

Fibonacci:
```json
{
  "swing_high": 140.0,
  "swing_low": 110.0,
  "swing_high_date": "2026-03-01",
  "swing_low_date": "2026-02-15",
  "trend_direction": "uptrend",
  "current_price": 128.50,
  "retracement_pct": 38.3,
  "fib_levels": {
    "23.6": {"price": 132.92, "status": "triggered", "triggered_at": "..."},
    "38.2": {"price": 128.54, "status": "active"},
    "50.0": {"price": 125.00, "status": "pending"},
    "61.8": {"price": 121.46, "status": "pending"}
  },
  "next_level": {"pct": 50.0, "price": 125.00}
}
```

Moving Average:
```json
{
  "ma_value": 125.50,
  "ma_period": 200,
  "current_price": 128.00,
  "distance_pct": 2.0,
  "ma_slope": "rising"
}
```

**`fib_levels` key format (B4):** The `fib_levels` keys are **string keys** in serialized JSON (e.g., `"23.6"`, `"38.2"`). Python dicts with float keys serialize to string keys in JSON per the JSON spec. Frontend types use `Record<string, FibLevelState>` on this basis. Backend must ensure consistent string key formatting (e.g., always one decimal place: `"23.6"` not `"23.60"`).

**`AlertEvent` model fields:**

```
id                  (from Base)
alert_id            Integer, ForeignKey("stock_alerts.id"), not null, indexed
event_type          String(30), not null  ("level_hit", "invalidated", "re_anchored", "status_change")
previous_status     String(30), nullable
new_status          String(30), not null
price_at_event      Numeric(12, 4), not null  (consistent with ArenaPosition.entry_price pattern)
details             JSON, nullable  (event-specific data: level hit, swing range, etc.)
created_at          (from Base)
```

**`AlertEvent` soft-delete semantics**: `AlertEvent` inherits `Base` which includes `deleted_at`, but events are immutable audit records -- `deleted_at` is never used on events. When a parent `StockAlert` is soft-deleted, its events remain for historical reference. Hard deletion of events only occurs if the parent alert record is hard-deleted (cascading FK).

**Status validation constants** (in `backend/app/models/alert.py` or `backend/app/services/alert_service.py`):

```python
VALID_FIBONACCI_STATUSES = {"no_structure", "rallying", "pullback_started", "retracing", "at_level", "bouncing", "invalidated"}
VALID_MA_STATUSES = {"above_ma", "approaching", "at_ma", "below_ma", "insufficient_data"}
```

Validate status before any DB write in `AlertService` and `AlertMonitorService`.

**Migration indexes:**
- `ix_stock_alerts_symbol` on `stock_alerts.symbol`
- `ix_stock_alerts_alert_type` on `stock_alerts.alert_type`
- `ix_stock_alerts_status` on `stock_alerts.status`
- `ix_stock_alerts_is_active` on `stock_alerts.is_active`
- `ix_alert_events_alert_id` on `alert_events.alert_id`

**Acceptance criteria:**
- `alembic upgrade head` runs without error
- `alembic downgrade -1` reverses cleanly
- Models can be instantiated and saved in tests

### Phase 2: Fibonacci Retracement Indicator ✅

**Goal**: Build the core Fibonacci calculation engine -- swing detection, level computation, and status determination.

**New files:**
- `backend/app/indicators/fibonacci.py` -- Fibonacci indicator module
- `backend/tests/unit/indicators/test_fibonacci.py` -- comprehensive tests

**Functions to implement:**

1. `detect_swing_high(highs: NDArray, lookback: int = 10) -> list[SwingPoint]`
   - Find local maxima where `highs[i]` is the highest value within `lookback` bars on each side
   - Return list of `SwingPoint(index, price, date)` sorted by index

2. `detect_swing_low(lows: NDArray, lookback: int = 10) -> list[SwingPoint]`
   - Find local minima where `lows[i]` is the lowest value within `lookback` bars on each side

3. `find_latest_swing_structure(highs, lows, dates, min_swing_pct: float = 10.0) -> SwingStructure | None`
   - Find the most recent valid swing high and swing low pair
   - Require minimum `min_swing_pct` percentage move between them
   - Determine trend direction: if swing low came before swing high, it's an uptrend (pullback); if swing high came before swing low, it's a downtrend (bounce)
   - Return `SwingStructure(high, low, direction, high_date, low_date)` or None if no valid structure

4. `calculate_fib_levels(swing_high: float, swing_low: float, direction: str) -> dict[float, float]`
   - For uptrend: levels are calculated downward from swing_high toward swing_low
   - For downtrend: levels are calculated upward from swing_low toward swing_high
   - Standard levels: 23.6%, 38.2%, 50.0%, 61.8%, 78.6%
   - **Use Python `Decimal` arithmetic (R18)** to avoid floating-point drift. For $110->$140 uptrend swing, exact values to 2 decimal places: 23.6%=$132.92, 38.2%=$128.54, 50.0%=$125.00, 61.8%=$121.46, 78.6%=$116.42
   - Return `{23.6: 132.92, 38.2: 128.54, ...}`

5. `compute_fibonacci_status(current_price, swing_structure, fib_levels, config, previous_state) -> FibonacciState`
   - Implement the full status state machine from the ticket
   - Handle all transitions: no_structure, rallying, pullback_started, retracing, at_level, bouncing, invalidated
   - **Invalidation boundary**: strict less-than (`current_price < swing_low` for uptrend). Price exactly AT swing_low = NOT invalidated. Daily candles eliminate the need for a cooldown -- a daily close below swing low is a genuine signal.
   - Detect re-anchoring when price makes new swing extreme beyond previous
   - **Timezone**: Daily candle timestamps are Eastern Time dates. Swing detection uses date-only comparisons.
   - Return new computed state with status, triggered levels, retracement depth

**Data types:**

```python
@dataclass
class SwingPoint:
    index: int
    price: float
    date: str

@dataclass
class SwingStructure:
    high: SwingPoint
    low: SwingPoint
    direction: str  # "uptrend" or "downtrend"

@dataclass
class FibonacciState:
    status: str
    swing_structure: SwingStructure | None
    fib_levels: dict[float, dict]  # {level_pct: {price, status, triggered_at}}
    retracement_pct: float | None
    next_level: dict | None  # {pct, price}
    current_price: float
    events: list[dict]  # events generated during this computation
```

**Tests (write FIRST, then implement):**

1. `test_detect_swing_high_basic` -- finds obvious peaks in synthetic data
2. `test_detect_swing_low_basic` -- finds obvious troughs
3. `test_no_swing_detected_flat_data` -- returns empty for flat prices
4. `test_swing_structure_uptrend` -- low-then-high pattern detected correctly
5. `test_swing_structure_downtrend` -- high-then-low pattern detected correctly
6. `test_swing_structure_minimum_move` -- rejects swings below `min_swing_pct`
7. `test_fib_levels_uptrend` -- correct level prices for uptrend (pullback levels)
8. `test_fib_levels_downtrend` -- correct level prices for downtrend (bounce levels)
9. `test_status_no_structure` -- returns no_structure when no valid swing found
10. `test_status_retracing` -- price between 23.6% and 78.6% returns retracing
11. `test_status_at_level` -- price within tolerance of fib level returns at_level and generates event
12. `test_status_at_level_fires_once` -- same level does not fire twice per swing structure
13. `test_status_invalidated_uptrend` -- price below swing low invalidates
14. `test_status_invalidated_downtrend` -- price above swing high invalidates
15. `test_status_bouncing` -- price moves back toward trend from at_level
16. `test_re_anchor_new_swing_high` -- new high beyond previous triggers re-anchor
17. `test_full_lifecycle` -- simulate realistic price sequence through all states
18. `test_status_at_level_boundary_outside` -- price at `level_price * 1.0051` (just outside 0.5% tolerance) must NOT trigger `at_level`
19. `test_status_at_level_boundary_inside` -- price at `level_price * 1.0049` (just inside 0.5% tolerance) MUST trigger `at_level`
20. `test_transition_no_structure_to_rallying_exact_lookback_boundary` -- swing confirmed only after N+lookback bars (R22)
21. `test_transition_at_level_tolerance_boundary_inclusive` -- price at `level * 1.00499` triggers; price at `level * 1.00501` does not (R22)
22. `test_transition_at_level_fires_exactly_once_on_oscillation` -- price crosses level band 5 times, event count = 1 (R22)
23. `test_invalidation_strict_less_than_swing_low` -- `current_price < swing_low` triggers invalidation; `current_price == swing_low` does not (R22)
24. `test_invalidation_price_exactly_at_swing_low_no_trigger` -- explicit test for the equality boundary decision (R22)

**Acceptance criteria:**
- All 24 tests pass
- Swing detection works on real-ish price data (not just synthetic)
- Status state machine matches the transition diagram in the ticket exactly
- Each level fires only once per swing structure
- Tolerance boundary is precise -- off-by-one on price tolerance means missed or false alerts on real money

### Phase 3: Alert Monitoring Service ✅

**Goal**: Build the background service that periodically computes alert state and generates events.

**New files:**
- `backend/app/services/alert_monitor.py` -- `AlertMonitorService` class
- `backend/app/services/alert_service.py` -- `AlertService` for CRUD operations and alert computation
- `backend/app/repositories/alert_repository.py` -- DB access layer
- `backend/tests/unit/services/test_alert_service.py` -- service tests
- `backend/tests/unit/services/test_alert_monitor.py` -- monitor tests

**Files to modify:**
- `backend/app/main.py:134-205` -- add alert monitor startup in `lifespan()`
- `backend/app/core/config.py:10` -- add `alert_monitor_interval` setting

**`AlertMonitorService`:**

```python
class AlertMonitorService:
    def __init__(self, session_factory, provider):
        self._running = False
        self._running_cycle = False  # Concurrent run guard (R17)
        self._session_factory = session_factory
        self._provider = provider  # MarketDataProviderInterface

    async def start(self) -> None:
        self._running = True
        while self._running:
            try:
                await self._run_cycle()
            except Exception:
                logger.exception("Alert monitor cycle failed")
            await asyncio.sleep(settings.alert_monitor_interval)

    async def stop(self) -> None:
        self._running = False

    async def _run_cycle(self) -> None:
        # Concurrent run guard (R17): prevent overlapping cycles
        if self._running_cycle:
            logger.warning("Previous monitor cycle still running, skipping")
            return
        self._running_cycle = True
        try:
            await self._run_cycle_inner()
        finally:
            self._running_cycle = False

    async def _run_cycle_inner(self) -> None:
        # DataService is instantiated per cycle to prevent stale connections (R8).
        # DataService takes session_factory (a factory, not a session) and provider.
        # session_factory is safe to reuse; provider is stateless (YahooFinanceProvider).
        # Pattern from backend/app/core/deps.py:192:
        #   DataService(session_factory=session_factory, provider=provider)
        data_service = DataService(
            session_factory=self._session_factory,
            provider=self._provider,
        )

        async with self._session_factory() as session:
            repo = AlertRepository(session)
            alerts = await repo.list_active_unpaused()

        # Group by symbol to share price data fetches
        alerts_by_symbol = defaultdict(list)
        for alert in alerts:
            alerts_by_symbol[alert.symbol].append(alert)

        # Batch size limit (R20): process up to batch_size unique symbols per cycle
        # to avoid thundering herd on data provider after first startup with many alerts.
        symbols_to_process = list(alerts_by_symbol.keys())[:settings.alert_monitor_batch_size]

        # Fetch price data sequentially per symbol to respect Yahoo rate limits (O2).
        # DataService has internal caching, so multiple alerts for the same symbol
        # in the same cycle share the cache hit.
        for symbol in symbols_to_process:
            symbol_alerts = alerts_by_symbol[symbol]
            try:
                # Date range: start_date=None, end_date=None uses DataService defaults:
                # end_date = now, start_date = end_date - default_history_days (365).
                # 365 days provides sufficient history for:
                # - Swing detection: needs lookback*2+1 bars minimum (~21 bars)
                # - MA200: needs 205+ bars
                # - MA150: needs 155+ bars
                # See data_service.py:353-354 for default behavior.
                price_data = await data_service.get_price_data(
                    symbol, interval="1d"
                )
            except Exception:
                logger.exception(f"Failed to fetch price data for {symbol}, skipping")
                continue

            # Per-alert error isolation (R1) with per-alert DB session (R21):
            # Each alert gets its own session/transaction. A rollback on one alert
            # does not poison the session state for subsequent alerts.
            for alert in symbol_alerts:
                try:
                    new_state = await self._compute_alert_state(alert, price_data)
                    async with self._session_factory() as session:
                        repo = AlertRepository(session)
                        await repo.update_state(alert.id, new_state)
                        # Create AlertEvent records for status transitions.
                        # MA deduplication (R19): notification fires only on transition
                        # TO actionable state, not when staying in it. AlertEvent is
                        # the deduplication proof. last_triggered_at updated on every
                        # actionable transition regardless of notification suppression.
                        for event in new_state.get("events", []):
                            await repo.create_event(alert.id, event)
                        if new_state.get("events"):
                            await repo.update_last_triggered(alert.id)
                        await session.commit()
                except Exception:
                    logger.exception(f"Alert {alert.id} ({alert.symbol}) failed during cycle, skipping")
```

**Deployment note**: The alert monitor assumes database migrations have been applied before the application starts. No runtime migration check is needed -- this is consistent with the existing `lifespan()` pattern where workers start after DB initialization.

**Decision on sequential vs concurrent price fetches (O2):** Price fetches are **sequential** per symbol, bounded by `alert_monitor_batch_size` (R20, default 50). Rationale: (1) `DataService` has internal caching so the same symbol is fetched only once; (2) Yahoo Finance has rate limits that unbounded concurrency could hit; (3) batch size prevents thundering herd on first startup with many alerts; (4) symbols not processed in one cycle are deferred to the next.

**`AlertService`:**

- `create_alert(symbol, alert_type, config) -> StockAlert` -- validate config via typed schemas (B1), validate symbol exists by calling `DataService.get_price_data()` (R3: returns 400 if symbol not found), create alert, request initial computation
- `update_alert(alert_id, config) -> StockAlert` -- update configuration
- `pause_alert(alert_id) -> StockAlert` -- toggle pause
- `delete_alert(alert_id)` -- soft delete
- `get_alert(alert_id) -> StockAlert` -- single alert with computed state
- `list_alerts(filters) -> list[StockAlert]` -- all alerts with optional status/type filters
- `get_alert_events(alert_id) -> list[AlertEvent]` -- event history for an alert
- `compute_fibonacci_state(alert, price_data) -> dict` -- compute fibonacci state using indicator
- `compute_ma_state(alert, price_data) -> dict` -- compute MA state using `analyze_ma_distance()`. When insufficient history (e.g., MA200 with <205 candles), return status `"insufficient_data"` (R16) with `computed_state: {"error": "Insufficient price history for MA200 (need 205 candles, have N)"}`. Note: `analyze_ma_distance()` returns `PricePosition.AT` with `distance_pct=0.0` and `MASlope.FLAT` when data is insufficient (see `ma_analysis.py:70-77`) -- the alert service must check candle count BEFORE calling `analyze_ma_distance()` and short-circuit to `"insufficient_data"` status. This is not an exception -- it's a valid state that the dashboard renders as a gray/dim badge.
- **MA notification deduplication (R19):** MA alert notification fires only when `previous_status != "at_ma"` AND `new_status == "at_ma"`. If price stays `at_ma` for multiple monitor cycles, notification fires exactly once. `AlertEvent` record serves as the deduplication proof.

**Config addition** (`backend/app/core/config.py`):

```python
alert_monitor_interval: int = Field(
    default=300,
    description="Interval for alert monitor to check all alerts in seconds (default 5 minutes)"
)
alert_monitor_batch_size: int = Field(
    default=50,
    description="Max symbols to process per monitor cycle to avoid data provider rate limits"
)
```

**Lifespan integration** (`backend/app/main.py`, after line 183):

```python
# Create and start alert monitor
from app.services.alert_monitor import AlertMonitorService
from app.providers.yahoo import YahooFinanceProvider

alert_provider = YahooFinanceProvider()
alert_monitor = AlertMonitorService(session_factory, alert_provider)
alert_monitor_task = asyncio.create_task(alert_monitor.start())
```

And in shutdown (after line 191):

```python
await alert_monitor.stop()
alert_monitor_task.cancel()
try:
    await alert_monitor_task
except asyncio.CancelledError:
    pass
```

**Tests:**

AlertService tests:
1. `test_create_fibonacci_alert` -- creates alert with correct defaults
2. `test_create_ma_alert` -- creates MA alert with correct defaults
3. `test_create_alert_invalid_config` -- rejects bad config (e.g., ma_periods=[999])
4. `test_create_alert_invalid_symbol` -- calls DataService, symbol not found, returns 400
5. `test_list_alerts_filters_by_status` -- filters work correctly
6. `test_list_alerts_excludes_deleted` -- soft-deleted alerts hidden
7. `test_pause_alert` -- toggles is_paused
8. `test_delete_alert` -- soft deletes
9. `test_compute_fibonacci_state_calls_indicator` -- integrates with fibonacci module
10. `test_compute_ma_state_uses_analyze_ma_distance` -- integrates with ma_analysis
11. `test_compute_ma_state_approaching` -- distance_pct between 0.5% and 2% returns approaching
12. `test_compute_ma_state_insufficient_history` -- MA200 with 50 candles returns status `"insufficient_data"`, no alert fired, no DB error (R16)
13. `test_ma_deduplication_at_ma_3_cycles` -- alert at `at_ma` for 3 consecutive cycles, assert exactly 1 `AlertEvent` record created (R19)

AlertMonitor tests:
1. `test_run_cycle_processes_active_alerts` -- fetches and processes only active, non-paused
2. `test_run_cycle_groups_by_symbol` -- single price fetch per symbol
3. `test_run_cycle_persists_state` -- computed_state written to DB
4. `test_run_cycle_creates_events` -- status transitions generate AlertEvent records
5. `test_run_cycle_handles_data_error` -- graceful handling when price data unavailable for a symbol; other symbols still processed
6. `test_run_cycle_isolates_alert_errors` -- one alert throwing exception does not prevent other alerts for same symbol from processing; mock `alert_repo.update_state()` to raise for alert #2 of 3, assert alerts #1 and #3 persisted, no orphan events for #2 (R21)
7. `test_stop_exits_loop` -- calling stop() breaks the loop
8. `test_concurrent_cycle_guard` -- call `_run_cycle()` twice concurrently, assert it runs only once (second invocation returns immediately) (R17)
9. `test_batch_size_limits_symbols` -- 60 alerts across 60 symbols, batch_size=50, assert only 50 symbols processed per cycle (R20)

**Acceptance criteria:**
- Monitor starts and stops cleanly in lifespan
- Concurrent run guard prevents overlapping cycles (R17)
- Each cycle processes up to `alert_monitor_batch_size` symbols (R20)
- Price data fetched once per symbol per cycle (not per alert), sequentially
- DataService instantiated per cycle (not once at startup) to prevent stale connections (R8)
- Each alert uses its own DB session/transaction (R21)
- Status transitions generate AlertEvent records
- MA notifications deduplicated: fire only on transition TO `at_ma`, not while staying (R19)
- Errors in one alert don't crash the cycle for other alerts (per-alert try/except, R1)
- Symbol validation on alert creation via DataService (R3)
- Insufficient MA history returns `"insufficient_data"` status (R16)
- Migrations must be applied before app start (deployment note)

### Phase 4: API Endpoints ✅

**Goal**: RESTful API for alert CRUD and state retrieval.

**New files:**
- `backend/app/api/v1/alerts.py` -- API router
- `backend/app/schemas/alert.py` -- request/response schemas
- `backend/tests/integration/test_alerts_api.py` -- API integration tests

**Files to modify:**
- `backend/app/main.py:292-324` -- register alerts router

**Schemas** (`backend/app/schemas/alert.py`):

```python
class FibonacciConfigRequest(StrictBaseModel):
    levels: list[float] = Field(default=[38.2, 50.0, 61.8])
    tolerance_pct: float = Field(default=0.5, ge=0.0, le=5.0)
    min_swing_pct: float = Field(default=10.0, ge=1.0, le=50.0)

VALID_MA_PERIODS = {20, 50, 150, 200}

class MAConfigRequest(StrictBaseModel):
    ma_periods: list[int] = Field(default=[200], min_length=1)
    tolerance_pct: float = Field(default=0.5, ge=0.0, le=5.0)
    direction: Literal["above", "below", "both"] = "both"

    @field_validator("ma_periods")
    @classmethod
    def validate_ma_periods(cls, v):
        for period in v:
            if period not in VALID_MA_PERIODS:
                raise ValueError(f"Invalid MA period {period}. Valid: {sorted(VALID_MA_PERIODS)}")
        return v

class CreateAlertRequest(StrictBaseModel):
    symbol: str = Field(..., min_length=1, max_length=20)
    alert_type: Literal["fibonacci", "moving_average"]
    config: FibonacciConfigRequest | MAConfigRequest

class UpdateAlertRequest(StrictBaseModel):
    config: FibonacciConfigRequest | MAConfigRequest | None = None
    is_paused: bool | None = None

class AlertResponse(StrictBaseModel):
    id: int
    symbol: str
    alert_type: str
    status: str
    is_active: bool
    is_paused: bool
    config: dict
    computed_state: dict | None
    last_triggered_at: datetime | None
    created_at: datetime
    updated_at: datetime

class AlertEventResponse(StrictBaseModel):
    id: int
    alert_id: int
    event_type: str
    previous_status: str | None
    new_status: str
    price_at_event: float
    details: dict | None
    created_at: datetime

class AlertListResponse(StrictBaseModel):
    items: list[AlertResponse]
    total: int
```

**Endpoints:**

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/alerts/` | Create alert(s). For MA with multiple periods, fans out into one row per period. Returns `list[AlertResponse]`. Validates symbol via DataService. |
| GET | `/api/v1/alerts/` | List all alerts (with optional filters: status, alert_type, symbol) |
| GET | `/api/v1/alerts/{alert_id}` | Get single alert with computed state |
| PATCH | `/api/v1/alerts/{alert_id}` | Update alert config or pause state |
| DELETE | `/api/v1/alerts/{alert_id}` | Soft-delete an alert |
| GET | `/api/v1/alerts/{alert_id}/events` | Get alert event history |
| GET | `/api/v1/alerts/{alert_id}/price-data` | Get price data for chart rendering (delegates to DataService). Query param: `days: int = 365` for deterministic date range. |

**`price-data` response schema (B5):** Returns the same format as the existing `/api/v1/stocks/{symbol}/prices/` endpoint -- a `StockPrice[]` array with OHLCV fields. For MA alerts, the relevant MA period values are pre-computed in the data array (matching existing `ma_20` field pattern). The frontend passes this directly to `CandlestickChart` without transformation.

```python
class AlertPriceDataResponse(StrictBaseModel):
    symbol: str
    alert_id: int
    data: list[dict]  # StockPrice records with OHLCV + computed MA fields
    days: int
```

**Router registration** (`backend/app/main.py`, after line 324):

```python
app.include_router(
    alerts.router,
    prefix=f"{settings.api_v1_prefix}/alerts",
    tags=["alerts"],
)
```

**Tests:**

1. `test_create_fibonacci_alert` -- 201, returns alert with defaults
2. `test_create_ma_alert` -- 201, returns alert with MA config
3. `test_create_alert_invalid_symbol` -- 400, clear error message
4. `test_create_alert_invalid_type` -- 422
5. `test_create_alert_invalid_ma_period` -- 422, rejects period not in {20, 50, 150, 200}
6. `test_list_alerts` -- 200, returns all non-deleted alerts
7. `test_list_alerts_filter_by_status` -- query param filtering works
8. `test_get_alert` -- 200, includes computed_state
9. `test_get_alert_not_found` -- 404
10. `test_update_alert_pause` -- 200, toggles is_paused
11. `test_delete_alert` -- 200, soft deletes
12. `test_get_alert_events` -- 200, returns event history ordered by created_at desc
13. `test_get_price_data_for_alert` -- 200, returns OHLCV data for chart
14. `test_get_price_data_days_param` -- respects `days` query parameter

**Acceptance criteria:**
- All endpoints follow existing patterns (StrictBaseModel, typed exceptions)
- Config validated via discriminated union schemas (not raw dict)
- `ma_periods` constrained to {20, 50, 150, 200}
- Symbol validated on creation via DataService
- `/price-data` accepts `days` query parameter (default 365)
- Invalid requests return proper 400/422 errors
- Deleted alerts return 404
- All 14 integration tests pass

### Phase 5: Frontend - Alert Service, Types, and Hooks ✅

**Goal**: Build the frontend data layer for alerts.

**New files:**
- `frontend/src/types/alert.ts` -- TypeScript types matching backend schemas
- `frontend/src/services/alertService.ts` -- API service functions
- `frontend/src/hooks/useAlerts.ts` -- CRUD hook for alerts
- `frontend/src/hooks/useAlertPolling.ts` -- polling hook for dashboard auto-refresh
- `frontend/src/hooks/useAlertDetail.ts` -- single alert + events fetch hook
- `frontend/src/hooks/useNotifications.ts` -- Web Notifications API wrapper

**Types** (`frontend/src/types/alert.ts`):

```typescript
export type AlertType = 'fibonacci' | 'moving_average';

export type FibonacciStatus = 'no_structure' | 'rallying' | 'pullback_started' | 'retracing' | 'at_level' | 'bouncing' | 'invalidated';

export type MAStatus = 'above_ma' | 'approaching' | 'at_ma' | 'below_ma' | 'insufficient_data';

// Base interface for shared fields
interface StockAlertBase {
  id: number;
  symbol: string;
  is_active: boolean;
  is_paused: boolean;
  last_triggered_at: string | null;
  created_at: string;
  updated_at: string;
}

// Discriminated union by alert_type (B4)
export interface FibonacciAlert extends StockAlertBase {
  alert_type: 'fibonacci';
  status: FibonacciStatus;
  config: FibonacciConfig;
  computed_state: FibonacciComputedState | null;
}

export interface MAAlert extends StockAlertBase {
  alert_type: 'moving_average';
  status: MAStatus;
  config: MAConfig;
  computed_state: MAComputedState | null;
}

export type StockAlert = FibonacciAlert | MAAlert;

// Type guards
export function isFibAlert(alert: StockAlert): alert is FibonacciAlert {
  return alert.alert_type === 'fibonacci';
}

export function isMAAlert(alert: StockAlert): alert is MAAlert {
  return alert.alert_type === 'moving_average';
}

export interface FibonacciConfig {
  levels: number[];
  tolerance_pct: number;
  min_swing_pct: number;
}

export interface MAConfig {
  ma_period: number;  // Single period per alert row (API fans out ma_periods list)
  tolerance_pct: number;
  direction: 'above' | 'below' | 'both';
}

// Full computed state types matching Phase 1 JSON structures (B5)
export interface FibLevelState {
  price: number;
  status: 'pending' | 'active' | 'triggered';
  triggered_at: string | null;
}

export interface FibonacciComputedState {
  swing_high: number;
  swing_low: number;
  swing_high_date: string;
  swing_low_date: string;
  trend_direction: 'uptrend' | 'downtrend';
  current_price: number;
  retracement_pct: number;
  fib_levels: Record<string, FibLevelState>;
  next_level: { pct: number; price: number } | null;
}

export interface MAComputedState {
  ma_value: number;
  ma_period: number;
  current_price: number;
  distance_pct: number;
  ma_slope: 'rising' | 'falling' | 'flat';
}

export interface AlertEvent {
  id: number;
  alert_id: number;
  event_type: 'level_hit' | 'invalidated' | 're_anchored' | 'status_change';
  previous_status: string | null;
  new_status: string;
  price_at_event: number;
  details: Record<string, unknown> | null;
  created_at: string;
}
```

**API types vs view models distinction:**

The types above (`StockAlert`, `FibonacciAlert`, `MAAlert`) are **API response types** -- they mirror the backend JSON exactly. For table rendering, derive **view model types** via a transform function:

```typescript
// View models for table rendering (derived from API types)
export interface AlertTableRow {
  id: number;
  symbol: string;
  alertTypeLabel: string;  // "Fibonacci Retracement" or "MA200" etc.
  currentPrice: number | null;
  status: string;
  detailsText: string;  // Pre-formatted details column
  lastTriggeredAt: string | null;
}

export function toAlertTableRow(alert: StockAlert): AlertTableRow { ... }
```

This keeps API types clean and presentation logic in the transform function.

**Service** (`frontend/src/services/alertService.ts`) -- follow pattern from `frontend/src/services/live20Service.ts`:

```typescript
const API_BASE = '/v1/alerts';

export const listAlerts = async (params?) => apiClient.get(`${API_BASE}/`, { params }).then(r => r.data);
export const createAlert = async (data) => apiClient.post(`${API_BASE}/`, data).then(r => r.data);
export const getAlert = async (id) => apiClient.get(`${API_BASE}/${id}`).then(r => r.data);
export const updateAlert = async (id, data) => apiClient.patch(`${API_BASE}/${id}`, data).then(r => r.data);
export const deleteAlert = async (id) => apiClient.delete(`${API_BASE}/${id}`).then(r => r.data);
export const getAlertEvents = async (id) => apiClient.get(`${API_BASE}/${id}/events`).then(r => r.data);
export const getAlertPriceData = async (id, days = 365) => apiClient.get(`${API_BASE}/${id}/price-data`, { params: { days } }).then(r => r.data);
```

**`useNotifications` hook (with unsupported browser guard -- B2):**

```typescript
const getInitialPermission = (): NotificationPermission => {
  if (typeof Notification === 'undefined') return 'default';
  return Notification.permission;
};

export function useNotifications() {
  const [permission, setPermission] = useState<NotificationPermission>(getInitialPermission);

  const requestPermission = async (): Promise<NotificationPermission> => {
    if (typeof Notification === 'undefined') return 'denied';
    const result = await Notification.requestPermission();
    setPermission(result);
    return result;
  };

  const notify = (title: string, body: string, onClick?: () => void) => {
    if (typeof Notification !== 'undefined' && permission === 'granted') {
      const n = new Notification(title, { body, icon: '/favicon.ico' });
      if (onClick) n.onclick = onClick;
    } else {
      toast(title, { description: body });  // sonner fallback
    }
  };

  return { permission, requestPermission, notify };
}
```

**`useAlertPolling` hook (with first-load guard -- B3)** -- follow pattern from `frontend/src/hooks/useArenaPolling.ts`:

```typescript
export function useAlertPolling(interval = 30000) {
  const [alerts, setAlerts] = useState<StockAlert[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const previousAlertsRef = useRef<StockAlert[]>([]);
  const isFirstFetchRef = useRef(true);
  const { notify } = useNotifications();

  const fetchAlerts = useCallback(async () => {
    try {
      const response = await listAlerts();
      const newAlerts = response.items;
      setAlerts(newAlerts);
      setError(null);

      // Skip notification on first fetch (B3)
      if (isFirstFetchRef.current) {
        isFirstFetchRef.current = false;
        previousAlertsRef.current = newAlerts;
        return;
      }

      // Detect status changes and fire notifications
      for (const alert of newAlerts) {
        const prev = previousAlertsRef.current.find(a => a.id === alert.id);
        if (prev && prev.status !== alert.status) {
          if (alert.status === 'at_level' || alert.status === 'at_ma') {
            notify(/* ... */);
          }
        }
      }
      previousAlertsRef.current = newAlerts;
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load alerts');
    } finally {
      setIsLoading(false);
    }
  }, [notify]);

  // ... setInterval with cleanup

  return { alerts, isLoading, error, refetch: fetchAlerts };
}
```

**Unknown `alert_type` handling**: Components rendering alert data must handle unknown `alert_type` values gracefully. When `alert_type` is neither `'fibonacci'` nor `'moving_average'`, render a fallback: `<span aria-label="Unknown alert type">--</span>`. Never crash on unexpected API data.

**Acceptance criteria:**
- Types match backend schemas exactly, using discriminated unions
- `FibonacciComputedState` and `MAComputedState` fully defined (not stubbed)
- `isFibAlert()` / `isMAAlert()` type guards exported
- All `Notification.*` calls guarded by `typeof Notification !== 'undefined'`
- Polling hook skips notifications on first fetch
- Service functions handle errors consistently
- Web Notification permission requested lazily on first alert creation
- Sonner toast fallback when permission denied or Notification API unavailable
- Unknown alert types render graceful fallback, not crash

### Phase 6: Frontend - Alerts Dashboard Page ✅

**Goal**: Build the main alerts monitoring dashboard.

**New files:**
- `frontend/src/pages/Alerts/AlertsDashboard.tsx` -- main page component
- `frontend/src/pages/Alerts/index.ts` -- barrel export
- `frontend/src/components/alerts/AlertsTable.tsx` -- table component (desktop) + card layout (mobile)
- `frontend/src/components/alerts/AlertStatusBadge.tsx` -- status badge component
- `frontend/src/components/alerts/CreateAlertDialog.tsx` -- dialog for adding alerts
- `frontend/src/components/alerts/AlertFilters.tsx` -- filter/sort controls

**Files to modify:**
- `frontend/src/App.tsx:42-52` -- add `/alerts` and `/alerts/:alertId` routes
- `frontend/src/components/layouts/navigationConfig.ts:17-43` -- add Alerts nav item

**Route additions** (`frontend/src/App.tsx`, after line 49):

```tsx
<Route path="/alerts" element={<AlertsDashboard />} />
<Route path="/alerts/:alertId" element={<AlertDetail />} />
```

**Nav item addition** (`frontend/src/components/layouts/navigationConfig.ts`):

Add to `NAV_ITEMS` array (import `Bell` from lucide-react):
```typescript
{
  path: '/alerts',
  label: 'Alerts',
  icon: Bell,
},
```

This makes it the 6th item, placing it in the "More" sheet on mobile (items 4+ go to More per line 49-55).

**`AlertsTable` columns:**

| Column | Fibonacci | Moving Average |
|--------|-----------|---------------|
| Symbol | ticker | ticker |
| Alert Type | "Fibonacci Retracement" | "MA50" / "MA200" etc. |
| Price | current price from computed_state (font-mono) | current price (font-mono) |
| Status | AlertStatusBadge with Fibonacci status | AlertStatusBadge with MA status |
| Details | Swing range, retracement %, next level | MA value, distance % |
| Last Alert | timestamp of last triggered event | timestamp |

**Responsive layout (R9):**
- Desktop: `<Table>` with `data-testid="alerts-table"`
- Mobile: Card list with `data-testid="alert-card"` per card
- Switch via `useResponsive().isMobile` (or equivalent media query hook)
- Playwright test at 375px viewport: assert `data-testid="alert-card"` exists, assert `data-testid="alerts-table"` does NOT exist

**`AlertStatusBadge` colors:**

Add `ALERT_STATUS_COLORS` constant to `frontend/src/constants/colors.ts`, following the existing pattern of `POSITION_COLORS`, `SCREENER_COLORS`, `INDICATOR_COLORS` (see `frontend/src/constants/colors.ts:20-96`). Do NOT use inline Tailwind strings in badge components -- reference the constant.

**File to modify:** `frontend/src/constants/colors.ts` -- add at end of file:

```typescript
export const ALERT_STATUS_COLORS = {
  // Fibonacci statuses
  rallying: 'bg-accent-bullish/15 text-accent-bullish border border-accent-bullish/30',
  pullback_started: 'bg-yellow-500/15 text-yellow-500 border border-yellow-500/30',
  retracing: 'bg-orange-500/15 text-orange-500 border border-orange-500/30',
  at_level: 'bg-accent-bearish/15 text-accent-bearish border border-accent-bearish/30 animate-pulse',
  bouncing: 'bg-blue-500/15 text-blue-500 border border-blue-500/30',
  invalidated: 'bg-text-muted/15 text-text-muted border border-text-muted/30',
  no_structure: 'bg-text-muted/10 text-text-muted/60 border border-text-muted/20',
  // MA statuses
  above_ma: 'bg-accent-bullish/15 text-accent-bullish border border-accent-bullish/30',
  approaching: 'bg-yellow-500/15 text-yellow-500 border border-yellow-500/30',
  at_ma: 'bg-accent-bearish/15 text-accent-bearish border border-accent-bearish/30 animate-pulse',
  below_ma: 'bg-orange-500/15 text-orange-500 border border-orange-500/30',
  insufficient_data: 'bg-text-muted/10 text-text-muted/60 border border-text-muted/20',
} as const satisfies Record<string, string>;
```

Usage in `AlertStatusBadge`:
```tsx
import { ALERT_STATUS_COLORS } from '../../constants/colors';

<Badge className={ALERT_STATUS_COLORS[status] ?? 'bg-text-muted/10 text-text-muted/60'}>
  {statusLabel}
</Badge>
```

**Accessibility: `aria-live` for actionable statuses (R11):**

```tsx
<div role="status" aria-live="assertive" aria-atomic="true" className="sr-only">
  {actionableAlerts.map(a => `${a.symbol} is now at an actionable level`).join('. ')}
</div>
```

Test: assert live region text updates when status transitions to `at_level`/`at_ma`.

**"Tab must be open" persistent banner (R10):**

When `Notification.permission === 'granted'`, render a persistent non-dismissible banner at the top of the `/alerts` page:
> "Alerts require this tab to remain open. Notifications will not fire if the browser tab is closed."

This banner uses `typeof Notification !== 'undefined'` guard. Not shown when permission is `'default'` or `'denied'`.

**`CreateAlertDialog`:**
- Symbol search input (reuse pattern from `frontend/src/hooks/useStockSearch.ts`)
- Alert type selector (Fibonacci / Moving Average)
- Fibonacci: checkboxes for levels (default 38.2%, 50%, 61.8%)
- MA: checkboxes for periods (MA20, MA50, MA150, MA200), direction selector
- Tolerance advanced setting (collapsed by default)
- On first alert creation, call `requestPermission()` for Web Notifications
- **Zero-level validation (R12):** If zero Fibonacci levels are selected, show inline error: "Select at least one Fibonacci level to monitor." Submit button stays enabled (shows error on attempt, not silently disabled). `alertService.createAlert` must NOT be called. Same for zero MA periods: "Select at least one moving average period."

**Dashboard features:**
- Sort by status (ascending: actionable states first)
- Filter by alert type, status
- Empty state: "No alerts configured. Add a stock to start monitoring."
- Loading skeleton: 3 rows of `Skeleton` components
- Error state with retry button

**Acceptance criteria:**
- Dashboard renders one row per alert (not per stock)
- Clicking a row navigates to `/alerts/:alertId`
- Status badges match the color spec from the ticket
- `at_level`/`at_ma` badges have `animate-pulse` and update `aria-live` region
- Create dialog validates inputs before submission (zero levels blocked with inline error)
- Notification permission requested on first alert creation
- Responsive: card list on mobile, table on desktop
- Persistent "tab must be open" banner when notifications are granted
- Unknown `alert_type` renders graceful fallback

### Phase 7: Frontend - Alert Detail View ✅

**Goal**: Build the stock detail view with chart overlays and alert info panel.

**New files:**
- `frontend/src/pages/Alerts/AlertDetail.tsx` -- detail page
- `frontend/src/components/alerts/FibonacciChartOverlay.tsx` -- helper to convert fibonacci state to chart props
- `frontend/src/components/alerts/AlertInfoPanel.tsx` -- sidebar/bottom panel with alert state and history

**Files to modify:**
- `frontend/src/components/organisms/CandlestickChart/CandlestickChart.tsx:23-31` -- add optional `extraLineSeries` prop for additional MA lines

**Chart integration:**

The existing `CandlestickChart` already supports:
- `priceLines` prop for horizontal lines (Fibonacci levels, swing markers)
- `markers` prop for point markers on candles (swing high/low confirmations)
- `LineSeries` for MA lines (MA20 already implemented at line 105-112)

For Fibonacci alerts, the detail view will:
1. Convert `computed_state.fib_levels` to `ChartPriceLine[]` -- each level as a horizontal line with label (e.g., "50% -- $125.00"). Triggered levels use solid style; pending use dashed.
2. Add swing high/low as `ChartMarker[]` -- arrow markers at swing points.

For MA alerts, the detail view will:
1. Pass additional MA line data as a new `extraLineSeries` prop on `CandlestickChart`.
2. The chart component adds each extra series as a `LineSeries` in pane 0, following the same pattern as MA20 (line 105-112).

**`CandlestickChart` modification:**

Add prop to `CandlestickChartProps` interface (line 23):

```typescript
extraLineSeries?: {
  label: string;
  color: string;
  data: { time: UTCTimestamp; value: number }[];
}[];
```

**The `extraLineSeries` must be handled in a separate `useEffect` (R13)**, not inside the chart initialization effect. This follows the existing pattern for `priceLines` at `CandlestickChart.tsx:367-398` -- a separate effect that watches the prop and adds/removes series when it changes. Adding series inside the initialization effect causes silent failures when the prop changes post-mount.

**Loading and error states (R14):**
- Loading: `Skeleton` placeholder for chart area and info panel, consistent with `Live20Dashboard` pattern
- Error: `Alert variant="destructive"` component with retry button
- 404: "Alert not found" message with back button

**`AlertInfoPanel` content:**

For Fibonacci:
- Status badge (same as dashboard)
- Swing range: "$110.00 -> $140.00 (27.3% move)"
- Current retracement: "38.2% ($128.54)"
- Distance to next level: "11.8% to 50% ($125.00)"
- Level status table: each configured level with pending/triggered/invalidated status
- Alert history: list of AlertEvent records with timestamps

For MA:
- Status badge
- MA value and period: "MA200 @ $125.50"
- Distance: "2.0% above MA"
- MA slope: "Rising"
- Alert history

**Navigation:**
- Back button to `/alerts` (using `useNavigate()`)
- Quick actions: Pause/Resume button, Edit button (opens dialog), Delete button (with confirmation)

**Acceptance criteria:**
- Fibonacci levels render as horizontal lines on the chart
- Triggered levels visually distinct from pending (solid vs dashed)
- Swing high/low marked on chart
- MA lines render as overlays when MA alerts configured
- `extraLineSeries` managed in a separate `useEffect` (not in chart init)
- Loading skeleton shown during data fetch
- Error state with retry button
- Info panel shows accurate current state
- Alert history displayed in reverse chronological order
- Back navigation works

### Phase 8: Web Notifications Integration ✅

**Goal**: Wire up browser Web Notifications for alert delivery.

**Files to modify:**
- `frontend/src/hooks/useAlertPolling.ts` -- add notification trigger on status transitions
- `frontend/src/hooks/useNotifications.ts` -- (created in Phase 5)

**Notification trigger logic in `useAlertPolling`:**

On each poll, compare previous alert states with new states. For each alert where status changed:

- Fibonacci `retracing -> at_level`: fire notification -- "NVDA hit 38.2% Fibonacci at $128.50 (swing: $110->$140)"
- Fibonacci `* -> invalidated`: fire notification -- "NVDA broke below swing low $110 -- Fibonacci setup invalidated"
- MA `approaching -> at_ma` or `above_ma -> at_ma` or `below_ma -> at_ma`: fire notification -- "NVDA touched MA200 at $125.50 (0.3% away)"

**Notification click behavior (R15 -- no full page reload):**

```typescript
n.onclick = () => {
  window.focus();
  // Use history API to avoid full SPA reload
  window.history.pushState({}, '', `/alerts/${alert.id}`);
  window.dispatchEvent(new PopStateEvent('popstate'));
};
```

This avoids a full page reload that `window.location.href` would cause. React Router listens to `popstate` events, so this triggers a client-side navigation. Service worker is NOT in v1 scope -- this is a local-first app for 2-3 users.

**Fallback:** When `Notification.permission !== 'granted'` or `typeof Notification === 'undefined'`, use sonner toast with action button linking to alert detail.

**Acceptance criteria:**
- Permission requested on first alert creation (not on page load)
- Notifications fire only on actionable status transitions
- First poll after mount does NOT fire notifications (B3)
- Clicking notification navigates to alert detail view without full page reload
- Sonner toast fallback works when permission denied or API unavailable
- No duplicate notifications (track last-seen status per alert)
- All `Notification.*` calls guarded by `typeof Notification !== 'undefined'`

## Testing Strategy

### Backend Unit Tests

| Module | File | Test Count |
|--------|------|-----------|
| Fibonacci indicator | `tests/unit/indicators/test_fibonacci.py` | 24 |
| Alert service | `tests/unit/services/test_alert_service.py` | 13 |
| Alert monitor | `tests/unit/services/test_alert_monitor.py` | 9 |

### Backend Integration Tests

| Module | File | Test Count |
|--------|------|-----------|
| Alerts API | `tests/integration/test_alerts_api.py` | 14 |

### Frontend Unit Tests

| Component | File | Key Tests |
|-----------|------|-----------|
| AlertStatusBadge | colocated `.test.tsx` | Renders correct color/text for each status; unknown status shows fallback |
| AlertsTable | colocated `.test.tsx` | Renders rows, handles empty/loading/error states; mobile card layout at 375px |
| CreateAlertDialog | colocated `.test.tsx` | Form validation, zero-level error, submission, permission request |
| AlertInfoPanel | colocated `.test.tsx` | Renders fibonacci and MA info correctly |
| useNotifications | colocated `.test.ts` | Permission request, notify, fallback, unsupported browser guard |
| useAlertPolling | colocated `.test.ts` | Polls, detects changes, fires notifications; first load does NOT fire notifications |
| aria-live region | in AlertsDashboard `.test.tsx` | Live region text updates on `at_level`/`at_ma` transition |

### Manual Test Steps

1. **Create Fibonacci alert**: Add AAPL with default levels (38.2%, 50%, 61.8%). Verify alert appears in dashboard with correct status badge.
2. **Create MA alert**: Add NVDA MA200. Verify separate row in dashboard.
3. **Zero-level validation**: Try to create Fibonacci alert with no levels selected. Verify inline error, no API call made.
4. **Dashboard filtering**: Filter by "at_level" status. Verify only matching alerts shown.
5. **Detail view - Fibonacci**: Click a Fibonacci alert. Verify chart shows horizontal Fibonacci level lines, swing markers, and info panel.
6. **Detail view - MA**: Click an MA alert. Verify MA line overlay on chart, correct distance display.
7. **Web Notification**: Wait for or trigger a status transition. Verify browser notification appears. Click it to navigate to detail view (no page reload).
8. **Notification fallback**: Deny notification permission. Verify sonner toast appears instead.
9. **First-load no notification**: Refresh page when an alert is `at_level`. Verify no notification fires on initial load.
10. **Pause/Resume**: Pause an alert. Verify monitor skips it. Resume and verify it's picked up again.
11. **Delete alert**: Delete an alert. Verify it disappears from dashboard and returns 404 on direct access.
12. **Monitor cycle**: Check backend logs for successful monitor cycles processing alerts.
13. **Mobile layout**: View dashboard at 375px width. Verify card layout renders (not table).
14. **Tab banner**: Grant notification permission. Verify persistent "tab must be open" banner.

## Success Criteria

**Dashboard:**
- [ ] Dashboard shows one row per alert (not per stock)
- [ ] Fibonacci alerts have their own status badges (rallying, retracing, at level, etc.)
- [ ] MA alerts have their own status badges (above MA, approaching, at MA, below MA)
- [ ] Dashboard is sortable/filterable by status
- [ ] Fibonacci rows show swing range, retracement depth, and next level
- [ ] MA rows show MA value and distance from price
- [ ] Responsive: table on desktop, card list on mobile
- [ ] Persistent "tab must be open" banner when notifications granted
- [ ] `aria-live` region announces actionable status changes

**Stock Detail View:**
- [ ] Clicking an alert opens a detail view with candlestick chart
- [ ] Fibonacci retracement levels drawn on chart as horizontal lines with labels
- [ ] Swing high and swing low clearly marked on chart
- [ ] Triggered vs pending levels visually distinct (solid vs dashed)
- [ ] MA lines overlaid when MA alerts configured
- [ ] Alert info panel shows current state and history
- [ ] Loading skeleton and error state with retry

**Fibonacci Alerts:**
- [ ] User can create Fibonacci alert by picking symbol and levels
- [ ] Zero-level selection blocked with inline error
- [ ] System automatically detects swing structures
- [ ] Works for both uptrend (pullbacks) and downtrend (bounces)
- [ ] System correctly calculates Fibonacci levels
- [ ] Tolerance boundary is precise (0.5% default)
- [ ] Auto-invalidates when price breaks beyond swing origin
- [ ] Auto-re-anchors when new swing extremes confirmed
- [ ] Each level triggers once per swing structure (no spam)

**Moving Average Alerts:**
- [ ] User can configure MA touch alerts (MA20/50/150/200 only)
- [ ] Invalid MA periods rejected at API level
- [ ] Correctly calculates MAs and detects price proximity
- [ ] Insufficient history returns `insufficient_data` status with descriptive message
- [ ] MA alerts show status (above, approaching, at, below, insufficient_data)
- [ ] MA notifications deduplicated: fire only on transition to `at_ma`
- [ ] Each MA period is a separate alert row

**Notifications & History:**
- [ ] Alerts fire as browser Web Notifications on actionable transitions
- [ ] No notification on first page load
- [ ] In-app toast fallback when permission denied or API unavailable
- [ ] Notification click navigates without full page reload (pushState)
- [ ] Alert history persisted and viewable (global and per-alert)
- [ ] Alerts can be paused, edited, and deleted

**Backend:**
- [ ] Monitor service runs reliably on configured interval
- [ ] Concurrent run guard prevents overlapping cycles
- [ ] Batch size limits symbols processed per cycle
- [ ] DataService instantiated per cycle
- [ ] Price fetches sequential, one per symbol per cycle
- [ ] Per-alert error isolation with per-alert DB session
- [ ] Symbol validated on alert creation
- [ ] Computes and persists state each cycle
- [ ] All alert logic has comprehensive test coverage (>= 80%)
- [ ] All backend tests pass (100% pass rate): 24 + 13 + 9 + 14 = 60 tests
- [ ] All frontend tests pass (100% pass rate)
