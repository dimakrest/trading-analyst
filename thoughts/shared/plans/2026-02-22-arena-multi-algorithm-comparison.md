# Arena Multi-Algorithm Comparison Implementation Plan

## Overview

Allow users to compare portfolio selection strategies side-by-side by creating a group of simulations (one per strategy) from a single form submission, then viewing results on a dedicated comparison page with equity curve overlays, sortable metrics table, and benchmark comparison.

## Current State Analysis

### Key Architecture Points:
- Each `ArenaSimulation` stores a single `agent_type` + `agent_config` JSON (including `portfolio_strategy`) — `backend/app/models/arena.py:100-109`
- 4 portfolio strategies registered in `SELECTOR_REGISTRY`: `none`, `score_sector_low_atr`, `score_sector_high_atr`, `score_sector_moderate_atr` — `backend/app/services/portfolio_selector.py:160-165`
- `POST /api/v1/arena/simulations` creates one simulation per call — `backend/app/api/v1/arena.py:147-221`
- Frontend routes: `/arena` (list + create) and `/arena/:id` (detail) — `frontend/src/App.tsx:48-49`
- `ArenaEquityChart` already supports multi-series (portfolio + SPY + QQQ) on one chart — `frontend/src/components/arena/ArenaEquityChart.tsx`
- `Simulation` type carries all scalar metrics needed for comparison without fetching full detail — `frontend/src/types/arena.ts:30-62`

### What Exists:
- Complete single-simulation flow (create, run, view results)
- Equity chart with multi-series pattern (portfolio + benchmarks)
- Portfolio strategy single-select in `ArenaSetupForm` — `frontend/src/components/arena/ArenaSetupForm.tsx:451-469`

### What's Missing:
- No `group_id` concept to link related simulations
- No multi-strategy selection in the form
- No comparison page or route
- No API endpoint to fetch grouped simulations

## Desired End State

1. User selects multiple portfolio strategies (via checkboxes) in the setup form
2. Clicking "Start Comparison" creates N simulations (one per strategy) linked by `group_id`
3. User is redirected to `/arena/compare/:groupId` which shows:
   - Progress overview (all simulations' status/progress)
   - Sortable summary table with one row per strategy, one column per metric
   - Equity curve chart with all strategies overlaid + benchmarks
4. Clicking a row in the summary table drills down to the existing `/arena/:id` detail view
5. Simulation list page shows grouped simulations with a "Compare" link

## What We're NOT Doing

- No changes to the simulation engine or agent layer (strategies vary, agent stays the same)
- No new backend worker logic (each simulation runs independently via existing worker)
- No changes to the existing single-simulation detail page
- No comparison of different agent types or scoring algorithms (only portfolio strategies)
- No persistence of comparison metadata beyond `group_id` (no separate comparison table)

## Implementation Approach

**Grouped Simulations**: Add a nullable `group_id` (UUID) column to `arena_simulations`. When the user selects multiple strategies, the API creates N simulations with the same config except `portfolio_strategy`, all sharing the same `group_id`. A new API endpoint fetches all simulations by `group_id`. The frontend comparison page polls this endpoint and renders the comparison view.

---

## Phase 1: Backend — Group Model & API

### Overview
Add `group_id` column to the model, create a batch-create endpoint, and add a group-fetch endpoint.

### Changes Required:

#### 1. Database Migration
**File**: New migration `backend/alembic/versions/YYYYMMDD_HHMM-_add_arena_group_id.py`
**Changes**: Add nullable `group_id` column (UUID stored as String(36)) with index

```python
from alembic import op
import sqlalchemy as sa

def upgrade() -> None:
    op.add_column(
        "arena_simulations",
        # Note: no index=True here — the explicit op.create_index below provides
        # the named index referenced in downgrade(). Using both would create duplicates.
        sa.Column("group_id", sa.String(36), nullable=True),
    )
    op.create_index("ix_arena_simulations_group_id", "arena_simulations", ["group_id"])

def downgrade() -> None:
    op.drop_index("ix_arena_simulations_group_id", table_name="arena_simulations")
    op.drop_column("arena_simulations", "group_id")
```

#### 2. Model Update
**File**: `backend/app/models/arena.py`
**Changes**: Add `group_id` column to `ArenaSimulation`

After `agent_config` (line ~109), add:
```python
# Comparison grouping
group_id: Mapped[str | None] = mapped_column(
    String(36), nullable=True, index=True,
    doc="UUID linking simulations in a multi-strategy comparison group",
)
```

#### 3. Schema Updates
**File**: `backend/app/schemas/arena.py`
**Changes**:

a) Extract shared validator logic into module-level standalone functions **before** both schema classes. This replaces the fragile `__func__` pattern (which accesses Pydantic internals and can break across minor versions):

