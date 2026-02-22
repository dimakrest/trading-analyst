/**
 * UI Tests for Arena Portfolio Analytics Components
 *
 * These tests use page.route() to mock backend responses and validate
 * that the Arena simulation detail page renders all portfolio analytics
 * components correctly when given a completed simulation with all new fields.
 *
 * Components under test:
 * - ArenaResultsTable (11-metric grid: Return, Win Rate, Profit Factor, Sharpe Ratio,
 *                      Total Trades, Avg Hold Time, Avg Win, Avg Loss, Max DD,
 *                      Final Equity, Realized P&L)
 * - ArenaEquityChart (equity curve with SPY/QQQ benchmark toggles)
 * - ArenaPortfolioComposition (winners/losers/P&L/concentration)
 * - ArenaSectorBreakdown (sector allocation and performance)
 *
 * NOTE: Canvas content (lightweight-charts) is not accessible to Playwright
 * queries. Tests assert the chart container div is present, not canvas internals.
 *
 * Route: /arena/:id (maps to ArenaSimulationDetail component)
 * API calls: GET /api/v1/arena/simulations/:id
 */

import { test, expect } from '@playwright/test';

// ---------------------------------------------------------------------------
// Mock data — a fully completed simulation with all new analytics fields
// ---------------------------------------------------------------------------

const mockCompletedSimulation = {
  id: 1,
  name: 'Test Analytics Simulation',
  stock_list_id: null,
  stock_list_name: null,
  symbols: ['AAPL', 'MSFT', 'NVDA', 'GOOGL'],
  start_date: '2024-01-01',
  end_date: '2024-03-31',
  initial_capital: '100000.00',
  position_size: '5000.00',
  agent_type: 'live20',
  trailing_stop_pct: '5.0',
  min_buy_score: 60,
  scoring_algorithm: 'v2',
  portfolio_strategy: null,
  max_per_sector: null,
  max_open_positions: null,
  status: 'completed',
  current_day: 63,
  total_days: 63,
  final_equity: '112500.00',
  total_return_pct: '12.50',
  total_trades: 15,
  winning_trades: 9,
  max_drawdown_pct: '8.50',
  // New analytics fields added in the portfolio analytics implementation
  avg_hold_days: '8.20',
  avg_win_pnl: '950.00',
  avg_loss_pnl: '-420.00',
  profit_factor: '2.03',
  sharpe_ratio: '1.45',
  total_realized_pnl: '12500.00',
  created_at: '2024-01-01T00:00:00Z',
};

// Closed positions (for ArenaPortfolioComposition winners/losers and ArenaSectorBreakdown)
const mockClosedPositions = [
  {
    id: 1,
    symbol: 'AAPL',
    status: 'closed',
    signal_date: '2024-01-05',
    entry_date: '2024-01-08',
    entry_price: '185.00',
    shares: 27,
    highest_price: '198.00',
    current_stop: null,
    exit_date: '2024-01-22',
    exit_price: '196.50',
    exit_reason: 'stop_hit',
    realized_pnl: '310.50',
    return_pct: '6.22',
    agent_reasoning: null,
    agent_score: 75,
    sector: 'Technology',
  },
  {
    id: 2,
    symbol: 'MSFT',
    status: 'closed',
    signal_date: '2024-01-10',
    entry_date: '2024-01-12',
    entry_price: '375.00',
    shares: 13,
    highest_price: '405.00',
    current_stop: null,
    exit_date: '2024-02-05',
    exit_price: '402.00',
    exit_reason: 'stop_hit',
    realized_pnl: '351.00',
    return_pct: '7.20',
    agent_reasoning: null,
    agent_score: 80,
    sector: 'Technology',
  },
  {
    id: 3,
    symbol: 'NVDA',
    status: 'closed',
    signal_date: '2024-01-15',
    entry_date: '2024-01-17',
    entry_price: '520.00',
    shares: 9,
    highest_price: '610.00',
    current_stop: null,
    exit_date: '2024-02-20',
    exit_price: '595.00',
    exit_reason: 'stop_hit',
    realized_pnl: '675.00',
    return_pct: '14.42',
    agent_reasoning: null,
    agent_score: 88,
    sector: 'Technology',
  },
  {
    id: 4,
    symbol: 'GOOGL',
    status: 'closed',
    signal_date: '2024-02-01',
    entry_date: '2024-02-05',
    entry_price: '140.00',
    shares: 35,
    highest_price: '145.00',
    current_stop: null,
    exit_date: '2024-02-15',
    exit_price: '134.00',
    exit_reason: 'stop_hit',
    realized_pnl: '-210.00',
    return_pct: '-4.29',
    agent_reasoning: null,
    agent_score: 62,
    sector: 'Communication Services',
  },
];

