# Historical Bounce Rate Filter — Implementation Plan

## Overview

Add a per-symbol "bounce rate" metric that measures how reliably each stock mean-reverts after pulling back to MA20. Display it as an informational column in the Live20 dashboard. No portfolio selection changes — purely observational for now.

## Current State Analysis

### Data Flow (Live20 Dashboard):
1. **Compute**: `live20_service.py:68` — `_analyze_symbol()` fetches 60 days of price data, evaluates criteria, creates `Recommendation`
2. **Store**: `recommendation.py:90-161` — `Recommendation` model has `live20_*` columns (trend, MA20, candle, volume, CCI, ATR, etc.)
3. **Serialize**: `schemas/live20.py:19-125` — `Live20ResultResponse` maps model to API response via `from_recommendation()`
4. **Frontend type**: `types/live20.ts:7-39` — `Live20Result` TypeScript interface
5. **Display**: `Live20Table.tsx:166-396` — Table columns (Symbol, Sector, Direction, Score, ATR, Trend, MA20, Candle, Volume, Momentum)

### Key Discoveries:
- Live20 service only fetches 60 days of data (`live20_service.py:84`). Bounce rate needs ~1 year of history for meaningful sample size. We extend the existing fetch to 1 year and slice the last ~60 days for core analysis — no redundant API calls.
- Bounce rate aligns with existing criteria: the system already detects pullback to MA20 (≥5% below) in bearish trend — this is exactly what defines a "bounce event".
- The `_get_cached_price_history()` pattern in `simulation_engine.py:790-795` shows how to window data without look-ahead bias.
- All indicator functions follow a consistent pattern: pure function, accepts price lists (oldest→newest), returns `float | None` or dataclass, minimum-data guard with safe default.

### Bounce Rate Definition (Decided):
- **Pullback event**: Price is within 5% below MA20 AND 10-day trend is bearish (matches Live20 BUY signal criteria exactly)
- **Successful bounce**: Price recovers ≥2.5% from the pullback-day low within 15 trading days (matches trailing stop and max hold period)
- **Bounce rate**: `successful_bounces / total_pullback_events` over trailing 1-year window
- **Minimum sample**: ≥3 pullback events required for the metric to be considered valid

## Desired End State

The Live20 dashboard table shows a "Bounce" column next to ATR displaying the historical bounce rate as a percentage (e.g., "45%") with color coding. Users can see at a glance which stocks have a track record of bouncing from MA20 pullbacks. Null/insufficient data shown as "-".

### How to Verify:
- Run a Live20 analysis on any stock list
- The Bounce column appears in the results table
- Stocks with sufficient history show a percentage
- Stocks with insufficient data show "-"
- Sorting by bounce rate works

## What We're NOT Doing

- No changes to portfolio selection / ranking logic
- No changes to arena simulation engine
- No changes to signal scoring
- No new database caching layer for bounce rates
- Not adding bounce rate to the arena agent config or comparison charts

## Implementation Approach

The bounce rate is computed fresh on each Live20 analysis run, like ATR. The service fetches 1 year of data (instead of the current 60 days) and reuses it for both the core analysis (sliced to ~60 days) and bounce rate computation — no redundant API calls. The computation is a pure function in `app/indicators/` following existing patterns. The result is stored on the `Recommendation` model, serialized through the schema, and displayed in the frontend table. Bounce rate computation is wrapped in its own error handler so a failure never suppresses core analysis results.

---

## Phase 1: Bounce Rate Indicator

### Overview
Create the pure-function bounce rate indicator.

### Changes Required:

#### 1. New indicator: `backend/app/indicators/bounce_rate.py`

**File**: `backend/app/indicators/bounce_rate.py` (new file)