```python
# --- Shared validator functions (referenced by both schemas) ---

def _normalize_symbols_value(v: Any) -> list[str]:
    """Normalize symbols: split comma-separated strings, uppercase, deduplicate."""
    if isinstance(v, str):
        v = [s.strip() for s in v.split(",")]
    return list(dict.fromkeys(s.upper() for s in v if s.strip()))


def _validate_symbols_count_value(v: list[str]) -> list[str]:
    if len(v) > 500:
        raise ValueError("Cannot submit more than 500 symbols")
    return v


def _validate_date_range_value(v: date, info: FieldValidationInfo) -> date:
    start = info.data.get("start_date")
    if start and v <= start:
        raise ValueError("end_date must be after start_date")
    return v


def _validate_agent_type_value(v: str) -> str:
    allowed = {"live20"}
    if v not in allowed:
        raise ValueError(f"Unknown agent_type: {v}. Allowed: {allowed}")
    return v
```

**Note**: Match the actual validator bodies from `CreateSimulationRequest` — the above is illustrative. The key constraint is that these must be plain functions (not classmethods), referencing no `self`/`cls`.

b) Update `CreateSimulationRequest` to use the shared functions:
```python
_normalize_symbols = field_validator("symbols", mode="before")(_normalize_symbols_value)
_validate_symbols_count = field_validator("symbols")(_validate_symbols_count_value)
_validate_date_range = field_validator("end_date")(_validate_date_range_value)
_validate_agent_type = field_validator("agent_type")(_validate_agent_type_value)
```

c) Add `CreateComparisonRequest` schema using the same shared functions:
```python
class CreateComparisonRequest(StrictBaseModel):
    """Request to create a multi-strategy comparison run.

    Creates one simulation per selected portfolio strategy,
    all sharing the same group_id and base configuration.
    """
    name: str | None = Field(default=None, max_length=255)
    stock_list_id: int | None = Field(default=None)
    stock_list_name: str | None = Field(default=None, max_length=255)
    symbols: list[str] = Field(..., min_length=1)
    start_date: date = Field(...)
    end_date: date = Field(...)
    initial_capital: Decimal = Field(default=Decimal("10000"), gt=0)
    position_size: Decimal = Field(default=Decimal("1000"), gt=0)
    agent_type: str = Field(default="live20")
    trailing_stop_pct: float = Field(default=5.0, gt=0, lt=100)
    min_buy_score: int = Field(default=60, ge=20, le=100)
    agent_config_id: int | None = Field(None)
    scoring_algorithm: Literal["cci", "rsi2"] = Field(default="cci")
    portfolio_strategies: list[str] = Field(
        ..., min_length=2, max_length=4,
        description="Portfolio strategies to compare (2-4 required)",
    )
    max_per_sector: int | None = Field(default=None, ge=1)
    max_open_positions: int | None = Field(default=None, ge=1)

    # Shared validators — same standalone functions as CreateSimulationRequest
    _normalize_symbols = field_validator("symbols", mode="before")(_normalize_symbols_value)
    _validate_symbols_count = field_validator("symbols")(_validate_symbols_count_value)
    _validate_date_range = field_validator("end_date")(_validate_date_range_value)
    _validate_agent_type = field_validator("agent_type")(_validate_agent_type_value)

    @field_validator("portfolio_strategies")
    @classmethod
    def validate_strategies(cls, v: list[str]) -> list[str]:
        from app.services.portfolio_selector import SELECTOR_REGISTRY
        for s in v:
            if s not in SELECTOR_REGISTRY:
                available = ", ".join(SELECTOR_REGISTRY.keys())
                raise ValueError(f"Unknown strategy: {s}. Available: {available}")
        if len(v) != len(set(v)):
            raise ValueError("Duplicate strategies not allowed")
        return v
```

**TODO (follow-up)**: Extract shared fields into a `BaseSimulationRequest` mixin to eliminate field duplication between the two schemas.

