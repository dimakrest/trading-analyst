# Arena Portfolio Analytics — Test Gap Remediation Plan

## Overview

Close four test gaps identified in the portfolio analytics feature: a missing bug fix in the frontend type, missing response assertions in the backend unit API test, a missing exact-value Sharpe test, and a missing integration test that verifies analytics fields are actually populated after simulation finalization. One minor frontend component gap is also included.

## Current State Analysis

### Confirmed Gaps

| # | Gap | Severity | File |
|---|-----|----------|------|
| 1 | `ExitReason` frontend type missing `'insufficient_capital'` | Bug | `frontend/src/types/arena.ts:17` |
| 2 | `GET /simulations/{id}` unit test never asserts analytics fields in response | High | `backend/tests/unit/api/v1/test_arena.py` |
| 3 | Sharpe ratio tests assert only sign/not-None — no exact value verification | Medium | `backend/tests/unit/services/arena/test_arena_analytics.py` |
| 4 | No integration test runs a simulation to completion and asserts analytics fields are populated | High | `backend/tests/integration/test_arena_simulation.py` |
| 5 | `ArenaSectorBreakdown`: no test for open position with `null entry_price`/`null shares` → cost basis 0, not NaN | Low | `frontend/src/components/arena/ArenaSectorBreakdown.test.tsx` |

### What is Already Tested Well (Do NOT Re-Test)

- `ArenaSectorBreakdown.test.tsx` — **already has comprehensive coverage**: sort order, Unknown-last, win rates, P&L coloring, empty state, both sections. Only the null-entry-price guard is missing.
- `test_arena_analytics.py` — empty, all-winners, all-losers, mixed, hold time, Sharpe edge cases all covered.
- `test_arena_simulation.py` — simulation lifecycle, trailing stop, metrics, winning trade — just missing analytics field assertions at completion.

### Key Architectural Discoveries

- **analytics.py**: `compute_simulation_analytics(sim, positions, snapshots)` — pure function, mutates `simulation` in-place at `simulation_engine.py:882` inside `_finalize_simulation()`. Only called when `closed` list is non-empty (line 26).
- **Sharpe formula** (`analytics.py:65-73`): `daily_returns = [float(s.daily_return_pct) / 100 for s in snapshots]`, annualized via `(mean / std_dev) * sqrt(252)`, quantized to `Decimal("0.0001")`. Uses sample std dev (n-1).
- **Test DB**: Transaction rollback isolation — `db_session` commits are savepoint releases, all rolled back after the test.
- **Integration test pattern**: `SimulationEngine(db_session, session_factory=rollback_session_factory)`, patch `app.services.arena.simulation_engine.get_agent` + `engine.data_service.get_price_data`, call `run_to_completion()`.
- **`_build_simulation_response`** (`arena.py:49-88`): analytics fields are direct model column reads — if DB has them set, they appear in the response.

## Desired End State

1. `arena.ts` `ExitReason` type includes all three backend values: `'stop_hit' | 'simulation_end' | 'insufficient_capital'`
2. `test_arena.py` GET `/simulations/{id}` test asserts all 6 analytics fields are present in the response (null for non-completed simulation, non-null for a completed simulation with closed positions)
3. `test_arena_analytics.py` contains one test with a hand-calculated Sharpe value (`Decimal("31.7490")` for the specified input)
4. `test_arena_simulation.py` contains one integration test that completes a simulation with trades and asserts all 6 analytics fields are non-null and pass sanity checks
5. `ArenaSectorBreakdown.test.tsx` contains one test for a position with `entry_price: null` and `shares: null` in the open positions list — verifies it does not break allocation rendering

## What We're NOT Doing

- Not adding E2E Playwright tests (existing smoke tests are sufficient)
- Not testing `ArenaSimulationDetail.tsx` conditional rendering (too complex, lower priority)
- Not re-testing the 40+ scenarios already covered in `test_arena_analytics.py`
- Not testing `arenaService.ts` functions (lower priority, no critical math)

---

## Phase 1: Bug Fix + Trivial Assertions

**Effort: ~30 minutes**

### Changes Required

#### 1. Fix `ExitReason` type

**File**: `frontend/src/types/arena.ts:17`

```typescript
// Before
export type ExitReason = 'stop_hit' | 'simulation_end';

// After
export type ExitReason = 'stop_hit' | 'simulation_end' | 'insufficient_capital';
```

No test needed — this is a type fix. TypeScript will now correctly type-check any switch/if-else on `exit_reason`.

#### 2. Assert analytics fields in GET `/simulations/{id}` unit test

**File**: `backend/tests/unit/api/v1/test_arena.py`

Find the existing test that calls `GET /simulations/{id}` (in class `TestGetSimulation`). Add two assertions:

**2a. Analytics fields are null for a non-completed simulation:**

