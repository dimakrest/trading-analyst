import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act, waitFor } from '@testing-library/react';
import { useLive20 } from './useLive20';
import * as live20Service from '@/services/live20Service';
import { useLive20Polling } from './useLive20Polling';
import type { Live20RunDetail, Live20Result } from '@/types/live20';

// Mock the services and hooks
vi.mock('@/services/live20Service', () => ({
  analyzeSymbols: vi.fn(),
  cancelRun: vi.fn(),
  getResults: vi.fn(),
}));

vi.mock('./useLive20Polling', () => ({
  useLive20Polling: vi.fn(),
}));

const mockAnalyzeResponse = {
  run_id: 123,
  total: 10,
  status: 'pending',
  message: null,
};

// Minimal mock result for testing
const createMockResult = (id: number, stock: string, direction: 'LONG' | 'SHORT' | 'NO_SETUP'): Live20Result => ({
  id,
  stock,
  created_at: '2025-12-24T12:00:00Z',
  recommendation: direction,
  confidence_score: 75,
  sector_etf: 'XLK',
  trend_direction: 'UP',
  trend_aligned: true,
  ma20_distance_pct: -2,
  ma20_aligned: true,
  candle_pattern: 'hammer',
  candle_bullish: true,
  candle_aligned: true,
  candle_explanation: 'Test',
  volume_aligned: true,
  volume_approach: 'accumulation',
  rvol: 1.5,
  cci_direction: 'rising',
  cci_value: -100,
  cci_zone: 'oversold',
  cci_aligned: true,
  criteria_aligned: 5,
  direction,
  atr: 2.35,  // ATR is always calculated, regardless of direction
});

const mockResults = [
  createMockResult(1, 'AAPL', 'LONG'),
  createMockResult(2, 'MSFT', 'SHORT'),
  createMockResult(3, 'NVDA', 'LONG'),
];

const createMockRunDetail = (status: string, results: Live20Result[]): Live20RunDetail => ({
  id: 123,
  created_at: '2025-12-24T12:00:00Z',
  status,
  symbol_count: 10,
  processed_count: results.length,
  long_count: results.filter(r => r.direction === 'LONG').length,
  short_count: results.filter(r => r.direction === 'SHORT').length,
  no_setup_count: results.filter(r => r.direction === 'NO_SETUP').length,
  input_symbols: ['AAPL', 'MSFT', 'NVDA'],
  stock_list_id: null,
  stock_list_name: null,
  results,
});