```python
"""Historical bounce rate indicator for mean-reversion analysis.

Measures how reliably a stock mean-reverts after pulling back to MA20
in a bearish trend. A "bounce" is defined as recovering ≥2.5% from
the pullback-day low within 15 trading days.
"""

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from app.indicators.technical import simple_moving_average
from app.indicators.trend import detect_trend, TrendDirection


@dataclass
class BounceRateAnalysis:
    """Result of bounce rate analysis."""
    bounce_rate: float | None  # 0.0-1.0, or None if insufficient data
    total_events: int          # Number of pullback events found
    successful_bounces: int    # Number that recovered ≥2.5% within 15 days


# Minimum pullback events required for a valid bounce rate
MIN_BOUNCE_EVENTS = 3

# Recovery threshold (matches trailing stop %)
RECOVERY_PCT = 2.5

# Max days to recover (matches max hold period)
RECOVERY_WINDOW_DAYS = 15

# MA20 distance threshold (matches Live20 alignment criterion)
MA20_DISTANCE_THRESHOLD = -5.0

# Trend detection period (matches Live20 trend criterion)
TREND_PERIOD = 10

# MA period — hardcoded to 20 (all other constants are MA20-specific)
MA_PERIOD = 20


def calculate_bounce_rate(
    closes: list[float] | NDArray[np.float64],
    lows: list[float] | NDArray[np.float64],
) -> BounceRateAnalysis:
    """Calculate historical bounce rate from pullbacks to MA20.

    Scans the price history for pullback events (price ≥5% below MA20
    in a bearish 10-day trend) and checks whether each recovered ≥2.5%
    from the pullback-day low within 15 trading days.

    Args:
        closes: Closing prices, oldest to newest.
        lows: Low prices, oldest to newest.

    Returns:
        BounceRateAnalysis with bounce_rate (0.0-1.0 or None),
        total_events, and successful_bounces.
    """
    closes_arr = np.array(closes, dtype=float)
    lows_arr = np.array(lows, dtype=float)
    n = len(closes_arr)

    # Need enough data for MA20 + trend detection + at least some recovery window
    min_required = MA_PERIOD + TREND_PERIOD + RECOVERY_WINDOW_DAYS
    if n < min_required:
        return BounceRateAnalysis(bounce_rate=None, total_events=0, successful_bounces=0)

    # Precompute MA20 for all bars
    ma = simple_moving_average(closes_arr, MA_PERIOD)

    total_events = 0
    successful_bounces = 0

    # Start scanning from the first bar where MA20 and trend are both computable.
    # After a pullback event, skip forward RECOVERY_WINDOW_DAYS to avoid
    # overlapping events from the same pullback.
    start_idx = max(MA_PERIOD, TREND_PERIOD)
    # Stop early enough to allow recovery window to be evaluated
    # (last event must have room for 15-day forward check)
    end_idx = n - RECOVERY_WINDOW_DAYS

    i = start_idx
    while i < end_idx:
        # Check MA20 distance at this bar
        current_ma = ma[i]
        if np.isnan(current_ma) or current_ma <= 0:
            i += 1
            continue

        distance_pct = ((closes_arr[i] - current_ma) / current_ma) * 100

        if distance_pct > MA20_DISTANCE_THRESHOLD:
            # Not far enough below MA20
            i += 1
            continue

        # Check 10-day trend ending at this bar
        trend_slice = closes_arr[max(0, i - TREND_PERIOD + 1):i + 1]
        if len(trend_slice) < TREND_PERIOD:
            i += 1
            continue

        trend = detect_trend(trend_slice, period=TREND_PERIOD)
        if trend != TrendDirection.BEARISH:
            i += 1
            continue

        # This is a pullback event.
        total_events += 1
        pullback_low = lows_arr[i]

        # Check if price recovers ≥2.5% from pullback-day low within 15 days
        recovery_target = pullback_low * (1 + RECOVERY_PCT / 100)
        recovery_end = min(i + RECOVERY_WINDOW_DAYS + 1, n)

        recovered = False
        for j in range(i + 1, recovery_end):
            if closes_arr[j] >= recovery_target:
                recovered = True
                break

        if recovered:
            successful_bounces += 1

        # Skip forward to avoid overlapping events from the same pullback
        i += RECOVERY_WINDOW_DAYS
        continue

    if total_events < MIN_BOUNCE_EVENTS:
        return BounceRateAnalysis(
            bounce_rate=None,
            total_events=total_events,
            successful_bounces=successful_bounces,
        )

    return BounceRateAnalysis(
        bounce_rate=successful_bounces / total_events,
        total_events=total_events,
        successful_bounces=successful_bounces,
    )
```

