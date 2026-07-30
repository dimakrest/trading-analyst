# Frontend Review: ATR-Based Exit Strategies (Issue #47)
**Reviewer**: frontend-reviewer
**Date**: 2026-03-30
**Based on**: Direct analysis of modified backend code + existing frontend codebase
**Files reviewed**:
- `backend/app/schemas/arena.py` — new request params (all layers 3–8)
- `backend/app/models/arena.py` — ExitReason enum, ArenaPosition model
- `backend/app/api/v1/arena.py` — _build_simulation_response, agent_config wiring
- `backend/app/services/arena/trailing_stop.py` — AtrTrailingStop implementation
- `frontend/src/types/arena.ts` — TypeScript types
- `frontend/src/components/arena/ArenaSetupForm.tsx` — form + initialValues
- `frontend/src/components/arena/ArenaConfigPanel.tsx` — config display
- `frontend/src/components/arena/ArenaPortfolio.tsx` — position display
- `frontend/src/components/arena/ArenaSimulationList.tsx` — list view
- `frontend/src/components/arena/ArenaResultsTable.tsx` — metrics display

---

## Summary

The backend adds 17 new simulation parameters across 5 layers (ATR stops, take profit, hold period, position sizing %, breakeven/ratchet, regime filter). The frontend plan must address all of these cohesively. Several **critical gaps** exist between the current backend implementation and what the frontend can currently handle. These must be explicitly addressed in the plan.

---

## 1. Critical Gaps — Must Be Addressed

### 1.1 SimulationResponse does NOT expose the new parameters

`_build_simulation_response()` in `arena.py:88–136` only extracts these fields from `agent_config`:
```
trailing_stop_pct, min_buy_score, scoring_algorithm, volume_score,
candle_pattern_score, cci_score, ma20_distance_score,
portfolio_strategy, max_per_sector, max_open_positions
```

**None** of the new Layer 3–8 fields are extracted: `stop_type`, `atr_stop_multiplier`, `atr_stop_min_pct`, `atr_stop_max_pct`, `take_profit_pct`, `take_profit_atr_mult`, `max_hold_days`, `max_hold_days_profit`, `position_size_pct`, `breakeven_trigger_pct`, `ratchet_trigger_pct`, `ratchet_trail_pct`, `regime_filter`, `regime_symbol`, `regime_sma_period`, `regime_bull_max_positions`, `regime_bear_max_positions`.

**Consequences**:
- `ArenaConfigPanel` cannot display new params (it reads from `Simulation` type)
- Replay (`ArenaSetupForm.initialValues`) cannot restore them
- `ArenaSimulationList` cannot distinguish simulations by stop type
- The frontend TypeScript `Simulation` type is also missing these fields

**Plan must require**: `SimulationResponse` schema + `_build_simulation_response()` + `Simulation` TS type all get the new fields.

### 1.2 CreateComparisonRequest is missing all new parameters

`CreateComparisonRequest` (`schemas/arena.py:298–398`) has none of the Layer 3–8 fields. It only has the original parameters.

**Consequence**: Multi-strategy comparisons cannot use ATR stops, take profit, hold period, regime filter, etc. This is a major feature gap — running "Aggressive vs Conservative" as a comparison is the core use case of the feature, yet the comparison endpoint can't accept the strategy parameters.

**Plan must require**: All new Layer 3–8 parameters mirrored into `CreateComparisonRequest`.

### 1.3 ExitReason TypeScript type is already broken — IMMEDIATE HOTFIX required

Frontend type (`types/arena.ts:17`):
```typescript
export type ExitReason = 'stop_hit' | 'simulation_end' | 'insufficient_capital';
```

Backend enum (`models/arena.py:48–55`) now has:
```python
TAKE_PROFIT = "take_profit"
MAX_HOLD = "max_hold"
```

**Phases 1 and 2 are already deployed.** Any simulation that already exited via `take_profit` or `max_hold` is currently showing broken/empty exit reason displays in `ArenaPortfolioComposition` and `ArenaSectorBreakdown`. This is not future work — it's a live bug.

