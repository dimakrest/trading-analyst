# Stock Price Alerts

## Objective

Add a stock monitoring system where users can configure price alerts based on technical analysis levels — specifically Fibonacci retracement levels and Moving Average touches. Alerts are delivered as browser Web Notifications so users don't need to keep the app in focus.

## What to Build

### Stock Monitoring Dashboard

A new page/tab ("Alerts" or "Monitor") — the main hub for all monitored stocks.

**Dashboard table — one row per alert** (a stock with both a Fibonacci alert and an MA alert appears as two separate rows):

| Column | Description |
|--------|-------------|
| Symbol | Stock ticker |
| Alert Type | Fibonacci Retracement or Moving Average (MA50, MA200, etc.) |
| Price | Current price |
| Status | Phase badge — different per alert type (see below) |
| Details | Alert-type-specific info (see below) |
| Last Alert | Most recent triggered alert with timestamp |

**Details column by alert type:**
- **Fibonacci**: Swing range ("$110 → $140"), retracement depth ("38%"), next level ("50% @ $125")
- **Moving Average**: MA value ("MA200 @ $125.50"), distance ("2.3% above")

**Fibonacci status badges:**

| Status | Meaning | Color |
|--------|---------|-------|
| Rallying | Price making new highs, no confirmed swing high yet | Green |
| Pullback started | Swing high confirmed, price pulling back but above 23.6% | Yellow |
| Retracing | Price between 23.6% and 78.6% Fibonacci levels | Orange |
| At level | Price within tolerance of a Fibonacci level (actionable!) | Red/pulsing |
| Invalidated | Price broke below swing low (uptrend) or above swing high (downtrend) — trend broken | Gray |
| No structure | No valid swing structure detected yet | Dim/muted |
| Bouncing | Price touched a level and is moving back toward the trend | Blue |

**Moving Average status badges:**

| Status | Meaning | Color |
|--------|---------|-------|
| Above MA | Price is above the moving average | Green |
| Approaching | Price is within 2% of the MA but outside tolerance band | Yellow |
| At MA | Price within tolerance band of the MA (actionable!) | Red/pulsing |
| Below MA | Price is below the moving average | Orange |

**Additional dashboard features:**
- **Add stocks to watch** — search and select symbols
- **Configure alert rules per stock** — each stock can have multiple alert rules
- **View alert history** — log of triggered alerts with timestamps
- **Sort/filter** by status — e.g., show only stocks that are currently retracing

### Stock Detail View (Click-through from Dashboard)

When the user clicks a stock row in the dashboard, they see a detail view with:

**Price chart with Fibonacci overlay:**
- Candlestick chart showing recent price action
- Swing low and swing high marked with horizontal lines and labels
- Fibonacci retracement levels drawn as horizontal lines between swing low and swing high, each labeled with the level % and price (e.g., "50% — $125.00")
- Triggered levels highlighted differently (e.g., solid line vs dashed for pending)
- Current price position clearly visible relative to the levels
- If the stock has a Moving Average alert, overlay the MA lines on the same chart

**Alert info panel (sidebar or below chart):**
- Current status badge (same as dashboard)
- Swing range: "$110.00 → $140.00 (27.3% move)"
- Current retracement: "38.2% ($128.54)" with how far from next level
- List of configured alert levels with status: pending / triggered (with timestamp) / invalidated
- Alert history for this symbol — past triggers with timestamps and prices

**Navigation:**
- Back to dashboard
- Quick actions: pause alert, edit levels, delete

### Alert Type 1: Fibonacci Retracement

Fully automatic — user adds a symbol, system continuously detects swing structures and alerts when price retraces to Fibonacci levels. No manual chart drawing or anchor selection needed.

**User interaction:**
1. User adds a symbol (e.g., NVDA) and selects "Fibonacci Retracement" alert type
2. User picks which levels to alert on (default: 38.2%, 50%, 61.8%) — that's it
3. System handles everything: swing detection, level calculation, monitoring, re-anchoring
4. User receives notifications like: **"NVDA hit 50% Fibonacci retracement at $125.30 (swing: $110→$140)"**

**What the system does automatically:**
1. Detects swing highs and swing lows from daily price data
2. Identifies the most recent valid swing structure (minimum 10% move)
3. Calculates Fibonacci retracement levels from the swing range
4. Monitors current price against selected levels
5. **Auto-invalidates** if price breaks beyond the swing origin (below swing low for uptrend, above swing high for downtrend) — notifies user
6. **Auto-re-anchors** when a new swing extreme forms — recalculates all levels and continues monitoring