/**
 * Build 25 daily snapshots — enough to trigger:
 * - ArenaEquityChart (needs >= 2 snapshots, isComplete must be true)
 * - ArenaMonthlyPnl (needs >= 20 snapshots)
 */
const buildMockSnapshots = () => {
  const snapshots = [];
  const startEquity = 100000;
  // Use a fixed sequence to avoid randomness making tests flaky
  const dailyChanges = [
    200, 150, -100, 300, -50, 400, -200, 100, 250, -80,
    350, -120, 180, 220, -90, 310, -60, 140, 260, -110,
    380, -40, 160, 290, 200,
  ];
  let equity = startEquity;

  for (let i = 0; i < 25; i++) {
    const date = new Date('2024-01-02');
    date.setDate(date.getDate() + i);
    const dateStr = date.toISOString().split('T')[0];
    const dailyPnl = dailyChanges[i];
    equity += dailyPnl;

    snapshots.push({
      id: i + 1,
      snapshot_date: dateStr,
      day_number: i + 1,
      cash: (equity * 0.6).toFixed(2),
      positions_value: (equity * 0.4).toFixed(2),
      total_equity: equity.toFixed(2),
      daily_pnl: dailyPnl.toFixed(2),
      daily_return_pct: ((dailyPnl / (equity - dailyPnl)) * 100).toFixed(4),
      cumulative_return_pct: (((equity - startEquity) / startEquity) * 100).toFixed(4),
      open_position_count: 2,
      decisions: {},
    });
  }
  return snapshots;
};

const mockSnapshots = buildMockSnapshots();

const mockSimulationDetail = {
  simulation: mockCompletedSimulation,
  positions: mockClosedPositions,
  snapshots: mockSnapshots,
};

// ---------------------------------------------------------------------------
// Helper: Set up all required route mocks before navigating
// ---------------------------------------------------------------------------

const setupMocks = async (page: import('@playwright/test').Page) => {
  // Mock the simulation detail endpoint: GET /api/v1/arena/simulations/1
  // The route /arena/1 in the app maps to ArenaSimulationDetail with id=1
  await page.route('**/api/v1/arena/simulations/1', async (route) => {
    if (route.request().method() === 'GET') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(mockSimulationDetail),
      });
    } else {
      await route.continue();
    }
  });

  // Mock benchmark requests (triggered when SPY/QQQ toggle is clicked)
  await page.route('**/api/v1/arena/simulations/1/benchmark**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify([
        { date: '2024-01-02', close: '470.50', cumulative_return_pct: '0.00' },
        { date: '2024-01-03', close: '472.00', cumulative_return_pct: '0.32' },
        { date: '2024-01-04', close: '469.00', cumulative_return_pct: '-0.32' },
      ]),
    });
  });
};

// ---------------------------------------------------------------------------
// Test suite: Page loads and overall structure
// ---------------------------------------------------------------------------

