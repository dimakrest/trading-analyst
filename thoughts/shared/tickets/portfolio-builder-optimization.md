# Portfolio Builder Optimization

## Objective
Improve portfolio construction quality to achieve aggressive P&L targets through smarter selection, sizing, and risk management — without touching signal generation.

## Rules (Hard Constraints)
- Agent signal weights are LOCKED (25/25/25/25 for volume/candle/momentum/ma20_distance)
- Minimum buy score = 75 (raised from current 60)
- No look-ahead bias — all decisions use only data available at decision time
- No cheating — no future data leakage in any form
- Signal generation (Live20Evaluator) is off-limits for changes

## Goals (Backtest Targets)
- 2025 full year data: 100% P&L return
- Jan 1 - Mar 1, 2026: 20% P&L return

## Scope of Improvements (Portfolio Construction Only)
Ideas include but are not limited to:
- Smart position sizing (not just equal weight)
- Sector-aware allocation (correlation, concentration limits)
- Market regime detection (bull/bear/sideways — adjust exposure)
- Sector regime awareness (sector rotation, relative strength)
- Tiebreaking for same-score signals (use indicator depth: CCI value, candle quality, MA distance, RVOL)
- Stop loss optimization (trailing stop tuning, ATR-based stops)
- Take profit rules
- Cash management (when to be fully invested vs hold cash)
- Position limit optimization
- Entry timing refinement

## Current State
- Portfolio selector: `backend/app/services/portfolio_selector.py`
- Simulation engine: `backend/app/services/arena/simulation_engine.py`
- Signal evaluator (READ ONLY): `backend/app/services/live20_evaluator.py`
- Arena agent (READ ONLY weights): `backend/app/services/arena/agents/live20_agent.py`
- Indicators (READ ONLY): `backend/app/indicators/`
