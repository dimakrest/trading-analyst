import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useArenaPolling } from './useArenaPolling';
import * as arenaService from '../services/arenaService';
import type { SimulationDetail } from '../types/arena';

// Mock the arena service
vi.mock('../services/arenaService', () => ({
  getSimulation: vi.fn(),
  cancelSimulation: vi.fn(),
}));

const mockDetail: SimulationDetail = {
  simulation: {
    id: 1,
    name: 'Test Simulation',
    stock_list_id: null,
    stock_list_name: null,
    symbols: ['AAPL'],
    start_date: '2024-01-01',
    end_date: '2024-01-31',
    initial_capital: '10000',
    position_size: '1000',
    agent_type: 'live20',
    trailing_stop_pct: '5.0',
    min_buy_score: 60,
    status: 'running',
    current_day: 10,
    total_days: 22,
    final_equity: null,
    total_return_pct: null,
    total_trades: 2,
    winning_trades: 1,
    max_drawdown_pct: null,
    created_at: '2024-01-01T10:00:00Z',
  },
  positions: [],
  snapshots: [],
};

const mockCompletedDetail: SimulationDetail = {
  simulation: {
    ...mockDetail.simulation,
    status: 'completed',
    current_day: 22,
    final_equity: '10500',
    total_return_pct: '5.00',
  },
  positions: [],
  snapshots: [],
};

