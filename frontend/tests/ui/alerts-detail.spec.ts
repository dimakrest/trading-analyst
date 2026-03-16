/**
 * UI Tests for Alert Detail View
 *
 * These tests use page.route() to mock backend responses and validate that
 * the Alert Detail page renders all components correctly for both alert types
 * and handles error states gracefully.
 *
 * Components under test:
 * - AlertDetail page (symbol heading, breadcrumb, back button, chart, actions)
 * - AlertInfoPanel (Fibonacci and MA info sections, event history)
 * - CandlestickChart (container + canvas rendered by lightweight-charts)
 * - AlertStatusBadge (status display)
 * - Delete confirmation dialog (AlertDialog)
 *
 * NOTE: Canvas content (lightweight-charts) is not accessible to Playwright
 * queries. Tests assert the chart container div is present, not canvas internals.
 *
 * Route: /alerts/:alertId (maps to AlertDetail component)
 * API calls:
 *   GET /api/v1/alerts/:id
 *   GET /api/v1/alerts/:id/events
 *   GET /api/v1/alerts/:id/price-data
 */

import { test, expect } from '@playwright/test';
import {
  mockFibAtLevelAlert,
  mockMAAlert,
  mockAlertEvents,
  mockAlertPriceData,
} from '../fixtures/mockAlertData';
import { AlertDetailPage } from '../pages/AlertDetailPage';

// ---------------------------------------------------------------------------
// Mock price data helpers
// ---------------------------------------------------------------------------

/**
 * Transform mockAlertPriceData (which uses `timestamp` fields from the backend)
 * into the shape that AlertDetail.tsx's toPriceData() expects (`date` field).
 *
 * The raw backend response uses `timestamp`; toPriceData reads `item.date`.
 * The route handler must perform this mapping so the chart receives valid data.
 */
const buildPriceDataResponse = (symbolOverride?: string) => ({
  symbol: symbolOverride ?? mockAlertPriceData.symbol,
  alert_id: mockAlertPriceData.alert_id,
  days: mockAlertPriceData.days,
  data: mockAlertPriceData.data.map((candle) => ({
    date: candle.timestamp.split('T')[0], // toPriceData reads `item.date`
    open: candle.open,
    high: candle.high,
    low: candle.low,
    close: candle.close,
    volume: candle.volume,
  })),
});

/** Minimal OHLCV data for MA alert (5 candles, `date` field) */
const buildMAPriceDataResponse = () => ({
  symbol: 'NVDA',
  alert_id: 2,
  days: 365,
  data: [
    { date: '2026-03-10', open: 130.0, high: 132.0, low: 128.5, close: 129.0, volume: 45000000 },
    { date: '2026-03-11', open: 129.0, high: 130.5, low: 127.0, close: 128.5, volume: 48000000 },
    { date: '2026-03-12', open: 128.5, high: 129.5, low: 126.5, close: 127.5, volume: 50000000 },
    { date: '2026-03-13', open: 127.5, high: 128.5, low: 126.0, close: 128.0, volume: 47000000 },
    { date: '2026-03-14', open: 128.0, high: 129.0, low: 127.5, close: 128.0, volume: 46000000 },
  ],
});

// ---------------------------------------------------------------------------
// Route mock helpers
// ---------------------------------------------------------------------------

/**
 * Set up the three route mocks required for the Fibonacci at-level alert (ID 3).
 *
 * - GET /api/v1/alerts/3          → mockFibAtLevelAlert
 * - GET /api/v1/alerts/3/events   → mockAlertEvents
 * - GET /api/v1/alerts/3/price-data → transformed price data (date field)
 */
const setupFibMocks = async (page: import('@playwright/test').Page) => {
  await page.route('**/api/v1/alerts/3', async (route) => {
    if (route.request().method() === 'GET') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(mockFibAtLevelAlert),
      });
    } else {
      await route.continue();
    }
  });

  await page.route('**/api/v1/alerts/3/events', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(mockAlertEvents),
    });
  });

  await page.route('**/api/v1/alerts/3/price-data**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(buildPriceDataResponse()),
    });
  });
};

/**
 * Set up the three route mocks required for the MA approaching alert (ID 2).
 *
 * - GET /api/v1/alerts/2          → mockMAAlert (NVDA, MA200, approaching)
 * - GET /api/v1/alerts/2/events   → [] (empty history)
 * - GET /api/v1/alerts/2/price-data → minimal MA price data
 */
const setupMAMocks = async (page: import('@playwright/test').Page) => {
  await page.route('**/api/v1/alerts/2', async (route) => {
    if (route.request().method() === 'GET') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(mockMAAlert),
      });
    } else {
      await route.continue();
    }
  });

  await page.route('**/api/v1/alerts/2/events', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify([]),
    });
  });

  await page.route('**/api/v1/alerts/2/price-data**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(buildMAPriceDataResponse()),
    });
  });
};