b) Add `ComparisonResponse` schema:
```python
class ComparisonResponse(StrictBaseModel):
    """Response for a comparison group."""
    group_id: str
    simulations: list[SimulationResponse]
```

c) Add `group_id` to `SimulationResponse`:
```python
group_id: str | None = None
```

#### 4. API Endpoints
**File**: `backend/app/api/v1/arena.py`
**Changes**: Add two new endpoints

a) `POST /api/v1/arena/comparisons` — creates grouped simulations:
```python
@router.post(
    "/comparisons",
    response_model=ComparisonResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Create Multi-Strategy Comparison",
    description=(
        "Creates one simulation per selected portfolio strategy, all sharing a common "
        "group_id. The simulations are created atomically in a single transaction and "
        "queued for independent execution by the worker. Returns 202 immediately; "
        "poll GET /comparisons/{group_id} for progress."
    ),
    operation_id="create_arena_comparison",
    responses={
        400: {"description": "Validation error (invalid strategies, date range, symbols)"},
        404: {"description": "Agent config not found (when agent_config_id is provided)"},
    },
)
async def create_comparison(
    request: CreateComparisonRequest,
    session: AsyncSession = Depends(get_db_session),
) -> ComparisonResponse:
    import uuid

    # Look up agent config if provided (same logic as create_simulation)
    if request.agent_config_id:
        config_repo = AgentConfigRepository(session)
        agent_config_obj = await config_repo.get_by_id(request.agent_config_id)
        if not agent_config_obj:
            raise HTTPException(status_code=404, detail=f"Agent config {request.agent_config_id} not found")
        scoring_algorithm = agent_config_obj.scoring_algorithm
    else:
        scoring_algorithm = request.scoring_algorithm

    group_id = str(uuid.uuid4())
    simulations = []

    for strategy in request.portfolio_strategies:
        agent_config = {
            "trailing_stop_pct": request.trailing_stop_pct,
            "min_buy_score": request.min_buy_score,
            "scoring_algorithm": scoring_algorithm,
            "portfolio_strategy": strategy,
            "max_per_sector": request.max_per_sector,
            "max_open_positions": request.max_open_positions,
        }
        if request.agent_config_id is not None:
            agent_config["agent_config_id"] = request.agent_config_id

        sim = ArenaSimulation(
            name=f"{request.name or 'Comparison'} [{strategy}]",
            stock_list_id=request.stock_list_id,
            stock_list_name=request.stock_list_name,
            symbols=request.symbols,
            start_date=request.start_date,
            end_date=request.end_date,
            initial_capital=request.initial_capital,
            position_size=request.position_size,
            agent_type=request.agent_type,
            agent_config=agent_config,
            group_id=group_id,
            status=SimulationStatus.PENDING.value,
            current_day=0,
            total_days=0,
        )
        session.add(sim)
        simulations.append(sim)

    await session.commit()
    for sim in simulations:
        await session.refresh(sim)

    logger.info(
        "Created comparison group %s with %d simulations: %s",
        group_id,
        len(simulations),
        request.portfolio_strategies,
    )

    return ComparisonResponse(
        group_id=group_id,
        simulations=[_build_simulation_response(s) for s in simulations],
    )
```

b) `GET /api/v1/arena/comparisons/{group_id}` — fetch comparison group:
```python
@router.get(
    "/comparisons/{group_id}",
    response_model=ComparisonResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Comparison Group",
    description=(
        "Returns all simulations belonging to the given comparison group, ordered by "
        "creation (simulation id). Used by the frontend to poll progress and render "
        "the comparison page. Returns 404 if the group_id is unknown."
    ),
    operation_id="get_arena_comparison",
    responses={
        404: {"description": "Comparison group not found"},
    },
)
async def get_comparison(
    group_id: str,
    session: AsyncSession = Depends(get_db_session),
) -> ComparisonResponse:
    stmt = (
        select(ArenaSimulation)
        .where(ArenaSimulation.group_id == group_id)
        .order_by(ArenaSimulation.id)
    )
    result = await session.execute(stmt)
    simulations = result.scalars().all()

    if not simulations:
        logger.warning("Comparison group not found: %s", group_id)
        raise HTTPException(status_code=404, detail="Comparison group not found")

    return ComparisonResponse(
        group_id=group_id,
        simulations=[_build_simulation_response(s) for s in simulations],
    )
```

