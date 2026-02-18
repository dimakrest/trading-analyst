import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ArenaResultsTable } from './ArenaResultsTable';
import type { Simulation } from '../../types/arena';

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
  final_equity: '10830',
  total_return_pct: '8.30',
  total_trades: 12,
  winning_trades: 7,
  max_drawdown_pct: '4.10',
  created_at: '2024-01-01T10:00:00Z',
};

describe('ArenaResultsTable', () => {
  it('should render results table with headers', () => {
    render(<ArenaResultsTable simulation={mockSimulation} />);

    expect(screen.getByText('Results')).toBeInTheDocument();
    expect(screen.getByText('Agent')).toBeInTheDocument();
    expect(screen.getByText('Return')).toBeInTheDocument();
    expect(screen.getByText('Trades')).toBeInTheDocument();
    expect(screen.getByText('Win Rate')).toBeInTheDocument();
    expect(screen.getByText('Max DD')).toBeInTheDocument();
    expect(screen.getByText('Final Equity')).toBeInTheDocument();
  });

  it('should display agent name', () => {
    render(<ArenaResultsTable simulation={mockSimulation} />);

    expect(screen.getByText('Live20')).toBeInTheDocument();
  });

  it('should display positive return with plus sign', () => {
    render(<ArenaResultsTable simulation={mockSimulation} />);

    expect(screen.getByText('+8.30%')).toBeInTheDocument();
  });

  it('should display negative return without plus sign', () => {
    const negativeSimulation: Simulation = {
      ...mockSimulation,
      total_return_pct: '-5.25',
    };
    render(<ArenaResultsTable simulation={negativeSimulation} />);

    expect(screen.getByText('-5.25%')).toBeInTheDocument();
  });

  it('should display total trades', () => {
    render(<ArenaResultsTable simulation={mockSimulation} />);

    expect(screen.getByText('12')).toBeInTheDocument();
  });

  it('should calculate and display win rate', () => {
    render(<ArenaResultsTable simulation={mockSimulation} />);

    // 7/12 = 58.3%
    expect(screen.getByText('58.3%')).toBeInTheDocument();
  });

  it('should display max drawdown with negative sign', () => {
    render(<ArenaResultsTable simulation={mockSimulation} />);

    expect(screen.getByText('-4.10%')).toBeInTheDocument();
  });

  it('should display formatted final equity', () => {
    render(<ArenaResultsTable simulation={mockSimulation} />);

    expect(screen.getByText('$10,830.00')).toBeInTheDocument();
  });

  it('should show dash for null return', () => {
    const noReturnSimulation: Simulation = {
      ...mockSimulation,
      total_return_pct: null,
    };
    render(<ArenaResultsTable simulation={noReturnSimulation} />);

    // Return column should show dash
    const dashes = screen.getAllByText('-');
    expect(dashes.length).toBeGreaterThan(0);
  });

  it('should show dash for null max drawdown', () => {
    const noDrawdownSimulation: Simulation = {
      ...mockSimulation,
      max_drawdown_pct: null,
    };
    render(<ArenaResultsTable simulation={noDrawdownSimulation} />);

    // Max DD column should show dash
    const dashes = screen.getAllByText('-');
    expect(dashes.length).toBeGreaterThan(0);
  });

  it('should show dash for null final equity', () => {
    const noEquitySimulation: Simulation = {
      ...mockSimulation,
      final_equity: null,
    };
    render(<ArenaResultsTable simulation={noEquitySimulation} />);

    // Final equity column should show dash
    const dashes = screen.getAllByText('-');
    expect(dashes.length).toBeGreaterThan(0);
  });

  it('should show 0.0% win rate when no trades', () => {
    const noTradesSimulation: Simulation = {
      ...mockSimulation,
      total_trades: 0,
      winning_trades: 0,
    };
    render(<ArenaResultsTable simulation={noTradesSimulation} />);

    expect(screen.getByText('0.0%')).toBeInTheDocument();
  });
});
