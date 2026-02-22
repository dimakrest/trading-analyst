/**
 * Chart Color Constants
 *
 * Single source of truth for all chart-related colors.
 * Ensures consistency between canvas chart rendering and UI legend elements.
 *
 * Uses Tailwind default colors to maintain design system consistency.
 * If design system changes, update these constants only.
 */

export const CHART_COLORS = {
  /**
   * MA 20 indicator line color
   * Matches Tailwind blue-500: #3b82f6
   */
  MA_20: '#3b82f6',

  /**
   * Bullish candle color (price up)
   * Matches Tailwind green-500: #10b981
   */
  BULLISH: '#10b981',

  /**
   * Bearish candle color (price down)
   * Matches Tailwind red-500: #ef4444
   */
  BEARISH: '#ef4444',

  /**
   * Candle wicks color
   * Matches Tailwind gray-500: #6b7280
   */
  WICKS: '#6b7280',

  /**
   * Trigger price line color
   * Matches Tailwind amber-500: #f59e0b
   */
  TRIGGER_PRICE: '#f59e0b',

  /**
   * Stop loss price line color
   * Matches Tailwind red-500: #ef4444
   */
  STOP_LOSS: '#ef4444',

  /**
   * Entry point marker color
   * Matches Tailwind green-500: #22c55e
   */
  ENTRY_POINT: '#22c55e',

  /**
   * Exit point marker color
   * Matches Tailwind blue-500: #3b82f6
   */
  EXIT_POINT: '#3b82f6',

  /**
   * CCI indicator line color
   * Matches Tailwind purple-500: #8b5cf6
   */
  CCI: '#8b5cf6',

  /**
   * CCI bullish signal marker color
   * Matches Tailwind green-500: #10b981
   */
  CCI_BULLISH: '#10b981',

  /**
   * CCI bearish signal marker color
   * Matches Tailwind red-500: #ef4444
   */
  CCI_BEARISH: '#ef4444',

  /**
   * CCI reference line color
   * Matches Tailwind gray-500: #6b7280
   */
  CCI_REFERENCE: '#6b7280',

  /**
   * Portfolio equity curve line color
   * Matches Tailwind indigo-500: #6366f1
   */
  EQUITY: '#6366f1',

  /**
   * MA 50 indicator line color
   * Matches Tailwind orange-400: #fb923c
   */
  MA_50: '#fb923c',

  /**
   * SPY (S&P 500) benchmark overlay color
   * Matches Tailwind orange-500: #f97316
   */
  SPY: '#f97316',

  /**
   * QQQ (Nasdaq-100) benchmark overlay color
   * Matches Tailwind cyan-400: #22d3ee
   */
  QQQ: '#22d3ee',
} as const;

/**
 * Tailwind CSS class mappings for the same colors
 * Use these for DOM elements (buttons, legend items, etc.)
 */
export const CHART_COLOR_CLASSES = {
  MA_20: 'bg-blue-500',
  BULLISH: 'bg-green-500',
  BEARISH: 'bg-red-500',
  WICKS: 'bg-gray-500',
  CCI: 'bg-purple-500',
} as const;

/**
 * Strategy comparison color palette (up to 4 strategies).
 * Used by ArenaComparisonChart to assign a distinct color to each strategy series.
 */
export const STRATEGY_COLORS = ['#2962FF', '#FF6D00', '#00C853', '#AA00FF'] as const;

/**
 * Chart pane configuration
 * Heights in pixels for each indicator pane
 */
export const CHART_PANE_CONFIG = {
  /** Volume histogram pane height */
  VOLUME_PANE_HEIGHT: 120,
  /** CCI indicator pane height */
  CCI_PANE_HEIGHT: 150,
} as const;
