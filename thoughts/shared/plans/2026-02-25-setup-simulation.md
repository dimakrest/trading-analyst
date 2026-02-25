# Setup Simulation (Backtesting) Implementation Plan

## Overview

A standalone feature for backtesting user-defined trading setups against historical price data. Unlike the existing Arena (which uses algorithmic agent signals), this feature lets the user specify exact entry prices and stop losses, then replays price history to evaluate P&L.

## Current State Analysis

### What Exists:
- **Arena simulation** (`backend/app/services/arena/simulation_engine.py`) — agent-driven backtesting with single trailing stop
- **DataService** (`backend/app/services/data_service.py`) — cache-first price data fetching, reusable for this feature
- **FixedPercentTrailingStop** (`backend/app/services/arena/trailing_stop.py`) — reusable for day 2+ stop logic, including `calculate_initial_stop()` for initial stop setup
- **PriceBar** (`backend/app/services/arena/agent_protocol.py:34-59`) — reusable OHLCV dataclass
- **Existing error types** (`backend/app/core/exceptions.py`) — `SymbolNotFoundError`, `APIError`, `DataValidationError`
- **Symbol validation** (`backend/app/utils/validation.py`) — `is_valid_symbol()` for format validation
- **Frontend utilities** — `extractErrorMessage` (`frontend/src/utils/errors.ts`), `formatPnL`/`formatCurrency`/`formatPercent` (`frontend/src/utils/formatters.ts`)

### Key Differences from Arena:
- Entry: user-specified price level vs. agent signal
- Stop loss: two-tier (fixed day-1 price + trailing %) vs. single trailing %
- Retriggering: positions can reopen after stop-out
- No capital constraint, no portfolio selection, no agent evaluation

### Key Discoveries:
- `DataService.get_price_data()` returns `list[PriceDataPoint]` with OHLCV — can be reused directly
- `FixedPercentTrailingStop.update()` can be reused for day 2+ trailing stop logic
- `FixedPercentTrailingStop.calculate_initial_stop()` should be used for initial stop to avoid inline duplication
- Arena engine uses `min(stop_price, bar.open)` for gap-down exit realism — this pattern must be adopted
- API pattern: routes use `Depends(get_db_session)` and `Depends(get_data_service)` for injection
- Frontend pattern: controlled form → service call → results display, using shadcn `Card`/`Table`/`Input` components
- Mobile nav uses `NAV_ITEMS` directly in `grid-cols-4` — adding items requires careful handling

## Desired End State

- User navigates to `/setup-sim` page
- Adds multiple setups (symbol, entry price, day-1 stop, trailing stop %, start date)
- Sets an end date, clicks "Run Simulation"
- Sees overall metrics (total P&L, win rate, avg gain/loss) and per-setup trade list
- Results computed synchronously (no background worker — small data, fast computation)
- No DB persistence for MVP (stateless compute-and-return)

## What We're NOT Doing

- No DB models or migrations (stateless endpoint)
- No background worker or polling
- No comparison features
- No equity curve or daily snapshots
- No persistence of simulation history
- No capital constraints or position limits

## Implementation Approach

Stateless compute endpoint: POST request with setups → fetch price data → run simulation in-memory → return results. This avoids new DB models, migrations, and background workers while delivering the full feature.

---

## Phase 1: Backend — Schemas & Simulation Service

### Overview
Create the Pydantic request/response schemas and the core simulation logic as a pure service.

### Changes Required:

#### 1. Request/Response Schemas
**File**: `backend/app/schemas/setup_sim.py` (new)

