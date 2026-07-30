# Portfolio Builder Optimization Plan

## Architecture Overview

The current system has a clean separation: **signal generation** (Live20Evaluator, read-only) produces criteria and scores, the **agent** (Live20ArenaAgent) converts those into BUY/HOLD/NO_SIGNAL decisions, the **portfolio selector** ranks and filters qualifying signals, and the **simulation engine** manages position lifecycle with fixed trailing stops and fixed position sizing.

All changes target the portfolio construction layer: selection ranking, position sizing, stop management, exit rules, and regime awareness. Signal generation and agent weights remain locked (25/25/25/25). Minimum buy score = 75.

---

## Layer 1: Enriched Signal Ranking (Tiebreaker Cascade)

**What it does**: When multiple stocks have the same score (e.g., three stocks all at 75), the current system either preserves arbitrary order (FIFO) or uses ATR as the sole tiebreaker. This layer adds a multi-factor tiebreaker cascade using the rich data that the evaluator already computes but the agent discards at `live20_agent.py:161` (`criteria, _, _, _ = ...`).

**Algorithm**:
```python
# In AgentDecision, add optional metadata dict
@dataclass
class AgentDecision:
    symbol: str
    action: str
    score: int | None = None
    reasoning: str | None = None
    metadata: dict | None = None  # NEW: carries enriched signal data

# In Live20ArenaAgent.evaluate(), capture discarded data:
criteria, volume_signal, momentum_analysis, candle_explanation = self._evaluator.evaluate_criteria(...)

# Populate metadata on BUY decisions:
metadata = {
    "cci_value": momentum_analysis.value if isinstance(momentum_analysis, CCIAnalysis) else None,
    "cci_direction": momentum_analysis.direction.value if isinstance(momentum_analysis, CCIAnalysis) else None,
    "ma_distance_pct": ma_analysis.distance_pct,
    "rvol": volume_signal.rvol,
    "candle_duration": multi_day_result.duration.value,  # "1-day", "2-day", "3-day"
    "candle_pattern": multi_day_result.pattern_name,
}

# New selector: EnrichedScoreSelector
class EnrichedScoreSelector(PortfolioSelector):
    def rank(self, signals: list[QualifyingSignal]) -> list[QualifyingSignal]:
        return sorted(signals, key=lambda s: self._rank_key(s))

    def _rank_key(self, s: QualifyingSignal) -> tuple:
        m = s.metadata or {}
        return (
            -s.score,                                           # 1. Higher score first
            -self._candle_quality_score(m),                     # 2. Multi-day candle > single
            -(abs(m.get("cci_value", 0)) if m.get("cci_value") else 0),  # 3. Deeper oversold CCI
            -(abs(m.get("ma_distance_pct", 0))),               # 4. Further from MA20
            -(m.get("rvol", 1.0)),                              # 5. Higher volume conviction
            s.atr_pct if s.atr_pct is not None else float("inf"),  # 6. Lower ATR (calmer)
        )

    def _candle_quality_score(self, m: dict) -> int:
        duration = m.get("candle_duration", "1-day")
        return {"3-day": 3, "2-day": 2, "1-day": 1}.get(duration, 0)
```

**Tiebreaker cascade priority**:
1. **Score** (primary, already exists)
2. **Candle quality** -- 3-day patterns (Morning Star, Three Inside Up) score 3, 2-day score 2, 1-day score 1
3. **CCI depth** -- CCI at -180 is more oversold than -110; deeper oversold = more mean-reversion potential
4. **MA20 distance** -- Price at -12% from MA20 is more stretched than -6%; larger snap-back potential
5. **RVOL** -- Higher volume ratio = more conviction behind the reversal signal
6. **ATR** -- Lower ATR as final tiebreaker for calmer stocks

**Why it improves P&L**: Stocks with identical scores are not equal. A stock with a 3-day Morning Star, CCI at -180, and 3x volume has far more reversal conviction than one with a 1-day Doji, CCI at -105, and 1.1x volume.

