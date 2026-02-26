/**
 * Utility functions for candlestick pattern handling
 */

/**
 * Get human-readable label for a candlestick pattern
 */
export function getCandlePatternLabel(pattern: string | null): string {
  if (!pattern) return 'Unknown';

  const labels: Record<string, string> = {
    doji: 'Doji',
    hammer: 'Hammer',
    hanging_man: 'Hanging Man',
    shooting_star: 'Shooting Star',
    inverted_hammer: 'Inverted Hammer',
    engulfing_bullish: 'Bullish Engulfing',
    engulfing_bearish: 'Bearish Engulfing',
    marubozu_bullish: 'Bullish Marubozu',
    marubozu_bearish: 'Bearish Marubozu',
    spinning_top: 'Spinning Top',
    standard: 'Standard',
  };

  return labels[pattern.toLowerCase()] || pattern;
}
