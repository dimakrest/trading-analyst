import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import { ArenaConfigPanel } from './ArenaConfigPanel';
import type { Simulation } from '../../types/arena';

/**
 * Create a mock Simulation object for testing
 * All fields are set to reasonable defaults and can be overridden
 */
const createMockSimulation = (overrides: Partial<Simulation> = {}): Simulation => ({
  id: 1,
  name: 'Test Simulation',
  stock_list_id: null,
  stock_list_name: null,
  symbols: ['AAPL', 'GOOGL', 'MSFT'],
  start_date: '2024-01-01',
  end_date: '2024-03-01',
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
  current_day: 40,
  total_days: 40,
  final_equity: '11500',
  total_return_pct: '15.0',
  total_trades: 10,
  winning_trades: 7,
  max_drawdown_pct: '3.5',
  created_at: '2024-01-01T00:00:00Z',
  ...overrides,
});

describe('ArenaConfigPanel', () => {
  describe('Configuration Fields', () => {
    it('renders date range', () => {
      render(<ArenaConfigPanel simulation={createMockSimulation()} />);
      expect(screen.getByText('2024-01-01 → 2024-03-01')).toBeInTheDocument();
    });

    it('renders agent type', () => {
      render(<ArenaConfigPanel simulation={createMockSimulation()} />);
      expect(screen.getByText('live20')).toBeInTheDocument();
    });

    it('renders trailing stop percentage', () => {
      render(<ArenaConfigPanel simulation={createMockSimulation()} />);
      expect(screen.getByText('5.0%')).toBeInTheDocument();
    });

    it('renders dash for null trailing stop', () => {
      render(<ArenaConfigPanel simulation={createMockSimulation({ trailing_stop_pct: null })} />);
      expect(screen.getByText('—')).toBeInTheDocument();
    });

    it('renders min buy score', () => {
      render(<ArenaConfigPanel simulation={createMockSimulation()} />);
      expect(screen.getByText('60')).toBeInTheDocument();
    });

    it('renders dash for null min buy score', () => {
      render(<ArenaConfigPanel simulation={createMockSimulation({ min_buy_score: null })} />);
      const dashes = screen.getAllByText('—');
      expect(dashes.length).toBeGreaterThanOrEqual(1);
    });
  });

  describe('Symbol List', () => {
    it('renders symbol count', () => {
      render(<ArenaConfigPanel simulation={createMockSimulation()} />);
      expect(screen.getByText('Symbols (3)')).toBeInTheDocument();
    });

    it('renders all symbols when count is below threshold', () => {
      render(<ArenaConfigPanel simulation={createMockSimulation()} />);
      expect(screen.getByText('AAPL')).toBeInTheDocument();
      expect(screen.getByText('GOOGL')).toBeInTheDocument();
      expect(screen.getByText('MSFT')).toBeInTheDocument();
    });

    it('shows expand button when symbols exceed threshold', () => {
      const manySymbols = Array.from({ length: 12 }, (_, i) => `SYM${i}`);
      render(<ArenaConfigPanel simulation={createMockSimulation({ symbols: manySymbols })} />);
      expect(screen.getByText('Show all 12')).toBeInTheDocument();
      expect(screen.getByText('+4 more')).toBeInTheDocument();
    });

    it('expands and collapses symbols list', async () => {
      const user = userEvent.setup();
      const manySymbols = Array.from({ length: 12 }, (_, i) => `SYM${i}`);
      render(<ArenaConfigPanel simulation={createMockSimulation({ symbols: manySymbols })} />);

      // Initially collapsed - SYM11 should not be visible
      expect(screen.queryByText('SYM11')).not.toBeInTheDocument();

      // Expand
      await user.click(screen.getByText('Show all 12'));
      expect(screen.getByText('SYM11')).toBeInTheDocument();
      expect(screen.getByText('Show less')).toBeInTheDocument();

      // Collapse
      await user.click(screen.getByText('Show less'));
      expect(screen.queryByText('SYM11')).not.toBeInTheDocument();
    });
  });
});
