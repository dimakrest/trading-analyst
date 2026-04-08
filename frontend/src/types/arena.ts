/**
 * Arena simulation types
 *
 * Type definitions for the Trading Agent Arena feature.
 * Agents compete by making trading decisions on historical data.
 */

import type { ScoringAlgorithm } from './live20';

/** Simulation lifecycle states */
export type SimulationStatus = 'pending' | 'running' | 'paused' | 'completed' | 'cancelled' | 'failed';

/** Position lifecycle states */
export type PositionStatus = 'pending' | 'open' | 'closed';

/** Why a position was closed */
export type ExitReason =
  | 'stop_hit'
  | 'simulation_end'
  | 'insufficient_capital'
  | 'insufficient_data'
  | 'take_profit'
  | 'max_hold';

/** Agent information from /api/v1/arena/agents */
export interface AgentInfo {
  /** Agent type identifier (e.g., 'live20') */
  type: string;
  /** Human-readable agent name */
  name: string;
  /** Number of days of historical data required */
  required_lookback_days: number;
}

/** Simulation summary for list view */
export interface Simulation {
  id: number;
  name: string | null;
  stock_list_id: number | null;
  stock_list_name: string | null;
  symbols: string[];
  start_date: string;
  end_date: string;
  initial_capital: string;
  position_size: string;
  agent_type: string;
  trailing_stop_pct: string | null;
  min_buy_score: number | null;
  scoring_algorithm: ScoringAlgorithm | null;
  volume_score?: number | null;
  candle_pattern_score?: number | null;
  cci_score?: number | null;
  ma20_distance_score?: number | null;
  portfolio_strategy: string | null;
  max_per_sector: number | null;
  max_open_positions: number | null;
  ma_sweet_spot_center?: number | null;
  stop_type?: 'fixed' | 'atr' | null;
  atr_stop_multiplier?: number | null;
  atr_stop_min_pct?: number | null;
  atr_stop_max_pct?: number | null;
  position_size_pct?: number | null;
  sizing_mode?: 'fixed' | 'fixed_pct' | 'risk_based' | null;
  risk_per_trade_pct?: number | null;
  win_streak_bonus_pct?: number | null;
  max_risk_pct?: number | null;
  group_id: string | null;
  status: SimulationStatus;
  current_day: number;
  total_days: number;
  final_equity: string | null;
  total_return_pct: string | null;
  total_trades: number;
  winning_trades: number;
  max_drawdown_pct: string | null;
  avg_hold_days: string | null;
  avg_win_pnl: string | null;
  avg_loss_pnl: string | null;
  profit_factor: string | null;
  sharpe_ratio: string | null;
  total_realized_pnl: string | null;
  created_at: string;
}

/** Paginated response for simulation list */
export interface SimulationListResponse {
  items: Simulation[];
  total: number;
  has_more: boolean;
}

/** Trading position within a simulation */
export interface Position {
  id: number;
  symbol: string;
  status: PositionStatus;
  signal_date: string;
  entry_date: string | null;
  entry_price: string | null;
  shares: number | null;
  highest_price: string | null;
  current_stop: string | null;
  exit_date: string | null;
  exit_price: string | null;
  exit_reason: ExitReason | null;
  realized_pnl: string | null;
  return_pct: string | null;
  agent_reasoning: string | null;
  agent_score: number | null;
  sector: string | null;
}

/** Agent decision for a symbol on a given day */
export interface AgentDecision {
  action: string;
  score: number | null;
  reasoning: string | null;
}

/** Daily snapshot of portfolio state */
export interface Snapshot {
  id: number;
  snapshot_date: string;
  day_number: number;
  cash: string;
  positions_value: string;
  total_equity: string;
  daily_pnl: string;
  daily_return_pct: string;
  cumulative_return_pct: string;
  open_position_count: number;
  /** Agent decisions keyed by symbol */
  decisions: Record<string, AgentDecision>;
}

/** Full simulation detail with positions and snapshots */
export interface SimulationDetail {
  simulation: Simulation;
  positions: Position[];
  snapshots: Snapshot[];
}

