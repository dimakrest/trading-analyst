# Live20 Support & Resistance Lines — Implementation Plan

## Overview

Add support and resistance level calculations to live20 run results. These are **not part of the agent** — they are supplementary information for the trader. S/R values will be displayed in the Live20Table and drawn as horizontal price lines on the expanded-row CandlestickChart.

## Current State Analysis

### Key Discoveries:
- `support_resistance_levels()` already exists at `backend/app/indicators/technical.py:726` — calculates S1/S2/S3 and R1/R2/R3 using Standard Pivot Points
- `CandlestickChart` already supports a `priceLines` prop (`ChartPriceLine[]`) — horizontal lines drawn on the main price pane
- `ExpandedRowContent` renders `CandlestickChart` but does NOT pass any `priceLines` currently
- `Live20Service._analyze_symbol()` at `live20_service.py:68` is where we add the calculation (same as ATR — computed alongside criteria, stored on Recommendation)
- The existing S/R function uses only the **most recent candle** to compute pivot, which gives a single day's pivot levels — appropriate for intraday/next-day levels

### Data Flow:
```
Live20Service._analyze_symbol()
  → support_resistance_levels(highs, lows, closes)
  → Store as live20_support_1, live20_resistance_1, live20_pivot on Recommendation
  → API returns via Live20ResultResponse
  → Frontend: Live20Table shows S1/R1 in a new column
  → Frontend: ExpandedRowContent passes priceLines to CandlestickChart
```

## Desired End State

- Live20Table has a new "S/R" column showing S1 and R1 values (compact display)
- Expanded row's CandlestickChart draws S1, R1, and Pivot as horizontal price lines (color-coded: green for support, red for resistance, gray/yellow for pivot)
- Values stored in DB for historical lookback
- No changes to the agent protocol or agent logic

## What We're NOT Doing

- Not adding S/R to arena agent decisions (separate feature if needed)
- Not computing multi-timeframe S/R (just daily pivot points)
- Not adding S2/S3 and R2/R3 to the UI (too cluttered — just S1/R1/Pivot)
- Not making S/R levels configurable (fixed to Standard Pivot Points)

---

## Phase 1: Backend — Add S/R Calculation and Storage

### Overview
Compute support/resistance levels in the live20 analysis pipeline and store them on the Recommendation model.

### Changes Required:

#### 1. Database Model — Add columns
**File**: `backend/app/models/recommendation.py`
**Changes**: Add 3 new nullable columns after the existing `live20_*` columns

```python
live20_pivot = Column(Numeric(12, 4), nullable=True)
live20_support_1 = Column(Numeric(12, 4), nullable=True)
live20_resistance_1 = Column(Numeric(12, 4), nullable=True)
```

#### 2. Alembic Migration
**File**: New migration file
**Changes**: `ALTER TABLE recommendations ADD COLUMN` for each of the 3 columns

#### 3. Live20Service — Calculate S/R alongside ATR
**File**: `backend/app/services/live20_service.py`
**Changes**: In `_analyze_symbol()`, after ATR calculation (line ~108), call `support_resistance_levels(highs, lows, closes, num_levels=1)` and store the results on the Recommendation object.

```python
from app.indicators.technical import support_resistance_levels

# After ATR calculation, compute S/R levels
support_levels, resistance_levels, pivot = support_resistance_levels(
    highs, lows, closes, num_levels=1
)
# Store on recommendation (they're Decimal-friendly floats from numpy)
recommendation.live20_pivot = pivot
recommendation.live20_support_1 = support_levels[0] if support_levels else None
recommendation.live20_resistance_1 = resistance_levels[0] if resistance_levels else None
```

#### 4. Pydantic Schema — Add fields to API response
**File**: `backend/app/schemas/live20.py`
**Changes**: Add to `Live20ResultResponse`:

```python
pivot: Decimal | None = None
support_1: Decimal | None = None
resistance_1: Decimal | None = None
```

Update `from_recommendation()` to map `rec.live20_pivot`, `rec.live20_support_1`, `rec.live20_resistance_1`.

Update `field_serializer` to include the new Decimal fields.

### Success Criteria:

#### Automated Verification:
- [x] Alembic migration runs cleanly (`alembic upgrade head`)
- [x] Existing tests pass
- [x] New unit test: `_analyze_symbol()` returns S/R values for a valid symbol

