/**
 * UI Tests for the Alerts Dashboard page
 *
 * These tests use page.route() to mock backend responses and validate
 * that the AlertsDashboard renders correctly across all states and interactions.
 *
 * Components under test:
 * - AlertsDashboard (page-level layout, loading/error/empty/data states)
 * - AlertsTable (rows, badges, details, sorting)
 * - AlertFilters (type and status dropdowns, count label)
 * - AlertStatusBadge (status label text, animate-pulse for actionable states)
 *
 * Route: /alerts
 * API calls: GET /api/v1/alerts/
 */

import { test, expect } from '@playwright/test';
import {
  mockAlertList,
  mockEmptyAlertList,
} from '../fixtures/mockAlertData';
import { AlertsPage } from '../pages/AlertsPage';

// ---------------------------------------------------------------------------
// Helper: Set up all required route mocks before navigating
// ---------------------------------------------------------------------------

const setupMocks = async (
  page: import('@playwright/test').Page,
  responseBody: unknown = mockAlertList,
  statusCode = 200,
) => {
  await page.route('**/api/v1/alerts/**', async (route) => {
    if (route.request().method() === 'GET') {
      await route.fulfill({
        status: statusCode,
        contentType: 'application/json',
        body: JSON.stringify(responseBody),
      });
    } else {
      await route.continue();
    }
  });
};

// ---------------------------------------------------------------------------
// Test suite: Page States
// ---------------------------------------------------------------------------

