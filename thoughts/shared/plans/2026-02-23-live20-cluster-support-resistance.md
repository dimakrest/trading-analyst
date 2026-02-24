# Live20 Cluster-Based Support & Resistance — Implementation Plan

## Overview

Replace the current single-candle Standard Pivot Point S/R calculation with a **cluster-based algorithm** that detects historically validated support and resistance levels. The new approach identifies where price has actually reversed multiple times, clusters nearby levels, and scores them by touch count, recency, and volume — producing levels that are statistically more likely to hold.

## Current State Analysis

### What Exists:
- `support_resistance_levels()` at `backend/app/indicators/technical.py:726` — Standard Pivot Points using **only the most recent candle** (`high[-1]`, `low[-1]`, `close[-1]`)
- DB columns: `live20_pivot`, `live20_support_1`, `live20_resistance_1` (Numeric 12,4) at `recommendation.py:169-176`
- Schema maps these at `live20.py:65-67`, serialized as floats at `live20.py:141`
- Frontend table column at `Live20Table.tsx:259-294` shows "R {price} (+X%)" / "S {price} (-X%)"
- Frontend chart lines at `ExpandedRowContent.tsx:35-71` draws S1 (green), R1 (red), PP (yellow) on candlestick
- Constants at `constants.py:1132-1222` define cluster-based parameters (touch proximity, min touches, pivot window, strength weights) — **pre-planned but currently unused**

### What's Wrong:
- Only 1 candle used out of 60 days of available data (all history discarded)
- Daily pivots are for day trading, not swing trading
- No historical validation — levels have zero bounce history
- No volume confirmation
- The levels shift every day, providing no stability

### Data Flow (unchanged structure):
```
Live20Service._analyze_symbol()
  → [NEW] cluster_support_resistance(highs, lows, closes, volumes)
  → Store support_1, resistance_1, touches on Recommendation
  → API returns via Live20ResultResponse
  → Frontend: Live20Table shows levels with touch count
  → Frontend: CandlestickChart draws S/R lines (no more pivot line)
```

## Desired End State

- S/R levels are based on **historical swing points clustered and scored** over 1 year of daily data
- Each level has a touch count (number of times price reversed at that zone)
- Levels with more touches and more recent activity score higher
- Volume at touch points boosts level confidence
- Frontend shows touch count alongside price levels
- Chart line width varies by level strength
- The `pivot` field is set to `None` (no pivot concept in cluster-based S/R)

## What We're NOT Doing

- Not adding multi-timeframe S/R (daily data only for now)
- Not adding S/R to agent scoring decisions (remains supplementary info)
- Not implementing Volume Profile (POC/VAH/VAL) — requires intraday data
- Not adding supply/demand zone detection — separate, more complex feature
- Not removing the old `support_resistance_levels()` function — it may be useful for other contexts
- Not removing the `pivot` DB column — just set to None (avoids unnecessary migration complexity)

---

## Phase 1: Core Algorithm — Cluster-Based S/R Detection

### Overview
Implement the new `cluster_support_resistance()` function with comprehensive unit tests. Pure algorithm — no integration changes.

### Algorithm Design

