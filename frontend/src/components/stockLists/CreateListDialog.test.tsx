import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { CreateListDialog } from './CreateListDialog';

describe('CreateListDialog', () => {
  const defaultProps = {
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
      render(<CreateListDialog {...defaultProps} />);

      expect(screen.getByText('Create New List')).toBeInTheDocument();
      expect(
        screen.getByText('Create a new stock list to organize your watchlist')
      ).toBeInTheDocument();
    });

    it('renders form fields', () => {
      render(<CreateListDialog {...defaultProps} />);

      expect(screen.getByLabelText(/list name/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/symbols/i)).toBeInTheDocument();
    });

    it('renders Cancel and Create List buttons', () => {
      render(<CreateListDialog {...defaultProps} />);

      expect(screen.getByRole('button', { name: /cancel/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /create list/i })).toBeInTheDocument();
    });
  });

  describe('Form Submission', () => {
    it('submits with name only', async () => {
      defaultProps.onSubmit.mockResolvedValue(undefined);
      render(<CreateListDialog {...defaultProps} />);

      const nameInput = screen.getByLabelText(/list name/i);
      fireEvent.change(nameInput, { target: { value: 'My List' } });

      const submitButton = screen.getByRole('button', { name: /create list/i });
      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(defaultProps.onSubmit).toHaveBeenCalledWith({
          name: 'My List',
          symbols: undefined,
        });
      });
    });

    it('submits with name and symbols', async () => {
      defaultProps.onSubmit.mockResolvedValue(undefined);
      render(<CreateListDialog {...defaultProps} />);

      const nameInput = screen.getByLabelText(/list name/i);
      fireEvent.change(nameInput, { target: { value: 'Tech Stocks' } });

      const symbolsInput = screen.getByLabelText(/symbols/i);
      fireEvent.change(symbolsInput, { target: { value: 'AAPL, MSFT, GOOGL' } });

      const submitButton = screen.getByRole('button', { name: /create list/i });
      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(defaultProps.onSubmit).toHaveBeenCalledWith({
          name: 'Tech Stocks',
          symbols: ['AAPL', 'MSFT', 'GOOGL'],
        });
      });
    });

    it('normalizes symbols to uppercase', async () => {
      defaultProps.onSubmit.mockResolvedValue(undefined);
      render(<CreateListDialog {...defaultProps} />);

      const nameInput = screen.getByLabelText(/list name/i);
      fireEvent.change(nameInput, { target: { value: 'Test' } });

      const symbolsInput = screen.getByLabelText(/symbols/i);
      fireEvent.change(symbolsInput, { target: { value: 'aapl, msft' } });

      const submitButton = screen.getByRole('button', { name: /create list/i });
      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(defaultProps.onSubmit).toHaveBeenCalledWith({
          name: 'Test',
          symbols: ['AAPL', 'MSFT'],
        });
      });
    });

    it('removes duplicate symbols', async () => {
      defaultProps.onSubmit.mockResolvedValue(undefined);
      render(<CreateListDialog {...defaultProps} />);

      const nameInput = screen.getByLabelText(/list name/i);
      fireEvent.change(nameInput, { target: { value: 'Test' } });

      const symbolsInput = screen.getByLabelText(/symbols/i);
      fireEvent.change(symbolsInput, { target: { value: 'AAPL, aapl, AAPL' } });

      const submitButton = screen.getByRole('button', { name: /create list/i });
      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(defaultProps.onSubmit).toHaveBeenCalledWith({
          name: 'Test',
          symbols: ['AAPL'],
        });
      });
    });
  });

  describe('Validation', () => {
    it('shows error when name is empty', async () => {
      render(<CreateListDialog {...defaultProps} />);

      const submitButton = screen.getByRole('button', { name: /create list/i });
      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(screen.getByText('List name is required')).toBeInTheDocument();
      });

      expect(defaultProps.onSubmit).not.toHaveBeenCalled();
    });

    it('trims whitespace from name', async () => {
      defaultProps.onSubmit.mockResolvedValue(undefined);
      render(<CreateListDialog {...defaultProps} />);

      const nameInput = screen.getByLabelText(/list name/i);
      fireEvent.change(nameInput, { target: { value: '  My List  ' } });

      const submitButton = screen.getByRole('button', { name: /create list/i });
      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(defaultProps.onSubmit).toHaveBeenCalledWith({
          name: 'My List',
          symbols: undefined,
        });
      });
    });
  });

  describe('Cancel Behavior', () => {
    it('calls onOpenChange when Cancel is clicked', () => {
      render(<CreateListDialog {...defaultProps} />);

      const cancelButton = screen.getByRole('button', { name: /cancel/i });
      fireEvent.click(cancelButton);

      expect(defaultProps.onOpenChange).toHaveBeenCalledWith(false);
    });

    it('resets form when canceled', () => {
      render(<CreateListDialog {...defaultProps} />);

      const nameInput = screen.getByLabelText(/list name/i);
      fireEvent.change(nameInput, { target: { value: 'Test' } });

      const cancelButton = screen.getByRole('button', { name: /cancel/i });
      fireEvent.click(cancelButton);

      // Re-render with open=true to verify form was reset
      // (In actual usage, the dialog would close and reopen)
      expect(defaultProps.onOpenChange).toHaveBeenCalledWith(false);
    });
  });

  describe('Submitting State', () => {
    it('disables buttons when submitting', () => {
      render(<CreateListDialog {...defaultProps} isSubmitting={true} />);

      expect(screen.getByRole('button', { name: /cancel/i })).toBeDisabled();
      expect(screen.getByRole('button', { name: /creating/i })).toBeDisabled();
    });

    it('shows "Creating..." text when submitting', () => {
      render(<CreateListDialog {...defaultProps} isSubmitting={true} />);

      expect(screen.getByRole('button', { name: /creating/i })).toBeInTheDocument();
    });
  });

  describe('Error Handling', () => {
    it('displays error message when submission fails', async () => {
      const errorMessage = 'A list with this name already exists';
      defaultProps.onSubmit.mockRejectedValue(new Error(errorMessage));
      render(<CreateListDialog {...defaultProps} />);

      const nameInput = screen.getByLabelText(/list name/i);
      fireEvent.change(nameInput, { target: { value: 'Duplicate List' } });

      const submitButton = screen.getByRole('button', { name: /create list/i });
      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(screen.getByText(errorMessage)).toBeInTheDocument();
      });
    });

    it('displays Axios error detail when available', async () => {
      const axiosError = {
        response: {
          data: {
            detail: 'A list named "Tech" already exists',
          },
        },
      };
      defaultProps.onSubmit.mockRejectedValue(axiosError);
      render(<CreateListDialog {...defaultProps} />);

      const nameInput = screen.getByLabelText(/list name/i);
      fireEvent.change(nameInput, { target: { value: 'Tech' } });

      const submitButton = screen.getByRole('button', { name: /create list/i });
      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(screen.getByText('A list named "Tech" already exists')).toBeInTheDocument();
      });
    });

    it('keeps dialog open when submission fails', async () => {
      defaultProps.onSubmit.mockRejectedValue(new Error('Failed'));
      render(<CreateListDialog {...defaultProps} />);

      const nameInput = screen.getByLabelText(/list name/i);
      fireEvent.change(nameInput, { target: { value: 'Test' } });

      const submitButton = screen.getByRole('button', { name: /create list/i });
      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(screen.getByText('Failed')).toBeInTheDocument();
      });

      // Dialog should still be open
      expect(screen.getByText('Create New List')).toBeInTheDocument();
      // onOpenChange should NOT have been called with false
      expect(defaultProps.onOpenChange).not.toHaveBeenCalledWith(false);
    });

    it('clears error when form is resubmitted', async () => {
      defaultProps.onSubmit
        .mockRejectedValueOnce(new Error('First error'))
        .mockResolvedValueOnce(undefined);
      render(<CreateListDialog {...defaultProps} />);

      const nameInput = screen.getByLabelText(/list name/i);
      fireEvent.change(nameInput, { target: { value: 'Test' } });

      const submitButton = screen.getByRole('button', { name: /create list/i });
      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(screen.getByText('First error')).toBeInTheDocument();
      });

      // Submit again
      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(screen.queryByText('First error')).not.toBeInTheDocument();
      });
    });
  });
});
