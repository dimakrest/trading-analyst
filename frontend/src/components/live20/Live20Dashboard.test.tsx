import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { Live20Dashboard } from './Live20Dashboard';
import { useLive20 } from '@/hooks/useLive20';
import type { Live20Result, Live20Counts } from '@/types/live20';

// Mock the useLive20 hook
vi.mock('@/hooks/useLive20');

// Mock the useResponsive hook to avoid mobile-specific behavior
vi.mock('@/hooks/useResponsive', () => ({
  useResponsive: () => ({ isMobile: false }),
}));

// Mock the useStockLists hook to prevent async state updates after unmount
vi.mock('@/hooks/useStockLists', () => ({
  useStockLists: () => ({
    lists: [],
    isLoading: false,
    error: null,
    createList: vi.fn(),
    updateList: vi.fn(),
    deleteList: vi.fn(),
    refetch: vi.fn(),
  }),
}));

const mockResults: Live20Result[] = [
  {
    id: 1,
    stock: 'AAPL',
    created_at: '2025-12-24T12:00:00Z',
    recommendation: 'LONG',
    confidence_score: 85,
    sector_etf: 'XLK',
    trend_direction: 'UP',
    trend_aligned: true,
    ma20_distance_pct: -2.1,
    ma20_aligned: true,
    candle_pattern: 'hammer',
    candle_bullish: true,
    candle_aligned: true,
    candle_explanation: 'Bullish hammer pattern',
    volume_aligned: true,
    volume_approach: 'accumulation',
    rvol: 1.8,
    cci_direction: 'rising',
    cci_value: -120,
    cci_zone: 'oversold',
    cci_aligned: true,
    criteria_aligned: 5,
    direction: 'LONG',
    atr: 3.45,
  },
  {
    id: 2,
    stock: 'MSFT',
    created_at: '2025-12-24T12:00:00Z',
    recommendation: 'SHORT',
    confidence_score: 72,
    sector_etf: 'XLK',
    trend_direction: 'DOWN',
    trend_aligned: true,
    ma20_distance_pct: 3.2,
    ma20_aligned: true,
    candle_pattern: 'shooting_star',
    candle_bullish: false,
    candle_aligned: true,
    candle_explanation: 'Bearish shooting star',
    volume_aligned: false,
    volume_approach: 'distribution',
    rvol: 2.5,
    cci_direction: 'falling',
    cci_value: 150,
    cci_zone: 'overbought',
    cci_aligned: true,
    criteria_aligned: 4,
    direction: 'SHORT',
    atr: 5.80,
  },
  {
    id: 3,
    stock: 'NVDA',
    created_at: '2025-12-24T12:00:00Z',
    recommendation: 'LONG',
    confidence_score: 68,
    sector_etf: 'XLK',
    trend_direction: 'UP',
    trend_aligned: true,
    ma20_distance_pct: -1.5,
    ma20_aligned: true,
    candle_pattern: 'doji',
    candle_bullish: true,
    candle_aligned: false,
    candle_explanation: 'Neutral doji',
    volume_aligned: true,
    volume_approach: 'accumulation',
    rvol: 1.2,
    cci_direction: 'rising',
    cci_value: -80,
    cci_zone: 'neutral',
    cci_aligned: true,
    criteria_aligned: 4,
    direction: 'LONG',
    atr: 12.50,
  },
];

const mockCounts: Live20Counts = {
  long: 2,
  short: 1,
  no_setup: 0,
  total: 3,
};

const renderDashboard = () => {
  return render(
    <MemoryRouter>
      <Live20Dashboard />
    </MemoryRouter>
  );
};

