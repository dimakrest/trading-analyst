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
   * @param value - Numeric score (positive = bullish, zero or negative = no-setup/neutral)
   * @returns Tailwind color class (text-long-signal for positive, text-short-signal for zero/negative)
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

/**
 * Alert status color mappings for stock price alerts
 *
 * Maps each alert status to Tailwind background/text/border classes.
 * Actionable statuses (at_level, at_ma) include animate-pulse for visibility.
 *
 * @example
 * ```tsx
 * <Badge className={ALERT_STATUS_COLORS[status]}>Active</Badge>
 * ```
 */
export const ALERT_STATUS_COLORS: Record<string, string> = {
  rallying: 'bg-accent-bullish/15 text-accent-bullish border border-accent-bullish/30',
  pullback_started: 'bg-yellow-500/15 text-yellow-500 border border-yellow-500/30',
  retracing: 'bg-orange-500/15 text-orange-500 border border-orange-500/30',
  at_level: 'bg-accent-bearish/15 text-accent-bearish border border-accent-bearish/30 animate-pulse',
  bouncing: 'bg-blue-500/15 text-blue-500 border border-blue-500/30',
  invalidated: 'bg-text-muted/15 text-text-muted border border-text-muted/30',
  no_structure: 'bg-text-muted/10 text-text-muted/60 border border-text-muted/20',
  above_ma: 'bg-accent-bullish/15 text-accent-bullish border border-accent-bullish/30',
  approaching: 'bg-yellow-500/15 text-yellow-500 border border-yellow-500/30',
  at_ma: 'bg-accent-bearish/15 text-accent-bearish border border-accent-bearish/30 animate-pulse',
  below_ma: 'bg-orange-500/15 text-orange-500 border border-orange-500/30',
  insufficient_data: 'bg-text-muted/10 text-text-muted/60 border border-text-muted/20',
};