**Files to modify**:
- `backend/app/services/arena/agent_protocol.py:14` -- add `metadata` field to `AgentDecision`
- `backend/app/services/arena/agents/live20_agent.py:161` -- capture and pass enriched data
- `backend/app/services/portfolio_selector.py:28` -- add `metadata` to `QualifyingSignal`, add `EnrichedScoreSelector`
- `backend/app/services/arena/simulation_engine.py:405-413` -- pass `decision.metadata` to `QualifyingSignal`

---

## Layer 2: Market Regime Filter

**What it does**: Fetches SPY daily close prices, applies the existing `detect_trend()` function to classify the market as BULL, BEAR, CAUTION, or NEUTRAL. Adjusts max open positions by regime.

**Algorithm**:
```python
def detect_market_regime(spy_closes: list[float], current_date: date) -> str:
    # Filter to bars up to current_date (no look-ahead)

    # Short-term trend (20-day)
    short_trend = detect_trend(spy_closes, period=20, threshold_pct=2.0)

    # Medium-term trend (50-day)
    medium_trend = detect_trend(spy_closes, period=50, threshold_pct=3.0)

    if short_trend == BULLISH and medium_trend == BULLISH:
        return "BULL"
    elif short_trend == BEARISH and medium_trend == BEARISH:
        return "BEAR"
    elif short_trend == BEARISH or medium_trend == BEARISH:
        return "CAUTION"
    else:
        return "NEUTRAL"

# Regime adjustments:
REGIME_CONFIG = {
    "BULL":    {"max_positions_pct": 1.0, "position_size_mult": 1.0},
    "NEUTRAL": {"max_positions_pct": 0.8, "position_size_mult": 1.0},
    "CAUTION": {"max_positions_pct": 0.5, "position_size_mult": 0.75},
    "BEAR":    {"max_positions_pct": 0.3, "position_size_mult": 0.5},
}

# In step_day, before portfolio selection:
regime = detect_market_regime(spy_closes_up_to_today, current_date)
base_max = simulation.agent_config.get("max_open_positions", 10)
adjusted_max = max(1, int(base_max * regime_config["max_positions_pct"]))
```

**No look-ahead guarantee**: SPY data filtered to `<= current_date` before calling `detect_trend()`.

**Why it improves P&L**: Mean reversion strategies suffer in persistent bear markets where "oversold" keeps getting more oversold. Reducing exposure preserves capital.

**Files to modify**:
- `backend/app/services/arena/simulation_engine.py` -- load SPY data at init, compute regime in `step_day()`
- New file: `backend/app/services/arena/market_regime.py`

---

## Layer 3: Dynamic Position Sizing

**What it does**: Sizes positions based on conviction (score) and volatility (ATR%). Higher score and lower ATR = larger position.

**Algorithm**:
```python
def calculate_position_size(
    base_size: Decimal, score: int, atr_pct: float | None,
    regime: str, config: dict,
) -> Decimal:
    # Score multiplier: 75->0.75x, 100->1.5x (linear)
    min_score = config.get("min_buy_score", 75)
    score_mult = 0.75 + (score - min_score) / (100 - min_score) * 0.75
    score_mult = max(0.75, min(1.5, score_mult))

    # ATR normalization: target 3% ATR, inverse relationship
    target_atr_pct = config.get("target_atr_pct", 3.0)
    if atr_pct and atr_pct > 0:
        atr_mult = target_atr_pct / atr_pct
        atr_mult = max(0.5, min(2.0, atr_mult))
    else:
        atr_mult = 1.0

    # Regime multiplier from Layer 2
    regime_mult = REGIME_CONFIG.get(regime, {}).get("position_size_mult", 1.0)

    final_size = base_size * score_mult * atr_mult * regime_mult
    # Clamp to [0.5x, 2.0x] of base
    return max(base_size * 0.5, min(base_size * 2.0, final_size))
```

