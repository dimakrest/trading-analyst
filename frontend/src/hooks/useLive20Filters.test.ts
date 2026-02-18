import { describe, it, expect, beforeEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useLive20Filters } from './useLive20Filters';
import type { Live20Result } from '../types/live20';

function makeResult(overrides: Partial<Live20Result> = {}): Live20Result {
  return {
    id: 1,
    stock: 'AAPL',
    created_at: '2024-01-01',
    recommendation: 'LONG',
    confidence_score: 75,
    atr: null,
    direction: 'LONG',
    rvol: null,
    trend_direction: null,
    trend_aligned: null,
    ma20_distance_pct: null,
    ma20_aligned: null,
    candle_pattern: null,
    candle_bullish: null,
    candle_aligned: null,
    candle_explanation: null,
    volume_aligned: null,
    volume_approach: null,
    cci_direction: null,
    cci_value: null,
    cci_zone: null,
    cci_aligned: null,
    criteria_aligned: null,
    sector_etf: null,
    scoring_algorithm: null,
    rsi2_value: null,
    rsi2_score: null,
    ...overrides,
  } as Live20Result;
}

describe('useLive20Filters', () => {
  const results = [
    makeResult({ id: 1, stock: 'AAPL', direction: 'LONG', confidence_score: 80, rvol: 1.5, atr: 2 }),
    makeResult({ id: 2, stock: 'TSLA', direction: 'SHORT', confidence_score: 60, rvol: 0.8, atr: 5 }),
    makeResult({ id: 3, stock: 'NVDA', direction: 'NO_SETUP', confidence_score: 40, rvol: null, atr: 8 }),
    makeResult({ id: 4, stock: 'META', direction: 'LONG', confidence_score: 90, rvol: 2.0, atr: null }),
  ];

  describe('Initial State', () => {
    it('passes all results through with no filters', () => {
      const { result } = renderHook(() => useLive20Filters(results));
      expect(result.current.filteredResults).toEqual(results);
    });

    it('isAtrFilterActive is false with default [0, 0]', () => {
      const { result } = renderHook(() => useLive20Filters(results));
      expect(result.current.isAtrFilterActive).toBe(false);
    });
  });

  describe('Direction Filter', () => {
    it('hides SHORT and NO_SETUP when set to LONG', () => {
      const { result } = renderHook(() => useLive20Filters(results));

      act(() => {
        result.current.setDirectionFilter('LONG');
      });

      const stocks = result.current.filteredResults.map((r) => r.stock);
      expect(stocks).toContain('AAPL');
      expect(stocks).toContain('META');
      expect(stocks).not.toContain('TSLA');
      expect(stocks).not.toContain('NVDA');
    });

    it('restores all results when set back to null', () => {
      const { result } = renderHook(() => useLive20Filters(results));

      act(() => {
        result.current.setDirectionFilter('LONG');
      });
      act(() => {
        result.current.setDirectionFilter(null);
      });

      expect(result.current.filteredResults).toEqual(results);
    });
  });

  describe('Search Query Filter', () => {
    it('filters by case-insensitive substring match on stock', () => {
      const { result } = renderHook(() => useLive20Filters(results));

      act(() => {
        result.current.setSearchQuery('ts');
      });

      const stocks = result.current.filteredResults.map((r) => r.stock);
      expect(stocks).toEqual(['TSLA']);
    });

    it('empty string shows all results', () => {
      const { result } = renderHook(() => useLive20Filters(results));

      act(() => {
        result.current.setSearchQuery('AAPL');
      });
      act(() => {
        result.current.setSearchQuery('');
      });

      expect(result.current.filteredResults).toEqual(results);
    });
  });

  describe('Min Score Filter', () => {
    it('hides stocks below minScore', () => {
      const { result } = renderHook(() => useLive20Filters(results));

      act(() => {
        result.current.setMinScore(70);
      });

      const stocks = result.current.filteredResults.map((r) => r.stock);
      expect(stocks).toContain('AAPL');  // 80
      expect(stocks).toContain('META');  // 90
      expect(stocks).not.toContain('TSLA');  // 60
      expect(stocks).not.toContain('NVDA');  // 40
    });

    it('minScore = 0 disables the filter', () => {
      const { result } = renderHook(() => useLive20Filters(results));

      act(() => {
        result.current.setMinScore(0);
      });

      expect(result.current.filteredResults).toEqual(results);
    });
  });

  describe('Min Rvol Filter', () => {
    it('hides stocks below minRvol', () => {
      const { result } = renderHook(() => useLive20Filters(results));

      act(() => {
        result.current.setMinRvol(1.0);
      });

      const stocks = result.current.filteredResults.map((r) => r.stock);
      expect(stocks).toContain('AAPL');  // 1.5
      expect(stocks).toContain('META');  // 2.0
      expect(stocks).not.toContain('TSLA');  // 0.8
      expect(stocks).not.toContain('NVDA');  // null → treated as 0
    });

    it('null rvol is treated as 0 and filtered out when minRvol > 0', () => {
      const { result } = renderHook(() => useLive20Filters(results));

      act(() => {
        result.current.setMinRvol(0.1);
      });

      const stocks = result.current.filteredResults.map((r) => r.stock);
      expect(stocks).not.toContain('NVDA');  // rvol is null
    });

    it('minRvol = 0 disables the filter', () => {
      const { result } = renderHook(() => useLive20Filters(results));

      act(() => {
        result.current.setMinRvol(0);
      });

      expect(result.current.filteredResults).toEqual(results);
    });
  });

  describe('ATR Range Filter', () => {
    it('[0, 0] — no filtering', () => {
      const { result } = renderHook(() => useLive20Filters(results));

      act(() => {
        result.current.setAtrRange([0, 0]);
      });

      expect(result.current.filteredResults).toEqual(results);
    });

    it('[3, 0] — min-only: hides stocks with atr < 3, null ATR passes', () => {
      const { result } = renderHook(() => useLive20Filters(results));

      act(() => {
        result.current.setAtrRange([3, 0]);
      });

      const stocks = result.current.filteredResults.map((r) => r.stock);
      expect(stocks).not.toContain('AAPL');  // atr=2 < 3
      expect(stocks).toContain('TSLA');       // atr=5 >= 3
      expect(stocks).toContain('NVDA');       // atr=8 >= 3
      expect(stocks).toContain('META');       // atr=null always passes
    });

    it('[0, 6] — max-only: hides stocks with atr > 6, null ATR passes', () => {
      const { result } = renderHook(() => useLive20Filters(results));

      act(() => {
        result.current.setAtrRange([0, 6]);
      });

      const stocks = result.current.filteredResults.map((r) => r.stock);
      expect(stocks).toContain('AAPL');       // atr=2 <= 6
      expect(stocks).toContain('TSLA');       // atr=5 <= 6
      expect(stocks).not.toContain('NVDA');  // atr=8 > 6
      expect(stocks).toContain('META');       // atr=null always passes
    });

    it('[3, 6] — both bounds: only stocks with 3 ≤ atr ≤ 6 (plus nulls)', () => {
      const { result } = renderHook(() => useLive20Filters(results));

      act(() => {
        result.current.setAtrRange([3, 6]);
      });

      const stocks = result.current.filteredResults.map((r) => r.stock);
      expect(stocks).not.toContain('AAPL');  // atr=2 < 3
      expect(stocks).toContain('TSLA');       // atr=5 in [3,6]
      expect(stocks).not.toContain('NVDA');  // atr=8 > 6
      expect(stocks).toContain('META');       // atr=null always passes
    });

    it('null ATR always passes regardless of filter state', () => {
      const { result } = renderHook(() => useLive20Filters(results));

      act(() => {
        result.current.setAtrRange([1, 3]);
      });

      const stocks = result.current.filteredResults.map((r) => r.stock);
      expect(stocks).toContain('META');  // atr=null
    });

    it('[6, 3] — crossed thumbs: empty set for non-null ATR values (documents current behavior)', () => {
      const { result } = renderHook(() => useLive20Filters(results));

      act(() => {
        result.current.setAtrRange([6, 3]);
      });

      const nonNullAtrResults = result.current.filteredResults.filter(
        (r) => r.atr !== null
      );
      // min=6 means atr>=6, max=3 means atr<=3 — no value satisfies both
      expect(nonNullAtrResults).toHaveLength(0);
      // null ATR still passes
      const stocks = result.current.filteredResults.map((r) => r.stock);
      expect(stocks).toContain('META');
    });
  });

  describe('isAtrFilterActive', () => {
    it('is false when [0, 0]', () => {
      const { result } = renderHook(() => useLive20Filters(results));
      expect(result.current.isAtrFilterActive).toBe(false);
    });

    it('is true when min > 0', () => {
      const { result } = renderHook(() => useLive20Filters(results));

      act(() => {
        result.current.setAtrRange([3, 0]);
      });

      expect(result.current.isAtrFilterActive).toBe(true);
    });

    it('is true when max > 0', () => {
      const { result } = renderHook(() => useLive20Filters(results));

      act(() => {
        result.current.setAtrRange([0, 6]);
      });

      expect(result.current.isAtrFilterActive).toBe(true);
    });

    it('is true when both > 0', () => {
      const { result } = renderHook(() => useLive20Filters(results));

      act(() => {
        result.current.setAtrRange([3, 6]);
      });

      expect(result.current.isAtrFilterActive).toBe(true);
    });
  });

  describe('Filter Composition', () => {
    it('direction + search + minScore all active simultaneously filters correctly', () => {
      const { result } = renderHook(() => useLive20Filters(results));

      act(() => {
        result.current.setDirectionFilter('LONG');
        result.current.setSearchQuery('a');
        result.current.setMinScore(85);
      });

      // LONG direction: AAPL (80), META (90)
      // search 'a': AAPL, META (both contain 'a' case-insensitive)
      // minScore 85: META (90) passes, AAPL (80) does not
      const stocks = result.current.filteredResults.map((r) => r.stock);
      expect(stocks).toEqual(['META']);
    });
  });
});
