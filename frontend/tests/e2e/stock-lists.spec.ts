/**
 * Stock Lists Feature E2E Tests
 *
 * Tests the complete Stock Lists feature including:
 * - CRUD operations (Create, Read, Update, Delete)
 * - Integration with Stock Analysis page
 * - Mobile navigation
 */

import { test, expect } from '@playwright/test';
import { TEST_CONFIG } from './config';

const FRONTEND_URL = TEST_CONFIG.FRONTEND_URL;
const BACKEND_URL = TEST_CONFIG.BACKEND_URL;

test.describe('Stock Lists Feature', () => {
  test.beforeAll(async () => {
    // Verify backend is running
    const backendCheck = await fetch(`${BACKEND_URL}/docs`);
    if (!backendCheck.ok) {
      throw new Error('Backend is not running. Start it with: ./scripts/dc.sh up -d');
    }
  });

  test.describe('Stock Lists Page CRUD', () => {
    // Clean up any test lists before each test
    test.beforeEach(async () => {
      // Get all existing lists and delete any with "E2E Test" prefix
      const response = await fetch(`${BACKEND_URL}/api/v1/stock-lists`);
      if (response.ok) {
        const data = await response.json();
        for (const list of data.items) {
          if (list.name.startsWith('E2E Test')) {
            await fetch(`${BACKEND_URL}/api/v1/stock-lists/${list.id}`, {
              method: 'DELETE',
            });
          }
        }
      }
    });

    test('displays empty state when no lists exist', async ({ page }) => {
      // Clean up all lists first
      const response = await fetch(`${BACKEND_URL}/api/v1/stock-lists`);
      if (response.ok) {
        const data = await response.json();
        for (const list of data.items) {
          await fetch(`${BACKEND_URL}/api/v1/stock-lists/${list.id}`, {
            method: 'DELETE',
          });
        }
      }

      await page.goto(`${FRONTEND_URL}/lists`);

      // Should show empty state
      await expect(page.getByText('No stock lists yet')).toBeVisible({ timeout: 10000 });
      await expect(
        page.getByText('Create your first list to organize symbols for quick analysis')
      ).toBeVisible();
    });

    test('can create a new stock list', async ({ page }) => {
      await page.goto(`${FRONTEND_URL}/lists`);

      // Click Create List button (button text is "Create List", dialog heading is "Create New List")
      await page.getByRole('button', { name: /^create list$/i }).click();

      // Dialog should open - use role heading for more specific match
      await expect(page.getByRole('heading', { name: 'Create New List' })).toBeVisible();

      // Fill in the form
      await page.getByLabel(/list name/i).fill('E2E Test Watchlist');
      await page.getByLabel(/symbols/i).fill('AAPL, MSFT, GOOGL');

      // Submit
      await page.getByRole('button', { name: /^create list$/i }).click();

      // Dialog should close and list should appear in the table
      // Use specific table cell selector to avoid matching toast notification
      await expect(
        page.getByRole('row').filter({ hasText: 'E2E Test Watchlist' })
      ).toBeVisible({ timeout: 5000 });
      await expect(page.getByRole('cell', { name: '3 symbols' })).toBeVisible();
    });

    test('can edit a stock list', async ({ page }) => {
      // Create a list via API first
      const createResponse = await fetch(`${BACKEND_URL}/api/v1/stock-lists`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: 'E2E Test Edit List',
          symbols: ['AAPL', 'MSFT'],
        }),
      });
      expect(createResponse.ok).toBe(true);

      await page.goto(`${FRONTEND_URL}/lists`);

      // Wait for list to appear
      await expect(page.getByText('E2E Test Edit List')).toBeVisible({ timeout: 5000 });

      // Click Edit button (use aria-label that starts with "Edit" to avoid matching "Delete")
      await page.getByRole('row', { name: /e2e test edit list/i }).locator('button[aria-label^="Edit"]').click();

      // Dialog should open with existing data - use role heading for specific match
      await expect(page.getByRole('heading', { name: 'Edit List' })).toBeVisible();
      // Verify the name input has the existing list name
      await expect(page.getByLabel(/list name/i)).toHaveValue('E2E Test Edit List');

      // Change name
      await page.getByLabel(/list name/i).clear();
      await page.getByLabel(/list name/i).fill('E2E Test Updated List');

      // Add a new symbol - fill the input and click Add button
      await page.getByLabel(/add symbols/i).fill('TSLA');
      await page.getByRole('button', { name: /^add$/i }).click();

      // Verify the new symbol appears in the list before saving
      await expect(page.getByText('TSLA')).toBeVisible();

      // Submit
      await page.getByRole('button', { name: /save changes/i }).click();

      // Updated name should appear
      await expect(page.getByText('E2E Test Updated List')).toBeVisible({ timeout: 5000 });
      await expect(page.getByText('3 symbols')).toBeVisible();
    });

    test('can delete a stock list with confirmation', async ({ page }) => {
      // Create a list via API first
      const createResponse = await fetch(`${BACKEND_URL}/api/v1/stock-lists`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: 'E2E Test Delete List',
          symbols: ['NVDA'],
        }),
      });
      expect(createResponse.ok).toBe(true);

      await page.goto(`${FRONTEND_URL}/lists`);

      // Wait for list to appear
      await expect(page.getByText('E2E Test Delete List')).toBeVisible({ timeout: 5000 });

      // Click Delete button (use aria-label that starts with "Delete")
      await page.getByRole('row', { name: /e2e test delete list/i }).locator('button[aria-label^="Delete"]').click();

      // Confirmation dialog should appear (heading is "Delete List" not "Delete List?")
      await expect(page.getByRole('alertdialog')).toBeVisible();
      await expect(page.getByRole('heading', { name: 'Delete List' })).toBeVisible();

      // Confirm deletion
      await page.getByRole('button', { name: /delete list/i }).click();

      // Wait for dialog to close first
      await expect(page.getByRole('alertdialog')).not.toBeVisible({ timeout: 5000 });

      // List row should no longer be in the table
      await expect(
        page.getByRole('row').filter({ hasText: 'E2E Test Delete List' })
      ).not.toBeVisible({ timeout: 5000 });
    });

    test('prevents duplicate list names', async ({ page }) => {
      // Create a list via API first
      await fetch(`${BACKEND_URL}/api/v1/stock-lists`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: 'E2E Test Duplicate',
          symbols: ['AAPL'],
        }),
      });

      await page.goto(`${FRONTEND_URL}/lists`);

      // Wait for the existing list to load
      await expect(page.getByText('E2E Test Duplicate')).toBeVisible({ timeout: 5000 });

      // Try to create another list with the same name
      await page.getByRole('button', { name: /^create list$/i }).click();
      await page.getByLabel(/list name/i).fill('E2E Test Duplicate');
      await page.getByRole('button', { name: /^create list$/i }).click();

      // Should show error message in the dialog (API returns 400 with "already exists" message)
      // Scope to dialog to avoid matching toast notification
      await expect(
        page.getByRole('dialog').getByText(/already exists/i)
      ).toBeVisible({ timeout: 5000 });
    });
  });

  test.describe('Stock Analysis Integration', () => {
    test.beforeEach(async () => {
      // Create a test list for analysis integration
      // First clean up
      const response = await fetch(`${BACKEND_URL}/api/v1/stock-lists`);
      if (response.ok) {
        const data = await response.json();
        for (const list of data.items) {
          if (list.name.startsWith('E2E Test')) {
            await fetch(`${BACKEND_URL}/api/v1/stock-lists/${list.id}`, {
              method: 'DELETE',
            });
          }
        }
      }

      // Create a fresh test list
      await fetch(`${BACKEND_URL}/api/v1/stock-lists`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: 'E2E Test Analysis',
          symbols: ['AAPL', 'TSLA', 'NVDA'],
        }),
      });
    });

    test('can select a list in Stock Analysis and see symbol chips', async ({ page }) => {
      await page.goto(FRONTEND_URL);

      // Wait for the page to load
      await expect(page.getByPlaceholder(/search for stocks/i)).toBeVisible({ timeout: 10000 });

      // Open the list selector dropdown
      await page.getByRole('combobox', { name: /list/i }).click();

      // Select the test list
      await page.getByRole('option', { name: /E2E Test Analysis/i }).click();

      // Symbol chips should appear
      await expect(page.getByRole('button', { name: 'AAPL' })).toBeVisible({ timeout: 5000 });
      await expect(page.getByRole('button', { name: 'TSLA' })).toBeVisible();
      await expect(page.getByRole('button', { name: 'NVDA' })).toBeVisible();
    });

    test('clicking a symbol chip loads that stock', async ({ page }) => {
      await page.goto(FRONTEND_URL);

      // Wait for the page to load
      await expect(page.getByPlaceholder(/search for stocks/i)).toBeVisible({ timeout: 10000 });

      // Open the list selector dropdown and select the test list
      await page.getByRole('combobox', { name: /list/i }).click();
      await page.getByRole('option', { name: /E2E Test Analysis/i }).click();

      // Wait for chips to appear
      await expect(page.getByRole('button', { name: 'TSLA' })).toBeVisible({ timeout: 5000 });

      // Wait for first symbol (AAPL) to fully load before clicking another
      // This prevents race condition where click happens during initial load
      await expect(page.getByTestId('stock-hero-symbol')).toHaveText('AAPL', { timeout: 15000 });

      // Click on TSLA chip
      await page.getByRole('button', { name: 'TSLA' }).click();

      // The stock display should show TSLA (symbol is in a span with data-testid="stock-hero-symbol")
      await expect(page.getByTestId('stock-hero-symbol')).toHaveText('TSLA', { timeout: 15000 });
    });

    test('active symbol chip is highlighted', async ({ page }) => {
      await page.goto(FRONTEND_URL);

      // Wait for the page to load
      await expect(page.getByPlaceholder(/search for stocks/i)).toBeVisible({ timeout: 10000 });

      // Open the list selector and select test list
      await page.getByRole('combobox', { name: /list/i }).click();
      await page.getByRole('option', { name: /E2E Test Analysis/i }).click();

      // First symbol should be auto-loaded and highlighted
      await expect(page.getByRole('button', { name: 'AAPL' })).toBeVisible({ timeout: 5000 });

      // Wait for stock to load (symbol is in a span with data-testid="stock-hero-symbol")
      await expect(page.getByTestId('stock-hero-symbol')).toHaveText('AAPL', { timeout: 15000 });

      // AAPL chip should be active (has accent-primary-muted class and aria-pressed=true)
      const aaplChip = page.getByRole('button', { name: 'AAPL' });
      await expect(aaplChip).toHaveClass(/bg-accent-primary-muted/);
      await expect(aaplChip).toHaveAttribute('aria-pressed', 'true');

      // Click TSLA
      await page.getByRole('button', { name: 'TSLA' }).click();
      await expect(page.getByTestId('stock-hero-symbol')).toHaveText('TSLA', { timeout: 15000 });

      // Now TSLA should be active, AAPL should not be
      const tslaChip = page.getByRole('button', { name: 'TSLA' });
      await expect(tslaChip).toHaveClass(/bg-accent-primary-muted/);
      await expect(tslaChip).toHaveAttribute('aria-pressed', 'true');
      await expect(aaplChip).not.toHaveClass(/bg-accent-primary-muted/);
      await expect(aaplChip).toHaveAttribute('aria-pressed', 'false');
    });
  });

  test.describe('Mobile Navigation', () => {
    test.use({ viewport: { width: 375, height: 667 } }); // iPhone SE viewport

    test('Lists is visible in bottom navigation on mobile', async ({ page }) => {
      await page.goto(FRONTEND_URL);

      // Should see the Lists button in bottom nav
      await expect(page.getByRole('link', { name: /lists/i })).toBeVisible({
        timeout: 5000,
      });
    });

    test('can navigate to Lists page from bottom nav', async ({ page }) => {
      await page.goto(FRONTEND_URL);

      // Click Lists in bottom nav
      await page.getByRole('link', { name: /lists/i }).click();

      // Should navigate to Lists page
      await expect(page).toHaveURL(/\/lists/);
      await expect(page.getByText('Stock Lists')).toBeVisible({ timeout: 5000 });
    });

    test('Lists button is highlighted when on Lists page', async ({ page }) => {
      await page.goto(`${FRONTEND_URL}/lists`);

      // Lists button should have active styling (redesigned UI uses text-accent-primary)
      const listsLink = page.getByRole('link', { name: /lists/i });
      await expect(listsLink).toHaveClass(/text-accent-primary/);
    });
  });
});