```
Input: highs[], lows[], closes[], volumes[] (1 year of daily OHLCV)

Step 1: Detect swing points
  → Scan for local extrema using a window (default 5 bars each side)
  → Swing high at i: high[i] >= all highs in [i-window, i+window]
  → Swing low at i: low[i] <= all lows in [i-window, i+window]
  → Output: list of (index, price, type) tuples

Step 2: Cluster nearby levels (fixed-center merge)
  → Sort all swing points by price
  → Walk sorted list: first point starts a new cluster and sets its center
  → Subsequent points merge into the cluster if within TOUCH_PROXIMITY (2%) of
    the cluster's FIXED CENTER (first point's price), NOT a running mean
  → This prevents chaining drift where a dense sequence of gradually rising
    prices absorbs a nearby distinct level
  → Each cluster = one S/R level
  → Level price = mean of cluster member prices (for the final representative price)

Step 3: Score each cluster
  → touch_score = min(cluster_size / 5, 1.0)          [weight: 0.35]
  → recency_score = exp(-0.005 * bars_since_last_touch) [weight: 0.30]
  → volume_score = min(avg_vol_at_touches / max(avg_vol, ε), 2.0) / 2.0 [weight: 0.20]
  → proximity_score = 1.0 - (distance_from_price / max_distance)  [weight: 0.15]
  → strength = 0.35 * touch + 0.30 * recency + 0.20 * volume + 0.15 * proximity

  Note: volume_score guarded against zero average volume (ε = 1e-10).
  Proximity rewards levels closer to current price — a medium-strength
  level 1% away is more actionable than a strong level 9% away.

Step 4: Filter
  → Remove levels with touches < MIN_TOUCHES (2)
  → Remove levels with strength < MIN_STRENGTH (0.3)
  → Remove levels > MAX_DISTANCE (10%) from current price

Step 5: Return all levels sorted by strength (descending)

Note on partial history: Stocks with < 252 bars (recent IPOs, etc.) are
handled gracefully. The algorithm only requires >= 2*window+1 bars (11 by
default). Fewer bars means fewer swing points and potentially no qualifying
levels — in which case the function returns an empty list and the service
stores NULL for S/R fields.
```

### Changes Required:

#### 1. Data Structures
**File**: `backend/app/indicators/technical.py`
**Changes**: Add dataclass and new function at end of file (after existing `support_resistance_levels`)

```python
from dataclasses import dataclass

@dataclass
class SRLevel:
    """A detected support/resistance level."""
    price: float
    touches: int
    strength: float       # 0.0 to 1.0 composite score
    last_touch_idx: int   # index in the input array of most recent touch
```

#### 2. Swing Point Detection
**File**: `backend/app/indicators/technical.py`

```python
def _detect_swing_points(
    highs: NDArray[np.float64],
    lows: NDArray[np.float64],
    window: int = 5,
) -> list[tuple[int, float]]:
    """Detect local extrema (swing highs and swing lows).

    A swing high at index i: high[i] >= all highs in [i-window, i+window].
    A swing low at index i: low[i] <= all lows in [i-window, i+window].

    Returns list of (index, price) tuples for all detected swing points.
    """
```

Both swing highs and swing lows are returned in the same list — they all represent price levels where reversals occurred, regardless of direction.

#### 3. Level Clustering
**File**: `backend/app/indicators/technical.py`

```python
def _cluster_price_levels(
    points: list[tuple[int, float]],
    merge_threshold_pct: float = 0.02,
) -> list[list[tuple[int, float]]]:
    """Cluster nearby price points using fixed-center sort-and-merge.

    Sort all points by price. Walk through the sorted list.
    The first point in each cluster sets the cluster's CENTER.
    Subsequent points merge into the cluster if within
    merge_threshold_pct of that FIXED center price.

    Using a fixed center (not a running mean) prevents chaining
    drift where a dense sequence of gradually increasing prices
    absorbs nearby distinct levels.

    Returns list of clusters, where each cluster is a list of
    (index, price) tuples.
    """
```

#### 4. Level Scoring
**File**: `backend/app/indicators/technical.py`

```python
def _score_levels(
    clusters: list[list[tuple[int, float]]],
    volumes: NDArray[np.float64],
    total_bars: int,
    current_price: float,
    max_distance_pct: float = 0.10,
    touch_weight: float = 0.35,
    recency_weight: float = 0.30,
    volume_weight: float = 0.20,
    proximity_weight: float = 0.15,
    decay_rate: float = 0.005,
) -> list[SRLevel]:
    """Score each cluster by touch count, recency, volume, and proximity.

    - touch_score: min(cluster_size / 5, 1.0)
    - recency_score: exp(-decay_rate * bars_since_last_touch)
      (bars, not calendar days, since we work with index positions)
    - volume_score: min(avg_volume_at_touches / max(overall_avg_volume, 1e-10), 2.0) / 2.0
    - proximity_score: 1.0 - (abs(level_price - current_price) / (current_price * max_distance_pct))
      Closer levels score higher. Levels at max_distance get 0, levels at current price get 1.

    Returns list of SRLevel objects.
    """
```