**Action**: File as a standalone hotfix ticket. Do NOT gate on this plan's approval. 5-line fix, zero risk:
```typescript
export type ExitReason = 'stop_hit' | 'simulation_end' | 'insufficient_capital' | 'take_profit' | 'max_hold';
```

### 1.4 ArenaSetupForm.initialValues interface missing new fields

`initialValues` prop (`ArenaSetupForm.tsx:35–49`) doesn't include any of the new params. When a user replays a simulation that used ATR stops + take profit + regime filter, none of those settings will be restored to the form.

**Plan must require**: `initialValues` extended with all new fields; replay hydration logic updated.

---

## 2. Form UX — Progressive Disclosure is Non-Negotiable

17 new parameters dumped into the existing flat form would be unusable. The current form already has ~10 controls. Adding 17 more without grouping would make configuration overwhelming.

**Recommended approach** (to be specified in plan):

### 2a. Stop Type as Mode Switcher
Use a segmented control / toggle: **Fixed %** | **ATR-Adaptive**
- `Fixed %`: Show only `trailing_stop_pct` input (current behavior)
- `ATR-Adaptive`: Hide `trailing_stop_pct`; show `atr_stop_multiplier`, `atr_stop_min_pct`, `atr_stop_max_pct`

These two modes are mutually exclusive by design — the plan must enforce this via conditional rendering, not just documentation.

### 2b. Take Profit as Optional Section
Default: collapsed/disabled. Three sub-modes:
- Off (None)
- Fixed %: `take_profit_pct`
- ATR Multiple: `take_profit_atr_mult`

`take_profit_pct` and `take_profit_atr_mult` are mutually exclusive — you'd pick one mode. A Select or radio is appropriate.

### 2c. Hold Period as Optional Inputs
Default: disabled. When enabled, show `max_hold_days` and optionally `max_hold_days_profit` (extended hold for winners). These should be numeric inputs with clear labels about what "trading days" means.

### 2d. Advanced Settings collapsible section
`breakeven_trigger_pct`, `ratchet_trigger_pct`, `ratchet_trail_pct` should be in a collapsed "Advanced" section. These are expert-only parameters.

### 2e. Position Sizing Mode
Current: fixed `position_size ($)` input. New: Add a toggle **Fixed $** | **% of Equity**. When `% of Equity` selected, show `position_size_pct` and hide the fixed `position_size` input.

### 2f. Market Regime Filter as Collapsible Section
Default: toggle OFF. When toggled ON, show `regime_symbol`, `regime_sma_period`, `regime_bull_max_positions`, `regime_bear_max_positions` in a collapsible sub-section.

**Risk**: If the plan doesn't specify the UX grouping strategy, implementation will be ad-hoc and inconsistent.

---

## 3. State Management

The current form uses component-level `useState` hooks with no Redux/Zustand. This pattern is fine but 17 new params adds complexity. The plan should call out:

### New state variables needed in ArenaSetupForm:
```typescript
// Stop type
const [stopType, setStopType] = useState<'fixed' | 'atr'>('fixed');
const [atrStopMultiplier, setAtrStopMultiplier] = useState('2.0');
const [atrStopMinPct, setAtrStopMinPct] = useState('2.0');
const [atrStopMaxPct, setAtrStopMaxPct] = useState('10.0');

// Take profit
const [tpMode, setTpMode] = useState<'off' | 'fixed' | 'atr_mult'>('off');
const [takeProfitPct, setTakeProfitPct] = useState('');
const [takeProfitAtrMult, setTakeProfitAtrMult] = useState('');

// Hold period
const [holdPeriodEnabled, setHoldPeriodEnabled] = useState(false);
const [maxHoldDays, setMaxHoldDays] = useState('');
const [maxHoldDaysProfit, setMaxHoldDaysProfit] = useState('');

// Position sizing
const [positionSizeMode, setPositionSizeMode] = useState<'fixed' | 'pct'>('fixed');
const [positionSizePct, setPositionSizePct] = useState('');

// Breakeven/ratchet (advanced)
const [breakevenTriggerPct, setBreakevenTriggerPct] = useState('');
const [ratchetTriggerPct, setRatchetTriggerPct] = useState('');
const [ratchetTrailPct, setRatchetTrailPct] = useState('');

// Regime filter
const [regimeFilterEnabled, setRegimeFilterEnabled] = useState(false);
const [regimeSymbol, setRegimeSymbol] = useState('SPY');
const [regimeSma, setRegimeSma] = useState('20');
const [regimeBullMax, setRegimeBullMax] = useState('');
const [regimeBearMax, setRegimeBearMax] = useState('1');
```

