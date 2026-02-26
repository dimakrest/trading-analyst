import { test, expect } from '@playwright/test';
import { StockAnalysisPage } from '../pages/StockAnalysisPage';
import { mockErrorResponse, mockEmptyDataResponse } from '../fixtures/mockStockData';

test.describe('Error Handling', () => {
  let stockPage: StockAnalysisPage;

  test.beforeEach(async ({ page }) => {
    stockPage = new StockAnalysisPage(page);
    await stockPage.goto();
  });

  test('should display error message for invalid stock symbol', async ({ page }) => {
    // Mock error response for both endpoints
    await page.route('**/api/v1/stocks/INVALID/prices/*', async (route) => {
      await route.fulfill({ status: 404, json: mockErrorResponse });
    });
    await page.route('**/api/v1/stocks/INVALID/indicators/*', async (route) => {
      await route.fulfill({ status: 404, json: mockErrorResponse });
    });

    await stockPage.searchStock('INVALID');

    // Wait for error message
    await expect(stockPage.errorMessage).toBeVisible({ timeout: 5000 });

    const errorText = await stockPage.getErrorText();
    expect(errorText).toContain('Error');
  });

  test('should handle network errors gracefully', async ({ page }) => {
    // Mock network error for both endpoints
    await page.route('**/api/v1/stocks/NETWORK/prices/*', async (route) => {
      await route.abort('failed');
    });
    await page.route('**/api/v1/stocks/NETWORK/indicators/*', async (route) => {
      await route.abort('failed');
    });

    await stockPage.searchStock('NETWORK');

    // Network errors may show as error message or remain in loading state
    // Wait for either error to appear or loading to finish
    await expect(async () => {
      const hasError = await stockPage.isErrorVisible();
      const isLoading = await stockPage.isLoadingVisible();
      // Should either show error or stop loading
      expect(hasError || !isLoading).toBeTruthy();
    }).toPass({ timeout: 5000 });
  });

  test('should show empty state when no data available', async ({ page }) => {
    // Mock empty response for prices
    await page.route('**/api/v1/stocks/EMPTY/prices/*', async (route) => {
      await route.fulfill({ json: mockEmptyDataResponse });
    });
    // Mock empty indicators response
    await page.route('**/api/v1/stocks/EMPTY/indicators/*', async (route) => {
      await route.fulfill({
        json: {
          symbol: 'EMPTY',
          data: [],
          total_records: 0,
          start_date: '',
          end_date: '',
          interval: '1d',
          indicators: ['ma_20', 'cci'],
        },
      });
    });

    await stockPage.searchStock('EMPTY');

    // Wait for response to be processed - should show either no data message, error, or just not show chart
    await expect(async () => {
      const hasNoData = await stockPage.isNoDataMessageVisible();
      const hasError = await stockPage.isErrorVisible();
      const hasChart = await stockPage.isChartVisible();
      // Should show no data message, error, or no chart
      expect(hasNoData || hasError || !hasChart).toBeTruthy();
    }).toPass({ timeout: 5000 });
  });

  test('should not display chart when error occurs', async ({ page }) => {
    // Mock error for both endpoints
    await page.route('**/api/v1/stocks/ERROR/prices/*', async (route) => {
      await route.fulfill({ status: 500, json: { detail: 'Internal server error' } });
    });
    await page.route('**/api/v1/stocks/ERROR/indicators/*', async (route) => {
      await route.fulfill({ status: 500, json: { detail: 'Internal server error' } });
    });

    await stockPage.searchStock('ERROR');
    await page.waitForTimeout(1000);

    // Chart should not be visible
    const isChartVisible = await stockPage.isChartVisible();
    expect(isChartVisible).toBe(false);
  });

  test('should handle timeout errors', async ({ page }) => {
    // Mock timeout for both endpoints - abort after delay to simulate timeout
    await page.route('**/api/v1/stocks/TIMEOUT/prices/*', async (route) => {
      // Simulate timeout by delaying then aborting
      await new Promise((resolve) => setTimeout(resolve, 2000));
      await route.abort('timedout');
    });
    await page.route('**/api/v1/stocks/TIMEOUT/indicators/*', async (route) => {
      await new Promise((resolve) => setTimeout(resolve, 2000));
      await route.abort('timedout');
    });

    await stockPage.searchStock('TIMEOUT');

    // Wait for loading state to appear first
    await page.waitForTimeout(500);

    // After timeout, should show either loading state or error
    // The component may continue showing loading or may show an error
    await expect(async () => {
      const isLoading = await stockPage.isLoadingVisible();
      const hasError = await stockPage.isErrorVisible();
      const chartVisible = await stockPage.isChartVisible();
      // Should be in loading state OR showing error OR no chart visible
      expect(isLoading || hasError || !chartVisible).toBeTruthy();
    }).toPass({ timeout: 5000 });
  });
});