Note: We use bar count (index distance from end) rather than calendar days for the decay calculation. With daily data, 1 bar ≈ 1 trading day. The decay rate of 0.005 gives a half-life of ~139 bars (~139 trading days ≈ 6.5 months).

#### 5. Main Function
**File**: `backend/app/indicators/technical.py`

```python
def cluster_support_resistance(
    highs: list[float] | NDArray[np.float64],
    lows: list[float] | NDArray[np.float64],
    closes: list[float] | NDArray[np.float64],
    volumes: list[float] | NDArray[np.float64],
    window: int = 5,
    merge_threshold_pct: float = 0.02,
    min_touches: int = 2,
    min_strength: float = 0.3,
    max_distance_pct: float = 0.10,
) -> list[SRLevel]:
    """Detect support/resistance levels using historical swing point clustering.

    Algorithm:
    1. Detect swing highs and lows (local extrema within window)
    2. Cluster nearby price points (within merge_threshold_pct)
    3. Score each cluster (touch count × recency × volume)
    4. Filter by minimum touches, minimum strength, max distance from current price
    5. Return levels sorted by strength (descending)

    Args:
        highs/lows/closes/volumes: OHLCV arrays (daily, >= 2*window+1 bars)
        window: Bars on each side for swing point detection
        merge_threshold_pct: Max price distance (%) to merge into same cluster
        min_touches: Minimum cluster size to qualify as a level
        min_strength: Minimum composite score (0-1) to include
        max_distance_pct: Max distance from current close to include

    Returns:
        List of SRLevel objects sorted by strength (descending).
        Empty list if insufficient data or no levels found.
    """
```

#### 6. Update Constants
**File**: `backend/app/core/constants.py`
**Changes**: Update the existing S/R constants section to match the new algorithm's scoring weights. Change the weights from the current 5-factor split to the 3-factor split:

```python
# Level Strength Calculation Weights (cluster-based algorithm, 4 factors)
SUPPORT_RESISTANCE_TOUCH_WEIGHT = 0.35
SUPPORT_RESISTANCE_RECENCY_WEIGHT = 0.30
SUPPORT_RESISTANCE_VOLUME_WEIGHT = 0.20
SUPPORT_RESISTANCE_PROXIMITY_WEIGHT = 0.15

# Recency Decay
SUPPORT_RESISTANCE_DECAY_RATE = 0.005
"""Exponential decay rate for recency scoring. Half-life ≈ 139 bars (~6.5 months)."""
```

Remove the old weights that are no longer used: `TIME_WEIGHT`, `PIVOT_WEIGHT`, `RESPECT_WEIGHT`, `VOLATILITY_WEIGHT`.

### Success Criteria:

#### Automated Verification:
- [ ] All existing tests pass (no regressions)
- [ ] New unit tests for `_detect_swing_points()`:
  - Detects known swing highs/lows in synthetic data
  - Returns empty list for insufficient data (< 2*window+1 bars)
  - Handles flat price (no swings) gracefully
- [ ] New unit tests for `_cluster_price_levels()`:
  - Merges points within threshold
  - Keeps distinct points as separate clusters
  - Handles single point (returns 1 cluster)
  - Handles empty input
- [ ] New unit tests for `_score_levels()`:
  - Higher touch count → higher score
  - More recent touches → higher score
  - Higher volume at touches → higher score
  - Score bounded between 0 and 1
