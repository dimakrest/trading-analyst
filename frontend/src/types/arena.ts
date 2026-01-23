/**
 * Arena simulation types
 *
 * Type definitions for the Trading Agent Arena feature.
 * Agents compete by making trading decisions on historical data.
 */

/** Simulation lifecycle states */
export type SimulationStatus = 'pending' | 'running' | 'paused' | 'completed' | 'cancelled' | 'failed';

/** Position lifecycle states */
export type PositionStatus = 'pending' | 'open' | 'closed';

/** Why a position was closed */
export type ExitReason = 'stop_hit' | 'simulation_end';

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
  status: SimulationStatus;
  current_day: number;
  total_days: number;
  final_equity: string | null;
  total_return_pct: string | null;
  total_trades: number;
  winning_trades: number;
  max_drawdown_pct: string | null;
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
  /** Trailing stop percentage (default: 5.0) */
  trailing_stop_pct?: number;
  /** Minimum score to generate BUY signal (20-100, default: 60) */
  min_buy_score?: number;
}

/** Response from step endpoint */
export interface StepResponse {
  simulation: Simulation;
  snapshot: Snapshot | null;
  is_complete: boolean;
}