#### Manual Verification:
- [ ] Run a live20 analysis, check the API response includes `pivot`, `support_1`, `resistance_1` fields
- [ ] Values make sense relative to the stock's current price

**Implementation Note**: After completing this phase and all automated verification passes, pause for manual confirmation before proceeding to the next phase.

---

## Phase 2: Frontend — Table Column and Chart Price Lines

### Overview
Display S/R values in the Live20Table and draw them as horizontal lines on the candlestick chart.

### Changes Required:

#### 1. Frontend Types — Add S/R fields
**File**: `frontend/src/types/live20.ts`
**Changes**: Add to `Live20Result` interface:

```typescript
pivot: number | null;
support_1: number | null;
resistance_1: number | null;
```

#### 2. Live20Table — Add S/R column
**File**: `frontend/src/components/live20/Live20Table.tsx`
**Changes**: Add a new column after ATR (or before Trend) showing compact S/R info.

Column definition:
```typescript
{
  id: 'support_resistance',
  header: 'S/R',
  cell: ({ row }) => {
    const { support_1, resistance_1 } = row.original;
    if (support_1 === null && resistance_1 === null) {
      return <span className="text-muted-foreground">-</span>;
    }
    return (
      <div className="flex flex-col text-xs font-mono">
        {resistance_1 !== null && (
          <span className="text-accent-bearish">R {resistance_1.toFixed(2)}</span>
        )}
        {support_1 !== null && (
          <span className="text-accent-bullish">S {support_1.toFixed(2)}</span>
        )}
      </div>
    );
  },
}
```

#### 3. ExpandedRowContent — Pass priceLines to CandlestickChart
**File**: `frontend/src/components/live20/ExpandedRowContent.tsx`
**Changes**: Build `priceLines` array from the result's S/R values and pass to `CandlestickChart`.

```typescript
const priceLines: ChartPriceLine[] = [];
if (result.support_1 !== null) {
  priceLines.push({
    price: result.support_1,
    color: '#22c55e',  // green
    lineWidth: 1,
    lineStyle: 'dashed',
    label: 'S1',
    labelVisible: true,
  });
}
if (result.resistance_1 !== null) {
  priceLines.push({
    price: result.resistance_1,
    color: '#ef4444',  // red
    lineWidth: 1,
    lineStyle: 'dashed',
    label: 'R1',
    labelVisible: true,
  });
}
if (result.pivot !== null) {
  priceLines.push({
    price: result.pivot,
    color: '#eab308',  // yellow
    lineWidth: 1,
    lineStyle: 'dotted',
    label: 'PP',
    labelVisible: true,
  });
}

// Pass to CandlestickChart
<CandlestickChart
  data={stockData}
  symbol={result.stock}
  height={600}
  priceLines={priceLines}
/>
```

### Success Criteria:

#### Automated Verification:
- [x] TypeScript compiles without errors
- [x] Existing frontend tests pass

#### Manual Verification:
- [ ] Live20 table shows S/R column with values
- [ ] Expanding a row shows candlestick chart with S1 (green dashed), R1 (red dashed), and PP (yellow dotted) horizontal lines
- [ ] Lines are at sensible price levels relative to the stock's recent candles

---

## Testing Strategy

### Unit Tests:
- Backend: Test that `_analyze_symbol` populates S/R fields on the recommendation
- Backend: Test `Live20ResultResponse.from_recommendation()` maps S/R fields correctly
- Backend: Test edge case: symbol with insufficient data returns null S/R values

### Manual Testing Steps:
1. Run `alembic upgrade head` — migration applies cleanly
2. Start backend and frontend
3. Run a live20 analysis with a few symbols
4. Verify the API response at `/v1/live-20/runs/{id}` includes `pivot`, `support_1`, `resistance_1`
5. Check the Live20Table for the new S/R column
6. Expand a row and verify the chart shows horizontal price lines

## References

- Original ticket: GitHub issue #36
- Existing S/R function: `backend/app/indicators/technical.py:726-783`
- CandlestickChart priceLines prop: `frontend/src/components/organisms/CandlestickChart/CandlestickChart.tsx:28`
- ChartPriceLine type: `frontend/src/types/chart.ts`