In the existing basic GET test (the one that creates a PENDING or RUNNING sim), add after `sim_data = data["simulation"]`:

```python
# Analytics fields present but null for non-completed simulation
assert "avg_hold_days" in sim_data
assert "avg_win_pnl" in sim_data
assert "avg_loss_pnl" in sim_data
assert "profit_factor" in sim_data
assert "sharpe_ratio" in sim_data
assert "total_realized_pnl" in sim_data
assert sim_data["avg_hold_days"] is None
assert sim_data["sharpe_ratio"] is None
assert sim_data["total_realized_pnl"] is None
```

**2b. Analytics fields serialized correctly for a completed simulation:**

Add a new test method in `TestGetSimulation` class:

```python
@pytest.mark.unit
async def test_get_simulation_includes_analytics_fields_when_populated(
    self, async_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Analytics fields appear in GET /simulations/{id} response when set."""
    from decimal import Decimal
    sim = ArenaSimulation(
        name="Analytics Response Test",
        symbols=["AAPL"],
        start_date=date(2024, 1, 1),
        end_date=date(2024, 1, 31),
        initial_capital=Decimal("10000"),
        position_size=Decimal("1000"),
        agent_type="live20",
        agent_config={},
        status=SimulationStatus.COMPLETED.value,
        total_trades=2,
        winning_trades=1,
        # Analytics fields explicitly set
        total_realized_pnl=Decimal("150.50"),
        avg_hold_days=Decimal("5.0"),
        avg_win_pnl=Decimal("300.00"),
        avg_loss_pnl=Decimal("-149.50"),
        profit_factor=Decimal("2.008"),
        sharpe_ratio=Decimal("1.2345"),
    )
    db_session.add(sim)
    await db_session.commit()
    await db_session.refresh(sim)

    response = await async_client.get(f"/api/v1/arena/simulations/{sim.id}")
    assert response.status_code == 200
    sim_data = response.json()["simulation"]

    assert Decimal(sim_data["total_realized_pnl"]) == Decimal("150.50")
    assert Decimal(sim_data["avg_hold_days"]) == Decimal("5.0")
    assert Decimal(sim_data["avg_win_pnl"]) == Decimal("300.00")
    assert Decimal(sim_data["avg_loss_pnl"]) == Decimal("-149.50")
    assert Decimal(sim_data["profit_factor"]) == Decimal("2.008")
    assert Decimal(sim_data["sharpe_ratio"]) == Decimal("1.2345")
```

### Success Criteria

#### Automated Verification:
- [ ] `./scripts/dc.sh exec backend-dev pytest -m unit backend/tests/unit/api/v1/test_arena.py -v` — all tests pass
- [ ] `cd frontend && npx tsc --noEmit` — no TypeScript errors

#### Manual Verification:
- [ ] TypeScript correctly errors if code uses `exit_reason === 'insufficient_capital'` before this fix

**After this phase passes, proceed to Phase 2.**

---

## Phase 2: Sharpe Exact Value Test

**Effort: ~30 minutes**

### Changes Required

**File**: `backend/tests/unit/services/arena/test_arena_analytics.py`