// ---------------------------------------------------------------------------
// Test suite: Fibonacci alert detail (at_level, MSFT, ID 3)
// ---------------------------------------------------------------------------

test.describe('Alert Detail - Fibonacci', () => {
  test.beforeEach(async ({ page }) => {
    await setupFibMocks(page);
    const detailPage = new AlertDetailPage(page);
    await detailPage.goto(3);
  });

  // 1
  test('renders page with symbol heading', async ({ page }) => {
    await expect(page.getByRole('heading', { level: 1 })).toContainText('MSFT');
  });

  // 2
  test('renders breadcrumb navigation', async ({ page }) => {
    // Back button shows "Alerts" text (the breadcrumb link)
    await expect(page.getByRole('button', { name: 'Back to alerts' })).toContainText('Alerts');
    // h1 shows the current symbol as the page-level breadcrumb
    await expect(page.getByRole('heading', { level: 1 })).toContainText('MSFT');
  });

  // 3
  test('back button navigates to alerts list', async ({ page }) => {
    const detailPage = new AlertDetailPage(page);
    await detailPage.clickBack();
    await expect(page).toHaveURL(/\/alerts$/);
  });

  // 4
  test('renders chart container with canvas', async ({ page }) => {
    const detailPage = new AlertDetailPage(page);
    await expect(detailPage.chart).toBeVisible();
    // Give lightweight-charts time to initialise and paint the canvas
    await page.waitForTimeout(500);
    await expect(page.locator('canvas').first()).toBeAttached();
  });

  // 5
  test('renders Fibonacci info panel with swing range and current price', async ({ page }) => {
    // Card heading inside AlertInfoPanel
    await expect(page.getByText('Fibonacci Retracement')).toBeVisible();
    // Swing low and high from mockFibAtLevelAlert.computed_state
    await expect(page.getByText(/\$370/)).toBeVisible();
    await expect(page.getByText(/\$420/)).toBeVisible();
    // Current price: 400.90 — appears in multiple places (info panel, level row, event)
    await expect(page.getByText(/\$400\.90/).first()).toBeVisible();
  });

  // 6
  test('renders Fibonacci level table with all three levels', async ({ page }) => {
    // Levels rendered in FibonacciInfoSection as "{key}%" rows
    // "38.2%" also appears in "38.2% retraced" text — use exact to match the level label
    await expect(page.getByText('38.2%', { exact: true })).toBeVisible();
    await expect(page.getByText('50.0%', { exact: true })).toBeVisible();
    await expect(page.getByText('61.8%', { exact: true })).toBeVisible();
    // The 38.2% level price is $400.90 (at_level mock)
    await expect(page.getByText('$400.90').first()).toBeVisible();
  });

  // 7
  test('renders alert status badge with At Level', async ({ page }) => {
    // AlertStatusBadge renders the human-readable status label
    await expect(page.getByText('At Level')).toBeVisible();
  });

  // 8
  test('renders event history with level hit and status change events', async ({ page }) => {
    // EVENT_TYPE_LABELS maps 'level_hit' → 'Level Hit', 'status_change' → 'Status Change'
    await expect(page.getByText('Level Hit')).toBeVisible();
    await expect(page.getByText('Status Change')).toBeVisible();
    // Both events include a price and a formatted date
    await expect(page.getByText(/\$400\.90/).first()).toBeVisible();
    await expect(page.getByText(/\$410\.00/)).toBeVisible();
    // Dates are rendered via formatShortDate — check for Mar which covers both events
    await expect(page.getByText(/Mar/).first()).toBeVisible();
  });

  // 9
  test('renders Pause alert button when alert is not paused', async ({ page }) => {
    const detailPage = new AlertDetailPage(page);
    // mockFibAtLevelAlert.is_paused = false → aria-label="Pause alert"
    await expect(detailPage.pauseButton).toBeVisible();
  });

  // 10
  test('pause button sends PATCH and updates UI to show Resume', async ({ page }) => {
    const pausedAlert = { ...mockFibAtLevelAlert, is_paused: true };

    // Intercept the PATCH request and return the paused alert
    await page.route('**/api/v1/alerts/3', async (route) => {
      const method = route.request().method();
      if (method === 'PATCH') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(pausedAlert),
        });
      } else if (method === 'GET') {
        // Re-fetch after refetch() call returns the paused variant
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(pausedAlert),
        });
      } else {
        await route.continue();
      }
    });

    const detailPage = new AlertDetailPage(page);
    await detailPage.pauseButton.click();
    // After PATCH + refetch, is_paused becomes true → button label switches
    await expect(detailPage.resumeButton).toBeVisible({ timeout: 5000 });
  });

  // 11
  test('delete button opens confirmation dialog', async ({ page }) => {
    const detailPage = new AlertDetailPage(page);
    await detailPage.clickDelete();
    // AlertDialog renders with role="alertdialog"
    const dialog = page.getByRole('alertdialog');
    await expect(dialog).toBeVisible();
    await expect(dialog.getByRole('heading', { name: 'Delete alert?' })).toBeVisible();
    await expect(dialog.getByRole('button', { name: 'Delete' })).toBeVisible();
    await expect(dialog.getByRole('button', { name: 'Cancel' })).toBeVisible();
  });

  // 12
  test('confirming delete navigates back to alerts list', async ({ page }) => {
    // Mock the DELETE endpoint
    await page.route('**/api/v1/alerts/3', async (route) => {
      if (route.request().method() === 'DELETE') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ deleted: 3 }),
        });
      } else {
        await route.continue();
      }
    });

    const detailPage = new AlertDetailPage(page);
    await detailPage.clickDelete();
    await detailPage.confirmDelete();
    await expect(page).toHaveURL(/\/alerts$/, { timeout: 5000 });
  });
});

