# ATR-Based Exit Strategies: Architectural Plan

Parent issue: #47 -- Implement ATR-Based Exit Strategies (Aggressive + Conservative)
Sub-phases: #48, #49, #50, #51, #52

## Overview

This plan covers the architecture for implementing two complete ATR-based trading strategies (aggressive and conservative) across five independently shippable phases. The system already has significant infrastructure in place -- Phases 1 and 2 are fully implemented in the current working tree. This plan validates the decomposition, identifies what remains, and designs the shared interfaces.

### Strategy Summary

| | Aggressive | Conservative |
|---|---|---|
| Trailing Stop | 2.0x ATR | 2.5x ATR |
| Take Profit | 3.0x ATR | 2.5x ATR |
| Max Hold | 4 days | 5 days |
| IBS Filter | No | Yes (< 0.55) |
| MA50 Filter | Yes | Yes |
| Circuit Breaker | Yes (ATR% < 2.8) | Yes (ATR% < 2.8) |
| Position Sizing | Risk-based (2.5%) | Risk-based (2.5%) |

### Current Implementation Status

- Phase 1 (#48): ATR-Based Trailing Stop -- COMPLETE
- Phase 2 (#49): Take Profit + Max Hold Period -- COMPLETE
- Phase 3 (#50): Risk-Based Position Sizing -- PARTIAL (fixed-pct sizing exists, risk-based and win streak missing)
- Phase 4 (#51): IBS Entry Filter -- NOT STARTED
- Phase 5 (#52): MA50 Filter + Market Circuit Breaker -- NOT STARTED

---

## Current State (with file:line references)

### Simulation Engine (`backend/app/services/arena/simulation_engine.py`)

The engine is the orchestrator. Its `step_day()` method processes one trading day:

1. Opens pending positions at today's open (lines 358-432)
2. Updates trailing stops for open positions (lines 436-453)
3. Checks exit conditions: stop hit (lines 455-475), breakeven/ratchet (lines 481-508), take profit (lines 510-560), max hold (lines 562-611)
4. Collects BUY signals from agent (lines 613-625)
5. Runs portfolio selection with constraints (lines 627-700)
6. Creates daily snapshot (lines 703-736)

Config extraction happens at the top of `step_day()` (lines 238-273). All feature flags are read from `simulation.agent_config` (a JSON column).

### Trailing Stop (`backend/app/services/arena/trailing_stop.py`)

Two implementations:
- `FixedPercentTrailingStop` (line 34): Fixed percentage below running high
- `AtrTrailingStop` (line 135): ATR-adaptive percentage, computed once at entry, then identical update mechanics

Both share `TrailingStopUpdate` result dataclass (line 18). The `_make_trail_multiplier()` helper (line 123) is shared.

### ATR Calculation (`backend/app/utils/technical_indicators.py:50`)

`calculate_atr_percentage(highs, lows, closes, period=14, price_override=None)` -- returns ATR as percentage of price. Used by:
- `SimulationEngine._calculate_symbol_atr_pct()` (simulation_engine.py:1090-1117)
- Portfolio selector's `QualifyingSignal.atr_pct` field

This is the shared ATR interface that all phases depend on.

### Agent Protocol (`backend/app/services/arena/agent_protocol.py`)

- `PriceBar` dataclass (line 46): date, open, high, low, close, volume
- `AgentDecision` dataclass (line 14): symbol, action, score, reasoning, metadata
- `BaseAgent.evaluate()` (line 105): receives `price_history: list[PriceBar]`, returns `AgentDecision`

### Live20 Agent (`backend/app/services/arena/agents/live20_agent.py`)

- Evaluates 5 criteria via `Live20Evaluator` (line 165)
- Returns BUY when trend eligible AND score >= min_buy_score (line 196)
- Enriches BUY signals with metadata for portfolio selection (lines 204-224)
- Does NOT currently apply any entry filters beyond score threshold

### Models (`backend/app/models/arena.py`)

- `ArenaSimulation.agent_config`: JSON column (line 106) -- all new config stored here, no migration needed for new params
- `ArenaPosition.trailing_stop_pct`: per-position Decimal (line 276) -- set at entry for ATR stops
- `ExitReason` enum (line 48): already has STOP_HIT, SIMULATION_END, INSUFFICIENT_CAPITAL, TAKE_PROFIT, MAX_HOLD

### Schemas (`backend/app/schemas/arena.py`)

- `CreateSimulationRequest` (line 59): already has fields for stop_type, atr_stop_multiplier, take_profit_atr_mult, max_hold_days, position_size_pct, breakeven/ratchet, regime filter
- All fields are plumbed to `agent_config` dict in `api/v1/arena.py:237-272`

### Portfolio Selector (`backend/app/services/portfolio_selector.py`)

- `QualifyingSignal` (line 29): symbol, score, sector, atr_pct, metadata
- `PortfolioSelector._apply_constraints()` (line 88): enforces sector cap + position limit
- Existing selectors: FifoSelector, ScoreSectorSelector, EnrichedScoreSelector

---

## Shared ATR Interface Design

ATR(14) is the shared input for trailing stops, take profit, and position sizing. The data flow is already well-designed:

```
Price Cache (in-memory)
    |
    v
_calculate_symbol_atr_pct(simulation_id, symbol, current_date)
    |                               [simulation_engine.py:1090]
    |                               Uses 90-day window, 14-period Wilder's ATR
    |                               Returns float | None
    |
    +---> Trailing stop init (at position open)
    |         AtrTrailingStop.calculate_initial_stop(entry_price, atr_pct)
    |         Result: trail_pct stored on ArenaPosition.trailing_stop_pct
    |
    +---> Take profit check (each day, for open positions)
    |         atr_target = take_profit_atr_mult * current_atr_pct
    |         Triggered when unrealized_return_pct >= atr_target
    |
    +---> Position sizing (Phase 3 -- NEW)
    |         stop_distance = trail_multiplier * atr_pct * entry_price
    |         shares = (equity * risk_pct) / stop_distance
    |
    +---> QualifyingSignal.atr_pct (for portfolio selection ranking)
```

### Design Decisions

1. **ATR is computed fresh each call** via `_calculate_symbol_atr_pct()`. This is correct -- ATR changes daily and different use-sites may evaluate on different dates.

2. **Per-position trail_pct is frozen at entry** on `ArenaPosition.trailing_stop_pct`. This is correct -- the stop distance should not change after entry (only the stop price moves up).

3. **Per-day ATR memoization in step_day().** With `stop_type="atr"` + `take_profit_atr_mult` + `sizing_mode="risk_based"`, `_calculate_symbol_atr_pct()` is called 3-4x per symbol per day, each creating a list slice and running the ATR calculation. For 66 symbols x 250 days = ~50-66k redundant operations. Add a local dict at the top of `step_day()` to memoize ATR per symbol for the current day:

```python
# Per-day ATR cache (cleared each step_day call, avoids redundant calculation)
_day_atr_cache: dict[str, float | None] = {}

def _get_atr_for_day(symbol: str) -> float | None:
    if symbol not in _day_atr_cache:
        _day_atr_cache[symbol] = self._calculate_symbol_atr_pct(
            simulation_id, symbol, current_date
        )
    return _day_atr_cache[symbol]
```

This is a local optimization within step_day(), not a class-level cache. It does not survive across days (ATR changes daily).

4. **Risk-based sizing (Phase 3) reuses the same ATR path.** The stop distance for sizing = `atr_stop_multiplier * atr_pct * entry_price`. This is the same ATR value used by `AtrTrailingStop.calculate_initial_stop()`, so sizing and stop are always consistent.

---

## Phase-by-Phase Architecture

### Phase 1: ATR-Based Trailing Stop (#48) -- COMPLETE

**Status**: Fully implemented in current working tree.

**What exists**:
- `AtrTrailingStop` class with calculate_initial_stop() and update()
- Schema fields: stop_type, atr_stop_multiplier, atr_stop_min_pct, atr_stop_max_pct
- Engine wiring: stop type dispatch, ATR init at position open, per-position trail_pct
- Graceful fallback to fixed stop when ATR data unavailable
- Tests in test_trailing_stop.py

**Dependencies on prior phases**: None (first phase).

**What ships**: Simulations can use `stop_type="atr"` with configurable multiplier.

---

### Phase 2: Take Profit + Max Hold Period (#49) -- COMPLETE

**Status**: Fully implemented in current working tree.

**What exists**:
- Fixed-% TP (take_profit_pct) and ATR-multiple TP (take_profit_atr_mult)
- Max hold period (max_hold_days) with profitable position extension (max_hold_days_profit)
- Exit priority: trailing stop -> take profit -> max hold (correct order in step_day)
- ExitReason.TAKE_PROFIT and ExitReason.MAX_HOLD already in enum
- Schema fields for all four parameters

**Dependencies on prior phases**: Uses ATR from Phase 1 for ATR-multiple TP.

**What ships**: Simulations can use ATR-based take profit and max hold period exits.

**TP trigger behavior (canonical definition)**: The current implementation checks TP against `today_bar.close` (simulation_engine.py:514-518). Issue #49 specifies TP should trigger when "intraday high reaches entry + TP target" with gap-up handling at open.

Decision: **Update the TP trigger to use `today_bar.high` for the trigger check.** The exit price should be `min(tp_target_price, today_bar.open)` -- if the stock gaps up past the TP target on open, exit at open; otherwise exit at the TP target price. This matches the issue spec and standard backtesting methodology. The change is localized to simulation_engine.py:514-518:
- Trigger condition: `today_bar.high >= entry_price + tp_target` (or equivalently, unrealized return at high >= threshold)
- Exit price for fixed-% TP: `min(entry_price * (1 + take_profit_pct/100), today_bar.open)` (gap-up handling)
- Exit price for ATR TP: `min(entry_price * (1 + atr_target/100), today_bar.open)` (gap-up handling)

This is a Phase 2 fix that should be completed before Phase 3 risk-based sizing, since sizing validation backtests depend on correct TP behavior.

---

### Phase 3: Risk-Based Position Sizing (#50) -- REMAINING WORK

**Status**: Partially implemented. Fixed-pct sizing (`position_size_pct`) exists. Missing: risk-based volatility-adjusted sizing and consecutive win scaling.

**What changes, where**:

#### 3a. Risk-Based Sizing Formula

Location: `simulation_engine.py`, position open block (lines 362-377).

Currently:
```python
if position_size_pct is not None:
    effective_position_size = current_equity * Decimal(str(position_size_pct / 100))
else:
    effective_position_size = simulation.position_size
```

New sizing mode (`sizing_mode="risk_based"`):
```python
# stop_distance_per_share = atr_stop_multiplier * atr_pct / 100 * entry_price
# risk_amount = current_equity * risk_pct / 100
# shares = risk_amount / stop_distance_per_share
```

This requires ATR to be known at position open time -- which it already is, since ATR trailing stop init happens in the same block. The ATR value can be computed once and used for both stop init and sizing.

**Zero ATR guard**: When `atr_pct` is `None` or near-zero (< 0.01), `stop_distance_per_share` would be zero or undefined, causing a division-by-zero crash. Guard:
```python
if symbol_atr_pct is None or symbol_atr_pct < 0.01:
    # Fall back to fixed position_size when ATR data is unavailable or degenerate
    effective_position_size = simulation.position_size
else:
    stop_distance_per_share = atr_stop_multiplier * symbol_atr_pct / 100 * entry_price
    risk_amount = current_equity * Decimal(str(effective_risk / 100))
    calculated_shares = int(risk_amount / stop_distance_per_share)
```

**`sizing_mode` + `stop_type` interaction**: Risk-based sizing computes `shares = risk_amount / stop_distance`, where stop distance is derived from ATR. This formula is only meaningful when the actual trailing stop also uses ATR -- otherwise the sizing is calibrated to a stop distance that does not match the real stop, producing undefined risk exposure.

Valid combinations:
- `sizing_mode="risk_based"` + `stop_type="atr"` -- intended usage, sizing and stop both calibrated to ATR
- `sizing_mode="risk_based"` + `stop_type="fixed"` -- REJECTED at schema validation. No well-defined risk formula exists for fixed stops.
- `sizing_mode="fixed"` or `"fixed_pct"` + any `stop_type` -- no interaction, sizing ignores ATR

Schema validator (add to BOTH `CreateSimulationRequest` and `CreateComparisonRequest`):
```python
@model_validator(mode="after")
def validate_sizing_stop_combination(self):
    if getattr(self, "sizing_mode", "fixed") == "risk_based" and getattr(self, "stop_type", "fixed") != "atr":
        raise ValueError("sizing_mode='risk_based' requires stop_type='atr'")
    return self
```

**Sizing mode precedence**: `sizing_mode` is the authoritative field. When explicitly set:
- `"fixed"` -- uses `simulation.position_size` (ignores `position_size_pct`)
- `"fixed_pct"` -- uses `position_size_pct` percentage of equity
- `"risk_based"` -- uses risk formula above

For backward compatibility with simulations created before `sizing_mode` existed: if `sizing_mode` is absent from `agent_config` (old simulations), fall back to the legacy behavior: check `position_size_pct` -- if set, use it; otherwise use fixed `position_size`. This preserves exact behavior for all existing simulations.

```python
sizing_mode = simulation.agent_config.get("sizing_mode")
if sizing_mode is None:
    # Legacy fallback: pre-sizing_mode simulations
    if position_size_pct is not None:
        sizing_mode = "fixed_pct"
    else:
        sizing_mode = "fixed"
```

New config keys in `agent_config`:
- `sizing_mode`: "fixed" | "fixed_pct" | "risk_based" (default: "fixed")
- `risk_per_trade_pct`: float (default: 2.5)
- `win_streak_bonus_pct`: float (default: 0.3)
- `max_risk_pct`: float (default: 4.0)

#### 3b. Consecutive Win Streak Tracking

The win streak counter must persist across trading days within a simulation. Options:

**Option A: In-memory counter on SimulationEngine** -- Reset on resume. Not viable for crash recovery.

**Option B: New column on ArenaSimulation model** -- `consecutive_wins: int`. Requires DB migration. Updated whenever a position closes (win increments, loss resets to 0).

**Option C: Compute from closed positions** -- Query closed positions ordered by exit_date, count consecutive wins from the end. No migration, but O(n) query per position open.

**Recommended: Option B.** A single integer column is cheap, survives crashes, and is O(1) to read. The migration is trivial (add nullable int column with default 0).

Location for win streak update: After each position close in step_day() (lines 471-474 for stop hit, lines 556-558 for TP, lines 607-609 for max hold). Add:
```python
if realized_pnl > 0:
    simulation.consecutive_wins += 1
else:
    simulation.consecutive_wins = 0
```

Location for risk calculation: Position open block, compute effective risk:
```python
base_risk = risk_per_trade_pct
streak_bonus = simulation.consecutive_wins * win_streak_bonus_pct
effective_risk = min(base_risk + streak_bonus, max_risk_pct)
```

#### 3c. Hard Limits (Position Cap, Sector Cap)

These already exist in the portfolio selector (`_apply_constraints()` at portfolio_selector.py:88). The issue specifies "max 10 open positions" and "max 3 per sector" as defaults for risk-based mode. These map directly to existing `max_open_positions` and `max_per_sector` fields.

No new code needed -- just documentation that risk-based mode should be used with `max_open_positions=10` and `max_per_sector=3`.

#### 3d. Schema Changes

New fields on `CreateSimulationRequest`:
- `sizing_mode: str = "fixed"` (validates: "fixed", "fixed_pct", "risk_based")
- `risk_per_trade_pct: float = 2.5` (gt=0, le=10)
- `win_streak_bonus_pct: float = 0.3` (ge=0, le=2)
- `max_risk_pct: float = 4.0` (gt=0, le=10)

#### 3e. DB Migration

Single migration: add `consecutive_wins` integer column (default 0) to `arena_simulations`.

**Dependencies on prior phases**: Requires ATR from Phase 1 for stop distance calculation. Independent of Phase 2 (TP/max hold).

**What ships**: Simulations can use risk-based position sizing where volatile stocks get smaller positions.

---

### Phase 4: IBS Entry Filter (#51) -- NEW

**Status**: Not started.

**What changes, where**:

#### 4a. IBS Calculation

IBS is trivial: `(close - low) / (high - low)`. No need for a separate utility function -- it is a one-liner. Add a static helper on SimulationEngine or compute inline.

Edge case: if `high == low` (zero range day), IBS defaults to 0.5 (neutral).

#### 4b. Where to Apply the Filter

**Decision: Apply in simulation_engine.py, not in the agent.**

Rationale:
- The agent (`Live20ArenaAgent.evaluate()`) is responsible for signal generation (score-based BUY/NO_SIGNAL). Entry filters are a separate concern -- they gate whether a signal is acted upon, not whether it exists.
- Keeping filters in the engine means the agent's `AgentDecision` still carries the BUY signal with its score, and the snapshot `decisions` dict can record that a BUY was generated but filtered. This is valuable for analysis ("how many entries did IBS block?").
- This matches the existing pattern: the regime filter and portfolio selector both operate in the engine, downstream of agent decisions.

Location: After BUY signal collection (simulation_engine.py:624) and before portfolio selection (line 627). Add a filter pass:

```python
# --- Entry Filters ---
ibs_max = simulation.agent_config.get("ibs_max_threshold")
if ibs_max is not None:
    filtered_buy_signals = []
    for symbol, decision in buy_signals:
        today_bar = self._get_cached_bar_for_date(simulation_id, symbol, current_date)
        if today_bar and today_bar.high != today_bar.low:
            ibs = float((today_bar.close - today_bar.low) / (today_bar.high - today_bar.low))
        else:
            ibs = 0.5  # zero-range day = neutral
        if ibs < ibs_max:
            filtered_buy_signals.append((symbol, decision))
        else:
            decisions[symbol]["ibs_filtered"] = True
            decisions[symbol]["ibs_value"] = round(ibs, 4)
            decisions[symbol]["portfolio_selected"] = False  # explicit for frontend
    buy_signals = filtered_buy_signals
```

Similarly, MA50-filtered and circuit-breaker-filtered signals must also set `portfolio_selected = False` explicitly to prevent frontend `None` issues when rendering signal status.

#### 4c. Schema Changes

New fields on `CreateSimulationRequest`:
- `ibs_max_threshold: float | None = None` (ge=0, le=1). None = disabled.

Single field design: if the field is None, IBS filter is off. If set (e.g., 0.55), filter is active. No need for a separate boolean toggle -- None/non-None is the toggle.

#### 4d. No DB Migration

All config stored in `agent_config` JSON. No model changes needed.

**Dependencies on prior phases**: None. IBS is independent of ATR, TP, sizing. Can be shipped in any order after the base engine exists.

**What ships**: Conservative strategy entry filter. Simulations with `ibs_max_threshold=0.55` will reject entries where the stock closed near its high.

---

### Phase 5: MA50 Filter + Market Volatility Circuit Breaker (#52) -- NEW

**Status**: Not started.

**What changes, where**:

#### 5a. MA50 Filter

Calculation: 50-day SMA of closing prices. The codebase already has `calculate_sma()` in `technical_indicators.py:13`, but it operates on pandas DataFrames. For the simulation engine (which uses lists of PriceBars), a simpler approach is to compute inline from the price cache:

```python
closes = [float(bar.close) for bar in price_history[-50:]]
ma50 = sum(closes) / len(closes) if len(closes) >= 50 else None
```

Location: Same entry filter block as IBS (after BUY signal collection, before portfolio selection). Applied per-symbol. Note: `price_history` is a local variable scoped to the per-symbol agent evaluation loop above and is NOT available in the post-loop filter block. The filter must explicitly fetch price data from the cache:

```python
if ma50_filter_enabled:
    filtered_buy_signals = []
    for symbol, decision in buy_signals:
        ph = self._get_cached_price_history(
            simulation_id, symbol,
            current_date - timedelta(days=90), current_date,
        )
        if ph and len(ph) >= 50:
            closes = [float(bar.close) for bar in ph[-50:]]
            ma50 = sum(closes) / len(closes)
            today_close = float(ph[-1].close)
            if today_close < ma50:
                decisions[symbol]["ma50_filtered"] = True
                decisions[symbol]["portfolio_selected"] = False
                continue
        # else: insufficient data for MA50, allow entry (log warning)
        filtered_buy_signals.append((symbol, decision))
    buy_signals = filtered_buy_signals
```

When price history has fewer than 50 bars (simulation start or short-history stock), the MA50 filter is inactive for that symbol. Log a debug warning. Document this in the schema field description.

Note: Issue #52 says "only buy stocks above their 50-day MA" which means `close > MA50`. This is a trend-following filter, not mean-reversion. The existing Live20 agent already checks for uptrend eligibility via 10-day trend, but MA50 is a longer-term filter.

#### 5b. Market ATR% Circuit Breaker

This is conceptually similar to the existing regime filter (simulation_engine.py:633-647) but uses ATR% instead of SMA crossover.

Calculation: ATR(14) percentage of a market proxy (e.g., SPY). If market ATR% exceeds threshold, block all new entries for that day.

Location: After the per-symbol BUY signal collection loop (after line 625) and before the entry filter block (IBS, MA50) and portfolio selection. The circuit breaker operates on the populated `buy_signals` list -- placing it before the loop would be a no-op since `buy_signals` is built inside the loop.

```python
# --- Circuit Breaker (day-level gate, checked before per-symbol filters) ---
circuit_breaker_threshold = simulation.agent_config.get("circuit_breaker_atr_threshold")
if circuit_breaker_threshold is not None and buy_signals:
    market_symbol = simulation.agent_config.get("circuit_breaker_symbol", "SPY")
    market_atr_pct = self._calculate_symbol_atr_pct(simulation_id, market_symbol, current_date)
    if market_atr_pct is not None and market_atr_pct >= circuit_breaker_threshold:
        # Block all new entries -- mark each filtered signal for transparency
        for symbol, decision in buy_signals:
            decisions[symbol]["circuit_breaker_filtered"] = True
        buy_signals = []
```

**Snapshot market conditions -- dedicated ArenaSnapshot columns**: Day-level metadata (circuit breaker, regime state) is stored as dedicated typed columns on `ArenaSnapshot`, NOT inside the `decisions` dict. Storing non-symbol keys in `decisions` breaks any code iterating `decisions.items()` (including `ArenaDecisionLog` rendering). Dedicated columns are queryable, typed, and render cleanly in a separate "Market Conditions" frontend section without key-iteration guards.

New columns on `ArenaSnapshot` (added in Phase 5 migration):
```python
circuit_breaker_triggered: Mapped[bool] = mapped_column(
    Boolean, nullable=False, default=False,
    doc="Whether circuit breaker blocked entries this day",
)
circuit_breaker_atr_pct: Mapped[Decimal | None] = mapped_column(
    Numeric(precision=8, scale=4), nullable=True,
    doc="Market proxy ATR% this day (for circuit breaker display)",
)
regime_state: Mapped[str | None] = mapped_column(
    String(10), nullable=True,
    doc="Market regime this day: 'bull' or 'bear' (None = regime filter disabled)",
)
```

Written in `step_day()` when creating the snapshot:
```python
snapshot = ArenaSnapshot(
    ...,
    circuit_breaker_triggered=cb_triggered,
    circuit_breaker_atr_pct=Decimal(str(round(market_atr_pct, 4))) if cb_threshold else None,
    regime_state=regime if regime_filter_enabled else None,
)
```

The `SnapshotResponse` schema also gets these three new fields. Per-symbol filter annotations (`ibs_filtered`, `ma50_filtered`, `circuit_breaker_filtered`, `portfolio_selected`) remain in `decisions[symbol]` since they ARE per-symbol data.

**Data dependency**: The market proxy (SPY) must be in the price cache even if not in the simulation's symbol list. This matches the existing pattern for regime filter, which already loads the regime symbol separately via `_load_regime_symbol_cache()` (simulation_engine.py:138-144). The circuit breaker can reuse the same mechanism, or share the regime symbol's cache if they use the same proxy.

Design choice: If both regime filter and circuit breaker use SPY, they share the same cache entry. If different symbols, each gets its own cache load. The `_load_regime_symbol_cache()` method (simulation_engine.py:967-1022) already handles loading a non-simulation symbol into the price cache.

#### 5c. Schema Changes

New fields on `CreateSimulationRequest`:
- `ma50_filter_enabled: bool = False`
- `circuit_breaker_atr_threshold: float | None = None` (gt=0). None = disabled.
- `circuit_breaker_symbol: str = "SPY"` (max_length=10)

#### 5d. Price Cache for Circuit Breaker Symbol

At simulation initialization (`initialize_simulation()`), if `circuit_breaker_atr_threshold` is set and `circuit_breaker_symbol` is not in the simulation's symbol list, load it into the price cache. This mirrors the regime filter pattern at simulation_engine.py:137-144.

Can either:
- Reuse `_load_regime_symbol_cache()` directly (rename to `_load_auxiliary_symbol_cache()`)
- Or add a separate call with the same pattern

Recommended: Generalize the helper. Both regime filter and circuit breaker need the same thing -- load a non-simulation symbol into the price cache with sufficient lookback for their indicator period.

#### 5e. Lazy-Load on Resume

The circuit breaker symbol pre-load happens in `initialize_simulation()`. On crash/resume, `initialize_simulation()` is skipped (it is idempotent and returns early if already initialized). The `step_day()` lazy-load guard (simulation_engine.py:276-293) covers simulation symbols and the regime filter symbol, but does NOT currently cover auxiliary symbols added by new features.

Add the circuit breaker symbol to the lazy-load guard in `step_day()`, mirroring the existing regime filter pattern:

```python
# Existing regime filter lazy-load (line 285-292)
if simulation.agent_config.get("regime_filter", False):
    await self._load_regime_symbol_cache(...)

# Add: circuit breaker symbol lazy-load
cb_threshold = simulation.agent_config.get("circuit_breaker_atr_threshold")
if cb_threshold is not None:
    cb_symbol = simulation.agent_config.get("circuit_breaker_symbol", "SPY")
    await self._load_auxiliary_symbol_cache(simulation_id, cb_symbol, ...)
```

Without this, a resumed simulation with circuit breaker enabled would silently skip the breaker check (safe but incorrect).

#### 5f. DB Migration

Add three columns to `arena_snapshots` for market condition tracking (see Schema/Migration Strategy section). Config params (ma50_filter_enabled, circuit_breaker_atr_threshold, circuit_breaker_symbol) stored in `agent_config` JSON as usual.

**Dependencies on prior phases**: None for MA50 filter. Circuit breaker reuses `_calculate_symbol_atr_pct()` from Phase 1 infrastructure (but that already exists). Both are independent entry filters.

**What ships**: Full entry rule set -- stocks must be in uptrend (MA50) and market must not be too volatile (circuit breaker). Completes both aggressive and conservative strategies.

---

## Schema/Migration Strategy

### DB Migrations Required

Two migrations across all five phases:

**Phase 3 migration**: Add `consecutive_wins` column to `arena_simulations` table.
```sql
ALTER TABLE arena_simulations ADD COLUMN consecutive_wins INTEGER NOT NULL DEFAULT 0;
```
Known limitation: in-progress simulations at migration time will start with `consecutive_wins = 0`, which may not reflect their actual streak. Document this in the migration file. Acceptable because win streak is a marginal sizing adjustment, not a correctness issue.

**Phase 5 migration**: Add market condition columns to `arena_snapshots` table.
```sql
ALTER TABLE arena_snapshots ADD COLUMN circuit_breaker_triggered BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE arena_snapshots ADD COLUMN circuit_breaker_atr_pct NUMERIC(8,4) NULL;
ALTER TABLE arena_snapshots ADD COLUMN regime_state VARCHAR(10) NULL;
```
Dedicated typed columns are queryable and render cleanly in the frontend without JSON parsing. If Phases 3 and 5 ship close together, both migrations can be combined.

Both migrations are backwards-compatible (nullable/default-safe). Existing simulations and snapshots are unaffected. Both are independently rollbackable.

### Why No Other Migrations

All other new configuration (IBS threshold, MA50 filter, circuit breaker, risk-based sizing params) goes into `ArenaSimulation.agent_config` -- a JSON column (models/arena.py:106). This is the established pattern: every "Layer" (stop type, TP, max hold, breakeven, ratchet, regime filter, position sizing) stores its config in this JSON dict.

New fields are added to `CreateSimulationRequest` in the schema (schemas/arena.py), validated by Pydantic, then plumbed into `agent_config` in the API route (api/v1/arena.py:237-272). The simulation engine reads them from `agent_config` at runtime.

### Schema Field Addition Pattern (Mandatory 5-Step Process)

For each new feature, ALL five steps are required:

1. Add field(s) to `CreateSimulationRequest` (schemas/arena.py) with sensible defaults and validators
2. Add the SAME field(s) to `CreateComparisonRequest` (schemas/arena.py) -- the comparison endpoint is the primary use case for #47 (aggressive vs conservative comparison). Omitting fields from `CreateComparisonRequest` makes the comparison endpoint unable to create ATR strategy simulations.
3. Wire field(s) into `agent_config` dict in `create_simulation()` API route (api/v1/arena.py:237-272). Also wire in `create_comparison()`.
4. Extract field(s) from `agent_config` in `_build_simulation_response()` (api/v1/arena.py:78-137) AND add corresponding field(s) to `SimulationResponse` schema (schemas/arena.py:495). Without this step, the frontend cannot display config, replay simulations, or distinguish simulation types.
5. Read from `simulation.agent_config` in `step_day()`

Step 4 is mandatory, not optional. Every config parameter must be visible in the response. This affects all new parameters across Phases 3-5:
- Phase 3: sizing_mode, risk_per_trade_pct, win_streak_bonus_pct, max_risk_pct
- Phase 4: ibs_max_threshold
- Phase 5: ma50_filter_enabled, circuit_breaker_atr_threshold, circuit_breaker_symbol

### SimulationResponse Approach

Continue adding each new field as a top-level field on `SimulationResponse` (consistent with existing fields like `trailing_stop_pct`, `min_buy_score`, etc.). All new fields are `Optional` with `None` default for backward compatibility with older simulations that do not have these config keys.

Exact fields to add per phase (on both `SimulationResponse` and `_build_simulation_response()`):

**Phase 1** (already shipped, verify these exist):
- `stop_type: str | None`
- `atr_stop_multiplier: float | None`
- `atr_stop_min_pct: float | None`
- `atr_stop_max_pct: float | None`

**Phase 2** (already shipped, verify these exist):
- `take_profit_pct: float | None`
- `take_profit_atr_mult: float | None`
- `max_hold_days: int | None`
- `max_hold_days_profit: int | None`

**Phase 3** (new):
- `sizing_mode: str | None`
- `risk_per_trade_pct: float | None`
- `win_streak_bonus_pct: float | None`
- `max_risk_pct: float | None`

**Phase 4** (new):
- `ibs_max_threshold: float | None`

**Phase 5** (new):
- `ma50_filter_enabled: bool | None`
- `circuit_breaker_atr_threshold: float | None`
- `circuit_breaker_symbol: str | None`

Also update `SnapshotResponse` to include new `ArenaSnapshot` columns (Phase 5):
- `circuit_breaker_triggered: bool`
- `circuit_breaker_atr_pct: Decimal | None`
- `regime_state: str | None`

---

## Risk Assessment

### Risk 1: step_day() Complexity (MEDIUM)

`step_day()` is already ~460 lines and handles stops, TP, max hold, breakeven, ratchet, regime filter, and portfolio selection. Adding IBS filter, MA50 filter, circuit breaker, and risk-based sizing will push it further.

**Mitigation**: Each new feature is a self-contained block gated by a config check. The exit-check ordering (stop -> breakeven/ratchet -> TP -> max hold) and entry-filter ordering (circuit breaker -> IBS -> MA50 -> portfolio selection) are both linear pipelines. Consider extracting helper methods (e.g., `_apply_entry_filters()`, `_calculate_position_size()`) to keep step_day() readable without changing the architecture.

### Risk 2: TP Trigger Price -- RESOLVED

The TP trigger is now defined canonically in Phase 2 above: use `today_bar.high` for trigger check, `min(tp_target_price, today_bar.open)` for exit price. This is a required Phase 2 fix before Phase 3 work begins.

### Risk 3: Backward Compatibility of Existing Simulations (LOW)

All new features use `None` or `False` as defaults (disabled by default). Existing simulations that do not set new config keys will behave identically. The `agent_config` JSON dict is read with `.get()` and default fallbacks throughout the engine.

No risk of breaking existing simulations.

### Risk 4: Win Streak Persistence Across Crash/Resume (LOW)

If the simulation engine crashes mid-day, the entire day's changes are rolled back (step_day is transactional -- single commit at line 790). The `consecutive_wins` counter is updated in the same transaction as position closes, so it is always consistent.

On resume, the counter is read from DB (it was committed with the last successful day). No data loss.

### Risk 5: Circuit Breaker Symbol Not in Price Cache (LOW)

If circuit breaker uses a symbol not in the simulation's symbol list and the cache is not pre-loaded, `_calculate_symbol_atr_pct()` returns `None`, and the circuit breaker would not trigger (safe default).

**Mitigation**: Pre-load the circuit breaker symbol in `initialize_simulation()`, matching the regime filter pattern.

### Risk 6: Entry Filter Interaction Effects (MEDIUM)

With IBS, MA50, circuit breaker, regime filter, and portfolio selector all gating entries, there is risk of over-filtering where very few trades execute. This is a strategy tuning concern, not an architecture concern.

**Mitigation**: Record filter decisions in snapshot `decisions` dict (e.g., `ibs_filtered: true`, `ma50_filtered: true`, `circuit_breaker_triggered: true`). This enables post-simulation analysis of which filters blocked which signals.

---

## Testing Strategy

### Unit Test Locations

| Phase | Test File | What to Test |
|-------|-----------|-------------|
| 2 (fix) | test_simulation_engine.py | TP trigger uses high price, exit at min(target, open) for gap-up |
| 3 | test_simulation_engine.py | Risk-based sizing formula, win streak increment/reset, sizing cap, zero-ATR fallback |
| 3 | test_simulation_engine.py | sizing_mode precedence: explicit > legacy position_size_pct detection |
| 4 | test_simulation_engine.py | IBS calculation, filter gating, zero-range edge case, disabled behavior, portfolio_selected=False |
| 5 | test_simulation_engine.py | MA50 filter, circuit breaker trigger/no-trigger, aux symbol cache loading, resume lazy-load |
| 5 | test_simulation_engine.py | Dedicated snapshot columns (circuit_breaker_triggered, regime_state populated, NOT in decisions dict) |
| 3 | test_portfolio_selector.py | No changes needed (existing constraints cover sector/position caps) |

### Test Patterns (follow existing conventions)

Existing tests use:
- `pytest` with `@pytest.mark.asyncio` for async tests
- `AsyncMock` session factory + `MagicMock` sessions
- Direct instantiation of `SimulationEngine` with mocked dependencies
- Isolated feature tests (e.g., test_trailing_stop.py tests stop logic without DB)

For new features:
- Each entry filter gets isolated tests: enabled/disabled, threshold boundary, edge cases
- Risk-based sizing: test formula correctness, win streak scaling, cap enforcement
- Integration-style tests in test_simulation_engine.py: run a multi-day simulation with feature enabled, verify positions are sized/filtered correctly

### Required Integration Test: ALL Features Enabled

After Phase 5, add a comprehensive integration test that runs a 20-day simulation with ALL features active simultaneously: ATR stop, ATR TP, max hold, breakeven, ratchet, risk-based sizing, win streak, IBS filter, MA50 filter, and circuit breaker. This verifies:
- No feature interactions cause crashes or accounting errors
- Deterministic results (same config = same P&L)
- All exit reasons appear correctly
- Filter annotations present in snapshot decisions
- Market condition columns populated on snapshots

### Test Audit: Decisions Dict Assertions

Before Phase 4 ships, audit all existing tests in `test_simulation_engine.py` for exact `decisions[symbol] == {...}` equality assertions. Adding new keys (`ibs_filtered`, `ma50_filtered`, `portfolio_selected`) to the decisions dict will break these tests. Update to use key-specific assertions (e.g., `assert decisions[symbol]["action"] == "BUY"`) instead of full dict equality.

### Regression Testing

Run the full existing test suite after each phase to verify backward compatibility:
```bash
./scripts/dc.sh exec backend-dev pytest tests/unit/services/arena/
./scripts/dc.sh exec backend-dev pytest tests/unit/services/test_portfolio_selector.py
```

### Backtest Validation

After Phase 3 (risk-based sizing) is complete, run a full backtest with the aggressive strategy config:
- `stop_type="atr"`, `atr_stop_multiplier=2.0`
- `take_profit_atr_mult=3.0`, `max_hold_days=4`
- `sizing_mode="risk_based"`, `risk_per_trade_pct=2.5`
- `max_open_positions=10`, `max_per_sector=3`

Compare against research results (2025: +41.5%, 155 trades, 10.3% max DD).

After Phase 5 (all filters), run both aggressive and conservative configs and compare to #47 targets.

---

## Backend Refactoring (Required Before or During Phase 3)

### Extract `_close_position()` Helper

The position close logic (update status, set exit fields, return cash, increment trade counters, update win streak) is duplicated in three separate blocks in `step_day()`: stop hit (lines 462-475), take profit (lines 536-560), and max hold (lines 588-611). If a new exit path is added and only updates one counter (`winning_trades` but not `consecutive_wins`), they silently diverge.

Extract a private helper:
```python
def _close_position(
    self,
    position: ArenaPosition,
    simulation: ArenaSimulation,
    exit_reason: ExitReason,
    exit_price: Decimal,
    exit_date: date,
    cash: Decimal,
) -> Decimal:
    """Close position and update all counters atomically. Returns updated cash."""
    realized_pnl = (exit_price - position.entry_price) * position.shares
    return_pct = (exit_price - position.entry_price) / position.entry_price * 100
    position.status = PositionStatus.CLOSED.value
    position.exit_date = exit_date
    position.exit_price = exit_price
    position.exit_reason = exit_reason.value
    position.realized_pnl = realized_pnl
    position.return_pct = return_pct
    simulation.total_trades += 1
    if realized_pnl > 0:
        simulation.winning_trades += 1
        simulation.consecutive_wins += 1
    else:
        simulation.consecutive_wins = 0
    return cash + position.shares * exit_price
```

This consolidates the win streak update (Phase 3) into one place, preventing counter divergence.

---

## Frontend Work (Per-Phase)

Each phase must include frontend tasks alongside backend implementation. These are NOT optional -- without them the features are invisible to users.

### Immediate Hotfix (Pre-Plan, File Separately)

The `ExitReason` TypeScript type in `types/arena.ts` is already broken. Phases 1 and 2 deployed `TAKE_PROFIT` and `MAX_HOLD` to the backend enum, but the frontend type only has `stop_hit | simulation_end | insufficient_capital`. Any simulation exiting via take profit or max hold shows broken display. This is a 5-line fix -- ship as a standalone hotfix ticket independent of this plan.

### Per-Phase Frontend Checklist

For each phase that adds schema fields, the following frontend tasks are required:

1. **TypeScript types**: Update `CreateSimulationRequest`, `Simulation`, `CreateComparisonRequest`, `SnapshotResponse` types to include new fields
2. **ArenaSetupForm**: Add form controls with progressive disclosure (collapsed by default, expand when non-default). Use `initialValues.field ?? defaultValue` pattern for replay hydration of old simulations missing new fields.
3. **ArenaConfigPanel**: Add display rows for new config values
4. **ArenaDecisionLog**: Display filter events (IBS, MA50, circuit breaker) when present in decisions or snapshot fields
5. **Test coverage**: Replay of old-schema simulation (missing new fields) must not crash. Circuit breaker info renders in dedicated section. Non-symbol keys never appear as symbol rows.

### Phase 5: Strategy Presets

The two exact strategy configurations (Aggressive and Conservative) each require 10+ parameters. Without preset buttons, users must manually configure each field. Add `STRATEGY_PRESETS` constants and "Load Aggressive" / "Load Conservative" buttons to `ArenaSetupForm`:

```typescript
const STRATEGY_PRESETS = {
  aggressive: {
    stop_type: "atr", atr_stop_multiplier: 2.0,
    take_profit_atr_mult: 3.0, max_hold_days: 4,
    sizing_mode: "risk_based", risk_per_trade_pct: 2.5,
    max_open_positions: 10, max_per_sector: 3,
    ma50_filter_enabled: true,
    circuit_breaker_atr_threshold: 2.8,
    // ibs_max_threshold: null (not used in aggressive)
  },
  conservative: {
    stop_type: "atr", atr_stop_multiplier: 2.5,
    take_profit_atr_mult: 2.5, max_hold_days: 5,
    sizing_mode: "risk_based", risk_per_trade_pct: 2.5,
    max_open_positions: 10, max_per_sector: 3,
    ibs_max_threshold: 0.55,
    ma50_filter_enabled: true,
    circuit_breaker_atr_threshold: 2.8,
  },
};
```

This enables one-click creation of the research-validated strategies.

---

## Known Limitations (Document in Code)

**D1. Win streak order-dependence**: When multiple positions close on the same day, `consecutive_wins` depends on symbol processing order (iteration order of `simulation.symbols`). This is deterministic (same config = same result) but the specific ordering is an implementation detail. Document in `step_day()` and test both orderings.

**D2. MA50 filter inactive for first ~50 trading days**: When a symbol has fewer than 50 bars of price history (early simulation days or short-history stock), the MA50 filter is inactive and allows entries that would otherwise be blocked. Add `logger.debug` warning when this occurs. Document in the `ma50_filter_enabled` schema field description. Consider surfacing in the frontend simulation detail view (e.g., "MA50 filter active from day N").

**D3. `consecutive_wins = 0` for in-progress simulations at migration time**: Simulations that are RUNNING when the Phase 3 migration runs will start with `consecutive_wins = 0` regardless of their actual streak. This is a known limitation -- document in the migration file. Acceptable because win streak is a marginal sizing adjustment (+0.3% per win), not a correctness issue.

---

## Success Criteria

1. **Phase 3**: Risk-based position sizing produces shares = risk_amount / stop_distance. Win streak scales risk correctly. Backtest results approximate research findings.

2. **Phase 4**: IBS filter reduces entries and drawdown when enabled. Simulations with `ibs_max_threshold=0.55` match conservative strategy profile (fewer trades, lower drawdown).

3. **Phase 5**: MA50 filter blocks entries for stocks below their 50MA. Circuit breaker blocks all entries on high-volatility days. Both are independently toggleable.

4. **All phases**: Backward compatible -- existing simulations produce identical results. All new features disabled by default. Filter decisions recorded in snapshot decisions for transparency.

5. **End state**: Can run both aggressive (`ma50_TS2.0_TP3.0ATR_H4`) and conservative (`ibs_TS2.5_TP2.5ATR_H5`) strategy configurations through the arena system and observe results consistent with research.

---

## Revision Log

### Rev 2 (2026-03-30) -- Cross-Review Consensus

Changes made based on unanimous feedback from backend, frontend, and QA reviewers:

**Blocking changes addressed:**
- B1: TP trigger price -- decided canonical behavior (use `today_bar.high` for trigger, `min(target, open)` for exit price). Added to Phase 2 as a required fix.
- B2: Zero ATR guard -- added fallback to fixed position_size when atr_pct is None or < 0.01. Defined sizing_mode + stop_type interaction matrix.
- B3: Circuit breaker placement -- moved from pre-loop (no-op) to post-loop. Changed `decisions["__circuit_breaker"]` to `decisions["__meta"]` to avoid breaking frontend iteration.
- B4: `_build_simulation_response()` extraction -- made step 4 mandatory in the 5-step schema pattern. All new fields must appear in SimulationResponse.
- B5: `CreateComparisonRequest` parity -- added as step 2 in the schema pattern. Comparison endpoint is the primary use case for aggressive vs conservative.
- B6: sizing_mode precedence -- defined explicit precedence rule with legacy fallback for pre-sizing_mode simulations.

**Non-blocking changes addressed:**
- N1: Per-day ATR memoization -- added local `_day_atr_cache` dict in step_day() to avoid 3-4x redundant ATR calculations per symbol per day.
- N2: Circuit breaker symbol lazy-load on resume -- added to step_day() lazy-load guard, mirroring regime filter pattern.
- N3: Regime state in `__meta` -- regime filter bull/bear determination now stored in snapshot decisions for frontend display.

**Consensus items documented (no plan changes needed):**
- Win streak order-dependence: deterministic, acceptable, documented
- consecutive_wins = 0 at migration time: known limitation, documented
- MA50 inactive for first 50 days: expected behavior, log it
- portfolio_selected = False for filtered signals: added to IBS filter code
- _close_position() helper: deferred to separate cleanup ticket

### Rev 3 (2026-03-30) -- Expanded Consensus + Final Sign-Offs

Addressed all items from the full cross-review consensus (8 blocking, 9 required, 3 documentation). Incorporated backend and QA sign-off feedback.

**Blocking changes addressed:**
- B4 (final): Circuit breaker storage changed from `decisions["__meta"]` to dedicated typed columns on `ArenaSnapshot` (`circuit_breaker_triggered`, `circuit_breaker_atr_pct`, `regime_state`). Adds Phase 5 migration. Typed columns are queryable, require no JSON parsing, and render cleanly in the frontend. Preferred by frontend reviewer over `snapshot_meta` JSON blob; accepted by all reviewers.
- B6 (new): MA50 filter scoping bug fixed -- `price_history` is not in scope in the post-loop filter block. Added explicit `_get_cached_price_history()` call per-symbol in the filter.
- B7 (expanded): `sizing_mode="risk_based"` + `stop_type="fixed"` now REJECTED at schema validation via `@model_validator`. No well-defined risk formula exists for fixed stops. Must be on both `CreateSimulationRequest` and `CreateComparisonRequest`.
- B8 (new): Exact field list for `SimulationResponse` and `_build_simulation_response()` specified per phase (Phases 1-5, 17 fields total + `snapshot_meta` on `SnapshotResponse`).

**Required changes addressed:**
- R3/R4: ALL-features-enabled integration test added to testing strategy (20-day sim with all features).
- R5/R7: Test audit for decisions dict equality assertions added (before Phase 4).
- R6: `_close_position()` helper extraction added as a new section -- consolidates win streak updates.
- R7 (frontend): Frontend work section added with per-phase checklist, ExitReason hotfix, and strategy presets.
- R8: Strategy presets (`STRATEGY_PRESETS` constants) added for Aggressive and Conservative modes.
- R9: `_load_auxiliary_symbol_cache()` generalization already in plan (Phase 5d).

**Documentation items addressed:**
- D1: Win streak order-dependence documented in Known Limitations with required tests for both orderings.
- D2: MA50 first-50-days inactivity documented with logging recommendation.
- D3: Migration `consecutive_wins = 0` limitation documented.

**Frontend addendum items:**
- ExitReason TypeScript hotfix called out as immediate pre-plan fix (not gated on this plan).
- Replay hydration test (old-schema simulations missing new fields) added to frontend checklist.
- Circuit breaker rendering test (`snapshot_meta.circuit_breaker` in dedicated section, no symbol rows).

**Sign-off status:**
- Backend: APPROVED (Rev 2, confirmed Rev 3 compatible)
- QA: APPROVED (Rev 2, with 4 implementation notes all addressed in Rev 3)
- Frontend: Pending (consensus received, awaiting formal sign-off)
