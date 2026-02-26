import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ArenaPortfolio } from './ArenaPortfolio';
import type { Position, Simulation, Snapshot } from '../../types/arena';

const mockSimulation: Simulation = {
  id: 1,
  name: 'Test Simulation',
  stock_list_id: null,
  stock_list_name: null,
  symbols: ['AAPL', 'NVDA', 'TSLA'],
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
  status: 'running',
  current_day: 10,
  total_days: 22,
  final_equity: null,
  total_return_pct: null,
  total_trades: 3,
  winning_trades: 2,
  max_drawdown_pct: null,
  avg_hold_days: null,
  avg_win_pnl: null,
  avg_loss_pnl: null,
  profit_factor: null,
  sharpe_ratio: null,
  total_realized_pnl: null,
  created_at: '2024-01-01T10:00:00Z',
};

const mockSnapshot: Snapshot = {
  id: 1,
  snapshot_date: '2024-01-10',
  day_number: 9,
  cash: '7156.50',
  positions_value: '3673.50',
  total_equity: '10830.00',
  daily_pnl: '150.00',
  daily_return_pct: '1.40',
  cumulative_return_pct: '8.30',
  open_position_count: 3,
  decisions: {},
};

const mockPositions: Position[] = [
  {
    id: 1,
    symbol: 'AAPL',
    status: 'open',
    signal_date: '2024-01-05',
    entry_date: '2024-01-06',
    entry_price: '195.00',
    shares: 5,
    highest_price: '198.50',
    current_stop: '185.25',
    exit_date: null,
    exit_price: null,
    exit_reason: null,
    realized_pnl: null,
    return_pct: null,
    agent_reasoning: 'Score: 80/100',
    agent_score: 80,
    sector: 'Technology',
  },
  {
    id: 2,
    symbol: 'NVDA',
    status: 'open',
    signal_date: '2024-01-07',
    entry_date: '2024-01-08',
    entry_price: '520.00',
    shares: 2,
    highest_price: '535.00',
    current_stop: '494.00',
    exit_date: null,
    exit_price: null,
    exit_reason: null,
    realized_pnl: null,
    return_pct: null,
    agent_reasoning: 'Score: 60/100',
    agent_score: 60,
    sector: 'Technology',
  },
];

describe('ArenaPortfolio', () => {
  it('should render portfolio card with title', () => {
    render(
      <ArenaPortfolio
        simulation={mockSimulation}
        positions={[]}
        snapshot={null}
      />
    );

    expect(screen.getByText('Portfolio')).toBeInTheDocument();
  });

  it('should display summary labels', () => {
    render(
      <ArenaPortfolio
        simulation={mockSimulation}
        positions={[]}
        snapshot={null}
      />
    );

    expect(screen.getByText('Cash')).toBeInTheDocument();
    expect(screen.getByText('Total Equity')).toBeInTheDocument();
    expect(screen.getByText('Return')).toBeInTheDocument();
  });

  it('should display initial capital when no snapshot', () => {
    render(
      <ArenaPortfolio
        simulation={mockSimulation}
        positions={[]}
        snapshot={null}
      />
    );

    // Initial capital should be shown twice (Cash and Total Equity)
    const amounts = screen.getAllByText('$10,000.00');
    expect(amounts.length).toBe(2);
    expect(screen.getByText('0.00%')).toBeInTheDocument();
  });

  it('should display snapshot values when available', () => {
    render(
      <ArenaPortfolio
        simulation={mockSimulation}
        positions={mockPositions}
        snapshot={mockSnapshot}
      />
    );

    expect(screen.getByText('$7,156.50')).toBeInTheDocument();
    expect(screen.getByText('$10,830.00')).toBeInTheDocument();
    expect(screen.getByText('+8.30%')).toBeInTheDocument();
  });

  it('should display negative return without plus sign', () => {
    const negativeSnapshot: Snapshot = {
      ...mockSnapshot,
      cumulative_return_pct: '-3.50',
    };
    render(
      <ArenaPortfolio
        simulation={mockSimulation}
        positions={[]}
        snapshot={negativeSnapshot}
      />
    );

    expect(screen.getByText('-3.50%')).toBeInTheDocument();
  });

  it('should show empty state when no positions', () => {
    render(
      <ArenaPortfolio
        simulation={mockSimulation}
        positions={[]}
        snapshot={mockSnapshot}
      />
    );

    expect(screen.getByText('No open positions')).toBeInTheDocument();
  });

  it('should display positions table when positions exist', () => {
    render(
      <ArenaPortfolio
        simulation={mockSimulation}
        positions={mockPositions}
        snapshot={mockSnapshot}
      />
    );

    // Table headers
    expect(screen.getByText('Symbol')).toBeInTheDocument();
    expect(screen.getByText('Shares')).toBeInTheDocument();
    expect(screen.getByText('Entry')).toBeInTheDocument();
    expect(screen.getByText('Stop')).toBeInTheDocument();

    // Position data
    expect(screen.getByText('AAPL')).toBeInTheDocument();
    expect(screen.getByText('NVDA')).toBeInTheDocument();
  });

  it('should display position shares', () => {
    render(
      <ArenaPortfolio
        simulation={mockSimulation}
        positions={mockPositions}
        snapshot={mockSnapshot}
      />
    );

    expect(screen.getByText('5')).toBeInTheDocument();
    expect(screen.getByText('2')).toBeInTheDocument();
  });

  it('should display formatted entry prices', () => {
    render(
      <ArenaPortfolio
        simulation={mockSimulation}
        positions={mockPositions}
        snapshot={mockSnapshot}
      />
    );

    expect(screen.getByText('$195.00')).toBeInTheDocument();
    expect(screen.getByText('$520.00')).toBeInTheDocument();
  });

  it('should display formatted stop prices', () => {
    render(
      <ArenaPortfolio
        simulation={mockSimulation}
        positions={mockPositions}
        snapshot={mockSnapshot}
      />
    );

    expect(screen.getByText('$185.25')).toBeInTheDocument();
    expect(screen.getByText('$494.00')).toBeInTheDocument();
  });

  it('should show dash for null entry price', () => {
    const pendingPosition: Position = {
      ...mockPositions[0],
      entry_price: null,
      shares: null,
    };
    render(
      <ArenaPortfolio
        simulation={mockSimulation}
        positions={[pendingPosition]}
        snapshot={mockSnapshot}
      />
    );

    const dashes = screen.getAllByText('-');
    expect(dashes.length).toBeGreaterThanOrEqual(2); // shares and entry
  });

  it('should show dash for null current stop', () => {
    const noStopPosition: Position = {
      ...mockPositions[0],
      current_stop: null,
    };
    render(
      <ArenaPortfolio
        simulation={mockSimulation}
        positions={[noStopPosition]}
        snapshot={mockSnapshot}
      />
    );

    const dashes = screen.getAllByText('-');
    expect(dashes.length).toBeGreaterThanOrEqual(1);
  });
});
