import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { ArenaPortfolioSetupsTab } from './ArenaPortfolioSetupsTab';
import { portfolioConfigService } from '../../services/portfolioConfigService';

vi.mock('../../services/portfolioConfigService', () => ({
  portfolioConfigService: {
    getConfigs: vi.fn(),
    createConfig: vi.fn(),
    updateConfig: vi.fn(),
    deleteConfig: vi.fn(),
  },
}));

vi.mock('sonner', () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}));

describe('ArenaPortfolioSetupsTab', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('loads and renders saved setups', async () => {
    vi.mocked(portfolioConfigService.getConfigs).mockResolvedValue({
      items: [
        {
          id: 1,
          name: 'Conservative',
          portfolio_strategy: 'score_sector_low_atr',
          position_size: 1200,
          min_buy_score: 65,
          trailing_stop_pct: 7.5,
          max_per_sector: 1,
          max_open_positions: 4,
        },
      ],
      total: 1,
    });

    render(<ArenaPortfolioSetupsTab />);

    await waitFor(() => {
      expect(screen.getByText('Conservative')).toBeInTheDocument();
    });
    expect(screen.getByText(/score \+ low atr/i)).toBeInTheDocument();
    expect(screen.getByText(/size: \$1200/i)).toBeInTheDocument();
    expect(screen.getByText(/min score: 65/i)).toBeInTheDocument();
    expect(screen.getByText(/stop: 7.5%/i)).toBeInTheDocument();
  });

  it('shows error state when loading fails', async () => {
    vi.mocked(portfolioConfigService.getConfigs).mockRejectedValue(new Error('boom'));

    render(<ArenaPortfolioSetupsTab />);

    await waitFor(() => {
      expect(screen.getByText(/boom/i)).toBeInTheDocument();
    });
    expect(screen.getByRole('button', { name: /retry/i })).toBeInTheDocument();
  });
});
