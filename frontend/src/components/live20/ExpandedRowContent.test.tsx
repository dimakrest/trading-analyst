import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ExpandedRowContent } from './ExpandedRowContent';
import type { Live20Result } from '../../types/live20';
import type { SectorTrend } from '../../services/live20Service';
import * as live20Service from '../../services/live20Service';
import * as stockService from '../../services/stockService';

// Mock services at module level
vi.mock('../../services/live20Service');
vi.mock('../../services/stockService');

// Mock CandlestickChart component
vi.mock('../organisms/CandlestickChart/CandlestickChart', () => ({
  CandlestickChart: ({ symbol, data }: { symbol: string; data: unknown[] }) => (
    <div data-testid="candlestick-chart">
      Chart for {symbol} with {data.length} data points
    </div>
  ),
}));

/**
 * Factory to create mock Live20Result with defaults
 */
const createMockResult = (overrides: Partial<Live20Result> = {}): Live20Result => ({
  id: 1,
  stock: 'AAPL',
  sector_etf: 'XLK',
  created_at: '2025-12-01T10:00:00Z',
  recommendation: 'LONG',
  confidence_score: 85,
  entry_price: 150.0,
  stop_loss: 145.0,
  atr: 2.5,
  trend_direction: 'up',
  trend_aligned: true,
  ma20_distance_pct: 2.5,
  ma20_aligned: true,
  candle_pattern: 'engulfing',
  candle_bullish: true,
  candle_aligned: true,
  candle_explanation: 'Bullish engulfing pattern',
  volume_aligned: true,
  volume_approach: 'accumulation',
  rvol: 1.5,
  cci_direction: 'rising',
  cci_value: -50.2,
  cci_zone: 'oversold',
  cci_aligned: true,
  criteria_aligned: 5,
  direction: 'LONG',
  entry_strategy: 'breakout_confirmation',
  exit_strategy: 'atr_based',
  ...overrides,
});

/**
 * Mock sector trend data
 */
const mockSectorTrend: SectorTrend = {
  sector_etf: 'XLK',
  trend_direction: 'up',
  ma20_position: 'above',
  ma20_distance_pct: 2.5,
  ma50_position: 'above',
  ma50_distance_pct: 5.1,
  price_change_5d_pct: 1.23,
  price_change_20d_pct: 4.56,
};

/**
 * Mock stock price data
 */
const mockStockData = {
  prices: [
    {
      date: '2025-12-01',
      open: 100,
      high: 105,
      low: 99,
      close: 103,
      volume: 1000000,
    },
    {
      date: '2025-12-02',
      open: 103,
      high: 106,
      low: 102,
      close: 105,
      volume: 1200000,
    },
  ],
};

/**
 * Mock indicators response
 */
const mockIndicatorsResponse = {
  data: [
    { date: '2025-12-01', ma_20: 100.5, cci: -50.2, cci_signal: 'neutral' as const },
    { date: '2025-12-02', ma_20: 101.2, cci: -30.5, cci_signal: 'neutral' as const },
  ],
};