#### 5. Update `_build_simulation_response`
**File**: `backend/app/api/v1/arena.py:38-88`
**Changes**: Add `group_id=simulation.group_id` to the `SimulationResponse` constructor.

### Success Criteria:

#### Automated Verification:
- [ ] Migration runs successfully: `./scripts/dc.sh exec backend-dev alembic upgrade head`
- [ ] All existing Arena tests still pass: `./scripts/dc.sh exec backend-dev pytest tests/unit/api/v1/test_arena.py tests/unit/services/arena/ -v`
- [ ] New tests pass for:
  - `POST /comparisons` creates N simulations with shared `group_id` and correct per-strategy `agent_config`
  - `POST /comparisons` validates `portfolio_strategies` (min 2, max 4, no duplicates, valid names)
  - `POST /comparisons` with valid `agent_config_id` uses config's `scoring_algorithm`, not request's
  - `POST /comparisons` with nonexistent `agent_config_id` returns 404
  - `POST /comparisons` with `portfolio_strategies` of length 1 returns 422
  - `GET /comparisons/{group_id}` returns all simulations in the group, ordered by id
  - `GET /comparisons/{group_id}` returns 404 for unknown group
  - `group_id` appears in `SimulationResponse` for both the list and detail endpoints
  - Shared validator functions produce identical behavior in both schema classes (symbol normalization, date range, agent_type)

#### Manual Verification:
- [ ] Create a comparison via API and verify simulations appear in the list endpoint
- [ ] Each simulation in the group is picked up by the worker independently
- [ ] Simulations complete and produce independent results

**Implementation Note**: After completing this phase and all automated verification passes, pause for manual confirmation before proceeding to the next phase.

---

## Phase 2: Frontend — Multi-Strategy Selection & Comparison Creation

### Overview
Update the setup form to allow selecting multiple portfolio strategies and submit as a comparison. Add the API client function.

### Changes Required:

#### 1. Types
**File**: `frontend/src/types/arena.ts`
**Changes**:

a) Add `group_id` to `Simulation`:
```typescript
group_id: string | null;
```
Add after `max_open_positions` (line ~46).

b) Add `CreateComparisonRequest` type:
```typescript
/** Request body for creating a multi-strategy comparison */
export interface CreateComparisonRequest {
  name?: string;
  stock_list_id?: number;
  stock_list_name?: string;
  symbols: string[];
  start_date: string;
  end_date: string;
  initial_capital?: number;
  position_size?: number;
  agent_type?: string;
  trailing_stop_pct?: number;
  min_buy_score?: number;
  agent_config_id?: number;
  scoring_algorithm?: ScoringAlgorithm;
  portfolio_strategies: string[];
  max_per_sector?: number | null;
  max_open_positions?: number | null;
}
```

c) Add `ComparisonResponse` type:
```typescript
/** Response from creating or fetching a comparison group */
export interface ComparisonResponse {
  group_id: string;
  simulations: Simulation[];
}
```

#### 2. API Service
**File**: `frontend/src/services/arenaService.ts`
**Changes**: Add two functions:

```typescript
import type { ComparisonResponse, CreateComparisonRequest } from '../types/arena';

/** Create a multi-strategy comparison (N simulations) */
export const createComparison = async (
  request: CreateComparisonRequest,
): Promise<ComparisonResponse> => {
  const response = await apiClient.post<ComparisonResponse>(
    `${API_BASE}/comparisons`,
    request,
  );
  return response.data;
};

/** Fetch comparison group by group_id */
export const getComparison = async (
  groupId: string,
): Promise<ComparisonResponse> => {
  const response = await apiClient.get<ComparisonResponse>(
    `${API_BASE}/comparisons/${groupId}`,
  );
  return response.data;
};
```

#### 3. Setup Form — Multi-Strategy Selection
**File**: `frontend/src/components/arena/ArenaSetupForm.tsx`
**Changes**:

a) Replace the single `Select` for portfolio strategy with a checkbox group. When multiple strategies are selected (2+), the form submits via `createComparison` instead of `createSimulation`.

b) Update props interface:
```typescript
interface ArenaSetupFormProps {
  onSubmit: (request: CreateSimulationRequest) => Promise<void>;
  onSubmitComparison: (request: CreateComparisonRequest) => Promise<void>;
  isLoading: boolean;
  initialValues?: { /* existing */ };
}
```

c) Replace `portfolioStrategy` state (single string) with `selectedStrategies` state (string array):
```typescript
const [selectedStrategies, setSelectedStrategies] = useState<string[]>(['none']);
```

