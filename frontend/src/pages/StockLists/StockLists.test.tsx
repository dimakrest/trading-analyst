import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { toast } from 'sonner';
import { StockLists } from './StockLists';
import * as useStockListsHook from '../../hooks/useStockLists';
import type { StockList } from '../../services/stockListService';

// Mock the useStockLists hook
vi.mock('../../hooks/useStockLists');

// Mock sonner toast
vi.mock('sonner', () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}));

// Mock the useResponsive hook
const mockUseResponsive = vi.hoisted(() => vi.fn());
vi.mock('../../hooks/useResponsive', () => ({
  useResponsive: mockUseResponsive,
}));

describe('StockLists Page', () => {
  const mockLists: StockList[] = [
    { id: 1, name: 'Tech Leaders', symbols: ['AAPL', 'MSFT', 'GOOGL'], symbol_count: 3 },
    { id: 2, name: 'Finance', symbols: ['JPM', 'BAC'], symbol_count: 2 },
  ];

  const mockUseStockLists = {
    lists: mockLists,
    isLoading: false,
    error: null,
    createList: vi.fn(),
    updateList: vi.fn(),
    deleteList: vi.fn(),
    refetch: vi.fn(),
  };

  const renderPage = () => {
    return render(
      <BrowserRouter>
        <StockLists />
      </BrowserRouter>
    );
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

    // Default mock implementation
    vi.spyOn(useStockListsHook, 'useStockLists').mockReturnValue(mockUseStockLists);
  });

  describe('Page Structure', () => {
    it('renders without crashing', () => {
      renderPage();
      expect(screen.getByText('Stock Lists')).toBeInTheDocument();
    });

    it('displays page header with title and description', () => {
      renderPage();

      expect(screen.getByText('Stock Lists')).toBeInTheDocument();
      expect(
        screen.getByText('Organize your symbols into watchlists for quick access')
      ).toBeInTheDocument();
    });

    it('displays Create List button', () => {
      renderPage();

      const createButton = screen.getByRole('button', { name: /create list/i });
      expect(createButton).toBeInTheDocument();
    });

    it('displays section header with list and symbol count', () => {
      renderPage();

      expect(screen.getByText('Your Lists')).toBeInTheDocument();
      // Format: "2 lists • 5 symbols total"
      expect(screen.getByText(/2 lists/)).toBeInTheDocument();
      expect(screen.getByText(/5 symbols total/)).toBeInTheDocument();
    });

    it('displays singular "list" and "symbol" when counts are 1', () => {
      vi.spyOn(useStockListsHook, 'useStockLists').mockReturnValue({
        ...mockUseStockLists,
        lists: [{ id: 1, name: 'Single', symbols: ['AAPL'], symbol_count: 1 }],
      });

      renderPage();

      expect(screen.getByText(/1 list/)).toBeInTheDocument();
      expect(screen.getByText(/1 symbol total/)).toBeInTheDocument();
    });
  });

  describe('Table Display', () => {
    it('displays lists in table', () => {
      renderPage();

      expect(screen.getByText('Tech Leaders')).toBeInTheDocument();
      expect(screen.getByText('Finance')).toBeInTheDocument();
    });

    it('displays symbol counts in badges', () => {
      renderPage();

      expect(screen.getByText('3')).toBeInTheDocument();
      expect(screen.getByText('2')).toBeInTheDocument();
    });

    it('displays symbol preview chips', () => {
      renderPage();

      expect(screen.getByText('AAPL')).toBeInTheDocument();
      expect(screen.getByText('MSFT')).toBeInTheDocument();
      expect(screen.getByText('GOOGL')).toBeInTheDocument();
    });

    it('displays Edit and Delete buttons for each list', () => {
      renderPage();

      expect(screen.getByRole('button', { name: /edit tech leaders/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /delete tech leaders/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /edit finance/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /delete finance/i })).toBeInTheDocument();
    });
  });

  describe('Loading State', () => {
    it('displays loading state when isLoading is true', () => {
      vi.spyOn(useStockListsHook, 'useStockLists').mockReturnValue({
        ...mockUseStockLists,
        isLoading: true,
        lists: [],
      });

      renderPage();

      // Table should not display list names when loading
      expect(screen.queryByText('Tech Leaders')).not.toBeInTheDocument();
    });
  });

  describe('Error State', () => {
    it('displays error message when error occurs', () => {
      vi.spyOn(useStockListsHook, 'useStockLists').mockReturnValue({
        ...mockUseStockLists,
        error: 'Failed to load lists',
        lists: [],
      });

      renderPage();

      expect(screen.getByText('Failed to load lists')).toBeInTheDocument();
    });
  });

  describe('Empty State', () => {
    it('displays empty state when no lists exist', () => {
      vi.spyOn(useStockListsHook, 'useStockLists').mockReturnValue({
        ...mockUseStockLists,
        lists: [],
      });

      renderPage();

      expect(screen.getByText('No stock lists yet')).toBeInTheDocument();
      expect(
        screen.getByText('Create your first list to organize symbols for quick analysis')
      ).toBeInTheDocument();
    });
  });

  describe('Create Dialog', () => {
    it('opens create dialog when Create List button is clicked', () => {
      renderPage();

      const createButton = screen.getByRole('button', { name: /create list/i });
      fireEvent.click(createButton);

      expect(screen.getByText('Create New List')).toBeInTheDocument();
      expect(
        screen.getByText('Create a new stock list to organize your watchlist')
      ).toBeInTheDocument();
    });

    it('submits create form with list name', async () => {
      mockUseStockLists.createList.mockResolvedValue({
        id: 3,
        name: 'New List',
        symbols: [],
        symbol_count: 0,
      });

      renderPage();

      // Open dialog
      const createButton = screen.getByRole('button', { name: /create list/i });
      fireEvent.click(createButton);

      // Fill in form
      const nameInput = screen.getByLabelText(/list name/i);
      fireEvent.change(nameInput, { target: { value: 'New List' } });

      // Submit
      const submitButton = screen.getByRole('button', { name: /^create list$/i });
      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(mockUseStockLists.createList).toHaveBeenCalledWith({
          name: 'New List',
          symbols: undefined,
        });
      });
    });
  });

  describe('Edit Dialog', () => {
    it('opens edit dialog when Edit button is clicked', () => {
      renderPage();

      const editButton = screen.getByRole('button', { name: /edit tech leaders/i });
      fireEvent.click(editButton);

      expect(screen.getByText('Edit List')).toBeInTheDocument();
      expect(screen.getByDisplayValue('Tech Leaders')).toBeInTheDocument();
    });
  });

  describe('Delete Dialog', () => {
    it('opens delete confirmation dialog when Delete button is clicked', () => {
      renderPage();

      const deleteButton = screen.getByRole('button', { name: /delete tech leaders/i });
      fireEvent.click(deleteButton);

      expect(screen.getByRole('alertdialog')).toBeInTheDocument();
      expect(
        screen.getByText(/Are you sure you want to delete/)
      ).toBeInTheDocument();
    });

    it('calls deleteList when delete is confirmed', async () => {
      mockUseStockLists.deleteList.mockResolvedValue(undefined);

      renderPage();

      // Open delete dialog
      const deleteButton = screen.getByRole('button', { name: /delete tech leaders/i });
      fireEvent.click(deleteButton);

      // Confirm deletion
      const confirmButton = screen.getByRole('button', { name: /delete list/i });
      fireEvent.click(confirmButton);

      await waitFor(() => {
        expect(mockUseStockLists.deleteList).toHaveBeenCalledWith(1);
      });
    });
  });

  describe('Responsive Behavior', () => {
    it('renders correctly on mobile', () => {
      mockUseResponsive.mockReturnValue({
        isMobile: true,
        isTablet: false,
        isDesktop: false,
        mounted: true,
      });

      renderPage();

      expect(screen.getByText('Stock Lists')).toBeInTheDocument();
      expect(screen.getByText('Tech Leaders')).toBeInTheDocument();
    });
  });

  describe('Error Handling', () => {
    describe('Create List Errors', () => {
      it('shows toast error when create fails', async () => {
        const errorMessage = 'A list with this name already exists';
        mockUseStockLists.createList.mockRejectedValue(new Error(errorMessage));

        renderPage();

        // Open dialog
        const createButton = screen.getByRole('button', { name: /create list/i });
        fireEvent.click(createButton);

        // Fill in form
        const nameInput = screen.getByLabelText(/list name/i);
        fireEvent.change(nameInput, { target: { value: 'Duplicate List' } });

        // Submit
        const submitButton = screen.getByRole('button', { name: /^create list$/i });
        fireEvent.click(submitButton);

        await waitFor(() => {
          expect(toast.error).toHaveBeenCalledWith(errorMessage);
        });
      });

      it('shows success toast when create succeeds', async () => {
        mockUseStockLists.createList.mockResolvedValue({
          id: 3,
          name: 'New List',
          symbols: [],
          symbol_count: 0,
        });

        renderPage();

        // Open dialog
        const createButton = screen.getByRole('button', { name: /create list/i });
        fireEvent.click(createButton);

        // Fill in form
        const nameInput = screen.getByLabelText(/list name/i);
        fireEvent.change(nameInput, { target: { value: 'New List' } });

        // Submit
        const submitButton = screen.getByRole('button', { name: /^create list$/i });
        fireEvent.click(submitButton);

        await waitFor(() => {
          expect(toast.success).toHaveBeenCalledWith('List "New List" created');
        });
      });
    });

    describe('Delete List Errors', () => {
      it('shows toast error when delete fails', async () => {
        const errorMessage = 'Cannot delete list in use';
        mockUseStockLists.deleteList.mockRejectedValue(new Error(errorMessage));

        renderPage();

        // Open delete dialog
        const deleteButton = screen.getByRole('button', { name: /delete tech leaders/i });
        fireEvent.click(deleteButton);

        // Confirm deletion
        const confirmButton = screen.getByRole('button', { name: /delete list/i });
        fireEvent.click(confirmButton);

        await waitFor(() => {
          expect(toast.error).toHaveBeenCalledWith(errorMessage);
        });
      });

      it('shows success toast when delete succeeds', async () => {
        mockUseStockLists.deleteList.mockResolvedValue(undefined);

        renderPage();

        // Open delete dialog
        const deleteButton = screen.getByRole('button', { name: /delete tech leaders/i });
        fireEvent.click(deleteButton);

        // Confirm deletion
        const confirmButton = screen.getByRole('button', { name: /delete list/i });
        fireEvent.click(confirmButton);

        await waitFor(() => {
          expect(toast.success).toHaveBeenCalledWith('List "Tech Leaders" deleted');
        });
      });
    });

    describe('Axios Error Handling', () => {
      it('extracts error detail from Axios response', async () => {
        const axiosError = {
          response: {
            data: {
              detail: 'A list named "Tech" already exists',
            },
          },
        };
        mockUseStockLists.createList.mockRejectedValue(axiosError);

        renderPage();

        // Open dialog
        const createButton = screen.getByRole('button', { name: /create list/i });
        fireEvent.click(createButton);

        // Fill in form
        const nameInput = screen.getByLabelText(/list name/i);
        fireEvent.change(nameInput, { target: { value: 'Tech' } });

        // Submit
        const submitButton = screen.getByRole('button', { name: /^create list$/i });
        fireEvent.click(submitButton);

        await waitFor(() => {
          expect(toast.error).toHaveBeenCalledWith('A list named "Tech" already exists');
        });
      });
    });
  });
});