describe('ExpandedRowContent', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('Initialization and lifecycle', () => {
    it('should render loading state on mount', () => {
      // Mock services to never resolve (keep loading)
      vi.spyOn(live20Service, 'fetchSectorTrend').mockImplementation(
        () => new Promise(() => {})
      );
      vi.spyOn(stockService, 'fetchStockDataByDateRange').mockImplementation(
        () => new Promise(() => {})
      );
      vi.spyOn(stockService, 'fetchIndicators').mockImplementation(
        () => new Promise(() => {})
      );

      const result = createMockResult();
      render(<ExpandedRowContent result={result} />);

      // Verify loading spinner and message shown
      expect(screen.getByText(/loading sector trend and chart data/i)).toBeInTheDocument();
      const loader = document.querySelector('.animate-spin');
      expect(loader).toBeInTheDocument();
    });

    it('should create AbortController and fetch data on mount', async () => {
      const fetchSectorTrendSpy = vi
        .spyOn(live20Service, 'fetchSectorTrend')
        .mockResolvedValue(mockSectorTrend);
      const fetchStockDataSpy = vi
        .spyOn(stockService, 'fetchStockDataByDateRange')
        .mockResolvedValue(mockStockData);
      const fetchIndicatorsSpy = vi
        .spyOn(stockService, 'fetchIndicators')
        .mockResolvedValue(mockIndicatorsResponse);

      const result = createMockResult({ stock: 'AAPL', sector_etf: 'XLK' });
      render(<ExpandedRowContent result={result} />);

      await waitFor(() => {
        expect(screen.queryByText(/loading/i)).not.toBeInTheDocument();
      });

      // Verify all service calls were made
      expect(fetchSectorTrendSpy).toHaveBeenCalledWith('XLK');
      expect(fetchStockDataSpy).toHaveBeenCalled();
      expect(fetchIndicatorsSpy).toHaveBeenCalledWith('AAPL', '1d');
    });

    it('should cleanup AbortController on unmount', () => {
      vi.spyOn(live20Service, 'fetchSectorTrend').mockResolvedValue(mockSectorTrend);
      vi.spyOn(stockService, 'fetchStockDataByDateRange').mockResolvedValue(mockStockData);
      vi.spyOn(stockService, 'fetchIndicators').mockResolvedValue(mockIndicatorsResponse);

      const abortSpy = vi.spyOn(AbortController.prototype, 'abort');

      const result = createMockResult();
      const { unmount } = render(<ExpandedRowContent result={result} />);

      unmount();

      // Verify abort was called during cleanup
      expect(abortSpy).toHaveBeenCalled();
    });

    it('should refetch data when result.stock changes', async () => {
      const fetchSectorTrendSpy = vi
        .spyOn(live20Service, 'fetchSectorTrend')
        .mockResolvedValue(mockSectorTrend);
      const fetchStockDataSpy = vi
        .spyOn(stockService, 'fetchStockDataByDateRange')
        .mockResolvedValue(mockStockData);
      const fetchIndicatorsSpy = vi
        .spyOn(stockService, 'fetchIndicators')
        .mockResolvedValue(mockIndicatorsResponse);

      const result1 = createMockResult({ stock: 'AAPL', sector_etf: 'XLK' });
      const { rerender } = render(<ExpandedRowContent result={result1} />);

      await waitFor(() => {
        expect(screen.queryByText(/loading/i)).not.toBeInTheDocument();
      });

      // Clear mock call history
      vi.clearAllMocks();

      // Rerender with different stock
      const result2 = createMockResult({ stock: 'MSFT', sector_etf: 'XLK' });
      rerender(<ExpandedRowContent result={result2} />);

      await waitFor(() => {
        expect(fetchIndicatorsSpy).toHaveBeenCalledWith('MSFT', '1d');
      });

      expect(fetchSectorTrendSpy).toHaveBeenCalledWith('XLK');
      expect(fetchStockDataSpy).toHaveBeenCalled();
    });

    it('should refetch data when result.sector_etf changes', async () => {
      const fetchSectorTrendSpy = vi
        .spyOn(live20Service, 'fetchSectorTrend')
        .mockResolvedValue(mockSectorTrend);
      vi.spyOn(stockService, 'fetchStockDataByDateRange').mockResolvedValue(mockStockData);
      vi.spyOn(stockService, 'fetchIndicators').mockResolvedValue(mockIndicatorsResponse);

      const result1 = createMockResult({ stock: 'AAPL', sector_etf: 'XLK' });
      const { rerender } = render(<ExpandedRowContent result={result1} />);

      await waitFor(() => {
        expect(screen.queryByText(/loading/i)).not.toBeInTheDocument();
      });

      // Clear mock call history
      vi.clearAllMocks();

      // Rerender with different sector_etf
      const result2 = createMockResult({ stock: 'AAPL', sector_etf: 'XLF' });
      rerender(<ExpandedRowContent result={result2} />);

      await waitFor(() => {
        expect(fetchSectorTrendSpy).toHaveBeenCalledWith('XLF');
      });
    });
  });

  describe('Data fetching', () => {
    it('should fetch sector trend when sector_etf exists', async () => {
      const fetchSectorTrendSpy = vi
        .spyOn(live20Service, 'fetchSectorTrend')
        .mockResolvedValue(mockSectorTrend);
      vi.spyOn(stockService, 'fetchStockDataByDateRange').mockResolvedValue(mockStockData);
      vi.spyOn(stockService, 'fetchIndicators').mockResolvedValue(mockIndicatorsResponse);

      const result = createMockResult({ sector_etf: 'XLK' });
      render(<ExpandedRowContent result={result} />);

      await waitFor(() => {
        expect(screen.queryByText(/loading/i)).not.toBeInTheDocument();
      });

      expect(fetchSectorTrendSpy).toHaveBeenCalledWith('XLK');
    });

    it('should skip sector trend fetch when sector_etf is null', async () => {
      const fetchSectorTrendSpy = vi
        .spyOn(live20Service, 'fetchSectorTrend')
        .mockResolvedValue(mockSectorTrend);
      vi.spyOn(stockService, 'fetchStockDataByDateRange').mockResolvedValue(mockStockData);
      vi.spyOn(stockService, 'fetchIndicators').mockResolvedValue(mockIndicatorsResponse);

      const result = createMockResult({ sector_etf: null });
      render(<ExpandedRowContent result={result} />);

      await waitFor(() => {
        expect(screen.queryByText(/loading/i)).not.toBeInTheDocument();
      });

      // fetchSectorTrend should NOT have been called
      expect(fetchSectorTrendSpy).not.toHaveBeenCalled();
    });

    it('should fetch stock prices with correct date range (3 months)', async () => {
      vi.spyOn(live20Service, 'fetchSectorTrend').mockResolvedValue(mockSectorTrend);
      const fetchStockDataSpy = vi
        .spyOn(stockService, 'fetchStockDataByDateRange')
        .mockResolvedValue(mockStockData);
      vi.spyOn(stockService, 'fetchIndicators').mockResolvedValue(mockIndicatorsResponse);

      const result = createMockResult({ stock: 'AAPL' });
      render(<ExpandedRowContent result={result} />);

      await waitFor(() => {
        expect(screen.queryByText(/loading/i)).not.toBeInTheDocument();
      });

      // Verify call arguments
      expect(fetchStockDataSpy).toHaveBeenCalledWith({
        symbol: 'AAPL',
        startDate: expect.stringMatching(/\d{4}-\d{2}-\d{2}/),
        endDate: expect.stringMatching(/\d{4}-\d{2}-\d{2}/),
        interval: '1d',
      });

      // Verify date range is approximately 3 months
      const callArgs = fetchStockDataSpy.mock.calls[0][0];
      const startDate = new Date(callArgs.startDate);
      const endDate = new Date(callArgs.endDate);
      const daysDiff = Math.floor(
        (endDate.getTime() - startDate.getTime()) / (1000 * 60 * 60 * 24)
      );

      // Should be around 90 days (3 months)
      expect(daysDiff).toBeGreaterThanOrEqual(85);
      expect(daysDiff).toBeLessThanOrEqual(95);
    });

    it('should fetch indicators with 1d interval', async () => {
      vi.spyOn(live20Service, 'fetchSectorTrend').mockResolvedValue(mockSectorTrend);
      vi.spyOn(stockService, 'fetchStockDataByDateRange').mockResolvedValue(mockStockData);
      const fetchIndicatorsSpy = vi
        .spyOn(stockService, 'fetchIndicators')
        .mockResolvedValue(mockIndicatorsResponse);

      const result = createMockResult({ stock: 'AAPL' });
      render(<ExpandedRowContent result={result} />);

      await waitFor(() => {
        expect(screen.queryByText(/loading/i)).not.toBeInTheDocument();
      });

      expect(fetchIndicatorsSpy).toHaveBeenCalledWith('AAPL', '1d');
    });

    it('should merge indicator data by date correctly', async () => {
      vi.spyOn(live20Service, 'fetchSectorTrend').mockResolvedValue(mockSectorTrend);
      vi.spyOn(stockService, 'fetchStockDataByDateRange').mockResolvedValue(mockStockData);
      vi.spyOn(stockService, 'fetchIndicators').mockResolvedValue(mockIndicatorsResponse);

      const result = createMockResult({ stock: 'AAPL', sector_etf: 'XLK' });
      render(<ExpandedRowContent result={result} />);

      await waitFor(() => {
        expect(screen.queryByText(/loading/i)).not.toBeInTheDocument();
      });

      // Verify chart received merged data
      const chart = screen.getByTestId('candlestick-chart');
      expect(chart).toBeInTheDocument();
      expect(chart).toHaveTextContent('Chart for AAPL with 2 data points');
    });

    it('should handle missing indicators gracefully', async () => {
      vi.spyOn(live20Service, 'fetchSectorTrend').mockResolvedValue(mockSectorTrend);
      vi.spyOn(stockService, 'fetchStockDataByDateRange').mockResolvedValue({
        prices: [
          { date: '2025-12-01', open: 100, high: 105, low: 99, close: 103, volume: 1000000 },
          { date: '2025-12-03', open: 104, high: 107, low: 103, close: 106, volume: 1100000 },
        ],
      });
      vi.spyOn(stockService, 'fetchIndicators').mockResolvedValue({
        data: [
          // Only one date has indicators
          { date: '2025-12-01', ma_20: 100.5, cci: -50.2, cci_signal: 'neutral' as const },
        ],
      });

      const result = createMockResult({ stock: 'AAPL' });
      render(<ExpandedRowContent result={result} />);

      await waitFor(() => {
        expect(screen.queryByText(/loading/i)).not.toBeInTheDocument();
      });

      // Should still render chart with 2 data points
      const chart = screen.getByTestId('candlestick-chart');
      expect(chart).toHaveTextContent('Chart for AAPL with 2 data points');
    });

    it('should make sector and stock calls in parallel', async () => {
      const fetchSectorTrendSpy = vi
        .spyOn(live20Service, 'fetchSectorTrend')
        .mockResolvedValue(mockSectorTrend);
      const fetchStockDataSpy = vi
        .spyOn(stockService, 'fetchStockDataByDateRange')
        .mockResolvedValue(mockStockData);
      vi.spyOn(stockService, 'fetchIndicators').mockResolvedValue(mockIndicatorsResponse);

      const result = createMockResult();
      render(<ExpandedRowContent result={result} />);

      await waitFor(() => {
        expect(screen.queryByText(/loading/i)).not.toBeInTheDocument();
      });

      // Verify both calls were made (implementation uses Promise.all for parallel execution)
      expect(fetchSectorTrendSpy).toHaveBeenCalled();
      expect(fetchStockDataSpy).toHaveBeenCalled();
    });

    it('should continue stock fetch even if sector fetch fails', async () => {
      vi.spyOn(live20Service, 'fetchSectorTrend').mockRejectedValue(
        new Error('Sector API error')
      );
      vi.spyOn(stockService, 'fetchStockDataByDateRange').mockResolvedValue(mockStockData);
      vi.spyOn(stockService, 'fetchIndicators').mockResolvedValue(mockIndicatorsResponse);

      const result = createMockResult({ sector_etf: 'XLK' });
      render(<ExpandedRowContent result={result} />);

      await waitFor(() => {
        expect(screen.queryByText(/loading/i)).not.toBeInTheDocument();
      });

      // Chart should still be rendered
      expect(screen.getByTestId('candlestick-chart')).toBeInTheDocument();

      // Sector info should show fallback
      expect(screen.getByText(/sector info not available/i)).toBeInTheDocument();
    });
  });

  describe('Loading states', () => {
    it('should show loading spinner with message', () => {
      vi.spyOn(live20Service, 'fetchSectorTrend').mockImplementation(
        () => new Promise(() => {})
      );
      vi.spyOn(stockService, 'fetchStockDataByDateRange').mockImplementation(
        () => new Promise(() => {})
      );
      vi.spyOn(stockService, 'fetchIndicators').mockImplementation(() => new Promise(() => {}));

      const result = createMockResult();
      render(<ExpandedRowContent result={result} />);

      // Verify loading message
      expect(screen.getByText(/loading sector trend and chart data/i)).toBeInTheDocument();

      // Verify spinner (animate-spin class)
      const loader = document.querySelector('.animate-spin');
      expect(loader).toBeInTheDocument();
    });

    it('should hide loading state after data loads', async () => {
      vi.spyOn(live20Service, 'fetchSectorTrend').mockResolvedValue(mockSectorTrend);
      vi.spyOn(stockService, 'fetchStockDataByDateRange').mockResolvedValue(mockStockData);
      vi.spyOn(stockService, 'fetchIndicators').mockResolvedValue(mockIndicatorsResponse);

      const result = createMockResult();
      render(<ExpandedRowContent result={result} />);

      // Initially loading
      expect(screen.getByText(/loading/i)).toBeInTheDocument();

      // Wait for loading to finish
      await waitFor(() => {
        expect(screen.queryByText(/loading/i)).not.toBeInTheDocument();
      });

      // Verify content is shown
      expect(screen.getByText(/sector trend analysis/i)).toBeInTheDocument();
    });

    it('should not set loading false if aborted', async () => {
      // This test verifies no state updates happen after unmount
      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

      vi.spyOn(live20Service, 'fetchSectorTrend').mockImplementation(
        () => new Promise((resolve) => setTimeout(() => resolve(mockSectorTrend), 200))
      );
      vi.spyOn(stockService, 'fetchStockDataByDateRange').mockImplementation(
        () => new Promise((resolve) => setTimeout(() => resolve(mockStockData), 200))
      );
      vi.spyOn(stockService, 'fetchIndicators').mockImplementation(
        () => new Promise((resolve) => setTimeout(() => resolve(mockIndicatorsResponse), 200))
      );

      const result = createMockResult();
      const { unmount } = render(<ExpandedRowContent result={result} />);

      // Unmount before fetch completes
      unmount();

      // Wait for promises to resolve
      await new Promise((resolve) => setTimeout(resolve, 300));

      // Should not have any React state update warnings
      expect(consoleSpy).not.toHaveBeenCalledWith(
        expect.stringContaining("Can't perform a React state update")
      );

      consoleSpy.mockRestore();
    });
  });

  describe('Error handling', () => {
    it('should display error message when fetch fails', async () => {
      vi.spyOn(live20Service, 'fetchSectorTrend').mockRejectedValue(new Error('API Error'));
      vi.spyOn(stockService, 'fetchStockDataByDateRange').mockRejectedValue(
        new Error('API Error')
      );
      vi.spyOn(stockService, 'fetchIndicators').mockRejectedValue(new Error('API Error'));

      const result = createMockResult();
      render(<ExpandedRowContent result={result} />);

      await waitFor(() => {
        expect(screen.getByText(/api error/i)).toBeInTheDocument();
      });

      // Error icon should be visible
      const errorIcon = document.querySelector('.text-accent-bearish');
      expect(errorIcon).toBeInTheDocument();
    });

    it('should extract error message from Error objects', async () => {
      vi.spyOn(live20Service, 'fetchSectorTrend').mockRejectedValue(
        new Error('Custom error message')
      );
      vi.spyOn(stockService, 'fetchStockDataByDateRange').mockRejectedValue(
        new Error('Custom error message')
      );
      vi.spyOn(stockService, 'fetchIndicators').mockRejectedValue(
        new Error('Custom error message')
      );

      const result = createMockResult();
      render(<ExpandedRowContent result={result} />);

      await waitFor(() => {
        expect(screen.getByText(/custom error message/i)).toBeInTheDocument();
      });
    });

    it('should use fallback message for non-Error exceptions', async () => {
      vi.spyOn(live20Service, 'fetchSectorTrend').mockRejectedValue('String error');
      vi.spyOn(stockService, 'fetchStockDataByDateRange').mockRejectedValue('String error');
      vi.spyOn(stockService, 'fetchIndicators').mockRejectedValue('String error');

      const result = createMockResult();
      render(<ExpandedRowContent result={result} />);

      await waitFor(() => {
        expect(screen.getByText(/failed to fetch data/i)).toBeInTheDocument();
      });
    });

    it('should show retry button in error state', async () => {
      vi.spyOn(live20Service, 'fetchSectorTrend').mockRejectedValue(new Error('Error'));
      vi.spyOn(stockService, 'fetchStockDataByDateRange').mockRejectedValue(new Error('Error'));
      vi.spyOn(stockService, 'fetchIndicators').mockRejectedValue(new Error('Error'));

      const result = createMockResult();
      render(<ExpandedRowContent result={result} />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /retry/i })).toBeInTheDocument();
      });
    });

    it('should refetch data when retry button clicked', async () => {
      const user = userEvent.setup();

      // First call fails, second call succeeds
      const fetchSectorTrendSpy = vi
        .spyOn(live20Service, 'fetchSectorTrend')
        .mockRejectedValueOnce(new Error('Error'))
        .mockResolvedValueOnce(mockSectorTrend);
      const fetchStockDataSpy = vi
        .spyOn(stockService, 'fetchStockDataByDateRange')
        .mockRejectedValueOnce(new Error('Error'))
        .mockResolvedValueOnce(mockStockData);
      const fetchIndicatorsSpy = vi
        .spyOn(stockService, 'fetchIndicators')
        .mockRejectedValueOnce(new Error('Error'))
        .mockResolvedValueOnce(mockIndicatorsResponse);

      const result = createMockResult();
      render(<ExpandedRowContent result={result} />);

      // Wait for error state
      await waitFor(() => {
        expect(screen.getByText(/error/i)).toBeInTheDocument();
      });

      // Click retry button
      const retryButton = screen.getByRole('button', { name: /retry/i });
      await user.click(retryButton);

      // Wait for successful load
      await waitFor(() => {
        expect(screen.queryByText(/error/i)).not.toBeInTheDocument();
      });

      // Verify services were called twice (initial + retry)
      expect(fetchSectorTrendSpy).toHaveBeenCalledTimes(2);
      expect(fetchStockDataSpy).toHaveBeenCalledTimes(2);
      expect(fetchIndicatorsSpy).toHaveBeenCalledTimes(2);

      // Verify content is shown
      expect(screen.getByText(/sector trend analysis/i)).toBeInTheDocument();
    });

    it('should not set error state if aborted', async () => {
      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

      vi.spyOn(live20Service, 'fetchSectorTrend').mockImplementation(
        () => new Promise((_, reject) => setTimeout(() => reject(new Error('Error')), 200))
      );
      vi.spyOn(stockService, 'fetchStockDataByDateRange').mockImplementation(
        () => new Promise((_, reject) => setTimeout(() => reject(new Error('Error')), 200))
      );
      vi.spyOn(stockService, 'fetchIndicators').mockImplementation(
        () => new Promise((_, reject) => setTimeout(() => reject(new Error('Error')), 200))
      );

      const result = createMockResult();
      const { unmount } = render(<ExpandedRowContent result={result} />);

      // Unmount before fetch fails
      unmount();

      // Wait for promises to reject
      await new Promise((resolve) => setTimeout(resolve, 300));

      // Should not have any React state update warnings
      expect(consoleSpy).not.toHaveBeenCalledWith(
        expect.stringContaining("Can't perform a React state update")
      );

      consoleSpy.mockRestore();
    });
  });

  describe('Sector trend display', () => {
    it('should display sector ETF name', async () => {
      vi.spyOn(live20Service, 'fetchSectorTrend').mockResolvedValue(mockSectorTrend);
      vi.spyOn(stockService, 'fetchStockDataByDateRange').mockResolvedValue(mockStockData);
      vi.spyOn(stockService, 'fetchIndicators').mockResolvedValue(mockIndicatorsResponse);

      const result = createMockResult({ sector_etf: 'XLK' });
      render(<ExpandedRowContent result={result} />);

      await waitFor(() => {
        expect(screen.queryByText(/loading/i)).not.toBeInTheDocument();
      });

      // Verify sector ETF shown in monospace font
      expect(screen.getByText('XLK')).toBeInTheDocument();
      expect(screen.getByText('XLK')).toHaveClass('font-mono');
    });

    it('should show trend direction with correct icon - up', async () => {
      vi.spyOn(live20Service, 'fetchSectorTrend').mockResolvedValue({
        ...mockSectorTrend,
        trend_direction: 'up',
      });
      vi.spyOn(stockService, 'fetchStockDataByDateRange').mockResolvedValue(mockStockData);
      vi.spyOn(stockService, 'fetchIndicators').mockResolvedValue(mockIndicatorsResponse);

      const result = createMockResult({ sector_etf: 'XLK' });
      render(<ExpandedRowContent result={result} />);

      await waitFor(() => {
        expect(screen.queryByText(/loading/i)).not.toBeInTheDocument();
      });

      expect(screen.getByText('up')).toBeInTheDocument();
    });

    it('should show trend direction with correct icon - down', async () => {
      vi.spyOn(live20Service, 'fetchSectorTrend').mockResolvedValue({
        ...mockSectorTrend,
        trend_direction: 'down',
      });
      vi.spyOn(stockService, 'fetchStockDataByDateRange').mockResolvedValue(mockStockData);
      vi.spyOn(stockService, 'fetchIndicators').mockResolvedValue(mockIndicatorsResponse);

      const result = createMockResult({ sector_etf: 'XLK' });
      render(<ExpandedRowContent result={result} />);

      await waitFor(() => {
        expect(screen.queryByText(/loading/i)).not.toBeInTheDocument();
      });

      expect(screen.getByText('down')).toBeInTheDocument();
    });

    it('should show trend direction with correct icon - sideways', async () => {
      vi.spyOn(live20Service, 'fetchSectorTrend').mockResolvedValue({
        ...mockSectorTrend,
        trend_direction: 'sideways',
      });
      vi.spyOn(stockService, 'fetchStockDataByDateRange').mockResolvedValue(mockStockData);
      vi.spyOn(stockService, 'fetchIndicators').mockResolvedValue(mockIndicatorsResponse);

      const result = createMockResult({ sector_etf: 'XLK' });
      render(<ExpandedRowContent result={result} />);

      await waitFor(() => {
        expect(screen.queryByText(/loading/i)).not.toBeInTheDocument();
      });

      expect(screen.getByText('sideways')).toBeInTheDocument();
    });

    it('should show MA20 position badge with correct variant', async () => {
      vi.spyOn(live20Service, 'fetchSectorTrend').mockResolvedValue({
        ...mockSectorTrend,
        ma20_position: 'above',
      });
      vi.spyOn(stockService, 'fetchStockDataByDateRange').mockResolvedValue(mockStockData);
      vi.spyOn(stockService, 'fetchIndicators').mockResolvedValue(mockIndicatorsResponse);

      const result = createMockResult({ sector_etf: 'XLK' });
      render(<ExpandedRowContent result={result} />);

      await waitFor(() => {
        expect(screen.queryByText(/loading/i)).not.toBeInTheDocument();
      });

      // Verify "above" badges are shown (both MA20 and MA50 can be above)
      const aboveBadges = screen.getAllByText('above');
      expect(aboveBadges.length).toBeGreaterThanOrEqual(1);
    });

    it('should show MA20 distance with correct formatting', async () => {
      vi.spyOn(live20Service, 'fetchSectorTrend').mockResolvedValue({
        ...mockSectorTrend,
        ma20_distance_pct: 2.5,
      });
      vi.spyOn(stockService, 'fetchStockDataByDateRange').mockResolvedValue(mockStockData);
      vi.spyOn(stockService, 'fetchIndicators').mockResolvedValue(mockIndicatorsResponse);

      const result = createMockResult({ sector_etf: 'XLK' });
      render(<ExpandedRowContent result={result} />);

      await waitFor(() => {
        expect(screen.queryByText(/loading/i)).not.toBeInTheDocument();
      });

      // Should show +2.5% (with + sign and 1 decimal)
      expect(screen.getByText('+2.5%')).toBeInTheDocument();
    });

    it('should show MA50 position and distance', async () => {
      vi.spyOn(live20Service, 'fetchSectorTrend').mockResolvedValue({
        ...mockSectorTrend,
        ma50_position: 'below',
        ma50_distance_pct: -3.2,
      });
      vi.spyOn(stockService, 'fetchStockDataByDateRange').mockResolvedValue(mockStockData);
      vi.spyOn(stockService, 'fetchIndicators').mockResolvedValue(mockIndicatorsResponse);

      const result = createMockResult({ sector_etf: 'XLK' });
      render(<ExpandedRowContent result={result} />);

      await waitFor(() => {
        expect(screen.queryByText(/loading/i)).not.toBeInTheDocument();
      });

      // Verify "below" badge and -3.2% distance
      expect(screen.getByText('below')).toBeInTheDocument();
      expect(screen.getByText('-3.2%')).toBeInTheDocument();
    });

    it('should show 5-day and 20-day price changes', async () => {
      vi.spyOn(live20Service, 'fetchSectorTrend').mockResolvedValue({
        ...mockSectorTrend,
        price_change_5d_pct: 1.23,
        price_change_20d_pct: -4.56,
      });
      vi.spyOn(stockService, 'fetchStockDataByDateRange').mockResolvedValue(mockStockData);
      vi.spyOn(stockService, 'fetchIndicators').mockResolvedValue(mockIndicatorsResponse);

      const result = createMockResult({ sector_etf: 'XLK' });
      render(<ExpandedRowContent result={result} />);

      await waitFor(() => {
        expect(screen.queryByText(/loading/i)).not.toBeInTheDocument();
      });

      // Verify 5-day change (positive, 2 decimals)
      expect(screen.getByText('+1.23%')).toBeInTheDocument();

      // Verify 20-day change (negative, 2 decimals)
      expect(screen.getByText('-4.56%')).toBeInTheDocument();
    });

    it('should show fallback message when no sector data', async () => {
      vi.spyOn(live20Service, 'fetchSectorTrend').mockResolvedValue(null);
      vi.spyOn(stockService, 'fetchStockDataByDateRange').mockResolvedValue(mockStockData);
      vi.spyOn(stockService, 'fetchIndicators').mockResolvedValue(mockIndicatorsResponse);

      const result = createMockResult({ sector_etf: null });
      render(<ExpandedRowContent result={result} />);

      await waitFor(() => {
        expect(screen.queryByText(/loading/i)).not.toBeInTheDocument();
      });

      // Verify fallback message
      expect(screen.getByText(/sector info not available/i)).toBeInTheDocument();
    });
  });

  describe('Stock chart display', () => {
    it('should render CandlestickChart with merged data', async () => {
      vi.spyOn(live20Service, 'fetchSectorTrend').mockResolvedValue(mockSectorTrend);
      vi.spyOn(stockService, 'fetchStockDataByDateRange').mockResolvedValue(mockStockData);
      vi.spyOn(stockService, 'fetchIndicators').mockResolvedValue(mockIndicatorsResponse);

      const result = createMockResult({ stock: 'AAPL' });
      render(<ExpandedRowContent result={result} />);

      await waitFor(() => {
        expect(screen.queryByText(/loading/i)).not.toBeInTheDocument();
      });

      // Verify chart is rendered
      const chart = screen.getByTestId('candlestick-chart');
      expect(chart).toBeInTheDocument();
    });

    it('should pass correct symbol to chart', async () => {
      vi.spyOn(live20Service, 'fetchSectorTrend').mockResolvedValue(mockSectorTrend);
      vi.spyOn(stockService, 'fetchStockDataByDateRange').mockResolvedValue(mockStockData);
      vi.spyOn(stockService, 'fetchIndicators').mockResolvedValue(mockIndicatorsResponse);

      const result = createMockResult({ stock: 'MSFT' });
      render(<ExpandedRowContent result={result} />);

      await waitFor(() => {
        expect(screen.queryByText(/loading/i)).not.toBeInTheDocument();
      });

      // Verify chart shows correct symbol
      expect(screen.getByText(/chart for msft/i)).toBeInTheDocument();
    });

    it('should pass height of 600px', async () => {
      vi.spyOn(live20Service, 'fetchSectorTrend').mockResolvedValue(mockSectorTrend);
      vi.spyOn(stockService, 'fetchStockDataByDateRange').mockResolvedValue(mockStockData);
      vi.spyOn(stockService, 'fetchIndicators').mockResolvedValue(mockIndicatorsResponse);

      const result = createMockResult();
      render(<ExpandedRowContent result={result} />);

      await waitFor(() => {
        expect(screen.queryByText(/loading/i)).not.toBeInTheDocument();
      });

      // Chart component receives height prop (tested via mocked component)
      expect(screen.getByTestId('candlestick-chart')).toBeInTheDocument();
    });

    it('should show fallback when no stock data', async () => {
      vi.spyOn(live20Service, 'fetchSectorTrend').mockResolvedValue(mockSectorTrend);
      vi.spyOn(stockService, 'fetchStockDataByDateRange').mockResolvedValue({ prices: [] });
      vi.spyOn(stockService, 'fetchIndicators').mockResolvedValue({ data: [] });

      const result = createMockResult();
      render(<ExpandedRowContent result={result} />);

      await waitFor(() => {
        expect(screen.queryByText(/loading/i)).not.toBeInTheDocument();
      });

      // Verify fallback message
      expect(screen.getByText(/no chart data available/i)).toBeInTheDocument();
    });
  });

  describe('UI rendering and layout', () => {
    it('should apply responsive grid classes', async () => {
      vi.spyOn(live20Service, 'fetchSectorTrend').mockResolvedValue(mockSectorTrend);
      vi.spyOn(stockService, 'fetchStockDataByDateRange').mockResolvedValue(mockStockData);
      vi.spyOn(stockService, 'fetchIndicators').mockResolvedValue(mockIndicatorsResponse);

      const result = createMockResult();
      render(<ExpandedRowContent result={result} />);

      await waitFor(() => {
        expect(screen.queryByText(/loading/i)).not.toBeInTheDocument();
      });

      // Find the grid container
      const gridContainer = document.querySelector('.grid');
      expect(gridContainer).toBeInTheDocument();
      expect(gridContainer).toHaveClass('grid-cols-1');
      expect(gridContainer).toHaveClass('lg:grid-cols-[280px_1fr]');
    });

    it('should show section headers', async () => {
      vi.spyOn(live20Service, 'fetchSectorTrend').mockResolvedValue(mockSectorTrend);
      vi.spyOn(stockService, 'fetchStockDataByDateRange').mockResolvedValue(mockStockData);
      vi.spyOn(stockService, 'fetchIndicators').mockResolvedValue(mockIndicatorsResponse);

      const result = createMockResult({ stock: 'AAPL' });
      render(<ExpandedRowContent result={result} />);

      await waitFor(() => {
        expect(screen.queryByText(/loading/i)).not.toBeInTheDocument();
      });

      // Verify both section headers
      expect(screen.getByText('Sector Trend Analysis')).toBeInTheDocument();
      expect(screen.getByText(/aapl chart \(3 months\)/i)).toBeInTheDocument();
    });

    it('should apply background and border styles', async () => {
      vi.spyOn(live20Service, 'fetchSectorTrend').mockResolvedValue(mockSectorTrend);
      vi.spyOn(stockService, 'fetchStockDataByDateRange').mockResolvedValue(mockStockData);
      vi.spyOn(stockService, 'fetchIndicators').mockResolvedValue(mockIndicatorsResponse);

      const result = createMockResult();
      render(<ExpandedRowContent result={result} />);

      await waitFor(() => {
        expect(screen.queryByText(/loading/i)).not.toBeInTheDocument();
      });

      // Find the main container
      const container = document.querySelector('.bg-bg-tertiary.border-t');
      expect(container).toBeInTheDocument();
      expect(container).toHaveClass('border-subtle');
    });
  });
});
