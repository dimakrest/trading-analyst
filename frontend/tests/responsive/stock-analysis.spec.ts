import { test, expect } from '@playwright/test';

/**
 * Responsive Tests for Stock Analysis Page
 *
 * Tests the responsive behavior of the stock analysis page across mobile,
 * tablet, and desktop viewports. Validates layout adaptation, search functionality,
 * and horizontal scroll prevention.
 *
 * Test Structure:
 * - Mobile tests use 375x667 viewport (iPhone SE)
 * - Tablet tests use 768x1024 viewport (iPad)
 * - Desktop tests use 1920x1080 viewport
 */

test.describe('Stock Analysis Page Responsive', () => {
  test('layout adapts to mobile', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 667 });
    await page.goto('/');
    await page.waitForLoadState('networkidle');

    // Use main container selector - first() to handle multiple containers
    const container = page.locator('main div.container').first();
    await expect(container).toBeVisible();

    const searchInput = page.locator('input[type="text"]').first();
    await expect(searchInput).toBeVisible();

    // Verify chart renders
    const chart = page.locator('canvas');
    await expect(chart.first()).toBeVisible();
  });

  test('layout adapts to tablet', async ({ page }) => {
    await page.setViewportSize({ width: 768, height: 1024 });
    await page.goto('/');
    await page.waitForLoadState('networkidle');

    const container = page.locator('main div.container').first();
    await expect(container).toBeVisible();

    // Verify chart renders
    const chart = page.locator('canvas');
    await expect(chart.first()).toBeVisible();
  });

  test('layout optimized for desktop', async ({ page }) => {
    await page.setViewportSize({ width: 1920, height: 1080 });
    await page.goto('/');
    await page.waitForLoadState('networkidle');

    const container = page.locator('main div.container').first();
    await expect(container).toBeVisible();

    // Verify chart renders
    const chart = page.locator('canvas');
    await expect(chart.first()).toBeVisible();
  });

  test('search bar works on mobile', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 667 });
    await page.goto('/');
    await page.waitForLoadState('networkidle');

    const searchInput = page.locator('input[type="text"]').first();
    await expect(searchInput).toBeVisible();

    await searchInput.fill('AAPL');
    await expect(searchInput).toHaveValue('AAPL');
  });

  test('no horizontal scroll on mobile', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 667 });
    await page.goto('/');
    await page.waitForLoadState('networkidle');

    const bodyScrollWidth = await page.evaluate(() => document.body.scrollWidth);
    const windowInnerWidth = await page.evaluate(() => window.innerWidth);

    // Allow 1px tolerance for rounding errors
    expect(bodyScrollWidth).toBeLessThanOrEqual(windowInnerWidth + 1);
  });
});
