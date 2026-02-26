/**
 * Full E2E User Flow Integration Tests (Real Backend)
 *
 * These tests validate complete user journeys from UI to backend and back.
 * Unlike mocked E2E tests, these hit the REAL backend to catch:
 * - Full data flow breaks
 * - Real API timing issues
 * - Actual error handling
 * - localStorage + real backend interactions
 *
 * IMPORTANT:
 * - Backend must be running (./scripts/dc.sh up -d)
 * - Ports configured in .env.dev (auto-generated)
 * - No API mocks - tests real system integration
 */

import { test, expect } from '@playwright/test';
import { TEST_CONFIG } from './config';

const FRONTEND_URL = TEST_CONFIG.FRONTEND_URL;
const BACKEND_URL = TEST_CONFIG.BACKEND_URL;

test.describe('Full E2E User Flows (Real Backend)', () => {
  test.beforeAll(async () => {
    // Verify backend is running
    const backendCheck = await fetch(`${BACKEND_URL}/docs`);
    if (!backendCheck.ok) {
      throw new Error('Backend is not running. Start it with: docker-compose up');
    }
  });

  test.beforeEach(async ({ page }) => {
    // Clear localStorage to ensure clean state
    await page.goto(FRONTEND_URL);
    await page.evaluate(() => localStorage.clear());
  });

  test('User can search for stock and see chart with real data', async ({ page }) => {
    // Navigate to app
    await page.goto(FRONTEND_URL);

    // Search for stock
    const searchInput = page.getByPlaceholder(/search for stocks/i);
    await searchInput.fill('AAPL');
    await searchInput.press('Enter');

    // Wait for chart to load from real backend API
    const chart = page.getByRole('img', { name: /candlestick chart/i });
    await expect(chart).toBeVisible({ timeout: 10000 });

    // Verify stock info header displays real price data
    const stockSymbol = page.getByText('AAPL', { exact: true }).first();
    await expect(stockSymbol).toBeVisible();

    // Verify price is displayed (format: $XXX.XX) in the stock info section
    // Find price by looking for text that follows "Current Price" label
    const priceDisplay = page.getByText(/^\$[0-9,.]+$/).first();
    await expect(priceDisplay).toBeVisible({ timeout: 10000 });

    // Verify it actually contains a price (starts with $)
    const priceText = await priceDisplay.textContent();
    expect(priceText).toMatch(/^\$[0-9,.]+$/);
  });

  // NOTE: Pattern detector UI tests moved to e2e/tests/pattern-detectors.spec.ts
  // Those tests use mocked backend for reliable UI testing.
  // This suite focuses on full system integration with real backend.

  test('Error handling works for invalid stock symbol', async ({ page }) => {
    await page.goto(FRONTEND_URL);

    // Search for invalid stock
    await page.getByPlaceholder(/search for stocks/i).fill('INVALID999');
    await page.getByPlaceholder(/search for stocks/i).press('Enter');

    // Should show error from real backend
    const errorMessage = page.getByText(/error/i);
    await expect(errorMessage).toBeVisible({ timeout: 5000 });

    // Error should contain meaningful message from backend
    const errorText = await errorMessage.textContent();
    expect(errorText).toBeTruthy();
    expect(errorText?.toLowerCase()).toContain('error');
  });

  test('Multiple stocks can be searched sequentially', async ({ page }) => {
    await page.goto(FRONTEND_URL);

    // Search for first stock
    await page.getByPlaceholder(/search for stocks/i).fill('AAPL');
    await page.getByPlaceholder(/search for stocks/i).press('Enter');
    await expect(page.getByText('AAPL', { exact: true }).first()).toBeVisible({ timeout: 10000 });

    // Search for second stock
    await page.getByPlaceholder(/search for stocks/i).fill('TSLA');
    await page.getByPlaceholder(/search for stocks/i).press('Enter');
    await expect(page.getByText('TSLA', { exact: true }).first()).toBeVisible({ timeout: 10000 });

    // Verify chart updated with new stock
    const chart = page.getByRole('img', { name: /candlestick chart for TSLA/i });
    await expect(chart).toBeVisible();
  });

  test('Real backend performance - stock data loads within acceptable time', async ({ page }) => {
    await page.goto(FRONTEND_URL);

    const startTime = Date.now();

    // Search for stock
    await page.getByPlaceholder(/search for stocks/i).fill('AAPL');
    await page.getByPlaceholder(/search for stocks/i).press('Enter');

    // Wait for chart to load
    await expect(page.getByRole('img', { name: /candlestick chart/i })).toBeVisible({ timeout: 10000 });

    const loadTime = Date.now() - startTime;

    console.log(`Stock data loaded in ${loadTime}ms`);

    // Should load within 5 seconds
    expect(loadTime).toBeLessThan(5000);
  });
});
