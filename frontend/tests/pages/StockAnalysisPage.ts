import { Page, Locator } from '@playwright/test';

/**
 * Page Object Model for Stock Analysis page
 *
 * Encapsulates all page interactions and element locators
 * following Playwright best practices with accessibility-first selectors
 */
export class StockAnalysisPage {
  readonly page: Page;
  readonly searchInput: Locator;
  readonly stockChart: Locator;
  readonly priceDisplay: Locator;
  readonly errorMessage: Locator;
  readonly loadingIndicator: Locator;
  readonly noDataMessage: Locator;
  readonly editButton: Locator;
  readonly shareButton: Locator;
  readonly notificationsButton: Locator;

  constructor(page: Page) {
    this.page = page;

    // Use accessibility-first selectors (getByRole, getByLabel, getByText)
    this.searchInput = page.getByPlaceholder(/search for stocks/i);
    // New CandlestickChart uses canvas with role="img" and dynamic aria-label
    // Use data-testid as primary selector (more reliable than role for canvas-based charts)
    this.stockChart = page.getByTestId('candlestick-chart');
    // StockHero displays current price with data-testid
    this.priceDisplay = page.getByTestId('stock-hero-price');
    // Note: Page heading "Stock Analysis" was removed in the redesign
    this.errorMessage = page.getByText(/error:/i);
    this.loadingIndicator = page.getByText(/loading stock data/i);
    this.noDataMessage = page.getByText(/no data available/i);
    // Edit and Share buttons were removed in the new design
    this.editButton = page.getByRole('button', { name: /edit/i }); // Won't exist
    this.shareButton = page.getByRole('button', { name: /share/i }); // Won't exist
    this.notificationsButton = page.getByRole('button', { name: /notifications/i });
  }

  async goto() {
    await this.page.goto('/');
    await this.page.waitForLoadState('networkidle');
  }

  async searchStock(symbol: string) {
    await this.searchInput.fill(symbol);
    await this.searchInput.press('Enter');
  }

  async waitForChartToLoad() {
    // Wait for chart container to be visible (it renders immediately)
    await this.stockChart.waitFor({ state: 'visible', timeout: 10000 });
    // Wait for canvas to be present (chart library creates it)
    await this.page.locator('canvas').first().waitFor({ state: 'attached', timeout: 10000 });
    // Give the chart a moment to render the candlesticks
    await this.page.waitForTimeout(1000);
  }

  async getCurrentPrice(): Promise<string | null> {
    return await this.priceDisplay.textContent();
  }

  async getCandlestickCount(): Promise<number> {
    // Canvas-based charts don't expose individual candlesticks to the DOM
    // Return 0 to indicate this feature is not available for canvas charts
    return 0;
  }

  async getGreenCandlestickCount(): Promise<number> {
    // Canvas-based charts don't expose individual candlesticks to the DOM
    return 0;
  }

  async getRedCandlestickCount(): Promise<number> {
    // Canvas-based charts don't expose individual candlesticks to the DOM
    return 0;
  }

  async getYAxisLabels(): Promise<string[]> {
    // Canvas-based charts don't expose axis labels to the DOM
    return [];
  }

  async getXAxisLabels(): Promise<string[]> {
    // Canvas-based charts don't expose axis labels to the DOM
    return [];
  }

  async isChartVisible(): Promise<boolean> {
    return await this.stockChart.isVisible();
  }

  async isLoadingVisible(): Promise<boolean> {
    return await this.loadingIndicator.isVisible();
  }

  async isErrorVisible(): Promise<boolean> {
    return await this.errorMessage.isVisible();
  }

  async isNoDataMessageVisible(): Promise<boolean> {
    return await this.noDataMessage.isVisible();
  }

  async getErrorText(): Promise<string | null> {
    return await this.errorMessage.textContent();
  }

  async clickEdit() {
    // Edit button no longer exists in the new design
    throw new Error('Edit button has been removed from the UI');
  }

  async clickShare() {
    // Share button no longer exists in the new design
    throw new Error('Share button has been removed from the UI');
  }

  async clickNotifications() {
    await this.notificationsButton.click();
  }

  async focusSearchInput() {
    await this.searchInput.focus();
  }

  async isSvgChartPresent(): Promise<boolean> {
    // New chart uses Canvas, not SVG - check for canvas element instead
    const canvasCount = await this.page.locator('canvas').count();
    return canvasCount > 0;
  }

  async getChartDescription(): Promise<string | null> {
    // Canvas chart uses aria-label on the container div, not SVG desc
    const chartContainer = this.stockChart;
    return await chartContainer.getAttribute('aria-label');
  }
}