test.describe('Alerts Dashboard - Page States', () => {
  test('renders loading skeletons before data arrives', async ({ page }) => {
    // Delay the response so we can observe the loading state
    await page.route('**/api/v1/alerts/**', async (route) => {
      if (route.request().method() === 'GET') {
        // Return a promise that resolves after a delay without using waitForTimeout
        await new Promise<void>((resolve) => {
          const timer = setTimeout(() => {
            clearTimeout(timer);
            resolve();
          }, 2000);
        });
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(mockAlertList),
        });
      } else {
        await route.continue();
      }
    });

    await page.goto('/alerts');

    const alertsPage = new AlertsPage(page);
    await expect(alertsPage.loadingSkeleton).toBeVisible();
    await expect(alertsPage.alertsTable).not.toBeVisible();
  });

  test('renders empty state when no alerts exist', async ({ page }) => {
    await setupMocks(page, mockEmptyAlertList);
    await page.goto('/alerts');

    const alertsPage = new AlertsPage(page);
    await expect(alertsPage.heading).toBeVisible();
    await expect(alertsPage.emptyState).toBeVisible();

    // The empty state card also has its own "Add Alert" button
    const emptyStateAddButton = page.getByRole('button', { name: 'Add Alert' }).last();
    await expect(emptyStateAddButton).toBeVisible();
  });

  test('renders error state when API fails', async ({ page }) => {
    await setupMocks(page, { detail: 'Internal Server Error' }, 500);
    await page.goto('/alerts');

    const alertsPage = new AlertsPage(page);
    await expect(alertsPage.errorState).toBeVisible();
    await expect(alertsPage.retryButton).toBeVisible();
  });

  test('retrying after error re-fetches alerts', async ({ page }) => {
    let callCount = 0;

    await page.route('**/api/v1/alerts/**', async (route) => {
      if (route.request().method() === 'GET') {
        callCount++;
        // Return 500 for first 2 calls (React StrictMode double-fires effects)
        if (callCount <= 2) {
          await route.fulfill({
            status: 500,
            contentType: 'application/json',
            body: JSON.stringify({ detail: 'Internal Server Error' }),
          });
        } else {
          await route.fulfill({
            status: 200,
            contentType: 'application/json',
            body: JSON.stringify(mockAlertList),
          });
        }
      } else {
        await route.continue();
      }
    });

    await page.goto('/alerts');

    const alertsPage = new AlertsPage(page);
    await expect(alertsPage.errorState).toBeVisible();

    await alertsPage.retryButton.click();

    await expect(alertsPage.alertsTable).toBeVisible();
  });

  test('renders page heading and Add Alert button', async ({ page }) => {
    await setupMocks(page);
    await page.goto('/alerts');

    const alertsPage = new AlertsPage(page);
    await expect(alertsPage.heading).toBeVisible();
    await expect(alertsPage.addAlertButton).toBeVisible();
  });

  test('renders all alert rows in the table', async ({ page }) => {
    await setupMocks(page);
    await page.goto('/alerts');

    const alertsPage = new AlertsPage(page);
    await expect(alertsPage.heading).toBeVisible();

    // All 13 symbols from mockAlertList should be visible as row buttons
    const symbols = ['META', 'CRM', 'AMD', 'AAPL', 'MSFT', 'NFLX', 'AMZN', 'COST', 'NVDA', 'GOOGL', 'INTC', 'IPO', 'TSLA'];
    for (const symbol of symbols) {
      const row = await alertsPage.getAlertRow(symbol);
      await expect(row).toBeVisible();
    }
  });

  test('displays correct status badges for ALL Fibonacci statuses', async ({ page }) => {
    await setupMocks(page);
    await page.goto('/alerts');

    const alertsPage = new AlertsPage(page);
    await expect(alertsPage.heading).toBeVisible();

    const fibBadges: [string, string][] = [
      ['META', 'No Structure'],
      ['CRM', 'Rallying'],
      ['AMD', 'Pullback'],
      ['AAPL', 'Retracing'],
      ['MSFT', 'At Level'],
      ['NFLX', 'Bouncing'],
      ['AMZN', 'Invalidated'],
    ];

    for (const [symbol, badgeText] of fibBadges) {
      const row = await alertsPage.getAlertRow(symbol);
      await expect(row.getByText(badgeText)).toBeVisible();
    }
  });

  test('displays correct status badges for ALL MA statuses', async ({ page }) => {
    await setupMocks(page);
    await page.goto('/alerts');

    const alertsPage = new AlertsPage(page);
    await expect(alertsPage.heading).toBeVisible();

    const maBadges: [string, string][] = [
      ['COST', 'Above MA'],
      ['NVDA', 'Approaching'],
      ['GOOGL', 'At MA'],
      ['INTC', 'Below MA'],
      ['IPO', 'No Data'],
    ];

    for (const [symbol, badgeText] of maBadges) {
      const row = await alertsPage.getAlertRow(symbol);
      await expect(row.getByText(badgeText)).toBeVisible();
    }
  });

  test('at_level and at_ma badges have pulse animation', async ({ page }) => {
    await setupMocks(page);
    await page.goto('/alerts');

    const alertsPage = new AlertsPage(page);
    await expect(alertsPage.heading).toBeVisible();

    // MSFT has status: at_level — badge should have animate-pulse class
    const msftRow = await alertsPage.getAlertRow('MSFT');
    const atLevelBadge = msftRow.getByText('At Level');
    await expect(atLevelBadge).toHaveClass(/animate-pulse/);

    // GOOGL has status: at_ma — badge should have animate-pulse class
    const googlRow = await alertsPage.getAlertRow('GOOGL');
    const atMaBadge = googlRow.getByText('At MA');
    await expect(atMaBadge).toHaveClass(/animate-pulse/);
  });

  test('displays Fibonacci details column (swing range, retracement, next level)', async ({ page }) => {
    await setupMocks(page);
    await page.goto('/alerts');

    const alertsPage = new AlertsPage(page);
    await expect(alertsPage.heading).toBeVisible();

    // AAPL: swing_low=110, swing_high=140, retracement_pct=38.3, next_level={pct:50.0, price:125.00}
    // detailsText = "$110.00 → $140.00 | 38.3% | Next: 50% @ $125.00"
    const aaplRow = await alertsPage.getAlertRow('AAPL');
    await expect(aaplRow.getByText(/\$110/)).toBeVisible();
    await expect(aaplRow.getByText(/\$140/)).toBeVisible();
    await expect(aaplRow.getByText(/38\.3%/)).toBeVisible();
    await expect(aaplRow.getByText(/\$125\.00/)).toBeVisible();
  });

  test('displays MA details column (MA value, distance)', async ({ page }) => {
    await setupMocks(page);
    await page.goto('/alerts');

    const alertsPage = new AlertsPage(page);
    await expect(alertsPage.heading).toBeVisible();

    // NVDA: ma_period=200, ma_value=125.50, distance_pct=2.0
    // detailsText = "MA200 @ $125.50 | +2.0% rising"
    const nvdaRow = await alertsPage.getAlertRow('NVDA');
    // "MA200" appears in both the Alert Type and Details columns — use .first()
    await expect(nvdaRow.getByText(/MA200/).first()).toBeVisible();
    await expect(nvdaRow.getByText(/\$125\.50/)).toBeVisible();
    await expect(nvdaRow.getByText(/2\.0%/)).toBeVisible();
  });

  test('computed_state null renders gracefully in Details column', async ({ page }) => {
    await setupMocks(page);
    await page.goto('/alerts');

    const alertsPage = new AlertsPage(page);
    await expect(alertsPage.heading).toBeVisible();

    // TSLA is paused with computed_state: null — row must be present and stable
    const tslaRow = await alertsPage.getAlertRow('TSLA');
    await expect(tslaRow).toBeVisible();
    // detailsText = "Awaiting data"
    await expect(tslaRow.getByText('Awaiting data')).toBeVisible();

    // META has status: no_structure with computed_state: null
    const metaRow = await alertsPage.getAlertRow('META');
    await expect(metaRow).toBeVisible();
    await expect(metaRow.getByText('Awaiting data')).toBeVisible();
  });

  test('clicking a row navigates to detail view', async ({ page }) => {
    await setupMocks(page);
    await page.goto('/alerts');

    const alertsPage = new AlertsPage(page);
    await expect(alertsPage.heading).toBeVisible();

    // AAPL has id: 1 in mockFibAlert
    await alertsPage.navigateToDetail('AAPL');

    await expect(page).toHaveURL(/\/alerts\/1/);
  });

  test('displays Last Alert timestamp for alerts with last_triggered_at', async ({ page }) => {
    await setupMocks(page);
    await page.goto('/alerts');

    const alertsPage = new AlertsPage(page);
    await expect(alertsPage.heading).toBeVisible();

    // MSFT has last_triggered_at: '2026-03-14T16:30:00Z'
    // formatDate produces locale-dependent output — assert the date portion is present
    const msftRow = await alertsPage.getAlertRow('MSFT');
    // The date should contain "Mar" and "14" from the timestamp
    await expect(msftRow.getByText(/Mar.*14/)).toBeVisible();
  });

  test('displays Price column from computed_state.current_price', async ({ page }) => {
    await setupMocks(page);
    await page.goto('/alerts');

    const alertsPage = new AlertsPage(page);
    await expect(alertsPage.heading).toBeVisible();

    // AAPL has computed_state.current_price: 128.50 → renders "$128.50"
    const aaplRow = await alertsPage.getAlertRow('AAPL');
    await expect(aaplRow.getByText('$128.50')).toBeVisible();
  });

  test('page loads without console errors', async ({ page }) => {
    const consoleErrors: string[] = [];

    page.on('console', (msg) => {
      if (msg.type() === 'error') {
        const text = msg.text();
        // Filter known React development-mode HTML nesting warnings
        if (text.includes('In HTML,') && text.includes('cannot be a descendant')) return;
        if (text.includes('cannot contain a nested')) return;
        // Filter pre-existing environment endpoint errors (no backend running for UI tests)
        if (text.includes('Failed to fetch environment')) return;
        if (text.includes('status of 500')) return;
        consoleErrors.push(text);
      }
    });

    await setupMocks(page);
    await page.goto('/alerts');
    await page.waitForLoadState('networkidle');
    await expect(page.getByRole('heading', { name: 'Alerts' })).toBeVisible();

    expect(consoleErrors).toHaveLength(0);
  });
});