- [ ] New unit tests for `cluster_support_resistance()`:
  - End-to-end: synthetic data with known S/R levels produces expected output
  - Filters by min_touches correctly
  - Filters by min_strength correctly
  - Filters by max_distance correctly
  - Returns levels sorted by strength descending
  - Returns empty list for < 11 bars of data
  - Real-world-ish data: oscillating price between 95-105 produces levels near those bounds

**Implementation Note**: After completing this phase, pause for review. The algorithm is the critical piece — get it right before integrating.

---

## Phase 2: Backend Integration — Wire Into Live20 Service

### Overview
Connect the new cluster-based S/R algorithm to the Live20 pipeline. Increase data fetch to 1 year. Add touch count fields to the DB and API schema.

### Changes Required:

#### 1. Increase Data Fetch Window + Slice Arrays for Indicator Safety
**File**: `backend/app/services/live20_service.py`
**Changes**: Increase fetch to 365 days, but slice arrays so existing indicators
receive the same ~60-day input they receive today. This is critical because
code analysis confirmed that `calculate_atr_percentage` (EWM path-dependent)
and `analyze_cci` signal_type (stateful crossover scan) produce **different outputs**
when given 252 bars vs 40 bars. All other indicators are safe (they only use
trailing windows), but we slice defensively for all of them.

```python
# Fetch price data (1 year for cluster-based S/R)
end_date = datetime.now(timezone.utc)
start_date = end_date - timedelta(days=365)

price_records = await data_service.get_price_data(
    symbol=symbol, start_date=start_date, end_date=end_date, interval="1d",
)

if not price_records or len(price_records) < 25:
    return Live20Result(symbol=symbol, status="error", ...)

# Full history arrays — used ONLY for S/R calculation
all_highs = [float(r.high_price) for r in price_records]
all_lows = [float(r.low_price) for r in price_records]
all_closes = [float(r.close_price) for r in price_records]
all_volumes = [float(r.volume) for r in price_records]

# Recent arrays — preserve existing indicator behavior (ATR, CCI are path-dependent)
recent_records = price_records[-60:]
opens = [float(r.open_price) for r in recent_records]
highs = [float(r.high_price) for r in recent_records]
lows = [float(r.low_price) for r in recent_records]
closes = [float(r.close_price) for r in recent_records]
volumes = [float(r.volume) for r in recent_records]

# S/R uses full 1-year history
sr_levels = cluster_support_resistance(all_highs, all_lows, all_closes, all_volumes, ...)

# All other indicators use recent data only (unchanged behavior)
atr_percentage = calculate_atr_percentage(highs, lows, closes)
criteria = evaluator.evaluate_criteria(opens, highs, lows, closes, volumes, ...)
```

**Why this matters**: Without slicing, ATR values change (EWM `adjust=False`
accumulates from bar 0) and CCI signal classification changes (stateful scan
of full crossover history). Both would silently alter scores for every symbol
in a system handling real money.

#### 2. Database Model — Add touch count columns
**File**: `backend/app/models/recommendation.py`
**Changes**: Add 2 new columns after the existing S/R columns, update column docs:

```python
# Support/Resistance levels (cluster-based: historical swing point detection)
live20_pivot: Mapped[Decimal | None] = mapped_column(
    Numeric(12, 4), nullable=True, doc="Deprecated: set to None for cluster-based S/R"
)
live20_support_1: Mapped[Decimal | None] = mapped_column(
    Numeric(12, 4), nullable=True, doc="Strongest support level below current price (cluster-based)"
)
live20_resistance_1: Mapped[Decimal | None] = mapped_column(
    Numeric(12, 4), nullable=True, doc="Strongest resistance level above current price (cluster-based)"
)
live20_support_1_touches: Mapped[int | None] = mapped_column(
    Integer, nullable=True, doc="Number of historical touches at support_1 level"
)
live20_resistance_1_touches: Mapped[int | None] = mapped_column(
    Integer, nullable=True, doc="Number of historical touches at resistance_1 level"
)
```

