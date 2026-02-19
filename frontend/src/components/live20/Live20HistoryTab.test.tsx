import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { userEvent } from '@testing-library/user-event';
import { BrowserRouter } from 'react-router-dom';
import { Live20HistoryTab } from './Live20HistoryTab';
import * as live20Service from '../../services/live20Service';
import type { Live20RunListResponse } from '../../types/live20';

vi.mock('../../services/live20Service');

const mockListRuns = vi.mocked(live20Service.listRuns);

// Mock navigate
const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

// Helper to render component with router
function renderWithRouter(component: React.ReactElement) {
  return render(<BrowserRouter>{component}</BrowserRouter>);
}

// Mock data
const mockRuns: Live20RunListResponse = {
  items: [
    {
      id: 1,
      created_at: '2025-12-24T12:45:00Z',
      status: 'completed',
      symbol_count: 45,
      processed_count: 45,
      long_count: 12,
      no_setup_count: 25,
      stock_list_id: null,
      stock_list_name: null,
    },
    {
      id: 2,
      created_at: '2025-12-24T11:30:00Z',
      status: 'completed',
      symbol_count: 38,
      processed_count: 38,
      long_count: 9,
      no_setup_count: 18,
      stock_list_id: null,
      stock_list_name: null,
    },
  ],
  total: 2,
  has_more: false,
  limit: 20,
  offset: 0,
};