// ---------------------------------------------------------------------------
// Test suite: Filtering
// ---------------------------------------------------------------------------

test.describe('Alerts Dashboard - Filtering', () => {
  test.beforeEach(async ({ page }) => {
    await setupMocks(page);
    const alertsPage = new AlertsPage(page);
    await alertsPage.goto();
  });

  test('filter by alert type shows only matching alerts', async ({ page }) => {
    const alertsPage = new AlertsPage(page);
    await alertsPage.filterByType('Fibonacci');

    // Fibonacci alerts (8 total including TSLA)
    const fibSymbols = ['META', 'CRM', 'AMD', 'AAPL', 'MSFT', 'NFLX', 'AMZN', 'TSLA'];
    for (const symbol of fibSymbols) {
      const row = await alertsPage.getAlertRow(symbol);
      await expect(row).toBeVisible();
    }

    // MA alerts should be hidden
    const maSymbols = ['COST', 'NVDA', 'GOOGL', 'INTC', 'IPO'];
    for (const symbol of maSymbols) {
      const row = await alertsPage.getAlertRow(symbol);
      await expect(row).not.toBeVisible();
    }
  });

  test('filter by status shows only matching alerts', async ({ page }) => {
    const alertsPage = new AlertsPage(page);
    // AAPL (status: retracing) and TSLA (status: retracing) are the only two
    await alertsPage.filterByStatus('Retracing');

    const aaplRow = await alertsPage.getAlertRow('AAPL');
    await expect(aaplRow).toBeVisible();

    const tslaRow = await alertsPage.getAlertRow('TSLA');
    await expect(tslaRow).toBeVisible();

    // Other symbols with different statuses should not be visible
    const otherSymbols = ['CRM', 'AMD', 'MSFT', 'NFLX', 'AMZN', 'COST', 'NVDA', 'GOOGL', 'INTC', 'IPO', 'META'];
    for (const symbol of otherSymbols) {
      const row = await alertsPage.getAlertRow(symbol);
      await expect(row).not.toBeVisible();
    }
  });

  test('combined type and status filter narrows to single result', async ({ page }) => {
    const alertsPage = new AlertsPage(page);
    await alertsPage.filterByType('Fibonacci');
    await alertsPage.filterByStatus('At Level');

    // Only MSFT has type=fibonacci AND status=at_level
    const msftRow = await alertsPage.getAlertRow('MSFT');
    await expect(msftRow).toBeVisible();

    // All other rows should be hidden
    const otherSymbols = ['META', 'CRM', 'AMD', 'AAPL', 'NFLX', 'AMZN', 'TSLA', 'COST', 'NVDA', 'GOOGL', 'INTC', 'IPO'];
    for (const symbol of otherSymbols) {
      const row = await alertsPage.getAlertRow(symbol);
      await expect(row).not.toBeVisible();
    }
  });

  test('empty filter result shows message', async ({ page }) => {
    const alertsPage = new AlertsPage(page);
    // Fibonacci + At Level produces only 1 result (MSFT).
    // Then switching to "Bouncing" also produces only 1 (NFLX).
    // But we need 0 results: use All Types + a status no one matches.
    // All statuses have at least one alert, so we combine type + status:
    // "Moving Average" restricts status options to MA-only; "No Data" (insufficient_data) → only IPO.
    // Instead: filter by "Fibonacci" first, then by "At Level". Then switch type to "Moving Average"
    // which auto-resets status to "all" (status not valid for MA).
    // Simplest: use type "Fibonacci" then manually check for "at_ma" which doesn't exist.
    // Actually we can programmatically create the condition via combined filters.
    //
    // Use the approach: filter by type="Fibonacci" (8 alerts), then status="At Level" (1: MSFT).
    // The count shows "1 of 13 alerts" — then change type to "Moving Average" which resets status.
    // The auto-reset means we can't reach 0 with type+status from the UI alone easily.
    //
    // Alternative: just verify the empty filter state exists by mocking a smaller list
    // and filtering it. But this test uses beforeEach with full mockAlertList.
    // Simplest working approach: override the mock with a list that has only Fibonacci alerts,
    // then filter by "Moving Average" type → 0 results.
    await page.route('**/api/v1/alerts/**', async (route) => {
      if (route.request().method() === 'GET') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            items: [mockAlertList.items[0]], // Only META (fibonacci, no_structure)
            total: 1,
          }),
        });
      } else {
        await route.continue();
      }
    });
    await page.goto('/alerts');
    await expect(alertsPage.heading).toBeVisible();

    await alertsPage.filterByType('Moving Average');

    await expect(alertsPage.emptyFilterState).toBeVisible();
  });

  test('alert count label updates with filter', async ({ page }) => {
    const alertsPage = new AlertsPage(page);

    // Without any filter: 13 of 13 alerts
    await expect(alertsPage.alertCountLabel).toHaveText('13 of 13 alerts');

    // After filtering to Fibonacci only: 8 of 13
    await alertsPage.filterByType('Fibonacci');
    await expect(alertsPage.alertCountLabel).toHaveText('8 of 13 alerts');
  });
});