Add one new test method inside the existing Sharpe test class (or as a standalone if the file isn't class-based). Use this exact input to get a deterministic expected value:

**Hand-calculated expected value:**
- Snapshots: `daily_return_pct = [Decimal("1.00"), Decimal("2.00"), Decimal("3.00")]`
- `daily_returns = [0.01, 0.02, 0.03]`
- `n = 3`, `mean = 0.02`
- `variance = ((0.01-0.02)² + 0 + (0.03-0.02)²) / 2 = 0.0001`
- `std_dev = 0.01`
- `sharpe = (0.02 / 0.01) * sqrt(252) = 2.0 * 15.874507866... = 31.749015...`
- Quantized to `Decimal("0.0001")` → **`Decimal("31.7490")`**

```python
@pytest.mark.unit
def test_sharpe_ratio_exact_value() -> None:
    """Sharpe ratio matches hand-calculated expected value.

    Verifies the annualization factor (sqrt(252)) and quantization (0.0001)
    are applied correctly so a scaling error would be caught.

    Input:
        daily_return_pct = [1.00, 2.00, 3.00] (as percentages stored in DB)
    Calculation:
        daily_returns = [0.01, 0.02, 0.03]
        mean = 0.02, std_dev = 0.01
        sharpe = (0.02 / 0.01) * sqrt(252) = 2 * 15.8745... = 31.7490...
    """
    sim = FakeSimulation()
    positions = [FakePosition(realized_pnl=Decimal("100"))]  # one closed trade required
    snapshots = [
        FakeSnapshot(snapshot_date=date(2024, 1, 3), daily_return_pct=Decimal("1.00"), day_number=1),
        FakeSnapshot(snapshot_date=date(2024, 1, 4), daily_return_pct=Decimal("2.00"), day_number=2),
        FakeSnapshot(snapshot_date=date(2024, 1, 5), daily_return_pct=Decimal("3.00"), day_number=3),
    ]
    compute_simulation_analytics(sim, positions, snapshots)
    assert sim.sharpe_ratio == Decimal("31.7490")
```

### Success Criteria

#### Automated Verification:
- [ ] `./scripts/dc.sh exec backend-dev pytest -m unit backend/tests/unit/services/arena/test_arena_analytics.py -v` — all tests pass including the new one

**After this phase passes, proceed to Phase 3.**

---

## Phase 3: Analytics Fields Populated After Finalization (Integration)

**Effort: ~2 hours**

This is the most critical gap: no test confirms analytics fields are populated when a real simulation completes with closed trades.

### Changes Required

**File**: `backend/tests/integration/test_arena_simulation.py`

Add a new test method to the existing `TestArenaSimulationIntegration` class. The test must ensure at least one position is opened **and closed** (stop-triggered or end-of-simulation) so `compute_simulation_analytics` runs the non-empty path.

**Strategy**: Use the existing `test_full_simulation_with_winning_trade` pattern — it already produces a closed trade via stop-trigger. Extend it (or add a new test) that additionally asserts all 6 analytics fields.

The simplest path is a short simulation (10–15 trading days) where:
1. Agent issues `BUY` on the first signal day
2. Price rises, then drops sharply to trigger the trailing stop
3. Position closes with a profit
4. Simulation completes → `_finalize_simulation` calls `compute_simulation_analytics`

```python
@pytest.mark.integration
async def test_analytics_fields_populated_after_simulation_completion(
    self, db_session, rollback_session_factory
) -> None:
    """All six analytics fields are non-null after a simulation with closed trades.

    Verifies that _finalize_simulation() correctly calls compute_simulation_analytics()
    and the results are persisted to the ArenaSimulation object.
    """
    from unittest.mock import MagicMock
    from decimal import Decimal

    # Price scenario: rises from 100 to 115, then drops to 105 (triggers 5% stop)
    # Entry at ~100 on day 16, stop triggered after new high, exit with profit.
    start = date(2024, 1, 1)
    price_data = []
    for i in range(90):
        if i < 20:
            price = 100.0 + (i * 0.75)   # rising: 100 → 115
        else:
            price = 115.0 - ((i - 20) * 0.5)  # falling: 115 → ...
        price_data.append(
            PriceDataPoint(
                symbol="AAPL",
                timestamp=datetime.combine(
                    start + timedelta(days=i),
                    datetime.min.time(),
                    tzinfo=timezone.utc,
                ),
                open_price=price,
                high_price=price * 1.02,
                low_price=price * 0.97,  # low enough to eventually trigger 5% stop
                close_price=price * 1.01,
                volume=1_000_000,
            )
        )

    simulation = ArenaSimulation(
        name="Analytics Finalization Test",
        symbols=["AAPL"],
        start_date=date(2024, 1, 15),
        end_date=date(2024, 3, 31),
        initial_capital=Decimal("10000.00"),
        position_size=Decimal("1000.00"),
        agent_type="live20",
        agent_config={"trailing_stop_pct": 5.0},
        status=SimulationStatus.PENDING.value,
    )
    db_session.add(simulation)
    await db_session.commit()
    await db_session.refresh(simulation)

    # BUY on the first evaluation, then HOLD/NO_SIGNAL afterward
    call_count = [0]
    mock_agent = MagicMock()
    mock_agent.required_lookback_days = 60

    async def mock_evaluate(symbol, price_history, current_date, has_position):
        call_count[0] += 1
        if call_count[0] == 1 and not has_position:
            return AgentDecision(symbol=symbol, action="BUY", score=85, reasoning="Signal")
        return AgentDecision(
            symbol=symbol,
            action="HOLD" if has_position else "NO_SIGNAL",
            score=50,
        )

    mock_agent.evaluate = mock_evaluate

    engine = SimulationEngine(db_session, session_factory=rollback_session_factory)

    async def mock_get_price_data(symbol, start_date, end_date, interval):
        return price_data if symbol == "AAPL" else []

    with patch("app.services.arena.simulation_engine.get_agent", return_value=mock_agent):
        with patch.object(engine.data_service, "get_price_data", side_effect=mock_get_price_data):
            await engine.initialize_simulation(simulation.id)
            completed_sim = await engine.run_to_completion(simulation.id)

    # --- Simulation must have completed with at least one closed trade ---
    assert completed_sim.status == SimulationStatus.COMPLETED.value
    assert completed_sim.total_trades >= 1, (
        "Test requires at least one closed trade to exercise analytics"
    )

    # --- All six analytics fields must be non-null ---
    assert completed_sim.total_realized_pnl is not None, "total_realized_pnl should be set"
    assert completed_sim.avg_hold_days is not None, "avg_hold_days should be set"
    assert completed_sim.avg_win_pnl is not None or completed_sim.avg_loss_pnl is not None, (
        "At least one of avg_win_pnl or avg_loss_pnl should be set"
    )
    assert completed_sim.sharpe_ratio is not None, "sharpe_ratio should be set"

    # --- Sanity checks on computed values ---
    # total_realized_pnl must match the sum of closed position P&L
    result = await db_session.execute(
        select(ArenaPosition)
        .where(ArenaPosition.simulation_id == completed_sim.id)
        .where(ArenaPosition.realized_pnl.is_not(None))
    )
    closed_positions = result.scalars().all()
    expected_total_pnl = sum(p.realized_pnl for p in closed_positions)
    assert completed_sim.total_realized_pnl == expected_total_pnl, (
        f"total_realized_pnl {completed_sim.total_realized_pnl} != "
        f"sum of closed positions {expected_total_pnl}"
    )

    # avg_hold_days must be positive
    assert completed_sim.avg_hold_days > 0, "avg_hold_days must be > 0 for closed trades"

    # profit_factor: set only if both winners and losers exist — don't assert here
    # (the simulation may be all-winners or all-losers)
```

### Success Criteria

#### Automated Verification:
- [ ] `./scripts/dc.sh exec backend-dev pytest -m integration backend/tests/integration/test_arena_simulation.py::TestArenaSimulationIntegration::test_analytics_fields_populated_after_simulation_completion -v` passes
- [ ] All existing tests in the file still pass

**After this phase passes, proceed to Phase 4.**

---

## Phase 4: Null Entry Price Guard in ArenaSectorBreakdown

**Effort: ~20 minutes**

### Changes Required

**File**: `frontend/src/components/arena/ArenaSectorBreakdown.test.tsx`

Add one test in the existing `'only open positions with sectors'` describe block (or a new `'null entry_price guard'` describe):

```typescript
describe('open positions with null entry_price or shares', () => {
  it('does not produce NaN in allocation when entry_price is null', () => {
    const positions = [
      // Position with all fields null (pending state — not yet opened)
      {
        ...makeOpenPosition(1, 'AAPL', 'Technology'),
        entry_price: null,
        shares: null,
        current_stop: null,
        highest_price: null,
      } as unknown as Position,
      makeOpenPosition(2, 'MSFT', 'Technology', '200.00', 5),
    ];
    render(<ArenaSectorBreakdown positions={positions} snapshot={null} />);
    // Should render without crashing and show Technology row
    expect(screen.getByText('Technology')).toBeInTheDocument();
    // Percentage should be a valid number (not "NaN%")
    const cells = screen.getAllByRole('cell');
    const cellTexts = cells.map((c) => c.textContent ?? '');
    expect(cellTexts.some((t) => t.includes('NaN'))).toBe(false);
  });
});
```

### Success Criteria

#### Automated Verification:
- [ ] `cd frontend && npm run test:unit -- ArenaSectorBreakdown` — all tests pass

---

## Testing Strategy Summary

| Phase | Command | Expected result |
|---|---|---|
| 1 (type fix + unit) | `npx tsc --noEmit` + `pytest -m unit test_arena.py` | 0 TS errors, unit tests pass |
| 2 (Sharpe exact) | `pytest -m unit test_arena_analytics.py` | All pass, exact value confirmed |
| 3 (integration) | `pytest -m integration test_arena_simulation.py` | New test passes, analytics fields populated |
| 4 (component) | `npm run test:unit -- ArenaSectorBreakdown` | No NaN rendering on null fields |
| Final | `pytest -m unit && pytest -m integration` + `npm run test:all` | Full suite green |

### Running Tests (per `docs/guides/testing.md`)

```bash
# Backend unit
./scripts/dc.sh exec backend-dev pytest -m unit

# Backend integration (requires Docker)
./scripts/dc.sh exec backend-dev pytest -m integration

# Frontend unit
cd frontend && npm run test:unit

# Frontend all
cd frontend && npm run test:all
```

## References

- Analytics implementation: `backend/app/services/arena/analytics.py`
- Engine finalization: `backend/app/services/arena/simulation_engine.py:872`
- API response builder: `backend/app/api/v1/arena.py:49-88`
- Existing analytics tests: `backend/tests/unit/services/arena/test_arena_analytics.py`
- Existing integration tests: `backend/tests/integration/test_arena_simulation.py`
- Frontend type: `frontend/src/types/arena.ts:17`
- Component tests: `frontend/src/components/arena/ArenaSectorBreakdown.test.tsx`
