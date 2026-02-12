/**
 * E2E Tests for Live 20 Multi-List Selection Feature
 *
 * Tests the API contracts and UI behavior for selecting multiple stock lists
 * in Live 20 analysis. These tests validate:
 * - Backend accepts source_lists parameter
 * - Backend validation (500 symbol limit, 10 list limit)
 * - Backend backward compatibility with stock_list_id
 * - Multi-list selector UI presence and structure
 * - History displays source_lists correctly
 *
 * IMPORTANT: Backend must be running (./scripts/dc.sh up -d)
 *
 * NOTE: These tests do NOT run full analysis flows (requires real market data).
 * They focus on API contracts, UI presence, and data structure validation.
 */

import { test, expect } from '@playwright/test';
import { TEST_CONFIG } from './config';

const BACKEND_URL = TEST_CONFIG.BACKEND_URL;
const FRONTEND_URL = TEST_CONFIG.FRONTEND_URL;

test.describe('Live 20 Multi-List API Contracts', () => {
  // Clean up test lists before and after each test
  test.beforeEach(async () => {
    await cleanupTestLists();
  });

  test.afterEach(async () => {
    await cleanupTestLists();
  });

  test('POST /api/v1/live-20/analyze accepts source_lists parameter', async () => {
    // Create test lists
    const list1 = await createTestList('E2E Test Tech', ['AAPL', 'MSFT']);
    const list2 = await createTestList('E2E Test Energy', ['XOM', 'CVX']);

    const payload = {
      symbols: ['AAPL', 'MSFT', 'XOM', 'CVX'],
      source_lists: [
        { id: list1.id, name: list1.name },
        { id: list2.id, name: list2.name },
      ],
    };

    const response = await fetch(`${BACKEND_URL}/api/v1/live-20/analyze`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

    expect(response.status).toBe(200);

    const data = await response.json();
    expect(data).toHaveProperty('run_id');
    expect(data).toHaveProperty('status');
    expect(data.status).toBe('pending');
  });

  test('GET /api/v1/live-20/runs returns source_lists field', async () => {
    // Create test lists and run analysis
    const list1 = await createTestList('E2E Test Tech', ['AAPL', 'MSFT']);
    const list2 = await createTestList('E2E Test Energy', ['XOM', 'CVX']);

    const payload = {
      symbols: ['AAPL', 'MSFT', 'XOM', 'CVX'],
      source_lists: [
        { id: list1.id, name: list1.name },
        { id: list2.id, name: list2.name },
      ],
    };

    // Create a run
    await fetch(`${BACKEND_URL}/api/v1/live-20/analyze`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

    // Fetch runs
    const response = await fetch(`${BACKEND_URL}/api/v1/live-20/runs`);
    expect(response.status).toBe(200);

    const data = await response.json();
    expect(data).toHaveProperty('items');
    expect(Array.isArray(data.items)).toBe(true);

    // Find our run (most recent)
    if (data.items.length > 0) {
      const run = data.items[0];
      expect(run).toHaveProperty('source_lists');

      // Verify source_lists structure if present
      if (run.source_lists) {
        expect(Array.isArray(run.source_lists)).toBe(true);
        if (run.source_lists.length > 0) {
          const sourceList = run.source_lists[0];
          expect(sourceList).toHaveProperty('id');
          expect(sourceList).toHaveProperty('name');
          expect(typeof sourceList.id).toBe('number');
          expect(typeof sourceList.name).toBe('string');
        }
      }
    }
  });

  test('API enforces 500 symbol limit', async () => {
    // Generate 501 symbols
    const symbols = Array.from({ length: 501 }, (_, i) => `SYM${i.toString().padStart(3, '0')}`);

    const payload = {
      symbols,
    };

    const response = await fetch(`${BACKEND_URL}/api/v1/live-20/analyze`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

    // Should return 422 Unprocessable Entity
    expect(response.status).toBe(422);

    const data = await response.json();
    expect(data).toHaveProperty('detail');
  });

  test('API enforces 10 list limit', async () => {
    // Create 11 list references (IDs don't need to be real for this validation test)
    const lists = Array.from({ length: 11 }, (_, i) => ({
      id: i + 1,
      name: `List ${i + 1}`,
    }));

    const payload = {
      symbols: ['AAPL'],
      source_lists: lists,
    };

    const response = await fetch(`${BACKEND_URL}/api/v1/live-20/analyze`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

    // Should return 422 Unprocessable Entity
    expect(response.status).toBe(422);

    const data = await response.json();
    expect(data).toHaveProperty('detail');
  });

  test('API rejects both stock_list_id and source_lists', async () => {
    const list = await createTestList('E2E Test', ['AAPL']);

    const payload = {
      symbols: ['AAPL'],
      stock_list_id: list.id,
      stock_list_name: list.name,
      source_lists: [{ id: list.id, name: list.name }],
    };

    const response = await fetch(`${BACKEND_URL}/api/v1/live-20/analyze`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

    // Should return 422 Unprocessable Entity
    expect(response.status).toBe(422);

    const data = await response.json();
    expect(data).toHaveProperty('detail');
    // Error message should mention both formats cannot be used
    expect(JSON.stringify(data.detail).toLowerCase()).toContain('both');
  });

  test('API maintains backward compatibility with stock_list_id', async () => {
    const list = await createTestList('E2E Test Legacy', ['AAPL', 'MSFT']);

    const payload = {
      symbols: ['AAPL', 'MSFT'],
      stock_list_id: list.id,
      stock_list_name: list.name,
    };

    const response = await fetch(`${BACKEND_URL}/api/v1/live-20/analyze`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

    expect(response.status).toBe(200);

    const data = await response.json();
    expect(data).toHaveProperty('run_id');
    expect(data.status).toBe('pending');
  });
});

test.describe('Live 20 Multi-List UI - Analyze Tab', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(`${FRONTEND_URL}/live-20`);
    await page.waitForLoadState('networkidle');
  });

  test('multi-list selector is present on analyze tab', async ({ page }) => {
    // Verify we're on the Analyze tab
    await expect(page.getByRole('tab', { name: /analyze/i })).toHaveAttribute(
      'data-state',
      'active'
    );

    // Multi-list selector should be present (look for "Load from Lists" label)
    await expect(page.getByText(/load from lists/i)).toBeVisible();

    // Verify the dropdown button is present - it may have different states
    // (Loading lists..., Select lists..., X lists selected)
    const selector = page.locator('button').filter({ hasText: /lists/i }).first();
    await expect(selector).toBeVisible();
  });

  test('multi-list selector shows loading state', async ({ page }) => {
    // Check for the dropdown button with any state
    const selector = page.locator('button').filter({ hasText: /lists/i }).first();
    await expect(selector).toBeVisible();

    const buttonText = (await selector.textContent()) || '';

    // Should show some variation of list-related text
    // (Loading lists..., Select lists..., X lists selected, or X list selected)
    expect(buttonText.toLowerCase()).toMatch(/list/);
  });

  test('multi-list selector dropdown can be opened', async ({ page }) => {
    // Wait for dropdown button to be ready (not in loading state)
    const dropdownButton = page.locator('button').filter({ hasText: /lists/i }).first();
    await expect(dropdownButton).toBeVisible();

    // Wait for lists to finish loading (button text should not contain "Loading")
    await expect(dropdownButton).not.toContainText('Loading', { timeout: 10000 });

    // Click the dropdown button
    await dropdownButton.click();

    // Wait for dropdown menu to appear - race to find any expected element
    await Promise.race([
      page.getByText(/no lists available/i).waitFor({ state: 'visible' }).catch(() => {}),
      page.locator('[role="menuitemcheckbox"]').first().waitFor({ state: 'visible' }).catch(() => {}),
      page.getByText(/select lists/i).waitFor({ state: 'visible' }).catch(() => {}),
    ]);

    // Should show either "No lists available" or list items or heading
    const hasNoLists = await page.getByText(/no lists available/i).isVisible().catch(() => false);
    const hasListItems = await page
      .locator('[role="menuitemcheckbox"]')
      .first()
      .isVisible()
      .catch(() => false);
    const hasHeading = await page.getByText(/select lists/i).isVisible().catch(() => false);

    expect(hasNoLists || hasListItems || hasHeading).toBe(true);
  });

  test('symbol count badge shows X/500 format', async ({ page }) => {
    // Type some symbols into the textarea
    const textarea = page.getByPlaceholder(/search for stocks|aapl, msft/i);
    await textarea.fill('AAPL, MSFT, GOOGL');

    // Wait for count to update (event-driven)
    await expect(page.getByText(/3\/500/)).toBeVisible();
  });
});

test.describe('Live 20 Multi-List - History Display', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(`${FRONTEND_URL}/live-20`);
    await page.waitForLoadState('networkidle');

    // Switch to History tab
    await page.getByRole('tab', { name: /history/i }).click();
    await expect(page.getByText(/analysis run history/i)).toBeVisible();
  });

  test('history run summary includes source_lists type check', async () => {
    // Fetch runs directly from API to verify structure
    const response = await fetch(`${BACKEND_URL}/api/v1/live-20/runs`);
    expect(response.status).toBe(200);

    const data = await response.json();
    expect(data).toHaveProperty('items');

    // Verify source_lists field is present in schema (even if null)
    if (data.items.length > 0) {
      const run = data.items[0];
      // Field should exist (may be null, empty array, or have data)
      expect('source_lists' in run).toBe(true);

      // If source_lists is present and has data, verify structure
      if (run.source_lists && run.source_lists.length > 0) {
        expect(Array.isArray(run.source_lists)).toBe(true);
        const sourceList = run.source_lists[0];
        expect(sourceList).toHaveProperty('id');
        expect(sourceList).toHaveProperty('name');
      }
    }
  });
});