d) Replace the `Select` component with a `ToggleGroup` (multi-select) or checkboxes from shadcn. Each of the 4 `PORTFOLIO_STRATEGIES` gets a toggle button. Selection rules:
- **0 selected**: Submit button disabled. This state is transient (default is 1 selected).
- **1 selected**: Single-simulation flow. Submit button reads "Start Simulation".
- **2–4 selected**: Comparison flow. Submit button reads "Start Comparison (N strategies)". The "Start Comparison" button must be disabled when `selectedStrategies.length < 2` — do NOT rely solely on the backend 422 for this; enforce client-side to give immediate feedback.

e) Update `handleSubmit`:
- If `selectedStrategies.length === 1` → call `onSubmit` with the single strategy (existing flow)
- If `selectedStrategies.length >= 2` → call `onSubmitComparison` with `portfolio_strategies: selectedStrategies`
- If `selectedStrategies.length === 0` → no-op (button is disabled, this branch should never fire)

f) Update the submit button text:
- 0 strategies: "Select a Strategy" (disabled)
- 1 strategy: "Start Simulation"
- 2+ strategies: "Start Comparison (N strategies)"

g) Show `max_per_sector` / `max_open_positions` fields when any strategy other than "none" is selected.

#### 4. Arena Page — Handle Comparison Creation
**File**: `frontend/src/pages/Arena.tsx`
**Changes**:

Add `handleCreateComparison` callback:
```typescript
const handleCreateComparison = async (request: CreateComparisonRequest) => {
  try {
    setIsCreating(true);
    const comparison = await createComparison(request);
    toast.success(`Comparison started — ${comparison.simulations.length} simulations`);
    navigate(`/arena/compare/${comparison.group_id}`);
  } catch {
    toast.error('Failed to create comparison');
  } finally {
    setIsCreating(false);
  }
};
```

Pass `onSubmitComparison={handleCreateComparison}` to `ArenaSetupForm`.

### Success Criteria:

#### Automated Verification:
- [ ] TypeScript compiles without errors
- [ ] Existing `ArenaSetupForm.test.tsx` passes (single strategy flow unchanged)
- [ ] New tests for multi-strategy form behavior:
  - Selecting 2+ strategies shows "Start Comparison (N strategies)" button text
  - Selecting 1 strategy shows "Start Simulation" button text
  - Selecting 0 strategies shows disabled "Select a Strategy" button
  - Deselecting all-but-one from a 2-strategy selection reverts to "Start Simulation"
  - Clicking a selected strategy deselects it (toggle behavior)
  - Portfolio constraint fields appear when any non-"none" strategy is selected
  - Form calls `onSubmitComparison` (not `onSubmit`) when 2+ strategies are selected
  - Form calls `onSubmit` (not `onSubmitComparison`) when exactly 1 strategy is selected

