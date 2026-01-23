/**
 * Arena Service
 *
 * API client for Trading Agent Arena endpoints.
 * Handles simulation CRUD operations.
 */
import { apiClient } from '../lib/apiClient';
import type {
  AgentInfo,
  CreateSimulationRequest,
  Simulation,
  SimulationDetail,
  SimulationListResponse,
} from '../types/arena';

const API_BASE = '/v1/arena';

/**
 * Get available trading agents
 *
 * @returns Promise resolving to array of agent info
 */
export const getAgents = async (): Promise<AgentInfo[]> => {
  const response = await apiClient.get<AgentInfo[]>(`${API_BASE}/agents`);
  return response.data;
};

/**
 * Create a new simulation
 *
 * @param request - Simulation configuration
 * @returns Promise resolving to created simulation
 */
export const createSimulation = async (
  request: CreateSimulationRequest
): Promise<Simulation> => {
  const response = await apiClient.post<Simulation>(
    `${API_BASE}/simulations`,
    request
  );
  return response.data;
};

/**
 * List recent simulations
 *
 * @param limit - Maximum number of simulations to return (default: 20)
 * @param offset - Number of simulations to skip (default: 0)
 * @returns Promise resolving to simulation list response with items and pagination metadata
 */
export const listSimulations = async (
  limit = 20,
  offset = 0
): Promise<SimulationListResponse> => {
  const response = await apiClient.get<SimulationListResponse>(
    `${API_BASE}/simulations?limit=${limit}&offset=${offset}`
  );
  return response.data;
};

/**
 * Get simulation detail with positions and snapshots
 *
 * @param id - Simulation ID
 * @returns Promise resolving to simulation detail
 */
export const getSimulation = async (id: number): Promise<SimulationDetail> => {
  const response = await apiClient.get<SimulationDetail>(
    `${API_BASE}/simulations/${id}`
  );
  return response.data;
};

/**
 * Cancel a running simulation
 *
 * Stops worker processing; partial results are preserved.
 * Only works for pending/running/paused simulations.
 *
 * @param id - Simulation ID to cancel
 * @throws Error if wrong status or not found
 */
export const cancelSimulation = async (id: number): Promise<void> => {
  await apiClient.post(`${API_BASE}/simulations/${id}/cancel`);
};

/**
 * Delete a completed, failed, or cancelled simulation
 *
 * Permanently removes the simulation from history.
 * Only works for completed/failed/cancelled simulations.
 *
 * @param id - Simulation ID to delete
 * @throws Error if wrong status or not found
 */
export const deleteSimulation = async (id: number): Promise<void> => {
  await apiClient.delete(`${API_BASE}/simulations/${id}`);
};
