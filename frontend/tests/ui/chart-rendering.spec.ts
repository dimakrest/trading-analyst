import { test, expect } from '@playwright/test';
import { StockAnalysisPage } from '../pages/StockAnalysisPage';
import { mockAAPLData, mockAAPLIndicators } from '../fixtures/mockStockData';

test.describe('Candlestick Chart Rendering', () => {
  let stockPage: StockAnalysisPage;

  test.beforeEach(async ({ page }) => {
    stockPage = new StockAnalysisPage(page);

    // Mock the prices API response
    await page.route('**/api/v1/stocks/AAPL/prices/*', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(mockAAPLData),
      });
    });

    // Mock the indicators API response (required for chart to render)
    await page.route('**/api/v1/stocks/AAPL/indicators/*', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(mockAAPLIndicators),
      });
    });

    await stockPage.goto();
    await stockPage.searchStock('AAPL');
    // Wait for chart to load
    await stockPage.waitForChartToLoad();
  });

  test('should render canvas-based chart', async ({ page }) => {
    // New chart uses Lightweight Charts (canvas-based)
    const canvasChart = await stockPage.isSvgChartPresent();
    expect(canvasChart).toBe(true);

    // Verify canvas element exists
    const canvas = page.locator('canvas');
    await expect(canvas.first()).toBeVisible();
  });

  test('should have accessible chart description', async () => {
    const description = await stockPage.getChartDescription();

    expect(description).toBeTruthy();
    expect(description).toContain('Candlestick chart');
    expect(description).toContain('AAPL');
  });

  test('should render chart container with proper dimensions', async ({ page }) => {
    // Chart container should be visible and have dimensions
    const chartContainer = page.getByTestId('candlestick-chart');
    await expect(chartContainer).toBeVisible();

    // Check that container has height set (600px from default props)
    const boundingBox = await chartContainer.boundingBox();
    expect(boundingBox).toBeTruthy();
    expect(boundingBox?.height).toBeGreaterThanOrEqual(500); // Should be ~600px
  });

  test('should display chart after loading data', async () => {
    // Verify chart is visible (not loading state)
    const isChartVisible = await stockPage.isChartVisible();
    expect(isChartVisible).toBe(true);

    // Verify loading indicator is not visible
    const isLoading = await stockPage.isLoadingVisible();
    expect(isLoading).toBe(false);
  });

  test('should have dark theme styling', async ({ page }) => {
    // Chart container should have dark background
    const chartContainer = page.getByTestId('candlestick-chart');
    const bgColor = await chartContainer.evaluate((el) =>
      window.getComputedStyle(el).backgroundColor
    );

    // Dark theme should have dark background (not white)
    // Should be black: rgb(0, 0, 0)
    expect(bgColor).toBe('rgb(0, 0, 0)');
  });

  test('should render without console errors', async ({ page }) => {
    // Monitor console for errors during chart rendering
    const consoleErrors: string[] = [];
    page.on('console', (msg) => {
      if (msg.type() === 'error') {
        consoleErrors.push(msg.text());
      }
    });

    // Wait a bit for any async rendering
    await page.waitForTimeout(1000);

    // Should have no errors
    expect(consoleErrors).toHaveLength(0);
  });
});