// ---------------------------------------------------------------------------
// Test suite: Moving Average alert detail (approaching, NVDA, ID 2)
// ---------------------------------------------------------------------------

test.describe('Alert Detail - Moving Average', () => {
  test.beforeEach(async ({ page }) => {
    await setupMAMocks(page);
    const detailPage = new AlertDetailPage(page);
    await detailPage.goto(2);
  });

  // 13
  test('renders MA info panel with MA value, distance, and slope', async ({ page }) => {
    // Card heading: `MA${cs.ma_period} Alert` → "MA200 Alert"
    await expect(page.getByText('MA200 Alert')).toBeVisible();
    // MA value from mockMAAlert.computed_state.ma_value = 125.50
    await expect(page.getByText('$125.50')).toBeVisible();
    // Distance: distanceAbs.toFixed(1) → "2.0%" (distance_pct = 2.0)
    await expect(page.getByText(/2\.0%/)).toBeVisible();
    // MA slope is "rising" in DOM text (CSS `capitalize` is visual-only; Playwright sees raw text)
    await expect(page.getByText('rising', { exact: true })).toBeVisible();
  });

  // 14
  test('renders empty event history message', async ({ page }) => {
    // No events → renders the empty-state italic paragraph
    await expect(page.getByText('No events recorded yet.')).toBeVisible();
  });
});

// ---------------------------------------------------------------------------
// Test suite: Error states
// ---------------------------------------------------------------------------

test.describe('Alert Detail - Error States', () => {
  // 15
  test('renders not found state for nonexistent alert', async ({ page }) => {
    // Mock 404 for alert ID 999
    await page.route('**/api/v1/alerts/999', async (route) => {
      await route.fulfill({ status: 404, contentType: 'application/json', body: '{"detail":"Not found"}' });
    });
    await page.route('**/api/v1/alerts/999/events', async (route) => {
      await route.fulfill({ status: 404, contentType: 'application/json', body: '{"detail":"Not found"}' });
    });
    await page.route('**/api/v1/alerts/999/price-data**', async (route) => {
      await route.fulfill({ status: 404, contentType: 'application/json', body: '{"detail":"Not found"}' });
    });

    await page.goto('/alerts/999');
    await page.waitForLoadState('networkidle');

    // A 404 from the API causes useAlertDetail to set error state.
    // AlertDetail shows the error branch (role="alert") before the !alert branch.
    const detailPage = new AlertDetailPage(page);
    await expect(detailPage.errorState).toBeVisible();
    await expect(page.getByText('Failed to load alert')).toBeVisible();
  });

  // 16
  test('renders error state with retry button on server error', async ({ page }) => {
    // Mock 500 for alert ID 3 — the hook sets error state
    await page.route('**/api/v1/alerts/3', async (route) => {
      await route.fulfill({ status: 500, contentType: 'application/json', body: '{"detail":"Internal Server Error"}' });
    });
    await page.route('**/api/v1/alerts/3/events', async (route) => {
      await route.fulfill({ status: 500, contentType: 'application/json', body: '{"detail":"Internal Server Error"}' });
    });
    await page.route('**/api/v1/alerts/3/price-data**', async (route) => {
      await route.fulfill({ status: 500, contentType: 'application/json', body: '{"detail":"Internal Server Error"}' });
    });

    await page.goto('/alerts/3');
    await page.waitForLoadState('networkidle');

    const detailPage = new AlertDetailPage(page);
    // ShadCN Alert renders with role="alert" in the destructive variant
    await expect(detailPage.errorState).toBeVisible();
    // Retry button is rendered inside the AlertDescription
    await expect(detailPage.retryButton).toBeVisible();
  });
});
