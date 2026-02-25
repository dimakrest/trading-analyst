import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { SetupSimForm } from './SetupSimForm';

describe('SetupSimForm', () => {
  const mockOnSubmit = vi.fn();

  beforeEach(() => {
    mockOnSubmit.mockClear();
  });

  // ---------------------------------------------------------------------------
  // Initial render
  // ---------------------------------------------------------------------------

  describe('initial render', () => {
    it('renders the card title', () => {
      render(<SetupSimForm onSubmit={mockOnSubmit} isLoading={false} />);
      expect(screen.getByText('Setup Simulation')).toBeInTheDocument();
    });

    it('renders end date input', () => {
      render(<SetupSimForm onSubmit={mockOnSubmit} isLoading={false} />);
      expect(screen.getByLabelText(/end date/i)).toBeInTheDocument();
    });

    it('renders one setup row by default', () => {
      render(<SetupSimForm onSubmit={mockOnSubmit} isLoading={false} />);
      expect(screen.getByTestId('setup-row-0')).toBeInTheDocument();
      expect(screen.queryByTestId('setup-row-1')).not.toBeInTheDocument();
    });

    it('renders the Run Simulation button as disabled when form is empty', () => {
      render(<SetupSimForm onSubmit={mockOnSubmit} isLoading={false} />);
      const btn = screen.getByTestId('run-simulation-btn');
      expect(btn).toBeDisabled();
    });

    it('does not render a remove button when only 1 row exists', () => {
      render(<SetupSimForm onSubmit={mockOnSubmit} isLoading={false} />);
      expect(screen.queryByRole('button', { name: /remove setup 1/i })).not.toBeInTheDocument();
    });
  });

  // ---------------------------------------------------------------------------
  // Add / remove rows
  // ---------------------------------------------------------------------------

  describe('add and remove rows', () => {
    it('adds a new row when "Add Setup" is clicked', () => {
      render(<SetupSimForm onSubmit={mockOnSubmit} isLoading={false} />);

      fireEvent.click(screen.getByRole('button', { name: /add setup/i }));

      expect(screen.getByTestId('setup-row-0')).toBeInTheDocument();
      expect(screen.getByTestId('setup-row-1')).toBeInTheDocument();
    });

    it('shows remove button when more than 1 row exists', () => {
      render(<SetupSimForm onSubmit={mockOnSubmit} isLoading={false} />);
      fireEvent.click(screen.getByRole('button', { name: /add setup/i }));

      expect(screen.getByRole('button', { name: /remove setup 1/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /remove setup 2/i })).toBeInTheDocument();
    });

    it('removes a row when the remove button is clicked', () => {
      render(<SetupSimForm onSubmit={mockOnSubmit} isLoading={false} />);
      fireEvent.click(screen.getByRole('button', { name: /add setup/i }));

      expect(screen.getByTestId('setup-row-1')).toBeInTheDocument();

      fireEvent.click(screen.getByRole('button', { name: /remove setup 2/i }));

      expect(screen.queryByTestId('setup-row-1')).not.toBeInTheDocument();
    });

    it('hides remove button again when back to 1 row', () => {
      render(<SetupSimForm onSubmit={mockOnSubmit} isLoading={false} />);
      fireEvent.click(screen.getByRole('button', { name: /add setup/i }));
      fireEvent.click(screen.getByRole('button', { name: /remove setup 2/i }));

      expect(screen.queryByRole('button', { name: /remove setup 1/i })).not.toBeInTheDocument();
    });
  });

  // ---------------------------------------------------------------------------
  // Form validation
  // ---------------------------------------------------------------------------

  describe('form validation', () => {
    /** Helper: fill in a valid setup row and end date */
    const fillValidForm = () => {
      const row = screen.getByTestId('setup-row-0');

      fireEvent.change(within(row).getByLabelText(/symbol/i), {
        target: { value: 'AAPL' },
      });
      fireEvent.change(within(row).getByLabelText(/start date/i), {
        target: { value: '2024-01-01' },
      });
      fireEvent.change(within(row).getByLabelText(/entry price/i), {
        target: { value: '150' },
      });
      fireEvent.change(within(row).getByLabelText(/stop loss day 1/i), {
        target: { value: '145' },
      });
      fireEvent.change(within(row).getByLabelText(/trailing stop/i), {
        target: { value: '5' },
      });

      // End date in the past
      fireEvent.change(screen.getByLabelText(/end date/i), {
        target: { value: '2024-06-01' },
      });
    };

    it('enables submit when all fields are valid', () => {
      render(<SetupSimForm onSubmit={mockOnSubmit} isLoading={false} />);
      fillValidForm();
      expect(screen.getByTestId('run-simulation-btn')).not.toBeDisabled();
    });

    it('keeps submit disabled when symbol is missing', () => {
      render(<SetupSimForm onSubmit={mockOnSubmit} isLoading={false} />);
      fillValidForm();

      const row = screen.getByTestId('setup-row-0');
      fireEvent.change(within(row).getByLabelText(/symbol/i), {
        target: { value: '' },
      });

      expect(screen.getByTestId('run-simulation-btn')).toBeDisabled();
    });

    it('keeps submit disabled when entry price is 0', () => {
      render(<SetupSimForm onSubmit={mockOnSubmit} isLoading={false} />);
      fillValidForm();

      const row = screen.getByTestId('setup-row-0');
      fireEvent.change(within(row).getByLabelText(/entry price/i), {
        target: { value: '0' },
      });

      expect(screen.getByTestId('run-simulation-btn')).toBeDisabled();
    });

    it('keeps submit disabled when stop loss >= entry price', () => {
      render(<SetupSimForm onSubmit={mockOnSubmit} isLoading={false} />);
      fillValidForm();

      const row = screen.getByTestId('setup-row-0');
      fireEvent.change(within(row).getByLabelText(/stop loss day 1/i), {
        target: { value: '150' }, // equal to entry price
      });

      expect(screen.getByTestId('run-simulation-btn')).toBeDisabled();
    });

    it('keeps submit disabled when trailing stop is 0', () => {
      render(<SetupSimForm onSubmit={mockOnSubmit} isLoading={false} />);
      fillValidForm();

      const row = screen.getByTestId('setup-row-0');
      fireEvent.change(within(row).getByLabelText(/trailing stop/i), {
        target: { value: '0' },
      });

      expect(screen.getByTestId('run-simulation-btn')).toBeDisabled();
    });

    it('keeps submit disabled when trailing stop is 100', () => {
      render(<SetupSimForm onSubmit={mockOnSubmit} isLoading={false} />);
      fillValidForm();

      const row = screen.getByTestId('setup-row-0');
      fireEvent.change(within(row).getByLabelText(/trailing stop/i), {
        target: { value: '100' },
      });

      expect(screen.getByTestId('run-simulation-btn')).toBeDisabled();
    });

    it('keeps submit disabled when end date is in the future', () => {
      render(<SetupSimForm onSubmit={mockOnSubmit} isLoading={false} />);
      fillValidForm();

      // Set end date to a far-future date
      fireEvent.change(screen.getByLabelText(/end date/i), {
        target: { value: '2099-01-01' },
      });

      expect(screen.getByTestId('run-simulation-btn')).toBeDisabled();
    });

    it('keeps submit disabled when start date >= end date', () => {
      render(<SetupSimForm onSubmit={mockOnSubmit} isLoading={false} />);
      fillValidForm();

      const row = screen.getByTestId('setup-row-0');
      fireEvent.change(within(row).getByLabelText(/start date/i), {
        target: { value: '2024-06-01' }, // same as end date
      });

      expect(screen.getByTestId('run-simulation-btn')).toBeDisabled();
    });

    it('keeps submit disabled when end date is empty', () => {
      render(<SetupSimForm onSubmit={mockOnSubmit} isLoading={false} />);
      fillValidForm();

      fireEvent.change(screen.getByLabelText(/end date/i), {
        target: { value: '' },
      });

      expect(screen.getByTestId('run-simulation-btn')).toBeDisabled();
    });

    it('shows error when stop loss >= entry price', () => {
      render(<SetupSimForm onSubmit={mockOnSubmit} isLoading={false} />);

      const row = screen.getByTestId('setup-row-0');
      fireEvent.change(within(row).getByLabelText(/entry price/i), {
        target: { value: '150' },
      });
      fireEvent.change(within(row).getByLabelText(/stop loss day 1/i), {
        target: { value: '155' },
      });

      expect(screen.getByText(/must be below entry price/i)).toBeInTheDocument();
    });
  });

  // ---------------------------------------------------------------------------
  // Submit behavior
  // ---------------------------------------------------------------------------

  describe('submit behavior', () => {
    it('calls onSubmit with correct payload when form is valid', async () => {
      const user = userEvent.setup();
      render(<SetupSimForm onSubmit={mockOnSubmit} isLoading={false} />);

      const row = screen.getByTestId('setup-row-0');

      await user.clear(within(row).getByLabelText(/symbol/i));
      await user.type(within(row).getByLabelText(/symbol/i), 'aapl');

      fireEvent.change(within(row).getByLabelText(/start date/i), {
        target: { value: '2024-01-01' },
      });
      fireEvent.change(within(row).getByLabelText(/entry price/i), {
        target: { value: '150' },
      });
      fireEvent.change(within(row).getByLabelText(/stop loss day 1/i), {
        target: { value: '145' },
      });
      fireEvent.change(within(row).getByLabelText(/trailing stop/i), {
        target: { value: '5' },
      });
      fireEvent.change(screen.getByLabelText(/end date/i), {
        target: { value: '2024-06-01' },
      });

      await user.click(screen.getByTestId('run-simulation-btn'));

      expect(mockOnSubmit).toHaveBeenCalledOnce();
      const call = mockOnSubmit.mock.calls[0][0];
      expect(call.end_date).toBe('2024-06-01');
      expect(call.setups).toHaveLength(1);
      expect(call.setups[0].symbol).toBe('AAPL'); // auto-uppercased
      expect(call.setups[0].entry_price).toBe('150');
      expect(call.setups[0].stop_loss_day1).toBe('145');
      expect(call.setups[0].trailing_stop_pct).toBe('5');
      expect(call.setups[0].start_date).toBe('2024-01-01');
    });

    it('does not call onSubmit when button is disabled', async () => {
      const user = userEvent.setup();
      render(<SetupSimForm onSubmit={mockOnSubmit} isLoading={false} />);

      // Button is disabled with empty form
      const btn = screen.getByTestId('run-simulation-btn');
      expect(btn).toBeDisabled();
      await user.click(btn);

      expect(mockOnSubmit).not.toHaveBeenCalled();
    });

    it('disables all inputs and buttons when isLoading is true', () => {
      render(<SetupSimForm onSubmit={mockOnSubmit} isLoading={true} />);

      expect(screen.getByLabelText(/end date/i)).toBeDisabled();
      expect(screen.getByRole('button', { name: /add setup/i })).toBeDisabled();
      expect(screen.getByTestId('run-simulation-btn')).toBeDisabled();
    });

    it('shows "Running..." label when isLoading is true', () => {
      render(<SetupSimForm onSubmit={mockOnSubmit} isLoading={true} />);
      expect(screen.getByText(/running\.\.\./i)).toBeInTheDocument();
    });

    it('includes all rows in the submission when multiple rows are filled', async () => {
      const user = userEvent.setup();
      render(<SetupSimForm onSubmit={mockOnSubmit} isLoading={false} />);

      // Fill row 0
      const row0 = screen.getByTestId('setup-row-0');
      await user.type(within(row0).getByLabelText(/symbol/i), 'AAPL');
      fireEvent.change(within(row0).getByLabelText(/start date/i), { target: { value: '2024-01-01' } });
      fireEvent.change(within(row0).getByLabelText(/entry price/i), { target: { value: '150' } });
      fireEvent.change(within(row0).getByLabelText(/stop loss day 1/i), { target: { value: '145' } });
      fireEvent.change(within(row0).getByLabelText(/trailing stop/i), { target: { value: '5' } });

      // Add row 1
      await user.click(screen.getByRole('button', { name: /add setup/i }));
      const row1 = screen.getByTestId('setup-row-1');
      await user.type(within(row1).getByLabelText(/symbol/i), 'MSFT');
      fireEvent.change(within(row1).getByLabelText(/start date/i), { target: { value: '2024-02-01' } });
      fireEvent.change(within(row1).getByLabelText(/entry price/i), { target: { value: '400' } });
      fireEvent.change(within(row1).getByLabelText(/stop loss day 1/i), { target: { value: '390' } });
      fireEvent.change(within(row1).getByLabelText(/trailing stop/i), { target: { value: '5' } });

      // Set end date
      fireEvent.change(screen.getByLabelText(/end date/i), { target: { value: '2024-06-01' } });

      await user.click(screen.getByTestId('run-simulation-btn'));

      expect(mockOnSubmit).toHaveBeenCalledOnce();
      const call = mockOnSubmit.mock.calls[0][0];
      expect(call.setups).toHaveLength(2);
      expect(call.setups[0].symbol).toBe('AAPL');
      expect(call.setups[1].symbol).toBe('MSFT');
    });
  });
});
