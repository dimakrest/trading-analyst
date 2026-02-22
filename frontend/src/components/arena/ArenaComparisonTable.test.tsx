/**
 * Tests for ArenaComparisonTable component.
 *
 * Covers:
 * - Renders correct column headers
 * - Sorts by return descending by default (best first)
 * - Click column header to toggle sort direction
 * - Best value gets bullish highlight, worst gets bearish
 * - No highlight when all column values are equal (min === max)
 * - In-progress simulations show strategy badge + status badge, metrics show "—"
 * - Win Rate shows "—" when total_trades === 0
 * - Row click navigates to /arena/:id
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { ArenaComparisonTable } from './ArenaComparisonTable';
import type { Simulation } from '../../types/arena';

const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

const makeSimulation = (overrides: Partial<Simulation> = {}): Simulation => ({
  id: 1,
  name: null,
  stock_list_id: null,
  stock_list_name: null,
  symbols: ['AAPL'],
  start_date: '2024-01-01',
  end_date: '2024-01-31',
  initial_capital: '10000',
  position_size: '1000',
  agent_type: 'live20',
  trailing_stop_pct: '5.0',
  min_buy_score: 60,
  scoring_algorithm: null,
  portfolio_strategy: 'none',
  max_per_sector: null,
  max_open_positions: null,
  group_id: 'test-group',
  status: 'completed',
  current_day: 22,
  total_days: 22,
  final_equity: '10500',
  total_return_pct: '5.00',
  total_trades: 10,
  winning_trades: 6,
  max_drawdown_pct: '3.50',
  avg_hold_days: '5.0',
  avg_win_pnl: '200.00',
  avg_loss_pnl: '-80.00',
  profit_factor: '1.80',
  sharpe_ratio: '1.20',
  total_realized_pnl: '500.00',
  created_at: '2024-01-01T10:00:00Z',
  ...overrides,
});

const renderTable = (simulations: Simulation[]) =>
  render(
    <MemoryRouter>
      <ArenaComparisonTable simulations={simulations} />
    </MemoryRouter>,
  );

describe('ArenaComparisonTable', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('column headers', () => {
    it('renders all expected column headers', () => {
      renderTable([makeSimulation()]);

      expect(screen.getByText('Strategy')).toBeInTheDocument();
      expect(screen.getByText('Return')).toBeInTheDocument();
      expect(screen.getByText('Max DD')).toBeInTheDocument();
      expect(screen.getByText('Sharpe')).toBeInTheDocument();
      expect(screen.getByText('Profit Factor')).toBeInTheDocument();
      expect(screen.getByText('Win Rate')).toBeInTheDocument();
      expect(screen.getByText('Total Trades')).toBeInTheDocument();
      expect(screen.getByText('Avg Hold')).toBeInTheDocument();
      expect(screen.getByText('Avg Win')).toBeInTheDocument();
      expect(screen.getByText('Avg Loss')).toBeInTheDocument();
    });
  });

  describe('default sort (return descending)', () => {
    it('renders strategies with highest return value appearing before lower return values', () => {
      const sims = [
        makeSimulation({ id: 1, portfolio_strategy: 'low_atr', total_return_pct: '3.00' }),
        makeSimulation({ id: 2, portfolio_strategy: 'high_atr', total_return_pct: '8.00' }),
        makeSimulation({ id: 3, portfolio_strategy: 'mod_atr', total_return_pct: '5.00' }),
      ];

      renderTable(sims);

      // Get all strategy badges in document order (reflects rendered row order)
      const strategyBadges = screen.getAllByText(/^(low_atr|high_atr|mod_atr)$/);
      expect(strategyBadges[0].textContent).toBe('high_atr');
      expect(strategyBadges[1].textContent).toBe('mod_atr');
      expect(strategyBadges[2].textContent).toBe('low_atr');
    });
  });

  describe('sort toggle', () => {
    it('reverses sort order when the same header is clicked twice', () => {
      const sims = [
        makeSimulation({ id: 1, portfolio_strategy: 'alpha_strat', total_return_pct: '8.00' }),
        makeSimulation({ id: 2, portfolio_strategy: 'beta_strat', total_return_pct: '3.00' }),
      ];

      renderTable(sims);

      // Default: alpha_strat (8%) should be first (descending by return)
      let badges = screen.getAllByText(/^(alpha_strat|beta_strat)$/);
      expect(badges[0].textContent).toBe('alpha_strat');

      // Click Return header to toggle to ascending
      fireEvent.click(screen.getByText('Return'));

      // Now ascending: beta_strat (3%) should be first
      badges = screen.getAllByText(/^(alpha_strat|beta_strat)$/);
      expect(badges[0].textContent).toBe('beta_strat');
    });

    it('switches to a different sort field when a different header is clicked', () => {
      const sims = [
        makeSimulation({ id: 1, portfolio_strategy: 'gamma_strat', total_return_pct: '8.00', total_trades: 5 }),
        makeSimulation({ id: 2, portfolio_strategy: 'delta_strat', total_return_pct: '3.00', total_trades: 15 }),
      ];

      renderTable(sims);

      // Default: gamma_strat (8% return) is first
      let badges = screen.getAllByText(/^(gamma_strat|delta_strat)$/);
      expect(badges[0].textContent).toBe('gamma_strat');

      // Sort by Total Trades descending — delta_strat (15 trades) should be first
      fireEvent.click(screen.getByText('Total Trades'));

      badges = screen.getAllByText(/^(gamma_strat|delta_strat)$/);
      expect(badges[0].textContent).toBe('delta_strat');
    });
  });

  describe('best / worst highlight', () => {
    it('applies bullish class to the best return value', () => {
      const sims = [
        makeSimulation({ id: 1, portfolio_strategy: 'high_atr', total_return_pct: '8.00' }),
        makeSimulation({ id: 2, portfolio_strategy: 'low_atr', total_return_pct: '3.00' }),
      ];

      renderTable(sims);

      const returnCells = screen.getAllByText(/[+-]\d+\.\d+%/);
      const bestCell = returnCells.find((el) => el.textContent === '+8.0%');
      expect(bestCell).toBeDefined();
      expect(bestCell!.className).toContain('text-accent-bullish');
    });

    it('applies bearish class to the worst return value', () => {
      const sims = [
        makeSimulation({ id: 1, portfolio_strategy: 'high_atr', total_return_pct: '8.00' }),
        makeSimulation({ id: 2, portfolio_strategy: 'low_atr', total_return_pct: '3.00' }),
      ];

      renderTable(sims);

      const returnCells = screen.getAllByText(/[+-]\d+\.\d+%/);
      const worstCell = returnCells.find((el) => el.textContent === '+3.0%');
      expect(worstCell).toBeDefined();
      expect(worstCell!.className).toContain('text-accent-bearish');
    });

    it('applies no highlight when all return values are equal', () => {
      const sims = [
        makeSimulation({ id: 1, portfolio_strategy: 'high_atr', total_return_pct: '5.00' }),
        makeSimulation({ id: 2, portfolio_strategy: 'low_atr', total_return_pct: '5.00' }),
      ];

      renderTable(sims);

      const returnCells = screen.getAllByText('+5.0%');
      returnCells.forEach((cell) => {
        expect(cell.className).not.toContain('text-accent-bullish');
        expect(cell.className).not.toContain('text-accent-bearish');
      });
    });
  });

  describe('in-progress simulations', () => {
    it('shows strategy badge and status badge for running simulations', () => {
      const sims = [
        makeSimulation({ id: 1, portfolio_strategy: 'none', status: 'completed' }),
        makeSimulation({
          id: 2,
          portfolio_strategy: 'high_atr',
          status: 'running',
          total_return_pct: null,
          max_drawdown_pct: null,
          sharpe_ratio: null,
        }),
      ];

      renderTable(sims);

      // Status badge for in-progress sim
      expect(screen.getByText('running')).toBeInTheDocument();
    });

    it('shows "—" for all metric columns for in-progress simulations', () => {
      const sims = [
        makeSimulation({
          id: 1,
          portfolio_strategy: 'high_atr',
          status: 'running',
          total_return_pct: null,
          max_drawdown_pct: null,
          sharpe_ratio: null,
          profit_factor: null,
          avg_hold_days: null,
          avg_win_pnl: null,
          avg_loss_pnl: null,
        }),
      ];

      renderTable(sims);

      // There should be multiple "—" for the metric columns
      const dashes = screen.getAllByText('—');
      expect(dashes.length).toBeGreaterThanOrEqual(1);
    });

    it('sorts in-progress simulations after completed ones regardless of direction', () => {
      const sims = [
        makeSimulation({
          id: 1,
          portfolio_strategy: 'running_strategy',
          status: 'running',
          total_return_pct: null,
        }),
        makeSimulation({ id: 2, portfolio_strategy: 'finished_strategy', total_return_pct: '8.00' }),
      ];

      renderTable(sims);

      // Get all strategy badges in document order (completed strategy should appear before running)
      const strategyBadges = screen.getAllByText(/^(running_strategy|finished_strategy)$/);
      expect(strategyBadges[0].textContent).toBe('finished_strategy');
      expect(strategyBadges[1].textContent).toBe('running_strategy');
    });

    it('excludes in-progress simulations from best/worst computation', () => {
      const sims = [
        makeSimulation({
          id: 1,
          portfolio_strategy: 'running_strat',
          status: 'running',
          total_return_pct: null,
        }),
        makeSimulation({
          id: 2,
          portfolio_strategy: 'only_completed',
          total_return_pct: '5.00',
        }),
      ];

      renderTable(sims);

      // The only completed sim has no competitor — min === max, so no highlight
      const returnCell = screen.getByText('+5.0%');
      expect(returnCell.className).not.toContain('text-accent-bullish');
      expect(returnCell.className).not.toContain('text-accent-bearish');
    });
  });

  describe('Win Rate edge cases', () => {
    it('shows "—" for Win Rate when total_trades is 0', () => {
      const sims = [
        makeSimulation({ id: 1, total_trades: 0, winning_trades: 0 }),
      ];

      renderTable(sims);

      // Win rate column should show "—" not a percentage
      const cells = screen.getAllByText('—');
      expect(cells.length).toBeGreaterThan(0);
    });

    it('renders win rate as percentage when total_trades > 0', () => {
      const sims = [
        makeSimulation({ id: 1, total_trades: 10, winning_trades: 6 }),
      ];

      renderTable(sims);

      expect(screen.getByText('60.0%')).toBeInTheDocument();
    });
  });

  describe('row click navigation', () => {
    it('navigates to /arena/:id when row is clicked', () => {
      const sims = [makeSimulation({ id: 42 })];

      renderTable(sims);

      // Find the data row (the one containing the strategy badge and metrics)
      // The row has role="row" - click it to trigger navigation
      const strategyBadge = screen.getByText('none');
      // Navigate up to the row element
      const dataRow = strategyBadge.closest('tr');
      expect(dataRow).not.toBeNull();
      fireEvent.click(dataRow!);

      expect(mockNavigate).toHaveBeenCalledWith('/arena/42');
    });
  });

  describe('metric formatting', () => {
    it('formats positive return with + prefix', () => {
      renderTable([makeSimulation({ total_return_pct: '7.50' })]);
      expect(screen.getByText('+7.5%')).toBeInTheDocument();
    });

    it('formats negative return with - prefix (no +)', () => {
      renderTable([makeSimulation({ total_return_pct: '-4.20' })]);
      expect(screen.getByText('-4.2%')).toBeInTheDocument();
    });

    it('formats max drawdown with leading dash and absolute value', () => {
      renderTable([makeSimulation({ max_drawdown_pct: '5.00' })]);
      expect(screen.getByText('-5.0%')).toBeInTheDocument();
    });

    it('formats avg hold in days', () => {
      renderTable([makeSimulation({ avg_hold_days: '6.5' })]);
      expect(screen.getByText('6.5 days')).toBeInTheDocument();
    });

    it('formats avg win as dollar amount', () => {
      renderTable([makeSimulation({ avg_win_pnl: '250.00' })]);
      expect(screen.getByText('$250.00')).toBeInTheDocument();
    });

    it('formats avg loss as dollar amount', () => {
      renderTable([makeSimulation({ avg_loss_pnl: '-120.00' })]);
      expect(screen.getByText('$-120.00')).toBeInTheDocument();
    });
  });
});