Total: 20 new state variables. The plan should group them or consider a `useReducer` if complexity grows further.

**Also**: The `canSubmit` validation logic (`ArenaSetupForm.tsx:264–272`) needs updating — `ratchet_trail_pct` must be provided when `ratchet_trigger_pct` is set; ATR min/max must be valid; etc.

---

## 4. TypeScript Type Changes Required

### 4a. `CreateSimulationRequest` in `types/arena.ts`
Must add all new fields matching the backend schema:
```typescript
// Layer 4
stop_type?: 'fixed' | 'atr';
atr_stop_multiplier?: number;
atr_stop_min_pct?: number;
atr_stop_max_pct?: number;
// Layer 5
take_profit_pct?: number | null;
take_profit_atr_mult?: number | null;
// Layer 6
max_hold_days?: number | null;
max_hold_days_profit?: number | null;
// Layer 3
position_size_pct?: number | null;
// Layer 8
breakeven_trigger_pct?: number | null;
ratchet_trigger_pct?: number | null;
ratchet_trail_pct?: number | null;
// Layer 7
regime_filter?: boolean;
regime_symbol?: string;
regime_sma_period?: number;
regime_bull_max_positions?: number | null;
regime_bear_max_positions?: number;
```

### 4b. `Simulation` type in `types/arena.ts`
Must add the same fields so `ArenaConfigPanel` and `initialValues` can read them.

### 4c. `CreateComparisonRequest` in `types/arena.ts`
Must also add the new fields (same as above) once the backend gap is fixed.

### 4d. `ExitReason` in `types/arena.ts`
```typescript
export type ExitReason = 'stop_hit' | 'simulation_end' | 'insufficient_capital' | 'take_profit' | 'max_hold';
```

---

## 5. ArenaConfigPanel — Display New Config

The config panel currently shows 4 items (Date Range, Agent, Trailing Stop, Min Score) + optional Portfolio section. It needs to show the new parameters for completed simulations.

**Required additions**:
- **Stop Type row**: Show "Fixed 5%" vs "ATR ×2.0 (2–10%)"
- **Take Profit row**: Show "8%" or "×3.0 ATR" or "Off" (conditional)
- **Hold Period row**: Show "22 days (profitable: 30)" or "Off" (conditional)
- **Regime Filter row**: Show "SPY > SMA(50)" or "Off" (conditional)
- **Position Sizing row**: Show "$1,000" or "33% of equity" (based on mode)

Consider adding a second expandable section "Exit Strategy" below the current grid.

---

## 6. Visualizations

### 6a. Exit Reason Breakdown — Required
With new exit reasons (`take_profit`, `max_hold` joining `stop_hit`), users need to understand what's driving exits. The existing `ArenaPortfolioComposition` and `ArenaTradeFrequency` components should:
- Update exit reason badge labels ("Take Profit", "Max Hold", "Stop Hit")
- Optionally: Add a breakdown chart (small bar or pie) showing exit reason distribution

### 6b. ATR Stop Lines on Equity Chart — Optional but Valuable
`ArenaEquityChart.tsx` shows equity curve. For ATR-adaptive stops, showing an average effective trail % badge below the chart (e.g., "Avg trail: 6.2%") would help users understand stop behavior without requiring chart overlays.

### 6c. Per-Position Trail % in ArenaPortfolio — Needed
`ArenaPortfolio.tsx` shows positions with Entry and Stop columns. The per-position `trailing_stop_pct` is stored in `ArenaPosition.trailing_stop_pct` but not shown in the UI. For ATR mode simulations, this is the key diagnostic metric — users need to see "NVDA: stop at $412.50 (7.2% trail)".