// ---------------------------------------------------------------------------
// Test suite: Sorting
// ---------------------------------------------------------------------------

test.describe('Alerts Dashboard - Sorting', () => {
  test('actionable statuses appear first in default sort', async ({ page }) => {
    await setupMocks(page);
    await page.goto('/alerts');

    const alertsPage = new AlertsPage(page);
    await expect(alertsPage.heading).toBeVisible();

    // STATUS_ORDER: at_level=0, at_ma=0 — these should appear before non-actionable statuses.
    // MSFT (at_level) and GOOGL (at_ma) both have order 0.
    // Verify they appear before symbols with higher order values like CRM (rallying=5).
    const msftRow = await alertsPage.getAlertRow('MSFT');
    const googlRow = await alertsPage.getAlertRow('GOOGL');
    const crmRow = await alertsPage.getAlertRow('CRM');

    // Retrieve bounding boxes to compare vertical positions in the DOM
    const msftBox = await msftRow.boundingBox();
    const googlBox = await googlRow.boundingBox();
    const crmBox = await crmRow.boundingBox();

    expect(msftBox).not.toBeNull();
    expect(googlBox).not.toBeNull();
    expect(crmBox).not.toBeNull();

    // at_level and at_ma rows (order=0) must appear above the rallying row (order=5)
    expect(msftBox!.y).toBeLessThan(crmBox!.y);
    expect(googlBox!.y).toBeLessThan(crmBox!.y);
  });
});