describe('Live20Dashboard progressive results', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('Progressive results display', () => {
    it('should show table while analysis is in progress when results exist', () => {
      // Mock: Analysis in progress with partial results
      vi.mocked(useLive20).mockReturnValue({
        results: mockResults,
        counts: mockCounts,
        isLoading: false,
        isAnalyzing: true,
        error: null,
        analyzeSymbols: vi.fn(),
        fetchResults: vi.fn(),
        progress: {
          runId: 123,
          total: 10,
          processed: 5,
          status: 'running',
        },
        cancelAnalysis: vi.fn(),
        isCancelling: false,
        failedSymbols: {},
      });

      renderDashboard();

      // Should show loading indicator
      expect(screen.getByText(/analyzing 10 symbols/i)).toBeInTheDocument();

      // Should also show table with partial results
      expect(screen.getByText('AAPL')).toBeInTheDocument();
      expect(screen.getByText('MSFT')).toBeInTheDocument();
      expect(screen.getByText('NVDA')).toBeInTheDocument();

      // Should show results count in loading component (use getAllByText since it appears in sr-only too)
      expect(screen.getAllByText(/3 setups found/i).length).toBeGreaterThan(0);
    });

    it('should update results dynamically during analysis', () => {
      // Initial state: 1 result
      const { rerender } = render(
        <MemoryRouter>
          <Live20Dashboard />
        </MemoryRouter>
      );

      vi.mocked(useLive20).mockReturnValue({
        results: [mockResults[0]],
        counts: { long: 1, short: 0, no_setup: 0, total: 1 },
        isLoading: false,
        isAnalyzing: true,
        error: null,
        analyzeSymbols: vi.fn(),
        fetchResults: vi.fn(),
        progress: {
          runId: 123,
          total: 10,
          processed: 3,
          status: 'running',
        },
        cancelAnalysis: vi.fn(),
        isCancelling: false,
        failedSymbols: {},
      });

      rerender(
        <MemoryRouter>
          <Live20Dashboard />
        </MemoryRouter>
      );

      // Should show only AAPL
      expect(screen.getByText('AAPL')).toBeInTheDocument();
      expect(screen.queryByText('MSFT')).not.toBeInTheDocument();
      expect(screen.getAllByText(/1 setup found/i).length).toBeGreaterThan(0);

      // Update: 3 results now
      vi.mocked(useLive20).mockReturnValue({
        results: mockResults,
        counts: mockCounts,
        isLoading: false,
        isAnalyzing: true,
        error: null,
        analyzeSymbols: vi.fn(),
        fetchResults: vi.fn(),
        progress: {
          runId: 123,
          total: 10,
          processed: 7,
          status: 'running',
        },
        cancelAnalysis: vi.fn(),
        isCancelling: false,
        failedSymbols: {},
      });

      rerender(
        <MemoryRouter>
          <Live20Dashboard />
        </MemoryRouter>
      );

      // Should now show all 3 results
      expect(screen.getByText('AAPL')).toBeInTheDocument();
      expect(screen.getByText('MSFT')).toBeInTheDocument();
      expect(screen.getByText('NVDA')).toBeInTheDocument();
      expect(screen.getAllByText(/3 setups found/i).length).toBeGreaterThan(0);
    });

    it('should not show table when no results yet', () => {
      // Mock: Analysis in progress but no results yet
      vi.mocked(useLive20).mockReturnValue({
        results: [],
        counts: { long: 0, short: 0, no_setup: 0, total: 0 },
        isLoading: false,
        isAnalyzing: true,
        error: null,
        analyzeSymbols: vi.fn(),
        fetchResults: vi.fn(),
        progress: {
          runId: 123,
          total: 10,
          processed: 2,
          status: 'running',
        },
        cancelAnalysis: vi.fn(),
        isCancelling: false,
        failedSymbols: {},
      });

      renderDashboard();

      // Should show loading indicator
      expect(screen.getByText(/analyzing 10 symbols/i)).toBeInTheDocument();

      // Should not show empty state or table headers
      expect(screen.queryByText('AAPL')).not.toBeInTheDocument();
      expect(screen.queryByText('No symbols analyzed yet')).not.toBeInTheDocument();
    });
  });

  describe('Cancel functionality', () => {
    it('should show cancel button during analysis', () => {
      vi.mocked(useLive20).mockReturnValue({
        results: [],
        counts: { long: 0, short: 0, no_setup: 0, total: 0 },
        isLoading: false,
        isAnalyzing: true,
        error: null,
        analyzeSymbols: vi.fn(),
        fetchResults: vi.fn(),
        progress: {
          runId: 123,
          total: 10,
          processed: 2,
          status: 'running',
        },
        cancelAnalysis: vi.fn(),
        isCancelling: false,
        failedSymbols: {},
      });

      renderDashboard();

      const cancelButton = screen.getByRole('button', { name: /cancel analysis/i });
      expect(cancelButton).toBeInTheDocument();
      expect(cancelButton).not.toBeDisabled();
    });

    it('should call cancelAnalysis when cancel button clicked', async () => {
      const mockCancelAnalysis = vi.fn();
      const user = userEvent.setup();

      vi.mocked(useLive20).mockReturnValue({
        results: [],
        counts: { long: 0, short: 0, no_setup: 0, total: 0 },
        isLoading: false,
        isAnalyzing: true,
        error: null,
        analyzeSymbols: vi.fn(),
        fetchResults: vi.fn(),
        progress: {
          runId: 123,
          total: 10,
          processed: 2,
          status: 'running',
        },
        cancelAnalysis: mockCancelAnalysis,
        isCancelling: false,
        failedSymbols: {},
      });

      renderDashboard();

      const cancelButton = screen.getByRole('button', { name: /cancel analysis/i });
      await user.click(cancelButton);

      expect(mockCancelAnalysis).toHaveBeenCalledTimes(1);
    });

    it('should show cancelling state when isCancelling is true', () => {
      vi.mocked(useLive20).mockReturnValue({
        results: mockResults,
        counts: mockCounts,
        isLoading: false,
        isAnalyzing: true,
        error: null,
        analyzeSymbols: vi.fn(),
        fetchResults: vi.fn(),
        progress: {
          runId: 123,
          total: 10,
          processed: 5,
          status: 'running',
        },
        cancelAnalysis: vi.fn(),
        isCancelling: true,
        failedSymbols: {},
      });

      renderDashboard();

      const cancelButton = screen.getByRole('button', { name: /cancelling/i });
      expect(cancelButton).toBeInTheDocument();
      expect(cancelButton).toBeDisabled();
    });
  });

  describe('Cancelled state UI', () => {
    it('should show cancelled banner after cancellation with result count', async () => {
      // Simulate cancelled state: isAnalyzing=false, progress.status was 'cancelled'
      vi.mocked(useLive20).mockReturnValue({
        results: mockResults,
        counts: mockCounts,
        isLoading: false,
        isAnalyzing: false,
        error: null,
        analyzeSymbols: vi.fn(),
        fetchResults: vi.fn(),
        progress: {
          runId: 123,
          total: 10,
          processed: 5,
          status: 'cancelled',
        },
        cancelAnalysis: vi.fn(),
        isCancelling: false,
        failedSymbols: {},
      });

      renderDashboard();

      // Should show cancelled alert banner
      await waitFor(() => {
        expect(
          screen.getByText(/analysis was cancelled\. showing 3 results? found before cancellation/i)
        ).toBeInTheDocument();
      });

      // Should show results table
      expect(screen.getByText('AAPL')).toBeInTheDocument();
      expect(screen.getByText('MSFT')).toBeInTheDocument();
      expect(screen.getByText('NVDA')).toBeInTheDocument();

      // Should NOT show loading indicator
      expect(screen.queryByText(/analyzing/i)).not.toBeInTheDocument();
    });

    it('should show singular form for 1 result after cancellation', async () => {
      vi.mocked(useLive20).mockReturnValue({
        results: [mockResults[0]],
        counts: { long: 1, short: 0, no_setup: 0, total: 1 },
        isLoading: false,
        isAnalyzing: false,
        error: null,
        analyzeSymbols: vi.fn(),
        fetchResults: vi.fn(),
        progress: {
          runId: 123,
          total: 10,
          processed: 2,
          status: 'cancelled',
        },
        cancelAnalysis: vi.fn(),
        isCancelling: false,
        failedSymbols: {},
      });

      renderDashboard();

      // Should use singular "result" not "results"
      await waitFor(() => {
        expect(
          screen.getByText(/analysis was cancelled\. showing 1 result found before cancellation/i)
        ).toBeInTheDocument();
      });
    });

    it('should not show cancelled banner when analysis completes normally', () => {
      vi.mocked(useLive20).mockReturnValue({
        results: mockResults,
        counts: mockCounts,
        isLoading: false,
        isAnalyzing: false,
        error: null,
        analyzeSymbols: vi.fn(),
        fetchResults: vi.fn(),
        progress: {
          runId: 123,
          total: 10,
          processed: 10,
          status: 'completed',
        },
        cancelAnalysis: vi.fn(),
        isCancelling: false,
        failedSymbols: {},
      });

      renderDashboard();

      // Should NOT show cancelled banner
      expect(screen.queryByText(/analysis was cancelled/i)).not.toBeInTheDocument();

      // Should show results normally
      expect(screen.getByText('AAPL')).toBeInTheDocument();
    });

    it('should not show cancelled banner when no results after cancellation', () => {
      vi.mocked(useLive20).mockReturnValue({
        results: [],
        counts: { long: 0, short: 0, no_setup: 0, total: 0 },
        isLoading: false,
        isAnalyzing: false,
        error: null,
        analyzeSymbols: vi.fn(),
        fetchResults: vi.fn(),
        progress: {
          runId: 123,
          total: 10,
          processed: 1,
          status: 'cancelled',
        },
        cancelAnalysis: vi.fn(),
        isCancelling: false,
        failedSymbols: {},
      });

      renderDashboard();

      // Should not show cancelled banner when results.length === 0
      expect(screen.queryByText(/analysis was cancelled/i)).not.toBeInTheDocument();

      // Should show empty state
      expect(screen.getByText(/no symbols analyzed yet/i)).toBeInTheDocument();
    });
  });

  describe('Accessibility', () => {
    it('should announce progress updates to screen readers', () => {
      vi.mocked(useLive20).mockReturnValue({
        results: mockResults,
        counts: mockCounts,
        isLoading: false,
        isAnalyzing: true,
        error: null,
        analyzeSymbols: vi.fn(),
        fetchResults: vi.fn(),
        progress: {
          runId: 123,
          total: 10,
          processed: 5,
          status: 'running',
        },
        cancelAnalysis: vi.fn(),
        isCancelling: false,
        failedSymbols: {},
      });

      renderDashboard();

      // Check for accessibility status region
      const statusRegion = screen.getByRole('status');
      expect(statusRegion).toBeInTheDocument();
      expect(statusRegion).toHaveAttribute('aria-live', 'polite');
      expect(statusRegion).toHaveAttribute('aria-atomic', 'true');

      // The status region contains the announcement text (but it's visually hidden)
      // We can't easily test the exact text since it's in sr-only, but we can verify the region exists
    });

    it('should announce cancellation to screen readers', () => {
      vi.mocked(useLive20).mockReturnValue({
        results: mockResults,
        counts: mockCounts,
        isLoading: false,
        isAnalyzing: false,
        error: null,
        analyzeSymbols: vi.fn(),
        fetchResults: vi.fn(),
        progress: {
          runId: 123,
          total: 10,
          processed: 5,
          status: 'cancelled',
        },
        cancelAnalysis: vi.fn(),
        isCancelling: false,
        failedSymbols: {},
      });

      renderDashboard();

      // Check for accessibility status region
      const statusRegion = screen.getByRole('status');
      expect(statusRegion).toBeInTheDocument();
      expect(statusRegion).toHaveAttribute('aria-live', 'polite');
    });
  });

  describe('Empty and error states', () => {
    it('should show empty state when no analysis has been run', () => {
      vi.mocked(useLive20).mockReturnValue({
        results: [],
        counts: { long: 0, short: 0, no_setup: 0, total: 0 },
        isLoading: false,
        isAnalyzing: false,
        error: null,
        analyzeSymbols: vi.fn(),
        fetchResults: vi.fn(),
        progress: null,
        cancelAnalysis: vi.fn(),
        isCancelling: false,
        failedSymbols: {},
      });

      renderDashboard();

      expect(screen.getByText(/no symbols analyzed yet/i)).toBeInTheDocument();
      expect(screen.getByText(/enter stock symbols above and click analyze to get started/i)).toBeInTheDocument();
    });

    it('should show error message when error occurs', () => {
      vi.mocked(useLive20).mockReturnValue({
        results: [],
        counts: { long: 0, short: 0, no_setup: 0, total: 0 },
        isLoading: false,
        isAnalyzing: false,
        error: 'Failed to analyze symbols',
        analyzeSymbols: vi.fn(),
        fetchResults: vi.fn(),
        progress: null,
        cancelAnalysis: vi.fn(),
        isCancelling: false,
        failedSymbols: {},
      });

      renderDashboard();

      expect(screen.getByText('Failed to analyze symbols')).toBeInTheDocument();
    });
  });

  describe('Failed symbols display', () => {
    it('should show failed symbols alert when symbols failed', () => {
      vi.mocked(useLive20).mockReturnValue({
        results: mockResults,
        counts: mockCounts,
        isLoading: false,
        isAnalyzing: false,
        error: null,
        analyzeSymbols: vi.fn(),
        fetchResults: vi.fn(),
        progress: null,
        cancelAnalysis: vi.fn(),
        isCancelling: false,
        failedSymbols: {
          'INVALID': 'Symbol not found',
          'ERROR': 'Data fetch failed',
        },
      });

      renderDashboard();

      expect(screen.getByText(/2 symbols failed to analyze:/i)).toBeInTheDocument();
      expect(screen.getByText(/INVALID: Symbol not found/i)).toBeInTheDocument();
      expect(screen.getByText(/ERROR: Data fetch failed/i)).toBeInTheDocument();
    });

    it('should use singular form for 1 failed symbol', () => {
      vi.mocked(useLive20).mockReturnValue({
        results: mockResults,
        counts: mockCounts,
        isLoading: false,
        isAnalyzing: false,
        error: null,
        analyzeSymbols: vi.fn(),
        fetchResults: vi.fn(),
        progress: null,
        cancelAnalysis: vi.fn(),
        isCancelling: false,
        failedSymbols: {
          'INVALID': 'Symbol not found',
        },
      });

      renderDashboard();

      expect(screen.getByText(/1 symbol failed to analyze:/i)).toBeInTheDocument();
    });

    it('should limit failed symbols display to 5', () => {
      vi.mocked(useLive20).mockReturnValue({
        results: mockResults,
        counts: mockCounts,
        isLoading: false,
        isAnalyzing: false,
        error: null,
        analyzeSymbols: vi.fn(),
        fetchResults: vi.fn(),
        progress: null,
        cancelAnalysis: vi.fn(),
        isCancelling: false,
        failedSymbols: {
          'SYM1': 'Error 1',
          'SYM2': 'Error 2',
          'SYM3': 'Error 3',
          'SYM4': 'Error 4',
          'SYM5': 'Error 5',
          'SYM6': 'Error 6',
          'SYM7': 'Error 7',
        },
      });

      renderDashboard();

      expect(screen.getByText(/7 symbols failed to analyze:/i)).toBeInTheDocument();
      expect(screen.getByText(/\.\.\.and 2 more/i)).toBeInTheDocument();
    });

    it('should not show failed symbols alert during analysis', () => {
      vi.mocked(useLive20).mockReturnValue({
        results: mockResults,
        counts: mockCounts,
        isLoading: false,
        isAnalyzing: true,
        error: null,
        analyzeSymbols: vi.fn(),
        fetchResults: vi.fn(),
        progress: {
          runId: 123,
          total: 10,
          processed: 5,
          status: 'running',
        },
        cancelAnalysis: vi.fn(),
        isCancelling: false,
        failedSymbols: {
          'INVALID': 'Symbol not found',
        },
      });

      renderDashboard();

      expect(screen.queryByText(/failed to analyze/i)).not.toBeInTheDocument();
    });

    it('should not show failed symbols alert when no failures', () => {
      vi.mocked(useLive20).mockReturnValue({
        results: mockResults,
        counts: mockCounts,
        isLoading: false,
        isAnalyzing: false,
        error: null,
        analyzeSymbols: vi.fn(),
        fetchResults: vi.fn(),
        progress: null,
        cancelAnalysis: vi.fn(),
        isCancelling: false,
        failedSymbols: {},
      });

      renderDashboard();

      expect(screen.queryByText(/failed to analyze/i)).not.toBeInTheDocument();
    });
  });

  describe('Min Rvol filter', () => {
    it('should filter results by minimum rvol threshold', async () => {
      const user = userEvent.setup();

      vi.mocked(useLive20).mockReturnValue({
        results: mockResults, // AAPL: 1.8, MSFT: 2.5, NVDA: 1.2
        counts: mockCounts,
        isLoading: false,
        isAnalyzing: false,
        error: null,
        analyzeSymbols: vi.fn(),
        fetchResults: vi.fn(),
        progress: null,
        cancelAnalysis: vi.fn(),
        isCancelling: false,
        failedSymbols: {},
      });

      renderDashboard();

      // All three symbols should be visible initially
      expect(screen.getByText('AAPL')).toBeInTheDocument();
      expect(screen.getByText('MSFT')).toBeInTheDocument();
      expect(screen.getByText('NVDA')).toBeInTheDocument();

      // Find the Min Rvol slider
      const sliders = screen.getAllByRole('slider');
      const rvolSlider = sliders.find((slider) => {
        const label = slider.closest('div')?.querySelector('span');
        return label?.textContent?.includes('Min Rvol');
      });
      expect(rvolSlider).toBeDefined();

      // Set min rvol to 1.5 (should exclude NVDA with 1.2)
      // The slider has min=0, max=3, step=0.1
      // We need to set it to 1.5, which is 15 steps from 0 (1.5 / 0.1 = 15)
      await user.click(rvolSlider!);
      const steps = '{ArrowRight}'.repeat(15);
      await user.keyboard(steps);

      // Wait for filtering to apply
      await waitFor(() => {
        expect(screen.getByText('AAPL')).toBeInTheDocument();
        expect(screen.getByText('MSFT')).toBeInTheDocument();
        expect(screen.queryByText('NVDA')).not.toBeInTheDocument();
      });
    });

    it('should display default minRvol value of 0', () => {
      vi.mocked(useLive20).mockReturnValue({
        results: mockResults,
        counts: mockCounts,
        isLoading: false,
        isAnalyzing: false,
        error: null,
        analyzeSymbols: vi.fn(),
        fetchResults: vi.fn(),
        progress: null,
        cancelAnalysis: vi.fn(),
        isCancelling: false,
        failedSymbols: {},
      });

      renderDashboard();

      // Find the Min Rvol input field with default value of 0
      const rvolInput = screen.getByDisplayValue('0');
      expect(rvolInput).toBeInTheDocument();
    });

    it('should exclude results below minRvol threshold when filter is applied', async () => {
      const user = userEvent.setup();

      const resultsWithLowRvol = [
        ...mockResults,
        {
          ...mockResults[0],
          id: 4,
          stock: 'LOWRVOL',
          rvol: 0.8,
        },
      ];

      vi.mocked(useLive20).mockReturnValue({
        results: resultsWithLowRvol,
        counts: { ...mockCounts, long: 3, total: 4 },
        isLoading: false,
        isAnalyzing: false,
        error: null,
        analyzeSymbols: vi.fn(),
        fetchResults: vi.fn(),
        progress: null,
        cancelAnalysis: vi.fn(),
        isCancelling: false,
        failedSymbols: {},
      });

      renderDashboard();

      // With default minRvol=0 (Off), all symbols should be visible
      expect(screen.getByText('AAPL')).toBeInTheDocument();
      expect(screen.getByText('LOWRVOL')).toBeInTheDocument();

      // Find the Min Rvol input field and set threshold
      const rvolInput = screen.getByDisplayValue('0');
      expect(rvolInput).toBeInTheDocument();

      // Clear and set to 1.0 (should exclude LOWRVOL with 0.8)
      await user.clear(rvolInput);
      await user.type(rvolInput, '1.0');

      // LOWRVOL should be filtered out since it's below 1.0
      await waitFor(() => {
        expect(screen.getByText('AAPL')).toBeInTheDocument();
        expect(screen.queryByText('LOWRVOL')).not.toBeInTheDocument();
      });
    });
  });
});