#### 2. Update indicator exports: `backend/app/indicators/__init__.py`

Add `BounceRateAnalysis` and `calculate_bounce_rate` to the module-level imports and `__all__` list, following the existing pattern for other indicator modules.

### Success Criteria:

#### Automated Verification:
- [ ] Unit tests pass for `calculate_bounce_rate()`
- [ ] `from app.indicators import calculate_bounce_rate, BounceRateAnalysis` works
- [ ] Edge cases: insufficient data, no pullback events, all bounces, no bounces
- [ ] No look-ahead bias: recovery check uses only bars after the event

**Implementation Note**: After completing this phase and all automated verification passes, pause for manual confirmation before proceeding to the next phase.

---

## Phase 2: Backend Integration (Model + Service + Schema)

### Overview
Store bounce rate on the Recommendation model, compute it in the Live20 service, and expose it in the API schema.

### Changes Required:

#### 1. Database Model — Add column
**File**: `backend/app/models/recommendation.py`

Add after `live20_sector_etf` (line 161):
```python
    live20_bounce_rate: Mapped[Decimal | None] = mapped_column(
        Numeric(3, 2), nullable=True,
        doc="Historical bounce rate (0.00-1.00): fraction of MA20 pullback events that recovered ≥2.5% within 15 days"
    )
    live20_bounce_events: Mapped[int | None] = mapped_column(
        Integer, nullable=True,
        doc="Number of MA20 pullback events used to compute bounce rate"
    )
```

Add a `CheckConstraint` in the table args (following existing `confidence_score` pattern):
```python
    CheckConstraint("live20_bounce_rate >= 0 AND live20_bounce_rate <= 1", name="ck_bounce_rate_range"),
```

#### 2. Alembic Migration
**File**: `backend/alembic/versions/20260225_0000-d4e5f6a7b8c9_add_bounce_rate_column.py` (new file)

```python
"""add_bounce_rate_column

Adds live20_bounce_rate and live20_bounce_events to recommendations table.
"""

def upgrade() -> None:
    op.add_column(
        "recommendations",
        sa.Column("live20_bounce_rate", sa.Numeric(3, 2), nullable=True),
    )
    op.add_column(
        "recommendations",
        sa.Column("live20_bounce_events", sa.Integer(), nullable=True),
    )
    op.create_check_constraint(
        "ck_bounce_rate_range",
        "recommendations",
        "live20_bounce_rate >= 0 AND live20_bounce_rate <= 1",
    )

def downgrade() -> None:
    op.drop_constraint("ck_bounce_rate_range", "recommendations", type_="check")
    op.drop_column("recommendations", "live20_bounce_events")
    op.drop_column("recommendations", "live20_bounce_rate")
```

#### 3. Service — Compute bounce rate
**File**: `backend/app/services/live20_service.py`

Changes:
- Add import for `calculate_bounce_rate`
- **Extend the existing data fetch to 1 year** (from 60 days). The current 60-day window becomes a slice of the larger dataset — no redundant API calls. Use the full 1-year data for bounce rate and slice the last ~60 days for existing core analysis.
- Compute bounce rate in an **isolated try/except** so failures never suppress core analysis
- Attach results to `Recommendation`

Change the existing data fetch window from 60 days to 365 days:
```python
            # Fetch 1 year of data — used for both core analysis (last ~60 days)
            # and bounce rate computation (full window)
            start_date = end_date - timedelta(days=365)
```

Slice for existing core analysis (after fetch, before existing indicator logic):
```python
            # Core analysis uses the most recent ~60 days
            core_records = price_records[-60:] if len(price_records) > 60 else price_records
```

