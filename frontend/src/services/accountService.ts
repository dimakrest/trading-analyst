import { apiClient } from '../lib/apiClient';
import type { SystemStatus } from '../types/account';

export const getSystemStatus = async (signal?: AbortSignal): Promise<SystemStatus> => {
  const response = await apiClient.get<SystemStatus>('/v1/account/status', { signal });
  return response.data;
};