#### 3. Alembic Migration
**File**: New migration `backend/alembic/versions/YYYYMMDD_HHMM-<hash>_add_sr_touch_count_columns.py`
**Changes**: Add `live20_support_1_touches` and `live20_resistance_1_touches` Integer nullable columns.

#### 4. Service — Replace Pivot S/R with Cluster S/R
**File**: `backend/app/services/live20_service.py`
**Changes**: Replace the import and call at lines 13, 112-117:

```python
# Before:
from app.indicators.technical import support_resistance_levels

sr_support, sr_resistance, sr_pivot = support_resistance_levels(
    highs, lows, closes, num_levels=1
)
pivot_decimal = Decimal(str(round(sr_pivot, 4))) if sr_pivot is not None else None
support_1_decimal = ...
resistance_1_decimal = ...

# After:
from app.indicators.technical import cluster_support_resistance

sr_levels = cluster_support_resistance(
    highs, lows, closes, volumes,
    window=SUPPORT_RESISTANCE_PIVOT_WINDOW,
    merge_threshold_pct=SUPPORT_RESISTANCE_TOUCH_PROXIMITY,
    min_touches=SUPPORT_RESISTANCE_MIN_TOUCHES,
    min_strength=SUPPORT_RESISTANCE_MIN_STRENGTH,
    max_distance_pct=SUPPORT_RESISTANCE_MAX_DISTANCE,
)

# Pick strongest support (below price) and resistance (above price)
current_price = closes[-1]
strongest_support = None
strongest_resistance = None
for level in sr_levels:  # already sorted by strength desc
    if level.price < current_price and strongest_support is None:
        strongest_support = level
    elif level.price >= current_price and strongest_resistance is None:
        strongest_resistance = level
    if strongest_support and strongest_resistance:
        break

support_1_decimal = Decimal(str(round(strongest_support.price, 4))) if strongest_support else None
resistance_1_decimal = Decimal(str(round(strongest_resistance.price, 4))) if strongest_resistance else None
support_1_touches = strongest_support.touches if strongest_support else None
resistance_1_touches = strongest_resistance.touches if strongest_resistance else None
```

Update the Recommendation construction to include touch counts and set pivot to None:

```python
live20_pivot=None,  # No pivot concept in cluster-based S/R
live20_support_1=support_1_decimal,
live20_resistance_1=resistance_1_decimal,
live20_support_1_touches=support_1_touches,
live20_resistance_1_touches=resistance_1_touches,
```

#### 5. Schema — Add touch count fields
**File**: `backend/app/schemas/live20.py`
**Changes**: Add fields to `Live20ResultResponse`:

```python
# Support/Resistance levels (cluster-based)
pivot: Decimal | None = None         # Always None for cluster-based S/R
support_1: Decimal | None = None
resistance_1: Decimal | None = None
support_1_touches: int | None = None
resistance_1_touches: int | None = None
```

Update `from_recommendation()`:
```python
support_1_touches=rec.live20_support_1_touches,
resistance_1_touches=rec.live20_resistance_1_touches,
```

#### 6. Update Existing Tests
**File**: `backend/tests/unit/services/test_live20_service.py`
**Changes**: The existing `test_analyze_symbol_persists_support_resistance` (line 139)
patches `support_resistance_levels` and asserts pivot formula values (PP=129.6667, etc.).
This test must be rewritten to:
- Patch `cluster_support_resistance` instead
- Assert cluster-based S/R values and touch counts
- Assert `live20_pivot is None`

**File**: `backend/tests/unit/schemas/test_live20_schema.py`
**Changes**:
- `_make_mock_recommendation` helper (line 48): add `live20_support_1_touches` and
  `live20_resistance_1_touches` fields
