import { Page, Locator } from '@playwright/test';

/**
 * Page Object Model for Alert Detail page
 *
 * Encapsulates all page interactions and element locators
 * following Playwright best practices with accessibility-first selectors
 */
export class AlertDetailPage {
  readonly page: Page;
  readonly backButton: Locator;
  readonly symbolHeading: Locator;
  readonly pauseButton: Locator;
  readonly resumeButton: Locator;
  readonly deleteButton: Locator;
  readonly chart: Locator;
  readonly loadingSkeleton: Locator;
  readonly errorState: Locator;
  readonly notFoundState: Locator;
  readonly retryButton: Locator;

  constructor(page: Page) {
    this.page = page;
    // aria-label="Back to alerts" on the ghost Button in the header row
    this.backButton = page.getByRole('button', { name: 'Back to alerts' });
    // <h1> displaying the alert symbol (e.g. "AAPL")
    this.symbolHeading = page.getByRole('heading', { level: 1 });
    // aria-label toggled to "Pause alert" when the alert is active
    this.pauseButton = page.getByRole('button', { name: 'Pause alert' });
    // aria-label toggled to "Resume alert" when the alert is paused
    this.resumeButton = page.getByRole('button', { name: 'Resume alert' });
    // aria-label="Delete alert" on the AlertDialogTrigger button
    this.deleteButton = page.getByRole('button', { name: 'Delete alert' });
    // CandlestickChart container uses data-testid="candlestick-chart"
    this.chart = page.getByTestId('candlestick-chart');
    // Skeleton rows rendered during loading (div with animate-pulse)
    this.loadingSkeleton = page.locator('.animate-pulse').first();
    // ShadCN Alert component renders with role="alert" in the error state
    this.errorState = page.getByRole('alert');
    // Not-found state renders a <p> with this exact text
    this.notFoundState = page.getByText('Alert not found');
    // Retry button inside the error Alert description
    this.retryButton = page.getByRole('button', { name: /retry/i });
  }

  /**
   * Navigate directly to an alert detail page and wait for the symbol heading
   * to be visible (i.e. the alert loaded successfully).
   */
  async goto(alertId: number) {
    await this.page.goto(`/alerts/${alertId}`);
    await this.symbolHeading.waitFor({ state: 'visible' });
  }

  /** Click the breadcrumb back button to return to the alerts list. */
  async clickBack() {
    await this.backButton.click();
  }

  /** Click the Delete button to open the confirmation dialog. */
  async clickDelete() {
    await this.deleteButton.click();
  }

  /**
   * Confirm the delete action inside the AlertDialog.
   *
   * Clicks the "Delete" action button inside the alertdialog role so that
   * the test does not accidentally match other Delete buttons on the page.
   */
  async confirmDelete() {
    await this.page.getByRole('alertdialog').getByRole('button', { name: 'Delete' }).click();
  }
}
