# Phase 4: IBS Entry Filter (#51)

Parent: #47 -- ATR-Based Exit Strategies
Depends on: None (independent of other phases)

## Status

Implemented.

## What

Add Internal Bar Strength (IBS) as an entry filter. IBS measures where a stock's close falls within its daily range. Low IBS (close near the low) suggests oversold conditions favorable for mean-reversion entry. High IBS (close near the high) suggests the stock has already bounced -- less favorable.

## Why

The conservative strategy uses IBS < 0.55 to filter entries. This reduces entries on days when the stock has already moved up within its range, lowering drawdown at the cost of fewer trades.

---

## Backend Changes

### 4a. IBS Calculation

IBS = `(close - low) / (high - low)`. One-liner, no separate utility needed.

Edge case: if `high == low` (zero range day), IBS defaults to 0.5 (neutral).

### 4b. Where to Apply

**In simulation_engine.py, not in the agent.** The agent generates signals (BUY/NO_SIGNAL). Entry filters gate whether a signal is acted upon. This matches existing patterns (regime filter, portfolio selector operate in the engine downstream of agent decisions).

Location: `simulation_engine.py` -- after BUY signal collection (line 718) and before portfolio selection (line 720). Add a filter pass:

```python
# --- Entry Filters ---
# Entry filters run AFTER agent evaluation populates decisions[symbol]
# (simulation_engine.py:710-714) and BUY signal collection (line 716-718),
# but BEFORE portfolio selection (line 720+).
#
# decisions[symbol] is fully populated by agent evaluation loop above.
# today_bar is non-None guaranteed here: BUY signals only generated
# after today_bar check at simulation_engine.py line 419.
# The `today_bar is None` fallback is dead code kept as a safety net.

ibs_max = simulation.agent_config.get("ibs_max_threshold")
if ibs_max is not None:
    filtered_buy_signals = []
    for symbol, decision in buy_signals:
        today_bar = self._get_cached_bar_for_date(simulation_id, symbol, current_date)
        if today_bar and today_bar.high != today_bar.low:
            ibs = float((today_bar.close - today_bar.low) / (today_bar.high - today_bar.low))
        else:
            # high == low (zero-range day): use neutral IBS.
            # today_bar is non-None here by construction -- BUY signals are only
            # collected after the today_bar guard at simulation_engine.py:419.
            ibs = 0.5
        if ibs < ibs_max:
            filtered_buy_signals.append((symbol, decision))
        else:
            decisions[symbol]["ibs_filtered"] = True
            decisions[symbol]["ibs_value"] = round(ibs, 4)
            decisions[symbol]["portfolio_selected"] = False
    buy_signals = filtered_buy_signals
```

### 4c. Schema Changes

New field on `CreateSimulationRequest` (`schemas/arena.py:59`) AND `CreateComparisonRequest` (`schemas/arena.py:353`):
- `ibs_max_threshold: float | None = None` (**gt=0, le=1**). None = disabled.

**Critical: `gt=0` not `ge=0`.** Since IBS = (close-low)/(high-low) is mathematically bounded to [0,1], `ibs < 0` is never true. If the schema accepted `0`, the comparison `if ibs < 0` would filter every BUY signal, producing a simulation with zero trades that looks valid. Direct API calls (scripts, tests, replay endpoints) bypass frontend validation, so the backend must reject `0` itself. Precedent: `trailing_stop_pct` uses `gt=0` at `schemas/arena.py:103` for similar safety reasons.

Single field design: None = off, set value ∈ (0, 1] = active. No separate boolean toggle needed.

### 4d. API Wiring (5-Step Process)

1. **Schema fields**: Add `ibs_max_threshold` to `CreateSimulationRequest` (`schemas/arena.py:59`) and `CreateComparisonRequest` (`schemas/arena.py:353`)
2. **agent_config in create_simulation()**: Add to agent_config dict (`arena.py:256-297`):
   ```python
   # Layer 10: Entry filters
   "ibs_max_threshold": request.ibs_max_threshold,
   ```
3. **agent_config in create_comparison()**: Add to `base_agent_config` dict (`arena.py:698-716`):
   ```python
   "ibs_max_threshold": request.ibs_max_threshold,
   ```
   This ensures comparison simulations support IBS identically to single simulations.
