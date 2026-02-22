import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, waitFor, act } from '@testing-library/react';
import { useActiveArenaSimulation } from './useActiveArenaSimulation';
import * as arenaService from '../services/arenaService';
import type { Simulation } from '../types/arena';

// Mock the arena service
vi.mock('../services/arenaService', () => ({
  listSimulations: vi.fn(),
}));

const mockCompletedSimulation: Simulation = {
  id: 1,
  name: 'Completed Simulation',
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
  scoring_algorithm: null,
  portfolio_strategy: null,
  max_per_sector: null,
  max_open_positions: null,
  status: 'completed',
  current_day: 22,
  total_days: 22,
  final_equity: '10500',
  total_return_pct: '5.00',
  total_trades: 5,
  winning_trades: 3,
  max_drawdown_pct: '2.50',
  avg_hold_days: null,
  avg_win_pnl: null,
  avg_loss_pnl: null,
  profit_factor: null,
  sharpe_ratio: null,
  total_realized_pnl: null,
  created_at: '2024-01-01T10:00:00Z',
};

const mockRunningSimulation: Simulation = {
  id: 2,
  name: 'Running Simulation',
  stock_list_id: null,
  stock_list_name: null,
  symbols: ['NVDA'],
  start_date: '2024-02-01',
  end_date: '2024-02-29',
  initial_capital: '10000',
  position_size: '1000',
  agent_type: 'live20',
  trailing_stop_pct: '5.0',
  min_buy_score: 60,
  scoring_algorithm: null,
  portfolio_strategy: null,
  max_per_sector: null,
  max_open_positions: null,
  status: 'running',
  current_day: 10,
  total_days: 20,
  final_equity: null,
  total_return_pct: null,
  total_trades: 2,
  winning_trades: 1,
  max_drawdown_pct: null,
  avg_hold_days: null,
  avg_win_pnl: null,
  avg_loss_pnl: null,
  profit_factor: null,
  sharpe_ratio: null,
  total_realized_pnl: null,
  created_at: '2024-02-01T10:00:00Z',
};

const mockPendingSimulation: Simulation = {
  id: 3,
  name: 'Pending Simulation',
  stock_list_id: null,
  stock_list_name: null,
  symbols: ['AMD'],
  start_date: '2024-03-01',
  end_date: '2024-03-15',
  initial_capital: '10000',
  position_size: '1000',
  agent_type: 'live20',
  trailing_stop_pct: '5.0',
  min_buy_score: 60,
  scoring_algorithm: null,
  portfolio_strategy: null,
  max_per_sector: null,
  max_open_positions: null,
  status: 'pending',
  current_day: 0,
  total_days: 10,
  final_equity: null,
  total_return_pct: null,
  total_trades: 0,
  winning_trades: 0,
  max_drawdown_pct: null,
  avg_hold_days: null,
  avg_win_pnl: null,
  avg_loss_pnl: null,
  profit_factor: null,
  sharpe_ratio: null,
  total_realized_pnl: null,
  created_at: '2024-03-01T10:00:00Z',
};

