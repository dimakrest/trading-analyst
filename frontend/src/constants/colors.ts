/**
 * Semantic color mapping constants for trading application
 *
 * These constants provide type-safe, reusable color logic for common UI patterns.
 * They wrap the semantic color tokens defined in index.css into convenient helpers.
 */

/**
 * Position P&L color utility
 *
 * Maps profit/loss values to semantic color classes (green for profit, red for loss).
 *
 * @example
 * ```tsx
 * <span className={POSITION_COLORS.profitLoss(pnlValue)}>
 *   ${pnlValue.toFixed(2)}
 * </span>
 * ```
 */
export const POSITION_COLORS = {
  /**
   * Get color class based on P&L value
   * @param value - Numeric P&L value (positive = profit, negative = loss)
   * @returns Tailwind color class (text-profit or text-loss)
   */
  profitLoss: (value: number): string => (value >= 0 ? 'text-profit' : 'text-loss'),

  /**
   * Get background color class based on P&L value
   * @param value - Numeric P&L value (positive = profit, negative = loss)
   * @returns Tailwind background color class with opacity
   */
  profitLossBg: (value: number): string => (value >= 0 ? 'bg-profit/10' : 'bg-loss/10'),
} as const;

/**
 * Trade direction type for screener
 */
export type TradeDirection = 'LONG' | 'NEUTRAL';

/**
 * Screener color utilities
 *
 * Maps trade directions and scores to semantic color classes (teal/orange for reduced alarm fatigue).
 *
 * @example
 * ```tsx
 * <Badge className={SCREENER_COLORS.direction.LONG}>LONG</Badge>
 * <span className={SCREENER_COLORS.score(scoreValue)}>Score: {scoreValue}</span>
 * ```
 */
export const SCREENER_COLORS = {
  /**
   * Direction-based color classes (full color with background)
   */
  direction: {
    LONG: 'text-long-signal bg-long-signal/10',
    NEUTRAL: 'text-muted-foreground bg-muted',
  } as const satisfies Record<TradeDirection, string>,

  /**
   * Score-based color class (text only)
   * @param value - Numeric score (positive = long bias, negative = short bias)
   * @returns Tailwind color class (text-long-signal or text-short-signal)
   */
  score: (value: number): string => (value > 0 ? 'text-long-signal' : 'text-short-signal'),

  /**
   * Badge variants for screener signals
   */
  badge: {
    LONG: 'bg-long-signal text-white hover:bg-long-signal/80',
    NEUTRAL: 'bg-muted-foreground text-white hover:bg-muted-foreground/80',
  } as const satisfies Record<TradeDirection, string>,
} as const;

/**
 * Technical indicator color utilities
 *
 * Uses neutral blue/purple colors for directional indicators that don't represent immediate P&L.
 *
 * @example
 * ```tsx
 * <span className={INDICATOR_COLORS.trend(trendValue)}>
 *   {trendValue > 0 ? '↑' : '↓'} Trend
 * </span>
 * ```
 */
export const INDICATOR_COLORS = {
  /**
   * Trend-based color class
   * @param value - Numeric trend value (positive = up, negative = down)
   * @returns Tailwind color class (text-up-indicator or text-down-indicator)
   */
  trend: (value: number): string => (value >= 0 ? 'text-up-indicator' : 'text-down-indicator'),
} as const;