```python
from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import Field, field_validator, model_validator

from app.schemas.base import StrictBaseModel
from app.utils.validation import is_valid_symbol


class SetupDefinition(StrictBaseModel):
    """A single user-defined trading setup."""
    symbol: str = Field(..., description="Ticker symbol")
    entry_price: Decimal = Field(..., gt=0, description="Price level that triggers long entry")
    stop_loss_day1: Decimal = Field(..., gt=0, description="Fixed stop loss price for day 1")
    trailing_stop_pct: Decimal = Field(
        ..., gt=0, lt=100,
        description="Trailing stop % applied from day 2 onward"
    )
    start_date: date = Field(..., description="Earliest date setup becomes eligible")

    @field_validator("symbol", mode="before")
    @classmethod
    def normalize_symbol(cls, v: str) -> str:
        v = v.strip().upper()
        if not is_valid_symbol(v):
            raise ValueError(f"Invalid symbol format: {v}")
        return v

    @field_validator("stop_loss_day1")
    @classmethod
    def stop_below_entry(cls, v: Decimal, info) -> Decimal:
        entry = info.data.get("entry_price")
        if entry and v >= entry:
            raise ValueError("stop_loss_day1 must be below entry_price")
        return v


class RunSetupSimulationRequest(StrictBaseModel):
    """Request to run a setup simulation."""
    setups: list[SetupDefinition] = Field(..., min_length=1, max_length=50)
    end_date: date = Field(..., description="Simulation end date")

    @field_validator("end_date")
    @classmethod
    def end_date_not_future(cls, v: date) -> date:
        if v > date.today():
            raise ValueError("end_date cannot be in the future")
        return v

    @model_validator(mode="after")
    def validate_date_ranges(self) -> "RunSetupSimulationRequest":
        """Validate all setup start_dates are before end_date and date range is reasonable."""
        for i, setup in enumerate(self.setups):
            if setup.start_date >= self.end_date:
                raise ValueError(
                    f"Setup {i + 1} ({setup.symbol}): start_date must be before end_date"
                )
        # Enforce max 5-year date range to prevent excessive data fetches
        earliest_start = min(s.start_date for s in self.setups)
        days_span = (self.end_date - earliest_start).days
        if days_span > 365 * 5:
            raise ValueError(
                f"Date range too large ({days_span} days). Maximum is 5 years (1825 days)."
            )
        return self


# Exit reason as a typed literal for type safety
ExitReasonType = Literal["stop_day1", "trailing_stop", "simulation_end"]


class TradeResult(StrictBaseModel):
    """A single completed trade."""
    entry_date: date
    entry_price: Decimal
    exit_date: date
    exit_price: Decimal
    shares: int
    pnl: Decimal
    return_pct: Decimal
    exit_reason: ExitReasonType


class SetupResult(StrictBaseModel):
    """Results for a single setup."""
    symbol: str
    entry_price: Decimal
    stop_loss_day1: Decimal
    trailing_stop_pct: Decimal
    start_date: date
    times_triggered: int
    pnl: Decimal
    trades: list[TradeResult]


class SimulationSummary(StrictBaseModel):
    """Overall simulation metrics."""
    total_pnl: Decimal
    total_pnl_pct: Decimal  # relative to actual capital deployed
    total_capital_deployed: Decimal  # sum of (entry_price * shares) across all trades
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: Decimal | None  # None if 0 trades
    avg_gain: Decimal | None  # avg P&L of winners
    avg_loss: Decimal | None  # avg P&L of losers
    position_size: Decimal


class SetupSimulationResponse(StrictBaseModel):
    """Complete simulation results."""
    summary: SimulationSummary
    setups: list[SetupResult]
```

#### 2. Simulation Service
**File**: `backend/app/services/setup_sim_service.py` (new)

Core simulation logic — a pure function that takes setups + price data and returns results.

