# Phase 3: Risk-Based Position Sizing (#50)

Parent: #47 -- ATR-Based Exit Strategies
Depends on: #48 (ATR trailing stop -- COMPLETE)

## Status

Partially implemented. Fixed-pct sizing (`position_size_pct`) exists. Missing: risk-based volatility-adjusted sizing and consecutive win scaling.

## What

Replace fixed-dollar position sizing with risk-based sizing. Instead of "buy $1,000 of each stock," size positions so that each trade risks the same percentage of portfolio equity, with the stop distance (ATR-based) determining how many shares to buy.

## Why

Fixed-dollar sizing ignores volatility. A $1,000 position in a volatile stock risks much more than in a calm one. Risk-based sizing ensures consistent risk per trade -- volatile stocks get fewer shares, stable stocks get more.

---

## Backend Changes

### 3a. Risk-Based Sizing Formula

Location: `simulation_engine.py`, position open block (currently around the `effective_position_size` calculation).

New sizing mode (`sizing_mode="risk_based"`):
```python
# stop_distance_per_share = atr_stop_multiplier * atr_pct / 100 * entry_price
# risk_amount = current_equity * risk_pct / 100
# shares = risk_amount / stop_distance_per_share
```

This requires ATR at position open time -- already available since ATR trailing stop init happens in the same block.

**Zero ATR guard**: When `atr_pct` is `None` or < 0.01, fall back to fixed `position_size`:
```python
if symbol_atr_pct is None or symbol_atr_pct < 0.01:
    effective_position_size = simulation.position_size
else:
    stop_distance_per_share = atr_stop_multiplier * symbol_atr_pct / 100 * entry_price
    risk_amount = current_equity * Decimal(str(effective_risk / 100))
    calculated_shares = int(risk_amount / stop_distance_per_share)
```

**`sizing_mode` + `stop_type` interaction**: Risk-based sizing only makes sense with ATR stops. Reject at schema validation:
```python
@model_validator(mode="after")
def validate_sizing_stop_combination(self):
    if getattr(self, "sizing_mode", "fixed") == "risk_based" and getattr(self, "stop_type", "fixed") != "atr":
        raise ValueError("sizing_mode='risk_based' requires stop_type='atr'")
    return self
```

**Sizing mode precedence**:
- `"fixed"` -- uses `simulation.position_size` (ignores `position_size_pct`)
- `"fixed_pct"` -- uses `position_size_pct` percentage of equity
- `"risk_based"` -- uses risk formula above

Legacy fallback (no `sizing_mode` in agent_config): check `position_size_pct` -- if set, use `"fixed_pct"`; otherwise `"fixed"`.

### 3b. Consecutive Win Streak Tracking

**Approach**: New column on `ArenaSimulation` model -- `consecutive_wins: int` (default 0). Updated whenever a position closes.

Location for win streak update -- after each position close in step_day():
```python
if realized_pnl > 0:
    simulation.consecutive_wins += 1
else:
    simulation.consecutive_wins = 0
```

Location for risk calculation -- position open block:
```python
base_risk = risk_per_trade_pct
streak_bonus = simulation.consecutive_wins * win_streak_bonus_pct
effective_risk = min(base_risk + streak_bonus, max_risk_pct)
```

### 3c. Extract `_close_position()` Helper (Refactoring)

The position close logic is duplicated in three blocks (stop hit, take profit, max hold). Extract a helper to consolidate win streak updates:

```python
def _close_position(
    self, position, simulation, exit_reason, exit_price, exit_date, cash,
) -> Decimal:
    realized_pnl = (exit_price - position.entry_price) * position.shares
    return_pct = (exit_price - position.entry_price) / position.entry_price * 100
    position.status = PositionStatus.CLOSED.value
    position.exit_date = exit_date
    position.exit_price = exit_price
    position.exit_reason = exit_reason.value
    position.realized_pnl = realized_pnl
    position.return_pct = return_pct
    simulation.total_trades += 1
    if realized_pnl > 0:
        simulation.winning_trades += 1
        simulation.consecutive_wins += 1
    else:
        simulation.consecutive_wins = 0
    return cash + position.shares * exit_price
```

### 3d. Per-Day ATR Memoization

With ATR stops + TP + risk sizing, `_calculate_symbol_atr_pct()` is called 3-4x per symbol per day. Add a local memoization dict at the top of `step_day()`:

