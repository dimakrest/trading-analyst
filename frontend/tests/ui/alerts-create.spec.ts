/**
 * UI Tests for Create Alert Dialog
 *
 * These tests use page.route() to mock backend responses and validate
 * the CreateAlertDialog component: form structure, client-side validation,
 * successful submission flows, server error handling, and advanced settings.
 *
 * All tests mock GET /api/v1/alerts/ with mockAlertList for the initial
 * dashboard load, then add per-test POST mocks as needed.
 *
 * Route: /alerts (AlertsDashboard → CreateAlertDialog)
 * API calls:
 *   GET  /api/v1/alerts/           → initial list
 *   POST /api/v1/alerts/           → create alert
 */

import { test, expect } from '@playwright/test';
import {
  mockAlertList,
  mockCreatedFibResponse,
  mockCreatedMAResponse,
} from '../fixtures/mockAlertData';

// ---------------------------------------------------------------------------
// Helper: set up GET /api/v1/alerts/ mock for initial dashboard load
// ---------------------------------------------------------------------------

const setupMocks = async (page: import('@playwright/test').Page) => {
  await page.route('**/api/v1/alerts/', async (route) => {
    if (route.request().method() === 'GET') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(mockAlertList),
      });
    } else {
      await route.continue();
    }
  });
};

// ---------------------------------------------------------------------------
// Helper: open the Create Alert dialog from /alerts
// ---------------------------------------------------------------------------

const openDialog = async (page: import('@playwright/test').Page) => {
  await page.goto('/alerts');
  await page.waitForLoadState('networkidle');
  await page.getByRole('button', { name: 'Add Alert' }).first().click();
  await expect(page.getByRole('dialog')).toBeVisible();
};

// ---------------------------------------------------------------------------
// Test suite: Create Alert Dialog - Fibonacci
// ---------------------------------------------------------------------------

