# Arena Multi-Algorithm Comparison

## Objective

Allow a single Arena run to execute multiple portfolio management algorithms in parallel and present a side-by-side comparison view so users can evaluate which algorithm performs best on a given universe and time period.

## What to Build

### Multi-Algorithm Run

- A user can select **one or more portfolio management algorithms** when configuring an Arena run
- All selected algorithms simulate on the **same universe, time period, and capital**
- Each algorithm produces its own independent result set (positions, snapshots, metrics)

### Comparison View

A dedicated view that presents all algorithm results side-by-side. For each algorithm, display:

**Performance Summary**
- Total P&L (absolute and %)
- Max drawdown
- Sharpe ratio
- Profit factor
- Win rate

**Trade Statistics**
- Total number of trades
- Average hold time
- Average win vs average loss

**Benchmark Comparison**
- Portfolio return overlaid against SPX and QQQ
- All algorithms on the same chart for direct visual comparison

**Equity Curve Comparison**
- All algorithm equity curves on a single chart, normalized to % return
- Benchmark lines (SPX, QQQ) included for reference
- Each algorithm clearly distinguished by color or label

### Summary Ranking

- A sortable table with one row per algorithm and one column per metric
- Users can sort by any metric (e.g., best Sharpe, lowest drawdown, most trades)
- Highlights best and worst value in each column

## Success Criteria

- Running Arena with multiple algorithms does not require re-configuring the universe or time period multiple times
- Comparison view is accessible directly from the Arena run result
- All algorithms are compared on identical market conditions (same symbols, same dates, same starting capital)
- Equity curve chart shows all algorithms and benchmarks on the same axis, normalized to % return
- Summary table is sortable and clearly identifies best/worst per metric
- Individual algorithm drill-down remains available (existing per-algorithm detail view still works)
