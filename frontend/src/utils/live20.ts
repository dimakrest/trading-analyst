import type { StrategyConfig } from '../types/live20';

/**
 * Get the display label for entry strategy badge.
 * Returns null for default/legacy configs (no badge shown).
 *
 * @param config - Strategy configuration from run
 * @returns Display label like "Breakout +2%" or null for default
 *
 * @example
 * getStrategyDisplayLabel(null) // null (legacy run)
 * getStrategyDisplayLabel({ entry_strategy: 'current_price' }) // null (default)
 * getStrategyDisplayLabel({ entry_strategy: 'breakout_confirmation', breakout_offset_pct: 2.0 }) // "Breakout +2%"
 */
export function getStrategyDisplayLabel(config: StrategyConfig | null): string | null {
  if (!config) return null; // Legacy run
  if (!config.entry_strategy || config.entry_strategy === 'current_price') {
    return null; // Default strategy
  }
  if (config.entry_strategy === 'breakout_confirmation') {
    const offset = config.breakout_offset_pct ?? 2.0;
    return `Breakout +${offset}%`;
  }
  return null;
}

/**
 * Check if ATR multiplier is non-default (default is 0.5).
 *
 * @param config - Strategy configuration from run
 * @returns true if custom ATR multiplier is set
 *
 * @example
 * hasCustomAtrMultiplier(null) // false
 * hasCustomAtrMultiplier({ atr_multiplier: 0.5 }) // false (default)
 * hasCustomAtrMultiplier({ atr_multiplier: 1.0 }) // true (custom)
 */
export function hasCustomAtrMultiplier(config: StrategyConfig | null): boolean {
  if (!config) return false;
  return config.atr_multiplier !== undefined && config.atr_multiplier !== 0.5;
}
