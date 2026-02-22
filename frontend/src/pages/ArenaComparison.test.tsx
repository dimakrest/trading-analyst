/**
 * Tests for ArenaComparison page.
 *
 * Covers:
 * - Shows loading spinner initially
 * - Renders progress cards for each simulation (running state)
 * - Shows summary table when at least one simulation is completed
 * - Shows "not found" error state when API returns 404
 * - Shows error message when all simulations failed/cancelled
 * - Header includes "Strategy Comparison" title and back button
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { fireEvent } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { ArenaComparison } from './ArenaComparison';
import type { ComparisonResponse } from '../types/arena';

const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

vi.mock('../hooks/useComparisonPolling', () => ({
  useComparisonPolling: vi.fn(),
}));

// Also mock the chart and table to avoid heavyweight rendering
vi.mock('../components/arena/ArenaComparisonChart', () => ({
  ArenaComparisonChart: () => <div data-testid="comparison-chart-mock">Chart</div>,
}));

vi.mock('../components/arena/ArenaComparisonTable', () => ({
  ArenaComparisonTable: () => <div data-testid="comparison-table-mock">Table</div>,
}));

import { useComparisonPolling } from '../hooks/useComparisonPolling';

const mockUseComparisonPolling = useComparisonPolling as ReturnType<typeof vi.fn>;

const makeSim = (id: number, status: string, strategy: string) => ({
  id,
  name: null,
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
  portfolio_strategy: strategy,
  max_per_sector: null,
  max_open_positions: null,
  group_id: 'test-group',
  status,
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
});

const renderPage = () =>
  render(
    <MemoryRouter initialEntries={['/arena/compare/test-group']}>
      <Routes>
        <Route path="/arena/compare/:groupId" element={<ArenaComparison />} />
      </Routes>
    </MemoryRouter>,
  );

describe('ArenaComparison', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('loading state', () => {
    it('shows a loading spinner when data is null and no error', () => {
      mockUseComparisonPolling.mockReturnValue({
        data: null,
        isPolling: true,
        error: null,
      });

      const { container } = renderPage();

      // Loader2 renders an SVG with the animate-spin class
      const spinner = container.querySelector('.animate-spin');
      expect(spinner).toBeInTheDocument();
    });
  });

  describe('error state (no data)', () => {
    it('shows error message and back button when there is no data and an error', () => {
      mockUseComparisonPolling.mockReturnValue({
        data: null,
        isPolling: false,
        error: 'Failed to load comparison',
      });

      renderPage();

      expect(screen.getByText(/Comparison not found or failed to load/i)).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /back to arena/i })).toBeInTheDocument();
    });

    it('navigates to /arena when Back to Arena is clicked in error state', () => {
      mockUseComparisonPolling.mockReturnValue({
        data: null,
        isPolling: false,
        error: 'Failed to load comparison',
      });

      renderPage();

      fireEvent.click(screen.getByRole('button', { name: /back to arena/i }));
      expect(mockNavigate).toHaveBeenCalledWith('/arena');
    });
  });

  describe('progress cards', () => {
    it('renders a progress card for each simulation when running', () => {
      const data: ComparisonResponse = {
        group_id: 'test-group',
        simulations: [
          makeSim(1, 'running', 'none') as never,
          makeSim(2, 'running', 'score_sector_low_atr') as never,
        ],
      };

      mockUseComparisonPolling.mockReturnValue({ data, isPolling: true, error: null });

      renderPage();

      expect(screen.getByTestId('progress-cards')).toBeInTheDocument();
      expect(screen.getByTestId('progress-card-1')).toBeInTheDocument();
      expect(screen.getByTestId('progress-card-2')).toBeInTheDocument();
    });

    it('shows strategy names and statuses in progress cards', () => {
      const data: ComparisonResponse = {
        group_id: 'test-group',
        simulations: [
          makeSim(1, 'running', 'none') as never,
          makeSim(2, 'pending', 'high_atr') as never,
        ],
      };

      mockUseComparisonPolling.mockReturnValue({ data, isPolling: true, error: null });

      renderPage();

      expect(screen.getByText('none')).toBeInTheDocument();
      expect(screen.getByText('high_atr')).toBeInTheDocument();
      // Status badges
      expect(screen.getAllByText('running').length).toBeGreaterThan(0);
      expect(screen.getAllByText('pending').length).toBeGreaterThan(0);
    });
  });

  describe('summary table visibility', () => {
    it('does not show summary table when no simulation is completed', () => {
      const data: ComparisonResponse = {
        group_id: 'test-group',
        simulations: [
          makeSim(1, 'running', 'none') as never,
          makeSim(2, 'running', 'high_atr') as never,
        ],
      };

      mockUseComparisonPolling.mockReturnValue({ data, isPolling: true, error: null });

      renderPage();

      expect(screen.queryByTestId('comparison-table-mock')).not.toBeInTheDocument();
    });

    it('shows summary table when at least one simulation is completed', () => {
      const data: ComparisonResponse = {
        group_id: 'test-group',
        simulations: [
          makeSim(1, 'completed', 'none') as never,
          makeSim(2, 'running', 'high_atr') as never,
        ],
      };

      mockUseComparisonPolling.mockReturnValue({ data, isPolling: true, error: null });

      renderPage();

      expect(screen.getByTestId('comparison-table-mock')).toBeInTheDocument();
    });
  });

  describe('equity chart visibility', () => {
    it('does not show equity chart when not all simulations are completed', () => {
      const data: ComparisonResponse = {
        group_id: 'test-group',
        simulations: [
          makeSim(1, 'completed', 'none') as never,
          makeSim(2, 'running', 'high_atr') as never,
        ],
      };

      mockUseComparisonPolling.mockReturnValue({ data, isPolling: false, error: null });

      renderPage();

      expect(screen.queryByTestId('comparison-chart-mock')).not.toBeInTheDocument();
    });

    it('shows equity chart when all simulations are completed', () => {
      const data: ComparisonResponse = {
        group_id: 'test-group',
        simulations: [
          makeSim(1, 'completed', 'none') as never,
          makeSim(2, 'completed', 'high_atr') as never,
        ],
      };

      mockUseComparisonPolling.mockReturnValue({ data, isPolling: false, error: null });

      renderPage();

      expect(screen.getByTestId('comparison-chart-mock')).toBeInTheDocument();
    });
  });

  describe('all failed edge case', () => {
    it('shows error message when all simulations failed or cancelled', () => {
      const data: ComparisonResponse = {
        group_id: 'test-group',
        simulations: [
          makeSim(1, 'failed', 'none') as never,
          makeSim(2, 'cancelled', 'high_atr') as never,
        ],
      };

      mockUseComparisonPolling.mockReturnValue({ data, isPolling: false, error: null });

      renderPage();

      expect(
        screen.getByText(/all simulations in this comparison failed or were cancelled/i),
      ).toBeInTheDocument();
    });
  });

  describe('partial completion warning', () => {
    it('shows warning when some simulations completed and some cancelled', () => {
      const data: ComparisonResponse = {
        group_id: 'test-group',
        simulations: [
          makeSim(1, 'completed', 'none') as never,
          makeSim(2, 'cancelled', 'high_atr') as never,
        ],
      };

      mockUseComparisonPolling.mockReturnValue({ data, isPolling: false, error: null });

      renderPage();

      expect(
        screen.getByText(/some simulations were cancelled or failed/i),
      ).toBeInTheDocument();
    });
  });

  describe('header', () => {
    it('renders the Strategy Comparison heading', () => {
      const data: ComparisonResponse = {
        group_id: 'test-group',
        simulations: [makeSim(1, 'running', 'none') as never],
      };

      mockUseComparisonPolling.mockReturnValue({ data, isPolling: true, error: null });

      renderPage();

      expect(screen.getByRole('heading', { name: /strategy comparison/i })).toBeInTheDocument();
    });

    it('navigates to /arena when the Back to Arena button is clicked', async () => {
      const data: ComparisonResponse = {
        group_id: 'test-group',
        simulations: [makeSim(1, 'running', 'none') as never],
      };

      mockUseComparisonPolling.mockReturnValue({ data, isPolling: true, error: null });

      renderPage();

      // The Back to Arena button in the header (not the error state one)
      const backButton = screen.getByRole('button', { name: /back to arena/i });
      fireEvent.click(backButton);

      await waitFor(() => {
        expect(mockNavigate).toHaveBeenCalledWith('/arena');
      });
    });

    it('shows polling spinner when isPolling is true', () => {
      const data: ComparisonResponse = {
        group_id: 'test-group',
        simulations: [makeSim(1, 'running', 'none') as never],
      };

      mockUseComparisonPolling.mockReturnValue({ data, isPolling: true, error: null });

      renderPage();

      expect(screen.getByLabelText('Polling for updates')).toBeInTheDocument();
    });
  });
});