**Required**: Add `trailing_stop_pct` column to the open positions table when `stop_type = 'atr'`.

### 6d. Regime State Indicator — Needed for Regime Filter
When `regime_filter=True`, users running a live sim want to know the current regime. A small badge in `ArenaConfigPanel` or simulation header showing "Bull Regime" / "Bear Regime" / "Unknown" would be valuable. This requires the backend to return regime state in snapshots or simulation response.

**Plan must clarify**: Is regime state surfaced in snapshots? If not, this visualization can't be built.

---

## 7. Missing: Comparison Mode Support

The current "Aggressive vs Conservative" use case — the stated goal of the feature — would naturally run as a comparison. But `CreateComparisonRequest` lacks all new parameters. The frontend form's comparison mode (`selectedStrategies.length >= 2`) also won't submit ATR stop settings.

**This is the highest-priority gap.** The plan must address whether:
- Option A: Fix `CreateComparisonRequest` to accept all new params (same sim config, different portfolio strategies)
- Option B: The aggressive/conservative comparison is two separate single simulations (workaround)
- Option C: A new endpoint for "strategy preset" comparison (Aggressive preset vs Conservative preset)

Without a decision here, the feature title "Aggressive + Conservative" has no UI path to actually compare them.

---

## 8. Test Coverage Requirements

### 8a. ArenaSetupForm tests
- Stop type toggle: switching from fixed to ATR hides/shows correct fields
- TP mode switching: off → fixed → atr_mult shows correct inputs
- Position size mode: fixed vs pct shows correct inputs
- Regime filter toggle: off → on shows regime sub-section
- Validation: ratchet_trail_pct required when ratchet_trigger_pct is set
- Replay: `initialValues` with new fields populates all form controls
- Comparison submit: new fields included in comparison request
- **Replay of old-schema simulation** (pre-new-fields): `initialValues` missing `stop_type`, `atr_stop_multiplier`, etc. must NOT crash; all missing fields fall back to form defaults via optional chaining (`initialValues.stop_type ?? 'fixed'`)

### 8b. ArenaConfigPanel tests
- Shows "ATR ×2.0" stop type when stop_type='atr'
- Shows take profit value or "Off"
- Shows hold period or "Off"
- Shows regime filter status

### 8c. ArenaPortfolio tests
- Shows trailing_stop_pct column for ATR mode positions
- Hides trailing_stop_pct column for fixed mode

### 8d. Exit reason display tests
- 'take_profit' renders "Take Profit" badge (not undefined/empty)
- 'max_hold' renders "Max Hold" badge (not undefined/empty)

### 8e. ArenaDecisionLog circuit breaker rendering
- When snapshot has `circuit_breaker_triggered: true` (dedicated field per B4), circuit breaker renders in its own "Market Conditions" section
- Non-symbol keys (`__circuit_breaker`, `__meta`) must NEVER appear as symbol rows — assert `queryByText('__circuit_breaker')` is null
- When `circuit_breaker_triggered: false`, no circuit breaker section rendered

---

## 9. Risk Table

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| SimulationResponse gaps cause silent data loss (new params not in API response) | **High** (already confirmed missing) | **High** — config panel broken, replay broken | Backend plan must add fields to response schema AND `_build_simulation_response()` |
| CreateComparisonRequest missing new params makes the core use case impossible | **High** (already confirmed missing) | **High** — "Aggressive vs Conservative" comparison unachievable | Fix in same PR as CreateSimulationRequest |
| 17 new form fields without UX strategy → unusable form | **High** (no grouping specified yet) | **High** — user adoption fails, impossible to configure | Plan must prescribe progressive disclosure layout |
| ExitReason type stale → components silently ignore take_profit/max_hold exits | **High** (confirmed stale) | **Medium** — stats/charts show wrong exit distribution | Simple type update + component audit for exhaustive checks |
| Regime state not in snapshots → regime indicator can't be built | **Medium** (unknown) | **Medium** — planned visualization blocked | Plan must clarify regime state exposure in API |
| Ratchet params cross-dependency not validated in form | **Medium** | **Low** — server will reject, user gets generic error | Add form-level validation: ratchet_trail_pct required with ratchet_trigger_pct |
| initialValues replay missing new fields → confusing pre-fill | **High** (confirmed missing) | **Medium** — replay feature broken for new simulations | Extend initialValues interface and hydration |
| ArenaComparisonTable doesn't show new config params | **High** | **Low** — cosmetic only | Add config params to comparison display |
| TypeScript types out of sync → API calls succeed but FE shows wrong defaults | **High** | **Medium** — silent mismatches | Derive TS types from OpenAPI spec if possible |

