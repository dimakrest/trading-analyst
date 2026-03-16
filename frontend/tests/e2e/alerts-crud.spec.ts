/**
 * Alerts Feature E2E Tests — CRUD Operations
 *
 * Tests the complete Alerts feature against a real backend.
 * Uses well-known liquid symbols (AAPL, MSFT, GOOGL, NVDA, TSLA) so that
 * the backend's Yahoo Finance price fetch succeeds during alert creation.
 *
 * Prerequisites: backend must be running (`./scripts/dc.sh up -d`)
 */

import { test, expect } from '@playwright/test';
import { TEST_CONFIG } from './config';

const FRONTEND_URL = TEST_CONFIG.FRONTEND_URL;
const BACKEND_URL = TEST_CONFIG.BACKEND_URL;

// Symbols used by UI tests that create alerts through the form.
// These must be real symbols accepted by Yahoo Finance.
const UI_TEST_SYMBOLS = ['AAPL', 'MSFT', 'NVDA'];

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Create a Fibonacci alert via API and return the created alert object. */
async function createFibAlertViaApi(symbol: string = 'AAPL') {
  const response = await fetch(`${BACKEND_URL}/api/v1/alerts/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      symbol,
      alert_type: 'fibonacci',
      config: { levels: [0.382, 0.5, 0.618], tolerance_pct: 0.5, min_swing_pct: 5 },
    }),
  });
  expect(response.ok).toBe(true);
  const data = await response.json();
  // POST /api/v1/alerts/ returns an array of created alerts
  return data[0] as { id: number; symbol: string; is_paused: boolean };
}

/** Pause an alert via API (PATCH is_paused = true). */
async function pauseAlertViaApi(id: number) {
  const response = await fetch(`${BACKEND_URL}/api/v1/alerts/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ is_paused: true }),
  });
  expect(response.ok).toBe(true);
}

/** Delete an alert by ID via API (best-effort; ignores errors). */
async function deleteAlertViaApi(id: number) {
  await fetch(`${BACKEND_URL}/api/v1/alerts/${id}`, { method: 'DELETE' });
}

/** Delete all alerts for a given symbol via API (best-effort). */
async function deleteAlertsBySymbol(symbol: string) {
  const response = await fetch(`${BACKEND_URL}/api/v1/alerts/?symbol=${symbol}`);
  if (!response.ok) return;
  const data = await response.json();
  const items: { id: number }[] = Array.isArray(data) ? data : (data.items ?? []);
  for (const item of items) {
    await deleteAlertViaApi(item.id);
  }
}

// ---------------------------------------------------------------------------
// Test suite
// ---------------------------------------------------------------------------

test.describe.configure({ mode: 'serial' });

