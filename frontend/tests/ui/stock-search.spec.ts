import { test, expect } from '@playwright/test';
import { StockAnalysisPage } from '../pages/StockAnalysisPage';
import { mockAAPLData, mockTSLAData, mockAAPLIndicators, mockTSLAIndicators } from '../fixtures/mockStockData';

test.describe('Stock Search', () => {
  let stockPage: StockAnalysisPage;

  test.beforeEach(async ({ page }) => {
    stockPage = new StockAnalysisPage(page);

    // Mock API response for AAPL prices
    await page.route('**/api/v1/stocks/AAPL/prices/*', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(mockAAPLData),
      });
    });

    // Mock API response for AAPL indicators
    await page.route('**/api/v1/stocks/AAPL/indicators/*', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(mockAAPLIndicators),
      });
    });

    // Mock API response for TSLA prices
    await page.route('**/api/v1/stocks/TSLA/prices/*', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(mockTSLAData),
      });
    });

    // Mock API response for TSLA indicators
    await page.route('**/api/v1/stocks/TSLA/indicators/*', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(mockTSLAIndicators),
      });
    });

    await stockPage.goto();
  });

  test('should load the page successfully', async ({ page }) => {
    await expect(page).toHaveTitle(/Stock Analysis/);
    await expect(stockPage.searchInput).toBeVisible();
    // Note: Page heading "Stock Analysis" was removed in the redesign
    // The page now just has a search bar at the top
  });

  test('should search for a stock and display chart', async () => {
    await stockPage.searchStock('AAPL');
    await stockPage.waitForChartToLoad();

    // Verify chart is visible
    await expect(stockPage.stockChart).toBeVisible();

    // Verify canvas chart is rendered (Lightweight Charts uses canvas)
    const hasCanvas = await stockPage.isSvgChartPresent();
    expect(hasCanvas).toBe(true);
  });

  test('should display stock price information', async () => {
    await stockPage.searchStock('AAPL');
    await stockPage.waitForChartToLoad();

    // Verify price is displayed
    const price = await stockPage.getCurrentPrice();
    expect(price).toBeTruthy();
    expect(price).toMatch(/\$/); // Should contain dollar sign
  });

  test('should handle Enter key press in search', async () => {
    await stockPage.searchInput.fill('AAPL');
    await stockPage.searchInput.press('Enter');
    await stockPage.waitForChartToLoad();

    await expect(stockPage.stockChart).toBeVisible();
  });

  test('should search for different stocks', async () => {
    // Search for AAPL
    await stockPage.searchStock('AAPL');
    await stockPage.waitForChartToLoad();
    await expect(stockPage.stockChart).toBeVisible();

    // Search for TSLA
    await stockPage.searchStock('TSLA');
    await stockPage.waitForChartToLoad();
    await expect(stockPage.stockChart).toBeVisible();
  });

  test('should allow clearing search input', async () => {
    await stockPage.searchInput.fill('AAPL');
    await expect(stockPage.searchInput).toHaveValue('AAPL');

    await stockPage.searchInput.clear();
    await expect(stockPage.searchInput).toHaveValue('');
  });
});
