export interface SetupDefinition {
  symbol: string;
  entry_price: string; // Decimal as string
  stop_loss_day1: string;
  trailing_stop_pct: string;
  start_date: string; // YYYY-MM-DD
}

export interface TradeResult {
  entry_date: string;
  entry_price: string;
  exit_date: string;
  exit_price: string;
  shares: number;
  pnl: string;
  return_pct: string;
  exit_reason: 'stop_day1' | 'trailing_stop' | 'simulation_end';
}

export interface SetupResult {
  symbol: string;
  entry_price: string;
  stop_loss_day1: string;
  trailing_stop_pct: string;
  start_date: string;
  times_triggered: number;
  pnl: string;
  trades: TradeResult[];
}

export interface SimulationSummary {
  total_pnl: string;
  total_pnl_pct: string;
  total_capital_deployed: string;
  total_trades: number;
  winning_trades: number;
  losing_trades: number;
  win_rate: string | null;
  avg_gain: string | null;
  avg_loss: string | null;
  position_size: string;
}

export interface SetupSimulationResponse {
  summary: SimulationSummary;
  setups: SetupResult[];
}

export interface RunSetupSimulationRequest {
  setups: SetupDefinition[];
  end_date: string;
}