```python
_day_atr_cache: dict[str, float | None] = {}
def _get_atr_for_day(symbol: str) -> float | None:
    if symbol not in _day_atr_cache:
        _day_atr_cache[symbol] = self._calculate_symbol_atr_pct(
            simulation_id, symbol, current_date
        )
    return _day_atr_cache[symbol]
```

### 3e. Schema Changes

New fields on `CreateSimulationRequest` AND `CreateComparisonRequest`:
- `sizing_mode: str = "fixed"` (validates: "fixed", "fixed_pct", "risk_based")
- `risk_per_trade_pct: float = 2.5` (gt=0, le=10)
- `win_streak_bonus_pct: float = 0.3` (ge=0, le=2)
- `max_risk_pct: float = 4.0` (gt=0, le=10)

### 3f. API Wiring (5-Step Process)

1. Add fields to `CreateSimulationRequest` (schemas/arena.py)
2. Add same fields to `CreateComparisonRequest` (schemas/arena.py)
3. Wire into `agent_config` dict in `create_simulation()` and `create_comparison()` (api/v1/arena.py)
4. Extract from `agent_config` in `_build_simulation_response()` + add to `SimulationResponse`
5. Read from `simulation.agent_config` in `step_day()`

### 3g. DB Migration

Add `consecutive_wins` integer column (default 0) to `arena_simulations`:
```sql
ALTER TABLE arena_simulations ADD COLUMN consecutive_wins INTEGER NOT NULL DEFAULT 0;
```

Known limitation: in-progress simulations at migration time start with 0. Acceptable -- win streak is a marginal sizing adjustment.

---

## Frontend Changes

The form is split into 3 tabs: **Setup** (symbols, dates, capital), **Agent** (agent type, scoring), **Portfolio** (strategy, constraints, tuning).

1. **TypeScript types**: Add `sizing_mode`, `risk_per_trade_pct`, `win_streak_bonus_pct`, `max_risk_pct` to `CreateSimulationRequest`, `Simulation`
2. **ArenaSetupForm -- Setup tab**: Add a "Stop Type" selector (fixed/ATR) and a "Sizing Mode" selector (fixed/pct/risk-based) alongside the existing Capital, Position Size, and Trailing Stop fields. When `sizing_mode="risk_based"` is selected, show risk parameters (risk per trade %, win streak bonus, max risk cap) and auto-set `stop_type="atr"`. Hide the fixed "Position Size ($)" field when risk-based is active since it's replaced by the formula.
3. **ArenaConfigPanel**: Display sizing config when non-default
4. **Replay hydration**: `initialValues.sizing_mode ?? "fixed"` for old simulations
5. **Note**: `stop_type` is currently backend-only (not exposed in the form). This phase must add it to the Setup tab so users can choose ATR stops, which is a prerequisite for risk-based sizing.

---

## Testing

| Test File | What to Test |
|-----------|-------------|
| test_simulation_engine.py | Risk-based sizing formula: shares = risk_amount / stop_distance |
| test_simulation_engine.py | Win streak increment on win, reset on loss |
| test_simulation_engine.py | Sizing cap: effective_risk never exceeds max_risk_pct |
| test_simulation_engine.py | Zero ATR fallback to fixed position_size |
| test_simulation_engine.py | sizing_mode precedence: explicit > legacy position_size_pct |
| test_simulation_engine.py | _close_position() helper produces same results as inline code |

## Backtest Validation

After implementation, run with aggressive config:
- `stop_type="atr"`, `atr_stop_multiplier=2.0`
- `take_profit_atr_mult=3.0`, `max_hold_days=4`
- `sizing_mode="risk_based"`, `risk_per_trade_pct=2.5`
- `max_open_positions=10`, `max_per_sector=3`

Compare against research: 2025 full year +41.5%, 155 trades, 10.3% max DD.

## Known Limitations

- **Win streak order-dependence**: When multiple positions close on the same day, `consecutive_wins` depends on symbol processing order. Deterministic but order is an implementation detail.
- **`consecutive_wins = 0` at migration time**: Running simulations get reset. Acceptable -- marginal adjustment.

## Success Criteria

- [x] Position sizes scale with portfolio equity (not fixed dollar amount)
- [x] Volatile stocks (high ATR) get smaller positions than calm stocks
- [x] Consecutive wins increase position sizes up to cap
- [x] A losing trade resets sizing back to base
- [x] Old fixed-dollar simulations still run correctly
- [x] Schema rejects `sizing_mode="risk_based"` with `stop_type="fixed"`