#### Manual Verification:
- [ ] Can select multiple strategies via toggle/checkbox UI
- [ ] Single strategy submits via existing flow (navigates to `/arena/:id`)
- [ ] Multiple strategies submits via comparison flow (navigates to `/arena/compare/:groupId`)
- [ ] Strategy selection is visually clear (which are selected, which aren't)

**Implementation Note**: After completing this phase and all automated verification passes, pause for manual confirmation before proceeding to the next phase.

---

## Phase 3: Frontend — Comparison Page

### Overview
New page at `/arena/compare/:groupId` with polling, summary table, equity curve overlay, and benchmark comparison.

### Changes Required:

#### 1. Route
**File**: `frontend/src/App.tsx`
**Changes**: Add route:
```tsx
<Route path="/arena/compare/:groupId" element={<ArenaComparison />} />
```

#### 2. Polling Hook
**File**: `frontend/src/hooks/useComparisonPolling.ts` (new file)
**Changes**: Similar to `useArenaPolling` but fetches `getComparison(groupId)` and stops when all simulations reach terminal status.

```typescript
import { useEffect, useRef, useState } from 'react';
import { getComparison } from '../services/arenaService';
import type { ComparisonResponse } from '../types/arena';

const POLL_INTERVAL_MS = 3000;
const TERMINAL_STATUSES = new Set(['completed', 'cancelled', 'failed']);

export const useComparisonPolling = (groupId: string) => {
  const [data, setData] = useState<ComparisonResponse | null>(null);
  const [isPolling, setIsPolling] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const clearPolling = () => {
    if (intervalRef.current !== null) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
    setIsPolling(false);
  };

  useEffect(() => {
    let cancelled = false;

    const fetchData = async () => {
      try {
        const result = await getComparison(groupId);
        if (cancelled) return;
        setData(result);
        setError(null);
        // Stop polling when all simulations are in a terminal state
        const allDone = result.simulations.every((s) => TERMINAL_STATUSES.has(s.status));
        if (allDone) {
          clearPolling();
        }
      } catch {
        if (cancelled) return;
        // Keep polling on transient network errors; surface the error in UI
        setError('Failed to load comparison');
      }
    };

    fetchData();
    intervalRef.current = setInterval(fetchData, POLL_INTERVAL_MS);

    return () => {
      cancelled = true;
      if (intervalRef.current !== null) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    };
  }, [groupId]); // re-runs only if groupId changes

  return { data, isPolling, error, refetch: () => { /* manual trigger if needed */ } };
};
```

**Key changes from original**:
- Single `useEffect` manages the entire polling lifecycle — no coordination between two effects
- `cancelled` flag prevents stale async callbacks from updating state after unmount/groupId change (prevents memory leak)
- Interval is always cleared in the effect cleanup, so React Strict Mode double-invocation is safe
- Error path keeps polling (transient network errors); UI surfaces the error state via `error`

#### 3. Comparison Page
**File**: `frontend/src/pages/ArenaComparison.tsx` (new file)
**Changes**: Main comparison page component.

Layout (top to bottom):
1. **Header**: "Strategy Comparison" + back button + group progress indicator
2. **Progress Cards**: One card per simulation showing strategy name, status badge, progress bar (current_day/total_days)
3. **Summary Ranking Table** (`ArenaComparisonTable`): Shown when at least 1 simulation is complete
4. **Equity Curve Comparison** (`ArenaComparisonChart`): Shown when all simulations are complete
5. **Benchmark overlays**: SPY/QQQ toggles (same pattern as existing `ArenaEquityChart`)

#### 4. Summary Ranking Table Component
**File**: `frontend/src/components/arena/ArenaComparisonTable.tsx` (new file)
**Changes**: Sortable table with one row per simulation.

Columns (all sortable):
| Column | Source Field | Format |
|---|---|---|
| Strategy | `portfolio_strategy` from `agent_config` | Badge |
| Return | `total_return_pct` | +X.X% / -X.X% (colored) |
| Max DD | `max_drawdown_pct` | -X.X% |
| Sharpe | `sharpe_ratio` | X.XX |
| Profit Factor | `profit_factor` | X.XX |
| Win Rate | `winning_trades / total_trades * 100` | X.X% |
| Total Trades | `total_trades` | N |
| Avg Hold | `avg_hold_days` | X.X days |
| Avg Win | `avg_win_pnl` | $X.XX |
| Avg Loss | `avg_loss_pnl` | $X.XX |

Behavior:
- Default sort: Return descending (best return first)
- Click column header to sort by that metric
- Best value in each column gets `text-accent-bullish` highlight; worst gets `text-accent-bearish`
- **Edge case — all values equal**: When `min === max` for a column, apply no highlight to any row (no winner/loser when all strategies tie)
- **Edge case — zero trades**: Win Rate = `total_trades > 0 ? (winning_trades / total_trades * 100) : null`. Render `null` as `—`. Null values sort last regardless of direction.
- **Edge case — in-progress simulations**: Simulations that are not yet `completed` appear in the table with strategy badge + status badge, but all metric columns show `—`. They are excluded from best/worst highlight computation. They sort last (null metrics).
- Click row to navigate to `/arena/:id` (existing detail view)

Implementation approach:
- Use state `sortField` / `sortDirection` to track current sort
- Column headers render as clickable with sort indicator arrow
- Use `useMemo` to derive sorted simulations from sort state
- Compute per-column min/max over completed simulations only (skip null values)

#### 5. Equity Curve Comparison Chart Component
**File**: `frontend/src/components/arena/ArenaComparisonChart.tsx` (new file)
**Changes**: Multi-series equity chart showing all strategies on one axis.

Implementation:
- Similar structure to `ArenaEquityChart` but with N portfolio series instead of 1
- Each strategy gets a solid line with a distinct color from a predefined palette
- Benchmark series (SPY/QQQ) shown as dashed lines (same pattern as existing)
- Y-axis always in normalized % return mode (since comparing strategies)
- Legend shows strategy name + color for each series

Data flow:
- Receives `simulations: Simulation[]` (the comparison group, all `completed`)
- Fires N parallel `getSimulation(id)` calls (up to 4) using `Promise.all`
- While loading: render a spinner in the chart container (same height as final chart)
- On partial failure (some calls reject): render the successfully-loaded series + an inline warning banner listing which strategies failed to load. Do not block the chart on a single failure.
- Fetches benchmark data from the first simulation's id (lowest id in the group). If that sim's detail fetch failed, use the next available.
- After all detail fetches resolve, compute normalized `cumulative_return_pct` from each simulation's snapshots and render

**Performance note**: Each `getSimulation` call returns full positions + snapshots. For a 1-year sim this is acceptable at 2-3 users. If payload becomes a concern, a future `/simulations/{id}/snapshots` endpoint could be added.

Color palette for strategies (up to 4):
```typescript
const STRATEGY_COLORS = [
  '#2962FF',  // Blue
  '#FF6D00',  // Orange
  '#00C853',  // Green
  '#AA00FF',  // Purple
];
```

Chart configuration:
- All series use `PERCENT_PRICE_FORMAT` (`X.XX%`)
- Fixed height 320px (slightly taller than single-sim chart at 280px)
- Benchmark toggles identical to existing ArenaEquityChart pattern

#### 6. Strategy Color Constants
**File**: `frontend/src/constants/chartColors.ts`
**Changes**: Add strategy comparison colors to existing `CHART_COLORS`:
```typescript
export const STRATEGY_COLORS = ['#2962FF', '#FF6D00', '#00C853', '#AA00FF'] as const;
```

### Success Criteria:

#### Automated Verification:
- [ ] TypeScript compiles without errors
- [ ] New tests for:
  - `ArenaComparisonTable` renders correct columns and sort behavior
  - `ArenaComparisonTable` highlights best/worst values; no highlight when all values equal
  - `ArenaComparisonTable` shows `—` for metrics of in-progress simulations
  - `ArenaComparisonTable` shows `—` for Win Rate when `total_trades === 0`
  - `ArenaComparisonTable` row click navigates to detail
  - `ArenaComparison` page shows progress cards when simulations are running
  - `useComparisonPolling` continues polling when only some simulations are terminal
  - `useComparisonPolling` stops polling when ALL simulations are terminal
  - `useComparisonPolling` clears interval on unmount (no memory leak / stale updates after unmount)
  - `useComparisonPolling` surfaces error state but keeps polling on network error

#### Manual Verification:
- [ ] Create a comparison with 4 strategies and navigate to comparison page
- [ ] Progress cards update in real-time as simulations run
- [ ] Summary table appears as simulations complete, sorting works on all columns
- [ ] Equity chart shows all strategy curves + benchmarks with distinct colors
- [ ] Legend correctly identifies each strategy by color
- [ ] Clicking a row navigates to the individual simulation detail page
- [ ] Back button returns to `/arena`

**Implementation Note**: After completing this phase and all automated verification passes, pause for manual confirmation before proceeding to the next phase.

---

## Phase 4: Frontend — Navigation & Polish

### Overview
Link grouped runs from the simulation list, handle edge cases, and add polish.

### Changes Required:

#### 1. Simulation List — Group Indicator
**File**: `frontend/src/components/arena/ArenaSimulationList.tsx`
**Changes**:

a) When a simulation has `group_id`, show a "Compare" badge/link next to the strategy badge:
```tsx
{sim.group_id && (
  <Badge
    variant="outline"
    className="text-[10px] px-1.5 py-0 cursor-pointer hover:bg-accent"
    onClick={(e) => {
      e.stopPropagation();
      navigate(`/arena/compare/${sim.group_id}`);
    }}
  >
    Compare
  </Badge>
)}
```

