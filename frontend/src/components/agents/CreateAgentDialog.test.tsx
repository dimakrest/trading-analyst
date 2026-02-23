import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';

import { CreateAgentDialog } from './CreateAgentDialog';

describe('CreateAgentDialog', () => {
  const defaultProps = {
    open: true,
    onOpenChange: vi.fn(),
    onSubmit: vi.fn(),
    isSubmitting: false,
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('submits weighted signal payload when form is valid', async () => {
    defaultProps.onSubmit.mockResolvedValue({
      id: 1,
      name: 'Weighted Agent',
      agent_type: 'live20',
      scoring_algorithm: 'rsi2',
      volume_score: 10,
      candle_pattern_score: 20,
      cci_score: 30,
      ma20_distance_score: 40,
    });

    render(<CreateAgentDialog {...defaultProps} />);

    fireEvent.change(screen.getByLabelText(/agent name/i), {
      target: { value: '  Weighted Agent  ' },
    });
    fireEvent.click(
      screen.getByRole('radio', { name: /select rsi-2 algorithm/i })
    );
    fireEvent.change(screen.getByLabelText('Volume'), { target: { value: '10' } });
    fireEvent.change(screen.getByLabelText('Candle Pattern'), {
      target: { value: '20' },
    });
    fireEvent.change(screen.getByLabelText('CCI / Momentum'), {
      target: { value: '30' },
    });
    fireEvent.change(screen.getByLabelText('MA20 Distance'), {
      target: { value: '40' },
    });

    fireEvent.click(screen.getByRole('button', { name: /create agent/i }));

    await waitFor(() => {
      expect(defaultProps.onSubmit).toHaveBeenCalledWith({
        name: 'Weighted Agent',
        scoring_algorithm: 'rsi2',
        volume_score: 10,
        candle_pattern_score: 20,
        cci_score: 30,
        ma20_distance_score: 40,
      });
    });
  });

  it('blocks submit when scores do not sum to 100', async () => {
    render(<CreateAgentDialog {...defaultProps} />);

    fireEvent.change(screen.getByLabelText(/agent name/i), {
      target: { value: 'Bad Total' },
    });
    fireEvent.change(screen.getByLabelText('Volume'), { target: { value: '10' } });

    fireEvent.click(screen.getByRole('button', { name: /create agent/i }));

    await waitFor(() => {
      expect(
        screen.getByText('Signal scores must sum to 100 (current total: 85)')
      ).toBeInTheDocument();
    });
    expect(defaultProps.onSubmit).not.toHaveBeenCalled();
  });

  it('blocks submit when any score is not a valid integer', async () => {
    render(<CreateAgentDialog {...defaultProps} />);

    fireEvent.change(screen.getByLabelText(/agent name/i), {
      target: { value: 'Out of Range' },
    });
    fireEvent.change(screen.getByLabelText('Volume'), { target: { value: '' } });

    fireEvent.click(screen.getByRole('button', { name: /create agent/i }));

    await waitFor(() => {
      expect(
        screen.getByText('All signal scores must be integers between 0 and 100')
      ).toBeInTheDocument();
    });
    expect(defaultProps.onSubmit).not.toHaveBeenCalled();
  });
});