- `test_maps_support_resistance_fields` (line 60): add assertions for touch count fields
- `test_null_support_resistance_when_not_present` (line 70): add touch count null assertions
- `test_support_resistance_serialized_as_float_in_json` (line 84): this test asserts
  `pivot` is a float — must be updated since pivot will now be `None`. Either test that
  pivot serializes as `null`, or remove the pivot assertion and add touch count (int) assertions.
- `test_null_support_resistance_serialized_as_null_in_json` (line 99): add touch count
  null serialization assertions

### Success Criteria:

#### Automated Verification:
- [ ] Migration runs cleanly
- [ ] Existing tests updated for new S/R behavior (service test asserts cluster-based values, not pivot formula)
- [ ] Schema test updated: `from_recommendation()` maps touch count fields
- [ ] New test: service returns None for S/R when insufficient data
- [ ] New test: service returns correct touch counts
- [ ] Regression test: existing indicator outputs (ATR, CCI, MA20, trend, volume, candle) are identical before and after the fetch window change (verifies array slicing correctness)

#### Manual Verification:
- [ ] Run a Live20 analysis with 5+ symbols
- [ ] API response shows `support_1`, `resistance_1` at historically meaningful levels
- [ ] `support_1_touches` and `resistance_1_touches` are > 0 for detected levels
- [ ] `pivot` is `null` in the response
- [ ] Levels visually make sense on a chart (open TradingView to cross-reference)

**Implementation Note**: Pause for manual verification. The numbers should match visible S/R zones on charts before proceeding to frontend.

---

## Phase 3: Frontend — Display Touch Count and Update Chart Lines

### Overview
Update the frontend to show touch count alongside S/R levels and adjust chart lines.

### Changes Required:

#### 1. TypeScript Types — Add touch count fields
**File**: `frontend/src/types/live20.ts`
**Changes**: Add to `Live20Result` interface:

```typescript
support_1_touches: number | null;
resistance_1_touches: number | null;
```

#### 2. Table Column — Show touch count
**File**: `frontend/src/components/live20/Live20Table.tsx`
**Changes**: Update the `support_resistance` column cell renderer to include touch count:

```typescript
{resistance_1 !== null && (
  <span className="text-accent-bearish">
    R {resistance_1.toFixed(2)}
    {pct(resistance_1) != null && (
      <span className="text-muted-foreground ml-1">
        ({pct(resistance_1)! >= 0 ? '+' : ''}{pct(resistance_1)!.toFixed(2)}%)
      </span>
    )}
    {resistance_1_touches != null && resistance_1_touches > 0 && (
      <span className="text-muted-foreground ml-1">×{resistance_1_touches}</span>
    )}
  </span>
)}
```

Same pattern for support_1 / support_1_touches.

#### 3. Chart Lines — Remove pivot, adjust styling
**File**: `frontend/src/components/live20/ExpandedRowContent.tsx`
**Changes**: Update `buildPriceLines()`:

- Remove the pivot line (lines 60-68)
- Adjust line width based on touch count (thicker = more touches):

```typescript
function buildPriceLines(result: Live20Result): ChartPriceLine[] {
  const lines: ChartPriceLine[] = [];

  if (result.support_1 !== null) {
    const touches = result.support_1_touches ?? 0;
    lines.push({
      price: result.support_1,
      color: '#22c55e',
      lineWidth: touches >= 4 ? 2 : 1,
      lineStyle: 'dashed',
      label: `S ${touches > 0 ? `×${touches}` : ''}`,
      labelVisible: true,
    });
  }

  if (result.resistance_1 !== null) {
    const touches = result.resistance_1_touches ?? 0;
    lines.push({
      price: result.resistance_1,
      color: '#ef4444',
      lineWidth: touches >= 4 ? 2 : 1,
      lineStyle: 'dashed',
      label: `R ${touches > 0 ? `×${touches}` : ''}`,
      labelVisible: true,
    });
  }

  return lines;
}
```