describe('useArenaPolling', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.clearAllTimers();
    vi.useRealTimers();
  });

  it('should return null detail when simulationId is null', () => {
    const { result } = renderHook(() => useArenaPolling(null));

    expect(result.current.detail).toBeNull();
    expect(result.current.isPolling).toBe(false);
    expect(result.current.error).toBeNull();
  });

  it('should fetch simulation detail on mount', async () => {
    (arenaService.getSimulation as ReturnType<typeof vi.fn>).mockResolvedValue(mockDetail);

    const { result } = renderHook(() => useArenaPolling(1));

    // Initial fetch triggered on mount
    expect(arenaService.getSimulation).toHaveBeenCalledWith(1);

    await act(async () => {
      await vi.runOnlyPendingTimersAsync();
    });

    expect(result.current.detail).toEqual(mockDetail);
    expect(result.current.isPolling).toBe(true);
    expect(result.current.error).toBeNull();
  });

  it('should stop polling when simulation is completed', async () => {
    (arenaService.getSimulation as ReturnType<typeof vi.fn>).mockResolvedValue(mockCompletedDetail);

    const { result } = renderHook(() => useArenaPolling(1));

    await act(async () => {
      await vi.runOnlyPendingTimersAsync();
    });

    expect(result.current.detail?.simulation.status).toBe('completed');
    expect(result.current.isPolling).toBe(false);
  });

  it('should stop polling when simulation is cancelled', async () => {
    const cancelledDetail = {
      ...mockDetail,
      simulation: { ...mockDetail.simulation, status: 'cancelled' as const },
    };
    (arenaService.getSimulation as ReturnType<typeof vi.fn>).mockResolvedValue(cancelledDetail);

    const { result } = renderHook(() => useArenaPolling(1));

    await act(async () => {
      await vi.runOnlyPendingTimersAsync();
    });

    expect(result.current.isPolling).toBe(false);
  });

  it('should stop polling when simulation fails', async () => {
    const failedDetail = {
      ...mockDetail,
      simulation: { ...mockDetail.simulation, status: 'failed' as const },
    };
    (arenaService.getSimulation as ReturnType<typeof vi.fn>).mockResolvedValue(failedDetail);

    const { result } = renderHook(() => useArenaPolling(1));

    await act(async () => {
      await vi.runOnlyPendingTimersAsync();
    });

    expect(result.current.isPolling).toBe(false);
  });

  it('should handle fetch error', async () => {
    (arenaService.getSimulation as ReturnType<typeof vi.fn>).mockRejectedValue(
      new Error('Network error')
    );

    const { result } = renderHook(() => useArenaPolling(1));

    await act(async () => {
      await vi.runOnlyPendingTimersAsync();
    });

    expect(result.current.error).toBeInstanceOf(Error);
    expect(result.current.error?.message).toBe('Network error');
    expect(result.current.isPolling).toBe(false);
  });

  it('should cancel simulation', async () => {
    (arenaService.getSimulation as ReturnType<typeof vi.fn>)
      .mockResolvedValueOnce(mockDetail)
      .mockResolvedValueOnce({
        ...mockDetail,
        simulation: { ...mockDetail.simulation, status: 'cancelled' },
      });
    (arenaService.cancelSimulation as ReturnType<typeof vi.fn>).mockResolvedValue(undefined);

    const { result } = renderHook(() => useArenaPolling(1));

    await act(async () => {
      await vi.runOnlyPendingTimersAsync();
    });

    expect(result.current.detail).not.toBeNull();

    await act(async () => {
      await result.current.cancel();
    });

    expect(arenaService.cancelSimulation).toHaveBeenCalledWith(1);
    expect(result.current.isCancelling).toBe(false);
  });

  it('should handle cancel error', async () => {
    (arenaService.getSimulation as ReturnType<typeof vi.fn>).mockResolvedValue(mockDetail);
    (arenaService.cancelSimulation as ReturnType<typeof vi.fn>).mockRejectedValue(
      new Error('Cancel failed')
    );

    const { result } = renderHook(() => useArenaPolling(1));

    await act(async () => {
      await vi.runOnlyPendingTimersAsync();
    });

    await act(async () => {
      await result.current.cancel();
    });

    expect(result.current.error?.message).toBe('Cancel failed');
    expect(result.current.isCancelling).toBe(false);
  });

  it('should refetch on demand', async () => {
    (arenaService.getSimulation as ReturnType<typeof vi.fn>).mockResolvedValue(mockDetail);

    const { result } = renderHook(() => useArenaPolling(1));

    await act(async () => {
      await vi.runOnlyPendingTimersAsync();
    });

    const callsBefore = (arenaService.getSimulation as ReturnType<typeof vi.fn>).mock.calls.length;

    await act(async () => {
      await result.current.refetch();
    });

    expect((arenaService.getSimulation as ReturnType<typeof vi.fn>).mock.calls.length).toBeGreaterThan(callsBefore);
  });

  it('should reset state when simulationId changes to null', async () => {
    (arenaService.getSimulation as ReturnType<typeof vi.fn>).mockResolvedValue(mockDetail);

    const { result, rerender } = renderHook(({ id }) => useArenaPolling(id), {
      initialProps: { id: 1 as number | null },
    });

    await act(async () => {
      await vi.runOnlyPendingTimersAsync();
    });

    expect(result.current.detail).not.toBeNull();

    rerender({ id: null });

    expect(result.current.detail).toBeNull();
    expect(result.current.isPolling).toBe(false);
  });

  it('should restart polling when simulationId changes', async () => {
    const mockDetail2 = {
      ...mockDetail,
      simulation: { ...mockDetail.simulation, id: 2, name: 'Second Simulation' },
    };

    (arenaService.getSimulation as ReturnType<typeof vi.fn>).mockResolvedValue(mockDetail);

    const { result, rerender } = renderHook(({ id }) => useArenaPolling(id), {
      initialProps: { id: 1 },
    });

    await act(async () => {
      await vi.runOnlyPendingTimersAsync();
    });

    // Initially fetched with id 1
    expect(arenaService.getSimulation).toHaveBeenCalledWith(1);
    expect(result.current.detail).not.toBeNull();

    // Change mock for id 2
    (arenaService.getSimulation as ReturnType<typeof vi.fn>).mockResolvedValue(mockDetail2);
    rerender({ id: 2 });

    await act(async () => {
      await vi.runOnlyPendingTimersAsync();
    });

    expect(result.current.detail?.simulation.id).toBe(2);
    expect(arenaService.getSimulation).toHaveBeenLastCalledWith(2);
  });
});