```python
"""Setup simulation service for backtesting user-defined trading setups.

Simulation assumptions for OHLC daily bar data:
- When both entry and stop could trigger on the same bar, we assume entry
  happened first (standard backtesting convention — intra-day order cannot
  be determined from daily OHLC data).
- Gap-down handling: if the bar opens below a stop level, exit is at the
  open price (not the stop price), matching real-world slippage behavior.
  This follows the same convention as the Arena simulation engine.
"""

from datetime import date
from decimal import Decimal

from app.schemas.setup_sim import (
    SetupDefinition, TradeResult, SetupResult,
    SimulationSummary, SetupSimulationResponse,
)
from app.services.arena.agent_protocol import PriceBar
from app.services.arena.trailing_stop import FixedPercentTrailingStop

POSITION_SIZE = Decimal("1000")


def simulate_setup(
    setup: SetupDefinition,
    price_bars: list[PriceBar],  # sorted oldest→newest
    end_date: date,
) -> SetupResult:
    """Simulate a single setup over the given price data."""
    trades: list[TradeResult] = []
    trailing_stop = FixedPercentTrailingStop(setup.trailing_stop_pct)

    # Active trade state (None when no position)
    active_entry_date: date | None = None
    active_entry_price: Decimal | None = None
    active_shares: int | None = None
    active_highest: Decimal | None = None
    active_stop: Decimal | None = None

    for bar in price_bars:
        if bar.date < setup.start_date:
            continue

        if active_entry_date is None:
            # --- No position: check for entry ---
            if bar.high >= setup.entry_price:
                # Determine fill price:
                # - If open >= entry (gapped above): fill at open
                # - If open < entry and high >= entry: fill at entry_price
                if bar.open >= setup.entry_price:
                    fill_price = bar.open
                else:
                    fill_price = setup.entry_price

                shares = int(POSITION_SIZE / fill_price)
                if shares == 0:
                    continue  # price too high for position size

                # Day 1: check fixed stop loss
                if bar.low <= setup.stop_loss_day1:
                    # Entered and stopped out same day
                    # Gap-down realism: exit at min(stop, open) — but on day 1
                    # entry and stop are on the same bar, so exit at stop price
                    # (price must have passed through entry first, then dropped to stop)
                    exit_price = setup.stop_loss_day1
                    pnl = (exit_price - fill_price) * shares
                    return_pct = (
                        (exit_price - fill_price) / fill_price * 100
                    ).quantize(Decimal("0.01"))
                    trades.append(TradeResult(
                        entry_date=bar.date, entry_price=fill_price,
                        exit_date=bar.date, exit_price=exit_price,
                        shares=shares, pnl=pnl.quantize(Decimal("0.01")),
                        return_pct=return_pct, exit_reason="stop_day1",
                    ))
                    # Position closed — can retrigger on next day
                else:
                    # Position opened, survives day 1
                    # Use FixedPercentTrailingStop.calculate_initial_stop() to avoid
                    # duplicating stop calculation logic
                    active_entry_date = bar.date
                    active_entry_price = fill_price
                    active_shares = shares
                    active_highest, active_stop = trailing_stop.calculate_initial_stop(
                        fill_price
                    )
                    # Update highest to include day-1 high (may be above entry)
                    if bar.high > active_highest:
                        active_highest = bar.high
                        new_stop = (
                            active_highest * (Decimal("1") - setup.trailing_stop_pct / Decimal("100"))
                        ).quantize(Decimal("0.0001"))
                        active_stop = max(new_stop, active_stop)
        else:
            # --- Day 2+: apply trailing stop ---
            update = trailing_stop.update(
                current_high=bar.high,
                current_low=bar.low,
                previous_highest=active_highest,
                previous_stop=active_stop,
            )

            if update.stop_triggered:
                # Gap-down realism: if bar opens below stop, exit at open
                # (matching Arena engine convention)
                exit_price = min(update.trigger_price, bar.open)
                pnl = (exit_price - active_entry_price) * active_shares
                return_pct = (
                    (exit_price - active_entry_price) / active_entry_price * 100
                ).quantize(Decimal("0.01"))
                trades.append(TradeResult(
                    entry_date=active_entry_date, entry_price=active_entry_price,
                    exit_date=bar.date, exit_price=exit_price,
                    shares=active_shares, pnl=pnl.quantize(Decimal("0.01")),
                    return_pct=return_pct, exit_reason="trailing_stop",
                ))
                # Reset — can retrigger on next day
                active_entry_date = None
                active_entry_price = None
                active_shares = None
                active_highest = None
                active_stop = None
            else:
                active_highest = update.highest_price
                active_stop = update.stop_price

    # Close open position at end
    if active_entry_date is not None:
        last_bar = price_bars[-1] if price_bars else None
        if last_bar:
            exit_price = last_bar.close
            pnl = (exit_price - active_entry_price) * active_shares
            return_pct = (
                (exit_price - active_entry_price) / active_entry_price * 100
            ).quantize(Decimal("0.01"))
            trades.append(TradeResult(
                entry_date=active_entry_date, entry_price=active_entry_price,
                exit_date=last_bar.date, exit_price=exit_price,
                shares=active_shares, pnl=pnl.quantize(Decimal("0.01")),
                return_pct=return_pct, exit_reason="simulation_end",
            ))

    return SetupResult(
        symbol=setup.symbol,
        entry_price=setup.entry_price,
        stop_loss_day1=setup.stop_loss_day1,
        trailing_stop_pct=setup.trailing_stop_pct,
        start_date=setup.start_date,
        times_triggered=len(trades),
        pnl=sum(t.pnl for t in trades),
        trades=trades,
    )


def run_simulation(
    setup_results: list[SetupResult],
) -> SetupSimulationResponse:
    """Aggregate individual setup results into a simulation response."""
    all_trades = [t for sr in setup_results for t in sr.trades]

    total_pnl = sum(sr.pnl for sr in setup_results)
    total_trades = len(all_trades)
    winners = [t for t in all_trades if t.pnl > 0]
    losers = [t for t in all_trades if t.pnl <= 0]

    # Use actual capital deployed (entry_price * shares) for accurate P&L %
    total_capital_deployed = sum(
        t.entry_price * t.shares for t in all_trades
    ) if all_trades else Decimal("0")

    summary = SimulationSummary(
        total_pnl=total_pnl.quantize(Decimal("0.01")),
        total_pnl_pct=(
            (total_pnl / total_capital_deployed * 100).quantize(Decimal("0.01"))
            if total_capital_deployed > 0 else Decimal("0")
        ),
        total_capital_deployed=total_capital_deployed.quantize(Decimal("0.01")),
        total_trades=total_trades,
        winning_trades=len(winners),
        losing_trades=len(losers),
        win_rate=(
            (Decimal(len(winners)) / Decimal(total_trades) * 100).quantize(Decimal("0.01"))
            if total_trades > 0 else None
        ),
        avg_gain=(
            (sum(t.pnl for t in winners) / len(winners)).quantize(Decimal("0.01"))
            if winners else None
        ),
        avg_loss=(
            (sum(t.pnl for t in losers) / len(losers)).quantize(Decimal("0.01"))
            if losers else None
        ),
        position_size=POSITION_SIZE,
    )

    return SetupSimulationResponse(summary=summary, setups=setup_results)
```