4. **_build_simulation_response()** (`arena.py:78-155`): Extract and return the field:
   ```python
   ibs_max_threshold = agent_config.get("ibs_max_threshold")
   ```
   Add to `SimulationResponse` (`schemas/arena.py:631`):
   ```python
   ibs_max_threshold: float | None = None
   ```
   Add to the `SimulationResponse(...)` constructor call (`arena.py:109-155`):
   ```python
   ibs_max_threshold=ibs_max_threshold,
   ```
5. **step_day()**: Read from `simulation.agent_config` in the entry filter block (see 4b above)

### 4e. No DB Migration

All config stored in `agent_config` JSON. No model changes needed.

---

## Frontend Changes

The form is split into 3 tabs: **Setup** (symbols, dates, capital), **Agent** (agent type, scoring), **Portfolio** (strategy, constraints, tuning). Entry filters belong in the **Portfolio** tab under a collapsible "Entry Filters" section (similar to the existing "Advanced Tuning" collapsible). Label the section generically as "Entry Filters" since Phase 5 will add MA50 and circuit breaker controls to the same section.

### F1. TypeScript types (`types/arena.ts`)

Add `ibs_max_threshold` to:
- `Simulation` interface (`types/arena.ts:36-83`):
  ```typescript
  ibs_max_threshold?: number | null;
  ```
- `CreateSimulationRequest` interface (`types/arena.ts:144-197`):
  ```typescript
  ibs_max_threshold?: number;
  ```
- `CreateComparisonRequest` interface (`types/arena.ts:214-249`):
  ```typescript
  ibs_max_threshold?: number;
  ```

**New `DecisionEntry` type**: Do NOT extend `AgentDecision`. `AgentDecision` (`types/arena.ts:114-118`) represents pure agent output (action, score, reasoning) and is used elsewhere. Create a new `DecisionEntry` interface for the annotated snapshot decisions:

```typescript
/** Snapshot decision entry: agent output + engine filter annotations */
export interface DecisionEntry {
  // Agent output (same fields as AgentDecision)
  action: string;
  score: number | null;
  reasoning: string | null;
  // Engine annotations (added by portfolio execution / entry filters)
  portfolio_selected?: boolean;
  ibs_filtered?: boolean;
  ibs_value?: number;
}
```

Update `Snapshot.decisions` type (`types/arena.ts:133`):
```typescript
decisions: Record<string, DecisionEntry>;  // was Record<string, AgentDecision>
```

`ArenaDecisionLog` already uses `Object.entries(snapshot.decisions)` -- this is a type-level change, non-breaking at runtime. Update `ArenaDecisionLog.test.tsx` mock type from `Record<string, AgentDecision>` to `Record<string, DecisionEntry>` to match.

### F2. ArenaSetupForm -- Portfolio tab (`ArenaSetupForm.tsx`)

Add a collapsible "Entry Filters" section below the constraints grid. Include an IBS threshold input (number, 0-1 range, placeholder "Disabled"). This section will also hold MA50 and circuit breaker controls in Phase 5.

**IBS field validation** (CRITICAL -- JavaScript truthy bug): The naive check `ibsValue ? parseFloat(ibsValue) : undefined` treats `'0'` as truthy, which would send `ibs_max_threshold=0` -- blocking ALL entries since IBS is never < 0. The plan must specify:
- IBS field is active only when `value > 0 && value <= 1`
- A value of `0` must show an inline error ("Must be greater than 0") or be treated as disabled
- Empty field = omit `ibs_max_threshold` from request body entirely (not sent as `''` or `0`)
- Add IBS validation to the `canSubmit` guard

Add `ibs_max_threshold` to the `initialValues` prop type (`ArenaSetupForm.tsx:36-58`):
```typescript
initialValues?: {
  // ... existing fields ...
  ibs_max_threshold?: number | null;
};
```
Without this, replaying a simulation loses IBS config. On a real-money system, this is silent data loss -- the user reruns thinking it's the same strategy but results diverge.

### F3. ArenaConfigPanel