describe('Live20HistoryTab', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders loading state initially', () => {
    mockListRuns.mockImplementation(() => new Promise(() => {})); // Never resolves

    renderWithRouter(<Live20HistoryTab />);

    expect(screen.getByText('Loading runs...')).toBeInTheDocument();
  });

  it('renders run list with correct columns', async () => {
    mockListRuns.mockResolvedValue(mockRuns);

    renderWithRouter(<Live20HistoryTab />);

    await waitFor(() => {
      expect(screen.getByText('45')).toBeInTheDocument();
    });

    // Check column headers by role
    const columnHeaders = screen.getAllByRole('columnheader');
    expect(columnHeaders).toHaveLength(5); // Date, Symbols, Long, No Setup, and chevron column
    expect(columnHeaders[0]).toHaveTextContent(/date.*time/i);
    expect(columnHeaders[1]).toHaveTextContent(/symbols/i);
    expect(columnHeaders[2]).toHaveTextContent(/long/i);
    expect(columnHeaders[3]).toHaveTextContent(/no setup/i);

    // Check first run data
    expect(screen.getByText('45')).toBeInTheDocument(); // symbol_count
    expect(screen.getByText('12')).toBeInTheDocument(); // long_count
    expect(screen.getByText('25')).toBeInTheDocument(); // no_setup_count

    // Check second run data
    expect(screen.getByText('38')).toBeInTheDocument();
    expect(screen.getByText('9')).toBeInTheDocument();
    expect(screen.getByText('18')).toBeInTheDocument();
  });

  it('handles empty state', async () => {
    mockListRuns.mockResolvedValue({
      items: [],
      total: 0,
      has_more: false,
      limit: 20,
      offset: 0,
    });

    renderWithRouter(<Live20HistoryTab />);

    await waitFor(() => {
      expect(screen.getByText('No runs found')).toBeInTheDocument();
    });

    expect(screen.getByText('Try adjusting your filters or run a new analysis')).toBeInTheDocument();
  });

  it('handles error state', async () => {
    mockListRuns.mockRejectedValue(new Error('Network error'));

    renderWithRouter(<Live20HistoryTab />);

    await waitFor(() => {
      expect(screen.getByText(/network error/i)).toBeInTheDocument();
    });
  });

  it('changes date range filter', async () => {
    const user = userEvent.setup();
    mockListRuns.mockResolvedValue(mockRuns);

    renderWithRouter(<Live20HistoryTab />);

    await waitFor(() => {
      expect(screen.getByText('45')).toBeInTheDocument();
    });

    // Initially should call with last 7 days
    expect(mockListRuns).toHaveBeenCalledWith(
      expect.objectContaining({
        limit: 20,
        offset: 0,
        date_from: expect.any(String),
      })
    );

    const select = screen.getByRole('combobox');
    await user.selectOptions(select, 'all');

    await waitFor(() => {
      expect(mockListRuns).toHaveBeenCalledWith(
        expect.objectContaining({
          limit: 20,
          offset: 0,
          date_from: undefined,
        })
      );
    });
  });

  it('changes direction filter', async () => {
    const user = userEvent.setup();
    mockListRuns.mockResolvedValue(mockRuns);

    renderWithRouter(<Live20HistoryTab />);

    await waitFor(() => {
      expect(screen.getByText('45')).toBeInTheDocument();
    });

    // Find and click the Long button
    const longButton = screen.getByRole('button', { name: 'Long' });
    await user.click(longButton);

    await waitFor(() => {
      expect(mockListRuns).toHaveBeenCalledWith(
        expect.objectContaining({
          has_direction: 'LONG',
        })
      );
    });
  });

  it('searches by symbol with debounce', async () => {
    const user = userEvent.setup();
    mockListRuns.mockResolvedValue(mockRuns);

    renderWithRouter(<Live20HistoryTab />);

    await waitFor(() => {
      expect(screen.getByText('45')).toBeInTheDocument();
    });

    const searchInput = screen.getByPlaceholderText('Search by symbol...');
    await user.type(searchInput, 'AAPL');

    // Should not call immediately
    expect(mockListRuns).not.toHaveBeenCalledWith(
      expect.objectContaining({
        symbol: 'AAPL',
      })
    );

    // Should call after debounce (300ms)
    await waitFor(
      () => {
        expect(mockListRuns).toHaveBeenCalledWith(
          expect.objectContaining({
            symbol: 'AAPL',
          })
        );
      },
      { timeout: 500 }
    );
  });

  it('handles pagination - next page', async () => {
    const user = userEvent.setup();
    const manyRuns: Live20RunListResponse = {
      items: Array.from({ length: 20 }, (_, i) => ({
        id: i + 1,
        created_at: '2025-12-24T12:00:00Z',
        status: 'completed',
        symbol_count: 10,
        processed_count: 10,
        long_count: 3,
          no_setup_count: 5,
        stock_list_id: null,
        stock_list_name: null,
      })),
      total: 50,
      has_more: true,
      limit: 20,
      offset: 0,
    };

    mockListRuns.mockResolvedValue(manyRuns);

    renderWithRouter(<Live20HistoryTab />);

    await waitFor(() => {
      expect(screen.getByText('Showing 1-20 of 50 runs')).toBeInTheDocument();
    });

    const nextButton = screen.getByRole('button', { name: 'Next' });
    await user.click(nextButton);

    await waitFor(() => {
      expect(mockListRuns).toHaveBeenCalledWith(
        expect.objectContaining({
          offset: 20,
        })
      );
    });
  });

  it('handles pagination - previous page', async () => {
    const user = userEvent.setup();
    const page2Runs: Live20RunListResponse = {
      items: Array.from({ length: 20 }, (_, i) => ({
        id: i + 21,
        created_at: '2025-12-24T12:00:00Z',
        status: 'completed',
        symbol_count: 10,
        processed_count: 10,
        long_count: 3,
          no_setup_count: 5,
        stock_list_id: null,
        stock_list_name: null,
      })),
      total: 50,
      has_more: true,
      limit: 20,
      offset: 20,
    };

    mockListRuns.mockResolvedValue(page2Runs);

    renderWithRouter(<Live20HistoryTab />);

    // Wait for initial load
    await waitFor(() => {
      expect(mockListRuns).toHaveBeenCalled();
    });

    // Click next to go to page 2
    const nextButton = screen.getByRole('button', { name: 'Next' });
    await user.click(nextButton);

    await waitFor(() => {
      expect(screen.getByText('Showing 21-40 of 50 runs')).toBeInTheDocument();
    });

    // Click previous to go back to page 1
    const previousButton = screen.getByRole('button', { name: 'Previous' });
    await user.click(previousButton);

    await waitFor(() => {
      expect(mockListRuns).toHaveBeenCalledWith(
        expect.objectContaining({
          offset: 0,
        })
      );
    });
  });

  it('navigates to run detail on row click', async () => {
    const user = userEvent.setup();
    mockListRuns.mockResolvedValue(mockRuns);

    renderWithRouter(<Live20HistoryTab />);

    await waitFor(() => {
      expect(screen.getByText('45')).toBeInTheDocument();
    });

    // Click on the first row
    const firstRow = screen.getByText('45').closest('tr');
    expect(firstRow).toBeInTheDocument();

    if (firstRow) {
      await user.click(firstRow);

      expect(mockNavigate).toHaveBeenCalledWith('/live-20/runs/1');
    }
  });

  it('resets to page 1 when filters change', async () => {
    const user = userEvent.setup();

    // Initial load with many runs
    const manyRuns: Live20RunListResponse = {
      items: Array.from({ length: 20 }, (_, i) => ({
        id: i + 1,
        created_at: '2025-12-24T12:00:00Z',
        status: 'completed',
        symbol_count: 10,
        processed_count: 10,
        long_count: 3,
          no_setup_count: 5,
        stock_list_id: null,
        stock_list_name: null,
      })),
      total: 50,
      has_more: true,
      limit: 20,
      offset: 0,
    };
    mockListRuns.mockResolvedValue(manyRuns);

    renderWithRouter(<Live20HistoryTab />);

    await waitFor(() => {
      expect(screen.getByText('Showing 1-20 of 50 runs')).toBeInTheDocument();
    });

    // Clear previous calls
    mockListRuns.mockClear();

    // Go to page 2
    const page2Runs: Live20RunListResponse = {
      items: Array.from({ length: 20 }, (_, i) => ({
        id: i + 21,
        created_at: '2025-12-24T12:00:00Z',
        status: 'completed',
        symbol_count: 10,
        processed_count: 10,
        long_count: 3,
          no_setup_count: 5,
        stock_list_id: null,
        stock_list_name: null,
      })),
      total: 50,
      has_more: true,
      limit: 20,
      offset: 20,
    };
    mockListRuns.mockResolvedValue(page2Runs);

    const nextButton = screen.getByRole('button', { name: 'Next' });
    await user.click(nextButton);

    await waitFor(() => {
      expect(mockListRuns).toHaveBeenCalledWith(
        expect.objectContaining({
          offset: 20,
        })
      );
    });

    // Clear previous calls
    mockListRuns.mockClear();

    // Change filter - should reset to page 1
    mockListRuns.mockResolvedValue(manyRuns);
    const longButton = screen.getByRole('button', { name: 'Long' });
    await user.click(longButton);

    await waitFor(() => {
      expect(mockListRuns).toHaveBeenCalledWith(
        expect.objectContaining({
          offset: 0,
          has_direction: 'LONG',
        })
      );
    });
  });

  it('displays list badge when run has stock_list_name', async () => {
    const runsWithList: Live20RunListResponse = {
      items: [
        {
          id: 1,
          created_at: '2025-01-01T10:00:00Z',
          status: 'completed',
          symbol_count: 5,
          processed_count: 5,
          long_count: 2,
              no_setup_count: 2,
          stock_list_id: 10,
          stock_list_name: 'Tech Watchlist',
        },
      ],
      total: 1,
      has_more: false,
      limit: 20,
      offset: 0,
    };

    mockListRuns.mockResolvedValue(runsWithList);

    renderWithRouter(<Live20HistoryTab />);

    await waitFor(() => {
      expect(screen.getByText('Tech Watchlist')).toBeInTheDocument();
    });
  });

  it('does not display list badge when run has no stock_list_name', async () => {
    const runsWithoutList: Live20RunListResponse = {
      items: [
        {
          id: 1,
          created_at: '2025-01-01T10:00:00Z',
          status: 'completed',
          symbol_count: 5,
          processed_count: 5,
          long_count: 2,
              no_setup_count: 2,
          stock_list_id: null,
          stock_list_name: null,
        },
      ],
      total: 1,
      has_more: false,
      limit: 20,
      offset: 0,
    };

    mockListRuns.mockResolvedValue(runsWithoutList);

    renderWithRouter(<Live20HistoryTab />);

    await waitFor(() => {
      // Should show run data
      expect(screen.getByText('5')).toBeInTheDocument(); // symbol count
    });

    // No list name should be visible
    expect(screen.queryByText('Tech Watchlist')).not.toBeInTheDocument();
  });

  it('displays single list badge when run has source_lists with one item', async () => {
    const runsWithSourceList: Live20RunListResponse = {
      items: [
        {
          id: 1,
          created_at: '2025-01-01T10:00:00Z',
          status: 'completed',
          symbol_count: 5,
          processed_count: 5,
          long_count: 2,
              no_setup_count: 2,
          stock_list_id: null,
          stock_list_name: null,
          source_lists: [{ id: 10, name: 'Tech Watchlist' }],
        },
      ],
      total: 1,
      has_more: false,
      limit: 20,
      offset: 0,
    };

    mockListRuns.mockResolvedValue(runsWithSourceList);

    renderWithRouter(<Live20HistoryTab />);

    await waitFor(() => {
      expect(screen.getByText('Tech Watchlist')).toBeInTheDocument();
    });
  });

  it('displays "X lists combined" badge when run has multiple source_lists', async () => {
    const runsWithMultipleLists: Live20RunListResponse = {
      items: [
        {
          id: 1,
          created_at: '2025-01-01T10:00:00Z',
          status: 'completed',
          symbol_count: 15,
          processed_count: 15,
          long_count: 5,
              no_setup_count: 7,
          stock_list_id: null,
          stock_list_name: null,
          source_lists: [
            { id: 10, name: 'Tech Watchlist' },
            { id: 20, name: 'Growth Stocks' },
            { id: 30, name: 'High Momentum' },
          ],
        },
      ],
      total: 1,
      has_more: false,
      limit: 20,
      offset: 0,
    };

    mockListRuns.mockResolvedValue(runsWithMultipleLists);

    renderWithRouter(<Live20HistoryTab />);

    await waitFor(() => {
      expect(screen.getByText('3 lists combined')).toBeInTheDocument();
    });
  });

  it('shows tooltip with all list names for multiple source_lists', async () => {
    const runsWithMultipleLists: Live20RunListResponse = {
      items: [
        {
          id: 1,
          created_at: '2025-01-01T10:00:00Z',
          status: 'completed',
          symbol_count: 15,
          processed_count: 15,
          long_count: 5,
              no_setup_count: 7,
          stock_list_id: null,
          stock_list_name: null,
          source_lists: [
            { id: 10, name: 'Tech Watchlist' },
            { id: 20, name: 'Growth Stocks' },
          ],
        },
      ],
      total: 1,
      has_more: false,
      limit: 20,
      offset: 0,
    };

    mockListRuns.mockResolvedValue(runsWithMultipleLists);

    renderWithRouter(<Live20HistoryTab />);

    await waitFor(() => {
      const badge = screen.getByText('2 lists combined');
      expect(badge).toBeInTheDocument();
      expect(badge).toHaveAttribute('title', 'Tech Watchlist, Growth Stocks');
    });
  });

  it('falls back to stock_list_name when source_lists is not present', async () => {
    const runsWithLegacyList: Live20RunListResponse = {
      items: [
        {
          id: 1,
          created_at: '2025-01-01T10:00:00Z',
          status: 'completed',
          symbol_count: 5,
          processed_count: 5,
          long_count: 2,
              no_setup_count: 2,
          stock_list_id: 10,
          stock_list_name: 'Legacy Watchlist',
        },
      ],
      total: 1,
      has_more: false,
      limit: 20,
      offset: 0,
    };

    mockListRuns.mockResolvedValue(runsWithLegacyList);

    renderWithRouter(<Live20HistoryTab />);

    await waitFor(() => {
      expect(screen.getByText('Legacy Watchlist')).toBeInTheDocument();
    });
  });

  it('shows no list badge when neither source_lists nor stock_list_name is present', async () => {
    const runsWithoutLists: Live20RunListResponse = {
      items: [
        {
          id: 1,
          created_at: '2025-01-01T10:00:00Z',
          status: 'completed',
          symbol_count: 5,
          processed_count: 5,
          long_count: 2,
              no_setup_count: 2,
          stock_list_id: null,
          stock_list_name: null,
          source_lists: null,
        },
      ],
      total: 1,
      has_more: false,
      limit: 20,
      offset: 0,
    };

    mockListRuns.mockResolvedValue(runsWithoutLists);

    renderWithRouter(<Live20HistoryTab />);

    await waitFor(() => {
      expect(screen.getByText('5')).toBeInTheDocument(); // symbol_count renders
    });

    // No list badge should be present
    expect(screen.queryByText('Tech Watchlist')).not.toBeInTheDocument();
    expect(screen.queryByText('Legacy Watchlist')).not.toBeInTheDocument();
    expect(screen.queryByText(/lists combined/)).not.toBeInTheDocument();
  });
});