test.describe('Live 20 Multi-List - Mobile Responsive', () => {
  test('multi-list selector is visible on mobile', async ({ page }) => {
    // Set mobile viewport
    await page.setViewportSize({ width: 375, height: 667 });

    await page.goto(`${FRONTEND_URL}/live-20`);
    await page.waitForLoadState('networkidle');

    // Multi-list selector should be visible
    await expect(page.getByText(/load from lists/i)).toBeVisible();

    // Verify the dropdown button is visible with flexible selector
    const selector = page.locator('button').filter({ hasText: /lists/i }).first();
    await expect(selector).toBeVisible();
  });

  test('symbol count badge is visible on mobile', async ({ page }) => {
    // Set mobile viewport
    await page.setViewportSize({ width: 375, height: 667 });

    await page.goto(`${FRONTEND_URL}/live-20`);
    await page.waitForLoadState('networkidle');

    // Type symbols
    const textarea = page.getByPlaceholder(/search for stocks|aapl, msft/i);
    await textarea.fill('AAPL, MSFT');

    // Wait for count to update
    await page.waitForTimeout(300);

    // Badge should be visible
    await expect(page.getByText(/2\/500/)).toBeVisible();
  });
});

// Helper functions

/**
 * Clean up all test lists with "E2E Test" prefix
 */
async function cleanupTestLists(): Promise<void> {
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
}

/**
 * Create a test list via API with unique name
 */
async function createTestList(
  name: string,
  symbols: string[]
): Promise<{ id: number; name: string }> {
  // Make name unique by appending timestamp
  const uniqueName = `${name} ${Date.now()}`;

  const response = await fetch(`${BACKEND_URL}/api/v1/stock-lists`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name: uniqueName, symbols }),
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(
      `Failed to create test list: ${response.status} - ${JSON.stringify(errorData)}`
    );
  }

  return await response.json();
}