Display IBS threshold when configured.

### F4. ArenaDecisionLog

Display `ibs_filtered` badge and `ibs_value` when present in decisions.

---

## Testing

### Backend Tests

| Test File | What to Test |
|-----------|-------------|
| test_simulation_engine.py | IBS filter blocks entry when IBS >= threshold |
| test_simulation_engine.py | IBS filter allows entry when IBS < threshold |
| test_simulation_engine.py | **Boundary value**: `ibs == threshold` is blocked (>= comparison) |
| test_simulation_engine.py | **Boundary value**: `ibs == threshold - epsilon` is allowed |
| test_simulation_engine.py | **Boundary value**: Decimal precision at threshold (engineered close/high/low producing IBS exactly at boundary) |
| test_simulation_engine.py | Zero-range day (high == low) defaults to IBS 0.5 |
| test_simulation_engine.py | IBS filter disabled when threshold is None |
| test_simulation_engine.py | `ibs_filtered` and `ibs_value` recorded in decisions dict |
| test_simulation_engine.py | `portfolio_selected = False` set for filtered signals |
| test_simulation_engine.py | IBS-filtered symbol excluded from portfolio selection: not in `buy_signals` passed to `get_selector().select()`, `portfolio_selected` not overwritten to True |
| test_arena_api.py | POST with `ibs_max_threshold=0.55` accepted; GET returns it in response |
| test_arena_api.py | POST with `ibs_max_threshold=0` rejected with 422 (backend-level protection against the silent all-trades-off config; must pass without the frontend in the loop) |
| test_arena_api.py | POST with `ibs_max_threshold=-0.01` rejected with 422 |
| test_arena_api.py | POST with `ibs_max_threshold=1.0` accepted (upper bound inclusive) |

### Frontend Tests

| Scenario | Component | What to Test |
|----------|-----------|-------------|
| Renders in Portfolio tab | ArenaSetupForm | IBS threshold field renders inside "Entry Filters" collapsible |
| Included in payload | ArenaSetupForm | IBS value > 0 included in submit payload |
| Omitted when empty | ArenaSetupForm | IBS omitted from payload when field is empty |
| IBS=0 shows error | ArenaSetupForm | Value of 0 shows inline error, form does not submit |
| Decision log badge | ArenaDecisionLog | Shows `ibs_filtered` badge when present in snapshot decision |
| Decision log IBS value | ArenaDecisionLog | Shows `ibs_value` when present in decision entry |
| Config panel display | ArenaConfigPanel | Renders IBS threshold row when configured |
| Replay populates IBS | ArenaSetupForm | `initialValues` with `ibs_max_threshold` pre-populates IBS field |
| Mock type consistency | ArenaDecisionLog.test | Mock uses `Record<string, DecisionEntry>` (not `AgentDecision`) |

### Pre-Phase Test Audit

Grepping for full-dict equality assertions (`assert decisions[symbol] == {...}`) found NONE in the current test suite. Existing tests use key-specific assertions (e.g., `test_simulation_engine.py:2724-2725`, `test_simulation_engine.py:2899-2903`). Adding `ibs_filtered`, `ibs_value`, `portfolio_selected` keys to the decisions dict will not break existing tests. Confirm this finding before implementation.

## Success Criteria

- [x] Simulations with `ibs_max_threshold=0.55` reject entries where close is near daily high
- [x] Boundary: `ibs == threshold` is rejected; `ibs == threshold - epsilon` is accepted
- [x] Filter decisions recorded in snapshot for transparency
- [x] Disabled by default (None) -- no impact on existing simulations
- [x] Zero-range edge case handled gracefully
- [x] Comparison simulations support IBS filter identically to single simulations
- [x] Replaying a simulation preserves IBS config via initialValues
- [x] IBS=0 treated as disabled (inline error), not sent to backend
- [x] Backend schema rejects `ibs_max_threshold=0` with 422 (defense in depth -- API clients cannot bypass the frontend guard)
- [x] `DecisionEntry` type used for snapshot decisions; `AgentDecision` unchanged
- [x] IBS-filtered symbol excluded from portfolio selection (not in `buy_signals` passed to selector)
