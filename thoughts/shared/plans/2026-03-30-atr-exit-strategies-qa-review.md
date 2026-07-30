# QA Review: ATR-Based Exit Strategies Architecture
# Issue #47 — Phases #48–#52

**Reviewer**: qa-engineer
**Date**: 2026-03-30
**Plan reviewed**: `thoughts/shared/plans/2026-03-30-atr-exit-strategies-architecture.md`

---

## Overall Assessment

The plan is architecturally sound for Phases 1 and 2 (already implemented) and Phases 4 and 5 (IBS + MA50/circuit breaker). **Phase 3 (risk-based position sizing) has a critical unguarded edge case** (zero ATR → division by zero) and under-specifies how the new `sizing_mode` interacts with the existing `position_size_pct` field. The `decisions["__circuit_breaker"]` key design in Phase 5 will cause frontend breakage unless changed. These must be resolved before implementation begins.

---

## Phase 1 & 2 (Already Implemented) — QA Sign-off with One Caveat

**Phases 1 (#48) and 2 (#49) are complete. The test coverage for trailing stop logic is excellent** (`test_trailing_stop.py` covers init, boundary, update, trigger, lifecycle scenarios thoroughly).

**One open issue flagged in the plan itself (Risk 2):**
The plan notes that current TP triggers against `today_bar.close` but issue #49 specifies intraday-high trigger with gap-up handling. This is a correctness discrepancy — if backtests were run with close-price TP, the results are not reproducible from the spec. **The plan must explicitly state which behavior is canonical before Phases 3–5 build on top of it.** Changing TP trigger from close to intraday-high after Phase 3 ships will invalidate risk-based sizing research comparisons.

---

## Phase 3: Risk-Based Position Sizing — CRITICAL GAP

### CRITICAL: Zero Stop Distance → Division by Zero

The plan says:
> `shares = risk_amount / stop_distance_per_share`
> `stop_distance_per_share = atr_stop_multiplier * atr_pct / 100 * entry_price`

If `atr_pct = 0` (zero-range stock, possible in illiquid names), `stop_distance = 0` and the division crashes. The plan handles zero ATR for the trailing stop itself (graceful fallback to fixed stop) **but does not handle it for the sizing formula.**

**Required fix**: Before computing `shares`, guard:
```python
if stop_distance_per_share <= 0:
    # Fall back to fixed position size or skip entry
```

**Required test**:
```python
def test_risk_based_sizing_zero_atr_fallback():
    """When ATR is zero, risk-based sizing must not divide by zero."""
    # Set up position open with atr_pct = 0.0
    # Assert: falls back to fixed sizing or skips, does not raise ZeroDivisionError
```

### MEDIUM: `sizing_mode` vs. `position_size_pct` Ambiguity

The plan introduces `sizing_mode: "fixed" | "fixed_pct" | "risk_based"` but the existing schema already has `position_size_pct: float | None`. Their interaction is unspecified:
- If `sizing_mode="fixed_pct"` but `position_size_pct=None`, what happens?
- If `sizing_mode="fixed"` but `position_size_pct=30.0` (set by old request), which wins?

**Required**: The plan must define the precedence rule explicitly and add a validator in `CreateSimulationRequest` that rejects contradictory combinations.

**Required test**: Backward compat — existing simulations using only `position_size_pct` (without `sizing_mode`) must behave identically to before.

### MEDIUM: Win Streak with Multiple Same-Day Closes

If two positions close on the same day — one win, one loss — the final `consecutive_wins` depends on symbol processing order (`simulation.symbols` list order). A win at index 0 followed by a loss at index 1 yields `consecutive_wins = 0`. A loss at index 0 followed by a win at index 1 yields `consecutive_wins = 1`.

**Required tests**:
```python
def test_win_streak_loss_then_win_same_day():
    """Loss processed before win: streak should be 1."""

def test_win_streak_win_then_loss_same_day():
    """Win processed before loss: streak should be 0."""
```

Document the intentional behavior. If order-dependence is acceptable, state it explicitly.

### LOW: `consecutive_wins` for Mid-Progress Simulations at Migration Time

If a simulation is at day 30 with 3 actual consecutive wins when the Phase 3 migration runs, the new column starts at `DEFAULT 0` — the win streak is erased. Risk-based sizing for the remainder of that simulation will undersize positions.

**Mitigation**: Document this known limitation. Optionally, consider whether to compute the initial value from existing closed positions (query-based Option C from the plan) as a one-time migration step.

### Missing Tests for Phase 3

| Scenario | Test Exists? |
|----------|-------------|
| Risk-based sizing formula (unit test, not just integration) | ✗ MISSING |
| Zero ATR → fallback, no crash | ✗ MISSING |
| Win streak 0 → 1 → 2 → 0 (loss resets) | ✗ MISSING |
| `effective_risk` capped at `max_risk_pct` | ✗ MISSING |
| `sizing_mode="fixed"` when `position_size_pct` also set | ✗ MISSING |
| `consecutive_wins` survives simulated crash-resume (transactional rollback) | ✗ MISSING |
| `shares < 1` fallback in risk-based mode | ✗ MISSING |

---

## Phase 4: IBS Entry Filter — Two Gaps

### MEDIUM: Silent Block When `today_bar is None`

The plan's IBS filter code:
```python
if today_bar and today_bar.high != today_bar.low:
    ibs = float(...)
else:
    ibs = 0.5
```

When `today_bar is None`, `ibs = 0.5`. If threshold is 0.55, `0.5 < 0.55` → the signal passes. This is correct and safe. But the edge case needs explicit test coverage to prevent accidental regression.

**Additional concern**: The IBS filter calls `_get_cached_bar_for_date()` as a second bar lookup (the agent already looked up the bar earlier in the symbol loop). This is a redundant lookup — confirm the two methods (`_find_bar_for_date` and `_get_cached_bar_for_date`) return the same result. If they differ in edge cases, IBS decisions could be inconsistent with agent evaluation.

**Required test**:
```python
def test_ibs_filter_high_equals_low():
    """High == Low produces IBS = 0.5 (neutral). Should pass threshold 0.55."""

def test_ibs_filter_disabled_when_threshold_none():
    """No filtering when ibs_max_threshold is None."""

def test_ibs_filter_records_filtered_decision():
    """decisions[symbol]['ibs_filtered'] = True and 'ibs_value' set for blocked signals."""
```

### LOW: `portfolio_selected` Key Absent for IBS-Filtered Signals

After IBS filtering, blocked signals never reach portfolio selection, so `decisions[symbol]["portfolio_selected"]` is never set. This creates an asymmetry in the decisions dict:
- Unfiltered BUY signals: always have `portfolio_selected: True/False`
- IBS-filtered BUY signals: have `ibs_filtered: True` but no `portfolio_selected`

Any frontend code or analysis doing `decision.get("portfolio_selected")` on IBS-filtered entries will get `None` instead of `False`. **Explicitly set `portfolio_selected: False` for filtered signals**, or document the absent key behavior.

### Missing Tests for Phase 4

| Scenario | Test Exists? |
|----------|-------------|
| `ibs_max_threshold=None` → no filtering | ✗ MISSING |
| `high == low` → IBS = 0.5 | ✗ MISSING |
| IBS = 0.54 with threshold 0.55 → passes | ✗ MISSING |
| IBS = 0.56 with threshold 0.55 → blocked | ✗ MISSING |
| Blocked signal has `ibs_filtered=True`, `ibs_value` in decisions | ✗ MISSING |
| `portfolio_selected` not present / explicitly `False` for filtered signals | ✗ MISSING |

---

## Phase 5: MA50 Filter + Circuit Breaker — One MEDIUM, Two LOW Issues

### MEDIUM: `decisions["__circuit_breaker"]` Breaks Frontend Iteration

The plan proposes:
```python
decisions["__circuit_breaker"] = {"triggered": True, ...}
```

The `decisions` dict is keyed by **stock symbol**. The snapshot stores this as a JSON column. Any frontend or backend code iterating `decisions.items()` and expecting all keys to be valid symbols will receive `__circuit_breaker` as a symbol, causing display errors or broken iteration logic.

**Required change**: Store circuit breaker metadata outside the per-symbol decisions dict. Options:
- Add a separate `meta` key: `decisions["__meta"] = {"circuit_breaker": {...}}`
- Add a dedicated `circuit_breaker_triggered: bool` field on `ArenaSnapshot`
- Use a namespaced prefix that the frontend knows to skip: `"__circuit_breaker"` with frontend filter

At minimum, **the plan must specify how the frontend handles this key**, or it should be moved to a separate snapshot field.

### LOW: MA50 Filter Inactive for First 50 Trading Days

When price history has fewer than 50 bars, the plan sets `ma50 = None` and skips filtering. This means a simulation's **first ~10 calendar weeks** produce entries the MA50 filter would have blocked if data were available. This is a known limitation but must be:
1. Logged explicitly (`logger.debug("MA50 filter inactive: only N bars available")`)
2. Documented in the schema field description
3. Tested:

```python
def test_ma50_filter_inactive_with_insufficient_history():
    """MA50 filter does not block entries when < 50 bars available."""

def test_ma50_filter_blocks_stock_below_ma50():
    """Stock where close < 50-day SMA is filtered out."""

def test_ma50_filter_allows_stock_above_ma50():
    """Stock where close > 50-day SMA passes filter."""
```

### LOW: Circuit Breaker Symbol Missing from Cache on Resume

The plan says to pre-load the circuit breaker symbol in `initialize_simulation()`. But on simulation **resume** (crash recovery), `initialize_simulation()` is skipped (idempotent check at `is_initialized`). The `step_day()` method has a lazy-load guard for the price cache, but this guard only covers simulation symbols. If the circuit breaker symbol was in memory before the crash but the engine restarts, `_calculate_symbol_atr_pct()` returns `None` → circuit breaker silently disabled for that day.

**Required test**:
```python
def test_circuit_breaker_symbol_loaded_on_resume():
    """After simulated crash (cache cleared), circuit breaker symbol is lazy-loaded."""
```

**Fix**: Add circuit breaker symbol to the lazy-load guard in `step_day()`, mirroring the existing regime filter lazy-load pattern.

### Missing Tests for Phase 5

| Scenario | Test Exists? |
|----------|-------------|
| `ma50_filter_enabled=False` → no filtering | ✗ MISSING |
| MA50 filter with < 50 bars → filter inactive | ✗ MISSING |
| Circuit breaker triggers → new entries blocked | ✗ MISSING |
| Circuit breaker triggers → existing open positions NOT closed | ✗ MISSING |
| Circuit breaker turns off next day → entries resume | ✗ MISSING |
| Circuit breaker symbol `_calculate_symbol_atr_pct` returns `None` → safe default | ✗ MISSING |
| Circuit breaker on resume (symbol not in cache) → lazy-loaded | ✗ MISSING |
| All three filters active simultaneously (IBS + MA50 + circuit breaker) | ✗ MISSING |

---

## Cross-Phase: Regression Risks

### Risk A: `decisions` Dict Structure Evolution

The existing `test_simulation_engine.py` likely asserts on `decisions` dict structure in snapshot assertions. Adding new keys (`ibs_filtered`, `ma50_filtered`, `ibs_value`, `portfolio_selected`, `circuit_breaker`) will break any test using `assert decisions[symbol] == {...}` equality.

**Action required**: Audit existing tests for exact dict equality assertions before each phase ships. Use `assert decisions[symbol]["action"] == "BUY"` (key-specific) rather than full-dict equality.

### Risk B: Exit Condition Ordering After Three New Filters

The current exit priority is: trailing stop → breakeven/ratchet → take profit → max hold. After Phase 3–5, the entry pipeline is: circuit breaker → IBS → MA50 → portfolio selection. Each is gated by config, so individually correct. But **no test covers all exit/entry conditions active simultaneously.**

**Required integration test**: Run a 20-day simulation with ALL features enabled (ATR stop, TP, max hold, breakeven, ratchet, risk sizing, win streak, IBS, MA50, circuit breaker). Verify results are deterministic and match expected P&L.

### Risk C: `winning_trades` vs. `consecutive_wins` Divergence

Both counters are updated in three separate close-position blocks (stop hit, TP, max hold). If a new exit path is added in the future and only one counter is updated, they diverge silently.

**Recommended**: Extract a `_close_position()` helper that updates both counters atomically, replacing the duplicated update logic in all three close blocks.

---

## Risk Table

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Zero ATR → `stop_distance = 0` → ZeroDivisionError in risk-based sizing | **Medium** | **High** (crash on entry, real money) | Guard `stop_distance > 0`; fall back to fixed sizing; test explicitly |
| `decisions["__circuit_breaker"]` key breaks frontend symbol iteration | **Medium** | **Medium** (UI bug, incorrect display) | Move to separate snapshot field or `__meta` key; specify frontend handling |
| TP trigger price (close vs. intraday high) — research/impl discrepancy | **Medium** | **High** (P&L results not reproducible from spec) | Confirm canonical behavior before Phase 3; freeze it in a test |
| `sizing_mode` + `position_size_pct` interaction undefined | **Medium** | **Medium** (silent incorrect sizing) | Define precedence; add schema validator; test backward compat |
| Mid-progress simulation gets `consecutive_wins = 0` at migration | **Low** | **Medium** (incorrect risk scaling for in-flight runs) | Document limitation; consider computed initial value |
| Multiple positions close same day → streak order-dependent | **Medium** | **Low** (minor inaccuracy) | Document order; add test for both orderings |
| MA50 inactive for first 50 trading days (undocumented) | **High** (always) | **Low** (known gap, but silent) | Add log warning; document in schema; test explicitly |
| Circuit breaker symbol not lazy-loaded on resume → silently disabled | **Low** | **Low** (one missed circuit-breaker day) | Add to `step_day()` lazy-load guard; test resume scenario |
| All five filters active → over-filtering → 0 trades (silent empty backtest) | **Medium** | **Medium** (wasted compute, misleading null results) | Add warning log when all buy signals filtered in a day |
| IBS `portfolio_selected` absent for filtered signals → frontend `None` | **Low** | **Low** (display bug) | Explicitly set `portfolio_selected: False` for filtered signals |
| `decisions` dict structure breaks existing test assertions | **Medium** | **Low** (test failures, not production) | Audit and update tests before each phase ships |

---

## Migration Safety

| Phase | Migration Required | Rollback Safe? | Notes |
|-------|-------------------|----------------|-------|
| 1 (#48) | None | N/A | Complete |
| 2 (#49) | None | N/A | Complete |
| 3 (#50) | Yes — `consecutive_wins` column | Yes (DROP COLUMN) | In-progress simulations start at 0 after migration |
| 4 (#51) | None | Yes (code revert) | All config in `agent_config` JSON |
| 5 (#52) | None | Yes (code revert) | All config in `agent_config` JSON |

Each phase is independently rollbackable. Phase 3 rollback requires both code revert and migration rollback. Document the rollback procedure explicitly in the migration file.

---

## Backward Compatibility Verdict

All new features use `None`/`False` defaults → **existing simulations are unaffected**. The `agent_config` JSON dict is read with `.get()` throughout. ✓

One caveat: Adding new keys to the `decisions` dict per snapshot may affect existing frontend components that render decision data. **Verify frontend snapshot rendering is tolerant of unknown keys** before each phase ships.

---

## Summary of Required Actions Before Implementation

**Blocking (must fix in plan):**
1. Define zero-ATR handling in risk-based sizing formula (Phase 3)
2. Define `sizing_mode` vs. `position_size_pct` precedence and validator (Phase 3)
3. Move `decisions["__circuit_breaker"]` to non-symbol key or separate field (Phase 5)
4. Confirm canonical TP trigger behavior (close vs. intraday high) and document it (Phase 2 clarification)

**Required but non-blocking:**
5. Add explicit log warning when MA50 filter is inactive (< 50 bars) (Phase 5)
6. Set `portfolio_selected: False` explicitly for IBS-filtered signals (Phase 4)
7. Add circuit breaker symbol to `step_day()` lazy-load guard for resume safety (Phase 5)
8. Expand test matrix with ALL-features-enabled integration test (cross-phase)
9. Consider extracting `_close_position()` helper to prevent counter divergence (Phase 3)

**Documentation:**
10. Document that win streak is order-dependent when multiple positions close same day
11. Document that MA50 filter is inactive for the first ~10 weeks of any simulation
12. Document `consecutive_wins = 0` for in-progress simulations at migration time