describe('useLive20', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Default mock for useLive20Polling - returns null run
    vi.mocked(useLive20Polling).mockReturnValue({
      run: null,
      isPolling: false,
      error: null,
      reset: vi.fn(),
    });
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  describe('cancellation', () => {
    it('should call cancelRun when cancelAnalysis invoked', async () => {
      // Setup
      vi.mocked(live20Service.analyzeSymbols).mockResolvedValue(mockAnalyzeResponse);
      vi.mocked(live20Service.cancelRun).mockResolvedValue(undefined);
      vi.mocked(useLive20Polling).mockReturnValue({
        run: createMockRunDetail('running', mockResults),
        isPolling: true,
        error: null,
        reset: vi.fn(),
      });

      const { result } = renderHook(() => useLive20());

      // Start analysis
      await act(async () => {
        await result.current.analyzeSymbols(['AAPL', 'MSFT', 'NVDA']);
      });

      // Wait for analysis to be in progress
      await waitFor(() => {
        expect(result.current.isAnalyzing).toBe(true);
      });

      // Cancel analysis
      await act(async () => {
        await result.current.cancelAnalysis();
      });

      // Assert: cancelRun should be called with correct runId
      expect(live20Service.cancelRun).toHaveBeenCalledWith(123);
    });

    it('should not call cancelRun if no active run', async () => {
      // Setup - no active run
      vi.mocked(live20Service.cancelRun).mockResolvedValue(undefined);

      const { result } = renderHook(() => useLive20());

      // Try to cancel without starting analysis
      await act(async () => {
        await result.current.cancelAnalysis();
      });

      // Assert: cancelRun should not be called
      expect(live20Service.cancelRun).not.toHaveBeenCalled();
    });

    it('should handle cancel error gracefully', async () => {
      // Setup
      vi.mocked(live20Service.analyzeSymbols).mockResolvedValue(mockAnalyzeResponse);
      vi.mocked(live20Service.cancelRun).mockRejectedValue(new Error('Failed to cancel'));
      vi.mocked(useLive20Polling).mockReturnValue({
        run: createMockRunDetail('running', mockResults),
        isPolling: true,
        error: null,
        reset: vi.fn(),
      });

      const { result } = renderHook(() => useLive20());

      // Start analysis
      await act(async () => {
        await result.current.analyzeSymbols(['AAPL', 'MSFT', 'NVDA']);
      });

      // Wait for analysis to be in progress
      await waitFor(() => {
        expect(result.current.isAnalyzing).toBe(true);
      });

      // Try to cancel
      await act(async () => {
        await result.current.cancelAnalysis();
      });

      // Assert: Error should be set and isCancelling should be false
      expect(result.current.error).toBe('Failed to cancel');
      expect(result.current.isCancelling).toBe(false);
    });
  });

  describe('analyzeSymbols', () => {
    it('should handle analyze error', async () => {
      // Setup
      vi.mocked(live20Service.analyzeSymbols).mockRejectedValue(
        new Error('Failed to start analysis')
      );

      const { result } = renderHook(() => useLive20());

      // Try to analyze
      await act(async () => {
        await result.current.analyzeSymbols(['AAPL']);
      });

      // Assert: Error should be set
      expect(result.current.error).toBe('Failed to start analysis');
      expect(result.current.isAnalyzing).toBe(false);
    });
  });

  describe('progressive results', () => {
    it('should update results when run has results (even while running)', async () => {
      // Setup: Mock polling to return running state with results
      vi.mocked(useLive20Polling).mockReturnValue({
        run: createMockRunDetail('running', mockResults),
        isPolling: true,
        error: null,
        reset: vi.fn(),
      });

      // Render hook - results should be available immediately from the mocked polling
      const { result } = renderHook(() => useLive20());

      // Assert: Results should be available even during 'running' status
      // This is the key behavior - results update progressively
      expect(result.current.results.length).toBe(3);
      expect(result.current.counts.long).toBe(2);
      expect(result.current.counts.short).toBe(1);
    });

    it('should clear progress when run is cancelled', async () => {
      // Setup: Mock polling to return cancelled state with results
      vi.mocked(useLive20Polling).mockReturnValue({
        run: createMockRunDetail('cancelled', mockResults),
        isPolling: false,
        error: null,
        reset: vi.fn(),
      });

      // Render hook
      const { result } = renderHook(() => useLive20());

      // Assert: Results preserved, progress cleared, not analyzing
      expect(result.current.results.length).toBe(3);
      expect(result.current.progress).toBeNull();
      expect(result.current.isAnalyzing).toBe(false);
    });
  });

  describe('failed symbols tracking', () => {
    it('should track failed symbols from run detail', async () => {
      const runWithFailedSymbols = {
        ...createMockRunDetail('running', mockResults),
        failed_symbols: {
          'INVALID': 'Symbol not found',
          'ERROR': 'Data fetch failed',
        },
      };

      vi.mocked(useLive20Polling).mockReturnValue({
        run: runWithFailedSymbols,
        isPolling: true,
        error: null,
        reset: vi.fn(),
      });

      const { result } = renderHook(() => useLive20());

      expect(result.current.failedSymbols).toEqual({
        'INVALID': 'Symbol not found',
        'ERROR': 'Data fetch failed',
      });
    });

    it('should reset failed symbols on new analysis', async () => {
      // Start with failed symbols
      const runWithFailedSymbols = {
        ...createMockRunDetail('completed', mockResults),
        failed_symbols: {
          'INVALID': 'Symbol not found',
        },
      };

      vi.mocked(useLive20Polling).mockReturnValue({
        run: runWithFailedSymbols,
        isPolling: false,
        error: null,
        reset: vi.fn(),
      });

      const { result } = renderHook(() => useLive20());

      expect(result.current.failedSymbols).toEqual({ 'INVALID': 'Symbol not found' });

      // Start new analysis
      vi.mocked(live20Service.analyzeSymbols).mockResolvedValue(mockAnalyzeResponse);

      await act(async () => {
        await result.current.analyzeSymbols(['AAPL']);
      });

      // Failed symbols should be cleared
      expect(result.current.failedSymbols).toEqual({});
    });

    it('should start with empty failed symbols', () => {
      vi.mocked(useLive20Polling).mockReturnValue({
        run: null,
        isPolling: false,
        error: null,
        reset: vi.fn(),
      });

      const { result } = renderHook(() => useLive20());

      expect(result.current.failedSymbols).toEqual({});
    });
  });
});