**Supports both directions:**
- **Uptrend retracement** (pullback): stock rallies from $110 to $140, then pulls back. Fibonacci levels are support zones where price may bounce. Invalidates if price breaks below swing low ($110).
- **Downtrend retracement** (bounce): stock drops from $140 to $110, then bounces up. Fibonacci levels are resistance zones where price may reverse back down. Invalidates if price breaks above swing high ($140).

The system detects the direction automatically based on the swing structure (which came first — the high or the low).

**Standard Fibonacci levels:**

| Level | Significance |
|-------|-------------|
| 23.6% | Minor — very shallow pullback, strong trend |
| 38.2% | Major — trend continuation signal |
| 50.0% | Major — equilibrium zone (not true Fibonacci but universally used) |
| 61.8% | Most important — "golden ratio" reversal zone |
| 78.6% | Deep — last chance before trend reversal |

**User configuration (minimal — sensible defaults for everything):**
- Which Fibonacci levels to alert on (default: 38.2%, 50%, 61.8%)
- Tolerance band (default: ±0.5%) — advanced setting, collapsed by default

**Alert lifecycle per level:**
- Each selected level triggers **once** per swing structure — after firing, that level is marked as triggered
- If all selected levels have triggered or the setup invalidates, the system watches for the next swing structure
- The alert stays active indefinitely until the user deletes it — it keeps finding new swing structures and alerting on retracements

**Status transitions:**

```
                    ┌─────────────────────────────────┐
                    │                                 │
                    ▼                                 │
  ┌──────────────────────┐    swing high confirmed   │
  │    no_structure       │ ──────────────────────►   │
  │  (no valid swing      │                           │
  │   detected yet)       │   ┌────────────────┐      │
  └──────────────────────┘   │    rallying     │      │
              ▲              │  (price making   │      │
              │              │   new highs)     │      │
              │              └───────┬──────────┘      │
              │                      │                 │
              │         swing high confirmed           │
              │         (N candles passed)              │
              │                      │                 │
              │                      ▼                 │
              │         ┌────────────────────┐         │
              │         │ pullback_started   │         │
              │         │ (price < swing_high│         │
              │         │  but above 23.6%)  │         │
              │         └───────┬────────────┘         │
              │                 │                      │
              │     price crosses 23.6% level          │
              │                 │                      │
              │                 ▼                      │
              │         ┌────────────────────┐         │
              │         │    retracing       │◄────┐   │
              │         │ (between 23.6%     │     │   │
              │         │  and 78.6%)        │     │   │
              │         └──┬─────────────┬───┘     │   │
              │            │             │         │   │
              │   price within    price moves      │   │
              │   tolerance of    away from         │   │
              │   a fib level     the level         │   │
              │            │             │         │   │
              │            ▼             │         │   │
              │   ┌────────────────┐     │         │   │
              │   │   at_level     │─────┘         │   │
              │   │ (actionable!   │               │   │
              │   │  fires alert)  │               │   │
              │   └────────────────┘               │   │
              │                                    │   │
              │   price bounces back up            │   │
              │            │                       │   │
              │            ▼                       │   │
              │   ┌────────────────┐               │   │
              │   │   bouncing     │───────────────┘   │
              │   │ (moving back   │  price drops      │
              │   │  up from level)│  again             │
              │   └────────────────┘                   │
              │                                        │
              │   price breaks below swing low         │
              │            │                           │
              │            ▼                           │
              │   ┌────────────────┐                   │
              └───│  invalidated   │───────────────────┘
                  │ (trend broken, │  system finds
                  │  watch for new │  new structure
                  │  structure)    │
                  └────────────────┘
```

**Transition rules** (same logic applies to both uptrend and downtrend, just mirrored):
- `no_structure` → `rallying`: valid swing structure found, price trending
- `rallying` → `pullback_started`: swing extreme confirmed, price starts retracing
- `pullback_started` → `retracing`: price crosses 23.6% retracement level
- `retracing` → `at_level`: price enters tolerance band of a configured Fibonacci level — **fires alert**
- `at_level` → `bouncing`: price moves back toward the trend direction
- `at_level` → `retracing`: price moves deeper into retracement toward next level
- `bouncing` → `retracing`: price reverses again toward deeper retracement
- ANY → `invalidated`: price breaks beyond swing origin (below swing low for uptrend, above swing high for downtrend) — **fires alert**
- `invalidated` → `no_structure`: system starts looking for new swing structure
- ANY → `rallying`: new swing extreme surpasses previous one (re-anchor)

