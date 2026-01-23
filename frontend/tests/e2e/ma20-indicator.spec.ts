import { test, expect } from '@playwright/test';
import { TEST_CONFIG } from './config';

test.describe('MA 20 Indicator', () => {
  test.beforeEach(async ({ page }) => {
    // Navigate to a page with the CandlestickChart
    await page.goto(TEST_CONFIG.FRONTEND_URL);
  });

  test('should display MA 20 line on chart by default', async ({ page }) => {
    // Navigate to stock analysis page and wait for everything to load
    await page.goto(`${TEST_CONFIG.FRONTEND_URL}/?symbol=AAPL`, { waitUntil: 'networkidle' });

    // Wait for stock symbol to appear (indicates data loaded)
    await expect(page.getByText('AAPL', { exact: true }).first()).toBeVisible({ timeout: 15000 });

    // Wait for chart to render with data
    await expect(page.locator('[data-testid="candlestick-chart"]')).toBeVisible({ timeout: 10000 });

    // Act & Assert: Check MA 20 toggle button exists and is active
    const toggleButton = page.getByRole('button', { name: /MA 20 indicator/i });
    await expect(toggleButton).toBeVisible();
    await expect(toggleButton).toHaveAttribute('aria-pressed', 'true');
  });

  test('should toggle MA 20 visibility when button clicked', async ({ page }) => {
    // Navigate and wait for page to be ready
    await page.goto(`${TEST_CONFIG.FRONTEND_URL}/?symbol=AAPL`, { waitUntil: 'networkidle' });

    // Wait for data to load
    await expect(page.getByText('AAPL', { exact: true }).first()).toBeVisible({ timeout: 15000 });
    await expect(page.locator('[data-testid="candlestick-chart"]')).toBeVisible({ timeout: 10000 });

    // Find button by text content "MA 20"
    const toggleButton = page.getByRole('button', { name: 'MA 20' });

    // Initially should be showing (aria-pressed="true")
    await expect(toggleButton).toHaveAttribute('aria-pressed', 'true');
    await expect(toggleButton).toHaveAttribute('aria-label', 'Hide MA 20 indicator');

    // Act: Click to hide
    await toggleButton.click();

    // Assert: Button state changed
    await expect(toggleButton).toHaveAttribute('aria-pressed', 'false');
    await expect(toggleButton).toHaveAttribute('aria-label', 'Show MA 20 indicator');

    // Act: Click to show again
    await toggleButton.click();

    // Assert: Button state changed back
    await expect(toggleButton).toHaveAttribute('aria-pressed', 'true');
    await expect(toggleButton).toHaveAttribute('aria-label', 'Hide MA 20 indicator');
  });

  test('should display color legend with all elements', async ({ page }) => {
    // Navigate and wait for page to be ready
    await page.goto(`${TEST_CONFIG.FRONTEND_URL}/?symbol=AAPL`, { waitUntil: 'networkidle' });

    // Wait for data to load
    await expect(page.getByText('AAPL', { exact: true }).first()).toBeVisible({ timeout: 15000 });
    await expect(page.locator('[data-testid="candlestick-chart"]')).toBeVisible({ timeout: 10000 });

    // Act & Assert: Check all legend items
    const legend = page.getByRole('list', { name: /chart color legend/i });
    await expect(legend).toBeVisible();

    // Scope all text searches to the legend to avoid matching badge text
    await expect(legend.getByText(/bullish/i)).toBeVisible();
    await expect(legend.getByText(/bearish/i)).toBeVisible();
    await expect(legend.getByText(/MA 20/i)).toBeVisible();
    await expect(legend.getByText(/wicks/i)).toBeVisible();
  });

  test('should maintain toggle state during user interaction', async ({ page }) => {
    // Navigate and wait for page to be ready
    await page.goto(`${TEST_CONFIG.FRONTEND_URL}/?symbol=AAPL`, { waitUntil: 'networkidle' });

    // Wait for data to load
    await expect(page.getByText('AAPL', { exact: true }).first()).toBeVisible({ timeout: 15000 });
    await expect(page.locator('[data-testid="candlestick-chart"]')).toBeVisible({ timeout: 10000 });

    const toggleButton = page.getByRole('button', { name: /MA 20 indicator/i });

    // Act: Hide MA 20
    await toggleButton.click();
    await expect(toggleButton).toHaveAttribute('aria-pressed', 'false');

    // Interact with chart (zoom, pan, etc.)
    const chart = page.locator('[data-testid="candlestick-chart"]');
    await chart.hover();
    await chart.click(); // Simulate interaction

    // Assert: Toggle state persists
    await expect(toggleButton).toHaveAttribute('aria-pressed', 'false');
  });

  test('should verify MA 20 data is fetched from backend', async ({ page }) => {
    // Set up API response listener BEFORE navigation for INDICATORS endpoint
    const responsePromise = page.waitForResponse(
      response => response.url().includes('/api/v1/stocks/AAPL/indicators') && response.status() === 200
    );

    // Navigate (this will trigger the API call)
    await page.goto(`${TEST_CONFIG.FRONTEND_URL}/?symbol=AAPL`);

    // Wait for and verify API response
    const response = await responsePromise;
    const data = await response.json();

    expect(data.data).toBeDefined();
    expect(data.data.length).toBeGreaterThan(0);
    expect(data.indicators).toContain('MA-20');

    // Check that ma_20 field exists in response
    const firstDataPoint = data.data[0];
    expect(firstDataPoint).toHaveProperty('ma_20');

    // Verify chart rendered after data loaded
    await expect(page.getByText('AAPL', { exact: true }).first()).toBeVisible({ timeout: 15000 });
    await expect(page.locator('[data-testid="candlestick-chart"]')).toBeVisible({ timeout: 10000 });
  });
});
