/**
 * Portfolio configuration entity.
 */
export interface PortfolioConfig {
  id: number;
  name: string;
  portfolio_strategy: string;
  position_size: number;
  min_buy_score: number;
  trailing_stop_pct: number;
  max_per_sector: number | null;
  max_open_positions: number | null;
}

/**
 * Response from GET /api/v1/portfolio-configs.
 */
export interface PortfolioConfigListResponse {
  items: PortfolioConfig[];
  total: number;
}

/**
 * Request body for creating a new portfolio configuration.
 */
export interface CreatePortfolioConfigRequest {
  name: string;
  portfolio_strategy: string;
  position_size?: number;
  min_buy_score?: number;
  trailing_stop_pct?: number;
  max_per_sector?: number | null;
  max_open_positions?: number | null;
}

/**
 * Request body for updating a portfolio configuration.
 */
export interface UpdatePortfolioConfigRequest {
  name?: string;
  portfolio_strategy?: string;
  position_size?: number;
  min_buy_score?: number;
  trailing_stop_pct?: number;
  max_per_sector?: number | null;
  max_open_positions?: number | null;
}