After the existing ATR computation (line ~108), add bounce rate in isolated error handler:
```python
            # Calculate bounce rate from full 1-year history (non-critical)
            bounce_analysis = None
            try:
                if price_records and len(price_records) >= 60:
                    bounce_closes = [float(r.close_price) for r in price_records]
                    bounce_lows = [float(r.low_price) for r in price_records]
                    bounce_analysis = calculate_bounce_rate(
                        closes=bounce_closes,
                        lows=bounce_lows,
                    )
            except Exception as e:
                logger.warning(f"Failed to compute bounce rate for {symbol}: {e}")
```

Then in the `Recommendation()` constructor, add:
```python
                # Decimal(str(round(...))) avoids float→Decimal imprecision
                live20_bounce_rate=Decimal(str(round(bounce_analysis.bounce_rate, 2)))
                    if bounce_analysis and bounce_analysis.bounce_rate is not None else None,
                live20_bounce_events=bounce_analysis.total_events
                    if bounce_analysis else None,
```

#### 4. API Schema — Add fields
**File**: `backend/app/schemas/live20.py`

Add to `Live20ResultResponse` (after `sector_etf` line 59):
```python
    bounce_rate: Decimal | None = Field(
        None,
        description="Historical bounce rate (0.00-1.00): fraction of MA20 pullbacks that recovered ≥2.5%",
        ge=0,
        le=1,
    )
    bounce_events: int | None = Field(
        None,
        description="Number of MA20 pullback events used to compute bounce rate",
    )
```

Add to `from_recommendation()` method (after `sector_etf` mapping line 124):
```python
            bounce_rate=rec.live20_bounce_rate,
            bounce_events=rec.live20_bounce_events,
```

Add `"bounce_rate"` to the `@field_serializer` decorator (line 128):
```python
    @field_serializer(
        "ma20_distance_pct", "atr", "rvol", "cci_value", "rsi2_value", "bounce_rate",
        when_used="json"
    )
```

### Success Criteria:

#### Automated Verification:
- [ ] Migration applies cleanly (`alembic upgrade head`)
- [ ] Existing tests still pass
- [ ] New API returns `bounce_rate` and `bounce_events` fields (can be null)

#### Manual Verification:
- [ ] Run a Live20 analysis and check the API response includes bounce_rate values
- [ ] Stocks with sufficient history have non-null bounce_rate
- [ ] Values are reasonable (between 0 and 1)

**Implementation Note**: After completing this phase and all automated verification passes, pause for manual confirmation before proceeding to the next phase.

---

## Phase 3: Frontend Display

### Overview
Add a "Bounce" column to the Live20 results table.

### Changes Required:

#### 1. TypeScript type
**File**: `frontend/src/types/live20.ts`

Add to `Live20Result` interface (after `sector_etf` line 33):
```typescript
  bounce_rate: number | null;
  bounce_events: number | null;
```

#### 2. Table column
**File**: `frontend/src/components/live20/Live20Table.tsx`

Add a new column after the ATR column (after line ~237). The column should:
- Header: "Bounce" with sort toggle (like ATR)
- Custom `sortingFn` with null handling (nulls sort to bottom)
- Cell: Display as percentage with color coding using **design tokens** (matching ATR/Score pattern)
  - `≥50%`: `text-accent-bullish` (strong bouncer)
  - `30-49%`: `text-score-medium` (moderate — caution)
  - `<30%`: `text-accent-bearish` (weak bouncer)
  - `null`: "-" (insufficient data)
- Tooltip showing `N events` count for context

```typescript
      {
        accessorKey: 'bounce_rate',
        header: ({ column }) => (
          <button
            className="flex items-center gap-1 hover:text-foreground"
            onClick={() => column.toggleSorting(column.getIsSorted() === 'asc')}
          >
            Bounce
            <ArrowUpDown className="h-4 w-4" />
          </button>
        ),
        sortingFn: (rowA, rowB) =>
          (rowA.original.bounce_rate ?? -1) - (rowB.original.bounce_rate ?? -1),
        cell: ({ row }) => {
          const rate = row.original.bounce_rate;
          const events = row.original.bounce_events;

          if (rate == null) {
            return <span className="text-muted-foreground">-</span>;
          }

          const pct = Math.round(rate * 100);
          const colorClass =
            rate >= 0.5 ? 'text-accent-bullish' :
            rate >= 0.3 ? 'text-score-medium' :
            'text-accent-bearish';

          return (
            <Tooltip>
              <TooltipTrigger asChild>
                <span className={cn('font-mono font-semibold cursor-help', colorClass)}>
                  {pct}%
                </span>
              </TooltipTrigger>
              <TooltipContent>
                {events} pullback events observed
              </TooltipContent>
            </Tooltip>
          );
        },
      },
```

