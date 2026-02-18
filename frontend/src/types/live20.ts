export type Live20Direction = 'LONG' | 'SHORT' | 'NO_SETUP';

export type VolumeApproach = 'exhaustion' | 'accumulation' | 'distribution' | null;

export type ScoringAlgorithm = 'cci' | 'rsi2';

export interface Live20Result {
  id: number;
  stock: string;
  created_at: string;
  recommendation: Live20Direction;
  confidence_score: number;
  atr: number | null;

  // Criteria details
  trend_direction: string | null;
  trend_aligned: boolean | null;
  ma20_distance_pct: number | null;
  ma20_aligned: boolean | null;
  candle_pattern: string | null;
  candle_bullish: boolean | null;  // true if close > open (green candle)
  candle_aligned: boolean | null;
  candle_explanation: string | null;
  volume_aligned: boolean | null;
  volume_approach: VolumeApproach;
  rvol: number | null;
  cci_direction: string | null;  // "rising", "falling", "flat"
  cci_value: number | null;
  cci_zone: string | null;
  cci_aligned: boolean | null;
  criteria_aligned: number | null;
  direction: Live20Direction | null;
  sector_etf: string | null;

  // Scoring algorithm fields
  scoring_algorithm: ScoringAlgorithm | null;
  rsi2_value: number | null;
  rsi2_score: number | null;
}

/**
 * Response from POST /api/v1/live-20/analyze
 *
 * With async processing, this returns immediately with run_id and status.
 * Use GET /api/v1/live-20/runs/{run_id} to poll for results.
 */
export interface Live20AnalyzeResponse {
  run_id: number;
  status: string;
  total: number;
  message: string | null;
}

export interface Live20ResultsResponse {
  results: Live20Result[];
  total: number;
  counts: {
    long: number;
    short: number;
    no_setup: number;
  };
}

export interface Live20Counts {
  long: number;
  short: number;
  no_setup: number;
  total: number;
}

export interface Live20RunSummary {
  id: number;
  created_at: string;
  status: string;
  symbol_count: number;
  processed_count: number;
  long_count: number;
  short_count: number;
  no_setup_count: number;
  stock_list_id: number | null;
  stock_list_name: string | null;
  source_lists?: Array<{ id: number; name: string }> | null;
  scoring_algorithm: ScoringAlgorithm | null;
}

export interface Live20RunListResponse {
  items: Live20RunSummary[];
  total: number;
  has_more: boolean;
  limit: number;
  offset: number;
}

export interface Live20RunDetail {
  id: number;
  created_at: string;
  status: string;
  symbol_count: number;
  processed_count: number;
  long_count: number;
  short_count: number;
  no_setup_count: number;
  input_symbols: string[];
  stock_list_id: number | null;
  stock_list_name: string | null;
  source_lists?: Array<{ id: number; name: string }> | null;
  results: Live20Result[];
  error_message?: string | null;
  failed_symbols?: Record<string, string>;
  scoring_algorithm: ScoringAlgorithm | null;
}

/** Portfolio recommendation types -- used by Live20 Recommend Portfolio feature */

export interface PortfolioRecommendItem {
  symbol: string;
  score: number;
  direction: string | null;
  sector: string | null;
  atr_pct: number | null;
}

export interface PortfolioRecommendResponse {
  strategy: string;
  strategy_description: string;
  items: PortfolioRecommendItem[];
  total_qualifying: number;
  total_selected: number;
}
