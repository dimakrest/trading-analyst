# Historical Bounce Rate Filter

## Objective

Add a per-symbol "bounce rate" metric that measures how reliably each stock mean-reverts after pulling back to MA20. Use this to prefer stocks with a proven history of bouncing, and deprioritize stocks that tend to keep falling.

## Problem

The system generates ~20K BUY signals/year but only trades ~865 (4.3%). Current ranking uses agent score + ATR as tiebreaker, which treats all stocks equally. In reality, some stocks reliably bounce from MA20 while others just keep declining. We're wasting capacity on stocks with no historical tendency to mean-revert.

## What to Build

### Bounce Rate Metric

For each symbol, compute a historical bounce rate: of all the times this stock pulled back to MA20 in a bearish trend, what percentage of the time did it bounce back (e.g., recovered X% within N days)?

Key dimensions to define:
- What counts as a "pullback to MA20" (within what distance threshold?)
- What counts as a successful "bounce" (price recovery %, timeframe)
- How much history to use (rolling window vs all available)
- Minimum sample size before the metric is considered reliable

### Integration with Portfolio Selection

The bounce rate should influence which stocks get selected when the system has more BUY signals than capacity. Stocks with higher historical bounce rates should be preferred over stocks with no track record of reverting.

### No Look-Ahead Bias

The bounce rate for any given day must only use data available up to that day. Cannot use future price data to determine if a stock "bounces well."

## Success Criteria

- Stocks selected for trading have measurably higher average bounce rates than rejected stocks
- Overall simulation win rate improves vs baseline (sim #374: 40% WR, +57.1% return)
- No degradation in total number of trades (still ~780+/year)
- No look-ahead bias — metric is computed from trailing data only

## Context

- See `thoughts/shared/research/2026-02-24-optimization-log.md` — Signal Quality Improvement Brainstorm section
- Baseline sim #374: 865 trades, 40% WR, +57.1% return, $10K capital
- 1,865 score-90+ signals rejected per year due to capacity constraints
- Current portfolio selector: `score_sector_low_atr` in `backend/app/services/arena/portfolio_selector.py`