**Why it improves P&L**: Concentrates capital on highest-conviction, lowest-risk signals. ATR normalization ensures each position risks roughly the same dollar amount.

**Files to modify**:
- `backend/app/services/arena/simulation_engine.py:310-312` -- replace fixed sizing
- New module: `backend/app/services/arena/position_sizing.py`

---

## Layer 4: ATR-Based Trailing Stops

**What it does**: Replaces fixed 5% trailing stop with N x ATR%. Volatile stocks get wider stops, calm stocks get tighter stops.

**Algorithm**:
```python
class AtrTrailingStop:
    def __init__(self, atr_multiplier: float = 2.0):
        self.atr_multiplier = atr_multiplier

    def calculate_initial_stop(self, entry_price: Decimal, atr_pct: float) -> tuple[Decimal, Decimal]:
        trail_pct = self.atr_multiplier * atr_pct
        trail_pct = max(2.0, min(10.0, trail_pct))  # Clamp

        multiplier = Decimal("1") - Decimal(str(trail_pct / 100))
        highest = entry_price
        stop = (highest * multiplier).quantize(Decimal("0.0001"))
        return highest, stop

    # update() same as FixedPercentTrailingStop -- trail only moves up
```

**Why it improves P&L**: Fixed 5% too tight for volatile stocks (premature exits), too loose for calm stocks (give back profit). ATR-adaptive stops match actual volatility.

**Files to modify**:
- `backend/app/services/arena/trailing_stop.py` -- add `AtrTrailingStop`
- `backend/app/services/arena/simulation_engine.py:230-231, 337-339` -- select stop type, use per-position ATR stop

---

## Layer 5: Take Profit Rules

**What it does**: Exits at target profit (ATR multiple or fixed %). Mean reversion trades have natural profit targets.

**Algorithm**:
```python
def check_take_profit(position, current_close, atr_pct, config) -> bool:
    unrealized_return_pct = (current_close - position.entry_price) / position.entry_price * 100

    # Fixed percentage target
    fixed_target = config.get("take_profit_pct")
    if fixed_target and unrealized_return_pct >= fixed_target:
        return True

    # ATR multiple target (e.g., 3x ATR)
    atr_target_mult = config.get("take_profit_atr_mult")
    if atr_target_mult and atr_pct:
        if unrealized_return_pct >= atr_target_mult * atr_pct:
            return True

    return False

# Add ExitReason.TAKE_PROFIT
```

**Why it improves P&L**: Without take profit, winners ride back down. Capturing the reversion move at 2-3x ATR locks in gains.

**Files to modify**:
- `backend/app/models/arena.py:49` -- add `ExitReason.TAKE_PROFIT`
- `backend/app/services/arena/simulation_engine.py` -- add take profit check in position update loop

---

## Layer 6: Max Holding Period

**What it does**: Exits positions held for N trading days. Frees capital for fresh signals.

**Algorithm**:
```python
def check_max_hold(position, current_date, trading_days, max_hold_days) -> bool:
    entry_idx = trading_days.index(position.entry_date)
    current_idx = trading_days.index(current_date)
    return (current_idx - entry_idx) >= max_hold_days

# Add ExitReason.MAX_HOLD
```

**Why it improves P&L**: Stagnant positions have opportunity cost. Mean reversion should work within 5-15 days or the thesis is invalidated.

**Files to modify**:
- `backend/app/models/arena.py:49` -- add `ExitReason.MAX_HOLD`
- `backend/app/services/arena/simulation_engine.py` -- add holding period check

**Suggested default**: 15 trading days (3 weeks).

---

## Layer 7: Cash/Exposure Management

**What it does**: Controls total portfolio exposure by regime. Prevents 100% deployment in uncertain conditions.