b) Group simulations with the same `group_id` visually using a shared left border color. Without this, a list with multiple comparisons (e.g., 3 comparisons × 4 strategies = 12 rows) becomes unreadable — users cannot tell which simulations belong together.

Implementation: compute a stable color per `group_id` (e.g., hash the UUID to one of 6 CSS border colors). Apply `border-l-2` with that color to all rows sharing the same `group_id`. This is ~10 lines of code and meaningfully improves list comprehension.

#### 2. Arena Page — Replay for Comparison
**File**: `frontend/src/pages/Arena.tsx`
**Changes**:

The existing replay mechanism passes a `Simulation` to pre-populate the form. For grouped simulations, add a "Replay Comparison" button that:
- Reads the `group_id` from any simulation in the group
- Fetches the comparison group
- Pre-populates the form with the shared config and all selected strategies

This can be deferred to a follow-up since basic replay (single strategy) already works.

#### 3. Comparison Page — Edge Cases
**File**: `frontend/src/pages/ArenaComparison.tsx`
**Changes**:

Handle these edge cases:
- **All simulations failed**: Show error message with link back to Arena
- **Some simulations cancelled**: Show partial results with warning
- **Mixed completion states**: Show progress for running, results for completed
- **Invalid group_id**: Show 404-style message

#### 4. Navigation Breadcrumb
**File**: `frontend/src/pages/ArenaComparison.tsx`
**Changes**: Add back navigation to the header:
```tsx
<Button variant="ghost" size="sm" onClick={() => navigate('/arena')}>
  ← Back to Arena
</Button>
```