test.describe('Create Alert Dialog - Fibonacci', () => {
  test.beforeEach(async ({ page }) => {
    await setupMocks(page);
  });

  test('1. opens dialog when clicking Add Alert', async ({ page }) => {
    await page.goto('/alerts');
    await page.waitForLoadState('networkidle');

    await page.getByRole('button', { name: 'Add Alert' }).first().click();

    const dialog = page.getByRole('dialog');
    await expect(dialog).toBeVisible();
    await expect(dialog.getByRole('heading', { name: 'Add Alert' })).toBeVisible();

    // Symbol input is visible
    await expect(page.locator('#alert-symbol')).toBeVisible();

    // Fibonacci toggle is selected by default (data-state=on)
    const fibToggle = page.getByRole('radio', { name: 'Fibonacci retracement alert' });
    await expect(fibToggle).toBeVisible();
    await expect(fibToggle).toHaveAttribute('data-state', 'on');
  });

  test('2. creates Fibonacci alert with default levels', async ({ page }) => {
    // Updated alert list includes the newly created AAPL alert
    const updatedList = {
      items: [...mockAlertList.items, ...mockCreatedFibResponse],
      total: mockAlertList.total + mockCreatedFibResponse.length,
    };

    // Mock POST → return created alert
    await page.route('**/api/v1/alerts/', async (route) => {
      if (route.request().method() === 'POST') {
        await route.fulfill({
          status: 201,
          contentType: 'application/json',
          body: JSON.stringify(mockCreatedFibResponse),
        });
      } else if (route.request().method() === 'GET') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(updatedList),
        });
      } else {
        await route.continue();
      }
    });

    await openDialog(page);

    // Fill symbol
    await page.locator('#alert-symbol').fill('AAPL');

    // Confirm Fibonacci type is selected
    await expect(
      page.getByRole('radio', { name: 'Fibonacci retracement alert' })
    ).toHaveAttribute('data-state', 'on');

    // Default levels 38.2%, 50%, 61.8% are checked
    await expect(page.getByRole('checkbox', { name: '38.2%' })).toHaveAttribute(
      'aria-checked',
      'true'
    );
    await expect(page.getByRole('checkbox', { name: '50%' })).toHaveAttribute(
      'aria-checked',
      'true'
    );
    await expect(page.getByRole('checkbox', { name: '61.8%' })).toHaveAttribute(
      'aria-checked',
      'true'
    );

    // Submit
    await page.getByRole('dialog').getByRole('button', { name: 'Add Alert' }).click();

    // Dialog closes
    await expect(page.getByRole('dialog')).not.toBeVisible();

    // AAPL row(s) appear in the table (original + newly created)
    await expect(
      page.getByRole('button', { name: /View details for AAPL/ }).first()
    ).toBeVisible();
  });

  test('3. prevents submission when no symbol entered', async ({ page }) => {
    await openDialog(page);

    // Leave symbol empty, submit
    await page.getByRole('dialog').getByRole('button', { name: 'Add Alert' }).click();

    // Error visible inside dialog
    const error = page.getByRole('dialog').getByRole('alert');
    await expect(error).toBeVisible();
    await expect(error).toHaveText(/symbol is required/i);

    // Dialog stays open
    await expect(page.getByRole('dialog')).toBeVisible();
  });

  test('4. prevents submission when zero Fibonacci levels selected', async ({ page }) => {
    await openDialog(page);

    await page.locator('#alert-symbol').fill('AAPL');

    // Uncheck all three default levels
    await page.getByRole('checkbox', { name: '38.2%' }).click();
    await page.getByRole('checkbox', { name: '50%' }).click();
    await page.getByRole('checkbox', { name: '61.8%' }).click();

    await page.getByRole('dialog').getByRole('button', { name: 'Add Alert' }).click();

    const error = page.getByRole('dialog').getByRole('alert');
    await expect(error).toBeVisible();
    await expect(error).toHaveText(/select at least one fibonacci level/i);

    // Dialog stays open
    await expect(page.getByRole('dialog')).toBeVisible();
  });

  test('5. shows server error in dialog when API returns 400', async ({ page }) => {
    await page.route('**/api/v1/alerts/', async (route) => {
      if (route.request().method() === 'POST') {
        await route.fulfill({
          status: 400,
          contentType: 'application/json',
          body: JSON.stringify({ detail: 'Symbol not found' }),
        });
      } else {
        await route.continue();
      }
    });

    await openDialog(page);

    await page.locator('#alert-symbol').fill('INVALID');
    await page.getByRole('dialog').getByRole('button', { name: 'Add Alert' }).click();

    // Server error rendered inside dialog
    const error = page.getByRole('dialog').getByRole('alert');
    await expect(error).toBeVisible();

    // Dialog stays open
    await expect(page.getByRole('dialog')).toBeVisible();
  });

  test('6. cancel button closes dialog without API call', async ({ page }) => {
    let postCallCount = 0;

    await page.route('**/api/v1/alerts/', async (route) => {
      if (route.request().method() === 'POST') {
        postCallCount++;
        await route.fulfill({
          status: 201,
          contentType: 'application/json',
          body: JSON.stringify(mockCreatedFibResponse),
        });
      } else {
        await route.continue();
      }
    });

    await openDialog(page);

    await page.locator('#alert-symbol').fill('AAPL');
    await page.getByRole('button', { name: 'Cancel' }).click();

    // Dialog is dismissed
    await expect(page.getByRole('dialog')).not.toBeVisible();

    // No POST was made
    expect(postCallCount).toBe(0);
  });
});

// ---------------------------------------------------------------------------
// Test suite: Create Alert Dialog - Moving Average
// ---------------------------------------------------------------------------

