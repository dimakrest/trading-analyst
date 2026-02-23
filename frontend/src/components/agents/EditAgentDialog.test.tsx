import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';

import type { AgentConfig } from '../../types/agentConfig';
import { EditAgentDialog } from './EditAgentDialog';

describe('EditAgentDialog', () => {
  const config: AgentConfig = {
    id: 7,
    name: 'Existing Agent',
    agent_type: 'live20',
    scoring_algorithm: 'cci',
    volume_score: 30,
    candle_pattern_score: 20,
    cci_score: 30,
    ma20_distance_score: 20,
  };

  const defaultProps = {
    config,
    open: true,
    onOpenChange: vi.fn(),
    onSubmit: vi.fn(),
    isSubmitting: false,
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('pre-fills score inputs from the selected agent config', () => {
    render(<EditAgentDialog {...defaultProps} />);

    expect(screen.getByDisplayValue('Existing Agent')).toBeInTheDocument();
    expect(screen.getByLabelText('Volume')).toHaveValue(30);
    expect(screen.getByLabelText('Candle Pattern')).toHaveValue(20);
    expect(screen.getByLabelText('CCI / Momentum')).toHaveValue(30);
    expect(screen.getByLabelText('MA20 Distance')).toHaveValue(20);
  });

  it('submits updated weighted signal payload', async () => {
    defaultProps.onSubmit.mockResolvedValue({
      ...config,
      name: 'Updated Agent',
      scoring_algorithm: 'rsi2',
      volume_score: 10,
      candle_pattern_score: 20,
      cci_score: 30,
      ma20_distance_score: 40,
    });

    render(<EditAgentDialog {...defaultProps} />);

    fireEvent.change(screen.getByLabelText(/agent name/i), {
      target: { value: '  Updated Agent  ' },
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

    fireEvent.click(screen.getByRole('button', { name: /save changes/i }));

    await waitFor(() => {
      expect(defaultProps.onSubmit).toHaveBeenCalledWith(7, {
        name: 'Updated Agent',
        scoring_algorithm: 'rsi2',
        volume_score: 10,
        candle_pattern_score: 20,
        cci_score: 30,
        ma20_distance_score: 40,
      });
    });
  });

  it('blocks submit when score total is invalid', async () => {
    render(<EditAgentDialog {...defaultProps} />);

    fireEvent.change(screen.getByLabelText('Volume'), { target: { value: '40' } });
    fireEvent.click(screen.getByRole('button', { name: /save changes/i }));

    await waitFor(() => {
      expect(
        screen.getByText('Signal scores must sum to 100 (current total: 110)')
      ).toBeInTheDocument();
    });
    expect(defaultProps.onSubmit).not.toHaveBeenCalled();
  });
});
