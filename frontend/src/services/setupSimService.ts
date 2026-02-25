/**
 * Setup Simulation Service
 *
 * API client for the setup simulation endpoint.
 * Runs a stateless backtest against user-defined setup definitions.
 */
import { apiClient } from '../lib/apiClient';
import type { RunSetupSimulationRequest, SetupSimulationResponse } from '../types/setupSim';

const API_BASE = '/v1/setup-sim';

/**
 * Run a setup simulation synchronously.
 *
 * Sends user-defined setups and an end date to the backend, which fetches
 * historical price data and returns complete simulation results.
 *
 * @param request - Setups and end date for the simulation
 * @returns Complete simulation results including summary and per-setup trades
 */
export const runSetupSimulation = async (
  request: RunSetupSimulationRequest,
): Promise<SetupSimulationResponse> => {
  const response = await apiClient.post<SetupSimulationResponse>(
    `${API_BASE}/run`,
    request,
  );
  return response.data;
};