/** Request body for creating a new simulation */
export interface CreateSimulationRequest {
  /** Optional user-provided name */
  name?: string;
  /** ID of stock list used to populate symbols (optional) */
  stock_list_id?: number;
  /** Name of stock list at time of creation (optional) */
  stock_list_name?: string;
  /** List of stock symbols to trade */
  symbols: string[];
  /** Start date in YYYY-MM-DD format */
  start_date: string;
  /** End date in YYYY-MM-DD format */
  end_date: string;
  /** Starting capital (default: 10000) */
  initial_capital?: number;
  /** Fixed position size per trade (default: 1000) */
  position_size?: number;
  /** Agent type (default: 'live20') */
  agent_type?: string;
  /** Trailing stop type: 'fixed' or 'atr' (default: 'fixed') */
  stop_type?: 'fixed' | 'atr';
  /** ATR stop multiplier (default: 2.0, used when stop_type='atr') */
  atr_stop_multiplier?: number;
  /** ATR stop minimum percentage floor (default: 2.0, used when stop_type='atr') */
  atr_stop_min_pct?: number;
  /** ATR stop maximum percentage ceiling (default: 10.0, used when stop_type='atr') */
  atr_stop_max_pct?: number;
  /** Trailing stop percentage (default: 5.0) */
  trailing_stop_pct?: number;
  /** Minimum score to generate BUY signal (20-100, default: 60) */
  min_buy_score?: number;
  /** Agent configuration ID to use for this simulation */
  agent_config_id?: number;
  /** Scoring algorithm (fallback if no agent_config_id) */
  scoring_algorithm?: ScoringAlgorithm;
  /** Portfolio selection strategy */
  portfolio_strategy?: string;
  /** Max concurrent positions per sector (null = unlimited) */
  max_per_sector?: number | null;
  /** Max total open positions (null = unlimited) */
  max_open_positions?: number | null;
  /** MA20 sweet spot center percentage for enriched_score strategies */
  ma_sweet_spot_center?: number;
  /** Position sizing mode: 'fixed', 'fixed_pct', or 'risk_based' (default: 'fixed') */
  sizing_mode?: 'fixed' | 'fixed_pct' | 'risk_based';
  /** Position size as percentage of equity (used when sizing_mode='fixed_pct') */
  position_size_pct?: number;
  /** Base risk per trade as % of equity (used when sizing_mode='risk_based') */
  risk_per_trade_pct?: number;
  /** Extra risk % per consecutive win (used when sizing_mode='risk_based') */
  win_streak_bonus_pct?: number;
  /** Maximum effective risk % per trade cap (used when sizing_mode='risk_based') */
  max_risk_pct?: number;
}

/** Response from step endpoint */
export interface StepResponse {
  simulation: Simulation;
  snapshot: Snapshot | null;
  is_complete: boolean;
}

/** Single data point for benchmark (SPY / QQQ) price series. */
export interface BenchmarkDataPoint {
  date: string;
  close: string;
  cumulative_return_pct: string;
}

/** Request body for creating a multi-strategy comparison */
export interface CreateComparisonRequest {
  name?: string;
  stock_list_id?: number;
  stock_list_name?: string;
  symbols: string[];
  start_date: string;
  end_date: string;
  initial_capital?: number;
  position_size?: number;
  agent_type?: string;
  /** Trailing stop type: 'fixed' or 'atr' (default: 'fixed') */
  stop_type?: 'fixed' | 'atr';
  /** ATR stop multiplier (default: 2.0, used when stop_type='atr') */
  atr_stop_multiplier?: number;
  /** ATR stop minimum percentage floor (default: 2.0, used when stop_type='atr') */
  atr_stop_min_pct?: number;
  /** ATR stop maximum percentage ceiling (default: 10.0, used when stop_type='atr') */
  atr_stop_max_pct?: number;
  trailing_stop_pct?: number;
  min_buy_score?: number;
  agent_config_id?: number;
  scoring_algorithm?: ScoringAlgorithm;
  portfolio_strategies: string[];
  max_per_sector?: number | null;
  max_open_positions?: number | null;
  /** Position sizing mode: 'fixed', 'fixed_pct', or 'risk_based' (default: 'fixed') */
  sizing_mode?: 'fixed' | 'fixed_pct' | 'risk_based';
  /** Position size as percentage of equity (used when sizing_mode='fixed_pct') */
  position_size_pct?: number;
  /** Base risk per trade as % of equity (used when sizing_mode='risk_based') */
  risk_per_trade_pct?: number;
  /** Extra risk % per consecutive win (used when sizing_mode='risk_based') */
  win_streak_bonus_pct?: number;
  /** Maximum effective risk % per trade cap (used when sizing_mode='risk_based') */
  max_risk_pct?: number;
}

/** Response from comparison creation / retrieval */
export interface ComparisonResponse {
  group_id: string;
  simulations: Simulation[];
}

/** A single data point in an equity curve (date + equity value). */
export interface EquityCurvePoint {
  /** Date of the snapshot */
  snapshot_date: string;
  /** Portfolio total equity at this point (USD amount as string) */
  total_equity: string;
}

/** Equity curve for a single simulation in a comparison group. */
export interface SimulationEquityCurve {
  /** ID of the simulation */
  simulation_id: number;
  /** Portfolio strategy name (null if not set) */
  portfolio_strategy: string | null;
  /** Time-series data points for the equity curve */
  snapshots: EquityCurvePoint[];
}

/** Lightweight equity curves for all simulations in a comparison group. */
export interface ComparisonEquityCurvesResponse {
  /** UUID of the comparison group */
  group_id: string;
  /** Equity curves for all simulations in the group */
  simulations: SimulationEquityCurve[];
}