### Success Criteria:

#### Automated Verification:
- [ ] Unit tests for `simulate_setup()` covering:
  - Basic entry trigger and exit via trailing stop
  - Day-1 stop loss trigger
  - Retriggering after stop-out
  - No entry when price never reaches entry level
  - Position closed at end date
  - Gap-up entry (open above entry price → fill at open)
  - Gap-down exit (bar opens below trailing stop → exit at open, not stop)
- [ ] Unit tests for `run_simulation()` aggregation:
  - Win rate, avg gain/loss calculations
  - Zero trades case
  - `total_capital_deployed` reflects actual shares * entry_price
- [ ] All tests pass, linting passes

#### Manual Verification:
- [ ] N/A (no UI yet)

**Implementation Note**: After completing this phase and all automated verification passes, pause for manual confirmation before proceeding to the next phase.

---

## Phase 2: Backend — API Route

### Overview
Create the API endpoint that accepts setups, fetches price data, runs the simulation, and returns results. Includes proper error handling for DataService failures.

### Changes Required:

#### 1. API Route
**File**: `backend/app/api/v1/setup_sim.py` (new)

```python
"""Setup simulation API routes."""

import asyncio
import logging
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.deps import get_data_service
from app.core.exceptions import APIError, SymbolNotFoundError
from app.schemas.setup_sim import (
    RunSetupSimulationRequest,
    SetupSimulationResponse,
)
from app.services.arena.agent_protocol import PriceBar
from app.services.data_service import DataService
from app.services.setup_sim_service import simulate_setup, run_simulation

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post(
    "/run",
    response_model=SetupSimulationResponse,
    status_code=status.HTTP_200_OK,
    summary="Run Setup Simulation",
    operation_id="run_setup_simulation",
    responses={
        422: {"description": "Invalid request (validation or unknown symbol)"},
        502: {"description": "Market data provider unavailable"},
    },
)
async def run_setup_simulation(
    request: RunSetupSimulationRequest,
    data_service: DataService = Depends(get_data_service),
) -> SetupSimulationResponse:
    """Run a setup simulation and return results synchronously."""
    # Determine unique symbols and date range
    symbols = list({s.symbol for s in request.setups})
    earliest_start = min(s.start_date for s in request.setups)

    logger.info(
        "Setup simulation: %d setups, %d symbols, %s to %s",
        len(request.setups), len(symbols), earliest_start, request.end_date,
    )

    # Fetch price data for all symbols in parallel
    async def fetch_symbol(symbol: str) -> tuple[str, list[PriceBar]]:
        records = await data_service.get_price_data(
            symbol=symbol,
            start_date=datetime.combine(
                earliest_start, datetime.min.time(), tzinfo=timezone.utc
            ),
            end_date=datetime.combine(
                request.end_date, datetime.max.time(), tzinfo=timezone.utc
            ),
            interval="1d",
        )
        bars = [
            PriceBar(
                date=r.timestamp.date(),
                open=Decimal(str(r.open_price)),
                high=Decimal(str(r.high_price)),
                low=Decimal(str(r.low_price)),
                close=Decimal(str(r.close_price)),
                volume=int(r.volume),
            )
            for r in records
        ]
        return symbol, bars

    try:
        results = await asyncio.gather(*[fetch_symbol(s) for s in symbols])
    except SymbolNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Symbol not found: {e}",
        )
    except APIError as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Market data provider unavailable: {e}",
        )

    price_data: dict[str, list[PriceBar]] = dict(results)

    # Run simulation for each setup
    setup_results = []
    for setup in request.setups:
        bars = price_data.get(setup.symbol, [])
        result = simulate_setup(setup, bars, request.end_date)
        setup_results.append(result)

    return run_simulation(setup_results)
```

