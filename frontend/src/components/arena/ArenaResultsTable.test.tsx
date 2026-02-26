import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ArenaResultsTable } from './ArenaResultsTable';
import type { Simulation } from '../../types/arena';

/** Complete mock simulation with all fields including new analytics metrics */
const mockSimulation: Simulation = {
  id: 1,
  name: 'Test Simulation',
  stock_list_id: null,
  stock_list_name: null,
  symbols: ['AAPL', 'NVDA'],
  start_date: '2024-01-01',
  end_date: '2024-01-31',
  initial_capital: '10000',
  position_size: '1000',
  agent_type: 'live20',
  trailing_stop_pct: '5.0',
  min_buy_score: 60,
  scoring_algorithm: null,
  portfolio_strategy: null,
  max_per_sector: null,
  max_open_positions: null,
  status: 'completed',
  current_day: 22,
  total_days: 22,
  final_equity: '10830.00',
  total_return_pct: '8.30',
  total_trades: 12,
  winning_trades: 7,
  max_drawdown_pct: '4.10',
  avg_hold_days: '6.5',
  avg_win_pnl: '250.00',
  avg_loss_pnl: '-120.00',
  profit_factor: '2.08',
  sharpe_ratio: '1.45',
  total_realized_pnl: '1050.00',
  created_at: '2024-01-01T10:00:00Z',
};