**When alerts fire:**
- `retracing` → `at_level`: "NVDA hit 38.2% Fibonacci at $128.50 (swing: $110→$140)"
- ANY → `invalidated`: "NVDA broke below swing low $110 — Fibonacci setup invalidated"
- Each level fires **once** per swing structure (no spam from price oscillating around a level)

### Alert Type 2: Moving Average Touch

Alert when price reaches a specific moving average level.

**Supported MAs:**
- MA20 (20-day simple moving average)
- MA50
- MA150
- MA200

**User configuration:**
- Select which MAs to alert on
- Direction: alert on touch from above (pullback to support) or from below (rally to resistance), or both
- Tolerance band: how close price must be to the MA (default: ±0.5%)

**Alert condition:**
- Current price enters the tolerance band around the selected MA value
- Optional: only alert if MA is trending in a specific direction (rising/falling)

**Status lifecycle:**
- `above_ma`: price is above the MA — no action
- `approaching`: price is within 2% of the MA but outside tolerance band — heads up
- `at_ma`: price within tolerance band — **fires alert**
- `below_ma`: price is below the MA — no action

Each MA creates a separate alert row on the dashboard (e.g., NVDA MA50 and NVDA MA200 are two rows).

### Alert Delivery: Web Notifications

Use the browser Notifications API for delivery.

**Behavior:**
- On first alert configuration, request notification permission from the user
- Show notification with: symbol, alert type, current price, target level
- Clicking the notification opens the app to the stock's detail view
- In-app toast notification as fallback
- Alert history is persisted and viewable

### Backend: Alert Monitoring Service

A background service that periodically checks all active alerts, computes their current state (including the status badges shown on the dashboard), and fires notifications when conditions are met. The frontend is a pure renderer — it reads pre-computed state from the API.

## Success Criteria

**Dashboard:**
- [ ] Dashboard shows one row per alert (not per stock)
- [ ] Fibonacci alerts have their own status badges (rallying, retracing, at level, etc.)
- [ ] MA alerts have their own status badges (above MA, approaching, at MA, below MA)
- [ ] Dashboard is sortable/filterable by status
- [ ] Fibonacci rows show swing range, retracement depth, and next level
- [ ] MA rows show MA value and distance from price

**Stock Detail View:**
- [ ] Clicking a stock opens a detail view with candlestick chart
- [ ] Fibonacci retracement levels are drawn on the chart as horizontal lines with labels
- [ ] Swing high and swing low are clearly marked on the chart
- [ ] Triggered vs pending levels are visually distinct
- [ ] MA lines are overlaid when MA alerts are configured
- [ ] Alert info panel shows current state and history

**Fibonacci Alerts:**
- [ ] User can enable Fibonacci retracement alerts by just picking a symbol and levels
- [ ] System automatically detects swing structures without user input
- [ ] Works for both uptrend retracements (pullbacks) and downtrend retracements (bounces)
- [ ] System correctly detects swing highs/lows and calculates Fibonacci levels
- [ ] Fibonacci alerts auto-invalidate when price breaks beyond swing origin
- [ ] Fibonacci levels auto-re-anchor when new swing extremes are confirmed
- [ ] Fibonacci alerts keep finding new swing structures indefinitely until deleted
- [ ] Each Fibonacci level triggers once per swing structure (no spam)

**Moving Average Alerts:**
- [ ] User can configure Moving Average touch alerts (MA20/50/150/200)
- [ ] System correctly calculates moving averages and detects price proximity
- [ ] MA alerts show status (above MA, approaching, at MA, below MA)
- [ ] Each MA is a separate alert row on the dashboard

**Notifications & History:**
- [ ] Alerts fire as browser Web Notifications when conditions are met
- [ ] In-app toast fallback works when notification permission is denied
- [ ] Alert history is persisted and viewable (global and per-stock)
- [ ] Alerts can be paused, edited, and deleted

**Backend:**
- [ ] Backend monitoring service runs reliably on configured interval
- [ ] Backend computes and persists state each cycle
- [ ] All alert logic has comprehensive test coverage