### Success Criteria:

#### Automated Verification:
- [ ] All existing tests pass
- [ ] `ArenaSimulationList` test: grouped simulations show "Compare" badge
- [ ] Comparison page handles error/cancelled states gracefully

#### Manual Verification:
- [ ] Simulation list shows "Compare" badge for grouped simulations
- [ ] Clicking "Compare" badge navigates to comparison page
- [ ] Individual simulation rows still navigate to detail page on click
- [ ] Back button on comparison page works
- [ ] Edge cases (failed, cancelled) display appropriate messages

**Implementation Note**: After completing this phase and all automated verification passes, pause for final manual testing of the complete flow.

---

## Testing Strategy

### Unit Tests:

**Backend**:
- `POST /comparisons` creates N simulations with shared `group_id` and correct per-strategy config
- `POST /comparisons` validates: min 2 strategies, max 4, no duplicates, valid strategy names
- `POST /comparisons` with `portfolio_strategies` of length 1 returns 422
- `POST /comparisons` with valid `agent_config_id` → uses config's `scoring_algorithm`
- `POST /comparisons` with nonexistent `agent_config_id` → 404
- `GET /comparisons/{group_id}` returns all simulations in id order
- `GET /comparisons/{group_id}` returns 404 for nonexistent group
- `group_id` appears in `SimulationResponse` (detail endpoint)
- `group_id` appears in list endpoint response (confirms `_build_simulation_response` updated)
- Shared validator functions behave identically in both schemas (symbols, dates, agent_type)

**Frontend**:
- `ArenaSetupForm`: toggle behavior, button text at 0/1/2+ strategies, correct handler routing
- `ArenaSetupForm`: deselect-all → disabled; toggle selected → deselects
- `ArenaComparisonTable`: renders metrics, sorts correctly, highlights best/worst
- `ArenaComparisonTable`: no highlight when all column values equal
- `ArenaComparisonTable`: `—` for in-progress rows; `—` for win rate when zero trades
- `useComparisonPolling`: polls when only some terminal; stops when all terminal
- `useComparisonPolling`: clears interval on unmount (no stale updates)
- `useComparisonPolling`: surfaces error but keeps polling on network failure

### Integration Tests:

- Create comparison → all simulations picked up by worker → all complete → comparison endpoint returns full results
- Verify all simulations in a group have same symbols, dates, capital but different `portfolio_strategy`

### Manual Testing Steps:
1. Navigate to Arena → New Simulation
2. Select stock list, dates, capital settings
3. Select 4 portfolio strategies
4. Click "Start Comparison"
5. Verify redirect to comparison page with 4 progress cards
6. Wait for all to complete
7. Verify summary table is sortable and highlights best/worst
8. Verify equity chart shows 4 colored lines + benchmarks
9. Click a row → verify navigation to individual detail
10. Go back → verify simulation list shows "Compare" badges
11. Click "Compare" badge → verify return to comparison page

## References

- Original ticket: `thoughts/shared/tickets/007-arena-multi-algorithm-comparison.md`
- Portfolio analytics plan (reference for patterns): `thoughts/shared/plans/2026-02-19-arena-portfolio-analytics.md`
- Existing equity chart (multi-series pattern): `frontend/src/components/arena/ArenaEquityChart.tsx`