test.describe('Arena Analytics - Simulation Detail Page', () => {
  test.beforeEach(async ({ page }) => {
    await setupMocks(page);
    // Navigate to /arena/1 (the router pattern is /arena/:id)
    await page.goto('/arena/1');
    await page.waitForLoadState('networkidle');
  });

  test('page loads without JS errors', async ({ page }) => {
    const consoleErrors: string[] = [];

    // Attach error listener before setting up mocks and navigating
    page.on('console', (msg) => {
      if (msg.type() === 'error') {
        // Exclude React development-mode HTML nesting warnings — these are pre-existing
        // structural warnings in the codebase, not runtime application errors.
        const text = msg.text();
        if (text.includes('In HTML,') && text.includes('cannot be a descendant')) return;
        if (text.includes('cannot contain a nested')) return;
        consoleErrors.push(text);
      }
    });

    await setupMocks(page);
    await page.goto('/arena/1');
    await page.waitForLoadState('networkidle');

    expect(consoleErrors).toHaveLength(0);
  });

  test('metrics grid is visible with all 11 metric labels', async ({ page }) => {
    // Scope to the Results card to avoid strict-mode violations from labels
    // that also appear in table headers (e.g. "Return" appears in Portfolio Composition tables)
    const resultsCard = page.getByRole('heading', { name: 'Results' }).locator('../..');

    // Row 1: Key ratios — use .first() for labels shared with other sections
    await expect(page.getByText('Return').first()).toBeVisible();
    await expect(page.getByText('Win Rate').first()).toBeVisible();
    await expect(page.getByText('Profit Factor').first()).toBeVisible();
    await expect(page.getByText('Sharpe Ratio').first()).toBeVisible();

    // Row 2: Trade statistics — these labels are unique to the metrics grid
    await expect(resultsCard.getByText('Total Trades')).toBeVisible();
    await expect(resultsCard.getByText('Avg Hold Time')).toBeVisible();
    await expect(resultsCard.getByText('Avg Win')).toBeVisible();
    await expect(resultsCard.getByText('Avg Loss')).toBeVisible();
    await expect(resultsCard.getByText('Max DD')).toBeVisible();
    await expect(resultsCard.getByText('Final Equity')).toBeVisible();
    await expect(resultsCard.getByText('Realized P&L')).toBeVisible();
  });

  test('Return metric displays the total_return_pct value', async ({ page }) => {
    // total_return_pct is '12.50' → ArenaResultsTable displays '+12.5%'
    await expect(page.getByText('+12.5%')).toBeVisible();
  });

  test('Profit Factor metric displays the profit_factor value', async ({ page }) => {
    // profit_factor is '2.03' → displayed as '2.03'
    await expect(page.getByText('2.03')).toBeVisible();
  });

  test('Sharpe Ratio metric displays the sharpe_ratio value', async ({ page }) => {
    // sharpe_ratio is '1.45' → displayed as '1.45'
    await expect(page.getByText('1.45')).toBeVisible();
  });

  test('equity chart container is visible', async ({ page }) => {
    // ArenaEquityChart renders when isComplete && snapshots.length > 0
    // The chart container has data-testid="arena-equity-chart"
    const chartContainer = page.getByTestId('arena-equity-chart');
    await expect(chartContainer).toBeVisible({ timeout: 10000 });
  });

  test('equity chart has a canvas element rendered by lightweight-charts', async ({ page }) => {
    // Wait for the chart container to be rendered
    await page.getByTestId('arena-equity-chart').waitFor({ state: 'visible', timeout: 10000 });

    // Give lightweight-charts time to initialize and create the canvas element
    await page.waitForTimeout(500);

    // Canvas should exist — lightweight-charts renders into a canvas element
    const canvas = page.locator('canvas');
    await expect(canvas.first()).toBeAttached();
  });

  test('benchmark toggle buttons (SPY, QQQ) are present', async ({ page }) => {
    // ArenaEquityChart renders ToggleGroupItems with data-testid attributes
    await expect(page.getByTestId('benchmark-toggle-spy')).toBeVisible({ timeout: 10000 });
    await expect(page.getByTestId('benchmark-toggle-qqq')).toBeVisible({ timeout: 10000 });
  });

  test('portfolio composition section is visible when positions exist', async ({ page }) => {
    // ArenaPortfolioComposition renders when positions.length > 0
    // The card heading is "Portfolio Composition"
    await expect(page.getByText('Portfolio Composition')).toBeVisible();
  });

  test('portfolio composition shows biggest winners section', async ({ page }) => {
    // Winners section appears when there are closed positions with positive return
    await expect(page.getByText(/biggest winners/i)).toBeVisible();
  });

  test('portfolio composition shows biggest losers section', async ({ page }) => {
    // Losers section appears when there are closed positions with negative return
    await expect(page.getByText(/biggest losers/i)).toBeVisible();
  });

  test('portfolio composition shows P&L summary section', async ({ page }) => {
    // P&L Summary section appears when there are closed positions
    await expect(page.getByText(/p&l summary/i)).toBeVisible();
  });

  test('sector breakdown section is visible when positions exist', async ({ page }) => {
    // ArenaSectorBreakdown renders when positions.length > 0
    // The card heading is "Sector Breakdown"
    await expect(page.getByText('Sector Breakdown')).toBeVisible();
  });

  test('sector breakdown shows sector performance section for closed positions', async ({ page }) => {
    // Sector Performance section appears when there are closed positions
    await expect(page.getByText(/sector performance/i)).toBeVisible();
  });
});