**Algorithm**:
```python
EXPOSURE_LIMITS = {
    "BULL":    0.90,
    "NEUTRAL": 0.75,
    "CAUTION": 0.50,
    "BEAR":    0.30,
}

def calculate_available_capital(cash, positions_value, total_equity, regime):
    max_deployed = total_equity * EXPOSURE_LIMITS[regime]
    available = max_deployed - positions_value
    return max(0, min(cash, available))
```

**Why it improves P&L**: Holding cash in bear markets preserves capital. Compounds with Layer 2 for layered defense.

**Files to modify**:
- `backend/app/services/arena/simulation_engine.py:432-447` -- exposure check before PENDING creation

---

## Implementation Order (Fastest P&L Impact First)

### Phase 1 -- Foundation
1. **Layer 1: Enriched Signal Ranking** -- Lowest risk, highest certainty. Purely better selection.

### Phase 2 -- Exit Management (biggest P&L levers)
2. **Layer 4: ATR-Based Trailing Stops** -- Single biggest P&L lever. Stops are where most money is lost/saved.
3. **Layer 5: Take Profit Rules** -- Captures mean-reversion profits before they evaporate.
4. **Layer 6: Max Holding Period** -- Frees stuck capital. Simple.

### Phase 3 -- Regime Awareness
5. **Layer 2: Market Regime Filter** -- Requires SPY data loading.
6. **Layer 7: Cash/Exposure Management** -- Builds on Layer 2.

### Phase 4 -- Sizing (fine-tuning)
7. **Layer 3: Dynamic Position Sizing** -- Most complex, most parameter-sensitive. Do last.

---

## Risk Considerations

1. **Overfitting to 2025**: Every parameter creates overfitting risk. Mitigation: use 2025 H1 for calibration, H2 for validation, 2026 Q1 as holdout.
2. **ATR stops too wide in bear markets**: Mitigation: `atr_stop_max_pct: 10.0` ceiling.
3. **Regime detection lag**: Sudden crash not detected for 20+ days. Mitigation: dual timeframe (20+50 day).
4. **Take profit too tight**: May cut winners short. Mitigation: start at 3x ATR, tune down if needed.
5. **Max hold forcing bad exits**: Mitigation: only exit if position is at a loss or flat; let winners run.
6. **Dynamic sizing concentrating risk**: Mitigation: 2x cap on position size multiplier.
7. **SPY data unavailable**: Regime defaults to NEUTRAL (current behavior). Safe degradation.

---

## Config Parameters Summary

| Parameter | Type | Default | Layer |
|---|---|---|---|
| `min_buy_score` | int | 75 | -- |
| `portfolio_strategy` | str | "enriched_score" | 1 |
| `regime_enabled` | bool | false | 2 |
| `dynamic_sizing_enabled` | bool | false | 3 |
| `target_atr_pct` | float | 3.0 | 3 |
| `max_position_mult` | float | 2.0 | 3 |
| `min_position_mult` | float | 0.5 | 3 |
| `stop_type` | str | "fixed" | 4 |
| `trailing_stop_pct` | float | 5.0 | 4 |
| `atr_stop_multiplier` | float | 2.0 | 4 |
| `atr_stop_min_pct` | float | 2.0 | 4 |
| `atr_stop_max_pct` | float | 10.0 | 4 |
| `take_profit_pct` | float | None | 5 |
| `take_profit_atr_mult` | float | 3.0 | 5 |
| `max_hold_days` | int | None | 6 |
| `exposure_management_enabled` | bool | false | 7 |
| `max_exposure_bull` | float | 0.90 | 7 |
| `max_exposure_bear` | float | 0.30 | 7 |

---

## Validation Approach

1. **Baseline**: Run current system on 2025 full year, record metrics.
2. **Per-layer A/B**: Enable one layer at a time vs baseline.
3. **Combined**: Enable in recommended order, record metrics at each step.
4. **Holdout**: Final config on Jan 1 - Mar 1, 2026 (holdout period).
5. **Key metrics**: Total return %, max drawdown %, Sharpe ratio, profit factor, win rate, avg hold days, trade count.
