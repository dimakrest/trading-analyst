# Phase 5: MA50 Filter + Market Volatility Circuit Breaker (#52)

Parent: #47 -- ATR-Based Exit Strategies
Depends on: Phase 4 (#51) -- comparison route wiring and strategy presets reference Phase 4 fields. Ships last.

## Status

Implemented (2026-04-16). Backend (5a-5h), frontend (F1-F6), tests, and migration `f5a6b7c8d9e0` all shipped. Follow-up (2026-04-16): ALL-features engineered integration test (`TestSimulationEngineAllFeaturesIntegration`) and F6 `useEntryFilterState` hook extraction both added.

## What

Two entry-level filters that complete both aggressive and conservative strategies:
1. **MA50 filter**: Only buy stocks trading above their 50-day moving average (trend-following gate)
2. **Circuit breaker**: Block all new entries when market volatility (SPY ATR%) exceeds a threshold

## Why

- **MA50**: Prevents buying stocks in long-term downtrends. Both strategies use this.
- **Circuit breaker**: Both strategies use ATR% < 2.8 as a market-wide safety valve. When overall market volatility is extreme, all entries are paused.

---

## Filter Execution Order

Entry filters run in `step_day()` after BUY signal collection (`simulation_engine.py:716-718`) and before portfolio selection (`simulation_engine.py:720`). The order is:

1. **Circuit breaker** (day-level gate) -- blocks ALL entries if market ATR% >= threshold. When triggered, `buy_signals` is emptied. Neither IBS nor MA50 runs on an empty list, so filtered symbols show only `circuit_breaker_filtered=True` (no `ibs_filtered` or `ma50_filtered` annotations).
2. **IBS filter** (per-symbol) -- from Phase 4. Modifies `buy_signals` in-place.
3. **MA50 filter** (per-symbol) -- iterates the already-IBS-filtered list. A symbol filtered by IBS will have `ibs_filtered=True` and no `ma50_filtered` annotation.
4. **Portfolio selection** -- ranks and constrains remaining signals.

This ordering ensures: circuit breaker is cheapest (one ATR calc), IBS is next (one bar lookup), MA50 is most expensive (50-bar history). Early filters reduce work for later ones.

**Analyst-facing implication**: If a symbol shows `ibs_filtered=True` with no `ma50_filtered` annotation, MA50 was NOT evaluated for that symbol. The absence of `ma50_filtered` is NOT an implicit MA50 pass -- it means IBS caught the symbol first and MA50 never ran. This must be documented in both the backend code comment and the `ArenaDecisionLog` UI (tooltip or help text).

---

## Backend Changes

### 5a. MA50 Filter

Calculation: 50-day SMA of closing prices, computed from the price cache.

Location: Entry filter block, after IBS filter (Phase 4) and before portfolio selection. Note: `price_history` from the agent evaluation loop is NOT in scope here -- must fetch from cache explicitly.

**Stale-close guard**: Before comparing, verify `ph[-1].date == current_date` to avoid silent pricing errors from data gaps (comparing yesterday's close against today's MA).

```python
if ma50_filter_enabled:
    filtered_buy_signals = []
    for symbol, decision in buy_signals:
        ph = self._get_cached_price_history(
            simulation_id, symbol,
            current_date - timedelta(days=90), current_date,
        )
        # ph[-1].date == current_date is guaranteed for symbols in buy_signals
        # (agent loop NO_DATA guard), but checked explicitly for defensive
        # correctness against data gaps that could cause silent pricing errors.
        if ph and len(ph) >= 50 and ph[-1].date == current_date:
            closes = [float(bar.close) for bar in ph[-50:]]
            ma50 = sum(closes) / len(closes)
            today_close = float(ph[-1].close)
            if today_close < ma50:
                decisions[symbol]["ma50_filtered"] = True
                decisions[symbol]["portfolio_selected"] = False
                continue
        else:
            # Insufficient data (< 50 bars) or stale bar -- skip filter, allow entry.
            if ph and len(ph) < 50:
                logger.debug(f"MA50 filter skipped for {symbol}: only {len(ph)} bars available")
            elif ph and ph[-1].date != current_date:
                logger.debug(f"MA50 filter skipped for {symbol}: last bar date {ph[-1].date} != {current_date}")
        filtered_buy_signals.append((symbol, decision))
    buy_signals = filtered_buy_signals
```

When fewer than 50 bars exist, MA50 filter is inactive for that symbol. Add `logger.debug` for these cases to help operators identify symbols with insufficient history.

### 5b. Market ATR% Circuit Breaker

Day-level gate using ATR% of a market proxy (e.g., SPY). Four distinct states captured as an enum on every snapshot, regardless of whether entries were actually blocked:

| State | Meaning |
|-------|---------|
| `disabled` | Breaker not configured for this simulation |
| `clear` | Breaker configured, market ATR% below threshold |
| `triggered` | Breaker configured, market ATR% >= threshold, entries blocked |
| `data_unavailable` | Breaker configured but market ATR could not be computed (missing/stale SPY data) -- safety valve **bypassed** |

Location: After BUY signal collection, BEFORE per-symbol filters (IBS, MA50) and portfolio selection.

**Unconditional evaluation (Critical).** The breaker MUST evaluate on every trading day when configured, NOT only when `buy_signals` is non-empty. Rationale: on a high-volatility day with zero BUY signals, the old design would record `state=clear` when the market was actually above threshold -- corrupting backtest analytics ("how often would the breaker have fired?") and making live-trading post-mortem impossible ("we didn't trade because there were no signals" vs "...because the breaker would have fired"). The cost is one cached ATR lookup per trading day -- negligible.

**Tracking variables**: Declare before the circuit breaker block so they are available for snapshot construction later:

```python
# Declare before circuit breaker block:
circuit_breaker_state: str = "disabled"
circuit_breaker_atr_pct_today: float | None = None

circuit_breaker_threshold = simulation.agent_config.get("circuit_breaker_atr_threshold")
if circuit_breaker_threshold is not None:
    market_symbol = simulation.agent_config.get("circuit_breaker_symbol", "SPY")
    market_atr_pct = self._calculate_symbol_atr_pct(simulation_id, market_symbol, current_date)
    circuit_breaker_atr_pct_today = market_atr_pct  # record even when below threshold or None

    if market_atr_pct is None:
        # SPY data unavailable: fail-open (see rationale below), but make the
        # bypass explicit in state and logs so operators can see it.
        circuit_breaker_state = "data_unavailable"
        logger.warning(
            "Circuit breaker skipped for simulation %s on %s: ATR unavailable for %s. "
            "Entries proceed (fail-open). Check market-data feed health.",
            simulation_id, current_date, market_symbol,
        )
    elif market_atr_pct >= circuit_breaker_threshold:
        circuit_breaker_state = "triggered"
        # Empty buy_signals is a no-op; the state column is the audit record.
        for symbol, decision in buy_signals:
            decisions[symbol]["circuit_breaker_filtered"] = True
            decisions[symbol]["portfolio_selected"] = False
        buy_signals = []
    else:
        circuit_breaker_state = "clear"
```

**Fail-open policy**: When `market_atr_pct` is None (SPY data unavailable for `current_date`), the circuit breaker SKIPS -- all entries proceed normally. Rationale: missing ATR data is typically a data delay, not a market event. Fail-safe (blocking all entries) would cause significant opportunity cost on data quality issues. Operators should monitor data feed health separately.

**Observability requirement**: Unlike the prior design, the fail-open path is no longer invisible. The `data_unavailable` state is persisted in the snapshot, logged at `WARNING` level (not debug), and surfaced distinctly in the frontend banner. A safety-critical control being bypassed must not look like an ordinary calm day.

### 5c. Snapshot Market Condition Columns

Day-level metadata stored as dedicated typed columns on `ArenaSnapshot` (`models/arena.py:381`) -- NOT in `decisions` dict (that would break symbol iteration):

```python
circuit_breaker_state: Mapped[str] = mapped_column(
    String(20), nullable=False, server_default=sa.text("'disabled'")
)  # 'disabled' | 'clear' | 'triggered' | 'data_unavailable'
circuit_breaker_atr_pct: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)
regime_state: Mapped[str | None] = mapped_column(String(10), nullable=True)
```

**Design rationale**: An explicit 4-value state replaces the original `circuit_breaker_triggered: bool`. The boolean conflated three different realities into `false`: "not configured", "configured and calm", and "configured but data missing (safety valve bypassed)". A state enum distinguishes them and generalizes cleanly if future filters need their own day-level audit state.

**SQLAlchemy import**: No new imports needed for the state column (`String` is already imported in `models/arena.py:12`). Confirm current import line contains `String`; `Boolean` is NOT required since the boolean has been replaced by a string enum.

**Snapshot constructor update** (`simulation_engine.py:825-837`): Add all three new fields:
```python
# Determine regime state for snapshot (None if regime filter disabled)
regime_state_value = None
if simulation.agent_config.get("regime_filter", False):
    regime_symbol = simulation.agent_config.get("regime_symbol", "SPY")
    sma_period = simulation.agent_config.get("regime_sma_period", 20)
    regime_state_value = self._detect_market_regime(
        simulation_id, current_date, regime_symbol, sma_period
    )

snapshot = ArenaSnapshot(
    simulation_id=simulation.id,
    snapshot_date=current_date,
    day_number=simulation.current_day,
    cash=cash,
    positions_value=positions_value,
    total_equity=total_equity,
    daily_pnl=daily_pnl,
    daily_return_pct=daily_return_pct,
    cumulative_return_pct=cumulative_return_pct,
    open_position_count=len(positions_by_symbol),
    decisions=decisions,
    circuit_breaker_state=circuit_breaker_state,
    circuit_breaker_atr_pct=Decimal(str(circuit_breaker_atr_pct_today)) if circuit_breaker_atr_pct_today is not None else None,
    regime_state=regime_state_value,
)
```

Note: `regime_state` is populated from the `_detect_market_regime()` result when `regime_filter=True`, otherwise None. The regime detection already runs during the regime filter block (`simulation_engine.py:730-741`) but the `regime` variable is scoped inside that `if` block. Either hoist it or re-call `_detect_market_regime()` (it's a pure cache lookup, no cost).

### 5d. Price Cache for Circuit Breaker Symbol

**At simulation init** (`simulation_engine.py:139-147`): If circuit breaker is enabled and the symbol is not in the simulation list, load it into the price cache. This is the primary path.

```python
# In initialize_simulation, alongside the regime filter block (line 140-147):
cb_threshold = simulation.agent_config.get("circuit_breaker_atr_threshold")
if cb_threshold is not None:
    cb_symbol = simulation.agent_config.get("circuit_breaker_symbol", "SPY")
    if cb_symbol not in simulation.symbols:
        await self._load_auxiliary_symbol_cache(
            simulation.id, cb_symbol,
            simulation.start_date, simulation.end_date,
            lookback_days=90,
        )
```

**In step_day lazy-load guard** (`simulation_engine.py:293-311`): Add crash-recovery fallback:
```python
# Inside the resume block (after regime cache reload, before trading_days):
cb_threshold = simulation.agent_config.get("circuit_breaker_atr_threshold")
if cb_threshold is not None:
    cb_symbol = simulation.agent_config.get("circuit_breaker_symbol", "SPY")
    if cb_symbol not in self._price_cache.get(simulation_id, {}):
        await self._load_auxiliary_symbol_cache(
            simulation_id, cb_symbol,
            simulation.start_date, simulation.end_date,
            lookback_days=90,
        )
```

### 5e. Refactor: `_load_auxiliary_symbol_cache`

Rename/generalize `_load_regime_symbol_cache` (`simulation_engine.py:1034`) to `_load_auxiliary_symbol_cache`. The regime filter and circuit breaker both need to load non-simulation symbols into the price cache with different lookback requirements.

Explicit signature:
```python
async def _load_auxiliary_symbol_cache(
    self,
    simulation_id: int,
    symbol: str,
    start_date: date,
    end_date: date,
    lookback_days: int,  # regime: sma_period*2+30 / circuit_breaker: 90
) -> None:
    """Fetch auxiliary symbol (e.g. SPY) into the price cache with lookback."""
```

**Call sites**:
1. **Regime filter** (init + resume): `lookback_days=sma_period * 2 + 30`
2. **Circuit breaker** (init + resume): `lookback_days=90`

Update existing `_load_regime_symbol_cache` callers (`simulation_engine.py:141`, `simulation_engine.py:304`) to use the new signature, passing the computed lookback as the `lookback_days` parameter.

### 5f. Schema Changes

New fields on `CreateSimulationRequest` (`schemas/arena.py:59`) AND `CreateComparisonRequest` (`schemas/arena.py:353`):
- `ma50_filter_enabled: bool = False`
- `circuit_breaker_atr_threshold: float | None = None` (gt=0). None = disabled. Description should document units: "ATR% as a percentage, e.g. 2.8 = 2.8%"
- `circuit_breaker_symbol: str = "SPY"` (max_length=10, pattern=r"^[A-Z]{1,5}$")

### 5g. API Wiring (5-Step Process)

1. **Schema fields**: Add to `CreateSimulationRequest` (`schemas/arena.py:59`) and `CreateComparisonRequest` (`schemas/arena.py:353`)
2. **agent_config in create_simulation()** (`arena.py:256-297`): Add:
   ```python
   # Layer 10: Entry filters (continued from Phase 4)
   "ma50_filter_enabled": request.ma50_filter_enabled,
   "circuit_breaker_atr_threshold": request.circuit_breaker_atr_threshold,
   "circuit_breaker_symbol": request.circuit_breaker_symbol,
   ```
3. **agent_config in create_comparison()** (`arena.py:698-716`): Add to `base_agent_config`:
   ```python
   "ibs_max_threshold": request.ibs_max_threshold,  # Phase 4
   "ma50_filter_enabled": request.ma50_filter_enabled,
   "circuit_breaker_atr_threshold": request.circuit_breaker_atr_threshold,
   "circuit_breaker_symbol": request.circuit_breaker_symbol,
   ```
   **Comparison route full parity**: `base_agent_config` must include ALL filter fields so comparison simulations support IBS, MA50, and circuit breaker identically to single simulations.
4. **_build_simulation_response()** (`arena.py:78-155`): Extract and return:
   ```python
   ma50_filter_enabled = agent_config.get("ma50_filter_enabled", False)
   circuit_breaker_atr_threshold = agent_config.get("circuit_breaker_atr_threshold")
   circuit_breaker_symbol = agent_config.get("circuit_breaker_symbol", "SPY")
   ```
   Add to `SimulationResponse` (`schemas/arena.py:631`):
   ```python
   ma50_filter_enabled: bool = False
   circuit_breaker_atr_threshold: float | None = None
   circuit_breaker_symbol: str = "SPY"
   ```
   Add to `SimulationResponse(...)` constructor call.

   Add to `SnapshotResponse` (`schemas/arena.py:587`):
   ```python
   circuit_breaker_state: Literal["disabled", "clear", "triggered", "data_unavailable"] = "disabled"
   circuit_breaker_atr_pct: Decimal | None = None
   regime_state: str | None = None
   ```
   **Serialization note**: `Decimal | None` in Pydantic serializes to string in JSON. Frontend must expect `"2.8000"` not `2.8` for `circuit_breaker_atr_pct`. `circuit_breaker_state` is a plain string enum.

   Update `get_simulation` route snapshot constructor (`arena.py:449-464`):
   ```python
   SnapshotResponse(
       id=snap.id,
       snapshot_date=snap.snapshot_date,
       day_number=snap.day_number,
       cash=snap.cash,
       positions_value=snap.positions_value,
       total_equity=snap.total_equity,
       daily_pnl=snap.daily_pnl,
       daily_return_pct=snap.daily_return_pct,
       cumulative_return_pct=snap.cumulative_return_pct,
       open_position_count=snap.open_position_count,
       decisions=snap.decisions,
       circuit_breaker_state=snap.circuit_breaker_state,
       circuit_breaker_atr_pct=snap.circuit_breaker_atr_pct,
       regime_state=snap.regime_state,
   )
   ```
5. **step_day()**: Read from `simulation.agent_config` in the entry filter blocks (see 5a, 5b above)

### 5h. DB Migration

Add three columns to `arena_snapshots`:

```python
def upgrade() -> None:
    op.add_column(
        "arena_snapshots",
        sa.Column(
            "circuit_breaker_state",
            sa.String(20),
            nullable=False,
            server_default=sa.text("'disabled'"),
        ),
    )
    op.add_column("arena_snapshots", sa.Column("circuit_breaker_atr_pct", sa.Numeric(8, 4), nullable=True))
    op.add_column("arena_snapshots", sa.Column("regime_state", sa.String(10), nullable=True))

def downgrade() -> None:
    op.drop_column("arena_snapshots", "regime_state")
    op.drop_column("arena_snapshots", "circuit_breaker_atr_pct")
    op.drop_column("arena_snapshots", "circuit_breaker_state")
```

**Pre-existing snapshot compatibility**: Rows inserted before this migration receive `circuit_breaker_state='disabled'` from the server default, matching their actual state (no breaker config on those older simulations). `circuit_breaker_atr_pct` and `regime_state` default to `NULL`. API GET on pre-migration simulations must return 200 with these defaults -- asserted in the API test table below.

---

## Frontend Changes

The form is split into 3 tabs: **Setup** (symbols, dates, capital), **Agent** (agent type, scoring), **Portfolio** (strategy, constraints, tuning). Entry filters are in a collapsible "Entry Filters" section in the Portfolio tab (added in Phase 4).

### F1. TypeScript types (`types/arena.ts`)

**Simulation interface** (`types/arena.ts:36-83`):
```typescript
ma50_filter_enabled?: boolean;
circuit_breaker_atr_threshold?: number | null;
circuit_breaker_symbol?: string;
```

**CreateSimulationRequest** (`types/arena.ts:144-197`):
```typescript
ma50_filter_enabled?: boolean;
circuit_breaker_atr_threshold?: number;
circuit_breaker_symbol?: string;
```

**CreateComparisonRequest** (`types/arena.ts:214-249`):
```typescript
ma50_filter_enabled?: boolean;
circuit_breaker_atr_threshold?: number;
circuit_breaker_symbol?: string;
```

**Snapshot interface** (`types/arena.ts:121-134`):
```typescript
type CircuitBreakerState = "disabled" | "clear" | "triggered" | "data_unavailable";

// In the Snapshot interface:
circuit_breaker_state: CircuitBreakerState;            // Required; defaults to 'disabled' server-side
circuit_breaker_atr_pct?: string | null;  // Decimal serialized as string
regime_state?: string | null;
```

**DecisionEntry interface** (added in Phase 4) -- extend with Phase 5 annotations:
```typescript
export interface DecisionEntry {
  // Agent output
  action: string;
  score: number | null;
  reasoning: string | null;
  // Engine annotations
  portfolio_selected?: boolean;
  ibs_filtered?: boolean;       // Phase 4
  ibs_value?: number;           // Phase 4
  ma50_filtered?: boolean;      // Phase 5
  circuit_breaker_filtered?: boolean;  // Phase 5
}
```
Note: `AgentDecision` (`types/arena.ts:114-118`) remains unchanged -- it represents pure agent output.

### F2. ArenaSetupForm -- Portfolio tab (`ArenaSetupForm.tsx`)

Add MA50 toggle and circuit breaker fields to the existing "Entry Filters" collapsible section alongside the IBS threshold from Phase 4.

**MA50 toggle**: Use `<button aria-pressed>` pattern consistent with strategy cards (`ArenaSetupForm.tsx:859-918`). No new shadcn dependency needed.

**Circuit breaker fields**: Threshold input (number, gt 0) with unit hint label: "e.g., 2.8 for 2.8%". Symbol input (text, uppercase, validated). Show symbol field only when threshold is set.

**Validation**: Add `canSubmit` guard for CB symbol format: `pattern=/^[A-Z]{1,5}$/`. Reject submit if CB threshold is set but symbol is invalid. The input must auto-transform to uppercase on change. Show inline error for invalid formats (e.g., "BRK.B" -- dot-notation tickers are explicitly NOT supported by the pattern constraint; document this limitation).

**initialValues prop** (`ArenaSetupForm.tsx:36-58`): Add Phase 5 fields:
```typescript
initialValues?: {
  // ... existing fields ...
  ma50_filter_enabled?: boolean;
  circuit_breaker_atr_threshold?: number | null;
  circuit_breaker_symbol?: string;
};
```

### F3. ArenaConfigPanel

Display filter config when enabled.

### F4. ArenaDecisionLog

Display `ma50_filtered` and `circuit_breaker_filtered` annotations. Show circuit breaker info in a dedicated "Market Conditions" banner (not as symbol rows), including `circuit_breaker_state`, `circuit_breaker_atr_pct`, and `regime_state` from the snapshot. The banner renders BEFORE symbol decision rows and appears even when decisions is empty (no BUY candidates that day).

**Banner rendering by state:**

| `circuit_breaker_state` | Banner visibility | Visual treatment |
|-------------------------|-------------------|------------------|
| `disabled` | Hidden (no breaker configured) | n/a |
| `clear` | Shown, neutral/info style | "Market ATR: X.XX% (clear)" |
| `triggered` | Shown, alert/warning style | "Circuit breaker triggered: Market ATR X.XX% >= threshold. All entries blocked." |
| `data_unavailable` | Shown, distinct warning style (**different from triggered**) | "Circuit breaker bypassed: market data unavailable for {symbol} on this date. Entries proceeded without the safety gate." |

The `data_unavailable` styling must be visually distinct from both `clear` (calm) and `triggered` (blocking) so operators do not mistake a bypassed safety valve for either normal state. A subdued-but-attention-grabbing treatment (e.g., a yellow/amber banner with a warning icon) is appropriate; do not reuse the red/triggered styling.

**Analyst help text**: When a symbol shows `ibs_filtered=True` with no `ma50_filtered` annotation, add tooltip: "IBS filter caught this symbol before MA50 was evaluated. MA50 status unknown." This prevents analysts from misinterpreting the absence of `ma50_filtered` as an implicit MA50 pass.

### F5. Strategy Presets

After this phase, add `STRATEGY_PRESETS` constants and preset buttons to the **Setup tab header** (or above the tabs). A preset populates fields across all 3 tabs: stop type + sizing in Setup, scoring in Agent, filters + constraints in Portfolio. Add "Load Aggressive" / "Load Conservative" buttons that fill all fields at once.

**Overwrite semantics**: Preset buttons overwrite parametric fields only (stop type, sizing mode, ATR params, constraints, filter thresholds). They do NOT modify `selectedStrategies`, preserving comparison mode if active. They do NOT modify symbols, dates, or capital. Both presets include `circuit_breaker_symbol: "SPY"` to be self-contained. In comparison mode, all selected strategies receive the same preset parametric values -- this is correct and by design, as comparison mode compares portfolio selection strategies under identical execution parameters.

```typescript
const STRATEGY_PRESETS = {
  aggressive: {
    stop_type: "atr", atr_stop_multiplier: 2.0,
    take_profit_atr_mult: 3.0, max_hold_days: 4,
    sizing_mode: "risk_based", risk_per_trade_pct: 2.5,
    max_open_positions: 10, max_per_sector: 3,
    ibs_max_threshold: undefined,  // explicitly clear Phase 4 filter to prevent phantom state
    ma50_filter_enabled: true,
    circuit_breaker_atr_threshold: 2.8,
    circuit_breaker_symbol: "SPY",
  },
  conservative: {
    stop_type: "atr", atr_stop_multiplier: 2.5,
    take_profit_atr_mult: 2.5, max_hold_days: 5,
    sizing_mode: "risk_based", risk_per_trade_pct: 2.5,
    max_open_positions: 10, max_per_sector: 3,
    ibs_max_threshold: 0.55,
    ma50_filter_enabled: true,
    circuit_breaker_atr_threshold: 2.8,
    circuit_breaker_symbol: "SPY",
  },
};
```

### F6. Component complexity (recommended)

Consider extracting entry filter state into a custom hook (`useEntryFilterState`) to manage the growing number of `useState` calls in `ArenaSetupForm`. Not required for correctness but strongly recommended before the component becomes untestable.

---

## Testing

### Backend Unit Tests

| Test File | What to Test |
|-----------|-------------|
| test_simulation_engine.py | MA50 filter blocks entry when close < MA50 |
| test_simulation_engine.py | MA50 filter allows entry when close > MA50 |
| test_simulation_engine.py | **Boundary**: exactly 49 bars available -- MA50 inactive (filter skipped) |
| test_simulation_engine.py | **Boundary**: exactly 50 bars available -- MA50 active |
| test_simulation_engine.py | **Boundary**: 51+ bars available -- filter uses last 50 only (`ph[-50:]`) |
| test_simulation_engine.py | MA50 stale-close guard: `ph[-1].date != current_date` -- filter skipped |
| test_simulation_engine.py | Circuit breaker blocks ALL entries when market ATR% >= threshold; snapshot `circuit_breaker_state == "triggered"` |
| test_simulation_engine.py | **Boundary**: `market_atr_pct == threshold` -- fires (>= comparison), `state == "triggered"` |
| test_simulation_engine.py | Circuit breaker inactive when threshold is None; snapshot `circuit_breaker_state == "disabled"`, `atr_pct == None` |
| test_simulation_engine.py | Circuit breaker below threshold; snapshot `circuit_breaker_state == "clear"`, `atr_pct` populated |
| test_simulation_engine.py | **No-BUY day with market above threshold**: breaker still evaluates, snapshot `state == "triggered"` even though `buy_signals` was empty (auditability) |
| test_simulation_engine.py | **No-BUY day with market calm**: `state == "clear"`, `atr_pct` populated (proves evaluation is unconditional on `buy_signals`) |
| test_simulation_engine.py | **Fail-open with observability**: `market_atr_pct` is None -- entries proceed, snapshot `state == "data_unavailable"`, `atr_pct == None`, `WARNING` log emitted |
| test_simulation_engine.py | Auxiliary symbol cache loading for circuit breaker |
| test_simulation_engine.py | Resume lazy-load includes circuit breaker symbol |
| test_simulation_engine.py | Snapshot columns populated (`circuit_breaker_state`, `circuit_breaker_atr_pct`, `regime_state`) |
| test_simulation_engine.py | State transitions: over a multi-day simulation, assert state matches expectation per day (disabled/clear/triggered/data_unavailable mix) |
| test_simulation_engine.py | Filter annotations NOT stored as non-symbol keys in decisions |

### Filter Interaction Tests

| Test File | What to Test |
|-----------|-------------|
| test_simulation_engine.py | When circuit breaker fires: neither `ibs_filtered` nor `ma50_filtered` appear in decisions (IBS/MA50 don't run on empty buy_signals) |
| test_simulation_engine.py | When only IBS fires for symbol A: no `ma50_filtered` on symbol A |
| test_simulation_engine.py | When only MA50 fires for symbol B: no `ibs_filtered` on symbol B |

### API Tests

| Test File | What to Test |
|-----------|-------------|
| test_arena_api.py | POST with `ma50_filter_enabled=true`, `circuit_breaker_atr_threshold=2.8`, `circuit_breaker_symbol="SPY"` accepted |
| test_arena_api.py | GET returns new fields in response (simulation config and snapshot columns, including `circuit_breaker_state`) |
| test_arena_api.py | Invalid `circuit_breaker_symbol` pattern rejected with 422 |
| test_arena_api.py | Pre-existing snapshot compatibility: GET /simulations/{pre-migration-id} returns 200 after migration; `circuit_breaker_state="disabled"`, `circuit_breaker_atr_pct=null`, `regime_state=null` from DB defaults |
| test_arena_api.py | `SnapshotResponse` serializes `circuit_breaker_state` as one of the four enum values (no `None`/`null`) |

### Frontend Tests

| Scenario | Component | What to Test |
|----------|-----------|-------------|
| MA50 toggle state | ArenaSetupForm | Toggle on/off updates state correctly |
| MA50 in payload | ArenaSetupForm | `ma50_filter_enabled=true` included in submit payload |
| CB threshold shows symbol | ArenaSetupForm | Symbol field appears when CB threshold is set |
| CB symbol lowercase transform | ArenaSetupForm | Lowercase input auto-transforms to uppercase |
| CB symbol "BRK.B" error | ArenaSetupForm | Dot-notation ticker shows inline error |
| CB symbol validation blocks submit | ArenaSetupForm | Invalid symbol format blocks `canSubmit` |
| Preset populates across tabs | ArenaSetupForm | "Load Aggressive" / "Load Conservative" populate stop, sizing, filter fields |
| Preset preserves strategies | ArenaSetupForm | In comparison mode, preset does not modify `selectedStrategies` |
| Replay with MA50/CB fields | ArenaSetupForm | `initialValues` with MA50/CB fields pre-populates form correctly |
| Market Conditions banner (triggered) | ArenaDecisionLog | Banner renders with alert style when `state="triggered"`, shows ATR% from `circuit_breaker_atr_pct`, renders BEFORE symbol rows |
| Banner hidden when disabled | ArenaDecisionLog | No banner rendered when `state="disabled"` (breaker not configured) |
| Banner neutral when clear | ArenaDecisionLog | Banner renders with neutral/info style when `state="clear"`, shows ATR% value |
| Banner distinct for data_unavailable | ArenaDecisionLog | Banner renders with warning (not alert) style when `state="data_unavailable"`, message indicates the safety valve was bypassed, visually distinct from both clear and triggered |
| Banner with empty decisions | ArenaDecisionLog | Banner still renders when `state="triggered"` and decisions is empty (no BUY candidates that day) |
| Banner on no-BUY clear day | ArenaDecisionLog | Banner renders with clear state and ATR% when `state="clear"` even if decisions is empty (proves banner is keyed on state, not on decisions) |
| MA50 badge per symbol | ArenaDecisionLog | Shows `ma50_filtered` badge on filtered symbol entries |
| IBS-only tooltip | ArenaDecisionLog | Symbol with `ibs_filtered=True` and no `ma50_filtered` shows appropriate tooltip |
| Config panel MA50 | ArenaConfigPanel | Renders MA50 filter row when `ma50_filter_enabled=true` |
| Config panel CB | ArenaConfigPanel | Renders CB threshold and symbol when configured |
| Snapshot market conditions | ArenaDecisionLog | Shows `regime_state` and `circuit_breaker_atr_pct` from snapshot |
| Mock type consistency | ArenaDecisionLog.test | Mocks use `Record<string, DecisionEntry>` (not `AgentDecision`) |

### ALL-Features Integration Test

After this phase, add a comprehensive test with **engineered test data** guaranteeing each branch is exercised on specific days. 20-day simulation with ALL features active (ATR stop, ATR TP, max hold, breakeven, ratchet, risk-based sizing, win streak, IBS filter, MA50 filter, circuit breaker).

The test data must be ENGINEERED so each code path is provably exercised:
- A day where circuit breaker fires (SPY ATR% >= threshold) -- expect `state="triggered"`
- A day where circuit breaker is clear but buy_signals is empty -- expect `state="clear"` with populated `atr_pct` (unconditional-evaluation proof)
- A day where SPY data is deliberately missing -- expect `state="data_unavailable"` and WARNING log
- A day where IBS filters at least one symbol
- A day where MA50 filters at least one symbol
- A position that exits via ATR stop
- A position that exits via ATR take-profit
- A position that exits via max hold
Without engineered data, the test can pass without exercising any of the new features.

Verify:
- No crashes or accounting errors
- **Determinism regression guard**: two runs with identical config produce identical snapshot output. The engine has no randomness (no `random`, no `uuid`, no wall-clock in `step_day`; `simulation.symbols` preserves order; `sorted(all_dates)` for trading days). This test is a regression guard that catches future accidental introduction of non-determinism, not a proof of determinism.
  ```python
  async def test_all_features_deterministic():
      result_1 = await run_simulation_to_completion(all_features_config, seed_data)
      result_2 = await run_simulation_to_completion(all_features_config, seed_data)
      assert [(s.snapshot_date, s.total_equity, s.decisions) for s in result_1.snapshots] == \
             [(s.snapshot_date, s.total_equity, s.decisions) for s in result_2.snapshots]
  ```
- Each exit reason appears at least once (stop, TP, max-hold)
- Filter annotations present in decisions for the engineered days
- Market condition columns populated on snapshots
- Filter interaction: CB day shows only `circuit_breaker_filtered`, not `ibs_filtered` or `ma50_filtered`

## Known Limitations

- **MA50 inactive for first ~50 trading days**: When a symbol has fewer than 50 bars, filter is skipped. Log `logger.debug` warning. Document in schema field description.
- **Circuit breaker fail-open**: Missing SPY data causes circuit breaker to skip (not block), but the bypass is now explicit: snapshot `circuit_breaker_state="data_unavailable"`, a `logger.warning` is emitted, and the frontend banner surfaces a distinct warning. Operators can grep logs for this state or query snapshots to audit bypassed days.
- **CB symbol: dot-notation tickers not supported**: The `^[A-Z]{1,5}$` pattern rejects tickers like "BRK.B". This is a known limitation. Document in schema field description and show inline error in frontend.
- **Pre-existing snapshots unaffected**: After migration, old snapshots get `circuit_breaker_state='disabled'`, `circuit_breaker_atr_pct=NULL`, `regime_state=NULL` from DB defaults. The API serializes these correctly.

## Success Criteria

- [ ] MA50 filter blocks entries for stocks below their 50-day MA
- [ ] MA50 stale-close guard prevents silent pricing errors from data gaps
- [ ] Circuit breaker blocks all entries on high-volatility days (ATR% >= threshold); snapshot `circuit_breaker_state="triggered"`
- [ ] Circuit breaker boundary: `market_atr_pct == threshold` triggers (>= not >)
- [ ] Circuit breaker evaluates UNCONDITIONALLY on every trading day when configured, regardless of `buy_signals` content (auditability: no-BUY days with high ATR still record `state="triggered"`)
- [ ] Circuit breaker fail-open surfaces as explicit `circuit_breaker_state="data_unavailable"` in snapshot with `logger.warning` -- safety bypass is never invisible
- [ ] Frontend banner visually distinguishes `disabled` / `clear` / `triggered` / `data_unavailable` with distinct treatments
- [ ] Both independently toggleable (disabled by default)
- [ ] Filter decisions recorded in snapshots for transparency
- [ ] Market condition columns on snapshots (not in decisions dict)
- [ ] `regime_state` populated when regime filter is active, None otherwise
- [ ] Snapshot `circuit_breaker_atr_pct` serializes as string in JSON (Decimal)
- [ ] `circuit_breaker_state` column is NOT NULL with server default `'disabled'`; pre-migration snapshots survive
- [ ] Comparison simulations support all entry filters (full parity with single simulations)
- [ ] Strategy presets enable one-click aggressive/conservative setup (with `circuit_breaker_symbol: "SPY"`)
- [ ] Filter execution order: circuit breaker -> IBS -> MA50 -> portfolio selection
- [ ] ALL-features integration test passes with engineered deterministic data
- [ ] Determinism regression guard: two identical runs produce identical snapshots
- [ ] Replaying a simulation preserves MA50/CB config via initialValues
- [ ] `DecisionEntry` type used for snapshot decisions; `AgentDecision` unchanged
- [ ] CB symbol auto-uppercases input; "BRK.B" shows inline error
- [ ] Preset buttons preserve `selectedStrategies` in comparison mode
- [ ] Pre-existing snapshots render correctly after migration (DB defaults)
- [ ] Analyst tooltip for IBS-only filtered symbols (MA50 not evaluated)
