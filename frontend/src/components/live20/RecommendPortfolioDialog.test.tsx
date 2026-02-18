import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { RecommendPortfolioDialog } from './RecommendPortfolioDialog';
import * as live20Service from '../../services/live20Service';
import type { PortfolioRecommendResponse } from '../../types/live20';

// Mock the live20Service module
vi.mock('../../services/live20Service');

const mockRecommendPortfolio = vi.mocked(live20Service.recommendPortfolio);

/** Helper: render the dialog in the open state */
const renderDialog = (runId = 42) =>
  render(
    <RecommendPortfolioDialog
      open={true}
      onOpenChange={vi.fn()}
      runId={runId}
    />
  );

/** A full response fixture with 3 items */
const mockResponse: PortfolioRecommendResponse = {
  strategy: 'score_sector_low_atr',
  strategy_description: 'Rank by score, prefer lowest ATR%',
  items: [
    { symbol: 'AAPL', score: 85, direction: 'LONG', sector: 'Technology', atr_pct: 2.1 },
    { symbol: 'MSFT', score: 80, direction: 'LONG', sector: 'Technology', atr_pct: 2.5 },
    { symbol: 'XOM', score: 75, direction: 'SHORT', sector: 'Energy', atr_pct: 3.2 },
  ],
  total_qualifying: 10,
  total_selected: 3,
};

/** A response with no items (all filtered by sector cap) */
const emptyResponse: PortfolioRecommendResponse = {
  strategy: 'score_sector_low_atr',
  strategy_description: 'Rank by score, prefer lowest ATR%',
  items: [],
  total_qualifying: 0,
  total_selected: 0,
};