#### 4. Export `buildPriceLines` and Test Directly
**File**: `frontend/src/components/live20/ExpandedRowContent.tsx`
**Changes**: Export the `buildPriceLines` function so it can be tested as a pure unit function.
The current `CandlestickChart` mock in `ExpandedRowContent.test.tsx` (lines 15-21) throws
away the `priceLines` prop, making it impossible to assert on chart line behavior through
the component. Testing `buildPriceLines` directly is cleaner than refactoring the mock.

```typescript
// Change from:
function buildPriceLines(result: Live20Result): ChartPriceLine[] {
// To:
export function buildPriceLines(result: Live20Result): ChartPriceLine[] {
```

**File**: `frontend/src/components/live20/ExpandedRowContent.test.tsx`
**Changes**: Add direct unit tests for `buildPriceLines`:

```typescript
import { buildPriceLines } from './ExpandedRowContent';

describe('buildPriceLines', () => {
  it('returns empty array when no S/R levels', () => { ... });
  it('includes support line with touch count in label', () => { ... });
  it('includes resistance line with touch count in label', () => { ... });
  it('does not include pivot line', () => { ... });
  it('uses lineWidth 2 for 4+ touches', () => { ... });
  it('uses lineWidth 1 for <4 touches', () => { ... });
  it('omits touch count from label when touches is null', () => { ... });
  it('omits touch count from label when touches is 0', () => { ... });
});
```

#### 5. Add S/R Column Tests
**File**: `frontend/src/components/live20/Live20Table.test.tsx`
**Changes**: Add a dedicated `describe('S/R column')` test block. The current test file
has zero coverage for the S/R column renderer — it sets `support_1: null, resistance_1: null`
in all fixtures. The column has 6+ conditional branches that need coverage:

```typescript
describe('S/R column', () => {
  it('shows dash when both levels are null', () => {
    const result = createMockResult({ support_1: null, resistance_1: null });
    // Expect: "-"
  });
  it('shows resistance with percentage and touch count', () => {
    const result = createMockResult({
      resistance_1: 135.5, resistance_1_touches: 4, close_price: 130.0
    });
    // Expect: "R 135.50 (+4.23%) ×4"
  });
  it('shows support with percentage and touch count', () => {
    const result = createMockResult({
      support_1: 125.0, support_1_touches: 3, close_price: 130.0
    });
    // Expect: "S 125.00 (-3.85%) ×3"
  });
  it('shows both levels stacked', () => { ... });
  it('omits touch count when null', () => {
    // result with resistance_1_touches: null → no "×N" displayed
  });
  it('omits touch count when zero', () => {
    // result with resistance_1_touches: 0 → no "×0" displayed
  });
});
```

#### 6. Update Test Fixtures
**Files** (all 5 locations that need `support_1_touches: null, resistance_1_touches: null`):
- `frontend/src/components/live20/ExpandedRowContent.test.tsx` (line 26, `createMockResult`)
- `frontend/src/components/live20/Live20Table.test.tsx` (line 14, `createMockResult`)
- `frontend/src/components/live20/Live20Dashboard.test.tsx` (lines 30, 64, 93 — inline objects)
- `frontend/src/hooks/useLive20.test.ts` (line 27, factory)
- `frontend/src/hooks/useLive20Filters.test.ts` (line 6, factory)

Also update `frontend/src/pages/Live20RunDetail.test.tsx` (lines 58, 90, 122, 154, 186 — inline fixtures).

### Success Criteria:

#### Automated Verification:
- [ ] TypeScript compiles without errors
- [ ] All frontend tests pass
- [ ] ESLint passes
- [ ] `buildPriceLines` unit tests cover: no levels, support only, resistance only, both, touch counts, line widths, no pivot
- [ ] S/R column tests cover: both null, resistance only, support only, both present, null touches, zero touches

