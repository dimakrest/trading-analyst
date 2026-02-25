# Setup Simulation (Backtesting)

## Objective

Provide a way to define a batch of trading setups and simulate their execution over a historical period to evaluate P&L performance. This enables quick "what-if" testing of setup ideas against real price data.

## What to Build

### Setup Definition

Each setup consists of:

- **Symbol** — the ticker to trade
- **Entry price** — the price level that triggers a long entry
- **Stop loss day 1** — a fixed stop loss price used on the first day of the position
- **Stop loss day 1+** — a trailing stop loss (%) applied from day 2 onward
- **Setup start date** — the earliest date the setup becomes eligible for activation

A user can add multiple setups before running a simulation.

### Simulation Configuration

- **End date** — a single input that defines when the simulation stops
- **Position size** — fixed at $1,000 per position

### Simulation Rules

- The simulation advances **day by day** from each setup's start date through the end date
- A setup **activates** when the daily price reaches or exceeds the entry price
- Once activated, the position is held and evaluated daily:
  - **Day 1**: if price hits the day-1 stop loss, the position is closed at the stop loss price
  - **Day 2+**: the trailing stop loss applies — if price drops by the trailing stop % from the high since entry, the position is closed
- If a position is closed (stopped out or by end date), the same setup **can retrigger** — if price again crosses above the entry price on a subsequent day, a new position opens
- There is **no limit** on the number of concurrent positions (across different setups or retriggered entries on the same setup)
- Positions still open at the end date are closed at that day's closing price

### Results

For the overall simulation:

- **Total P&L** (absolute $ and %)
- **Number of trades** (total, wins, losses)
- **Win rate**
- **Average gain vs average loss**

Per setup:

- Number of times triggered
- P&L contribution
- List of individual trades (entry date, entry price, exit date, exit price, P&L)

## Success Criteria

- User can define multiple setups and run a simulation in a single action
- Simulation correctly identifies entry triggers, applies the two-tier stop loss logic, and handles retriggering
- Results clearly show overall and per-setup performance
- Position sizing is consistently $1,000 per trade
- All positions are resolved by the end date
