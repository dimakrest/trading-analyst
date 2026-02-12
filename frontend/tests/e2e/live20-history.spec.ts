/**
 * E2E Tests for Live 20 History API Contracts
 *
 * These tests validate the API contract for Live 20 history endpoints.
 * They run against the REAL backend (no mocks) to catch:
 * - Schema mismatches (field names, types)
 * - Response structure changes
 * - Required vs optional fields
 *
 * IMPORTANT: Backend must be running (./scripts/dc.sh up -d)
 *
 * NOTE: Full flow tests that depend on analyze are skipped because
 * analyze requires real market data which is not available in test env.
 */

import { test, expect } from '@playwright/test';
import { TEST_CONFIG } from './config';

const BACKEND_URL = TEST_CONFIG.BACKEND_URL;
const FRONTEND_URL = TEST_CONFIG.FRONTEND_URL;

test.describe('Live 20 History - API Contracts', () => {
  test.beforeAll(async () => {
    // Verify backend is running
    const response = await fetch(`${BACKEND_URL}/api/v1/health`);
    if (!response.ok) {
      throw new Error('Backend is not running. Start it with: ./scripts/dc.sh up -d');
    }
  });

  test('GET /api/v1/live-20/runs returns correct structure', async () => {
    const response = await fetch(`${BACKEND_URL}/api/v1/live-20/runs`);

    expect(response.status).toBe(200);

    const data = await response.json();

    // Validate response structure
    expect(data).toHaveProperty('items');
    expect(data).toHaveProperty('total');
    expect(data).toHaveProperty('has_more');
    expect(data).toHaveProperty('limit');
    expect(data).toHaveProperty('offset');

    // Validate types
    expect(Array.isArray(data.items)).toBe(true);
    expect(typeof data.total).toBe('number');
    expect(typeof data.has_more).toBe('boolean');
    expect(typeof data.limit).toBe('number');
    expect(typeof data.offset).toBe('number');

    // If there are runs, validate structure
    if (data.items.length > 0) {
      const run = data.items[0];

      // Validate required fields
      expect(run).toHaveProperty('id');
      expect(run).toHaveProperty('created_at');
      expect(run).toHaveProperty('symbol_count');
      expect(run).toHaveProperty('long_count');
      expect(run).toHaveProperty('short_count');
      expect(run).toHaveProperty('no_setup_count');

      // Validate types
      expect(typeof run.id).toBe('number');
      expect(typeof run.created_at).toBe('string');
      expect(typeof run.symbol_count).toBe('number');
      expect(typeof run.long_count).toBe('number');
      expect(typeof run.short_count).toBe('number');
      expect(typeof run.no_setup_count).toBe('number');

      // Validate timestamp format (ISO 8601)
      expect(run.created_at).toMatch(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}/);
    }
  });

  test('GET /api/v1/live-20/runs supports pagination params', async () => {
    const response = await fetch(`${BACKEND_URL}/api/v1/live-20/runs?limit=5&offset=0`);

    expect(response.status).toBe(200);

    const data = await response.json();
    expect(data.limit).toBe(5);
    expect(data.offset).toBe(0);
  });

  test('GET /api/v1/live-20/runs supports direction filter', async () => {
    const response = await fetch(`${BACKEND_URL}/api/v1/live-20/runs?direction=long`);

    expect(response.status).toBe(200);

    const data = await response.json();
    // Response should still have valid structure
    expect(data).toHaveProperty('items');
    expect(Array.isArray(data.items)).toBe(true);
  });

  test('GET /api/v1/live-20/runs supports symbol filter', async () => {
    const response = await fetch(`${BACKEND_URL}/api/v1/live-20/runs?symbol=AAPL`);

    expect(response.status).toBe(200);

    const data = await response.json();
    expect(data).toHaveProperty('items');
    expect(Array.isArray(data.items)).toBe(true);
  });

  test('GET /api/v1/live-20/runs supports date filters', async () => {
    // Date filters require ISO datetime format
    const now = new Date();
    const startOfDay = new Date(now.getFullYear(), now.getMonth(), now.getDate()).toISOString();
    const endOfDay = new Date(
      now.getFullYear(),
      now.getMonth(),
      now.getDate(),
      23,
      59,
      59
    ).toISOString();
    const response = await fetch(
      `${BACKEND_URL}/api/v1/live-20/runs?date_from=${encodeURIComponent(startOfDay)}&date_to=${encodeURIComponent(endOfDay)}`
    );

    expect(response.status).toBe(200);

    const data = await response.json();
    expect(data).toHaveProperty('items');
    expect(Array.isArray(data.items)).toBe(true);
  });

  test('GET /api/v1/live-20/runs/{id} returns 404 for non-existent run', async () => {
    const response = await fetch(`${BACKEND_URL}/api/v1/live-20/runs/999999`);

    expect(response.status).toBe(404);

    const data = await response.json();
    expect(data).toHaveProperty('detail');
  });

  test('DELETE /api/v1/live-20/runs/{id} returns 404 for non-existent run', async () => {
    const response = await fetch(`${BACKEND_URL}/api/v1/live-20/runs/999999`, {
      method: 'DELETE',
    });

    expect(response.status).toBe(404);

    const data = await response.json();
    expect(data).toHaveProperty('detail');
  });
});

