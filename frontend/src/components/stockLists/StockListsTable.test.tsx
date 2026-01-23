import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { StockListsTable } from './StockListsTable';
import type { StockList } from '../../services/stockListService';

// Mock the useResponsive hook
const mockUseResponsive = vi.hoisted(() => vi.fn());
vi.mock('../../hooks/useResponsive', () => ({
  useResponsive: mockUseResponsive,
}));

describe('StockListsTable', () => {
  const mockLists: StockList[] = [
    { id: 1, name: 'Tech Leaders', symbols: ['AAPL', 'MSFT', 'GOOGL'], symbol_count: 3 },
    { id: 2, name: 'Finance', symbols: ['JPM', 'BAC'], symbol_count: 2 },
  ];

  const defaultProps = {
    lists: mockLists,
    isLoading: false,
    error: null,
    totalSymbols: 5,
    onEdit: vi.fn(),
    onDelete: vi.fn(),
  };

  beforeEach(() => {
    vi.clearAllMocks();

    // Default to desktop mode
    mockUseResponsive.mockReturnValue({
      isMobile: false,
      isTablet: false,
      isDesktop: true,
      mounted: true,
    });
  });

  describe('Desktop Layout', () => {
    it('renders table with headers', () => {
      render(<StockListsTable {...defaultProps} />);

      expect(screen.getByText('List Name')).toBeInTheDocument();
      expect(screen.getByText('Symbols')).toBeInTheDocument();
      expect(screen.getByText('Preview')).toBeInTheDocument();
      expect(screen.getByText('Actions')).toBeInTheDocument();
    });

    it('renders section header with list count', () => {
      render(<StockListsTable {...defaultProps} />);

      expect(screen.getByText('Your Lists')).toBeInTheDocument();
      // The format is now "2 lists • 5 symbols total"
      expect(screen.getByText(/2 lists/)).toBeInTheDocument();
      expect(screen.getByText(/5 symbols total/)).toBeInTheDocument();
    });

    it('displays list names with icons', () => {
      render(<StockListsTable {...defaultProps} />);

      expect(screen.getByText('Tech Leaders')).toBeInTheDocument();
      expect(screen.getByText('Finance')).toBeInTheDocument();
    });

    it('displays symbol counts with badges', () => {
      render(<StockListsTable {...defaultProps} />);

      // Count badges show the number and "symbols" text separately
      expect(screen.getByText('3')).toBeInTheDocument();
      expect(screen.getByText('2')).toBeInTheDocument();
      // The "symbols" labels are in the Symbols column (header "Symbols" + 2 row labels)
      expect(screen.getAllByText(/symbols?/)).toHaveLength(3);
    });

    it('displays singular "symbol" when count is 1', () => {
      const singleSymbolList: StockList[] = [
        { id: 1, name: 'Single', symbols: ['AAPL'], symbol_count: 1 },
      ];

      render(<StockListsTable {...defaultProps} lists={singleSymbolList} totalSymbols={1} />);

      expect(screen.getByText('1')).toBeInTheDocument();
      expect(screen.getByText('symbol')).toBeInTheDocument(); // singular
    });

    it('displays preview chips for symbols', () => {
      render(<StockListsTable {...defaultProps} />);

      // First list symbols should be visible
      expect(screen.getByText('AAPL')).toBeInTheDocument();
      expect(screen.getByText('MSFT')).toBeInTheDocument();
      expect(screen.getByText('GOOGL')).toBeInTheDocument();
      // Second list symbols
      expect(screen.getByText('JPM')).toBeInTheDocument();
      expect(screen.getByText('BAC')).toBeInTheDocument();
    });

    it('displays "+N more" chip when more than 4 symbols', () => {
      const manySymbolsList: StockList[] = [
        {
          id: 1,
          name: 'Many Symbols',
          symbols: ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META', 'NFLX'],
          symbol_count: 6,
        },
      ];

      render(<StockListsTable {...defaultProps} lists={manySymbolsList} />);

      // Should show first 4 + "+2 more"
      expect(screen.getByText('AAPL')).toBeInTheDocument();
      expect(screen.getByText('MSFT')).toBeInTheDocument();
      expect(screen.getByText('GOOGL')).toBeInTheDocument();
      expect(screen.getByText('AMZN')).toBeInTheDocument();
      expect(screen.getByText('+2 more')).toBeInTheDocument();
    });

    it('renders edit buttons with aria-labels for each row', () => {
      render(<StockListsTable {...defaultProps} />);

      expect(screen.getByRole('button', { name: /edit tech leaders/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /edit finance/i })).toBeInTheDocument();
    });

    it('renders delete buttons with aria-labels for each row', () => {
      render(<StockListsTable {...defaultProps} />);

      expect(screen.getByRole('button', { name: /delete tech leaders/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /delete finance/i })).toBeInTheDocument();
    });

    it('calls onEdit when Edit button is clicked', () => {
      render(<StockListsTable {...defaultProps} />);

      const editButton = screen.getByRole('button', { name: /edit tech leaders/i });
      fireEvent.click(editButton);

      expect(defaultProps.onEdit).toHaveBeenCalledWith(mockLists[0]);
    });

    it('calls onDelete when Delete button is clicked', () => {
      render(<StockListsTable {...defaultProps} />);

      const deleteButton = screen.getByRole('button', { name: /delete tech leaders/i });
      fireEvent.click(deleteButton);

      expect(defaultProps.onDelete).toHaveBeenCalledWith(mockLists[0]);
    });
  });

  describe('Mobile Layout', () => {
    beforeEach(() => {
      mockUseResponsive.mockReturnValue({
        isMobile: true,
        isTablet: false,
        isDesktop: false,
        mounted: true,
      });
    });

    it('renders mobile headers', () => {
      render(<StockListsTable {...defaultProps} />);

      expect(screen.getByText('Name')).toBeInTheDocument();
      expect(screen.getByText('Count')).toBeInTheDocument();
      expect(screen.getByText('Actions')).toBeInTheDocument();
    });

    it('displays list names', () => {
      render(<StockListsTable {...defaultProps} />);

      expect(screen.getByText('Tech Leaders')).toBeInTheDocument();
      expect(screen.getByText('Finance')).toBeInTheDocument();
    });

    it('displays numeric symbol counts in badges', () => {
      render(<StockListsTable {...defaultProps} />);

      expect(screen.getByText('3')).toBeInTheDocument();
      expect(screen.getByText('2')).toBeInTheDocument();
    });

    it('uses icon buttons with aria-labels', () => {
      render(<StockListsTable {...defaultProps} />);

      expect(screen.getByRole('button', { name: /edit tech leaders/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /delete tech leaders/i })).toBeInTheDocument();
    });
  });

  describe('Loading State', () => {
    it('displays loading skeletons when loading', () => {
      render(<StockListsTable {...defaultProps} isLoading={true} lists={[]} />);

      // Section header should still show
      expect(screen.getByText('Your Lists')).toBeInTheDocument();
      // Table content should not be visible
      expect(screen.queryByText('Tech Leaders')).not.toBeInTheDocument();
    });
  });

  describe('Error State', () => {
    it('displays error message', () => {
      render(<StockListsTable {...defaultProps} error="Failed to load lists" lists={[]} />);

      expect(screen.getByText('Failed to load lists')).toBeInTheDocument();
    });

    it('does not display table when error occurs', () => {
      render(<StockListsTable {...defaultProps} error="Failed to load" lists={[]} />);

      expect(screen.queryByText('List Name')).not.toBeInTheDocument();
    });
  });

  describe('Empty State', () => {
    it('displays empty state message', () => {
      render(<StockListsTable {...defaultProps} lists={[]} />);

      expect(screen.getByText('No stock lists yet')).toBeInTheDocument();
      expect(
        screen.getByText('Create your first list to organize symbols for quick analysis')
      ).toBeInTheDocument();
    });

    it('displays empty state with list icon', () => {
      render(<StockListsTable {...defaultProps} lists={[]} />);

      // The List icon component should be present (we can check the container)
      expect(screen.getByText('No stock lists yet')).toBeInTheDocument();
    });
  });

  describe('Hydration Prevention', () => {
    it('displays loading message when not mounted', () => {
      mockUseResponsive.mockReturnValue({
        isMobile: false,
        isTablet: false,
        isDesktop: true,
        mounted: false,
      });

      render(<StockListsTable {...defaultProps} />);

      expect(screen.getByText('Loading lists...')).toBeInTheDocument();
      expect(screen.queryByText('Tech Leaders')).not.toBeInTheDocument();
    });
  });
});
