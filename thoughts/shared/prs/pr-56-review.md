# PR Review Report — #56 `feat(arena): MA50 filter + market volatility circuit breaker`

## Summary

Phase 5 adds two entry safety filters (MA50 per-symbol trend gate + market-volatility circuit breaker), a four-state snapshot audit column, a Market Conditions banner, and Aggressive/Conservative one-click presets. The implementation is focused, well-tested (1,645 lines of new test coverage), and reuses established patterns (`_load_auxiliary_symbol_cache`, `ConfigItem`, `calculate_atr_percentage`). Correctness and security are solid. Two **accessibility Must Fixes** on the frontend block merge; the most important **Should Fix** is a latent trap in the MA50 filter that will silently disable itself for any future agent with `required_lookback_days < ~40`.

## Code Cleanup Applied

- **`/simplify`**: Extracted `_load_filter_auxiliary_caches` helper in `simulation_engine.py` — 44 duplicated lines (regime + circuit-breaker preload across init and resume paths) collapsed into two call sites + a 19-line helper. All 197 arena backend tests remained green.
- **`code-cleanup`**: Unified the duplicate `_detect_market_regime` call (previously invoked twice per day — once for position-cap, again for snapshot column) by reusing `regime_state_value` in the snapshot construction. Single-file change, behavior-preserving.

## Must Fix (blocking merge)

- **[`frontend/src/components/arena/ArenaSetupForm.tsx:1185-1201`]** — MA50 `<Label>` is not programmatically associated with the toggle `<button>` (no `htmlFor`/`id` pair). Clicking the visible label text does nothing. Fix: either switch to the existing ShadCN `<Toggle>` primitive or add matching `id`/`htmlFor`. *(Source: Frontend)*
- **[`frontend/src/components/arena/ArenaDecisionLog.tsx:83`]** — `text-amber-600` on `bg-amber-500/10` contrasts at ~2.3:1, failing WCAG AA (4.5:1 required for 12px text). Same concern with `text-blue-600` (~4.7:1, borderline). This is the `data_unavailable` safety-critical banner. Fix: move to `text-amber-700`/`text-blue-700` or darker. *(Source: Frontend)*

## Should Fix (strongly recommended)

