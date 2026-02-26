/**
 * Portfolio selection strategy definitions
 *
 * Shared between Arena setup form and Live20 Recommend Portfolio dialog.
 * Mirrors the backend SELECTOR_REGISTRY in portfolio_selector.py.
 */

export interface PortfolioStrategyOption {
  /** Strategy identifier matching backend registry key */
  name: string;
  /** Short human-readable label for dropdowns */
  label: string;
  /** Longer description explaining the strategy behavior */
  description: string;
}

export const PORTFOLIO_STRATEGIES: readonly PortfolioStrategyOption[] = [
  {
    name: 'none',
    label: 'None (symbol order)',
    description: 'No ranking — opens positions in symbol list order (original behavior)',
  },
  {
    name: 'score_sector_low_atr',
    label: 'Score + Low ATR',
    description: 'Rank by score, prefer lowest ATR% (tighter stops, calmer stocks)',
  },
  {
    name: 'score_sector_high_atr',
    label: 'Score + High ATR',
    description: 'Rank by score, prefer highest ATR% (wider swings, more upside potential)',
  },
  {
    name: 'score_sector_moderate_atr',
    label: 'Score + Moderate ATR',
    description: 'Rank by score, prefer ATR% closest to median (avoid extremes)',
  },
] as const;