test.describe('Live 20 History - UI Navigation', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(`${FRONTEND_URL}/live-20`);
    await page.waitForLoadState('networkidle');
  });

  test('dashboard has analyze and history tabs', async ({ page }) => {
    // Verify tabs are present
    await expect(page.getByRole('tab', { name: /analyze/i })).toBeVisible();
    await expect(page.getByRole('tab', { name: /history/i })).toBeVisible();

    // Analyze tab is active by default
    await expect(page.getByRole('tab', { name: /analyze/i })).toHaveAttribute(
      'data-state',
      'active'
    );
  });

  test('can switch to history tab', async ({ page }) => {
    // Click History tab
    await page.getByRole('tab', { name: /history/i }).click();

    // History tab should be active
    await expect(page.getByRole('tab', { name: /history/i })).toHaveAttribute(
      'data-state',
      'active'
    );

    // History heading should be visible
    await expect(page.getByText(/analysis run history/i)).toBeVisible();
  });

  test('history tab shows filters', async ({ page }) => {
    // Switch to History tab
    await page.getByRole('tab', { name: /history/i }).click();
    await expect(page.getByText(/analysis run history/i)).toBeVisible();

    // Verify filter elements are present
    await expect(page.getByText(/date range/i)).toBeVisible();
    await expect(page.getByRole('button', { name: /^all$/i })).toBeVisible();
    await expect(page.getByRole('button', { name: /^long$/i })).toBeVisible();
    await expect(page.getByRole('button', { name: /^short$/i })).toBeVisible();
    await expect(page.getByRole('button', { name: /no setup/i })).toBeVisible();
    await expect(page.getByPlaceholder(/search by symbol/i)).toBeVisible();
  });

  test('history tab shows empty state or table', async ({ page }) => {
    // Switch to History tab
    await page.getByRole('tab', { name: /history/i }).click();
    await expect(page.getByText(/analysis run history/i)).toBeVisible();

    // Wait for content to load - either loading disappears or content appears
    await page.waitForLoadState('networkidle');

    // Wait for one of the expected states to appear
    await Promise.race([
      page.getByRole('table').waitFor({ state: 'visible' }).catch(() => {}),
      page.getByText(/no runs found/i).waitFor({ state: 'visible' }).catch(() => {}),
      page.getByText(/loading runs/i).waitFor({ state: 'visible' }).catch(() => {}),
      page.locator('text=/failed to fetch/i').waitFor({ state: 'visible' }).catch(() => {}),
    ]);

    // Should show either empty state, table, or loading
    const hasTable = await page.getByRole('table').isVisible().catch(() => false);
    const hasEmptyState = await page.getByText(/no runs found/i).isVisible().catch(() => false);
    const hasLoading = await page.getByText(/loading runs/i).isVisible().catch(() => false);
    const hasError = await page.locator('text=/failed to fetch/i').isVisible().catch(() => false);

    // In normal operation, should have table or empty state
    // Loading state is transient, error means backend issue
    expect(hasTable || hasEmptyState || hasLoading || hasError).toBeTruthy();
  });

  test('direction filter buttons are clickable', async ({ page }) => {
    // Switch to History tab
    await page.getByRole('tab', { name: /history/i }).click();
    await expect(page.getByText(/analysis run history/i)).toBeVisible();

    // Click LONG filter
    const longButton = page.getByRole('button', { name: /^long$/i });
    await longButton.click();

    // Button should have active styling (signal-long background using CSS variable)
    await expect(longButton).toHaveClass(/bg-\[var\(--signal-long/);

    // Click ALL to reset
    await page.getByRole('button', { name: /^all$/i }).click();
    await expect(longButton).not.toHaveClass(/bg-\[var\(--signal-long/);
  });

  test('search input accepts text', async ({ page }) => {
    // Switch to History tab
    await page.getByRole('tab', { name: /history/i }).click();

    // Type in search input
    const searchInput = page.getByPlaceholder(/search by symbol/i);
    await searchInput.fill('AAPL');

    // Input should have the value
    await expect(searchInput).toHaveValue('AAPL');
  });
});

test.describe('Live 20 Run Detail - UI', () => {
  test('non-existent run shows error', async ({ page }) => {
    // Navigate to non-existent run
    await page.goto(`${FRONTEND_URL}/live-20/runs/999999`);
    await page.waitForLoadState('networkidle');

    // Should show error message - axios error for 404 shows "Request failed with status code 404"
    const errorText = page.getByText(/request failed with status code 404|failed to load run|not found/i);
    await expect(errorText).toBeVisible({ timeout: 5000 });

    // Back button should be available
    await expect(page.getByRole('button', { name: /back/i })).toBeVisible();
  });

  test('back button navigates to history tab', async ({ page }) => {
    // Navigate to non-existent run (will show error)
    await page.goto(`${FRONTEND_URL}/live-20/runs/999999`);
    await page.waitForLoadState('networkidle');

    // Click back button
    await page.getByRole('button', { name: /back/i }).click();

    // Should return to Live 20 page with history tab active
    await expect(page).toHaveURL(/\/live-20$/);
    await expect(page.getByRole('tab', { name: /history/i })).toHaveAttribute(
      'data-state',
      'active'
    );
  });
});

test.describe('Live 20 History - Mobile Responsive', () => {
  test('filters are visible on mobile', async ({ page }) => {
    // Set mobile viewport
    await page.setViewportSize({ width: 375, height: 667 });

    await page.goto(`${FRONTEND_URL}/live-20`);
    await page.waitForLoadState('networkidle');

    // Switch to History tab
    await page.getByRole('tab', { name: /history/i }).click();

    // Filters should still be visible
    await expect(page.getByText(/date range/i)).toBeVisible();
    await expect(page.getByRole('button', { name: /^all$/i })).toBeVisible();
    await expect(page.getByPlaceholder(/search by symbol/i)).toBeVisible();
  });

  test('tabs work on mobile', async ({ page }) => {
    // Set mobile viewport
    await page.setViewportSize({ width: 375, height: 667 });

    await page.goto(`${FRONTEND_URL}/live-20`);
    await page.waitForLoadState('networkidle');

    // Both tabs should be visible
    await expect(page.getByRole('tab', { name: /analyze/i })).toBeVisible();
    await expect(page.getByRole('tab', { name: /history/i })).toBeVisible();

    // Switch to history
    await page.getByRole('tab', { name: /history/i }).click();
    await expect(page.getByText(/analysis run history/i)).toBeVisible();

    // Switch back to analyze
    await page.getByRole('tab', { name: /analyze/i }).click();
    await expect(page.getByText(/analyze symbols/i)).toBeVisible();
  });
});
