import { apiClient } from '../lib/apiClient';
import type {
  AgentConfig,
  AgentConfigListResponse,
  CreateAgentConfigRequest,
  UpdateAgentConfigRequest,
} from '../types/agentConfig';

/**
 * Get all agent configurations
 *
 * @returns Promise resolving to agent configurations response
 * @throws Error if the API request fails
 *
 * @example
 * const response = await agentConfigService.getConfigs();
 * console.log(`Found ${response.total} agent configs`);
 */
const getConfigs = async (): Promise<AgentConfigListResponse> => {
  const response = await apiClient.get<AgentConfigListResponse>('/v1/agent-configs');
  return response.data;
};

/**
 * Get a single agent configuration by ID
 *
 * @param id - Unique config identifier
 * @returns Promise resolving to the agent configuration details
 * @throws Error if the API request fails or config not found
 *
 * @example
 * const config = await agentConfigService.getConfig(1);
 * console.log(`Config ${config.name} uses ${config.scoring_algorithm}`);
 */
const getConfig = async (id: number): Promise<AgentConfig> => {
  const response = await apiClient.get<AgentConfig>(`/v1/agent-configs/${id}`);
  return response.data;
};

/**
 * Create a new agent configuration
 *
 * @param data - Config name and algorithm
 * @returns Promise resolving to the created agent configuration
 * @throws Error if the API request fails or validation fails
 *
 * @example
 * const newConfig = await agentConfigService.createConfig({
 *   name: 'RSI-2 Strategy',
 *   scoring_algorithm: 'rsi2'
 * });
 */
const createConfig = async (data: CreateAgentConfigRequest): Promise<AgentConfig> => {
  const response = await apiClient.post<AgentConfig>('/v1/agent-configs', data);
  return response.data;
};

/**
 * Update an existing agent configuration
 *
 * @param id - Unique config identifier
 * @param data - Fields to update (name and/or scoring_algorithm)
 * @returns Promise resolving to the updated agent configuration
 * @throws Error if the API request fails or config not found
 *
 * @example
 * const updatedConfig = await agentConfigService.updateConfig(1, {
 *   name: 'RSI-2 Aggressive',
 *   scoring_algorithm: 'rsi2'
 * });
 */
const updateConfig = async (id: number, data: UpdateAgentConfigRequest): Promise<AgentConfig> => {
  const response = await apiClient.put<AgentConfig>(`/v1/agent-configs/${id}`, data);
  return response.data;
};

/**
 * Delete an agent configuration
 *
 * @param id - Unique config identifier
 * @returns Promise resolving when deletion is complete
 * @throws Error if the API request fails or config not found
 *
 * @example
 * await agentConfigService.deleteConfig(1);
 */
const deleteConfig = async (id: number): Promise<void> => {
  await apiClient.delete(`/v1/agent-configs/${id}`);
};

export const agentConfigService = {
  getConfigs,
  getConfig,
  createConfig,
  updateConfig,
  deleteConfig,
};
