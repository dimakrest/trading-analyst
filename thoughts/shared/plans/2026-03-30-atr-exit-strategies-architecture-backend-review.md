# Backend Review: ATR-Based Exit Strategies Architecture
# Issue #47 — Implement ATR-Based Exit Strategies (Aggressive + Conservative)

**Reviewer**: backend-reviewer
**Plan reviewed**: `thoughts/shared/plans/2026-03-30-atr-exit-strategies-architecture.md`
**Date**: 2026-03-30

---

## Overall Assessment

**APPROVE WITH CONDITIONS.** The architectural approach is sound and consistent with established patterns in the codebase. Phases 1 and 2 are already implemented and working. The remaining three phases (3–5) follow the right patterns: config in `agent_config` JSON, no unnecessary migrations, correct transaction semantics. However, I found **six specific issues** the plan must address before implementation begins, plus an important performance concern.

---

## What the Plan Gets Right

1. **Config-in-JSON approach is correct.** All new feature flags go into `agent_config` (a JSON column), matching every prior "Layer." Only one DB migration across 5 phases — excellent constraint discipline.

2. **ATR data flow is already well-designed.** `_calculate_symbol_atr_pct()` (`simulation_engine.py:1090`) uses the in-memory price cache, 90-day window, Wilder's EMA (alpha=1/14), and returns `float | None`. It's called consistently for stop init, TP check, and portfolio selection. The plan correctly identifies this as the shared interface.

3. **IBS filter placement is correct.** Keeping it in the engine (not the agent) means BUY signals are still recorded in `decisions` even when filtered, enabling post-simulation analysis. Matches the existing regime filter pattern.

4. **win streak Option B (DB column) is the right call.** In-memory counters (Option A) don't survive crash/resume. O(n) query (Option C) is wasteful at scale. A single `consecutive_wins` integer with default 0 is the right trade-off.

5. **Circuit breaker correctly mirrors the regime filter pattern.** Pre-loading the circuit breaker symbol in `initialize_simulation()` via a generalized `_load_auxiliary_symbol_cache()` is the right approach.

---

## Issues Requiring Resolution

### Issue 1: ATR Recomputed 3–4× Per Symbol Per Day [MEDIUM — Performance]

**Code reference**: `simulation_engine.py:407`, `528`, `660`

For any simulation using `stop_type="atr"` with `take_profit_atr_mult` and risk-based sizing, `_calculate_symbol_atr_pct()` is called three separate times per symbol per day:
- At position open (stop init)
- At position update (ATR TP check)
- At portfolio selection (QualifyingSignal.atr_pct)

Phase 3 (risk-based sizing) would add a fourth call.

Each call allocates a 90-bar `pd.DataFrame`, runs `ewm()`, and extracts the last value. For 66 symbols × 250 days, this is ~49,500–66,000 pandas operations per full-year backtest.

**Required fix**: Add a per-day per-symbol ATR cache to `step_day()`:
```python
# At top of step_day(), after config extraction:
_atr_cache: dict[str, float | None] = {}

def _get_atr_pct(symbol: str) -> float | None:
    if symbol not in _atr_cache:
        _atr_cache[symbol] = self._calculate_symbol_atr_pct(simulation_id, symbol, current_date)
    return _atr_cache[symbol]
```

This replaces all 3–4 direct `_calculate_symbol_atr_pct()` calls per symbol with one. The dict is local to the `step_day()` call, so no cross-day state leaks.

---

### Issue 2: Circuit Breaker Placement Contradiction [LOW — Implementation Clarity]

**Plan section**: Phase 5b

The plan states the circuit breaker should be placed **"before the per-symbol BUY signal loop, as a day-level gate"** with `buy_signals = []`. But `buy_signals` is a list populated **inside** the per-symbol loop (`simulation_engine.py:624`). Placing `buy_signals = []` before an empty list is a no-op.

Two correct options:
- **Option A** (recommended): Place the circuit breaker check **after** the per-symbol loop (after line 625, before portfolio selection). Clear buy_signals there: `buy_signals = []`.
- **Option B**: Set a `circuit_breaker_active` flag before the loop and skip appending to `buy_signals` inside the loop.

Option A is simpler and matches the IBS filter pattern the plan proposes. **The plan must clarify this placement.**

---

### Issue 3: Risk-Based Sizing Division-by-Zero When Stop Distance Is Near Zero [LOW — Correctness]