#### 2. Register Route
**File**: `backend/app/main.py`

Add to the router registration section (after the arena router):

```python
from app.api.v1 import setup_sim

app.include_router(
    setup_sim.router,
    prefix=f"{settings.api_v1_prefix}/setup-sim",
    tags=["setup-sim"],
)
```

### Success Criteria:

#### Automated Verification:
- [ ] API integration test: POST valid request → 200 with correct response shape
- [ ] API validation test: invalid setups (stop >= entry, future end date, start >= end) → 422
- [ ] API error test: unknown symbol → 422 with clear message
- [ ] Linting passes

#### Manual Verification:
- [ ] `curl` or Swagger UI: POST a simple setup, verify results make sense against known price data

**Implementation Note**: After completing this phase and all automated verification passes, pause for manual confirmation before proceeding to the next phase.

---

## Phase 3: Frontend — Setup Simulation Page

### Overview
Create a new page at `/setup-sim` with a form for defining setups, running the simulation, and displaying results.

### Prerequisites
- Install shadcn Collapsible component: `npx shadcn@latest add collapsible`

### Changes Required:

#### 1. TypeScript Types
**File**: `frontend/src/types/setupSim.ts` (new)

```typescript
export interface SetupDefinition {
  symbol: string;
  entry_price: string;  // Decimal as string
  stop_loss_day1: string;
  trailing_stop_pct: string;
  start_date: string;   // YYYY-MM-DD
}

export interface TradeResult {
  entry_date: string;
  entry_price: string;
  exit_date: string;
  exit_price: string;
  shares: number;
  pnl: string;
  return_pct: string;
  exit_reason: 'stop_day1' | 'trailing_stop' | 'simulation_end';
}

export interface SetupResult {
  symbol: string;
  entry_price: string;
  stop_loss_day1: string;
  trailing_stop_pct: string;
  start_date: string;
  times_triggered: number;
  pnl: string;
  trades: TradeResult[];
}

export interface SimulationSummary {
  total_pnl: string;
  total_pnl_pct: string;
  total_capital_deployed: string;
  total_trades: number;
  winning_trades: number;
  losing_trades: number;
  win_rate: string | null;
  avg_gain: string | null;
  avg_loss: string | null;
  position_size: string;
}

export interface SetupSimulationResponse {
  summary: SimulationSummary;
  setups: SetupResult[];
}

export interface RunSetupSimulationRequest {
  setups: SetupDefinition[];
  end_date: string;
}
```

