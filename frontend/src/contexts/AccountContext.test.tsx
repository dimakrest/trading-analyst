import { renderHook, waitFor } from '@testing-library/react';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import { AccountProvider, useAccount } from './AccountContext';
import * as accountService from '@/services/accountService';
import type { SystemStatus } from '@/types/account';

vi.mock('@/services/accountService');

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

describe('AccountContext', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('fetches system status on mount', async () => {
    vi.mocked(accountService.getSystemStatus).mockResolvedValue(mockSystemStatus);

    const { result } = renderHook(() => useAccount(), {
      wrapper: AccountProvider,
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.status).toEqual(mockSystemStatus);
    expect(accountService.getSystemStatus).toHaveBeenCalledTimes(1);
    // Verify AbortSignal was passed
    expect(accountService.getSystemStatus).toHaveBeenCalledWith(expect.any(AbortSignal));
  });

  it('handles fetch errors gracefully', async () => {
    vi.mocked(accountService.getSystemStatus).mockRejectedValue(
      new Error('Network error')
    );

    const { result } = renderHook(() => useAccount(), {
      wrapper: AccountProvider,
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.error).toBe('Network error');
    expect(result.current.status?.broker.connection_status).toBe('DISCONNECTED');
    expect(result.current.status?.data_provider.connection_status).toBe('DISCONNECTED');
  });

  it('shows both broker and data provider as disconnected on error', async () => {
    vi.mocked(accountService.getSystemStatus).mockRejectedValue(
      new Error('API unreachable')
    );

    const { result } = renderHook(() => useAccount(), {
      wrapper: AccountProvider,
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.status?.broker.error_message).toBe('API unreachable');
    expect(result.current.status?.data_provider.error_message).toBe('API unreachable');
  });

  it('cancels in-flight requests on unmount', async () => {
    const abortSpy = vi.fn();
    let capturedSignal: AbortSignal | undefined;

    vi.mocked(accountService.getSystemStatus).mockImplementation((signal) => {
      capturedSignal = signal;
      // Add spy to the signal's abort event
      signal?.addEventListener('abort', abortSpy);
      // Return a promise that never resolves (simulating slow request)
      return new Promise(() => {});
    });

    const { unmount } = renderHook(() => useAccount(), {
      wrapper: AccountProvider,
    });

    // Wait for the effect to fire
    await waitFor(() => {
      expect(accountService.getSystemStatus).toHaveBeenCalled();
    });

    // Unmount should trigger abort
    unmount();

    // Wait for abort to be called
    await waitFor(() => {
      expect(abortSpy).toHaveBeenCalled();
    });

    expect(capturedSignal?.aborted).toBe(true);
  });

  it('ignores CanceledError and does not set error state', async () => {
    const cancelError = new Error('Request canceled');
    cancelError.name = 'CanceledError';

    vi.mocked(accountService.getSystemStatus).mockRejectedValue(cancelError);

    const { result } = renderHook(() => useAccount(), {
      wrapper: AccountProvider,
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    // Should not set error state for canceled requests
    expect(result.current.error).toBe(null);
    // Status should remain null (not set to disconnected)
    expect(result.current.status).toBe(null);
  });
});
