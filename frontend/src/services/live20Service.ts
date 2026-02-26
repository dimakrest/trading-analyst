import { apiClient } from '../lib/apiClient';
import type { Live20AnalyzeResponse, Live20ResultsResponse, Live20RunListResponse, Live20RunDetail, PortfolioRecommendResponse } from '../types/live20';

const API_BASE = '/v1/live-20';

/**
 * Analyze symbols for Live 20 mean reversion setups
 *
 * Submits a list of stock symbols to the Live 20 analysis API to evaluate
 * mean reversion trading criteria including trend, MA20 position, candle patterns,
 * volume, and momentum (CCI or RSI-2 based on agent config).
 *
 * @param symbols - Array of stock symbols to analyze (max 500)
 * @param sourceLists - Optional array of source list objects with id and name (for tracking)
 * @param agentConfigId - Optional agent configuration ID (determines scoring algorithm)
 * @param signal - Optional AbortSignal to cancel the request
 * @returns Promise resolving to analysis results with recommendations and errors
 * @throws Error if the API request fails
 *
 * @example
 * const response = await analyzeSymbols(['AAPL', 'MSFT', 'NVDA'], null, 1);
 * console.log(`${response.successful}/${response.total} analyzed successfully`);
 */
export const analyzeSymbols = async (
  symbols: string[],
  sourceLists: Array<{ id: number; name: string }> | null = null,
  agentConfigId?: number,
  signal?: AbortSignal
): Promise<Live20AnalyzeResponse> => {
  const body: {
    symbols: string[];
    source_lists?: Array<{ id: number; name: string }>;
    agent_config_id?: number;
  } = { symbols };

  if (sourceLists !== null && sourceLists.length > 0) {
    body.source_lists = sourceLists;
  }

  if (agentConfigId !== undefined) {
    body.agent_config_id = agentConfigId;
  }

  const response = await apiClient.post<Live20AnalyzeResponse>(
    `${API_BASE}/analyze`,
    body,
    { signal }
  );
  return response.data;
};

/**
 * Get Live 20 analysis results with optional filtering
 *
 * Retrieves stored Live 20 analysis results with optional filters for
 * direction (LONG/NO_SETUP), minimum confidence score, and result limit.
 *
 * @param params - Optional filter parameters
 * @param params.direction - Filter by recommendation direction (LONG or NO_SETUP)
 * @param params.min_score - Minimum confidence score threshold
 * @param params.limit - Maximum number of results to return
 * @returns Promise resolving to filtered results with counts
 * @throws Error if the API request fails
 *
 * @example
 * const response = await getResults({ direction: 'LONG', min_score: 80 });
 * console.log(`Found ${response.counts.long} LONG setups`);
 */
export const getResults = async (params?: {
  direction?: string;
  min_score?: number;
  limit?: number;
}): Promise<Live20ResultsResponse> => {
  const searchParams = new URLSearchParams();
  if (params?.direction) searchParams.set('direction', params.direction);
  if (params?.min_score) searchParams.set('min_score', params.min_score.toString());
  if (params?.limit) searchParams.set('limit', params.limit.toString());

  const queryString = searchParams.toString();
  const url = `${API_BASE}/results${queryString ? `?${queryString}` : ''}`;
  const response = await apiClient.get<Live20ResultsResponse>(url);
  return response.data;
};

export interface ListRunsParams {
  limit?: number;
  offset?: number;
  date_from?: string;
  date_to?: string;
  has_direction?: 'LONG' | 'NO_SETUP';
  symbol?: string;
}

/**
 * List Live 20 analysis runs with optional filters
 *
 * @param params - Optional filter parameters
 * @param params.limit - Maximum number of runs to return
 * @param params.offset - Number of runs to skip
 * @param params.date_from - Filter runs created after this date (ISO string)
 * @param params.date_to - Filter runs created before this date (ISO string)
 * @param params.has_direction - Filter runs containing at least one result with this direction
 * @param params.symbol - Filter runs containing this symbol
 * @returns Promise resolving to paginated run list
 * @throws Error if the API request fails
 *
 * @example
 * const response = await listRuns({ limit: 20, offset: 0, has_direction: 'LONG' });
 * console.log(`Found ${response.total} runs`);
 */