#### 2. API Service
**File**: `frontend/src/services/setupSimService.ts` (new)

```typescript
import { apiClient } from '@/lib/apiClient';
import type { RunSetupSimulationRequest, SetupSimulationResponse } from '@/types/setupSim';

const API_BASE = '/v1/setup-sim';

export const runSetupSimulation = async (
  request: RunSetupSimulationRequest,
): Promise<SetupSimulationResponse> => {
  const response = await apiClient.post<SetupSimulationResponse>(
    `${API_BASE}/run`,
    request,
  );
  return response.data;
};
```

#### 3. Page Component — Component Decomposition

The page is split into 3 components for maintainability:

**File**: `frontend/src/pages/SetupSimulation.tsx` (new) — Page orchestrator

```
SetupSimulation (page)
├── SetupSimForm        — form with dynamic setup rows + end date + run button
└── SetupSimResults     — summary metrics + per-setup collapsible trade tables
```

**State management**:
- `useState<SetupDefinition[]>` for the setup rows (initialized with 1 empty row)
- `useState<string>` for end date
- `useState<SetupSimulationResponse | null>` for results
- `useState<boolean>` for loading state

**Page-level API call pattern** (matches Arena page):
```typescript
const handleRun = async (request: RunSetupSimulationRequest) => {
  try {
    setIsLoading(true);
    setResults(null);
    const response = await runSetupSimulation(request);
    setResults(response);
    toast.success(`Simulation complete — ${response.summary.total_trades} trades`);
  } catch (err) {
    toast.error(extractErrorMessage(err, 'Failed to run simulation'));
  } finally {
    setIsLoading(false);
  }
};
```

**File**: `frontend/src/components/setup-sim/SetupSimForm.tsx` (new) — Form component

Props: `onSubmit: (request: RunSetupSimulationRequest) => void`, `isLoading: boolean`

State: `useState<SetupFormRow[]>` where `SetupFormRow` is the local form state (strings for all fields before conversion to the API type).

Key behaviors:
- Start with 1 empty row, "Add Setup" button appends more
- Each row: Symbol (text input), Entry Price (number input), Stop Loss Day 1 (number input), Trailing Stop % (number input), Start Date (date input), Remove button (X icon)
- End Date input above the setup table
- "Run Simulation" button disabled until all of:
  - At least 1 setup row has all fields filled
  - Each symbol is non-empty
  - Each entry price > 0
  - Each stop loss day 1 > 0 and < entry price
  - Each trailing stop % is between 0 and 100
  - Each start date is before end date
  - End date is set and not in the future
- Remove button hidden when only 1 row remains
- Uses shadcn `Card`, `CardContent`, `CardHeader`, `CardTitle`, `Input`, `Label`, `Button` components

**File**: `frontend/src/components/setup-sim/SetupSimResults.tsx` (new) — Results component

Props: `results: SetupSimulationResponse`

Two sections:
1. **Summary metrics grid** — reuse the MetricCard pattern from `ArenaResultsTable.tsx` (extract `MetricCard` into a shared component at `frontend/src/components/ui/MetricCard.tsx` or inline it). Display: Total P&L, Total P&L %, Win Rate, Avg Gain, Avg Loss, Total Trades. Use `formatPnL()` and `formatPercent()` from `frontend/src/utils/formatters.ts` for formatting and color-coding.

2. **Per-setup sections** — use shadcn `Collapsible` + `CollapsibleTrigger` + `CollapsibleContent` for expand/collapse. Each section header shows: symbol, times triggered, P&L (color-coded). Expanded content shows a `Table` with columns: Entry Date, Entry Price, Exit Date, Exit Price, Shares, P&L, Return %, Exit Reason.

3. **Empty state** — when `summary.total_trades === 0`, show "No setups were triggered during this period" message instead of the metrics grid.

#### 4. Navigation
**File**: `frontend/src/components/layouts/navigationConfig.ts`

Add nav item after Arena (use `Crosshair` icon from lucide-react):

```typescript
import { Crosshair } from 'lucide-react';

// Add to NAV_ITEMS array after Arena:
{
  path: '/setup-sim',
  label: 'Setups',
  icon: Crosshair,
},
```