// ---------------------------------------------------------------------------
// Test suite: Notification Banners
// ---------------------------------------------------------------------------

test.describe('Alerts Dashboard - Notification Banners', () => {
  test('notification granted banner is visible when permission is granted', async ({ page }) => {
    // Mock Notification.permission before any scripts run on the page
    await page.addInitScript(() => {
      Object.defineProperty(Notification, 'permission', {
        get: () => 'granted',
        configurable: true,
      });
    });

    await setupMocks(page);
    await page.goto('/alerts');
    await expect(page.getByRole('heading', { name: 'Alerts' })).toBeVisible();

    // Granted banner contains text about notifications being enabled and keeping the tab open
    const banner = page.getByRole('status').filter({ hasText: 'Browser notifications are enabled' });
    await expect(banner).toBeVisible();
  });

  test('notification denied banner is visible when permission is denied', async ({ page }) => {
    // Mock Notification.permission before any scripts run on the page
    await page.addInitScript(() => {
      Object.defineProperty(Notification, 'permission', {
        get: () => 'denied',
        configurable: true,
      });
    });

    await setupMocks(page);
    await page.goto('/alerts');
    await expect(page.getByRole('heading', { name: 'Alerts' })).toBeVisible();

    // Denied banner contains text about notifications being blocked
    const banner = page.getByRole('status').filter({ hasText: 'Notifications are blocked' });
    await expect(banner).toBeVisible();
  });
});