#### Manual Verification:
- [ ] S/R column shows "R 135.50 (+3.46%) ×4" format with touch counts
- [ ] Touch count hidden when null or zero (no "×0" displayed)
- [ ] Chart shows S/R lines without pivot line
- [ ] Lines with 4+ touches appear thicker than lines with 2-3 touches
- [ ] Expanding a row with no S/R levels shows no lines (no crash)
- [ ] `pivot` field remains in `Live20Result` interface (not removed — backend still sends it)

---

## Testing Strategy

### Unit Tests (Phase 1):
- `_detect_swing_points`: synthetic V-shape, W-bottom, head-and-shoulders patterns
- `_cluster_price_levels`: known clusters, edge cases (single point, all same price), fixed-center behavior
- `_score_levels`: verify score components individually and combined
- `cluster_support_resistance`: end-to-end with realistic oscillating price data

### Service Tests (Phase 2):
- `test_analyze_symbol_persists_cluster_sr`: verify cluster-based values stored
- `test_analyze_symbol_sr_touch_counts`: verify touch counts are persisted
- `test_analyze_symbol_no_sr_for_short_data`: insufficient data → null S/R
- `test_analyze_symbol_indicator_outputs_unchanged`: regression test verifying ATR, CCI, MA20, trend, volume, candle outputs are identical with 365-day fetch + array slicing vs the original 60-day fetch

### Frontend Tests (Phase 3):
- `buildPriceLines` unit tests: no levels, support/resistance with touches, line widths, no pivot
- S/R column tests: both null, one null, both present, with/without touch counts, zero guard
- Test fixtures updated across all 6 files (5 factory locations + Live20RunDetail inline fixtures)

### Manual Validation:
- Run on 10-20 well-known stocks (AAPL, MSFT, TSLA, etc.)
- Cross-reference detected levels with TradingView charts
- Verify touch counts match visible bounce points

## Key Constants (from `constants.py`, updated)

| Constant | Value | Purpose |
|----------|-------|---------|
| `SUPPORT_RESISTANCE_PIVOT_WINDOW` | 5 | Bars on each side for swing detection |
| `SUPPORT_RESISTANCE_TOUCH_PROXIMITY` | 0.02 (2%) | Max price distance to merge into cluster |
| `SUPPORT_RESISTANCE_MIN_TOUCHES` | 2 | Min cluster size to qualify |
| `SUPPORT_RESISTANCE_MIN_STRENGTH` | 0.3 | Min composite score (0-1) |
| `SUPPORT_RESISTANCE_MAX_DISTANCE` | 0.10 (10%) | Max distance from current price |
| `SUPPORT_RESISTANCE_MAX_LEVELS` | 10 | Cap on returned levels |
| `SUPPORT_RESISTANCE_TOUCH_WEIGHT` | 0.35 | Touch count weight in scoring |
| `SUPPORT_RESISTANCE_RECENCY_WEIGHT` | 0.30 | Recency weight in scoring |
| `SUPPORT_RESISTANCE_VOLUME_WEIGHT` | 0.20 | Volume weight in scoring |
| `SUPPORT_RESISTANCE_PROXIMITY_WEIGHT` | 0.15 | Proximity to current price weight |
| `SUPPORT_RESISTANCE_DECAY_RATE` | 0.005 | Recency decay (half-life ≈ 139 bars) |

## References

- Previous plan (pivot-based): `thoughts/shared/plans/2026-02-23-live20-support-resistance.md`
- S/R review and research: conversation analysis (2026-02-23)
- Academic basis: Chung & Bellotti (2021) arXiv:2101.07410 — S/R levels with more historical bounces are statistically more likely to hold
- Reference implementation: [github.com/day0market/support_resistance](https://github.com/day0market/support_resistance)
- Existing constants: `backend/app/core/constants.py:1132-1222`
- Existing S/R function: `backend/app/indicators/technical.py:726-783`