#### 3. Frontend tests: `frontend/src/components/live20/Live20Table.test.tsx`

Update `createMockResult` factory to include `bounce_rate: null, bounce_events: null` defaults.

**Test cases to add:**
- Renders bounce rate as percentage (e.g., `0.65` → displays `65%`)
- Displays dash for null `bounce_rate`
- Color coding: `>= 0.5` gets `text-accent-bullish`, `0.3-0.49` gets `text-score-medium`, `< 0.3` gets `text-accent-bearish`
- Tooltip shows event count text (e.g., "7 pullback events observed")
- Sorting ascending/descending works correctly
- Null values sort to bottom (via `?? -1` in sortingFn)
- Edge cases: `bounce_rate = 0`, `bounce_rate = 1.0`, `bounce_events = 0`

### Success Criteria:

#### Automated Verification:
- [ ] TypeScript compiles without errors
- [ ] No lint errors
- [ ] All new frontend tests pass

#### Manual Verification:
- [ ] Bounce column visible in the Live20 table
- [ ] Sorting by bounce rate works
- [ ] Hover tooltip shows event count
- [ ] Color coding applies correctly
- [ ] Null values display as "-"

**Implementation Note**: After completing this phase, the feature is complete.

---

## Phase 4: Unit Tests

### Overview
Tests for the bounce rate indicator function.

### Changes Required:

#### 1. Test file: `backend/tests/unit/indicators/test_bounce_rate.py`

**Test cases:**
- `test_insufficient_data_returns_none` — < 50 bars → `bounce_rate=None, total_events=0`
- `test_no_pullback_events_returns_none` — price always above MA20 → `bounce_rate=None, total_events=0`
- `test_all_bounces_returns_1` — every pullback recovers → `bounce_rate=1.0`
- `test_no_bounces_returns_0` — every pullback keeps falling → `bounce_rate=0.0`
- `test_mixed_bounces` — some bounce, some don't → correct ratio
- `test_below_min_events_returns_none` — only 1-2 events → `bounce_rate=None` (below MIN_BOUNCE_EVENTS=3)
- `test_events_do_not_overlap` — events skip RECOVERY_WINDOW_DAYS apart (no double-counting)
- `test_bearish_trend_required` — pullback only counts if 10-day trend is bearish
- `test_ma20_distance_threshold` — pullback only counts if ≥5% below MA20

### Success Criteria:

#### Automated Verification:
- [ ] All unit tests pass
- [ ] Edge cases covered

---

## Testing Strategy

### Unit Tests:
- `test_bounce_rate.py`: Pure indicator function tests with synthetic price data
- Existing `test_portfolio_selector.py`: Should still pass unchanged (no selector changes)

### Service Integration Test:
- `test_live20_service.py` (or add to existing): One test that runs `_analyze_symbol` with a mock data service returning 1-year data, and verifies the `Recommendation` has `live20_bounce_rate` and `live20_bounce_events` populated correctly. Also test the failure isolation: mock the bounce rate computation to raise, confirm core analysis results are still returned.

### Manual Testing Steps:
1. Start the backend and run `alembic upgrade head`
2. Trigger a Live20 analysis run on a stock list
3. Open the Live20 dashboard in the browser
4. Verify the "Bounce" column appears between ATR and Trend
5. Check that some stocks show bounce rate percentages
6. Sort by bounce rate — verify sorting works
7. Hover over a bounce rate — verify tooltip shows event count

## References

- Original ticket: `thoughts/shared/tickets/008-historical-bounce-rate-filter.md`
- Optimization log: `thoughts/shared/research/2026-02-24-optimization-log.md`
- Baseline sim #374: 865 trades, 40% WR, +57.1% return
