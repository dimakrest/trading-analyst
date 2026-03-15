/**
 * Alert Service
 *
 * API client functions for stock price alert CRUD operations and data fetching.
 * Covers Fibonacci retracement and moving average alert types.
 */

import { apiClient } from '../lib/apiClient';
import type {
  AlertListResponse,
  CreateAlertRequest,
  StockAlert,
  UpdateAlertRequest,
  AlertEvent,
  AlertPriceDataResponse,
} from '../types/alert';

const API_BASE = '/v1/alerts';

/**
 * List all alerts with optional filters
 *
 * @param params - Optional filter parameters
 * @param params.status - Filter by alert status
 * @param params.alert_type - Filter by alert type ('fibonacci' | 'moving_average')
 * @param params.symbol - Filter by stock symbol
 * @returns Promise resolving to paginated alert list
 * @throws Error if the API request fails
 */
export const listAlerts = async (params?: {
  status?: string;
  alert_type?: string;
  symbol?: string;
}): Promise<AlertListResponse> => {
  const response = await apiClient.get<AlertListResponse>(`${API_BASE}/`, { params });
  return response.data;
};

/**
 * Create one or more alerts
 *
 * For moving_average alerts with multiple ma_periods, the backend returns
 * one alert per period in the response array.
 *
 * @param data - Alert creation request (fibonacci or moving_average)
 * @returns Promise resolving to array of created alerts
 * @throws Error if the API request fails
 */
export const createAlert = async (data: CreateAlertRequest): Promise<StockAlert[]> => {
  const response = await apiClient.post<StockAlert[]>(`${API_BASE}/`, data);
  return response.data;
};

/**
 * Get a single alert by ID
 *
 * @param id - Alert ID
 * @returns Promise resolving to the alert with latest computed state
 * @throws Error if the API request fails or alert is not found
 */
export const getAlert = async (id: number): Promise<StockAlert> => {
  const response = await apiClient.get<StockAlert>(`${API_BASE}/${id}`);
  return response.data;
};

/**
 * Update an alert's config or paused state
 *
 * @param id - Alert ID
 * @param data - Fields to update (config and/or is_paused)
 * @returns Promise resolving to the updated alert
 * @throws Error if the API request fails or alert is not found
 */
export const updateAlert = async (id: number, data: UpdateAlertRequest): Promise<StockAlert> => {
  const response = await apiClient.patch<StockAlert>(`${API_BASE}/${id}`, data);
  return response.data;
};

/**
 * Delete an alert permanently
 *
 * @param id - Alert ID
 * @throws Error if the API request fails or alert is not found
 */
export const deleteAlert = async (id: number): Promise<void> => {
  await apiClient.delete(`${API_BASE}/${id}`);
};

/**
 * Get the event history for an alert
 *
 * Returns level hits, status changes, invalidations, and re-anchors in
 * reverse chronological order.
 *
 * @param id - Alert ID
 * @returns Promise resolving to array of alert events
 * @throws Error if the API request fails or alert is not found
 */
export const getAlertEvents = async (id: number): Promise<AlertEvent[]> => {
  const response = await apiClient.get<AlertEvent[]>(`${API_BASE}/${id}/events`);
  return response.data;
};

/**
 * Get historical price data for an alert's symbol
 *
 * Used to render the price chart in the alert detail view.
 *
 * @param id - Alert ID
 * @param days - Number of calendar days of history to fetch (default: 365)
 * @returns Promise resolving to OHLCV data and metadata
 * @throws Error if the API request fails or alert is not found
 */
export const getAlertPriceData = async (id: number, days = 365): Promise<AlertPriceDataResponse> => {
  const response = await apiClient.get<AlertPriceDataResponse>(`${API_BASE}/${id}/price-data`, {
    params: { days },
  });
  return response.data;
};
