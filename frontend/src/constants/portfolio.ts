/**
 * Portfolio selection strategy definitions
 *
 * Shared between Arena setup form and Live20 Recommend Portfolio dialog.
 * Mirrors the backend SELECTOR_REGISTRY in portfolio_selector.py.
 */

export interface PortfolioStrategyOption {
  /** Strategy identifier matching backend registry key */
  name: string;
  /** Short human-readable label for display */
  label: string;
  /** Longer description explaining the strategy behavior */
  description: string;
  /** Broad grouping for the card UI */
  category: 'basic' | 'score-ranked' | 'multi-factor';
  /** Volatility preference communicated to the user */
  volatility: 'neutral' | 'calm' | 'balanced' | 'volatile';
}

export const PORTFOLIO_STRATEGIES: readonly PortfolioStrategyOption[] = [
  {
    name: 'none',
    label: 'FIFO — Symbol Order',
    description: 'Opens positions in the order symbols appear in your list',
    category: 'basic',
    volatility: 'neutral',
  },
  {
    name: 'score_sector_low_atr',
    label: 'Best Score — Calm',
    description: 'Highest scoring signals, preferring less volatile stocks',
    category: 'score-ranked',
    volatility: 'calm',
  },
  {
    name: 'score_sector_high_atr',
    label: 'Best Score — Volatile',
    description: 'Highest scoring signals, preferring more volatile stocks',
    category: 'score-ranked',
    volatility: 'volatile',
  },
  {
    name: 'score_sector_moderate_atr',
    label: 'Best Score — Balanced',
    description: 'Highest scoring signals, balanced volatility preference',
    category: 'score-ranked',
    volatility: 'balanced',
  },
  {
    name: 'enriched_score',
    label: 'Multi-Factor — Calm',
    description:
      'Score + momentum direction + candle quality + volume, preferring calm stocks',
    category: 'multi-factor',
    volatility: 'calm',
  },
  {
    name: 'enriched_score_high_atr',
    label: 'Multi-Factor — Volatile',
    description:
      'Score + momentum direction + candle quality + volume, preferring volatile stocks',
    category: 'multi-factor',
    volatility: 'volatile',
  },
] as const;