---

## 10. Recommended Plan Additions

The plan should explicitly include these frontend work items that may not be obvious:

1. **Backend**: Extend `SimulationResponse` + `_build_simulation_response()` for all new params (affects frontend)
2. **Backend**: Mirror all new params into `CreateComparisonRequest`
3. **Frontend**: Update `ExitReason` type (5 min change, high value)
4. **Frontend**: Update `Simulation`, `CreateSimulationRequest`, `CreateComparisonRequest` TS types
5. **Frontend**: Progressive disclosure UX design for ArenaSetupForm (specify layout)
6. **Frontend**: Extend `initialValues` + replay hydration
7. **Frontend**: `ArenaConfigPanel` new config display rows
8. **Frontend**: Per-position `trailing_stop_pct` column in ArenaPortfolio (ATR mode)
9. **Frontend**: Exit reason badge labels for new reasons
10. **Clarify**: Regime state in snapshots — required for regime indicator visualization

---

## 11. Plan-Specific Findings (After Reading Architecture Plan)

### 11.1 SimulationResponse Option A Chosen — But Fields Not Specified

The plan (line 430) says: *"Continue with Option A for now (add specific fields)"* for SimulationResponse. Correct call. But it does **not specify which fields** to add. This is a gap — the plan writer left the decision to reviewers or implementers.

**My recommendation** (for the plan to incorporate): Add the following fields to `SimulationResponse` and `_build_simulation_response()`:
- From Phase 1 (already in schema, just not in response): `stop_type`, `atr_stop_multiplier`, `atr_stop_min_pct`, `atr_stop_max_pct`
- From Phase 2: `take_profit_pct`, `take_profit_atr_mult`, `max_hold_days`, `max_hold_days_profit`
- From Phase 3: `sizing_mode`, `risk_per_trade_pct`
- From Phase 4: `ibs_max_threshold`
- From Phase 5: `ma50_filter_enabled`, `circuit_breaker_atr_threshold`
- Omit from response (internal/redundant): `win_streak_bonus_pct`, `max_risk_pct`, `circuit_breaker_symbol`, all breakeven/ratchet detail params (optional — can always be added later)

Separately, `consecutive_wins` (the new Phase 3 DB column) could be surfaced in `SimulationResponse` as a live stat, but this is optional.

### 11.2 Phases 3–5 Schema Fields Not Yet Implemented

My pre-review was based on the current schema. The plan reveals Phases 3–5 introduce additional new fields that don't exist yet:
- **Phase 3**: `sizing_mode`, `risk_per_trade_pct`, `win_streak_bonus_pct`, `max_risk_pct`
- **Phase 4**: `ibs_max_threshold`
- **Phase 5**: `ma50_filter_enabled`, `circuit_breaker_atr_threshold`, `circuit_breaker_symbol`

All frontend TypeScript types and form controls for these phases must be planned in addition to Phases 1–2.

### 11.3 Snapshot Decisions Dict — ArenaDecisionLog Must Be Updated

The plan explicitly calls out new transparency keys in the snapshot `decisions` dict:
- `decisions[symbol]["ibs_filtered"] = True` and `decisions[symbol]["ibs_value"]`
- `decisions[symbol]["ma50_filtered"] = True`
- `decisions["__circuit_breaker"] = {"triggered": True, "market_atr_pct": ..., "threshold": ...}`

