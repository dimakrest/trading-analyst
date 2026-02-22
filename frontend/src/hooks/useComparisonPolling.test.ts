/**
 * Tests for useComparisonPolling hook.
 *
 * Verifies:
 * - continues polling when only some simulations are terminal
 * - stops polling when ALL simulations are terminal
 * - clears interval on unmount (no memory leak / stale updates after unmount)
 * - surfaces error state but keeps polling on network error
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useComparisonPolling } from './useComparisonPolling';
import * as arenaService from '../services/arenaService';
import type { ComparisonResponse } from '../types/arena';

vi.mock('../services/arenaService', () => ({
  getComparison: vi.fn(),
}));

const makeComparison = (statuses: string[]): ComparisonResponse => ({
  group_id: 'test-group',
  simulations: statuses.map((status, idx) => ({
    id: idx + 1,
    name: `Sim ${idx + 1}`,
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
    portfolio_strategy: `strategy_${idx}`,
    max_per_sector: null,
    max_open_positions: null,
    group_id: 'test-group',
    status: status as never,
    current_day: 10,
    total_days: 20,
    final_equity: status === 'completed' ? '10500' : null,
    total_return_pct: status === 'completed' ? '5.00' : null,
    total_trades: 0,
    winning_trades: 0,
    max_drawdown_pct: null,
    avg_hold_days: null,
    avg_win_pnl: null,
    avg_loss_pnl: null,
    profit_factor: null,
    sharpe_ratio: null,
    total_realized_pnl: null,
    created_at: '2024-01-01T10:00:00Z',
  })),
});

describe('useComparisonPolling', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.clearAllTimers();
    vi.useRealTimers();
  });

  it('continues polling when only some simulations are in a terminal state', async () => {
    // One running, one completed — should keep polling
    const mixedComparison = makeComparison(['running', 'completed']);
    (arenaService.getComparison as ReturnType<typeof vi.fn>).mockResolvedValue(mixedComparison);

    const { result } = renderHook(() => useComparisonPolling('test-group'));

    await act(async () => {
      await vi.runOnlyPendingTimersAsync();
    });

    expect(result.current.data).toEqual(mixedComparison);
    expect(result.current.isPolling).toBe(true);
  });

  it('stops polling when ALL simulations are in a terminal state', async () => {
    const allDone = makeComparison(['completed', 'completed']);
    (arenaService.getComparison as ReturnType<typeof vi.fn>).mockResolvedValue(allDone);

    const { result } = renderHook(() => useComparisonPolling('test-group'));

    await act(async () => {
      await vi.runOnlyPendingTimersAsync();
    });

    expect(result.current.data).toEqual(allDone);
    expect(result.current.isPolling).toBe(false);
  });

  it('stops polling when all simulations are failed or cancelled', async () => {
    const allFailed = makeComparison(['failed', 'cancelled']);
    (arenaService.getComparison as ReturnType<typeof vi.fn>).mockResolvedValue(allFailed);

    const { result } = renderHook(() => useComparisonPolling('test-group'));

    await act(async () => {
      await vi.runOnlyPendingTimersAsync();
    });

    expect(result.current.isPolling).toBe(false);
  });

  it('clears interval on unmount (no memory leak)', async () => {
    const mixedComparison = makeComparison(['running', 'running']);
    (arenaService.getComparison as ReturnType<typeof vi.fn>).mockResolvedValue(mixedComparison);

    const clearIntervalSpy = vi.spyOn(globalThis, 'clearInterval');

    const { unmount } = renderHook(() => useComparisonPolling('test-group'));

    await act(async () => {
      await vi.runOnlyPendingTimersAsync();
    });

    unmount();

    // clearInterval must have been called during cleanup
    expect(clearIntervalSpy).toHaveBeenCalled();
    clearIntervalSpy.mockRestore();
  });

  it('surfaces error state but keeps polling on network error', async () => {
    // All calls reject so the error stays visible and polling continues
    (arenaService.getComparison as ReturnType<typeof vi.fn>)
      .mockRejectedValue(new Error('Network error'));

    const { result } = renderHook(() => useComparisonPolling('test-group'));

    // Flush only the initial fetch (the first pending microtask/async op)
    await act(async () => {
      await vi.runOnlyPendingTimersAsync();
    });

    // Error should be surfaced
    expect(result.current.error).toBe('Failed to load comparison');
    // isPolling stays true — the interval is still running
    expect(result.current.isPolling).toBe(true);
  });

  it('does not update state after unmount (no stale state update)', async () => {
    let resolvePromise!: (v: ComparisonResponse) => void;
    (arenaService.getComparison as ReturnType<typeof vi.fn>).mockImplementation(
      () => new Promise<ComparisonResponse>((res) => { resolvePromise = res; }),
    );

    const { result, unmount } = renderHook(() => useComparisonPolling('test-group'));

    // Unmount before fetch resolves
    unmount();

    // Now resolve — should NOT update state
    await act(async () => {
      resolvePromise(makeComparison(['completed']));
      await vi.runAllTimersAsync();
    });

    // data should remain null since unmount happened before resolution
    expect(result.current.data).toBeNull();
  });

  it('resets state and restarts polling when groupId changes', async () => {
    const group2 = makeComparison(['completed', 'completed']);
    group2.group_id = 'group-2';
    group2.simulations.forEach((s) => { s.group_id = 'group-2'; });

    (arenaService.getComparison as ReturnType<typeof vi.fn>)
      .mockResolvedValue(group2);

    const { result, rerender } = renderHook(
      ({ id }) => useComparisonPolling(id),
      { initialProps: { id: 'group-1' } },
    );

    // Switch groupId to group-2 before the first fetch resolves
    rerender({ id: 'group-2' });

    await act(async () => {
      await vi.runOnlyPendingTimersAsync();
    });

    // After rerender to group-2, we should see group-2 data
    expect(result.current.data?.group_id).toBe('group-2');
    // All completed → polling should stop
    expect(result.current.isPolling).toBe(false);
  });
});
