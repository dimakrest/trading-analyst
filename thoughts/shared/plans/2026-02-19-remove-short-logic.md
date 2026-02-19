# Remove SHORT Logic - Full System LONG-Only Cleanup

## Overview

Remove all SHORT-related logic from the entire Live20 system, making it explicitly LONG-only. The system is a mean reversion bounce strategy — it only identifies oversold LONG setups. SHORT logic is dead code that creates confusion and maintenance burden.

**Ticket**: [GitHub Issue #24](https://github.com/dimakrest/trading-analyst/issues/24)

## Current State Analysis

SHORT logic exists across 6 layers:

| Layer | Files | What exists |
|-------|-------|-------------|
| Indicators | `volume.py`, `candlestick_interpretation.py`, `two_candle_patterns.py`, `multi_day_patterns.py`, `rsi2_analysis.py`, `registry.py` | `aligned_for_short` field on every result dataclass |
| Evaluator | `live20_evaluator.py` | `CriterionResult.aligned_for_short`, `score_for_short`, `Live20Direction.SHORT`, `determine_direction_and_score()` SHORT branch |
| Service/Worker | `live20_service.py`, `live20_worker.py` | SHORT direction handling, SHORT count tracking |
| API/Schemas | `live20.py`, `schemas/live20.py`, `schemas/live20_run.py`, `schemas/indicators.py`, `core/docs.py` | SHORT in direction filters, response types, run schemas, docs |
| Models/DB | `recommendation.py`, `live20_run.py`, repository, migration | `short_count` column, SHORT in CHECK constraints, `RecommendationDecision.SHORT` |
| Frontend | Types, filters, table, history tab, recommend dialog, colors | SHORT direction type, filter buttons, badges, counts |

### Key Discoveries:
- Arena agent (`live20_agent.py:148-149`) is already LONG-only — no changes needed there
- The evaluator `determine_direction_and_score()` (`live20_evaluator.py:222-257`) is the core logic that produces SHORT directions
- `live20_service.py:140-167` uses SHORT for criterion alignment checks
- `live20_worker.py:73-86` counts SHORT results
- Database has `short_count` column on `live20_runs` table and SHORT in recommendation CHECK constraint
- Frontend has SHORT filter buttons in `Live20Filters.tsx:122-128` and `Live20HistoryTab.tsx:171-179`
- `RecommendPortfolioDialog.tsx:86` has `includeShort` state and checkbox

## Desired End State

1. **No SHORT direction** — system only produces LONG or NO_SETUP
2. **No SHORT fields** on indicator/criterion dataclasses (`aligned_for_short`, `score_for_short` removed)
3. **No SHORT enum values** — `Live20Direction` and `RecommendationDecision` only have LONG + NO_SETUP
4. **Database cleaned** — `short_count` column dropped, CHECK constraint updated, existing SHORT data converted to NO_SETUP
5. **Frontend cleaned** — no SHORT filter buttons, no SHORT badges, no SHORT count display
6. **Simpler code** — `determine_direction_and_score()` only checks LONG alignment

## What We're NOT Doing

- NOT changing the indicator detection logic itself (patterns are still bullish/bearish — we just don't score bearish as SHORT)
- NOT removing the `aligned_for_long` field — it's still needed
- NOT changing any Arena agent logic (it's already LONG-only)
- NOT modifying stock price data or historical analysis logic

---

## Phase 1: Backend Indicators — Remove `aligned_for_short`

### Overview
Remove `aligned_for_short` field from all indicator result dataclasses and their producers. These are leaf dependencies — no other indicator depends on them.

### Changes Required:

#### 1. Volume indicator
**File**: `backend/app/indicators/volume.py`
- Remove `aligned_for_short` from `VolumeSignalAnalysis` dataclass (line 62)
- Remove all `aligned_for_short=` assignments in `detect_volume_signal()` (lines 99, 129, 137, 146)

#### 2. Candlestick interpretation
**File**: `backend/app/indicators/candlestick_interpretation.py`
- Remove `aligned_for_short` from `PatternInterpretation` dataclass (line 28)
- Remove `aligned_for_short = False` init (line 62)
- Remove all `aligned_for_short = True` assignments (lines 75, 86, 104, 114)
- Remove `aligned_for_short=aligned_for_short` from return (line 141)

#### 3. Two-candle patterns
**File**: `backend/app/indicators/two_candle_patterns.py`
- Remove `aligned_for_short` from `TwoCandleAnalysis` dataclass (line 41)
- Remove all `aligned_for_short=` assignments throughout (lines 106, 116, 128, 140, 152, 164, 171)

#### 4. Multi-day patterns
**File**: `backend/app/indicators/multi_day_patterns.py`
- Remove `aligned_for_short` from `MultiDayPatternResult` dataclass (line 50)
- Update `THREE_CANDLE_ALIGNMENT` dict — change from `(long, short, explanation)` tuples to `(long, explanation)` tuples (lines 55-64)
- Remove `aligned_for_short=aligned_short` in analyze function (lines 107, 119, 132, 141)

#### 5. RSI-2 analysis
**File**: `backend/app/indicators/rsi2_analysis.py`
- Remove `short_score` from `RSI2Analysis` dataclass (line 24)
- Delete `_score_for_short()` function entirely (lines 50-64)
- Remove `short_score=` from all `RSI2Analysis()` constructors (lines 85, 91, 98)

#### 6. Indicator registry
**File**: `backend/app/indicators/registry.py`
- Remove `pattern_interpretation.aligned_for_short` from `is_reversal` check (line 91) — simplify to just `aligned_for_long`
- Remove `"aligned_for_short"` from all returned dicts (lines 99, 116, 142)
- Remove `aligned_for_short` computation in CCI section (lines 133-134)

#### 7. Indicator schemas
**File**: `backend/app/schemas/indicators.py`
- Remove `"aligned_for_short": False` from example (line 112)

### Success Criteria:

#### Automated Verification:
- [ ] All indicator unit tests pass (after updating for removed fields)
- [ ] Python imports resolve correctly

#### Manual Verification:
- [ ] Indicator analysis endpoint returns results without `aligned_for_short`

**Implementation Note**: After completing this phase and all automated verification passes, pause for manual confirmation before proceeding to the next phase.

---

## Phase 2: Backend Evaluator — Remove SHORT from CriterionResult and Direction Logic

### Overview
Remove SHORT from the core evaluator that produces direction decisions. This is the key logic change.

### Changes Required:

#### 1. CriterionResult dataclass
**File**: `backend/app/services/live20_evaluator.py`
- Remove `aligned_for_short` field (line 56)
- Remove `score_for_short` field (line 58)
- Update docstring to remove SHORT references (lines 44-51)
- Update module docstring to remove "LONG/SHORT/NO_SETUP" (line 4)

#### 2. Live20Direction enum
**File**: `backend/app/services/live20_evaluator.py`
- Remove `SHORT = "SHORT"` (line 36)
- Update class docstring (line 73-74) — remove "SHORT: Uptrend + far above MA20"

#### 3. evaluate_criteria() method
**File**: `backend/app/services/live20_evaluator.py`
- Remove all `aligned_for_short=` and `score_for_short=` from every CriterionResult constructor:
  - Trend criterion (lines 121, 123)
  - MA20 distance criterion (lines 137, 139)
  - Candle criterion (lines 150, 152)
  - Volume criterion (lines 164, 166)
  - RSI-2 momentum criterion (lines 182, 184)
  - CCI momentum criterion (lines 200-206, 213, 215) — also delete `aligned_for_short` variable

#### 4. determine_direction_and_score() method
**File**: `backend/app/services/live20_evaluator.py`
- Simplify to only check LONG alignment:
  - Remove `short_aligned` calculation (line 243)
  - Remove SHORT direction branch (lines 248-250)
  - Simplify NO_SETUP branch — no need for `max(long_score, short_score)` (lines 253-255)
  - Update docstring

```python
def determine_direction_and_score(self, criteria: list[CriterionResult]) -> tuple[str, int]:
    """Determine direction and calculate score based on LONG criteria alignment.

    LONG-only: returns LONG when >= 3 criteria aligned, NO_SETUP otherwise.
    """
    long_aligned = sum(1 for c in criteria if c.aligned_for_long)

    if long_aligned >= self.MIN_CRITERIA_FOR_SETUP:
        direction = Live20Direction.LONG
        score = sum(c.score_for_long for c in criteria if c.aligned_for_long)
    else:
        direction = Live20Direction.NO_SETUP
        score = sum(c.score_for_long for c in criteria if c.aligned_for_long)

    return direction, score
```

### Success Criteria:

#### Automated Verification:
- [ ] Evaluator unit tests pass (after updating for removed fields/logic)
- [ ] No SHORT direction can be produced

---

## Phase 3: Backend Service, Worker, Repository — Remove SHORT Handling

### Overview
Remove SHORT handling from the service that creates recommendations, the worker that counts results, and the repository that filters runs.

### Changes Required:

#### 1. Live20 Service
**File**: `backend/app/services/live20_service.py`
- Remove all SHORT direction checks in criterion alignment computation (lines 142, 147, 153, 158, 167, 187)
- Simplify all alignment checks to just use `c.aligned_for_long` (since direction is only LONG or NO_SETUP, alignment = `direction == LONG and c.aligned_for_long`)
- Remove SHORT branch in RSI-2 score assignment (lines 195-196)
- Remove `short_score` references (lines 199-200)
- Update NOTE comment about short_score (lines 204-208)

#### 2. Live20 Worker
**File**: `backend/app/services/live20_worker.py`
- Remove `short_count` tracking entirely (lines 73-76, 85, 132-133)
- Remove `short_count` from final update values (line 175)
- Remove `SHORT={short_count}` from log message (line 185)

#### 3. Live20 Run Repository
**File**: `backend/app/repositories/live20_run_repository.py`
- Remove SHORT branch in `list_runs()` direction filter (line 139-140)
- Update docstring references

#### 4. RecommendationDecision enum
**File**: `backend/app/models/recommendation.py`
- Remove `SHORT = "SHORT"` from enum (line 37)
- Update docstring (lines 30-33)
- Update CHECK constraint — remove 'SHORT' (line 187)
- Update `live20_direction` doc (line 159)

#### 5. Live20Run model
**File**: `backend/app/models/live20_run.py`
- Remove `short_count` column (lines 48-50)
- Update `__repr__` to remove `short={self.short_count}` (line 129)

#### 6. Live20RunRepository
**File**: `backend/app/repositories/live20_run_repository.py`
- Remove `short_count` parameter from `create()` method (line 42)
- Remove `short_count=short_count` from `Live20Run()` constructor (line 73)
- Remove `SHORT={short_count}` from log message (line 88)
- Update `list_runs()` docstring

### Success Criteria:

#### Automated Verification:
- [ ] Service and worker unit tests pass
- [ ] No SHORT references remain in service layer

---

## Phase 4: Backend API, Schemas, Docs — Remove SHORT from Public Interface

### Changes Required:

#### 1. Live20 API endpoints
**File**: `backend/app/api/v1/live20.py`
- Update direction filter type from `Literal["LONG", "SHORT", "NO_SETUP"]` to `Literal["LONG", "NO_SETUP"]` (lines 131, 212)
- Remove `"short"` from counts dict (line 190)
- Update docstrings

#### 2. Live20 schemas
**File**: `backend/app/schemas/live20.py`
- Update `recommendation` field doc (line 27) — remove "SHORT"
- Update `direction` field doc (line 58) — remove "SHORT"
- Update counts description (line 217) — remove "short"
- Update `directions` field in `PortfolioRecommendRequest` (line 248-251) — remove SHORT example
- Update examples (line 88)

#### 3. API docs
**File**: `backend/app/core/docs.py`
- Update Live20 description (line 120) — remove "or SHORT (overbought pullback)"

#### 4. Indicator schemas
**File**: `backend/app/schemas/indicators.py`
- Already handled in Phase 1

#### 5. Live20Run schemas (CRITICAL — Gemini review catch)
**File**: `backend/app/schemas/live20_run.py`
- Remove `short_count` field from `Live20RunSummary` (line 28)
- Remove `short_count=obj.short_count` from `Live20RunSummary.model_validate()` (line 97)
- Remove `short_count` from `Live20RunSummary` example (line 53)
- Remove `short_count` field from `Live20RunDetailResponse` (line 135)
- Remove `short_count` from `Live20RunDetailResponse` example (line 163)

#### 6. Live20ResultsResponse counts
**File**: `backend/app/schemas/live20.py`
- Update counts description to remove `short` (line 217): `"Direction counts: {long: int, no_setup: int}"`

### Success Criteria:

#### Automated Verification:
- [ ] API integration tests pass
- [ ] OpenAPI schema validates

---

## Phase 5: Database Migration

### Overview
Create an Alembic migration to:
1. Convert existing `SHORT` data to `NO_SETUP`
2. Drop `short_count` column from `live20_runs`
3. Update CHECK constraint on `recommendations`

### Changes Required:

#### 1. New migration file
**File**: `backend/alembic/versions/YYYYMMDD_HHMM-<hash>_remove_short_direction.py`

```python
"""Remove SHORT direction — system is LONG-only.

Revision ID: <auto>
Revises: f364d831b617
"""

def upgrade():
    # 1. Convert existing SHORT recommendations to NO_SETUP
    op.execute("""
        UPDATE recommendations
        SET recommendation = 'NO_SETUP',
            live20_direction = 'NO_SETUP'
        WHERE live20_direction = 'SHORT'
    """)

    # 2. Drop short_count column from live20_runs
    op.drop_column('live20_runs', 'short_count')

    # 3. Update CHECK constraint (remove SHORT)
    op.drop_constraint('ck_recommendations_valid_decision', 'recommendations')
    op.create_check_constraint(
        'ck_recommendations_valid_decision',
        'recommendations',
        "recommendation IN ('Buy', 'Watchlist', 'Not Buy', 'LONG', 'NO_SETUP')"
    )

def downgrade():
    # Re-add short_count column
    op.add_column('live20_runs', sa.Column('short_count', sa.Integer(), nullable=False, server_default='0'))

    # Restore CHECK constraint with SHORT
    op.drop_constraint('ck_recommendations_valid_decision', 'recommendations')
    op.create_check_constraint(
        'ck_recommendations_valid_decision',
        'recommendations',
        "recommendation IN ('Buy', 'Watchlist', 'Not Buy', 'LONG', 'SHORT', 'NO_SETUP')"
    )
```

### Success Criteria:

#### Automated Verification:
- [ ] Migration applies cleanly
- [ ] Migration downgrades cleanly
- [ ] No SHORT data remains after upgrade

**Implementation Note**: After completing this phase and all automated verification passes, pause for manual confirmation before proceeding to frontend changes.

---

## Phase 6: Frontend — Remove SHORT from UI

### Overview
Remove SHORT from types, filters, components, and all display logic.

### Changes Required:

#### 1. Types
**File**: `frontend/src/types/live20.ts`
- Change `Live20Direction` from `'LONG' | 'SHORT' | 'NO_SETUP'` to `'LONG' | 'NO_SETUP'` (line 1)
- Remove `short` from `Live20Counts` (line 66) and `Live20ResultsResponse.counts` (line 59)
- Remove `short_count` from `Live20RunSummary` (line 78) and `Live20RunDetail` (line 101)

#### 2. Filter hook
**File**: `frontend/src/hooks/useLive20Filters.ts`
- No changes needed — filter already works generically with direction values

#### 3. Filter component — remove SHORT button
**File**: `frontend/src/components/live20/Live20Filters.tsx`
- Remove the SHORT `FilterButton` block (lines 122-128)
- Remove `'short'` from `FilterButton` variant type (line 46)
- Remove `case 'short':` from `getActiveStyles()` (lines 55-56)

#### 4. Table — remove SHORT badge
**File**: `frontend/src/components/live20/Live20Table.tsx`
- Remove `SHORT` entry from `DirectionBadge` variants (lines 46-49)

#### 5. History tab — remove SHORT filter
**File**: `frontend/src/components/live20/Live20HistoryTab.tsx`
- Change `DirectionFilter` type from `'all' | 'LONG' | 'SHORT' | 'NO_SETUP'` to `'all' | 'LONG' | 'NO_SETUP'` (line 13)
- Remove SHORT filter button (lines 171-179)

#### 6. Recommend Portfolio dialog — remove SHORT option
**File**: `frontend/src/components/live20/RecommendPortfolioDialog.tsx`
- Remove `includeShort` state (line 86)
- Remove SHORT from `directions` derivation (line 91)
- Remove SHORT checkbox from UI
- Simplify directions to always be `['LONG']`

#### 7. Colors constants
**File**: `frontend/src/constants/colors.ts`
- Remove `'SHORT'` from `TradeDirection` type (line 39)
- Remove `SHORT` entries from `SCREENER_COLORS.direction` (line 58) and `SCREENER_COLORS.badge` (line 74)

#### 8. useLive20 hook — remove short_count
**File**: `frontend/src/hooks/useLive20.ts`
- Remove `short:` from counts update (line 82)

#### 9. Live20 service
**File**: `frontend/src/services/live20Service.ts`
- Update `has_direction` type to remove SHORT (line 90)
- Update description (line 56)

### Success Criteria:

#### Automated Verification:
- [ ] TypeScript compiles without errors
- [ ] All frontend tests pass
- [ ] No SHORT references remain in frontend source

#### Manual Verification:
- [ ] Filter row shows only: All | Long | No Setup
- [ ] Direction badges only show LONG and NO SETUP
- [ ] Recommend Portfolio dialog has no SHORT checkbox

---

## Test Updates (Integrated Per Phase)

Tests should be updated **within each phase**, not batched at the end. This ensures each phase is independently verifiable.

### Phase 1 tests (indicators):
- `tests/indicators/test_multi_day_patterns.py` — remove `aligned_for_short` assertions
- `tests/indicators/test_two_candle_patterns.py` — remove `aligned_for_short` assertions
- `tests/indicators/test_volume.py` — remove `aligned_for_short` assertions
- `tests/unit/indicators/test_candlestick_interpretation.py` — remove `aligned_for_short` assertions
- `tests/unit/indicators/test_registry.py` — remove `aligned_for_short` from result checks
- `tests/indicators/test_rsi2_analysis.py` — remove all `short_score` and `_score_for_short` tests

### Phase 2 tests (evaluator):
- `tests/unit/services/test_live20_evaluator.py` — remove SHORT direction tests, update CriterionResult constructors, remove `score_for_short` assertions

### Phase 3 tests (service/worker):
- `tests/unit/services/test_live20_worker.py` — remove SHORT count tests, update mock data

### Phase 4 tests (API):
- `tests/integration/test_live20_recommend.py` — remove SHORT test fixtures and tests
- `tests/integration/test_live20_runs_api.py` — remove SHORT direction filter tests
- `tests/integration/test_live20_api.py` — remove SHORT direction filter test
- `tests/integration/test_indicator_analysis.py` — remove `aligned_for_short` assertions

### Phase 6 tests (frontend):
- `src/hooks/useLive20Filters.test.ts` — remove SHORT mock data and direction filter tests
- `src/hooks/useLive20.test.ts` — remove SHORT mock data
- `src/pages/Live20RunDetail.test.tsx` — remove SHORT mock data
- `src/components/live20/Live20Dashboard.test.tsx` — remove SHORT mock data
- `src/components/live20/Live20Table.test.tsx` — remove SHORT badge test
- `src/components/live20/RecommendPortfolioDialog.test.tsx` — remove SHORT tests
- `src/components/live20/Live20HistoryTab.test.tsx` — remove SHORT filter tests (if any)

---

## Testing Strategy

### Unit Tests:
- All existing tests updated to remove SHORT references
- Verify `determine_direction_and_score()` can only return LONG or NO_SETUP
- Verify indicators no longer have `aligned_for_short` attribute
- Verify CriterionResult no longer has `aligned_for_short` or `score_for_short`

### Integration Tests:
- API endpoints accept only LONG/NO_SETUP direction filters
- Portfolio recommendation works with LONG-only
- Run creation and completion works without short_count

### Manual Testing Steps:
1. Run Live20 analysis on a few symbols — verify all results are LONG or NO_SETUP
2. Check filter UI — only All/Long/No Setup buttons visible
3. Check history tab — only All/Long/No Setup filters
4. Run portfolio recommendation — no SHORT checkbox, works correctly
5. Verify direction badges show only LONG and NO SETUP styling

## References

- Original ticket: [GitHub Issue #24](https://github.com/dimakrest/trading-analyst/issues/24)
- Related plan: `thoughts/shared/plans/2026-02-15-pluggable-scoring-algorithms.md` (Phase 2, Section 13)