test.describe('Alerts E2E - CRUD Operations', () => {
  test.beforeAll(async () => {
    // Verify backend is running before any test executes
    const backendCheck = await fetch(`${BACKEND_URL}/docs`);
    if (!backendCheck.ok) {
      throw new Error('Backend is not running. Start it with: ./scripts/dc.sh up -d');
    }
  });

  test.beforeEach(async () => {
    // Clean up alerts for all symbols used by UI tests so each test starts clean
    for (const symbol of UI_TEST_SYMBOLS) {
      await deleteAlertsBySymbol(symbol);
    }
  });

  // -------------------------------------------------------------------------
  // Test 1 — Create a Fibonacci alert through the UI
  // -------------------------------------------------------------------------
  test('can create a Fibonacci alert through the UI', async ({ page }) => {
    await page.goto(`${FRONTEND_URL}/alerts`);

    // Open the create dialog
    await page.getByRole('button', { name: 'Add Alert' }).first().click();

    // Dialog should appear
    await expect(page.getByRole('dialog')).toBeVisible({ timeout: 5000 });

    // Fill in symbol
    await page.getByLabel(/symbol/i).fill('AAPL');

    // Fibonacci is selected by default — no type change needed

    // Submit the form
    await page.getByRole('button', { name: 'Add Alert' }).click();

    // Dialog should close
    await expect(page.getByRole('dialog')).not.toBeVisible({ timeout: 10000 });

    // New alert row should appear in the table
    await expect(
      page.getByRole('button', { name: /View details for AAPL/ }).first()
    ).toBeVisible({ timeout: 10000 });
  });

  // -------------------------------------------------------------------------
  // Test 2 — Create an MA alert through the UI
  // -------------------------------------------------------------------------
  test('can create an MA alert through the UI', async ({ page }) => {
    await page.goto(`${FRONTEND_URL}/alerts`);

    // Open the create dialog
    await page.getByRole('button', { name: 'Add Alert' }).first().click();
    await expect(page.getByRole('dialog')).toBeVisible({ timeout: 5000 });

    // Fill in symbol
    await page.getByLabel(/symbol/i).fill('MSFT');

    // Switch to Moving Average type
    await page.getByRole('radio', { name: 'Moving average alert' }).click();

    // MA50 is the default selected period — verify and leave it checked
    // (the MA50 checkbox button should have aria-checked="true" by default)
    await expect(
      page.getByRole('checkbox', { name: 'MA50' })
    ).toHaveAttribute('aria-checked', 'true');

    // Submit
    await page.getByRole('button', { name: 'Add Alert' }).click();

    // Dialog should close
    await expect(page.getByRole('dialog')).not.toBeVisible({ timeout: 10000 });

    // New MA50 alert row should appear
    await expect(
      page.getByRole('button', { name: /View details for MSFT/ })
    ).toBeVisible({ timeout: 10000 });
  });

  // -------------------------------------------------------------------------
  // Test 3 — MA fan-out creates multiple rows for multiple periods
  // -------------------------------------------------------------------------
  test('MA fan-out: selecting MA50 + MA200 creates two alert rows', async ({ page }) => {
    await page.goto(`${FRONTEND_URL}/alerts`);

    // Open the create dialog
    await page.getByRole('button', { name: 'Add Alert' }).first().click();
    await expect(page.getByRole('dialog')).toBeVisible({ timeout: 5000 });

    // Fill in symbol
    await page.getByLabel(/symbol/i).fill('NVDA');

    // Switch to Moving Average type
    await page.getByRole('radio', { name: 'Moving average alert' }).click();

    // MA50 is already checked by default; also check MA200
    await page.getByRole('checkbox', { name: 'MA200' }).click();

    // Verify both are selected
    await expect(page.getByRole('checkbox', { name: 'MA50' })).toHaveAttribute('aria-checked', 'true');
    await expect(page.getByRole('checkbox', { name: 'MA200' })).toHaveAttribute('aria-checked', 'true');

    // Submit
    await page.getByRole('button', { name: 'Add Alert' }).click();

    // Dialog should close
    await expect(page.getByRole('dialog')).not.toBeVisible({ timeout: 10000 });

    // Two separate alert rows should be visible — one for each MA period
    await expect(
      page.getByRole('button', { name: /View details for NVDA/ })
    ).toHaveCount(2, { timeout: 10000 });
  });

  // -------------------------------------------------------------------------
  // Test 4 — Navigate from dashboard to alert detail view
  // -------------------------------------------------------------------------
  test('can navigate from dashboard to alert detail view', async ({ page }) => {
    // Seed alert via API
    const alert = await createFibAlertViaApi('AAPL');

    await page.goto(`${FRONTEND_URL}/alerts`);

    // Wait for the row and click it
    const alertRow = page.getByRole('button', { name: /View details for AAPL/ }).first();
    await expect(alertRow).toBeVisible({ timeout: 10000 });
    await alertRow.click();

    // URL should contain the alert id
    await expect(page).toHaveURL(new RegExp(`/alerts/${alert.id}`), { timeout: 5000 });

    // Symbol heading should be visible
    await expect(page.getByRole('heading', { name: 'AAPL' })).toBeVisible({ timeout: 5000 });

    // Chart container should be present
    await expect(page.getByTestId('candlestick-chart')).toBeAttached({ timeout: 10000 });

    // Structural check: "Fibonacci Retracement" label in the info panel
    await expect(page.getByText('Fibonacci Retracement')).toBeVisible({ timeout: 5000 });

    await deleteAlertViaApi(alert.id);
  });

  // -------------------------------------------------------------------------
  // Test 5 — Pause an alert from the detail view
  // -------------------------------------------------------------------------
  test('can pause an alert from detail view', async ({ page }) => {
    const alert = await createFibAlertViaApi('AAPL');

    await page.goto(`${FRONTEND_URL}/alerts/${alert.id}`);

    // Wait for the page to load (symbol heading visible)
    await expect(page.getByRole('heading', { name: 'AAPL' })).toBeVisible({ timeout: 10000 });

    // Click "Pause alert"
    await page.getByRole('button', { name: 'Pause alert' }).click();

    // "Resume alert" button should appear after the action completes
    await expect(page.getByRole('button', { name: 'Resume alert' })).toBeVisible({ timeout: 10000 });

    // Verify via API that is_paused is now true
    const apiResponse = await fetch(`${BACKEND_URL}/api/v1/alerts/${alert.id}`);
    expect(apiResponse.ok).toBe(true);
    const updatedAlert = await apiResponse.json();
    expect(updatedAlert.is_paused).toBe(true);

    await deleteAlertViaApi(alert.id);
  });

  // -------------------------------------------------------------------------
  // Test 6 — Resume a paused alert from the detail view
  // -------------------------------------------------------------------------
  test('can resume a paused alert from detail view', async ({ page }) => {
    const alert = await createFibAlertViaApi('AAPL');

    // Pause it via API so we start in the paused state
    await pauseAlertViaApi(alert.id);

    await page.goto(`${FRONTEND_URL}/alerts/${alert.id}`);

    // Wait for the page to load and confirm it shows "Resume alert"
    await expect(page.getByRole('heading', { name: 'AAPL' })).toBeVisible({ timeout: 10000 });
    await expect(page.getByRole('button', { name: 'Resume alert' })).toBeVisible({ timeout: 5000 });

    // Click "Resume alert"
    await page.getByRole('button', { name: 'Resume alert' }).click();

    // "Pause alert" button should appear after the action completes
    await expect(page.getByRole('button', { name: 'Pause alert' })).toBeVisible({ timeout: 10000 });

    // Verify via API that is_paused is now false
    const apiResponse = await fetch(`${BACKEND_URL}/api/v1/alerts/${alert.id}`);
    expect(apiResponse.ok).toBe(true);
    const updatedAlert = await apiResponse.json();
    expect(updatedAlert.is_paused).toBe(false);

    await deleteAlertViaApi(alert.id);
  });

  // -------------------------------------------------------------------------
  // Test 7 — Delete an alert with confirmation
  // -------------------------------------------------------------------------
  test('can delete an alert with confirmation', async ({ page }) => {
    const alert = await createFibAlertViaApi('AAPL');

    await page.goto(`${FRONTEND_URL}/alerts/${alert.id}`);

    // Wait for the page to load
    await expect(page.getByRole('heading', { name: 'AAPL' })).toBeVisible({ timeout: 10000 });

    // Click "Delete alert" to open the confirmation dialog
    await page.getByRole('button', { name: 'Delete alert' }).click();

    // Confirmation alertdialog should appear
    await expect(page.getByRole('alertdialog')).toBeVisible({ timeout: 5000 });

    // Click the "Delete" confirm button inside the alertdialog
    await page.getByRole('alertdialog').getByRole('button', { name: 'Delete' }).click();

    // Should navigate back to the alerts dashboard (use regex to match /alerts without trailing ID)
    await expect(page).toHaveURL(/\/alerts$/, { timeout: 10000 });

    // The deleted alert row for this specific ID should NOT be present
    const apiResponse = await fetch(`${BACKEND_URL}/api/v1/alerts/${alert.id}`);
    expect(apiResponse.status).toBe(404);
  });

  // -------------------------------------------------------------------------
  // Test 8 — Alert detail shows chart container and canvas
  // -------------------------------------------------------------------------
  test('alert detail shows chart container and canvas element', async ({ page }) => {
    const alert = await createFibAlertViaApi('AAPL');

    await page.goto(`${FRONTEND_URL}/alerts/${alert.id}`);

    // Wait for the page to load
    await expect(page.getByRole('heading', { name: 'AAPL' })).toBeVisible({ timeout: 10000 });

    // Chart container should be in the DOM
    // The CandlestickChart renders a div wrapper that contains the TradingView canvas
    await expect(page.locator('canvas').first()).toBeAttached({ timeout: 10000 });

    await deleteAlertViaApi(alert.id);
  });

  // -------------------------------------------------------------------------
  // Test 9 — Back navigation returns to the alerts dashboard
  // -------------------------------------------------------------------------
  test('back button navigates from detail view to alerts dashboard', async ({ page }) => {
    const alert = await createFibAlertViaApi('AAPL');

    // Navigate directly to the detail page
    await page.goto(`${FRONTEND_URL}/alerts/${alert.id}`);

    // Wait for the page to load
    await expect(page.getByRole('heading', { name: 'AAPL' })).toBeVisible({ timeout: 10000 });

    // Click the back button (aria-label="Back to alerts")
    await page.getByRole('button', { name: 'Back to alerts' }).click();

    // Should navigate to the alerts dashboard
    await expect(page).toHaveURL(`${FRONTEND_URL}/alerts`, { timeout: 5000 });

    // The "Alerts" heading should be visible on the dashboard
    await expect(page.getByRole('heading', { name: 'Alerts' })).toBeVisible({ timeout: 5000 });

    await deleteAlertViaApi(alert.id);
  });
});
