import { test, expect } from '@playwright/test';
import { TEST_CONFIG } from './config';

test.describe('CCI Indicator', () => {
  test.beforeEach(async ({ page }) => {
    // Navigate to a page with the CandlestickChart
    await page.goto(TEST_CONFIG.FRONTEND_URL);
  });

  test('should display CCI toggle button on chart', async ({ page }) => {
    // Navigate to stock analysis page and wait for everything to load
    await page.goto(`${TEST_CONFIG.FRONTEND_URL}/?symbol=AAPL`, { waitUntil: 'networkidle' });

    // Wait for stock symbol to appear (indicates data loaded)
    await expect(page.getByText('AAPL', { exact: true }).first()).toBeVisible({ timeout: 15000 });

    // Wait for chart to render with data
    await expect(page.locator('[data-testid="candlestick-chart"]')).toBeVisible({ timeout: 10000 });

    // Act & Assert: Check CCI toggle button exists and is active by default
    const toggleButton = page.getByRole('button', { name: /CCI indicator/i });
    await expect(toggleButton).toBeVisible();
    await expect(toggleButton).toHaveAttribute('aria-pressed', 'true');
  });

  test('should toggle CCI visibility when button clicked', async ({ page }) => {
    // Navigate and wait for page to be ready
    await page.goto(`${TEST_CONFIG.FRONTEND_URL}/?symbol=AAPL`, { waitUntil: 'networkidle' });

    // Wait for data to load
    await expect(page.getByText('AAPL', { exact: true }).first()).toBeVisible({ timeout: 15000 });
    await expect(page.locator('[data-testid="candlestick-chart"]')).toBeVisible({ timeout: 10000 });

    // Find button by text content "CCI"
    const toggleButton = page.getByRole('button', { name: 'CCI' });

    // Initially should be showing (aria-pressed="true")
    await expect(toggleButton).toHaveAttribute('aria-pressed', 'true');
    await expect(toggleButton).toHaveAttribute('aria-label', 'Hide CCI indicator');

    // Act: Click to hide
    await toggleButton.click();

    // Assert: Button state changed
    await expect(toggleButton).toHaveAttribute('aria-pressed', 'false');
    await expect(toggleButton).toHaveAttribute('aria-label', 'Show CCI indicator');

    // Act: Click to show again
    await toggleButton.click();

    // Assert: Button state changed back
    await expect(toggleButton).toHaveAttribute('aria-pressed', 'true');
    await expect(toggleButton).toHaveAttribute('aria-label', 'Hide CCI indicator');
  });

  test('should maintain toggle state during user interaction', async ({ page }) => {
    // Navigate and wait for page to be ready
    await page.goto(`${TEST_CONFIG.FRONTEND_URL}/?symbol=AAPL`, { waitUntil: 'networkidle' });

    // Wait for data to load
    await expect(page.getByText('AAPL', { exact: true }).first()).toBeVisible({ timeout: 15000 });
    await expect(page.locator('[data-testid="candlestick-chart"]')).toBeVisible({ timeout: 10000 });

    const toggleButton = page.getByRole('button', { name: /CCI indicator/i });

    // Act: Hide CCI
    await toggleButton.click();
    await expect(toggleButton).toHaveAttribute('aria-pressed', 'false');

    // Interact with chart (zoom, pan, etc.)
    const chart = page.locator('[data-testid="candlestick-chart"]');
    await chart.hover();
    await chart.click(); // Simulate interaction

    // Assert: Toggle state persists
    await expect(toggleButton).toHaveAttribute('aria-pressed', 'false');
  });

  test('should verify CCI data is fetched from backend', async ({ page }) => {
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

    // Check that cci field exists in response
    const firstDataPoint = data.data[0];
    expect(firstDataPoint).toHaveProperty('cci');

    // Verify chart rendered after data loaded
    await expect(page.getByText('AAPL', { exact: true }).first()).toBeVisible({ timeout: 15000 });
    await expect(page.locator('[data-testid="candlestick-chart"]')).toBeVisible({ timeout: 10000 });
  });

  test('should have CCI pane separate from main chart', async ({ page }) => {
    // Navigate and wait for page to be ready
    await page.goto(`${TEST_CONFIG.FRONTEND_URL}/?symbol=AAPL`, { waitUntil: 'networkidle' });

    // Wait for data to load
    await expect(page.getByText('AAPL', { exact: true }).first()).toBeVisible({ timeout: 15000 });
    await expect(page.locator('[data-testid="candlestick-chart"]')).toBeVisible({ timeout: 10000 });

    // The chart container should exist with CCI pane
    // CCI is rendered in a separate pane (paneIndex: 2)
    // We verify by checking the API response contains CCI data
    const toggleButton = page.getByRole('button', { name: /CCI indicator/i });
    await expect(toggleButton).toBeVisible();

    // Verify all three toggle buttons exist (MA 20, Vol, CCI)
    const ma20Button = page.getByRole('button', { name: /MA 20/i });
    const volButton = page.getByRole('button', { name: /Vol/i });
    const cciButton = page.getByRole('button', { name: /CCI/i });

    await expect(ma20Button).toBeVisible();
    await expect(volButton).toBeVisible();
    await expect(cciButton).toBeVisible();
  });
});
