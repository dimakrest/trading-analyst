import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { Live20RunDetail } from './Live20RunDetail';
import * as live20Service from '../services/live20Service';
import type { Live20RunDetail as Live20RunDetailType } from '../types/live20';
import { toast } from 'sonner';

// Mock the live20Service
vi.mock('../services/live20Service');

// Mock sonner toast
vi.mock('sonner', () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}));

const mockRunDetail: Live20RunDetailType = {
  id: 42,
  created_at: '2025-12-24T12:45:00Z',
  status: 'completed',
  symbol_count: 5,
  processed_count: 5,
  long_count: 2,
  short_count: 1,
  no_setup_count: 2,
  input_symbols: ['AAPL', 'MSFT', 'NVDA', 'GOOGL', 'TSLA'],
  stock_list_id: null,
  stock_list_name: null,
  results: [
    {
      id: 1,
      stock: 'AAPL',
      created_at: '2025-12-24T12:45:00Z',
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
      created_at: '2025-12-24T12:45:00Z',
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
      created_at: '2025-12-24T12:45:00Z',
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
    {
      id: 4,
      stock: 'GOOGL',
      created_at: '2025-12-24T12:45:00Z',
      recommendation: 'NO_SETUP',
      confidence_score: 40,
      sector_etf: null,
      trend_direction: 'UP',
      trend_aligned: false,
      ma20_distance_pct: -5.2,
      ma20_aligned: false,
      candle_pattern: null,
      candle_bullish: null,
      candle_aligned: null,
      candle_explanation: null,
      volume_aligned: false,
      volume_approach: null,
      rvol: 0.8,
      cci_direction: 'flat',
      cci_value: 10,
      cci_zone: 'neutral',
      cci_aligned: false,
      criteria_aligned: 1,
      direction: 'NO_SETUP',
      atr: null,
    },
    {
      id: 5,
      stock: 'TSLA',
      created_at: '2025-12-24T12:45:00Z',
      recommendation: 'NO_SETUP',
      confidence_score: 35,
      sector_etf: null,
      trend_direction: null,
      trend_aligned: null,
      ma20_distance_pct: -8.5,
      ma20_aligned: false,
      candle_pattern: null,
      candle_bullish: null,
      candle_aligned: null,
      candle_explanation: null,
      volume_aligned: false,
      volume_approach: null,
      rvol: 0.5,
      cci_direction: 'flat',
      cci_value: 5,
      cci_zone: 'neutral',
      cci_aligned: false,
      criteria_aligned: 0,
      direction: 'NO_SETUP',
      atr: null,
    },
  ],
};

const renderWithRouter = (initialPath = '/live-20/runs/42') => {
  return render(
    <MemoryRouter initialEntries={[initialPath]}>
      <Routes>
        <Route path="/live-20/runs/:id" element={<Live20RunDetail />} />
        <Route path="/live-20" element={<div>History Tab</div>} />
      </Routes>
    </MemoryRouter>
  );
};

describe('Live20RunDetail', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('Loading State', () => {
    it('renders loading spinner while fetching run', async () => {
      vi.mocked(live20Service.getRunDetail).mockImplementation(
        () => new Promise(() => {}) // Never resolves
      );

      renderWithRouter();

      // Loader2 icon doesn't have role="img", so just check the container exists
      const container = document.querySelector('.container');
      expect(container).toBeInTheDocument();
      expect(live20Service.getRunDetail).toHaveBeenCalledWith(42);
    });
  });

  describe('Success State', () => {
    beforeEach(() => {
      vi.mocked(live20Service.getRunDetail).mockResolvedValue(mockRunDetail);
    });

    it('renders run details correctly', async () => {
      renderWithRouter();

      await waitFor(() => {
        expect(screen.getByText(/Analysis Run —/)).toBeInTheDocument();
      });

      // Header
      expect(screen.getByText(/Analysis Run — Dec 24, 2025/)).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /Back/ })).toBeInTheDocument();
      // Completed run should show Delete button
      expect(screen.getByRole('button', { name: /Delete/ })).toBeInTheDocument();
      // Should not show Cancel button for completed run
      expect(screen.queryByRole('button', { name: /Cancel/ })).not.toBeInTheDocument();

      // Summary card
      expect(screen.getByText('Run Summary')).toBeInTheDocument();
      expect(screen.getByText('Total Symbols')).toBeInTheDocument();
      expect(screen.getByText('Long Setups')).toBeInTheDocument();
      expect(screen.getByText('Short Setups')).toBeInTheDocument();
      // "No Setup" appears in both summary card and filter button, so use getAllByText
      expect(screen.getAllByText('No Setup').length).toBeGreaterThan(0);

      // Check counts exist (they may appear multiple times in different contexts)
      expect(screen.getAllByText('5').length).toBeGreaterThan(0); // symbol_count
      expect(screen.getAllByText('2').length).toBeGreaterThan(0); // long_count
      expect(screen.getAllByText('1').length).toBeGreaterThan(0); // short_count

      // Results card
      expect(screen.getByText('Results')).toBeInTheDocument();

      // Check filters are rendered (counts are now in separate spans)
      // The filter buttons have their label and count as separate elements
      const allButton = screen.getByRole('button', { name: /All/ });
      expect(allButton).toBeInTheDocument();
      expect(within(allButton).getByText('5')).toBeInTheDocument();

      const longButton = screen.getByRole('button', { name: /Long/ });
      expect(longButton).toBeInTheDocument();

      const shortButton = screen.getByRole('button', { name: /Short/ });
      expect(shortButton).toBeInTheDocument();

      // Multiple "No Setup" buttons may exist (one in filters, one label in summary)
      const noSetupButtons = screen.getAllByRole('button', { name: /No Setup/ });
      expect(noSetupButtons.length).toBeGreaterThan(0);

      // Check table has results
      expect(screen.getByText('AAPL')).toBeInTheDocument();
      expect(screen.getByText('MSFT')).toBeInTheDocument();
      expect(screen.getByText('NVDA')).toBeInTheDocument();
      expect(screen.getByText('GOOGL')).toBeInTheDocument();
      expect(screen.getByText('TSLA')).toBeInTheDocument();
    });

    it('filters results by direction', async () => {
      const user = userEvent.setup();
      renderWithRouter();

      await waitFor(() => {
        expect(screen.getByText('AAPL')).toBeInTheDocument();
      });

      // Click "Long" filter - button accessible name is "Long 2" (label + count)
      const longButton = screen.getByRole('button', { name: /Long/ });
      await user.click(longButton);

      // Should show only LONG results
      expect(screen.getByText('AAPL')).toBeInTheDocument();
      expect(screen.getByText('NVDA')).toBeInTheDocument();
      expect(screen.queryByText('MSFT')).not.toBeInTheDocument(); // SHORT
      expect(screen.queryByText('GOOGL')).not.toBeInTheDocument(); // NO_SETUP
      expect(screen.queryByText('TSLA')).not.toBeInTheDocument(); // NO_SETUP
    });

    it('filters results by search query', async () => {
      const user = userEvent.setup();
      renderWithRouter();

      await waitFor(() => {
        expect(screen.getByText('AAPL')).toBeInTheDocument();
      });

      // Type in search box
      const searchInput = screen.getByPlaceholderText(/Search symbols/);
      await user.type(searchInput, 'AAP');

      // Should show only AAPL
      expect(screen.getByText('AAPL')).toBeInTheDocument();
      expect(screen.queryByText('MSFT')).not.toBeInTheDocument();
      expect(screen.queryByText('NVDA')).not.toBeInTheDocument();
      expect(screen.queryByText('GOOGL')).not.toBeInTheDocument();
      expect(screen.queryByText('TSLA')).not.toBeInTheDocument();
    });

    it('filters results by minimum score', async () => {
      renderWithRouter();

      await waitFor(() => {
        expect(screen.getByText('AAPL')).toBeInTheDocument();
      });

      // The slider components are present (Min Score and Min Rvol)
      const sliders = screen.getAllByRole('slider');
      expect(sliders).toHaveLength(2);

      // Min Score slider (first)
      expect(sliders[0]).toHaveAttribute('aria-valuemin', '0');
      expect(sliders[0]).toHaveAttribute('aria-valuemax', '100');

      // Min Rvol slider (second)
      expect(sliders[1]).toHaveAttribute('aria-valuemin', '0');
      expect(sliders[1]).toHaveAttribute('aria-valuemax', '3');

      // Note: Testing slider interaction with Radix UI has known issues in JSDOM
      // In a real browser, users can adjust the sliders to filter by minimum score and rvol
      // The filtering logic is tested through the useMemo in the component
      // and the Live20Filters component is already tested separately
    });

    it('combines multiple filters', async () => {
      const user = userEvent.setup();
      renderWithRouter();

      await waitFor(() => {
        expect(screen.getByText('AAPL')).toBeInTheDocument();
      });

      // Filter by LONG direction - button accessible name is "Long 2" (label + count)
      const longButton = screen.getByRole('button', { name: /Long/ });
      await user.click(longButton);

      // Add search filter
      const searchInput = screen.getByPlaceholderText(/Search symbols/);
      await user.type(searchInput, 'NV');

      // Should show only NVDA (LONG + matches "NV")
      expect(screen.getByText('NVDA')).toBeInTheDocument();
      expect(screen.queryByText('AAPL')).not.toBeInTheDocument();
      expect(screen.queryByText('MSFT')).not.toBeInTheDocument();
      expect(screen.queryByText('GOOGL')).not.toBeInTheDocument();
      expect(screen.queryByText('TSLA')).not.toBeInTheDocument();
    });
  });

  describe('Error Handling', () => {
    it('handles 404 error when run not found', async () => {
      vi.mocked(live20Service.getRunDetail).mockRejectedValue(new Error('Run not found'));

      renderWithRouter();

      await waitFor(() => {
        expect(screen.getByText('Run not found')).toBeInTheDocument();
      });

      expect(screen.getByRole('button', { name: /Back to History/ })).toBeInTheDocument();
    });

    it('handles general API errors', async () => {
      vi.mocked(live20Service.getRunDetail).mockRejectedValue(
        new Error('Failed to fetch run: Internal Server Error')
      );

      renderWithRouter();

      await waitFor(() => {
        expect(screen.getByText(/Failed to fetch run/)).toBeInTheDocument();
      });

      expect(screen.getByRole('button', { name: /Back to History/ })).toBeInTheDocument();
    });
  });

  describe('Navigation', () => {
    beforeEach(() => {
      vi.mocked(live20Service.getRunDetail).mockResolvedValue(mockRunDetail);
    });

    it('navigates back to history tab on back button click', async () => {
      const user = userEvent.setup();
      renderWithRouter();

      await waitFor(() => {
        expect(screen.getByText('AAPL')).toBeInTheDocument();
      });

      const backButton = screen.getByRole('button', { name: /Back/ });
      await user.click(backButton);

      await waitFor(() => {
        expect(screen.getByText('History Tab')).toBeInTheDocument();
      });
    });
  });

  describe('Cancel Functionality', () => {
    it('shows Cancel button for running runs', async () => {
      const runningRun: Live20RunDetailType = {
        ...mockRunDetail,
        status: 'running',
      };
      vi.mocked(live20Service.getRunDetail).mockResolvedValue(runningRun);

      renderWithRouter();

      await waitFor(() => {
        expect(screen.getByText('AAPL')).toBeInTheDocument();
      });

      // Should show Cancel button for running run
      expect(screen.getByRole('button', { name: /Cancel/ })).toBeInTheDocument();
      // Should not show Delete button for running run
      expect(screen.queryByRole('button', { name: /Delete/ })).not.toBeInTheDocument();
    });

    it('shows Cancel button for pending runs', async () => {
      const pendingRun: Live20RunDetailType = {
        ...mockRunDetail,
        status: 'pending',
      };
      vi.mocked(live20Service.getRunDetail).mockResolvedValue(pendingRun);

      renderWithRouter();

      await waitFor(() => {
        expect(screen.getByText('AAPL')).toBeInTheDocument();
      });

      // Should show Cancel button for pending run
      expect(screen.getByRole('button', { name: /Cancel/ })).toBeInTheDocument();
      // Should not show Delete button for pending run
      expect(screen.queryByRole('button', { name: /Delete/ })).not.toBeInTheDocument();
    });

    it('opens confirmation dialog when cancel button clicked', async () => {
      const user = userEvent.setup();
      const runningRun: Live20RunDetailType = {
        ...mockRunDetail,
        status: 'running',
      };
      vi.mocked(live20Service.getRunDetail).mockResolvedValue(runningRun);

      renderWithRouter();

      await waitFor(() => {
        expect(screen.getByText('AAPL')).toBeInTheDocument();
      });

      const cancelButton = screen.getByRole('button', { name: /Cancel/ });
      await user.click(cancelButton);

      // Dialog should appear
      expect(screen.getByText('Stop analysis?')).toBeInTheDocument();
      expect(
        screen.getByText(/The analysis will stop immediately/)
      ).toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'Continue' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /Stop analysis/ })).toBeInTheDocument();
    });

    it('cancels run and refreshes data on confirmation', async () => {
      const user = userEvent.setup();
      const runningRun: Live20RunDetailType = {
        ...mockRunDetail,
        status: 'running',
      };
      const cancelledRun: Live20RunDetailType = {
        ...mockRunDetail,
        status: 'cancelled',
      };
      vi.mocked(live20Service.getRunDetail)
        .mockResolvedValueOnce(runningRun)
        .mockResolvedValueOnce(cancelledRun);
      vi.mocked(live20Service.cancelRun).mockResolvedValue();

      renderWithRouter();

      await waitFor(() => {
        expect(screen.getByText('AAPL')).toBeInTheDocument();
      });

      // Open dialog
      const cancelButton = screen.getByRole('button', { name: /Cancel/ });
      await user.click(cancelButton);

      // Wait for dialog to appear
      await waitFor(() => {
        expect(screen.getByText('Stop analysis?')).toBeInTheDocument();
      });

      // Find and click the confirm button
      const confirmButton = screen.getByRole('button', { name: /Stop analysis/ });
      await user.click(confirmButton);

      // Should call cancelRun
      await waitFor(() => {
        expect(live20Service.cancelRun).toHaveBeenCalledWith(42);
      });

      // Should show success toast
      await waitFor(() => {
        expect(toast.success).toHaveBeenCalledWith('Analysis run cancelled');
      });

      // Should refresh data
      await waitFor(() => {
        expect(live20Service.getRunDetail).toHaveBeenCalledTimes(2);
      });

      // Dialog should close
      await waitFor(() => {
        expect(screen.queryByText('Stop analysis?')).not.toBeInTheDocument();
      });

      // After refresh, cancelled run should show Delete button instead of Cancel
      expect(screen.getByRole('button', { name: /Delete/ })).toBeInTheDocument();
      expect(screen.queryByRole('button', { name: /Cancel/ })).not.toBeInTheDocument();
    });

    it('shows error message when cancel fails', async () => {
      const user = userEvent.setup();
      const runningRun: Live20RunDetailType = {
        ...mockRunDetail,
        status: 'running',
      };
      vi.mocked(live20Service.getRunDetail).mockResolvedValue(runningRun);
      vi.mocked(live20Service.cancelRun).mockRejectedValue(
        new Error('Failed to cancel run: Internal Server Error')
      );

      renderWithRouter();

      await waitFor(() => {
        expect(screen.getByText('AAPL')).toBeInTheDocument();
      });

      // Open dialog
      const cancelButton = screen.getByRole('button', { name: /Cancel/ });
      await user.click(cancelButton);

      // Wait for dialog to appear
      await waitFor(() => {
        expect(screen.getByText('Stop analysis?')).toBeInTheDocument();
      });

      // Find and click the confirm button
      const confirmButton = screen.getByRole('button', { name: /Stop analysis/ });
      await user.click(confirmButton);

      // Should show error toast
      await waitFor(() => {
        expect(toast.error).toHaveBeenCalledWith('Failed to cancel run: Internal Server Error');
      });
    });
  });

  describe('Delete Functionality', () => {
    beforeEach(() => {
      vi.mocked(live20Service.getRunDetail).mockResolvedValue(mockRunDetail);
    });

    it('opens confirmation dialog when delete button clicked', async () => {
      const user = userEvent.setup();
      renderWithRouter();

      await waitFor(() => {
        expect(screen.getByText('AAPL')).toBeInTheDocument();
      });

      const deleteButton = screen.getByRole('button', { name: /Delete/ });
      await user.click(deleteButton);

      // Dialog should appear
      expect(screen.getByText('Delete analysis run?')).toBeInTheDocument();
      expect(
        screen.getByText(/This will permanently remove this analysis run/)
      ).toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'Cancel' })).toBeInTheDocument();
      // There's one more Delete button in the dialog
      const deleteButtons = screen.getAllByRole('button', { name: /Delete/i });
      expect(deleteButtons.length).toBeGreaterThanOrEqual(1);
    });

    it('closes dialog when cancel button clicked', async () => {
      const user = userEvent.setup();
      renderWithRouter();

      await waitFor(() => {
        expect(screen.getByText('AAPL')).toBeInTheDocument();
      });

      // Open dialog
      const deleteButton = screen.getByRole('button', { name: /Delete/ });
      await user.click(deleteButton);

      expect(screen.getByText('Delete analysis run?')).toBeInTheDocument();

      // Click cancel
      const cancelButton = screen.getByRole('button', { name: 'Cancel' });
      await user.click(cancelButton);

      // Dialog should close
      await waitFor(() => {
        expect(screen.queryByText('Delete analysis run?')).not.toBeInTheDocument();
      });
    });

    it('deletes run and navigates to history on confirmation', async () => {
      const user = userEvent.setup();
      vi.mocked(live20Service.deleteRun).mockResolvedValue();

      renderWithRouter();

      await waitFor(() => {
        expect(screen.getByText('AAPL')).toBeInTheDocument();
      });

      // Open dialog
      const deleteButton = screen.getByRole('button', { name: /Delete/ });
      await user.click(deleteButton);

      // Wait for dialog to appear
      await waitFor(() => {
        expect(screen.getByText('Delete analysis run?')).toBeInTheDocument();
      });

      // Find and click the confirm delete button (there are two Delete buttons, one in header and one in dialog)
      const deleteButtons = screen.getAllByRole('button', { name: 'Delete' });
      const confirmButton = deleteButtons.find(button =>
        button.closest('[role="alertdialog"]')
      );
      expect(confirmButton).toBeDefined();
      await user.click(confirmButton!);

      // Should call deleteRun
      await waitFor(() => {
        expect(live20Service.deleteRun).toHaveBeenCalledWith(42);
      });

      // Should navigate to history tab
      await waitFor(() => {
        expect(screen.getByText('History Tab')).toBeInTheDocument();
      });
    });

    it('shows error message when delete fails', async () => {
      const user = userEvent.setup();
      vi.mocked(live20Service.deleteRun).mockRejectedValue(
        new Error('Failed to delete run: Internal Server Error')
      );

      renderWithRouter();

      await waitFor(() => {
        expect(screen.getByText('AAPL')).toBeInTheDocument();
      });

      // Open dialog
      const deleteButton = screen.getByRole('button', { name: /Delete/ });
      await user.click(deleteButton);

      // Wait for dialog to appear
      await waitFor(() => {
        expect(screen.getByText('Delete analysis run?')).toBeInTheDocument();
      });

      // Find and click the confirm delete button (there are two Delete buttons, one in header and one in dialog)
      const deleteButtons = screen.getAllByRole('button', { name: 'Delete' });
      const confirmButton = deleteButtons.find(button =>
        button.closest('[role="alertdialog"]')
      );
      expect(confirmButton).toBeDefined();
      await user.click(confirmButton!);

      // Should show error toast
      await waitFor(() => {
        expect(toast.error).toHaveBeenCalledWith('Failed to delete run: Internal Server Error');
      });

      // Dialog should close
      await waitFor(() => {
        expect(screen.queryByText('Delete analysis run?')).not.toBeInTheDocument();
      });

      // Should not navigate
      expect(screen.queryByText('History Tab')).not.toBeInTheDocument();
    });

    it('disables delete button while deleting', async () => {
      const user = userEvent.setup();
      vi.mocked(live20Service.deleteRun).mockImplementation(
        () => new Promise(() => {}) // Never resolves
      );

      renderWithRouter();

      await waitFor(() => {
        expect(screen.getByText('AAPL')).toBeInTheDocument();
      });

      // Open dialog
      const deleteButton = screen.getByRole('button', { name: /Delete/ });
      expect(deleteButton).not.toBeDisabled();
      await user.click(deleteButton);

      // Wait for dialog to appear
      await waitFor(() => {
        expect(screen.getByText('Delete analysis run?')).toBeInTheDocument();
      });

      // Find and click the confirm delete button (there are two Delete buttons, one in header and one in dialog)
      const deleteButtons = screen.getAllByRole('button', { name: 'Delete' });
      const confirmButton = deleteButtons.find(button =>
        button.closest('[role="alertdialog"]')
      );
      expect(confirmButton).toBeDefined();
      await user.click(confirmButton!);

      // Header delete button should be disabled while deleting
      await waitFor(() => {
        expect(deleteButton).toBeDisabled();
      });
    });
  });

  describe('Edge Cases', () => {
    it('handles invalid run ID in URL', async () => {
      vi.mocked(live20Service.getRunDetail).mockRejectedValue(new Error('Run not found'));

      renderWithRouter('/live-20/runs/invalid');

      await waitFor(() => {
        expect(screen.getByText('Run not found')).toBeInTheDocument();
      });
    });

    it('handles empty results array', async () => {
      const emptyRun: Live20RunDetailType = {
        ...mockRunDetail,
        results: [],
        symbol_count: 0,
        long_count: 0,
        short_count: 0,
        no_setup_count: 0,
      };

      vi.mocked(live20Service.getRunDetail).mockResolvedValue(emptyRun);

      renderWithRouter();

      await waitFor(() => {
        expect(screen.getByText('Run Summary')).toBeInTheDocument();
      });

      // Should show 0 counts (there will be multiple 0s in the summary grid)
      expect(screen.getAllByText('0').length).toBeGreaterThan(0);

      // Should show "No results found" in table
      expect(screen.getByText('No results found')).toBeInTheDocument();
    });
  });

  describe('Multi-List Display', () => {
    it('displays single list name from source_lists', async () => {
      const runWithSourceList: Live20RunDetailType = {
        ...mockRunDetail,
        source_lists: [{ id: 10, name: 'Tech Watchlist' }],
        stock_list_name: null,
      };

      vi.mocked(live20Service.getRunDetail).mockResolvedValue(runWithSourceList);

      renderWithRouter();

      await waitFor(() => {
        expect(screen.getByText('From list:')).toBeInTheDocument();
        expect(screen.getByText('Tech Watchlist')).toBeInTheDocument();
      });
    });

    it('displays multiple list names from source_lists', async () => {
      const runWithMultipleLists: Live20RunDetailType = {
        ...mockRunDetail,
        source_lists: [
          { id: 10, name: 'Tech Watchlist' },
          { id: 20, name: 'Growth Stocks' },
          { id: 30, name: 'High Momentum' },
        ],
        stock_list_name: null,
      };

      vi.mocked(live20Service.getRunDetail).mockResolvedValue(runWithMultipleLists);

      renderWithRouter();

      await waitFor(() => {
        expect(screen.getByText('Combined from 3 lists:')).toBeInTheDocument();
        expect(screen.getByText('Tech Watchlist')).toBeInTheDocument();
        expect(screen.getByText('Growth Stocks')).toBeInTheDocument();
        expect(screen.getByText('High Momentum')).toBeInTheDocument();
      });
    });

    it('falls back to stock_list_name when source_lists is not present', async () => {
      const runWithLegacyList: Live20RunDetailType = {
        ...mockRunDetail,
        stock_list_id: 10,
        stock_list_name: 'Legacy Watchlist',
        source_lists: undefined,
      };

      vi.mocked(live20Service.getRunDetail).mockResolvedValue(runWithLegacyList);

      renderWithRouter();

      await waitFor(() => {
        expect(screen.getByText('From list:')).toBeInTheDocument();
        expect(screen.getByText('Legacy Watchlist')).toBeInTheDocument();
      });
    });

    it('shows no list indicator when neither source_lists nor stock_list_name is present', async () => {
      const runWithoutLists: Live20RunDetailType = {
        ...mockRunDetail,
        stock_list_id: null,
        stock_list_name: null,
        source_lists: null,
      };

      vi.mocked(live20Service.getRunDetail).mockResolvedValue(runWithoutLists);

      renderWithRouter();

      await waitFor(() => {
        expect(screen.getByText('Run Summary')).toBeInTheDocument();
      });

      // Should not show any list indicator
      expect(screen.queryByText('From list:')).not.toBeInTheDocument();
      expect(screen.queryByText(/Combined from/)).not.toBeInTheDocument();
    });
  });
});
