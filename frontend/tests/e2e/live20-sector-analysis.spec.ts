import { test, expect } from '@playwright/test';
import { TEST_CONFIG } from './config';

const FRONTEND_URL = TEST_CONFIG.FRONTEND_URL;
const BACKEND_URL = TEST_CONFIG.BACKEND_URL;

test.describe('Live20 Sector Analysis', () => {
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

  test.describe('Sector column display', () => {
    test('table shows Sector column header', async ({ page }) => {
      // Enter symbol and analyze
      await page.getByPlaceholder(/AAPL.*MSFT/i).fill('AAPL');
      await page.getByRole('button', { name: /analyze/i }).click();

      // Wait for table
      await page.waitForSelector('table', { timeout: 30000 });

      // Verify Sector column exists
      const tableHeader = page.locator('thead');
      await expect(tableHeader.getByText('Sector', { exact: true })).toBeVisible();
    });

    test('table rows show sector ETF values', async ({ page }) => {
      // Run analysis
      await page.getByPlaceholder(/AAPL.*MSFT/i).fill('AAPL');
      await page.getByRole('button', { name: /analyze/i }).click();

      await page.waitForSelector('table', { timeout: 30000 });

      // Find AAPL row and verify sector shown
      const aaaplRow = page.getByRole('row').filter({ hasText: 'AAPL' });
      await expect(aaaplRow).toContainText(/XLK|XLF|XLE|Technology|Finance/i);
    });
  });

  test.describe('Row expansion mechanics', () => {
    test('can expand row to see sector details', async ({ page }) => {
      // Run analysis
      await page.getByPlaceholder(/AAPL.*MSFT/i).fill('AAPL');
      await page.getByRole('button', { name: /analyze/i }).click();
      await page.waitForSelector('table', { timeout: 30000 });

      // Find expand button
      const expandButton = page.getByLabel('Expand details for AAPL');
      await expect(expandButton).toBeVisible();
      await expect(expandButton).toHaveAttribute('aria-expanded', 'false');

      // Click to expand
      await expandButton.click();

      // Wait for expanded content to be visible (combines animation + state update)
      await expect(page.getByText('Sector Trend Analysis')).toBeVisible();

      // Verify expanded attribute changed
      await expect(expandButton).toHaveAttribute('aria-expanded', 'true');
    });

    test('can collapse expanded row', async ({ page }) => {
      // Expand first
      await page.getByPlaceholder(/AAPL.*MSFT/i).fill('AAPL');
      await page.getByRole('button', { name: /analyze/i }).click();
      await page.waitForSelector('table', { timeout: 30000 });

      const expandButton = page.getByLabel('Expand details for AAPL');
      await expandButton.click();

      // Wait for expanded content
      await expect(page.getByText('Sector Trend Analysis')).toBeVisible();

      // Click again to collapse
      await expandButton.click();

      // Wait for content to be hidden (verifies collapse animation completed)
      await expect(page.getByText('Sector Trend Analysis')).not.toBeVisible();

      // Verify collapsed attribute
      await expect(expandButton).toHaveAttribute('aria-expanded', 'false');
    });

    test('can expand multiple rows simultaneously', async ({ page }) => {
      // Run analysis with multiple symbols
      await page.getByPlaceholder(/AAPL.*MSFT/i).fill('AAPL, MSFT');
      await page.getByRole('button', { name: /analyze/i }).click();
      await page.waitForSelector('table', { timeout: 30000 });

      // Expand both rows
      const aaaplButton = page.getByLabel('Expand details for AAPL');
      const msftButton = page.getByLabel('Expand details for MSFT');

      await aaaplButton.click();
      await expect(aaaplButton).toHaveAttribute('aria-expanded', 'true');

      await msftButton.click();
      await expect(msftButton).toHaveAttribute('aria-expanded', 'true');

      // Both should show content (multiple "Sector Trend Analysis" headers)
      // Wait for at least 2 headers to be visible
      await expect(page.getByText('Sector Trend Analysis')).toHaveCount(2);
      const headers = await page.getByText('Sector Trend Analysis').all();
      expect(headers.length).toBeGreaterThanOrEqual(2);
    });
  });

  test.describe('Sector trend data display', () => {
    test('expanded row shows sector trend indicators', async ({ page }) => {
      await page.getByPlaceholder(/AAPL.*MSFT/i).fill('AAPL');
      await page.getByRole('button', { name: /analyze/i }).click();
      await page.waitForSelector('table', { timeout: 30000 });

      // Expand row
      const expandButton = page.getByLabel('Expand details for AAPL');
      await expandButton.click();

      // Verify sector trend section exists
      await expect(page.getByText('Sector Trend Analysis')).toBeVisible();

      // Wait for data to load by checking for specific indicators
      // These only appear after API response completes
      await expect(page.getByText('Sector ETF').first()).toBeVisible();
      await expect(page.getByText('MA20').first()).toBeVisible();
      await expect(page.getByText('MA50').first()).toBeVisible();
    });

    test('shows sector ETF name and trend direction', async ({ page }) => {
      await page.getByPlaceholder(/AAPL.*MSFT/i).fill('AAPL');
      await page.getByRole('button', { name: /analyze/i }).click();
      await page.waitForSelector('table', { timeout: 30000 });

      await page.getByLabel('Expand details for AAPL').click();

      // Wait for sector trend section to be visible
      await expect(page.getByText('Sector Trend Analysis')).toBeVisible();

      // Should show sector ETF (e.g., XLK) - use first() since it appears in table AND expanded row
      await expect(page.getByText(/XLK|XLF|XLE/i).first()).toBeVisible();
    });

    test('shows MA position badges and percentages', async ({ page }) => {
      await page.getByPlaceholder(/AAPL.*MSFT/i).fill('AAPL');
      await page.getByRole('button', { name: /analyze/i }).click();
      await page.waitForSelector('table', { timeout: 30000 });

      await page.getByLabel('Expand details for AAPL').click();

      // Verify sector trend section is visible
      await expect(page.getByText('Sector Trend Analysis')).toBeVisible();

      // Verify MA badges are visible (above/below)
      // Use locator that's more specific to avoid table header matches
      const expandedContent = page.locator('.bg-bg-tertiary.border-t');
      await expect(expandedContent.getByText(/above|below/i).first()).toBeVisible();

      // Verify percentage formats are shown (wait for API data to load)
      await expect(expandedContent.getByText(/[+-]\d+\.\d+%/).first()).toBeVisible();
    });
  });

  test.describe('Stock chart display', () => {
    test('expanded row shows stock chart', async ({ page }) => {
      await page.getByPlaceholder(/AAPL.*MSFT/i).fill('AAPL');
      await page.getByRole('button', { name: /analyze/i }).click();
      await page.waitForSelector('table', { timeout: 30000 });

      await page.getByLabel('Expand details for AAPL').click();

      // Verify chart header is visible (indicates content loaded)
      await expect(page.getByText(/AAPL Chart \(3 Months\)/i)).toBeVisible();

      // Chart canvas should be present (TradingView chart)
      // Wait for canvas to render after data loads
      const chartContainer = page.locator('canvas').first();
      await expect(chartContainer).toBeVisible();
    });

    test('chart shows for correct symbol', async ({ page }) => {
      await page.getByPlaceholder(/AAPL.*MSFT/i).fill('MSFT');
      await page.getByRole('button', { name: /analyze/i }).click();
      await page.waitForSelector('table', { timeout: 30000 });

      await page.getByLabel('Expand details for MSFT').click();

      // Wait for MSFT chart header to be visible (not AAPL)
      await expect(page.getByText(/MSFT Chart \(3 Months\)/i)).toBeVisible();
    });
  });

  test.describe('Mobile responsive', () => {
    test('row expansion works on mobile', async ({ page }) => {
      // Set mobile viewport
      await page.setViewportSize({ width: 375, height: 667 });

      await page.goto(`${FRONTEND_URL}/live-20`);
      await page.waitForLoadState('networkidle');

      // Run analysis
      await page.getByPlaceholder(/AAPL.*MSFT/i).fill('AAPL');
      await page.getByRole('button', { name: /analyze/i }).click();
      await page.waitForSelector('table', { timeout: 30000 });

      // Expand row
      const expandButton = page.getByLabel('Expand details for AAPL');
      await expandButton.click();

      // Wait for sector and chart sections to be visible on mobile
      await expect(page.getByText('Sector Trend Analysis')).toBeVisible();
      await expect(page.getByText(/AAPL Chart/i)).toBeVisible();
    });
  });
});