**Backend correctness**
- **[`simulation_engine.py:~785-817`]** — MA50 filter silently skips whenever the simulation-symbol cache has fewer than 50 bars (occurs when `agent.required_lookback_days + 30 < ~70`). The UI banner and snapshot config still advertise the filter as enabled. Tests already use `required_lookback_days=5`, so the agent protocol permits this. Fix: enforce `required_lookback_days >= 50` at init when `ma50_filter_enabled`, or load 90 calendar days unconditionally for MA50 like the circuit-breaker does. *(Source: Devil's Advocate)*
- **[`simulation_engine.py:~1197` `_load_auxiliary_symbol_cache`]** — Idempotence guard only checks symbol presence, not whether the existing cache window covers the new caller's requested lookback. Works today (ATR14 + min 40 calendar days is fine), but will bite when any aux-consumer's lookback grows. Fix: track `data_start` per symbol and top up if the new request is earlier. *(Source: Devil's Advocate)*
- **[`simulation_engine.py:806-815`]** — When `ph` is empty (full cache miss on a sim symbol), MA50 filter passes the symbol through with no debug/warning log. Fix: add an `else: logger.warning(...)` branch for the empty-cache case. *(Source: Backend)*

**Frontend quality**
- **[`ArenaSetupForm.tsx:559-576`]** — Preset buttons use raw `<button>` with ~100 chars of Tailwind instead of the project's `<Button variant="outline" size="sm">` primitive. Design-system drift. *(Source: Frontend)*
- **[`ArenaSetupForm.tsx:292`]** — `useEffect` missing `entryFilters` (+ pre-existing `setSelectedAgentConfigId`) in deps array; `eslint-plugin-react-hooks` flags it. Destructure `applyInitialValues` at the hook callsite and add to deps. *(Source: Frontend)*
- **[`ArenaDecisionLog.tsx:53-96`]** — `switch(circuitBreakerState)` uses `default: return null`, so any future addition to the `CircuitBreakerState` union silently produces an invisible banner. Replace with an exhaustiveness `never` assertion. *(Source: Frontend)*

**Test quality**
- **[`test_simulation_engine.py::test_circuit_breaker_boundary_at_threshold_triggers`]** — Name promises a `>=` boundary test but body re-proves the `>` case (same threshold=2.8 and atr_pct=3.0 as the adjacent test). Feed a controlled ATR equal to the threshold or delete. *(Source: QA)*
- **[`test_simulation_engine.py::test_ma50_filter_stale_close_guard`]** — Call-counter closure monkey-patches `_get_cached_price_history`; any future engine-side call addition silently turns this into a no-op pass. Prefer seeding `_price_cache` directly with a stale last-bar date. *(Source: QA)*
- **[`test_simulation_engine.py::test_resume_lazy_load_includes_circuit_breaker_symbol`]** — Bare `try/except Exception: pass` around `step_day`; masks unrelated regressions. Tighten to the expected exception type or patch enough surface to let it complete. *(Source: QA)*

## Consider (optional, non-blocking)

- **[`simulation_engine.py:789-791`]** — Add a comment clarifying why 90 *calendar* days reliably yields ≥50 *trading* bars for MA50. *(Source: Backend)*
- **[`schemas/arena.py:678`]** — `regime_state` is bare `str | None`; `circuit_breaker_state` already uses `Literal[...]`. Make `regime_state` a `Literal["bull","bear","neutral"]` for API-consumer clarity. *(Source: Backend)*
- **[`simulation_engine.py:789-803`]** — MA50 recomputes a 50-bar mean per BUY symbol per day. Fine at current scale; a rolling cache analogous to `_day_atr_cache` (line 350) would be cheaper. *(Source: Devil's Advocate, Feature Alignment)*
- **[`ArenaDecisionLog.tsx:54-65`]** — `role="status"` on the `clear` banner fires a polite live-region announcement on every day-change during fast replay. Reserve live announcements for `triggered`/`data_unavailable`; render `clear` as a passive indicator. *(Source: Frontend)*
- **[`ArenaSetupForm.tsx:345` `applyPreset`]** — Unconditionally sets `atrAutoSetByRiskSizing.current = true`. Violates the ref's invariant ("tracks whether *we* auto-flipped it"). On later sizing switch, the preset's explicit `stop_type='atr'` can silently revert. Only set the ref when pre-preset `stopType` was `'fixed'`. *(Source: Devil's Advocate)*
- **Schemas duplication** — The three new `Field` blocks are repeated verbatim in both `CreateSimulationRequest` and `CreateComparisonRequest` (consistent with prior phases; not PR-introduced, but this is the 4th layer extending the pattern). A shared mixin would reduce drift. *(Source: Feature Alignment)*
- **QA suggested tests**: (a) explicit `gt=0` rejection test for `circuit_breaker_atr_threshold=0`; (b) submit-payload negative-space assertion that empty threshold omits both fields; (c) fixture covering CB symbol already in `simulation.symbols`; (d) `selectedStrategies` identity assertion in the preset-preservation test. *(Source: QA)*

## Test Coverage

Strong and proportionate. All key Phase 5 gates are exercised: MA50 insufficient-history (49/50 bars), stale-close, circuit-breaker `data_unavailable` with WARNING assertion, Aggressive/Conservative presets, Phase 5 field replay-hydration, and the `TestSimulationEngineAllFeaturesIntegration` event-calendar combining every Phase 1-5 branch. No material files lack tests; the migration file has no dedicated upgrade/downgrade test but follows repo convention (no precedent). Minor quality tightening noted above.

## Security

**No security issues identified.** Checked: `circuit_breaker_symbol`/`regime_symbol` bounded by `^[A-Z]{1,5}$` server-side (FastAPI enforces before `agent_config` hits the engine or logger); SQL via ORM/Core only, migration uses hard-coded literal `sa.text("'disabled'")`; no `dangerouslySetInnerHTML` / `innerHTML` on new React rendering; no `pickle`/`yaml.load`; `logger.warning(%s, ...)` uses parameter format with regex-bounded inputs (no log injection); no new routes introduced (auth posture unchanged); arbitrary-ticker fetch is bounded by the same regex and cached, matching the existing `regime_symbol` risk profile.

## Feature Alignment

**Intent**: Ship two entry-level safety filters (MA50 trend gate + market-volatility circuit breaker) plus audit persistence, Market Conditions banner, and one-click Aggressive/Conservative presets — completing Phase 5 of the ATR-exit roadmap.

- **Directly-serving changes**: ~22 of 25 files.
- **Tangential / unnecessary**: None. The deferred `useEntryFilterState` hook and the ALL-features integration test were explicitly tagged follow-ups in the plan; both are small, well-scoped, and reduce maintenance burden rather than expanding scope.
- **Better alternatives spotted**: Schema-field duplication across the two request types (pre-existing pattern; extract a mixin as a separate clean-up PR); MA50 per-day recompute could piggy-back a rolling cache.
- **Overall**: Focused and well-scoped. The PR does exactly what the plan promised.

## Verdict

- [ ] Ready to merge
- [x] **Needs changes** — two a11y Must Fix items on the frontend, plus the MA50-silent-disable latent trap recommended as Should Fix before merging.
