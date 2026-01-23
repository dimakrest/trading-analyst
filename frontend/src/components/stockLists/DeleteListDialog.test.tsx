import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { DeleteListDialog } from './DeleteListDialog';
import type { StockList } from '../../services/stockListService';

describe('DeleteListDialog', () => {
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
    onConfirm: vi.fn(),
    isDeleting: false,
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('Rendering', () => {
    it('renders dialog when open', () => {
      render(<DeleteListDialog {...defaultProps} />);

      // Title is in the heading
      expect(screen.getByRole('heading', { name: /delete list/i })).toBeInTheDocument();
    });

    it('renders nothing when list is null', () => {
      render(<DeleteListDialog {...defaultProps} list={null} />);

      expect(screen.queryByRole('heading', { name: /delete list/i })).not.toBeInTheDocument();
    });

    it('displays list name in warning message', () => {
      render(<DeleteListDialog {...defaultProps} />);

      // The warning text contains the list name in a <strong> element
      expect(screen.getByText(/Are you sure you want to delete/)).toBeInTheDocument();
      expect(screen.getByText(/"Tech Leaders"/)).toBeInTheDocument();
    });

    it('displays undo warning', () => {
      render(<DeleteListDialog {...defaultProps} />);

      expect(screen.getByText(/This action cannot be undone/)).toBeInTheDocument();
    });

    it('renders Cancel and Delete List buttons', () => {
      render(<DeleteListDialog {...defaultProps} />);

      expect(screen.getByRole('button', { name: /cancel/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /delete list/i })).toBeInTheDocument();
    });
  });

  describe('Confirmation', () => {
    it('calls onConfirm with list when Delete List is clicked', async () => {
      defaultProps.onConfirm.mockResolvedValue(undefined);
      render(<DeleteListDialog {...defaultProps} />);

      const deleteButton = screen.getByRole('button', { name: /delete list/i });
      fireEvent.click(deleteButton);

      await waitFor(() => {
        expect(defaultProps.onConfirm).toHaveBeenCalledWith(mockList);
      });
    });

    it('closes dialog after successful deletion', async () => {
      defaultProps.onConfirm.mockResolvedValue(undefined);
      render(<DeleteListDialog {...defaultProps} />);

      const deleteButton = screen.getByRole('button', { name: /delete list/i });
      fireEvent.click(deleteButton);

      await waitFor(() => {
        expect(defaultProps.onOpenChange).toHaveBeenCalledWith(false);
      });
    });
  });

  describe('Cancel Behavior', () => {
    it('calls onOpenChange when Cancel is clicked', () => {
      render(<DeleteListDialog {...defaultProps} />);

      const cancelButton = screen.getByRole('button', { name: /cancel/i });
      fireEvent.click(cancelButton);

      // AlertDialogCancel should trigger onOpenChange
      expect(defaultProps.onConfirm).not.toHaveBeenCalled();
    });
  });

  describe('Deleting State', () => {
    it('disables buttons when deleting', () => {
      render(<DeleteListDialog {...defaultProps} isDeleting={true} />);

      expect(screen.getByRole('button', { name: /cancel/i })).toBeDisabled();
      expect(screen.getByRole('button', { name: /deleting/i })).toBeDisabled();
    });

    it('shows "Deleting..." text when deleting', () => {
      render(<DeleteListDialog {...defaultProps} isDeleting={true} />);

      expect(screen.getByRole('button', { name: /deleting/i })).toBeInTheDocument();
    });
  });

  describe('Different List Names', () => {
    it('displays correct list name for different lists', () => {
      const differentList: StockList = {
        id: 2,
        name: 'My Special List',
        symbols: [],
        symbol_count: 0,
      };

      render(<DeleteListDialog {...defaultProps} list={differentList} />);

      expect(screen.getByText(/Are you sure you want to delete/)).toBeInTheDocument();
      expect(screen.getByText(/"My Special List"/)).toBeInTheDocument();
    });
  });

  describe('Error Handling', () => {
    it('displays error message when deletion fails', async () => {
      const errorMessage = 'Failed to delete list';
      defaultProps.onConfirm.mockRejectedValue(new Error(errorMessage));
      render(<DeleteListDialog {...defaultProps} />);

      const deleteButton = screen.getByRole('button', { name: /delete list/i });
      fireEvent.click(deleteButton);

      await waitFor(() => {
        expect(screen.getByText(errorMessage)).toBeInTheDocument();
      });
    });

    it('displays Axios error detail when available', async () => {
      const axiosError = {
        response: {
          data: {
            detail: 'Cannot delete list: in use by scheduled jobs',
          },
        },
      };
      defaultProps.onConfirm.mockRejectedValue(axiosError);
      render(<DeleteListDialog {...defaultProps} />);

      const deleteButton = screen.getByRole('button', { name: /delete list/i });
      fireEvent.click(deleteButton);

      await waitFor(() => {
        expect(screen.getByText('Cannot delete list: in use by scheduled jobs')).toBeInTheDocument();
      });
    });

    it('keeps dialog open when deletion fails', async () => {
      defaultProps.onConfirm.mockRejectedValue(new Error('Network error'));
      render(<DeleteListDialog {...defaultProps} />);

      const deleteButton = screen.getByRole('button', { name: /delete list/i });
      fireEvent.click(deleteButton);

      await waitFor(() => {
        expect(screen.getByText('Network error')).toBeInTheDocument();
      });

      // Dialog should still be open
      expect(screen.getByRole('heading', { name: /delete list/i })).toBeInTheDocument();
      // onOpenChange should NOT have been called with false
      expect(defaultProps.onOpenChange).not.toHaveBeenCalledWith(false);
    });

    it('clears error when dialog is reopened', async () => {
      defaultProps.onConfirm.mockRejectedValue(new Error('First error'));
      const { rerender } = render(<DeleteListDialog {...defaultProps} />);

      const deleteButton = screen.getByRole('button', { name: /delete list/i });
      fireEvent.click(deleteButton);

      await waitFor(() => {
        expect(screen.getByText('First error')).toBeInTheDocument();
      });

      // Close and reopen dialog - error should be cleared on open
      rerender(<DeleteListDialog {...defaultProps} open={false} />);
      rerender(<DeleteListDialog {...defaultProps} open={true} />);

      // The useEffect clears error when open becomes true
      await waitFor(() => {
        expect(screen.queryByText('First error')).not.toBeInTheDocument();
      });

      // Dialog should still be showing
      expect(screen.getByRole('heading', { name: /delete list/i })).toBeInTheDocument();
    });
  });
});
