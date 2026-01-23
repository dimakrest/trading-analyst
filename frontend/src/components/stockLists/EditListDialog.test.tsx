import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { EditListDialog } from './EditListDialog';
import type { StockList } from '../../services/stockListService';

describe('EditListDialog', () => {
  const mockList: StockList = {
    id: 1,
    name: 'Tech Leaders',
    symbols: ['AAPL', 'MSFT', 'GOOGL'],
    symbol_count: 3,
  };

  const defaultProps = {
    list: mockList,
    open: true,
    onOpenChange: vi.fn(),
    onSubmit: vi.fn(),
    isSubmitting: false,
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('Rendering', () => {
    it('renders dialog when open', () => {
      render(<EditListDialog {...defaultProps} />);

      expect(screen.getByText('Edit List')).toBeInTheDocument();
      expect(screen.getByText('Update list name and manage symbols')).toBeInTheDocument();
    });

    it('renders nothing when list is null', () => {
      render(<EditListDialog {...defaultProps} list={null} />);

      expect(screen.queryByText('Edit List')).not.toBeInTheDocument();
    });

    it('pre-fills form with list data', () => {
      render(<EditListDialog {...defaultProps} />);

      expect(screen.getByDisplayValue('Tech Leaders')).toBeInTheDocument();
      expect(screen.getByText('AAPL')).toBeInTheDocument();
      expect(screen.getByText('MSFT')).toBeInTheDocument();
      expect(screen.getByText('GOOGL')).toBeInTheDocument();
    });

    it('displays symbol count', () => {
      render(<EditListDialog {...defaultProps} />);

      // Label says "Current Symbols" and count is shown separately as "3 symbols"
      expect(screen.getByText('Current Symbols')).toBeInTheDocument();
      expect(screen.getByText('3 symbols')).toBeInTheDocument();
    });
  });

  describe('Symbol Removal', () => {
    it('removes symbol when Remove button is clicked', async () => {
      render(<EditListDialog {...defaultProps} />);

      const removeButtons = screen.getAllByRole('button', { name: /remove aapl/i });
      fireEvent.click(removeButtons[0]);

      await waitFor(() => {
        expect(screen.queryByText('AAPL')).not.toBeInTheDocument();
      });

      // Other symbols should still be present
      expect(screen.getByText('MSFT')).toBeInTheDocument();
      expect(screen.getByText('GOOGL')).toBeInTheDocument();
    });

    it('updates symbol count after removal', async () => {
      render(<EditListDialog {...defaultProps} />);

      const removeButtons = screen.getAllByRole('button', { name: /remove/i });
      fireEvent.click(removeButtons[0]);

      await waitFor(() => {
        expect(screen.getByText('2 symbols')).toBeInTheDocument();
      });
    });
  });

  describe('Adding Symbols', () => {
    it('adds new symbols via input', async () => {
      render(<EditListDialog {...defaultProps} />);

      const addInput = screen.getByPlaceholderText(/NFLX, CRM, INTC/i);
      fireEvent.change(addInput, { target: { value: 'NVDA, TSLA' } });

      const addButton = screen.getByRole('button', { name: /^add$/i });
      fireEvent.click(addButton);

      await waitFor(() => {
        expect(screen.getByText('NVDA')).toBeInTheDocument();
        expect(screen.getByText('TSLA')).toBeInTheDocument();
      });
    });

    it('clears input after adding symbols', async () => {
      render(<EditListDialog {...defaultProps} />);

      const addInput = screen.getByPlaceholderText(/NFLX, CRM, INTC/i);
      fireEvent.change(addInput, { target: { value: 'NVDA' } });

      const addButton = screen.getByRole('button', { name: /^add$/i });
      fireEvent.click(addButton);

      await waitFor(() => {
        expect(addInput).toHaveValue('');
      });
    });

    it('prevents duplicate symbols', async () => {
      render(<EditListDialog {...defaultProps} />);

      const addInput = screen.getByPlaceholderText(/NFLX, CRM, INTC/i);
      fireEvent.change(addInput, { target: { value: 'AAPL, NVDA' } });

      const addButton = screen.getByRole('button', { name: /^add$/i });
      fireEvent.click(addButton);

      await waitFor(() => {
        // Only one AAPL should exist
        const aaplElements = screen.getAllByText('AAPL');
        expect(aaplElements).toHaveLength(1);
        // NVDA should be added
        expect(screen.getByText('NVDA')).toBeInTheDocument();
      });
    });

    it('adds symbols on Enter key', async () => {
      render(<EditListDialog {...defaultProps} />);

      const addInput = screen.getByPlaceholderText(/NFLX, CRM, INTC/i);
      fireEvent.change(addInput, { target: { value: 'NVDA' } });
      fireEvent.keyDown(addInput, { key: 'Enter' });

      await waitFor(() => {
        expect(screen.getByText('NVDA')).toBeInTheDocument();
      });
    });
  });

  describe('Form Submission', () => {
    it('submits with updated name', async () => {
      defaultProps.onSubmit.mockResolvedValue(undefined);
      render(<EditListDialog {...defaultProps} />);

      const nameInput = screen.getByDisplayValue('Tech Leaders');
      fireEvent.change(nameInput, { target: { value: 'Updated Tech' } });

      const saveButton = screen.getByRole('button', { name: /save changes/i });
      fireEvent.click(saveButton);

      await waitFor(() => {
        expect(defaultProps.onSubmit).toHaveBeenCalledWith(1, {
          name: 'Updated Tech',
          symbols: ['AAPL', 'MSFT', 'GOOGL'],
        });
      });
    });

    it('submits with modified symbols', async () => {
      defaultProps.onSubmit.mockResolvedValue(undefined);
      render(<EditListDialog {...defaultProps} />);

      // Remove MSFT
      const removeButtons = screen.getAllByRole('button', { name: /remove msft/i });
      fireEvent.click(removeButtons[0]);

      // Add NVDA
      const addInput = screen.getByPlaceholderText(/NFLX, CRM, INTC/i);
      fireEvent.change(addInput, { target: { value: 'NVDA' } });
      fireEvent.click(screen.getByRole('button', { name: /^add$/i }));

      await waitFor(() => {
        expect(screen.getByText('NVDA')).toBeInTheDocument();
      });

      const saveButton = screen.getByRole('button', { name: /save changes/i });
      fireEvent.click(saveButton);

      await waitFor(() => {
        expect(defaultProps.onSubmit).toHaveBeenCalledWith(1, {
          name: 'Tech Leaders',
          symbols: ['AAPL', 'GOOGL', 'NVDA'],
        });
      });
    });
  });

  describe('Validation', () => {
    it('shows error when name is empty', async () => {
      render(<EditListDialog {...defaultProps} />);

      const nameInput = screen.getByDisplayValue('Tech Leaders');
      fireEvent.change(nameInput, { target: { value: '' } });

      const saveButton = screen.getByRole('button', { name: /save changes/i });
      fireEvent.click(saveButton);

      await waitFor(() => {
        expect(screen.getByText('List name is required')).toBeInTheDocument();
      });

      expect(defaultProps.onSubmit).not.toHaveBeenCalled();
    });
  });

  describe('Empty Symbols State', () => {
    it('shows empty message when all symbols are removed', async () => {
      const emptyList: StockList = {
        id: 1,
        name: 'Empty List',
        symbols: [],
        symbol_count: 0,
      };
      render(<EditListDialog {...defaultProps} list={emptyList} />);

      expect(screen.getByText('No symbols in this list')).toBeInTheDocument();
    });
  });

  describe('Submitting State', () => {
    it('disables buttons when submitting', () => {
      render(<EditListDialog {...defaultProps} isSubmitting={true} />);

      expect(screen.getByRole('button', { name: /cancel/i })).toBeDisabled();
      expect(screen.getByRole('button', { name: /saving/i })).toBeDisabled();
    });

    it('shows "Saving..." text when submitting', () => {
      render(<EditListDialog {...defaultProps} isSubmitting={true} />);

      expect(screen.getByRole('button', { name: /saving/i })).toBeInTheDocument();
    });
  });

  describe('Error Handling', () => {
    it('displays error message when submission fails', async () => {
      const errorMessage = 'A list with this name already exists';
      defaultProps.onSubmit.mockRejectedValue(new Error(errorMessage));
      render(<EditListDialog {...defaultProps} />);

      const saveButton = screen.getByRole('button', { name: /save changes/i });
      fireEvent.click(saveButton);

      await waitFor(() => {
        expect(screen.getByText(errorMessage)).toBeInTheDocument();
      });
    });

    it('displays Axios error detail when available', async () => {
      const axiosError = {
        response: {
          data: {
            detail: 'A list named "Finance" already exists',
          },
        },
      };
      defaultProps.onSubmit.mockRejectedValue(axiosError);
      render(<EditListDialog {...defaultProps} />);

      const nameInput = screen.getByDisplayValue('Tech Leaders');
      fireEvent.change(nameInput, { target: { value: 'Finance' } });

      const saveButton = screen.getByRole('button', { name: /save changes/i });
      fireEvent.click(saveButton);

      await waitFor(() => {
        expect(screen.getByText('A list named "Finance" already exists')).toBeInTheDocument();
      });
    });

    it('keeps dialog open when submission fails', async () => {
      defaultProps.onSubmit.mockRejectedValue(new Error('Update failed'));
      render(<EditListDialog {...defaultProps} />);

      const saveButton = screen.getByRole('button', { name: /save changes/i });
      fireEvent.click(saveButton);

      await waitFor(() => {
        expect(screen.getByText('Update failed')).toBeInTheDocument();
      });

      // Dialog should still be open
      expect(screen.getByText('Edit List')).toBeInTheDocument();
      // onOpenChange should NOT have been called with false
      expect(defaultProps.onOpenChange).not.toHaveBeenCalledWith(false);
    });

    it('clears error when dialog is closed and reopened', async () => {
      defaultProps.onSubmit.mockRejectedValue(new Error('First error'));
      const { rerender } = render(<EditListDialog {...defaultProps} />);

      const saveButton = screen.getByRole('button', { name: /save changes/i });
      fireEvent.click(saveButton);

      await waitFor(() => {
        expect(screen.getByText('First error')).toBeInTheDocument();
      });

      // Close dialog
      rerender(<EditListDialog {...defaultProps} open={false} />);

      // Reopen dialog with same list - error should be cleared
      rerender(<EditListDialog {...defaultProps} open={true} />);

      await waitFor(() => {
        expect(screen.queryByText('First error')).not.toBeInTheDocument();
      });

      // Dialog should still be showing
      expect(screen.getByText('Edit List')).toBeInTheDocument();
    });
  });
});