test.describe('Create Alert Dialog - Moving Average', () => {
  test.beforeEach(async ({ page }) => {
    await setupMocks(page);
  });

  test('7. creates MA alert with selected periods', async ({ page }) => {
    const updatedList = {
      items: [...mockAlertList.items, ...mockCreatedMAResponse],
      total: mockAlertList.total + mockCreatedMAResponse.length,
    };

    await page.route('**/api/v1/alerts/', async (route) => {
      if (route.request().method() === 'POST') {
        await route.fulfill({
          status: 201,
          contentType: 'application/json',
          body: JSON.stringify(mockCreatedMAResponse),
        });
      } else if (route.request().method() === 'GET') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(updatedList),
        });
      } else {
        await route.continue();
      }
    });

    await openDialog(page);

    await page.locator('#alert-symbol').fill('NVDA');

    // Switch to Moving Average type
    await page.getByRole('radio', { name: 'Moving average alert' }).click();
    await expect(
      page.getByRole('radio', { name: 'Moving average alert' })
    ).toHaveAttribute('data-state', 'on');

    // MA50 is checked by default; also check MA200
    await expect(page.getByRole('checkbox', { name: 'MA50' })).toHaveAttribute(
      'aria-checked',
      'true'
    );
    await page.getByRole('checkbox', { name: 'MA200' }).click();
    await expect(page.getByRole('checkbox', { name: 'MA200' })).toHaveAttribute(
      'aria-checked',
      'true'
    );

    await page.getByRole('dialog').getByRole('button', { name: 'Add Alert' }).click();

    // Dialog closes on success
    await expect(page.getByRole('dialog')).not.toBeVisible();
  });

  test('8. prevents submission when zero MA periods selected', async ({ page }) => {
    await openDialog(page);

    await page.locator('#alert-symbol').fill('NVDA');

    // Switch to Moving Average type
    await page.getByRole('radio', { name: 'Moving average alert' }).click();

    // Uncheck the default MA50
    await page.getByRole('checkbox', { name: 'MA50' }).click();
    await expect(page.getByRole('checkbox', { name: 'MA50' })).toHaveAttribute(
      'aria-checked',
      'false'
    );

    await page.getByRole('dialog').getByRole('button', { name: 'Add Alert' }).click();

    const error = page.getByRole('dialog').getByRole('alert');
    await expect(error).toBeVisible();
    await expect(error).toHaveText(/select at least one moving average/i);

    // Dialog stays open
    await expect(page.getByRole('dialog')).toBeVisible();
  });

  test('9. MA direction selector defaults to "both"', async ({ page }) => {
    await openDialog(page);

    // Switch to Moving Average type
    await page.getByRole('radio', { name: 'Moving average alert' }).click();

    // Direction select trigger shows "Both directions" (the SelectItem label for value="both")
    const directionTrigger = page.locator('#ma-direction');
    await expect(directionTrigger).toBeVisible();
    await expect(directionTrigger).toContainText('Both directions');
  });
});

// ---------------------------------------------------------------------------
// Test suite: Create Alert Dialog - Advanced Settings
// ---------------------------------------------------------------------------

test.describe('Create Alert Dialog - Advanced Settings', () => {
  test.beforeEach(async ({ page }) => {
    await setupMocks(page);
  });

  test('10. advanced settings are collapsed by default', async ({ page }) => {
    await openDialog(page);

    // Tolerance input not visible when section is collapsed
    await expect(page.locator('#tolerance-pct')).not.toBeVisible();

    // The toggle button itself is visible
    await expect(page.getByText(/advanced settings/i)).toBeVisible();
  });

  test('11. clicking advanced settings reveals tolerance input', async ({ page }) => {
    await openDialog(page);

    await page.getByText(/advanced settings/i).click();

    // Tolerance input is now visible with default value 0.5
    const toleranceInput = page.locator('#tolerance-pct');
    await expect(toleranceInput).toBeVisible();
    await expect(toleranceInput).toHaveValue('0.5');
  });

  test('12. shows submitting state on button while creating', async ({ page }) => {
    // Mock POST with a 1-second delay so the submitting state is observable
    await page.route('**/api/v1/alerts/', async (route) => {
      if (route.request().method() === 'POST') {
        await new Promise((resolve) => setTimeout(resolve, 1000));
        await route.fulfill({
          status: 201,
          contentType: 'application/json',
          body: JSON.stringify(mockCreatedFibResponse),
        });
      } else {
        await route.continue();
      }
    });

    await openDialog(page);

    await page.locator('#alert-symbol').fill('AAPL');

    // Click submit — do not await the dialog closing
    await page.getByRole('dialog').getByRole('button', { name: 'Add Alert' }).click();

    // While the POST is in flight the button text should change to "Adding..."
    await expect(
      page.getByRole('dialog').getByRole('button', { name: 'Adding...' })
    ).toBeVisible();
  });
});
