# TP Trigger Fix + ExitReason TypeScript Hotfix

## Overview

Fix two Phase 2 (#49) issues that were identified during architectural review of #47:

1. **TP trigger bug**: Take profit checks unrealized return against `today_bar.close` but should trigger on `today_bar.high` (intraday high), with exit price = `min(tp_target, today_bar.open)` for gap-up handling. This is a prerequisite for Phase 3 (#50) -- sizing validation backtests depend on correct TP behavior.

2. **ExitReason TypeScript hotfix**: Frontend type is missing `take_profit` and `max_hold` values deployed by Phases 1-2. Any simulation exiting via TP or max hold shows broken display.

## Current State Analysis

### TP Trigger Logic (`simulation_engine.py:510-560`)

The TP block computes unrealized return from `today_bar.close`:

```python
# Line 514-518
unrealized_return_pct = float(
    (today_bar.close - position.entry_price)
    / position.entry_price
    * 100
)
```

This value is used for both trigger checks:
- Fixed-% TP (line 523): `unrealized_return_pct >= take_profit_pct`
- ATR TP (line 533): `unrealized_return_pct >= atr_target`

Exit price is unconditionally `today_bar.close` (line 537).

**Problem**: A stock that touches $108 intraday (hitting an 8% TP target) but closes at $105 will NOT trigger TP. This understates backtest returns and misses fills that would occur in live trading.

### ExitReason Frontend Type (`frontend/src/types/arena.ts:17`)

```typescript
export type ExitReason = 'stop_hit' | 'simulation_end' | 'insufficient_capital';
```

Missing: `'take_profit'` and `'max_hold'` (backend enum has both at `models/arena.py:54-55`).

### Key Discoveries

- Existing tests (`test_simulation_engine.py:3113-3409`) all use `close` for TP assertions -- they will need updating
- No ATR-multiple TP tests exist (all 5 tests use `take_profit_pct` only)
- The `_make_open_position` helper (line 3135) provides sufficient scaffolding for new tests
- Test assertion at line 3205 explicitly checks `exit_price == Decimal("110.00")` (the close price) -- this will break and must be updated

## Desired End State

1. TP triggers when intraday high reaches the target (not close)
2. Exit price = `min(tp_target_price, today_bar.open)` -- gap-up at open fills at open, normal TP fills at exact target
3. Both fixed-% and ATR-multiple paths use the same trigger/exit logic
4. Frontend ExitReason type matches backend enum
5. All existing tests updated, new tests for high-trigger and gap-up scenarios

## What We're NOT Doing

- No changes to TP schema fields or API
- No changes to exit priority order (stop still takes precedence)
- No ATR calculation changes
- No max hold logic changes
- No frontend component changes beyond the type fix

---

## Phase 1: Regression Tests (Write Failing Tests First)

### Overview

Write tests that exercise the correct behavior (high-based trigger, gap-up exit price). These tests will FAIL on the current code, proving the bug exists. After the fix, they will PASS.

### Changes Required

**File**: `backend/tests/unit/services/arena/test_simulation_engine.py`

Add the following tests to `TestSimulationEngineTakeProfit` class (after line 3409):

#### Test 1: TP triggers on intraday high even when close is below target

```python
@pytest.mark.unit
async def test_fixed_take_profit_triggers_on_intraday_high(
    self, db_session, rollback_session_factory
) -> None:
    """TP triggers when intraday HIGH reaches target, even if close is below.

    Entry: $100, target: 8%, high: $109 (9% intraday), close: $105 (5%).
    TP should trigger because high exceeded 8% target.
    Exit price = target price ($108), not close ($105).
    """
    sim = self._make_simulation(
        db_session,
        {"trailing_stop_pct": 5.0, "take_profit_pct": 8.0},
    )
    db_session.add(sim)
    await db_session.commit()
    await db_session.refresh(sim)

    position = self._make_open_position(sim.id, entry_price=100.0, stop=95.0)
    db_session.add(position)
    await db_session.commit()

    engine = SimulationEngine(db_session, session_factory=rollback_session_factory)

    price_bars = [
        PriceBar(
            date=date(2024, 1, 15),
            open=Decimal("102.00"),
            high=Decimal("109.00"),   # 9% intraday -- exceeds 8% TP target
            low=Decimal("101.00"),
            close=Decimal("105.00"),  # 5% close -- below TP target
            volume=1000000,
        )
    ]
    trading_days = [date(2024, 1, 15), date(2024, 1, 16), date(2024, 1, 17)]
    engine._trading_days_cache[sim.id] = trading_days
    engine._price_cache[sim.id] = {"AAPL": price_bars}
    engine._sector_cache[sim.id] = {"AAPL": None}

    mock_agent = MagicMock()
    mock_agent.required_lookback_days = 60
    mock_agent.evaluate = AsyncMock(
        return_value=AgentDecision(symbol="AAPL", action="NO_SIGNAL")
    )

    with patch("app.services.arena.simulation_engine.get_agent", return_value=mock_agent):
        await engine.step_day(sim.id)

    await db_session.refresh(position)
    assert position.status == PositionStatus.CLOSED.value
    assert position.exit_reason == ExitReason.TAKE_PROFIT.value
    # Exit at target price ($108), not close ($105)
    assert position.exit_price == Decimal("108.00")
```

#### Test 2: Gap-up past TP target -- exit at open

```python
@pytest.mark.unit
async def test_fixed_take_profit_gap_up_exits_at_open(
    self, db_session, rollback_session_factory
) -> None:
    """When stock gaps up past TP target on open, exit at open price.

    Entry: $100, target: 8% ($108), open: $112 (gaps past target).
    Exit price = open ($112), not target ($108), because we can't
    fill below the open price on a gap-up.
    """
    sim = self._make_simulation(
        db_session,
        {"trailing_stop_pct": 5.0, "take_profit_pct": 8.0},
    )
    db_session.add(sim)
    await db_session.commit()
    await db_session.refresh(sim)

    position = self._make_open_position(sim.id, entry_price=100.0, stop=95.0)
    db_session.add(position)
    await db_session.commit()

    engine = SimulationEngine(db_session, session_factory=rollback_session_factory)

    price_bars = [
        PriceBar(
            date=date(2024, 1, 15),
            open=Decimal("112.00"),   # Gaps up past $108 target
            high=Decimal("115.00"),
            low=Decimal("111.00"),
            close=Decimal("113.00"),
            volume=1000000,
        )
    ]
    trading_days = [date(2024, 1, 15), date(2024, 1, 16), date(2024, 1, 17)]
    engine._trading_days_cache[sim.id] = trading_days
    engine._price_cache[sim.id] = {"AAPL": price_bars}
    engine._sector_cache[sim.id] = {"AAPL": None}

    mock_agent = MagicMock()
    mock_agent.required_lookback_days = 60
    mock_agent.evaluate = AsyncMock(
        return_value=AgentDecision(symbol="AAPL", action="NO_SIGNAL")
    )

    with patch("app.services.arena.simulation_engine.get_agent", return_value=mock_agent):
        await engine.step_day(sim.id)

    await db_session.refresh(position)
    assert position.status == PositionStatus.CLOSED.value
    assert position.exit_reason == ExitReason.TAKE_PROFIT.value
    # Exit at open ($112) since it gapped past target ($108)
    assert position.exit_price == Decimal("112.00")
```

#### Test 3: TP does NOT trigger when high is below target

```python
@pytest.mark.unit
async def test_fixed_take_profit_no_trigger_when_high_below_target(
    self, db_session, rollback_session_factory
) -> None:
    """TP does NOT trigger when intraday high is below target.

    Entry: $100, target: 8%, high: $107 (7%), close: $105.
    Neither high nor close reaches 8%. Position stays open.
    """
    sim = self._make_simulation(
        db_session,
        {"trailing_stop_pct": 5.0, "take_profit_pct": 8.0},
    )
    db_session.add(sim)
    await db_session.commit()
    await db_session.refresh(sim)

    position = self._make_open_position(sim.id, entry_price=100.0, stop=95.0)
    db_session.add(position)
    await db_session.commit()

    engine = SimulationEngine(db_session, session_factory=rollback_session_factory)

    price_bars = [
        PriceBar(
            date=date(2024, 1, 15),
            open=Decimal("102.00"),
            high=Decimal("107.00"),   # 7% -- below 8% target
            low=Decimal("101.00"),
            close=Decimal("105.00"),
            volume=1000000,
        )
    ]
    trading_days = [date(2024, 1, 15), date(2024, 1, 16), date(2024, 1, 17)]
    engine._trading_days_cache[sim.id] = trading_days
    engine._price_cache[sim.id] = {"AAPL": price_bars}
    engine._sector_cache[sim.id] = {"AAPL": None}

    mock_agent = MagicMock()
    mock_agent.required_lookback_days = 60
    mock_agent.evaluate = AsyncMock(
        return_value=AgentDecision(symbol="AAPL", action="NO_SIGNAL")
    )

    with patch("app.services.arena.simulation_engine.get_agent", return_value=mock_agent):
        await engine.step_day(sim.id)

    await db_session.refresh(position)
    assert position.status == PositionStatus.OPEN.value
```

#### Test 4: ATR-multiple TP triggers on intraday high

```python
@pytest.mark.unit
async def test_atr_take_profit_triggers_on_intraday_high(
    self, db_session, rollback_session_factory
) -> None:
    """ATR-multiple TP triggers when intraday high reaches ATR target.

    Entry: $100, ATR%: 3.0, multiplier: 2.0, target: 6%.
    High: $107 (7% intraday) -- exceeds 6% target. Close: $103.
    Exit at target price ($106).
    """
    sim = self._make_simulation(
        db_session,
        {"trailing_stop_pct": 5.0, "take_profit_atr_mult": 2.0},
    )
    db_session.add(sim)
    await db_session.commit()
    await db_session.refresh(sim)

    position = self._make_open_position(sim.id, entry_price=100.0, stop=95.0)
    db_session.add(position)
    await db_session.commit()

    engine = SimulationEngine(db_session, session_factory=rollback_session_factory)

    price_bars = [
        PriceBar(
            date=date(2024, 1, 15),
            open=Decimal("102.00"),
            high=Decimal("107.00"),   # 7% intraday -- exceeds 6% ATR target
            low=Decimal("101.00"),
            close=Decimal("103.00"),  # 3% close -- below target
            volume=1000000,
        )
    ]
    trading_days = [date(2024, 1, 15), date(2024, 1, 16), date(2024, 1, 17)]
    engine._trading_days_cache[sim.id] = trading_days
    engine._price_cache[sim.id] = {"AAPL": price_bars}
    engine._sector_cache[sim.id] = {"AAPL": None}

    # Mock ATR to return 3.0%
    with patch.object(engine, "_calculate_symbol_atr_pct", return_value=3.0):
        mock_agent = MagicMock()
        mock_agent.required_lookback_days = 60
        mock_agent.evaluate = AsyncMock(
            return_value=AgentDecision(symbol="AAPL", action="NO_SIGNAL")
        )

        with patch("app.services.arena.simulation_engine.get_agent", return_value=mock_agent):
            await engine.step_day(sim.id)

    await db_session.refresh(position)
    assert position.status == PositionStatus.CLOSED.value
    assert position.exit_reason == ExitReason.TAKE_PROFIT.value
    # Exit at target price: $100 * (1 + 6/100) = $106
    assert position.exit_price == Decimal("106.00")
```

### Update Existing Tests

The existing test at line 3153 (`test_fixed_take_profit_triggers_when_return_meets_target`) asserts `exit_price == Decimal("110.00")` (the close). After the fix, this test's price bars have:
- Entry: $100, TP target: 8% ($108)
- Open: $105, High: $112, Close: $110

The exit price should become $108 (the TP target, since open $105 < target $108). Update line 3205:

```python
# Before:
assert position.exit_price == Decimal("110.00")  # closed at today's close
assert position.realized_pnl == Decimal("100.00")  # (110-100)*10

# After:
assert position.exit_price == Decimal("108.00")  # TP target price (open < target)
assert position.realized_pnl == Decimal("80.00")   # (108-100)*10
```

The trade count test at line 3367 has: Entry $100, TP 5% ($105), Open $108, High $112, Close $110. Since open $108 > target $105, exit at open. Update line 3409 area:

```python
# Before (implicit): exit_price = close ($110)
# After: exit_price = open ($108) because open gaps past $105 target
```

Review and update assertions accordingly.

### Success Criteria

#### Automated:
- [x] New tests 1-4 FAIL on current code (confirming the bug)
- [x] Existing tests still pass (no changes yet to production code)

---

## Phase 2: Fix TP Trigger Logic

### Overview

Change the trigger check from close-based to high-based, and the exit price from close to min(target, open).

### Changes Required

**File**: `backend/app/services/arena/simulation_engine.py`

#### 2a. Change trigger calculation (lines 510-518)

Replace:
```python
                    # --- Layer 5: Take Profit ---
                    # Check AFTER the trailing stop so that a stop exit always
                    # takes precedence.  Use today's close as the exit price.
                    if take_profit_pct is not None or take_profit_atr_mult is not None:
                        unrealized_return_pct = float(
                            (today_bar.close - position.entry_price)
                            / position.entry_price
                            * 100
                        )
                        take_profit_triggered = False
```

With:
```python
                    # --- Layer 5: Take Profit ---
                    # Check AFTER the trailing stop so that a stop exit always
                    # takes precedence. Trigger on intraday high; exit at
                    # min(target_price, today_open) for gap-up handling.
                    if take_profit_pct is not None or take_profit_atr_mult is not None:
                        unrealized_return_pct_at_high = float(
                            (today_bar.high - position.entry_price)
                            / position.entry_price
                            * 100
                        )
                        take_profit_triggered = False
                        tp_target_pct: float | None = None
```

#### 2b. Update fixed-% trigger (lines 521-525)

Replace:
```python
                        if (
                            take_profit_pct is not None
                            and unrealized_return_pct >= take_profit_pct
                        ):
                            take_profit_triggered = True
```

With:
```python
                        if (
                            take_profit_pct is not None
                            and unrealized_return_pct_at_high >= take_profit_pct
                        ):
                            take_profit_triggered = True
                            tp_target_pct = take_profit_pct
```

#### 2c. Update ATR trigger (lines 527-534)

Replace:
```python
                        if not take_profit_triggered and take_profit_atr_mult is not None:
                            pos_atr_pct = self._calculate_symbol_atr_pct(
                                simulation_id, symbol, current_date
                            )
                            if pos_atr_pct is not None and pos_atr_pct > 0:
                                atr_target = take_profit_atr_mult * pos_atr_pct
                                if unrealized_return_pct >= atr_target:
                                    take_profit_triggered = True
```

With:
```python
                        if not take_profit_triggered and take_profit_atr_mult is not None:
                            pos_atr_pct = self._calculate_symbol_atr_pct(
                                simulation_id, symbol, current_date
                            )
                            if pos_atr_pct is not None and pos_atr_pct > 0:
                                atr_target = take_profit_atr_mult * pos_atr_pct
                                if unrealized_return_pct_at_high >= atr_target:
                                    take_profit_triggered = True
                                    tp_target_pct = atr_target
```

#### 2d. Update exit price calculation (lines 536-537)

Replace:
```python
                        if take_profit_triggered:
                            exit_price = today_bar.close
```

With:
```python
                        if take_profit_triggered:
                            tp_target_price = position.entry_price * (
                                1 + Decimal(str(tp_target_pct)) / 100
                            )
                            exit_price = min(tp_target_price, today_bar.open)
```

The rest of the exit block (lines 538-560) is unchanged -- it uses `exit_price` which now has the correct value.

### Success Criteria

#### Automated:
- [x] All new Phase 1 tests PASS
- [x] All updated existing tests PASS
- [x] Full TP test suite passes: `./scripts/dc.sh exec backend-dev pytest tests/unit/services/arena/test_simulation_engine.py -k "TakeProfit" -v`

#### Manual:
- [ ] Run an existing simulation with TP enabled, verify results reflect high-based triggers

---

## Phase 3: ExitReason TypeScript Hotfix

### Overview

Add missing `take_profit` and `max_hold` values to the frontend ExitReason type.

### Changes Required

**File**: `frontend/src/types/arena.ts:17`

Replace:
```typescript
export type ExitReason = 'stop_hit' | 'simulation_end' | 'insufficient_capital';
```

With:
```typescript
export type ExitReason = 'stop_hit' | 'simulation_end' | 'insufficient_capital' | 'take_profit' | 'max_hold';
```

### Success Criteria

#### Automated:
- [x] TypeScript compiles: `cd frontend && npx tsc --noEmit`

#### Manual:
- [ ] View a simulation with TP or max hold exits -- exit reason displays correctly instead of broken/undefined

---

## Testing Strategy

### Unit Tests (Phase 1)

| Test | What It Verifies |
|------|-----------------|
| `test_fixed_take_profit_triggers_on_intraday_high` | High reaches target but close does not -- still triggers, exits at target price |
| `test_fixed_take_profit_gap_up_exits_at_open` | Open gaps past target -- exits at open price (can't fill below open) |
| `test_fixed_take_profit_no_trigger_when_high_below_target` | High below target -- stays open (negative test) |
| `test_atr_take_profit_triggers_on_intraday_high` | ATR-multiple path also uses high-based trigger, exits at target |

### Updated Existing Tests

| Test | Change |
|------|--------|
| `test_fixed_take_profit_triggers_when_return_meets_target` | Update exit_price assertion from close to min(target, open) |
| `test_take_profit_exit_updates_simulation_trade_count` | Update exit_price and realized_pnl assertions |

### Regression

```bash
./scripts/dc.sh exec backend-dev pytest tests/unit/services/arena/test_simulation_engine.py -v
./scripts/dc.sh exec backend-dev pytest tests/unit/services/arena/ -v
```

## References

- Architectural plan: `thoughts/shared/plans/2026-03-30-atr-exit-strategies-architecture.md` (lines 183-191)
- Ticket: #49
- Parent ticket: #47
