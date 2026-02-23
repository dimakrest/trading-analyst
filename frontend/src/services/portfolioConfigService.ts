import { apiClient } from '../lib/apiClient';
import type {
  CreatePortfolioConfigRequest,
  PortfolioConfig,
  PortfolioConfigListResponse,
  UpdatePortfolioConfigRequest,
} from '../types/portfolioConfig';

/**
 * Get all portfolio configurations.
 */
const getConfigs = async (): Promise<PortfolioConfigListResponse> => {
  const response = await apiClient.get<PortfolioConfigListResponse>('/v1/portfolio-configs');
  return response.data;
};

/**
 * Get one portfolio configuration by ID.
 */
const getConfig = async (id: number): Promise<PortfolioConfig> => {
  const response = await apiClient.get<PortfolioConfig>(`/v1/portfolio-configs/${id}`);
  return response.data;
};

/**
 * Create portfolio configuration.
 */
const createConfig = async (data: CreatePortfolioConfigRequest): Promise<PortfolioConfig> => {
  const response = await apiClient.post<PortfolioConfig>('/v1/portfolio-configs', data);
  return response.data;
};

/**
 * Update portfolio configuration.
 */
const updateConfig = async (
  id: number,
  data: UpdatePortfolioConfigRequest
): Promise<PortfolioConfig> => {
  const response = await apiClient.put<PortfolioConfig>(`/v1/portfolio-configs/${id}`, data);
  return response.data;
};

/**
 * Delete portfolio configuration.
 */
const deleteConfig = async (id: number): Promise<void> => {
  await apiClient.delete(`/v1/portfolio-configs/${id}`);
};

export const portfolioConfigService = {
  getConfigs,
  getConfig,
  createConfig,
  updateConfig,
  deleteConfig,
};
