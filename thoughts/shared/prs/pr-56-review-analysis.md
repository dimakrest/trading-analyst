# PR #56 Review — Analysis & Recommendations

**Source review**: `thoughts/shared/prs/pr-56-review.md`
**PR**: `feat(arena): MA50 filter + market volatility circuit breaker` (Phase 5)
**Analyzed**: 2026-04-17

---

## Context Understood

Phase 5 of the ATR-exit roadmap adds two **entry safety filters** (MA50 per-symbol trend gate + market-volatility circuit breaker), a four-state snapshot audit column, a Market Conditions banner, and Aggressive/Conservative one-click presets.

**Reviewer's overall verdict**: Correctness and security are solid. Two **a11y Must Fixes** block merge. The most important **Should Fix** is a latent trap where the MA50 filter silently disables itself for any future agent with `required_lookback_days < ~40`.

The recurring failure mode in the highest-priority items: **UI/state advertises a safety feature as ON while the engine silently skips it.** That is the exact class of bug the project's "real money / no shortcuts" rule exists to prevent.

---

## Recommendations Table

| # | Item | Severity | Why it matters | Risk if ignored | Recommendation |
|---|------|----------|----------------|-----------------|----------------|
| 1 | MA50 `<Label>` not associated with toggle button (`ArenaSetupForm.tsx:1185-1201`) | **Must Fix** | Click-on-label is broken; assistive tech can't bind label↔control | Low blast (UX only) but blocks merge per reviewer | **Fix now** — 2-line change, swap to ShadCN `<Toggle>` or add `id`/`htmlFor` |
| 2 | Amber/blue text contrast fails WCAG AA on safety banner (`ArenaDecisionLog.tsx:83`) | **Must Fix** | `data_unavailable` is a *safety-critical* banner; users may miss it | Real money risk if user misses circuit breaker degraded state | **Fix now** — bump to `text-amber-700` / `text-blue-700` |
| 3 | MA50 silently disables when `required_lookback_days < 50` (`simulation_engine.py:~785-817`) | **Should Fix** | UI says filter is ON, engine quietly skips it. Tests already use `lookback=5` — protocol *permits* this | **High latent risk** — future agent ships with filter "enabled" but no-op'd; trades take entries the filter was supposed to block | **Fix now** — enforce `required_lookback_days >= 50` at init OR unconditionally load 90d for MA50 (matches CB pattern). Aligns with "real money / no shortcuts" project standard |
| 4 | `_load_auxiliary_symbol_cache` idempotence ignores window coverage (`simulation_engine.py:~1197`) | **Should Fix** | Works today (ATR14+40d covers all callers); breaks silently when any aux-consumer's lookback grows | Latent — won't fire until next aux feature added | **Fix now while context is fresh** — track `data_start` per symbol, top up on shorter request. Cheap insurance |
| 5 | Empty-cache MA50 path has no warning log (`simulation_engine.py:806-815`) | Should Fix | Silent pass-through obscures debugging when symbol data fetch fails | Diagnosability only | **Fix now** — one `logger.warning` line |
| 6 | Preset buttons bypass `<Button>` primitive (`ArenaSetupForm.tsx:559-576`) | Should Fix | Design-system drift; visual inconsistency over time | Low — cosmetic | **Fix now** — trivial swap |
| 7 | `useEffect` missing deps (`ArenaSetupForm.tsx:292`) | Should Fix | ESLint flags it; stale-closure bug class | Low today, classic React footgun | **Fix now** — destructure + add deps |
| 8 | `switch` default returns null on `CircuitBreakerState` union (`ArenaDecisionLog.tsx:53-96`) | Should Fix | Future enum addition → invisible safety banner | Latent safety-banner risk | **Fix now** — `never` exhaustiveness assertion |
| 9 | Boundary test mis-named, doesn't test `>=` (`test_circuit_breaker_boundary_at_threshold_triggers`) | Should Fix | False confidence in coverage | Test debt | **Fix now** — 5-line test correction |
| 10 | Stale-close test monkey-patches `_get_cached_price_history` | Should Fix | Will silently no-op on engine refactor | Test debt | **Fix now** — seed `_price_cache` directly |
| 11 | `try/except Exception: pass` in resume test | Should Fix | Masks unrelated regressions | Test debt | **Fix now** — narrow exception type |
| 12 | `regime_state` should be `Literal[...]` (`schemas/arena.py:678`) | Consider | API consumer clarity, parity with `circuit_breaker_state` | None | **Defer** — quick follow-up PR |
| 13 | MA50 50-bar mean recompute per BUY/day | Consider | Perf, fine at current scale | None now | **Defer** — only optimize when measured |
| 14 | `role="status"` on `clear` banner spams a11y live region | Consider | Screen-reader noise during fast replay | UX (a11y) | **Fix now** while in a11y mindset (low cost) |
| 15 | `applyPreset` violates `atrAutoSetByRiskSizing.current` invariant | Consider | Subtle preset→sizing-switch bug; preset's ATR can silently revert | Latent UX bug | **Fix now** — guard the ref assignment |
| 16 | Schema `Field` duplication across 2 request types | Consider → **Promoted** | Pattern is now in 4 layers (Phase 2-5); each new phase doubles the touch surface and risk of drift between `CreateSimulationRequest` and `CreateComparisonRequest` | Drift risk compounds — the next phase will pay this cost again, and any field that diverges silently breaks comparison parity | **Fix now in this PR** — extract a shared `EntryFiltersMixin` (or equivalent) that both request schemas inherit. 4 layers is the inflection point where the mixin pays for itself; deferring means Phase 6 inherits the same problem |
| 17 | QA suggested edge-case tests (gt=0 rejection, etc.) | Consider | Coverage of negative space | Low | **Defer to follow-up** — not blocking |

---

## Suggested Merge Plan

1. **Block merge until**: items **1, 2** (Must Fix) + **3, 4, 8, 15** (latent safety/silent-failure traps that bite real-money trades).
2. **Bundle into this PR**: items **5–11, 14, 16** (small, in-context cleanups that get harder to do later — including the schema-mixin extraction now that 4 phases of drift have accumulated).
3. **Follow-up PR**: items **12, 13, 17** (true scope-creep candidates).

## Why Items 3, 8, 15 Get Promoted Above "Should Fix"

The reviewer classified these as Should Fix / Consider, but each shares the **same defect signature** as the formal Must Fix items:

- **Item 3** — UI shows MA50 enabled, engine silently skips → entry filter believed ON is OFF.
- **Item 8** — Future `CircuitBreakerState` enum value renders no banner → safety state believed visible is invisible.
- **Item 15** — Preset sets `stop_type='atr'`, later sizing switch silently reverts it → user-chosen stop believed configured is overwritten.

In a system that handles real money, every "silent" path between **what the user/UI believes is happening** and **what the engine actually does** is a defect of the same severity as a contrast failure on a safety banner. Treat them as merge-blocking.