describe('useActiveArenaSimulation', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('should start in loading state', () => {
    (arenaService.listSimulations as ReturnType<typeof vi.fn>).mockReturnValue(
      new Promise(() => {}) // Never resolves
    );

    const { result } = renderHook(() => useActiveArenaSimulation());

    expect(result.current.isLoading).toBe(true);
    expect(result.current.activeSimulation).toBeNull();
    expect(result.current.error).toBeNull();
  });

  it('should return null when no active simulations', async () => {
    (arenaService.listSimulations as ReturnType<typeof vi.fn>).mockResolvedValue({
      items: [mockCompletedSimulation],
      total: 1,
      limit: 20,
      offset: 0,
    });

    const { result } = renderHook(() => useActiveArenaSimulation());

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.activeSimulation).toBeNull();
    expect(result.current.error).toBeNull();
  });

  it('should return running simulation', async () => {
    (arenaService.listSimulations as ReturnType<typeof vi.fn>).mockResolvedValue({
      items: [mockCompletedSimulation, mockRunningSimulation],
      total: 2,
      limit: 20,
      offset: 0,
    });

    const { result } = renderHook(() => useActiveArenaSimulation());

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.activeSimulation).toEqual(mockRunningSimulation);
  });

  it('should return pending simulation', async () => {
    (arenaService.listSimulations as ReturnType<typeof vi.fn>).mockResolvedValue({
      items: [mockCompletedSimulation, mockPendingSimulation],
      total: 2,
      limit: 20,
      offset: 0,
    });

    const { result } = renderHook(() => useActiveArenaSimulation());

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.activeSimulation).toEqual(mockPendingSimulation);
  });

  it('should return first active simulation when multiple active', async () => {
    (arenaService.listSimulations as ReturnType<typeof vi.fn>).mockResolvedValue({
      items: [mockPendingSimulation, mockRunningSimulation],
      total: 2,
      limit: 20,
      offset: 0,
    });

    const { result } = renderHook(() => useActiveArenaSimulation());

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    // Should return first one (pending)
    expect(result.current.activeSimulation).toEqual(mockPendingSimulation);
  });

  it('should handle fetch error', async () => {
    (arenaService.listSimulations as ReturnType<typeof vi.fn>).mockRejectedValue(
      new Error('Network error')
    );

    const { result } = renderHook(() => useActiveArenaSimulation());

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.error).toBeInstanceOf(Error);
    expect(result.current.error?.message).toBe('Network error');
    expect(result.current.activeSimulation).toBeNull();
  });

  it('should clear active simulation', async () => {
    (arenaService.listSimulations as ReturnType<typeof vi.fn>).mockResolvedValue({
      items: [mockRunningSimulation],
      total: 1,
      limit: 20,
      offset: 0,
    });

    const { result } = renderHook(() => useActiveArenaSimulation());

    await waitFor(() => {
      expect(result.current.activeSimulation).toEqual(mockRunningSimulation);
    });

    act(() => {
      result.current.clearActiveSimulation();
    });

    expect(result.current.activeSimulation).toBeNull();
  });

  it('should only fetch once on mount', async () => {
    (arenaService.listSimulations as ReturnType<typeof vi.fn>).mockResolvedValue({
      items: [],
      total: 0,
      limit: 20,
      offset: 0,
    });

    const { rerender } = renderHook(() => useActiveArenaSimulation());

    await waitFor(() => {
      expect(arenaService.listSimulations).toHaveBeenCalledTimes(1);
    });

    // Re-render should not trigger another fetch
    rerender();
    rerender();

    expect(arenaService.listSimulations).toHaveBeenCalledTimes(1);
  });

  it('should return null for empty simulation list', async () => {
    (arenaService.listSimulations as ReturnType<typeof vi.fn>).mockResolvedValue({
      items: [],
      total: 0,
      limit: 20,
      offset: 0,
    });

    const { result } = renderHook(() => useActiveArenaSimulation());

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.activeSimulation).toBeNull();
    expect(result.current.error).toBeNull();
  });

  it('should not return cancelled simulations as active', async () => {
    const cancelledSimulation = {
      ...mockRunningSimulation,
      status: 'cancelled' as const,
    };

    (arenaService.listSimulations as ReturnType<typeof vi.fn>).mockResolvedValue({
      items: [cancelledSimulation],
      total: 1,
      limit: 20,
      offset: 0,
    });

    const { result } = renderHook(() => useActiveArenaSimulation());

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.activeSimulation).toBeNull();
  });

  it('should not return failed simulations as active', async () => {
    const failedSimulation = {
      ...mockRunningSimulation,
      status: 'failed' as const,
    };

    (arenaService.listSimulations as ReturnType<typeof vi.fn>).mockResolvedValue({
      items: [failedSimulation],
      total: 1,
      limit: 20,
      offset: 0,
    });

    const { result } = renderHook(() => useActiveArenaSimulation());

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.activeSimulation).toBeNull();
  });
});