describe('RecommendPortfolioDialog', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('Rendering', () => {
    it('renders the dialog title and description', () => {
      renderDialog();

      expect(screen.getByText('Recommend Portfolio')).toBeInTheDocument();
      expect(
        screen.getByText(/read-only recommendation/i)
      ).toBeInTheDocument();
    });

    it('renders the "Get Recommendations" button', () => {
      renderDialog();

      expect(
        screen.getByRole('button', { name: /get recommendations/i })
      ).toBeInTheDocument();
    });

    it('renders with default min score of 60', () => {
      renderDialog();

      // The Select shows the current value
      expect(screen.getByText('60')).toBeInTheDocument();
    });

    it('renders all four strategy options in the select', async () => {
      const user = userEvent.setup();
      renderDialog();

      // Open the strategy dropdown
      const strategyTriggers = screen.getAllByRole('combobox');
      // Strategy is the second combobox (after min score)
      const strategySelect = strategyTriggers[1];
      await user.click(strategySelect);

      expect(screen.getByText('None (symbol order)')).toBeInTheDocument();
      expect(screen.getAllByText('Score + Low ATR').length).toBeGreaterThanOrEqual(1);
      expect(screen.getByText('Score + High ATR')).toBeInTheDocument();
      expect(screen.getByText('Score + Moderate ATR')).toBeInTheDocument();
    });

    it('renders max per sector input with default value of 2', () => {
      renderDialog();

      const maxPerSectorInput = screen.getByLabelText(/max per sector/i);
      expect(maxPerSectorInput).toHaveValue(2);
    });

    it('renders max positions input as empty (unlimited)', () => {
      renderDialog();

      const maxPositionsInput = screen.getByLabelText(/max positions/i);
      expect(maxPositionsInput).toHaveValue(null);
    });

    it('does not show results section initially', () => {
      renderDialog();

      expect(
        screen.queryByTestId('recommendations-result')
      ).not.toBeInTheDocument();
    });
  });

  describe('API call', () => {
    it('calls recommendPortfolio with default params when button clicked', async () => {
      const user = userEvent.setup();
      mockRecommendPortfolio.mockResolvedValue(mockResponse);

      renderDialog(42);

      await user.click(
        screen.getByRole('button', { name: /get recommendations/i })
      );

      expect(mockRecommendPortfolio).toHaveBeenCalledWith(42, {
        min_score: 60,
        strategy: 'score_sector_low_atr',
        max_per_sector: 2,
        max_positions: null,
      });
    });

    it('passes null for max_positions when input is empty', async () => {
      const user = userEvent.setup();
      mockRecommendPortfolio.mockResolvedValue(mockResponse);

      renderDialog(7);

      await user.click(
        screen.getByRole('button', { name: /get recommendations/i })
      );

      const callArgs = mockRecommendPortfolio.mock.calls[0][1];
      expect(callArgs.max_positions).toBeNull();
    });

    it('passes max_positions as a number when entered', async () => {
      const user = userEvent.setup();
      mockRecommendPortfolio.mockResolvedValue(mockResponse);

      renderDialog();

      const maxPositionsInput = screen.getByLabelText(/max positions/i);
      await user.type(maxPositionsInput, '5');

      await user.click(
        screen.getByRole('button', { name: /get recommendations/i })
      );

      const callArgs = mockRecommendPortfolio.mock.calls[0][1];
      expect(callArgs.max_positions).toBe(5);
    });

    it('calls recommendPortfolio once per button click', async () => {
      const user = userEvent.setup();
      mockRecommendPortfolio.mockResolvedValue(mockResponse);

      renderDialog();

      await user.click(
        screen.getByRole('button', { name: /get recommendations/i })
      );

      expect(mockRecommendPortfolio).toHaveBeenCalledTimes(1);
    });
  });

  describe('Loading state', () => {
    it('shows loading indicator while API call is in progress', async () => {
      const user = userEvent.setup();
      // Never resolves during this test
      mockRecommendPortfolio.mockReturnValue(new Promise(() => {}));

      renderDialog();

      await user.click(
        screen.getByRole('button', { name: /get recommendations/i })
      );

      expect(
        screen.getByText(/fetching recommendations/i)
      ).toBeInTheDocument();
    });

    it('disables the button while loading', async () => {
      const user = userEvent.setup();
      mockRecommendPortfolio.mockReturnValue(new Promise(() => {}));

      renderDialog();

      await user.click(
        screen.getByRole('button', { name: /get recommendations/i })
      );

      // The button text changes; find it by partial match
      const loadingButton = screen.getByRole('button', {
        name: /fetching recommendations/i,
      });
      expect(loadingButton).toBeDisabled();
    });
  });

  describe('Results display', () => {
    it('renders the results table when API returns data', async () => {
      const user = userEvent.setup();
      mockRecommendPortfolio.mockResolvedValue(mockResponse);

      renderDialog();

      await user.click(
        screen.getByRole('button', { name: /get recommendations/i })
      );

      await waitFor(() => {
        expect(screen.getByTestId('recommendations-result')).toBeInTheDocument();
      });

      // All three symbols should be visible
      expect(screen.getByText('AAPL')).toBeInTheDocument();
      expect(screen.getByText('MSFT')).toBeInTheDocument();
      expect(screen.getByText('XOM')).toBeInTheDocument();
    });

    it('renders the qualifying/selected summary correctly', async () => {
      const user = userEvent.setup();
      mockRecommendPortfolio.mockResolvedValue(mockResponse);

      renderDialog();

      await user.click(
        screen.getByRole('button', { name: /get recommendations/i })
      );

      await waitFor(() => {
        expect(screen.getByText('qualifying signals')).toBeInTheDocument();
        expect(screen.getByText('selected')).toBeInTheDocument();
        // total_qualifying = 10 (unique in the page)
        expect(screen.getByText('10')).toBeInTheDocument();
        // total_selected = 3 may appear multiple times; just verify summary text
        expect(screen.getAllByText('3').length).toBeGreaterThanOrEqual(1);
      });
    });

    it('renders direction, score, sector, and ATR% columns for each item', async () => {
      const user = userEvent.setup();
      mockRecommendPortfolio.mockResolvedValue(mockResponse);

      renderDialog();

      await user.click(
        screen.getByRole('button', { name: /get recommendations/i })
      );

      await waitFor(() => {
        // Directions
        expect(screen.getAllByText('LONG')).toHaveLength(2);
        expect(screen.getByText('SHORT')).toBeInTheDocument();
        // Scores
        expect(screen.getByText('85')).toBeInTheDocument();
        expect(screen.getByText('80')).toBeInTheDocument();
        expect(screen.getByText('75')).toBeInTheDocument();
        // Sectors
        expect(screen.getAllByText('Technology')).toHaveLength(2);
        expect(screen.getByText('Energy')).toBeInTheDocument();
        // ATR% values
        expect(screen.getByText('2.1%')).toBeInTheDocument();
        expect(screen.getByText('2.5%')).toBeInTheDocument();
        expect(screen.getByText('3.2%')).toBeInTheDocument();
      });
    });

    it('renders row numbers starting from 1', async () => {
      const user = userEvent.setup();
      mockRecommendPortfolio.mockResolvedValue(mockResponse);

      renderDialog();

      await user.click(
        screen.getByRole('button', { name: /get recommendations/i })
      );

      await waitFor(() => {
        // Row numbers appear in table cells; use getAllBy to handle any duplicates
        expect(screen.getAllByText('1').length).toBeGreaterThanOrEqual(1);
        expect(screen.getAllByText('2').length).toBeGreaterThanOrEqual(1);
        // "3" appears both as a row number and as total_selected — both are fine
        expect(screen.getAllByText('3').length).toBeGreaterThanOrEqual(1);
      });
    });

    it('renders "—" for null direction, null sector, and null ATR%', async () => {
      const user = userEvent.setup();
      const responseWithNulls: PortfolioRecommendResponse = {
        ...mockResponse,
        items: [
          { symbol: 'UNKN', score: 70, direction: null, sector: null, atr_pct: null },
        ],
        total_qualifying: 1,
        total_selected: 1,
      };
      mockRecommendPortfolio.mockResolvedValue(responseWithNulls);

      renderDialog();

      await user.click(
        screen.getByRole('button', { name: /get recommendations/i })
      );

      await waitFor(() => {
        // Both null sector and null ATR should display "—"
        const dashes = screen.getAllByText('—');
        expect(dashes.length).toBeGreaterThanOrEqual(2);
      });
    });
  });

  describe('Empty state', () => {
    it('shows "No qualifying signals" when items array is empty', async () => {
      const user = userEvent.setup();
      mockRecommendPortfolio.mockResolvedValue(emptyResponse);

      renderDialog();

      await user.click(
        screen.getByRole('button', { name: /get recommendations/i })
      );

      await waitFor(() => {
        expect(
          screen.getByText(/no qualifying signals/i)
        ).toBeInTheDocument();
      });
    });

    it('shows hint to lower the min score threshold on empty state', async () => {
      const user = userEvent.setup();
      mockRecommendPortfolio.mockResolvedValue(emptyResponse);

      renderDialog();

      await user.click(
        screen.getByRole('button', { name: /get recommendations/i })
      );

      await waitFor(() => {
        expect(
          screen.getByText(/try lowering the minimum score threshold/i)
        ).toBeInTheDocument();
      });
    });

    it('does not render a table when items array is empty', async () => {
      const user = userEvent.setup();
      mockRecommendPortfolio.mockResolvedValue(emptyResponse);

      renderDialog();

      await user.click(
        screen.getByRole('button', { name: /get recommendations/i })
      );

      await waitFor(() => {
        expect(screen.queryByRole('table')).not.toBeInTheDocument();
      });
    });
  });

  describe('Error handling', () => {
    it('shows error message when API call fails', async () => {
      const user = userEvent.setup();
      mockRecommendPortfolio.mockRejectedValue(
        new Error('Network request failed')
      );

      renderDialog();

      await user.click(
        screen.getByRole('button', { name: /get recommendations/i })
      );

      await waitFor(() => {
        expect(
          screen.getByText(/network request failed/i)
        ).toBeInTheDocument();
      });
    });

    it('shows generic error message for non-Error exceptions', async () => {
      const user = userEvent.setup();
      mockRecommendPortfolio.mockRejectedValue('some string error');

      renderDialog();

      await user.click(
        screen.getByRole('button', { name: /get recommendations/i })
      );

      await waitFor(() => {
        expect(
          screen.getByText(/failed to fetch recommendations/i)
        ).toBeInTheDocument();
      });
    });

    it('clears previous results on a new API call', async () => {
      const user = userEvent.setup();
      // First call succeeds
      mockRecommendPortfolio.mockResolvedValueOnce(mockResponse);
      // Second call fails
      mockRecommendPortfolio.mockRejectedValueOnce(
        new Error('Server error')
      );

      renderDialog();

      // First call
      await user.click(
        screen.getByRole('button', { name: /get recommendations/i })
      );
      await waitFor(() => {
        expect(screen.getByText('AAPL')).toBeInTheDocument();
      });

      // Second call
      await user.click(
        screen.getByRole('button', { name: /get recommendations/i })
      );
      await waitFor(() => {
        expect(screen.getByText(/server error/i)).toBeInTheDocument();
        // Previous results should be gone
        expect(screen.queryByText('AAPL')).not.toBeInTheDocument();
      });
    });

    it('re-enables the button after an error', async () => {
      const user = userEvent.setup();
      mockRecommendPortfolio.mockRejectedValue(new Error('Timeout'));

      renderDialog();

      await user.click(
        screen.getByRole('button', { name: /get recommendations/i })
      );

      await waitFor(() => {
        const button = screen.getByRole('button', {
          name: /get recommendations/i,
        });
        expect(button).not.toBeDisabled();
      });
    });
  });
});