**Plan section**: Phase 3a

The risk-based sizing formula:
```
stop_distance_per_share = atr_stop_multiplier * atr_pct / 100 * entry_price
shares = risk_amount / stop_distance_per_share
```

is not safe when `atr_pct` is near zero (e.g., a stock that hasn't moved in 14 days). The plan's graceful fallback handles `atr_pct is None`, but not `atr_pct ≈ 0.0`.

Additionally: what if `sizing_mode="risk_based"` but `stop_type="fixed"` (not `"atr"`)? The stop distance should then use `trailing_stop_pct` instead of `atr_stop_multiplier * atr_pct`. The plan assumes `stop_type="atr"` is always paired with `sizing_mode="risk_based"`, but this is not enforced anywhere.

**Required fix**:
1. Add `if stop_distance_per_share <= 0: fall back to fixed/pct sizing` guard.
2. Either document the constraint "risk_based sizing requires stop_type=atr" and add a schema-level validator, OR define a formula for risk-based sizing with fixed stops (use `trailing_stop_pct` as the stop distance).

---

### Issue 4: MA50 Filter Needs Price History — Not Just `today_bar` [LOW — Implementation Clarity]

**Plan section**: Phase 5a

The plan's IBS filter code does a single bar lookup:
```python
today_bar = self._get_cached_bar_for_date(simulation_id, symbol, current_date)
```

But the MA50 filter in the same block needs 50 closing prices:
```python
closes = [float(bar.close) for bar in price_history[-50:]]
```

`price_history` is a local variable inside the per-symbol loop — it's not available in the post-loop filter block. The plan doesn't specify how to retrieve it.

**Required fix**: Clarify that the MA50 filter uses:
```python
price_history = self._get_cached_price_history(
    simulation_id, symbol,
    current_date - timedelta(days=90),  # 90 days ensures 50 trading days
    current_date,
)
```

This is a cached list slice — fast — but the plan should call it out explicitly to avoid implementation confusion.

---

### Issue 5: `_build_simulation_response()` Doesn't Extract New Fields [MEDIUM — API Correctness]

**Code reference**: `api/v1/arena.py:88–136`

`_build_simulation_response()` only extracts 11 fields from `agent_config`: `trailing_stop_pct`, `min_buy_score`, `scoring_algorithm`, `volume_score`, `candle_pattern_score`, `cci_score`, `ma20_distance_score`, `portfolio_strategy`, `max_per_sector`, `max_open_positions`. None of the Layer 3–8 fields (stop_type, atr_stop_multiplier, take_profit_pct, take_profit_atr_mult, max_hold_days, position_size_pct, regime_filter, etc.) are extracted or surfaced in `SimulationResponse`.

This is a compound problem:
- Frontend cannot display new params in config panel
- Simulation replay cannot restore settings
- `SimulationResponse` schema has no fields for these params, so adding extraction alone is not enough — both the schema and the builder must be updated together

**Required fix**: For each new field added across Phases 3–5, the implementation plan must include three steps, not two:
1. Add field to `CreateSimulationRequest` with validator
2. Wire into `agent_config` in `create_simulation()`
3. **Extract from `agent_config` in `_build_simulation_response()` AND add to `SimulationResponse` schema**

The plan's current field-addition pattern (§Schema Field Addition Pattern) lists only steps 1 and 2, then separately mentions "optionally add to SimulationResponse." This is not optional — all new config fields should be surfaced in the response.

---

### Issue 6: `CreateComparisonRequest` Missing New Fields [LOW — API Completeness]

**Code reference**: `schemas/arena.py:298`

The plan describes adding new fields (`sizing_mode`, `ibs_max_threshold`, `ma50_filter_enabled`, `circuit_breaker_atr_threshold`, etc.) to `CreateSimulationRequest`. But `CreateComparisonRequest` (line 298) also creates simulations and shares many fields with `CreateSimulationRequest`. Users running comparative backtests (aggressive vs. conservative) need these parameters on comparison requests too.

The plan's schema section only mentions `CreateSimulationRequest`. `CreateComparisonRequest` is not mentioned at all.

**Required fix**: Each new field added to `CreateSimulationRequest` must also be added to `CreateComparisonRequest` (with the same defaults and validators). The two schemas have always been kept in sync — this should be called out explicitly in the implementation plan.

---

### Issue 6: Take-Profit Trigger Price Should Use Intraday High, Not Close [MEDIUM — Correctness]

**Code reference**: `simulation_engine.py:514-518`

The plan correctly flags this in Risk #2. I'm upgrading it from a note to an explicit resolution requirement because it affects whether live backtests match the research results.

Current implementation:
```python
unrealized_return_pct = float(
    (today_bar.close - position.entry_price) / position.entry_price * 100
)
```

If the research backtests used intraday-high TP (i.e., "exit when today's high crosses TP target"), the current code will produce different results — it only triggers at close. For mean-reversion strategies specifically, a stock often overshoots intraday and closes lower, meaning intraday-high TP would trigger on many days where close-price TP would not.

**Required fix**: Decision needed before Phase 2 is declared "complete." Options:
- Use `today_bar.high` for trigger check, `min(tp_target_price, today_bar.open)` for gap-up exit price
- OR explicitly document "close-price TP is intentional design choice, backtests reflect this"

One or the other must be decided and documented.

---

## Risk Table

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| ATR recomputed 3-4× per symbol per day (perf) | Certain | Medium (slow backtests) | Per-day per-symbol ATR cache dict in step_day() |
| Circuit breaker placed incorrectly (no-op) | High if not clarified | Low (feature silently disabled) | Clarify placement: post-loop, not pre-loop |
| Division-by-zero in risk-based sizing (atr_pct≈0) | Low | High (crash) | Guard: fall back if stop_distance_per_share <= 0 |
| sizing_mode=risk_based + stop_type=fixed combination | Low | Medium (wrong sizing) | Schema validator or documented constraint |
| MA50 filter fails (price_history not in scope) | Certain if not specified | Low (implementation error) | Clarify cache lookup needed |
| CreateComparisonRequest missing new fields | Certain | Medium (API gap) | Explicitly include in each phase's schema section |
| TP triggers on close vs. intraday high | Confirmed existing | Medium (backtest mismatch) | Decide and document before Phase 2 is closed |
| Win streak order within same-day multi-close | Low | Negligible (deterministic) | Acceptable; document symbol ordering in step_day |
| Entry filter stack over-filters (IBS+MA50+circuit breaker+regime) | Medium | Medium (very few trades) | Record all filter decisions in snapshot.decisions (plan already covers this) |
| consecutive_wins migration on in-progress simulations | Certain | Low (default 0 = correct) | Migration sets default 0; acceptable for existing sims |
| Backward compatibility of new None/False defaults | None (by design) | None | All new features default-disabled; existing sims unaffected |

---

## Minor Observations (Not Blocking)

**Observation 1**: The plan recommends extracting `_apply_entry_filters()` and `_calculate_position_size()` helper methods to manage `step_day()` complexity (Risk #1). This is good hygiene and I agree — `step_day()` is already 460+ lines. Even if not done in the initial implementation, it should be a follow-up ticket.

**Observation 2**: The plan's `consecutive_wins` design only scales risk upward (bonus per win, reset on loss). There is no corresponding downscaling on losing streaks. This appears intentional (the feature is called "win streak scaling"), but the plan should explicitly state it. Traders often want both: reduce size after consecutive losses.

**Observation 3**: The `__circuit_breaker` key in `decisions` dict (Phase 5b) uses a dunder-style prefix. Consider `_circuit_breaker` (single underscore) for consistency with Python convention, or a specific key like `circuit_breaker_info`.

**Observation 4**: `_load_regime_symbol_cache()` and the proposed circuit breaker aux symbol loading are doing the same thing. The plan recommends generalizing to `_load_auxiliary_symbol_cache()`. This is the right refactor. If both regime filter and circuit breaker use SPY, they should share the cache key without double-loading.

---

## Summary of Required Changes to Plan

1. **Add ATR per-day cache** to the Phase 3 and Phase 5 sections.
2. **Clarify circuit breaker placement** as post-loop (not pre-loop).
3. **Add division-by-zero guard** to risk-based sizing formula, and address the `sizing_mode=risk_based` + `stop_type=fixed` combination.
4. **Clarify MA50 filter** needs `_get_cached_price_history()` call in the post-loop block.
5. **Fix schema field addition pattern** — step 3 (extract in `_build_simulation_response()` + add to `SimulationResponse`) is mandatory, not optional.
6. **Add `CreateComparisonRequest` updates** to each phase's schema section.
7. **Resolve TP trigger price** — close vs. intraday high — before Phase 2 is marked complete.
