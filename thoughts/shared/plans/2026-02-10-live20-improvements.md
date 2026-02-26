# Live 20 Improvements: Sort by Volume, Filter by Volume, Add ATR

## Overview

Enhance the Live 20 view with three improvements per [GitHub Issue #13](https://github.com/dimakrest/trading-analyst/issues/13):
1. **Sort by Volume** - Make the Volume column sortable by rvol (today/yesterday ratio)
2. **Filter by Volume** - Add a minimum rvol threshold filter
3. **Add ATR** - Display ATR value for each stock, sortable

## Current State Analysis

### Volume
- `volume_trend` field stores the rvol ratio as a string like `"1.5x"` (from `live20_evaluator.py:148`)
- The numeric rvol is calculated in `volume.py:104-111` as `today_volume / yesterday_volume`
- The numeric value is available as `volume_signal.rvol` (float) in `live20_service.py:99`
- Displayed in the Volume column alongside alignment icon and approach badge
- The column is **not sortable** - only `confidence_score` supports sorting currently
- **No numeric rvol is stored** - only the formatted string `"1.5x"`

### ATR
- ATR is calculated in `PricingCalculator._get_latest_atr()` (`calculator.py:126-172`) using 14-period ATR
- Used to compute stop loss: `stop_loss = entry ± (ATR × multiplier)`
- The **raw ATR value is NOT persisted** to the database
- Only `entry_price` and `stop_loss` (derived from ATR) are stored

### Table Sorting
- `Live20Table.tsx:147` - Only `confidence_score` is sortable via TanStack Table
- Uses `SortingState`, `getSortedRowModel()`, clickable header with `ArrowUpDown` icon

### Key Discoveries
- `volume_trend` contains `"1.5x"` string, not `"increasing"/"decreasing"` as DB doc suggests (`live20_service.py:146`)
- The numeric rvol value is already computed and available as `volume_signal.rvol` (float) at `live20_service.py:99` — just not persisted
- ATR calculation already exists and is reliable (`technical_indicators.py:27-45`)
- Arena agent (`live20_agent.py`) doesn't create Recommendations - only `Live20Service` does
- Test mock at `Live20Table.test.tsx:24` already has `volume_trend: '1.5x'`
- Dashboard test mocks at `Live20Dashboard.test.tsx:46,74,102` use stale `volume_trend: 'increasing'` format — must be updated
- Model doc string at `recommendation.py:125` says `"'increasing', 'decreasing', 'stable'"` but actual values are `"1.5x"` format — must be fixed

## Desired End State

1. **Volume column is sortable** by numeric rvol value from API
2. **Min rvol filter** added to filter bar, similar to existing Min Score slider
3. **New ATR column** in table displaying the dollar value (e.g., `$2.35`), sortable
4. ATR and rvol values persisted in database for each Live 20 recommendation
5. Frontend uses numeric `rvol` field for sorting/filtering (no string parsing)

**Note on historical data**: Pre-migration recommendations will have `live20_atr = NULL` and `live20_rvol = NULL`. The History tab will show `-` for ATR and sort null rvol to bottom. This is expected and acceptable.

## What We're NOT Doing

- NOT adding actual daily volume (raw share count) - using rvol ratio only
- NOT adding server-side sorting/filtering for volume or ATR (client-side is sufficient for Live 20 result sets)
- NOT changing ATR calculation logic (14-period, already working)
- NOT modifying Arena agent (it doesn't create Recommendations)
- NOT adding ATR filtering (only display + sort per user decision)
- NOT removing the `volume_trend` string field — it's still used for display; `rvol` is the numeric companion

## Implementation Approach

- **Phase 1 (Backend)**: Add `live20_atr` and `live20_rvol` columns, persist both, expose in API, **with backend tests**
- **Phase 2 (Frontend)**: Add volume sorting + rvol filter using numeric `rvol`, **with frontend tests**
- **Phase 3 (Frontend)**: Add ATR column to table, **with frontend tests**

---

## Phase 1: Backend - Persist ATR and Rvol Values

### Overview
Add `live20_atr` and `live20_rvol` columns to the `recommendations` table, persist both values during analysis, expose them in the API response schema, and add backend tests.

### Changes Required:

#### 1. Database Migration
**File**: New file `backend/alembic/versions/YYYYMMDD_HHMM-{hash}_add_live20_atr_and_rvol.py`

Create migration to add both nullable columns:
```python
def upgrade() -> None:
    op.add_column(
        'recommendations',
        sa.Column('live20_atr', sa.Numeric(precision=12, scale=4), nullable=True,
                  comment='ATR (14-period) value at time of analysis')
    )
    op.add_column(
        'recommendations',
        sa.Column('live20_rvol', sa.Numeric(precision=8, scale=2), nullable=True,
                  comment='Relative volume ratio (today/yesterday) at time of analysis')
    )

def downgrade() -> None:
    op.drop_column('recommendations', 'live20_rvol')
    op.drop_column('recommendations', 'live20_atr')
```

Generate via: `cd backend && alembic revision --autogenerate -m "add_live20_atr_and_rvol"`

#### 2. Recommendation Model
**File**: `backend/app/models/recommendation.py`

Add both mapped columns after `live20_exit_strategy` (line ~158):

```python
live20_atr: Mapped[Decimal | None] = mapped_column(
    Numeric(precision=12, scale=4), nullable=True,
    doc="ATR (14-period) value at time of analysis"
)
live20_rvol: Mapped[Decimal | None] = mapped_column(
    Numeric(precision=8, scale=2), nullable=True,
    doc="Relative volume ratio (today/yesterday) at time of analysis"
)
```

Also fix the stale doc string on `live20_volume_trend` (line 125):
```python
# Change from:
doc="Volume trend: 'increasing', 'decreasing', 'stable'"
# Change to:
doc="Relative volume ratio as string, e.g. '1.5x'"
```

#### 3. Add ATR to PricingResult
**File**: `backend/app/services/pricing_strategies/types.py`

Add `atr` field to the `PricingResult` dataclass:
```python
@dataclass
class PricingResult:
    entry_price: Decimal
    stop_loss: Decimal | None
    entry_strategy: EntryStrategy
    exit_strategy: ExitStrategy
    atr: Decimal | None = None  # Raw ATR value used in calculation
```

**File**: `backend/app/services/pricing_strategies/calculator.py`

In `calculate()` method, include ATR in the result (the ATR is already computed at `calculator.py:60`):
```python
# Normal return path — include ATR value:
return PricingResult(
    entry_price=Decimal(str(round(entry_price, 4))),
    stop_loss=Decimal(str(round(stop_loss, 4))),
    entry_strategy=self.config.entry_strategy,
    exit_strategy=self.config.exit_strategy,
    atr=Decimal(str(round(atr, 4))),
)
```
The early-return case (ATR unavailable, `calculator.py:64-69`) already gets `atr=None` from the dataclass default.

#### 4. Live20 Service - Persist ATR and Rvol
**File**: `backend/app/services/live20_service.py`

In `_analyze_symbol()`, add both values when constructing the Recommendation.

ATR — use `pricing_result.atr` (line ~118):
```python
live20_atr=pricing_result.atr if pricing_result else None,
```

Rvol — use `volume_signal.rvol` which is already available (returned from `evaluate_criteria()` at line 99):
```python
live20_rvol=Decimal(str(volume_signal.rvol)),
```

Note: `volume_signal.rvol` is always populated (defaults to 1.0 when yesterday's volume is 0, see `volume.py:107`), so no None check needed.

#### 5. API Response Schema
**File**: `backend/app/schemas/live20.py`

Add both fields to `Live20ResultResponse` using `Field(description=...)` per engineering standards:

```python
from pydantic import Field

# In Live20ResultResponse class, after exit_strategy field:
atr: Decimal | None = Field(None, description="ATR (14-period) value at time of analysis")
rvol: float | None = Field(None, description="Relative volume ratio (today/yesterday)")
```

In `from_recommendation()`:
```python
atr=rec.live20_atr,
rvol=float(rec.live20_rvol) if rec.live20_rvol is not None else None,
```

In `serialize_decimal_as_float`, add `"atr"` to the field list:
```python
@field_serializer(
    "entry_price", "stop_loss", "ma20_distance_pct", "cci_value", "atr", when_used="json"
)
```

Note: `rvol` is exposed as `float` (not `Decimal`) since it's a simple ratio with 2 decimal places — no precision concerns. It does NOT need to be in the `serialize_decimal_as_float` list since it's already `float`.

Update `json_schema_extra` example to include the new fields:
```python
# Add to the example dict (after "exit_strategy"):
"atr": 4.25,
"rvol": 1.5
```

Also update `volume_trend` in the example from `"increasing"` to `"1.5x"` to match actual values.

#### 6. Backend Tests

**New file**: `backend/tests/unit/services/test_pricing_calculator.py`

Test that `PricingResult` includes ATR:
- Create calculator with known test data (use `sample_price_data` fixture pattern)
- Call `calculate()` with known highs/lows/closes
- Assert `result.atr` is a specific expected `Decimal` value computed from the test data (not just "is not None")

**File**: `backend/tests/unit/services/test_live20_service.py`

Test ATR and rvol persistence:
- Mock price data with known OHLCV values
- Run `_analyze_symbol()`
- Assert `recommendation.live20_atr` is the specific expected `Decimal` value based on the test data
- Assert `recommendation.live20_rvol` is the specific expected `Decimal` value based on the test data

**File**: `backend/tests/integration/test_live20_api.py`

- Add `live20_atr=Decimal("2.35")` and `live20_rvol=Decimal("1.50")` to at least one entry in `sample_live20_results` fixture
- In `test_results_decimal_serialization`, add assertion for `atr` field serialization (Decimal -> float)
- Add assertions in `test_get_results_all` that `atr` and `rvol` fields are present in response
- Verify run detail endpoint (`GET /runs/{run_id}`) also returns `atr` and `rvol` fields

### Success Criteria:

#### Automated Verification:
- [x] `alembic upgrade head` runs without errors
- [x] Migration rollback works: `alembic downgrade -1` then `alembic upgrade head`
- [x] All existing backend tests pass
- [x] New PricingCalculator test passes with specific ATR assertion
- [x] New Live20Service test passes with specific ATR and rvol assertions
- [x] Integration test verifies ATR and rvol in API response (both `/results` and `/runs/{id}`)

#### Manual Verification:
- [ ] Run a Live 20 analysis and verify ATR and rvol values appear in API response (via browser dev tools or curl)
- [ ] Verify ATR is `null` for NO_SETUP results (since PricingCalculator returns None)
- [ ] Verify rvol is populated even for NO_SETUP results (volume is always calculated)

**Implementation Note**: After completing this phase and all automated verification passes, pause for manual confirmation before proceeding to the next phase.

---

## Phase 2: Frontend - Volume Sort & Filter (with tests)

### Overview
Make the Volume column sortable using the numeric `rvol` field from the API, and add a minimum rvol filter to the filter bar. All client-side, no backend changes. Includes frontend tests.

### Changes Required:

#### 1. Update TypeScript Type
**File**: `frontend/src/types/live20.ts`
**Changes**: Add `rvol` field to `Live20Result` interface

```typescript
// After volume_approach field:
rvol: number | null;
```

#### 2. Make Volume Column Sortable
**File**: `frontend/src/components/live20/Live20Table.tsx`
**Changes**: Add sorting capability to the volume column definition (around line 271)

```typescript
{
  accessorKey: 'volume_aligned',
  header: ({ column }) => (
    <button
      className="flex items-center gap-1 hover:text-foreground"
      onClick={() => column.toggleSorting(column.getIsSorted() === 'asc')}
    >
      Volume
      <ArrowUpDown className="h-4 w-4" />
    </button>
  ),
  // Sort by numeric rvol field, not by volume_aligned boolean.
  // The accessorKey is volume_aligned for cell rendering, but sorting uses
  // the numeric rvol from the API via row.original access.
  sortingFn: (rowA, rowB) => {
    return (rowA.original.rvol ?? 0) - (rowB.original.rvol ?? 0);
  },
  cell: ({ row }) => {
    // ... existing cell render (unchanged)
  },
},
```

No `parseRvol` utility needed — the API now provides the numeric value directly.

#### 3. Add Min Rvol Filter State
**File**: `frontend/src/components/live20/Live20Dashboard.tsx`
**Changes**: Add `minRvol` state and wire into filtering

```typescript
const [minRvol, setMinRvol] = useState(0);

// In filteredResults useMemo, add after minScore filter:
if (minRvol > 0) {
  filtered = filtered.filter((r) => (r.rvol ?? 0) >= minRvol);
}
```

Pass to Live20Filters:
```tsx
<Live20Filters
  // ... existing props
  minRvol={minRvol}
  onMinRvolChange={setMinRvol}
/>
```

#### 4. Add Rvol Filter UI
**File**: `frontend/src/components/live20/Live20Filters.tsx`
**Changes**: Add `minRvol` and `onMinRvolChange` to props and render a slider

Add to interface:
```typescript
/** Current minimum rvol filter */
minRvol: number;
/** Callback when minimum rvol changes */
onMinRvolChange: (rvol: number) => void;
```

Add UI after the Min Score slider (similar pattern):
```tsx
{/* Min Rvol Slider */}
<div className="flex items-center gap-3">
  <span className="text-xs text-text-muted whitespace-nowrap">Min Vol:</span>
  <Slider
    value={[minRvol]}
    onValueChange={([value]) => onMinRvolChange(value)}
    min={0}
    max={5}
    step={0.25}
    className="w-[120px]"
  />
  <span className="font-mono text-xs font-semibold text-text-primary min-w-[36px]">
    {minRvol > 0 ? `${minRvol}x` : 'Off'}
  </span>
</div>
```

**Design notes**:
- `max={5}` — rvol can exceed 3x for momentum/small-cap stocks
- `step={0.25}` — traders think in quarter-units (1x, 1.25x, 1.5x), less fiddly
- `min-w-[36px]` — aligned with Min Score slider (both need room for "Off" and values like "2.5x" / "80")

#### 5. Frontend Tests for Volume Sort & Filter

**File**: `frontend/src/components/live20/Live20Table.test.tsx`

Update `createMockResult` to include `rvol: 1.5` in defaults.

```typescript
describe('Volume sorting', () => {
  it('sorts ascending by rvol when Volume header clicked', () => {
    const results = [
      createMockResult({ stock: 'HIGH', rvol: 2.0 }),
      createMockResult({ id: 2, stock: 'LOW', rvol: 0.5 }),
    ];
    render(<Live20Table results={results} />);

    const volumeHeader = screen.getByRole('button', { name: /volume/i });
    fireEvent.click(volumeHeader);

    const rows = screen.getAllByRole('row');
    // Ascending: LOW (0.5) first, HIGH (2.0) second
    expect(rows[1]).toHaveTextContent('LOW');
    expect(rows[2]).toHaveTextContent('HIGH');
  });

  it('sorts descending on second click', () => {
    const results = [
      createMockResult({ stock: 'LOW', rvol: 0.5 }),
      createMockResult({ id: 2, stock: 'HIGH', rvol: 2.0 }),
    ];
    render(<Live20Table results={results} />);

    const volumeHeader = screen.getByRole('button', { name: /volume/i });
    fireEvent.click(volumeHeader); // ascending
    fireEvent.click(volumeHeader); // descending

    const rows = screen.getAllByRole('row');
    expect(rows[1]).toHaveTextContent('HIGH');
  });

  it('handles null rvol gracefully (sorts to bottom as 0)', () => {
    const results = [
      createMockResult({ stock: 'NULL', rvol: null }),
      createMockResult({ id: 2, stock: 'HAS_VOL', rvol: 1.5 }),
    ];
    render(<Live20Table results={results} />);

    const volumeHeader = screen.getByRole('button', { name: /volume/i });
    fireEvent.click(volumeHeader); // ascending

    const rows = screen.getAllByRole('row');
    // null (treated as 0) sorts first in ascending
    expect(rows[1]).toHaveTextContent('NULL');
    expect(rows[2]).toHaveTextContent('HAS_VOL');
  });
});
```

**File**: `frontend/src/components/live20/Live20Dashboard.test.tsx`

Fix stale mock data — change `volume_trend: 'increasing'` to `volume_trend: '1.5x'` at lines 46, 74, 102 to match actual backend format. Add `rvol: 1.5` to mock data.

```typescript
describe('Min Rvol filter', () => {
  it('filters out results below the rvol threshold', () => {
    // Setup: render dashboard with results having different rvol values
    // Mock results with rvol: 0.5, 1.5, 2.5
    // Set minRvol slider to 1.0
    // Assert: only rvol 1.5 and 2.5 results are visible
  });

  it('shows all results when minRvol is 0 (Off)', () => {
    // Default state — all results visible regardless of rvol
  });

  it('excludes results with null rvol when filter is active', () => {
    // Result with rvol: null should be hidden when minRvol > 0
  });
});
```

**Note**: Exact test implementation depends on how the Dashboard renders results and how Slider interactions can be triggered in tests. Follow existing `Live20Dashboard.test.tsx` patterns.

### Success Criteria:

#### Automated Verification:
- [x] TypeScript compiles without errors
- [x] All existing frontend tests pass
- [x] New volume sorting tests pass (ascending, descending, null handling)
- [x] New rvol filter tests pass (threshold, off state, null exclusion)

#### Manual Verification:
- [ ] Click Volume column header to sort ascending/descending
- [ ] Adjust Min Vol slider to filter out low-rvol results
- [ ] Verify sorting handles null rvol gracefully (sorts to bottom)

**Implementation Note**: After completing this phase and all automated verification passes, pause for manual confirmation before proceeding to the next phase.

---

## Phase 3: Frontend - ATR Column (with tests)

### Overview
Add a new ATR column to the table displaying the dollar-formatted ATR value, with sorting support. Includes frontend tests.

### Changes Required:

#### 1. Update TypeScript Type
**File**: `frontend/src/types/live20.ts`
**Changes**: Add `atr` field to `Live20Result` interface

```typescript
// After exit_strategy field:
atr: number | null;
```

This type is used by both `Live20ResultResponse` results and `Live20RunDetail.results`, so the new field flows through all views including the History tab. Historical records will show `atr: null` (displayed as `-`).

#### 2. Add ATR Column to Table
**File**: `frontend/src/components/live20/Live20Table.tsx`
**Changes**: Add new column definition **after the Stop Loss column and before Trend** (between current Risk and Trend columns, around line 219). This groups ATR with the pricing/risk columns since ATR is the basis for stop distance.

Full column order after change: Symbol, Direction, Score, Price, Stop, Risk, **ATR**, Trend, MA20, Candle, Volume, CCI

```typescript
{
  accessorKey: 'atr',
  header: ({ column }) => (
    <button
      className="flex items-center gap-1 hover:text-foreground"
      onClick={() => column.toggleSorting(column.getIsSorted() === 'asc')}
    >
      ATR
      <ArrowUpDown className="h-4 w-4" />
    </button>
  ),
  cell: ({ row }) => (
    <span className="font-mono">
      {row.original.atr != null
        ? `$${row.original.atr.toFixed(2)}`
        : '-'}
    </span>
  ),
},
```

**Notes**:
- No custom `sortingFn` needed — TanStack Table's default numeric sorting handles `number | null` correctly
- `font-mono` class is consistent with how `entry_price` and `stop_loss` are rendered
- Table wrapper already has `overflow-x-auto` (line 361) so 12 columns will scroll on smaller screens

#### 3. Frontend Tests for ATR Column

**File**: `frontend/src/components/live20/Live20Table.test.tsx`

Update `createMockResult` to include `atr: 2.35` in defaults.

```typescript
describe('ATR column', () => {
  it('displays ATR value formatted as dollar amount', () => {
    const result = createMockResult({ atr: 2.35 });
    render(<Live20Table results={[result]} />);
    expect(screen.getByText('$2.35')).toBeInTheDocument();
  });

  it('displays dash when ATR is null', () => {
    const result = createMockResult({ atr: null });
    render(<Live20Table results={[result]} />);
    // Find the ATR cell that shows '-'
    const atrCells = screen.getAllByText('-');
    expect(atrCells.length).toBeGreaterThan(0);
  });
});
```

### Success Criteria:

#### Automated Verification:
- [x] TypeScript compiles without errors
- [x] All existing frontend tests pass
- [x] New ATR column tests pass (display, null handling)
- [x] Linting passes

#### Manual Verification:
- [ ] ATR column shows dollar values for LONG/SHORT results
- [ ] ATR column shows `-` for NO_SETUP results and historical pre-migration records
- [ ] ATR column is sortable (click header)

**Implementation Note**: After completing this phase and all automated verification passes, pause for manual confirmation before proceeding.

---

## Testing Strategy

### Unit Tests:
- PricingCalculator returns ATR in PricingResult (specific value assertion)
- Live20Service persists ATR and rvol to Recommendation (specific value assertions)

### Integration Tests:
- API response includes ATR and rvol fields (both `/results` and `/runs/{id}` endpoints)
- ATR serialized correctly (Decimal -> float)
- Rvol serialized correctly (Decimal -> float)
- Records without ATR/rvol return `null`

### Frontend Tests:
- Volume column sorting using numeric rvol (ascending, descending, null handling)
- ATR column display (dollar format, null as dash)
- Rvol filter (threshold filtering, off state, null exclusion)

### Manual Testing Steps:
1. Run `./scripts/dc.sh exec backend-dev alembic upgrade head` to apply migration
2. Verify rollback: `alembic downgrade -1` then `alembic upgrade head`
3. Analyze a few symbols (e.g., AAPL, MSFT, NVDA)
4. Verify ATR and rvol values appear in API response via browser dev tools
5. In the UI: verify ATR column shows dollar values
6. Click Volume column header - verify sort works (ascending/descending)
7. Click ATR column header - verify sort works
8. Adjust Min Vol slider - verify results filter by rvol threshold
9. Verify NO_SETUP results show `-` for ATR but have rvol value
10. Check History tab — pre-migration results should show `-` for ATR and handle null rvol

## References

- Original ticket: [GitHub Issue #13](https://github.com/dimakrest/trading-analyst/issues/13)
- ATR calculation: `backend/app/utils/technical_indicators.py:27-45`
- Volume analysis: `backend/app/indicators/volume.py:67-149`
- Rvol calculation: `backend/app/indicators/volume.py:104-111` (numeric ratio)
- Rvol string formatting: `backend/app/services/live20_evaluator.py:148` (`f"{volume_signal.rvol}x"`)
- Rvol availability in service: `backend/app/services/live20_service.py:99` (`volume_signal.rvol`)
- Live20 service: `backend/app/services/live20_service.py:57-186`
- PricingCalculator: `backend/app/services/pricing_strategies/calculator.py:32-79`
- Live20Table: `frontend/src/components/live20/Live20Table.tsx:146-406`
- Live20Filters: `frontend/src/components/live20/Live20Filters.tsx:1-148`
- Live20Dashboard: `frontend/src/components/live20/Live20Dashboard.tsx:30-237`
