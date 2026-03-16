import { Page, Locator } from '@playwright/test';

/**
 * Page Object Model for the Alerts dashboard page
 *
 * Encapsulates all page interactions and element locators
 * following Playwright best practices with accessibility-first selectors.
 *
 * Selectors are derived from AlertsDashboard.tsx and its child components.
 */
export class AlertsPage {
  readonly page: Page;
  readonly heading: Locator;
  readonly addAlertButton: Locator;
  readonly alertsTable: Locator;
  readonly emptyState: Locator;
  readonly loadingSkeleton: Locator;
  readonly errorState: Locator;
  readonly retryButton: Locator;
  readonly filterTypeCombobox: Locator;
  readonly filterStatusCombobox: Locator;
  readonly alertCountLabel: Locator;
  readonly emptyFilterState: Locator;

  constructor(page: Page) {
    this.page = page;

    // Page header — h1 with exact text "Alerts"
    this.heading = page.getByRole('heading', { name: 'Alerts' });

    // Primary CTA in the header; a second one appears in the empty state card
    this.addAlertButton = page.getByRole('button', { name: 'Add Alert' }).first();

    // The <table> rendered by AlertsTable when filtered results are non-empty
    this.alertsTable = page.locator('table');

    // Empty state card shown when no alerts have been configured yet.
    // Full text from AlertsDashboard.tsx:
    //   "No alerts configured. Add a stock to start monitoring."
    this.emptyState = page.getByText('No alerts configured. Add a stock to start monitoring.');

    // Skeleton rows rendered during the initial data fetch (div with animate-pulse)
    this.loadingSkeleton = page.locator('.animate-pulse').first();

    // Error banner — first line of the error card
    this.errorState = page.getByText('Failed to load alerts');

    // Retry button inside the error card
    this.retryButton = page.getByRole('button', { name: /retry/i });

    // Alert-type filter combobox rendered by AlertFilters
    this.filterTypeCombobox = page.getByRole('combobox', { name: /type/i });

    // Status filter combobox rendered by AlertFilters
    this.filterStatusCombobox = page.getByRole('combobox', { name: /status/i });

    // Counter label: "N of M alert(s)" shown in the filters row
    this.alertCountLabel = page.getByText(/\d+ of \d+ alert/);

    // Shown when filters are active but no alerts match.
    // Full text from AlertsDashboard.tsx:
    //   "No alerts match the current filters."
    this.emptyFilterState = page.getByText('No alerts match the current filters.');
  }

  /** Navigate to /alerts and wait for the page heading to be visible. */
  async goto() {
    await this.page.goto('/alerts');
    await this.heading.waitFor({ state: 'visible' });
  }

  /** Open the Create Alert dialog via the header button. */
  async clickAddAlert() {
    await this.addAlertButton.click();
  }

  /**
   * Return the row button for a given symbol.
   *
   * AlertsTable renders each row as a <tr> with an aria-label of the form:
   *   "View details for {symbol} {alertTypeLabel} alert"
   * Using a RegExp matches regardless of the alert type suffix.
   */
  async getAlertRow(symbol: string): Promise<Locator> {
    return this.page.getByRole('button', { name: new RegExp(`View details for ${symbol}`) });
  }

  /**
   * Click the row for the given symbol to navigate to its detail view.
   */
  async navigateToDetail(symbol: string) {
    const row = await this.getAlertRow(symbol);
    await row.click();
  }

  /**
   * Select an alert-type filter option.
   *
   * @param type - Partial match for the option label (e.g. 'fibonacci', 'moving_average')
   */
  async filterByType(type: string) {
    await this.filterTypeCombobox.click();
    await this.page.getByRole('option', { name: new RegExp(type, 'i') }).click();
  }

  /**
   * Select a status filter option.
   *
   * @param status - Partial match for the option label (e.g. 'active', 'triggered')
   */
  async filterByStatus(status: string) {
    await this.filterStatusCombobox.click();
    await this.page.getByRole('option', { name: new RegExp(status, 'i') }).click();
  }
}
