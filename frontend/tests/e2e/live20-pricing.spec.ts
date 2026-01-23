/**
 * E2E Tests for Live 20 Pricing Strategies
 *
 * Tests the pricing strategy selection UI and integration:
 * - Strategy selector visibility and default value
 * - Strategy selection changes
 * - Stop Loss and Risk columns in results table
 *
 * IMPORTANT: Backend must be running (./scripts/dc.sh up -d)
 * Tests that interact with API require real market data.
 */

import { test, expect } from '@playwright/test';
import { TEST_CONFIG } from './config';

const FRONTEND_URL = TEST_CONFIG.FRONTEND_URL;
const BACKEND_URL = TEST_CONFIG.BACKEND_URL;

test.describe('Live20 Pricing Strategies', () => {
  test.beforeAll(async () => {
    // Verify backend is running
    const response = await fetch(`${BACKEND_URL}/api/v1/health`);
    if (!response.ok) {
      throw new Error('Backend is not running. Start it with: ./scripts/dc.sh up -d');
    }
  });

  test.beforeEach(async ({ page }) => {
    await page.goto(`${FRONTEND_URL}/live-20`);
    await page.waitForLoadState('networkidle');
  });

  test.describe('Strategy Selector UI', () => {
    test('should show strategy selector with default value', async ({ page }) => {
      // Strategy label should be visible
      await expect(page.getByText('Entry Strategy')).toBeVisible();

      // Strategy selector should be visible - using the select trigger
      const selector = page.locator('#entry-strategy');
      await expect(selector).toBeVisible();

      // Default should be Current Price (close)
      await expect(selector).toContainText('Current Price');
    });

    test('should allow changing entry strategy', async ({ page }) => {
      // Click the strategy selector to open it
      const selector = page.locator('#entry-strategy');
      await selector.click();

      // Select Breakout Confirmation option
      await page.getByRole('option', { name: /breakout confirmation/i }).click();

      // Verify selection changed
      await expect(selector).toContainText('Breakout Confirmation');
    });

    test('should show ATR stop loss badge', async ({ page }) => {
      // The stop loss configuration badge should be visible
      await expect(page.getByText('Stop: 0.5 x ATR')).toBeVisible();
    });

    test('should disable strategy selector during analysis', async ({ page }) => {
      // Enter symbols
      await page.getByPlaceholder(/AAPL.*MSFT/i).fill('AAPL');

      // Start analysis
      await page.getByRole('button', { name: /analyze/i }).click();

      // Strategy selector should be disabled during analysis
      const selector = page.locator('#entry-strategy');

      // Check that the select trigger is disabled
      // ShadCN Select uses data-disabled attribute
      await expect(selector).toBeDisabled();
    });

    test('should persist strategy selection after changing list', async ({ page }) => {
      // First, change strategy to Breakout Confirmation
      const selector = page.locator('#entry-strategy');
      await selector.click();
      await page.getByRole('option', { name: /breakout confirmation/i }).click();

      // Verify it's set
      await expect(selector).toContainText('Breakout Confirmation');

      // Enter some symbols manually
      await page.getByPlaceholder(/AAPL.*MSFT/i).fill('AAPL');

      // Strategy should still be Breakout Confirmation
      await expect(selector).toContainText('Breakout Confirmation');
    });
  });

  test.describe('Results Table Columns', () => {
    // These tests require analysis results which need real backend + market data

    test('table headers include Stop and Risk columns when results displayed', async ({
      page,
    }) => {
      // This test validates the table structure after analysis completes
      // We'll use a real symbol and wait for results

      // Enter a symbol
      await page.getByPlaceholder(/AAPL.*MSFT/i).fill('AAPL');

      // Click analyze
      await page.getByRole('button', { name: /analyze/i }).click();

      // Wait for results table to appear (with timeout for API response)
      // The table appears within the results card after analysis completes
      await page.waitForSelector('table', { timeout: 30000 });

      // Verify Stop column header exists (using th element selector)
      // ShadCN table uses <th> elements which may not always get columnheader role
      const tableHeader = page.locator('thead');
      await expect(tableHeader.getByText('Stop', { exact: true })).toBeVisible();

      // Verify Risk column header exists
      await expect(tableHeader.getByText('Risk', { exact: true })).toBeVisible();

      // Verify Price column exists (existing functionality)
      await expect(tableHeader.getByText('Price', { exact: true })).toBeVisible();
    });

    test('table headers include all expected columns', async ({ page }) => {
      // Enter a symbol and analyze
      await page.getByPlaceholder(/AAPL.*MSFT/i).fill('MSFT');
      await page.getByRole('button', { name: /analyze/i }).click();

      // Wait for results
      await page.waitForSelector('table', { timeout: 30000 });

      // Verify all key column headers
      // Using th element selector since ShadCN table may not expose columnheader role
      const tableHeader = page.locator('thead');
      const expectedHeaders = [
        'Symbol',
        'Direction',
        'Score',
        'Price',
        'Stop',
        'Risk',
        'Trend',
        'MA20',
        'Candle',
        'Volume',
        'CCI',
      ];

      for (const header of expectedHeaders) {
        await expect(tableHeader.getByText(header, { exact: true })).toBeVisible();
      }
    });
  });

  test.describe('Strategy Integration with Analysis', () => {
    test('should include strategy config in analysis request', async ({ page }) => {
      // Set up request interception to verify the payload
      let capturedRequest: { strategy_config?: { entry_strategy: string } } | null = null;

      await page.route('**/api/v1/live-20/analyze', async (route) => {
        const request = route.request();
        capturedRequest = JSON.parse(request.postData() || '{}');
        // Continue with the actual request
        await route.continue();
      });

      // Select Breakout Confirmation strategy
      const selector = page.locator('#entry-strategy');
      await selector.click();
      await page.getByRole('option', { name: /breakout confirmation/i }).click();

      // Enter a symbol
      await page.getByPlaceholder(/AAPL.*MSFT/i).fill('AAPL');

      // Click analyze
      await page.getByRole('button', { name: /analyze/i }).click();

      // Wait for request to be made
      await page.waitForTimeout(1000);

      // Verify the strategy config was included in the request
      expect(capturedRequest).not.toBeNull();
      expect(capturedRequest?.strategy_config).toBeDefined();
      expect(capturedRequest?.strategy_config?.entry_strategy).toBe('breakout_confirmation');
    });

    test('should include default strategy config when not changed', async ({ page }) => {
      // Set up request interception
      let capturedRequest: { strategy_config?: { entry_strategy: string } } | null = null;

      await page.route('**/api/v1/live-20/analyze', async (route) => {
        const request = route.request();
        capturedRequest = JSON.parse(request.postData() || '{}');
        await route.continue();
      });

      // Don't change strategy - leave as default

      // Enter a symbol
      await page.getByPlaceholder(/AAPL.*MSFT/i).fill('AAPL');

      // Click analyze
      await page.getByRole('button', { name: /analyze/i }).click();

      // Wait for request
      await page.waitForTimeout(1000);

      // Verify default strategy config
      expect(capturedRequest).not.toBeNull();
      expect(capturedRequest?.strategy_config).toBeDefined();
      expect(capturedRequest?.strategy_config?.entry_strategy).toBe('current_price');
    });
  });

  test.describe('Mobile Responsive', () => {
    test('strategy selector is visible on mobile', async ({ page }) => {
      // Set mobile viewport
      await page.setViewportSize({ width: 375, height: 667 });

      await page.goto(`${FRONTEND_URL}/live-20`);
      await page.waitForLoadState('networkidle');

      // Strategy label and selector should be visible
      await expect(page.getByText('Entry Strategy')).toBeVisible();
      await expect(page.locator('#entry-strategy')).toBeVisible();
    });

    test('strategy selector dropdown works on mobile', async ({ page }) => {
      // Set mobile viewport
      await page.setViewportSize({ width: 375, height: 667 });

      await page.goto(`${FRONTEND_URL}/live-20`);
      await page.waitForLoadState('networkidle');

      // Open the selector
      const selector = page.locator('#entry-strategy');
      await selector.click();

      // Options should be visible
      await expect(page.getByRole('option', { name: /current price/i })).toBeVisible();
      await expect(page.getByRole('option', { name: /breakout confirmation/i })).toBeVisible();

      // Select an option
      await page.getByRole('option', { name: /breakout confirmation/i }).click();

      // Verify selection
      await expect(selector).toContainText('Breakout Confirmation');
    });
  });
});
