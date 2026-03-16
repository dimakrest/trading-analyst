/**
 * Responsive UI Tests for Alerts Dashboard
 *
 * Tests verify that the Alerts dashboard renders the correct layout at both
 * mobile (375x667) and desktop (1280x800) breakpoints, using page.route() to
 * mock the backend so there is no dependency on a running server.
 *
 * Mobile layout: card list (md:hidden)  — table is hidden (hidden md:block)
 * Desktop layout: table (hidden md:block) — cards are hidden (md:hidden)
 *
 * API mocked: GET /api/v1/alerts/  →  mockAlertList (13 alerts)
 *
 * Key fixtures:
 *   mockFibAlert   — id:1, symbol:AAPL, status:retracing
 *   mockMAAlert    — id:2, symbol:NVDA, status:approaching
 */

import { test, expect } from '@playwright/test';
import { mockAlertList } from '../fixtures/mockAlertData';

// ---------------------------------------------------------------------------
// Helper: register the alerts list route mock before navigating
// ---------------------------------------------------------------------------

const setupMocks = async (page: import('@playwright/test').Page) => {
  await page.route('**/api/v1/alerts/**', async (route) => {
    if (route.request().method() === 'GET') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(mockAlertList),
      });
    } else {
      await route.continue();
    }
  });
};

// ---------------------------------------------------------------------------
// Mobile (375x667)
// ---------------------------------------------------------------------------

test.describe('Alerts Responsive - Mobile (375x667)', () => {
  test.use({ viewport: { width: 375, height: 667 } });

  test.beforeEach(async ({ page }) => {
    await setupMocks(page);
    await page.goto('/alerts');
    await page.waitForLoadState('networkidle');
  });

  test('dashboard renders card layout on mobile, not table', async ({ page }) => {
    // The desktop table lives inside `<div class="hidden md:block">` — at 375 px
    // the md breakpoint is not reached so the table should not be visible.
    await expect(page.locator('table').first()).not.toBeVisible();

    // The mobile card container is `<div class="md:hidden ...">`.
    // Scope to the mobile container to avoid matching hidden desktop <tr> elements.
    const mobileContainer = page.locator('.md\\:hidden');
    const cards = mobileContainer.locator('[role="button"][aria-label^="View details for"]');
    await expect(cards.first()).toBeVisible();
  });

  test('alert cards display symbol, status, and alert type', async ({ page }) => {
    // Scope to mobile container to avoid matching hidden desktop table rows
    const mobileContainer = page.locator('.md\\:hidden');

    // mockFibAlert: id=1, symbol=AAPL, status=retracing  →  badge text "Retracing"
    const aaplCard = mobileContainer.locator('[role="button"][aria-label*="AAPL"]').first();
    await expect(aaplCard).toBeVisible();
    await expect(aaplCard.getByText('AAPL')).toBeVisible();
    await expect(aaplCard.getByText('Retracing')).toBeVisible();

    // mockMAAlert: id=2, symbol=NVDA, status=approaching  →  badge text "Approaching"
    const nvdaCard = mobileContainer.locator('[role="button"][aria-label*="NVDA"]').first();
    await expect(nvdaCard).toBeVisible();
    await expect(nvdaCard.getByText('NVDA')).toBeVisible();
    await expect(nvdaCard.getByText('Approaching')).toBeVisible();
  });

  test('tapping a card navigates to the alert detail view', async ({ page }) => {
    // Scope to mobile container — desktop <tr> elements are hidden on mobile
    const mobileContainer = page.locator('.md\\:hidden');
    const aaplCard = mobileContainer.locator('[role="button"][aria-label*="AAPL"]').first();
    await aaplCard.click();
    await expect(page).toHaveURL(/\/alerts\/1/);
  });

  test('Add Alert button is accessible on mobile and opens the dialog', async ({ page }) => {
    const addAlertButton = page.getByRole('button', { name: /add alert/i }).first();
    await expect(addAlertButton).toBeVisible();

    await addAlertButton.click();

    // CreateAlertDialog renders a <DialogTitle> with text "Add Alert"
    await expect(page.getByRole('dialog')).toBeVisible();
    await expect(page.getByRole('heading', { name: /add alert/i })).toBeVisible();
  });

  test('no horizontal scroll on mobile', async ({ page }) => {
    const hasHorizontalScroll = await page.evaluate(
      () => document.body.scrollWidth > window.innerWidth + 1
    );
    expect(hasHorizontalScroll).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// Desktop (1280x800)
// ---------------------------------------------------------------------------

test.describe('Alerts Responsive - Desktop (1280x800)', () => {
  test.use({ viewport: { width: 1280, height: 800 } });

  test.beforeEach(async ({ page }) => {
    await setupMocks(page);
    await page.goto('/alerts');
    await page.waitForLoadState('networkidle');
  });

  test('dashboard renders table layout on desktop with all column headers', async ({ page }) => {
    // At 1280 px the md breakpoint is reached — `hidden md:block` wrapper becomes visible.
    const table = page.locator('table').first();
    await expect(table).toBeVisible();

    // Verify every expected column header is present in the table header row.
    const thead = page.locator('thead');
    await expect(thead.getByText('Symbol')).toBeVisible();
    await expect(thead.getByText('Alert Type')).toBeVisible();
    await expect(thead.getByText('Price')).toBeVisible();
    await expect(thead.getByText('Status')).toBeVisible();
    await expect(thead.getByText('Details')).toBeVisible();
    await expect(thead.getByText('Last Alert')).toBeVisible();
  });

  test('Alerts link is visible in the desktop sidebar', async ({ page }) => {
    // DesktopSidebar renders: aside[aria-label="Desktop navigation"]
    //   > nav[aria-label="Main navigation"]
    //     > a  (one per NAV_ITEM, including "Alerts")
    const sidebar = page.locator('aside[aria-label="Desktop navigation"]');
    await expect(sidebar).toBeVisible();

    const alertsLink = sidebar.locator('nav[aria-label="Main navigation"]').getByRole('link', { name: /alerts/i });
    await expect(alertsLink).toBeVisible();
  });

  test('both filter comboboxes are visible on desktop', async ({ page }) => {
    // AlertFilters renders two SelectTrigger elements with explicit aria-labels.
    const typeFilter = page.getByRole('combobox', { name: /filter by type/i });
    const statusFilter = page.getByRole('combobox', { name: /filter by status/i });

    await expect(typeFilter).toBeVisible();
    await expect(statusFilter).toBeVisible();
  });
});