// ---------------------------------------------------------------------------
// Test suite: Specific metric values from mock data
// ---------------------------------------------------------------------------

test.describe('Arena Analytics - Metrics Grid Values', () => {
  test.beforeEach(async ({ page }) => {
    await setupMocks(page);
    await page.goto('/arena/1');
    await page.waitForLoadState('networkidle');
  });

  test('Total Trades shows correct count from mock data', async ({ page }) => {
    // total_trades is 15 — displayed as-is in the Total Trades metric card.
    // Use exact match to avoid matching dates containing "15" (e.g. "2024-02-15")
    await expect(page.getByText('15', { exact: true })).toBeVisible();
  });

  test('Win Rate shows computed percentage from winning_trades / total_trades', async ({ page }) => {
    // 9 winning_trades / 15 total_trades = 60.0%
    await expect(page.getByText('60.0%')).toBeVisible();
  });

  test('Avg Hold Time shows formatted value from avg_hold_days', async ({ page }) => {
    // avg_hold_days is '8.20' → ArenaResultsTable formats it as '8.2 days'
    await expect(page.getByText('8.2 days')).toBeVisible();
  });
});

// ---------------------------------------------------------------------------
// Test suite: Navigation
// ---------------------------------------------------------------------------

test.describe('Arena Analytics - Navigation', () => {
  test('back button navigates to /arena', async ({ page }) => {
    await setupMocks(page);
    await page.goto('/arena/1');
    await page.waitForLoadState('networkidle');

    // The back button has aria-label="Back to Arena"
    const backButton = page.getByRole('button', { name: /back to arena/i });
    await expect(backButton).toBeVisible();
    await backButton.click();

    // Should navigate back to the /arena list page
    await expect(page).toHaveURL(/\/arena$/);
  });

  test('simulation shows completed status badge', async ({ page }) => {
    await setupMocks(page);
    await page.goto('/arena/1');
    await page.waitForLoadState('networkidle');

    // The status badge reflects simulation.status = 'completed'
    await expect(page.getByText('completed')).toBeVisible();
  });

  test('simulation name is shown in the page heading', async ({ page }) => {
    await setupMocks(page);
    await page.goto('/arena/1');
    await page.waitForLoadState('networkidle');

    // The page heading shows simulation.name = 'Test Analytics Simulation'
    await expect(page.getByRole('heading', { name: /Test Analytics Simulation/i })).toBeVisible();
  });
});