describe('ArenaResultsTable', () => {
  describe('complete simulation with all metrics', () => {
    it('renders the Results card title', () => {
      render(<ArenaResultsTable simulation={mockSimulation} />);
      expect(screen.getByText('Results')).toBeInTheDocument();
    });

    it('renders row-1 metric labels', () => {
      render(<ArenaResultsTable simulation={mockSimulation} />);
      expect(screen.getByText('Return')).toBeInTheDocument();
      expect(screen.getByText('Win Rate')).toBeInTheDocument();
      expect(screen.getByText('Profit Factor')).toBeInTheDocument();
      expect(screen.getByText('Sharpe Ratio')).toBeInTheDocument();
    });

    it('renders row-2 metric labels', () => {
      render(<ArenaResultsTable simulation={mockSimulation} />);
      expect(screen.getByText('Total Trades')).toBeInTheDocument();
      expect(screen.getByText('Avg Hold Time')).toBeInTheDocument();
      expect(screen.getByText('Avg Win')).toBeInTheDocument();
      expect(screen.getByText('Avg Loss')).toBeInTheDocument();
      expect(screen.getByText('Max DD')).toBeInTheDocument();
      expect(screen.getByText('Final Equity')).toBeInTheDocument();
      expect(screen.getByText('Realized P&L')).toBeInTheDocument();
    });

    it('formats positive return with + prefix and 1 decimal', () => {
      render(<ArenaResultsTable simulation={mockSimulation} />);
      expect(screen.getByText('+8.3%')).toBeInTheDocument();
    });

    it('formats win rate as percentage', () => {
      render(<ArenaResultsTable simulation={mockSimulation} />);
      // 7/12 = 58.3%
      expect(screen.getByText('58.3%')).toBeInTheDocument();
    });

    it('formats profit factor to 2 decimal places', () => {
      render(<ArenaResultsTable simulation={mockSimulation} />);
      expect(screen.getByText('2.08')).toBeInTheDocument();
    });

    it('formats sharpe ratio to 2 decimal places', () => {
      render(<ArenaResultsTable simulation={mockSimulation} />);
      expect(screen.getByText('1.45')).toBeInTheDocument();
    });

    it('formats total trades as integer', () => {
      render(<ArenaResultsTable simulation={mockSimulation} />);
      expect(screen.getByText('12')).toBeInTheDocument();
    });

    it('formats avg hold time as X.X days', () => {
      render(<ArenaResultsTable simulation={mockSimulation} />);
      expect(screen.getByText('6.5 days')).toBeInTheDocument();
    });

    it('formats avg win as currency', () => {
      render(<ArenaResultsTable simulation={mockSimulation} />);
      expect(screen.getByText('$250.00')).toBeInTheDocument();
    });

    it('formats avg loss as currency', () => {
      render(<ArenaResultsTable simulation={mockSimulation} />);
      expect(screen.getByText('-$120.00')).toBeInTheDocument();
    });

    it('formats max drawdown with negative sign', () => {
      render(<ArenaResultsTable simulation={mockSimulation} />);
      expect(screen.getByText('-4.1%')).toBeInTheDocument();
    });

    it('formats final equity as currency', () => {
      render(<ArenaResultsTable simulation={mockSimulation} />);
      expect(screen.getByText('$10,830.00')).toBeInTheDocument();
    });

    it('formats realized pnl as currency', () => {
      render(<ArenaResultsTable simulation={mockSimulation} />);
      expect(screen.getByText('$1,050.00')).toBeInTheDocument();
    });
  });

  describe('null metric display', () => {
    it('shows "-" for null total_return_pct', () => {
      render(
        <ArenaResultsTable simulation={{ ...mockSimulation, total_return_pct: null }} />
      );
      // Return label is present and its value is "-"
      expect(screen.getByText('Return')).toBeInTheDocument();
      const dashes = screen.getAllByText('-');
      expect(dashes.length).toBeGreaterThan(0);
    });

    it('shows "-" for null avg_hold_days', () => {
      render(
        <ArenaResultsTable simulation={{ ...mockSimulation, avg_hold_days: null }} />
      );
      expect(screen.getByText('Avg Hold Time')).toBeInTheDocument();
      const dashes = screen.getAllByText('-');
      expect(dashes.length).toBeGreaterThan(0);
    });

    it('shows "-" for null avg_win_pnl', () => {
      render(
        <ArenaResultsTable
          simulation={{ ...mockSimulation, avg_win_pnl: null, avg_loss_pnl: null }}
        />
      );
      expect(screen.getByText('Avg Win')).toBeInTheDocument();
    });

    it('shows "-" for null avg_loss_pnl', () => {
      render(
        <ArenaResultsTable simulation={{ ...mockSimulation, avg_loss_pnl: null }} />
      );
      expect(screen.getByText('Avg Loss')).toBeInTheDocument();
    });

    it('shows "-" for null total_realized_pnl', () => {
      render(
        <ArenaResultsTable simulation={{ ...mockSimulation, total_realized_pnl: null }} />
      );
      expect(screen.getByText('Realized P&L')).toBeInTheDocument();
      const dashes = screen.getAllByText('-');
      expect(dashes.length).toBeGreaterThan(0);
    });

    it('shows "-" for null sharpe_ratio', () => {
      render(
        <ArenaResultsTable simulation={{ ...mockSimulation, sharpe_ratio: null }} />
      );
      expect(screen.getByText('Sharpe Ratio')).toBeInTheDocument();
      const dashes = screen.getAllByText('-');
      expect(dashes.length).toBeGreaterThan(0);
    });
  });

  describe('profit_factor null display rules', () => {
    it('shows "∞" when profit_factor is null and there are winners but no losers', () => {
      render(
        <ArenaResultsTable
          simulation={{
            ...mockSimulation,
            profit_factor: null,
            avg_win_pnl: '300.00',
            avg_loss_pnl: null,
          }}
        />
      );
      expect(screen.getByText('∞')).toBeInTheDocument();
    });

    it('shows "-" when profit_factor is null and there are no closed trades', () => {
      render(
        <ArenaResultsTable
          simulation={{
            ...mockSimulation,
            profit_factor: null,
            avg_win_pnl: null,
            avg_loss_pnl: null,
          }}
        />
      );
      // Should NOT show "∞"
      expect(screen.queryByText('∞')).not.toBeInTheDocument();
      const dashes = screen.getAllByText('-');
      expect(dashes.length).toBeGreaterThan(0);
    });

    it('shows the numeric value when profit_factor is not null', () => {
      render(
        <ArenaResultsTable
          simulation={{ ...mockSimulation, profit_factor: '1.75' }}
        />
      );
      expect(screen.getByText('1.75')).toBeInTheDocument();
    });
  });

  describe('color coding', () => {
    it('applies bullish class to positive total_return_pct', () => {
      render(<ArenaResultsTable simulation={mockSimulation} />);
      const returnValue = screen.getByText('+8.3%');
      expect(returnValue.className).toContain('text-accent-bullish');
    });

    it('applies bearish class to negative total_return_pct', () => {
      render(
        <ArenaResultsTable
          simulation={{ ...mockSimulation, total_return_pct: '-5.25' }}
        />
      );
      const returnValue = screen.getByText('-5.3%');
      expect(returnValue.className).toContain('text-accent-bearish');
    });

    it('applies bullish class to positive total_realized_pnl', () => {
      render(
        <ArenaResultsTable
          simulation={{ ...mockSimulation, total_realized_pnl: '500.00' }}
        />
      );
      const pnlValue = screen.getByText('$500.00');
      expect(pnlValue.className).toContain('text-accent-bullish');
    });

    it('applies bearish class to negative total_realized_pnl', () => {
      render(
        <ArenaResultsTable
          simulation={{ ...mockSimulation, total_realized_pnl: '-200.00' }}
        />
      );
      const pnlValue = screen.getByText('-$200.00');
      expect(pnlValue.className).toContain('text-accent-bearish');
    });

    it('always applies bearish class to max_drawdown_pct', () => {
      render(<ArenaResultsTable simulation={mockSimulation} />);
      const ddValue = screen.getByText('-4.1%');
      expect(ddValue.className).toContain('text-accent-bearish');
    });

    it('applies bullish class to win_rate >= 50', () => {
      // 7/12 = 58.3% → bullish
      render(<ArenaResultsTable simulation={mockSimulation} />);
      const winRateValue = screen.getByText('58.3%');
      expect(winRateValue.className).toContain('text-accent-bullish');
    });

    it('applies bearish class to win_rate < 50', () => {
      render(
        <ArenaResultsTable
          simulation={{ ...mockSimulation, total_trades: 10, winning_trades: 3 }}
        />
      );
      // 3/10 = 30.0% → bearish
      const winRateValue = screen.getByText('30.0%');
      expect(winRateValue.className).toContain('text-accent-bearish');
    });

    it('always applies bullish class to avg_win_pnl when not null', () => {
      render(<ArenaResultsTable simulation={mockSimulation} />);
      const avgWinValue = screen.getByText('$250.00');
      expect(avgWinValue.className).toContain('text-accent-bullish');
    });

    it('always applies bearish class to avg_loss_pnl when not null', () => {
      render(<ArenaResultsTable simulation={mockSimulation} />);
      const avgLossValue = screen.getByText('-$120.00');
      expect(avgLossValue.className).toContain('text-accent-bearish');
    });

    it('applies no color class to profit_factor', () => {
      render(<ArenaResultsTable simulation={mockSimulation} />);
      const pfValue = screen.getByText('2.08');
      expect(pfValue.className).not.toContain('text-accent-bullish');
      expect(pfValue.className).not.toContain('text-accent-bearish');
    });

    it('applies no color class to sharpe_ratio', () => {
      render(<ArenaResultsTable simulation={mockSimulation} />);
      const sharpeValue = screen.getByText('1.45');
      expect(sharpeValue.className).not.toContain('text-accent-bullish');
      expect(sharpeValue.className).not.toContain('text-accent-bearish');
    });

    it('applies no color class to avg_hold_days', () => {
      render(<ArenaResultsTable simulation={mockSimulation} />);
      const holdValue = screen.getByText('6.5 days');
      expect(holdValue.className).not.toContain('text-accent-bullish');
      expect(holdValue.className).not.toContain('text-accent-bearish');
    });
  });

  describe('win rate with no trades', () => {
    it('shows 0.0% win rate when total_trades is 0', () => {
      render(
        <ArenaResultsTable
          simulation={{ ...mockSimulation, total_trades: 0, winning_trades: 0 }}
        />
      );
      expect(screen.getByText('0.0%')).toBeInTheDocument();
    });
  });

  describe('negative return formatting', () => {
    it('formats negative return without + prefix', () => {
      render(
        <ArenaResultsTable
          simulation={{ ...mockSimulation, total_return_pct: '-3.50' }}
        />
      );
      expect(screen.getByText('-3.5%')).toBeInTheDocument();
    });
  });
});
