import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Live20Loading } from './Live20Loading';

describe('Live20Loading', () => {
  describe('Cancel button rendering', () => {
    it('should render cancel button when onCancel is provided', () => {
      render(<Live20Loading symbolCount={10} onCancel={vi.fn()} />);

      const cancelButton = screen.getByRole('button', { name: /cancel analysis/i });
      expect(cancelButton).toBeInTheDocument();
      expect(cancelButton).not.toBeDisabled();
    });

    it('should not render cancel button when onCancel is not provided', () => {
      render(<Live20Loading symbolCount={10} />);

      const cancelButton = screen.queryByRole('button', { name: /cancel/i });
      expect(cancelButton).not.toBeInTheDocument();
    });
  });

  describe('Cancelling state', () => {
    it('should show "Cancelling..." state when isCancelling is true', () => {
      render(<Live20Loading symbolCount={10} onCancel={vi.fn()} isCancelling={true} />);

      const cancelButton = screen.getByRole('button', { name: /cancelling/i });
      expect(cancelButton).toBeInTheDocument();
      expect(cancelButton).toBeDisabled();
    });

    it('should disable button when isCancelling is true', () => {
      render(<Live20Loading symbolCount={10} onCancel={vi.fn()} isCancelling={true} />);

      const cancelButton = screen.getByRole('button');
      expect(cancelButton).toBeDisabled();
    });

    it('should show spinner icon when isCancelling is true', () => {
      const { container } = render(
        <Live20Loading symbolCount={10} onCancel={vi.fn()} isCancelling={true} />
      );

      // The Loader2 component from lucide-react has the animate-spin class
      const spinner = container.querySelector('.animate-spin');
      expect(spinner).toBeInTheDocument();
    });
  });

  describe('Results count display', () => {
    it('should display results count when provided (singular)', () => {
      render(<Live20Loading symbolCount={10} resultsCount={1} />);

      expect(screen.getByText(/1 setup found/i)).toBeInTheDocument();
    });

    it('should display results count when provided (plural)', () => {
      render(<Live20Loading symbolCount={10} resultsCount={5} />);

      expect(screen.getByText(/5 setups found/i)).toBeInTheDocument();
    });

    it('should not display results count when 0', () => {
      render(<Live20Loading symbolCount={10} resultsCount={0} />);

      expect(screen.queryByText(/setup/i)).not.toBeInTheDocument();
    });

    it('should not display results count when undefined', () => {
      render(<Live20Loading symbolCount={10} />);

      expect(screen.queryByText(/setup/i)).not.toBeInTheDocument();
    });
  });

  describe('Progress display', () => {
    it('should show determinate progress bar when processedCount is provided', () => {
      render(<Live20Loading symbolCount={10} processedCount={5} />);

      expect(screen.getByText(/5 of 10 processed \(50%\)/i)).toBeInTheDocument();
    });

    it('should calculate progress percentage correctly', () => {
      render(<Live20Loading symbolCount={100} processedCount={25} />);

      expect(screen.getByText(/25 of 100 processed \(25%\)/i)).toBeInTheDocument();
    });

    it('should show indeterminate progress when processedCount is not provided', () => {
      render(<Live20Loading symbolCount={10} />);

      // When no processedCount, should not show "X of Y processed"
      expect(screen.queryByText(/processed/i)).not.toBeInTheDocument();
    });

    it('should show indeterminate progress when processedCount is 0', () => {
      render(<Live20Loading symbolCount={10} processedCount={0} />);

      // Should not show progress text when processedCount is 0
      expect(screen.queryByText(/0 of 10 processed/i)).not.toBeInTheDocument();
    });
  });

  describe('Status messages', () => {
    it('should show "Queued for processing..." when status is pending', () => {
      render(<Live20Loading symbolCount={10} status="pending" />);

      expect(screen.getByText(/queued for processing/i)).toBeInTheDocument();
    });

    it('should show "Evaluating mean reversion criteria" when status is running', () => {
      render(<Live20Loading symbolCount={10} status="running" />);

      expect(screen.getByText(/evaluating mean reversion criteria/i)).toBeInTheDocument();
    });

    it('should show "Starting analysis..." when status is not provided', () => {
      render(<Live20Loading symbolCount={10} />);

      expect(screen.getByText(/starting analysis/i)).toBeInTheDocument();
    });

    it('should show "Starting analysis..." for unknown status', () => {
      render(<Live20Loading symbolCount={10} status="unknown" />);

      expect(screen.getByText(/starting analysis/i)).toBeInTheDocument();
    });
  });

  describe('Symbol count display', () => {
    it('should display singular form for 1 symbol', () => {
      render(<Live20Loading symbolCount={1} />);

      expect(screen.getByText(/analyzing 1 symbol/i)).toBeInTheDocument();
    });

    it('should display plural form for multiple symbols', () => {
      render(<Live20Loading symbolCount={10} />);

      expect(screen.getByText(/analyzing 10 symbols/i)).toBeInTheDocument();
    });
  });

  describe('Cancel button interaction', () => {
    it('should call onCancel when cancel button clicked', async () => {
      const onCancel = vi.fn();
      const user = userEvent.setup();

      render(<Live20Loading symbolCount={10} onCancel={onCancel} />);

      const cancelButton = screen.getByRole('button', { name: /cancel analysis/i });
      await user.click(cancelButton);

      expect(onCancel).toHaveBeenCalledTimes(1);
    });

    it('should not call onCancel when button is disabled', async () => {
      const onCancel = vi.fn();
      const user = userEvent.setup();

      render(<Live20Loading symbolCount={10} onCancel={onCancel} isCancelling={true} />);

      const cancelButton = screen.getByRole('button');

      // Attempt to click disabled button
      await user.click(cancelButton);

      // onCancel should not be called because button is disabled
      expect(onCancel).not.toHaveBeenCalled();
    });
  });

  describe('Complete loading state', () => {
    it('should display all elements together during active analysis', () => {
      render(
        <Live20Loading
          symbolCount={10}
          processedCount={5}
          status="running"
          resultsCount={3}
          onCancel={vi.fn()}
          isCancelling={false}
        />
      );

      // Should show all information
      expect(screen.getByText(/analyzing 10 symbols/i)).toBeInTheDocument();
      expect(screen.getByText(/5 of 10 processed \(50%\)/i)).toBeInTheDocument();
      expect(screen.getByText(/evaluating mean reversion criteria/i)).toBeInTheDocument();
      expect(screen.getByText(/3 setups found/i)).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /cancel analysis/i })).toBeInTheDocument();
    });

    it('should display cancelling state correctly', () => {
      render(
        <Live20Loading
          symbolCount={10}
          processedCount={5}
          status="running"
          resultsCount={3}
          onCancel={vi.fn()}
          isCancelling={true}
        />
      );

      // Should show cancelling button state
      const cancelButton = screen.getByRole('button', { name: /cancelling/i });
      expect(cancelButton).toBeInTheDocument();
      expect(cancelButton).toBeDisabled();
    });
  });
});