export const listRuns = async (
  params: ListRunsParams = {}
): Promise<Live20RunListResponse> => {
  const searchParams = new URLSearchParams();
  if (params.limit) searchParams.set('limit', params.limit.toString());
  if (params.offset) searchParams.set('offset', params.offset.toString());
  if (params.date_from) searchParams.set('date_from', params.date_from);
  if (params.date_to) searchParams.set('date_to', params.date_to);
  if (params.has_direction) searchParams.set('has_direction', params.has_direction);
  if (params.symbol) searchParams.set('symbol', params.symbol);

  const queryString = searchParams.toString();
  const url = `${API_BASE}/runs${queryString ? `?${queryString}` : ''}`;
  const response = await apiClient.get<Live20RunListResponse>(url);
  return response.data;
};

/**
 * Get detailed information about a specific analysis run
 *
 * @param runId - The ID of the run to fetch
 * @returns Promise resolving to run details including all results
 * @throws Error if the API request fails or run not found
 *
 * @example
 * const run = await getRunDetail(42);
 * console.log(`Run ${run.id} analyzed ${run.symbol_count} symbols`);
 */
export const getRunDetail = async (runId: number): Promise<Live20RunDetail> => {
  const response = await apiClient.get<Live20RunDetail>(`${API_BASE}/runs/${runId}`);
  return response.data;
};

/**
 * Cancel a pending or running Live 20 run
 *
 * Stops worker processing; partial results are preserved.
 * Only works for pending/running runs.
 *
 * @param runId - The ID of the run to cancel
 * @throws Error if the API request fails, run not found, or wrong status
 */
export const cancelRun = async (runId: number): Promise<void> => {
  await apiClient.post(`${API_BASE}/runs/${runId}/cancel`);
};

/**
 * Delete a completed, failed, or cancelled Live 20 run
 *
 * Soft-deletes the run from history.
 * Only works for completed/failed/cancelled runs.
 *
 * @param runId - The ID of the run to delete
 * @throws Error if the API request fails, run not found, or wrong status
 */
export const deleteRun = async (runId: number): Promise<void> => {
  await apiClient.delete(`${API_BASE}/runs/${runId}`);
};

/**
 * Sector trend data from sector ETF analysis
 */
export interface SectorTrend {
  sector_etf: string;
  trend_direction: 'up' | 'down' | 'sideways';
  ma20_position: 'above' | 'below';
  ma20_distance_pct: number;
  ma50_position: 'above' | 'below';
  ma50_distance_pct: number;
  price_change_5d_pct: number;
  price_change_20d_pct: number;
}

/**
 * Get sector trend analysis for a sector ETF
 *
 * Fetches trend analysis including MA positions and price changes.
 * Used in expanded Live20 rows to show sector context.
 *
 * @param sectorEtf - Sector ETF symbol (e.g., 'XLK', 'XLE')
 * @returns Promise resolving to sector trend data
 * @throws Error if the API request fails or ETF is invalid
 *
 * @example
 * const trend = await fetchSectorTrend('XLK');
 * console.log(`XLK trend: ${trend.trend_direction}`);
 */
export const fetchSectorTrend = async (sectorEtf: string): Promise<SectorTrend> => {
  const response = await apiClient.get<SectorTrend>(`/v1/stocks/${sectorEtf}/sector-trend`);
  return response.data;
};

/**
 * Get a portfolio recommendation from a completed Live 20 run
 *
 * Filters the run's results by minimum score, then applies the chosen
 * portfolio selection strategy (ranking + sector/position caps) to produce
 * a prioritized list of symbols to trade.
 *
 * @param runId - The ID of the completed Live 20 run
 * @param params - Selection parameters
 * @param params.min_score - Minimum confidence score threshold (5-100)
 * @param params.strategy - Portfolio selection strategy name
 * @param params.max_per_sector - Max positions per sector (null = unlimited)
 * @param params.max_positions - Max total positions (null = unlimited)
 * @returns Promise resolving to ranked recommendation list with summary counts
 * @throws Error if the API request fails or the run is not found/completed
 *
 * @example
 * const rec = await recommendPortfolio(42, {
 *   min_score: 60,
 *   strategy: 'score_sector_low_atr',
 *   max_per_sector: 2,
 *   max_positions: null,
 * });
 * console.log(`${rec.total_qualifying} qualifying → ${rec.total_selected} selected`);
 */
export const recommendPortfolio = async (
  runId: number,
  params: {
    min_score: number;
    strategy: string;
    max_per_sector: number | null;
    max_positions: number | null;
    directions: string[];
  }
): Promise<PortfolioRecommendResponse> => {
  const response = await apiClient.post<PortfolioRecommendResponse>(
    `${API_BASE}/runs/${runId}/recommend`,
    params
  );
  return response.data;
};