The `ArenaDecisionLog` component currently renders agent decisions from this dict. It must be updated to:
1. Show IBS filter events ("IBS=0.63, filtered") with the `ibs_value`
2. Show MA50 filter events ("MA50 filtered")
3. Show circuit breaker events ("Circuit breaker: SPY ATR 3.1% > 2.8%")

These are explicitly described as for "transparency UI" (plan line 471). This is new frontend work the plan doesn't mention.

**Also**: The `AgentDecision` TypeScript type (`types/arena.ts:98–102`) only has `action`, `score`, `reasoning`. The new fields (`ibs_filtered`, `ibs_value`, `ma50_filtered`) would need to be added to a more permissive type or a new `FilterEvent` type.

### 11.4 No Strategy Presets in UI

The plan defines two strategies with exactly-specified parameter combinations:
- **Aggressive**: stop 2.0x, TP 3.0x ATR, hold 4 days, MA50+circuit breaker
- **Conservative**: stop 2.5x, TP 2.5x ATR, hold 5 days, IBS<0.55+MA50+circuit breaker

Without UI presets, users must manually configure 10+ parameters to replicate these strategies. This defeats the purpose of naming them "Aggressive" and "Conservative."

**Recommendation**: Add `ArenaStrategyPresets` buttons to the form:
```typescript
const STRATEGY_PRESETS = {
  aggressive: {
    stop_type: 'atr', atr_stop_multiplier: 2.0,
    take_profit_atr_mult: 3.0, max_hold_days: 4,
    ma50_filter_enabled: true, circuit_breaker_atr_threshold: 2.8,
    sizing_mode: 'risk_based', risk_per_trade_pct: 2.5,
    max_open_positions: 10, max_per_sector: 3,
  },
  conservative: {
    stop_type: 'atr', atr_stop_multiplier: 2.5,
    take_profit_atr_mult: 2.5, max_hold_days: 5,
    ibs_max_threshold: 0.55, ma50_filter_enabled: true,
    circuit_breaker_atr_threshold: 2.8,
    sizing_mode: 'risk_based', risk_per_trade_pct: 2.5,
    max_open_positions: 10, max_per_sector: 3,
  },
}
```
Clicking a preset populates the form; user can still customize before submitting.

### 11.5 No Frontend Work Items in Plan

The entire plan covers only backend changes. Zero frontend work items are listed. The plan must be augmented with a "Frontend Work" section covering:
1. TypeScript type updates (phases 1–5 as they ship)
2. ArenaSetupForm new controls + progressive disclosure
3. Strategy presets
4. ArenaConfigPanel new config display
5. ArenaDecisionLog filter event display
6. ArenaPortfolio per-position trail% column
7. Exit reason label updates
8. Replay/initialValues updates
9. CreateComparisonRequest parity
10. Test coverage for all above

### 11.6 CreateComparisonRequest Still Not Addressed

The plan does not mention `CreateComparisonRequest` at all. This remains the highest-priority gap: multi-strategy comparisons can't use any of the new exit strategy parameters.

---

## Overall Assessment

The backend implementation is solid and well-structured. The core simulation logic is correct. The architectural plan covers backend phases 1–5 thoroughly. However, **the plan is entirely backend-focused** — it has zero frontend work items. The frontend integration work is significantly underspecified.

**Must be added to the plan before implementation begins:**
1. `SimulationResponse` Option A — specify exact field list (see §11.1)
2. `CreateComparisonRequest` — mirror all new params (see §1.2, §11.6)
3. Frontend work section (see §11.5) — TypeScript types, form UX, ArenaConfigPanel, ArenaDecisionLog, ArenaPortfolio, replay, tests
4. Strategy presets UI (see §11.4) — without this, the "Aggressive/Conservative" framing has no UI path
5. `ExitReason` type update (see §1.3) — quick win, already broken

**Good news**: The backend's agent_config JSON pattern is clean and extensible. Each phase adds zero migrations (except Phase 3's `consecutive_wins` counter). The phased approach is sound. Frontend can be built incrementally alongside each phase as they ship.