**Mobile nav**: The current `MobileBottomTabs` renders all `NAV_ITEMS` in a `grid-cols-4` layout (already 5 items in 4 columns). Adding a 6th item compounds this issue. Update `grid-cols-4` to `grid-cols-5` in `MobileBottomTabs.tsx` to accommodate the growing nav. Alternatively, if this produces icons that are too small, switch to using `MOBILE_NAV_ITEMS` (first 4) + a "More" overflow button — but that is a larger change and can be deferred.

#### 5. Route Registration
**File**: `frontend/src/App.tsx`

```typescript
import { SetupSimulation } from './pages/SetupSimulation';

// Add route:
<Route path="/setup-sim" element={<SetupSimulation />} />
```

### Success Criteria:

#### Automated Verification:
- [ ] TypeScript compiles without errors
- [ ] Linting passes

#### Manual Verification:
- [ ] Navigate to `/setup-sim` — page loads with empty form
- [ ] Add 2-3 setups with real symbols (e.g., AAPL, MSFT)
- [ ] Run simulation — loading state shows, then results appear
- [ ] Summary metrics are correct and color-coded (green/red for P&L) using `formatPnL()`
- [ ] Per-setup sections expand/collapse to show individual trades
- [ ] Trades show entry/exit dates, prices, P&L
- [ ] Zero-trades simulation shows "No setups were triggered" message
- [ ] API error shows toast with specific error message (e.g., "Symbol not found: XYZ")
- [ ] Nav sidebar shows "Setups" link, highlights when active
- [ ] Mobile bottom tabs accommodate the new item without breaking layout

**Implementation Note**: After completing this phase and all verification passes, pause for manual confirmation.

---

## Testing Strategy

### Unit Tests (Phase 1):
**File**: `backend/tests/unit/services/test_setup_sim_service.py` (new)

Test cases for `simulate_setup()`:
1. **Entry trigger** — price crosses above entry → position opens
2. **Day-1 stop** — price hits day-1 stop on entry day → closed at stop
3. **Trailing stop** — price rises then drops by trailing % → closed at stop
4. **Retriggering** — after stop-out, price crosses entry again → new trade
5. **No entry** — price never reaches entry level → 0 trades
6. **End-of-sim close** — open position at end date → closed at last close
7. **Gap-up entry** — bar opens above entry → fill at open price
8. **Gap-down trailing stop exit** — bar opens below trailing stop → exit at open, not stop price
9. **Multiple trades same setup** — verify all trades tracked

Test cases for `run_simulation()`:
1. **Aggregation** — multiple setups, verify totals
2. **Win rate** — mix of winners and losers
3. **Zero trades** — no entries triggered, all metrics handle gracefully
4. **Capital deployed** — `total_capital_deployed` equals sum of (entry_price * shares) across all trades, not POSITION_SIZE * count

### Integration Tests (Phase 2):
**File**: `backend/tests/integration/test_setup_sim_api.py` (new)

1. **Happy path** — POST valid request, verify 200 response with correct shape
2. **Validation** — missing fields, stop >= entry, future end date, start >= end → 422
3. **Date range limit** — > 5 years → 422
4. **Unknown symbol** — verify 422 with descriptive message

### Manual Testing (Phase 3):
1. Define setups for AAPL and MSFT with known breakout levels
2. Run simulation for a past 3-month period
3. Spot-check a few trades against actual chart data
4. Verify P&L math: shares * (exit - entry) matches reported P&L

## References

- Original ticket: `thoughts/shared/tickets/008-setup-simulation.md`
- Arena simulation engine (reference): `backend/app/services/arena/simulation_engine.py`
- Trailing stop (reused): `backend/app/services/arena/trailing_stop.py`
- DataService (reused): `backend/app/services/data_service.py`
- Error types: `backend/app/core/exceptions.py`
- Symbol validation: `backend/app/utils/validation.py`
- Frontend error utility: `frontend/src/utils/errors.ts`
- Frontend formatting: `frontend/src/utils/formatters.ts`
- Mobile nav: `frontend/src/components/layouts/MobileBottomTabs.tsx`
