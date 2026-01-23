import { describe, it, expect, vi, beforeEach } from 'vitest';
import type { InternalAxiosRequestConfig } from 'axios';
import { getSystemStatus } from './accountService';
import { apiClient } from '../lib/apiClient';
import type { SystemStatus } from '../types/account';

vi.mock('../lib/apiClient');

const mockSystemStatus: SystemStatus = {
  broker: {
    connection_status: 'CONNECTED',
    error_message: null,
    account_id: 'DU1234567',
    account_type: 'PAPER',
    net_liquidation: '25000.00',
    buying_power: '50000.00',
    unrealized_pnl: '150.50',
    realized_pnl: '75.25',
    daily_pnl: '225.75',
  },
  data_provider: {
    connection_status: 'CONNECTED',
    error_message: null,
  },
};

describe('getSystemStatus', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('fetches system status from API', async () => {
    vi.mocked(apiClient.get).mockResolvedValue({
      data: mockSystemStatus,
      status: 200,
      statusText: 'OK',
      headers: {},
      config: {} as InternalAxiosRequestConfig,
    });

    const result = await getSystemStatus();

    expect(apiClient.get).toHaveBeenCalledWith('/v1/account/status', { signal: undefined });
    expect(result).toEqual(mockSystemStatus);
  });

  it('passes AbortSignal to API client when provided', async () => {
    vi.mocked(apiClient.get).mockResolvedValue({
      data: mockSystemStatus,
      status: 200,
      statusText: 'OK',
      headers: {},
      config: {} as InternalAxiosRequestConfig,
    });

    const controller = new AbortController();
    const result = await getSystemStatus(controller.signal);

    expect(apiClient.get).toHaveBeenCalledWith('/v1/account/status', { signal: controller.signal });
    expect(result).toEqual(mockSystemStatus);
  });

  it('throws error when API call fails', async () => {
    vi.mocked(apiClient.get).mockRejectedValue(new Error('Network error'));

    await expect(getSystemStatus()).rejects.toThrow('Network error');
  });
});
