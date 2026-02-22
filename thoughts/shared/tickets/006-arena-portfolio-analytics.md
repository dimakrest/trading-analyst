# Arena Portfolio Analytics & Transparency

## Objective

Improve the Arena's portfolio section with richer analytics and transparency so users can evaluate portfolio performance at a glance and make better-informed decisions.

## What to Build

### Performance Metrics

- **Win rate** — percentage of closed positions that were profitable
- **Average hold time** — mean duration positions are held (open → close)
- **Average win vs average loss** — compares typical winner size to typical loser size
- **Profit factor** — gross total wins / gross total losses
- **Sharpe ratio** — risk-adjusted return relative to volatility
- **Max drawdown** — largest peak-to-trough decline in portfolio value

### Portfolio Composition

- **Biggest winners** — top N closed positions by absolute and % return
- **Biggest losers** — bottom N closed positions by absolute and % return
- **Realized vs unrealized P&L** — split between closed gains and open position gains
- **Position concentration** — exposure by individual position as % of portfolio

### Sector Breakdown

- **Per-sector allocation** — current portfolio value distributed across sectors
- **Per-sector performance** — win rate and P&L grouped by sector

### Time-Series Visualization

- **Portfolio total size over time** — line/area graph of total portfolio value
- **Monthly/weekly P&L calendar** — heatmap showing returns by period
- **Trade frequency** — number of trades per week/month over time

### Benchmark Comparison

- **Portfolio vs benchmark** — overlay portfolio returns against SPY or QQQ on the time-series graph

## Success Criteria

- All metrics visible on the Arena portfolios page without leaving the UI
- Stats are accurate and reflect actual trade history
- Time-series graph updates as new trades close
- Sector breakdown handles symbols with unknown sector gracefully
- Benchmark comparison clearly distinguished from portfolio line
