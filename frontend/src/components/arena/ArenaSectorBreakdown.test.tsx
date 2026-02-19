import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ArenaSectorBreakdown } from './ArenaSectorBreakdown';
import type { Position, Snapshot } from '../../types/arena';

// ---------------------------------------------------------------------------
// Mock factories
// ---------------------------------------------------------------------------

const makeOpenPosition = (
  id: number,
  symbol: string,
  sector: string | null,
  entryPrice = '100.00',
  shares = 10,
): Position => ({
  id,
  symbol,
  status: 'open',
  signal_date: '2024-01-05',
  entry_date: '2024-01-06',
  entry_price: entryPrice,
  shares,
  highest_price: entryPrice,
  current_stop: String(parseFloat(entryPrice) * 0.95),
  exit_date: null,
  exit_price: null,
  exit_reason: null,
  realized_pnl: null,
  return_pct: null,
  agent_reasoning: null,
  agent_score: null,
  sector,
});

const makeClosedPosition = (
  id: number,
  symbol: string,
  sector: string | null,
  realizedPnl: string,
  returnPct = '10.00',
): Position => ({
  id,
  symbol,
  status: 'closed',
  signal_date: '2024-01-05',
  entry_date: '2024-01-10',
  entry_price: '100.00',
  shares: 10,
  highest_price: '110.00',
  current_stop: null,
  exit_date: '2024-01-20',
  exit_price: '110.00',
  exit_reason: 'stop_hit',
  realized_pnl: realizedPnl,
  return_pct: returnPct,
  agent_reasoning: null,
  agent_score: null,
  sector,
});

const makeSnapshot = (overrides: Partial<Snapshot> = {}): Snapshot => ({
  id: 1,
  snapshot_date: '2024-01-20',
  day_number: 15,
  cash: '5000.00',
  positions_value: '5000.00',
  total_equity: '10000.00',
  daily_pnl: '50.00',
  daily_return_pct: '0.50',
  cumulative_return_pct: '5.00',
  open_position_count: 2,
  decisions: {},
  ...overrides,
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('ArenaSectorBreakdown', () => {
  // -------------------------------------------------------------------------
  describe('no positions', () => {
    it('renders nothing when positions array is empty', () => {
      const { container } = render(
        <ArenaSectorBreakdown positions={[]} snapshot={null} />,
      );
      expect(container.firstChild).toBeNull();
    });
  });

  // -------------------------------------------------------------------------
  describe('only open positions with sectors', () => {
    const positions = [
      makeOpenPosition(1, 'AAPL', 'Technology', '200.00', 5),
      makeOpenPosition(2, 'MSFT', 'Technology', '300.00', 3),
      makeOpenPosition(3, 'JPM', 'Financials', '150.00', 4),
    ];

    it('renders the card with Sector Breakdown title', () => {
      render(<ArenaSectorBreakdown positions={positions} snapshot={null} />);
      expect(screen.getByText('Sector Breakdown')).toBeInTheDocument();
    });

    it('shows Cost Basis Allocation section header', () => {
      render(<ArenaSectorBreakdown positions={positions} snapshot={null} />);
      expect(screen.getByText('Cost Basis Allocation')).toBeInTheDocument();
    });

    it('hides Sector Performance section when there are no closed positions', () => {
      render(<ArenaSectorBreakdown positions={positions} snapshot={null} />);
      expect(screen.queryByText('Sector Performance')).not.toBeInTheDocument();
    });

    it('shows correct sector names in allocation table', () => {
      render(<ArenaSectorBreakdown positions={positions} snapshot={null} />);
      expect(screen.getByText('Technology')).toBeInTheDocument();
      expect(screen.getByText('Financials')).toBeInTheDocument();
    });

    it('shows correct position counts per sector', () => {
      render(<ArenaSectorBreakdown positions={positions} snapshot={null} />);
      // Technology has 2 positions, Financials has 1
      const cells = screen.getAllByRole('cell');
      const textContents = cells.map((c) => c.textContent);
      // Count cells with "2" and "1" for position counts
      expect(textContents.filter((t) => t === '2').length).toBeGreaterThan(0);
      expect(textContents.filter((t) => t === '1').length).toBeGreaterThan(0);
    });

    it('sorts Technology before Financials (higher cost basis first)', () => {
      // Technology: 200*5 + 300*3 = 1000 + 900 = 1900
      // Financials: 150*4 = 600
      render(<ArenaSectorBreakdown positions={positions} snapshot={null} />);
      const rows = screen.getAllByRole('row');
      // row[0] = header, row[1] = first data row (Technology), row[2] = second (Financials)
      expect(rows[1].textContent).toContain('Technology');
      expect(rows[2].textContent).toContain('Financials');
    });

    it('renders allocation table column headers', () => {
      render(<ArenaSectorBreakdown positions={positions} snapshot={null} />);
      expect(screen.getByText('Sector')).toBeInTheDocument();
      expect(screen.getByText('Positions')).toBeInTheDocument();
      expect(screen.getByText('Cost Basis')).toBeInTheDocument();
      expect(screen.getByText('% of Total Cost Basis')).toBeInTheDocument();
    });
  });

  // -------------------------------------------------------------------------
  describe('only closed positions with sectors', () => {
    const positions = [
      makeClosedPosition(1, 'AAPL', 'Technology', '150.00', '15.00'),
      makeClosedPosition(2, 'MSFT', 'Technology', '-80.00', '-8.00'),
      makeClosedPosition(3, 'JPM', 'Financials', '200.00', '20.00'),
    ];

    it('shows Sector Performance section header', () => {
      render(<ArenaSectorBreakdown positions={positions} snapshot={null} />);
      expect(screen.getByText('Sector Performance')).toBeInTheDocument();
    });

    it('hides Cost Basis Allocation section when there are no open positions', () => {
      render(<ArenaSectorBreakdown positions={positions} snapshot={null} />);
      expect(screen.queryByText('Cost Basis Allocation')).not.toBeInTheDocument();
    });

    it('renders performance table column headers', () => {
      render(<ArenaSectorBreakdown positions={positions} snapshot={null} />);
      expect(screen.getByText('Trades')).toBeInTheDocument();
      expect(screen.getByText('Win Rate')).toBeInTheDocument();
      expect(screen.getByText('Total P&L')).toBeInTheDocument();
    });

    it('shows correct sector names in performance table', () => {
      render(<ArenaSectorBreakdown positions={positions} snapshot={null} />);
      expect(screen.getByText('Technology')).toBeInTheDocument();
      expect(screen.getByText('Financials')).toBeInTheDocument();
    });

    it('sorts Financials before Technology (higher total P&L first)', () => {
      // Financials: 200.00; Technology: 150 + (-80) = 70
      render(<ArenaSectorBreakdown positions={positions} snapshot={null} />);
      const rows = screen.getAllByRole('row');
      expect(rows[1].textContent).toContain('Financials');
      expect(rows[2].textContent).toContain('Technology');
    });

    it('shows correct trade count for Technology (2 trades)', () => {
      render(<ArenaSectorBreakdown positions={positions} snapshot={null} />);
      // Technology row should contain "2" for trade count
      // We check row content after sorting (Financials first, Technology second)
      const rows = screen.getAllByRole('row');
      // rows[2] is Technology (2 trades, 1 win, 50% win rate)
      expect(rows[2].textContent).toContain('2');
    });

    it('colors positive Total P&L with bullish class', () => {
      render(<ArenaSectorBreakdown positions={positions} snapshot={null} />);
      // $200.00 (Financials) is positive
      const positivePnl = screen.getByText('$200.00');
      expect(positivePnl).toHaveClass('text-accent-bullish');
    });

    it('colors negative Total P&L with bearish class', () => {
      // Technology total = 150 - 80 = 70, which is still positive
      // We need a case with a net negative sector. Let's test a separate render.
      const allLosers = [
        makeClosedPosition(1, 'AAPL', 'Technology', '-100.00', '-10.00'),
        makeClosedPosition(2, 'MSFT', 'Technology', '-50.00', '-5.00'),
      ];
      render(<ArenaSectorBreakdown positions={allLosers} snapshot={null} />);
      const negativePnl = screen.getByText('-$150.00');
      expect(negativePnl).toHaveClass('text-accent-bearish');
    });
  });

  // -------------------------------------------------------------------------
  describe('mixed open and closed positions', () => {
    const positions = [
      makeOpenPosition(1, 'AAPL', 'Technology'),
      makeClosedPosition(2, 'JPM', 'Financials', '120.00', '12.00'),
    ];

    it('renders both sections', () => {
      render(<ArenaSectorBreakdown positions={positions} snapshot={null} />);
      expect(screen.getByText('Cost Basis Allocation')).toBeInTheDocument();
      expect(screen.getByText('Sector Performance')).toBeInTheDocument();
    });
  });

  // -------------------------------------------------------------------------
  describe('positions with null sector (grouped as Unknown)', () => {
    it('groups null sector as "Unknown" in allocation table', () => {
      const positions = [
        makeOpenPosition(1, 'AAPL', null),
        makeOpenPosition(2, 'MSFT', 'Technology'),
      ];
      render(<ArenaSectorBreakdown positions={positions} snapshot={null} />);
      expect(screen.getByText('Unknown')).toBeInTheDocument();
      expect(screen.getByText('Technology')).toBeInTheDocument();
    });

    it('shows Unknown last in allocation table when other sectors are present', () => {
      const positions = [
        makeOpenPosition(1, 'AAPL', null, '100.00', 10),      // Unknown: 1000
        makeOpenPosition(2, 'MSFT', 'Technology', '50.00', 5), // Technology: 250
      ];
      render(<ArenaSectorBreakdown positions={positions} snapshot={null} />);
      const rows = screen.getAllByRole('row');
      // Header row + 2 data rows. Unknown should be last even though its cost basis is higher.
      expect(rows[rows.length - 1].textContent).toContain('Unknown');
    });

    it('groups null sector as "Unknown" in performance table', () => {
      const positions = [
        makeClosedPosition(1, 'AAPL', null, '100.00', '10.00'),
        makeClosedPosition(2, 'JPM', 'Financials', '50.00', '5.00'),
      ];
      render(<ArenaSectorBreakdown positions={positions} snapshot={null} />);
      expect(screen.getByText('Unknown')).toBeInTheDocument();
      expect(screen.getByText('Financials')).toBeInTheDocument();
    });

    it('shows Unknown last in performance table when other sectors are present', () => {
      const positions = [
        makeClosedPosition(1, 'AAPL', null, '500.00', '50.00'),    // Unknown: 500
        makeClosedPosition(2, 'JPM', 'Financials', '100.00', '10.00'), // Financials: 100
      ];
      render(<ArenaSectorBreakdown positions={positions} snapshot={null} />);
      const rows = screen.getAllByRole('row');
      expect(rows[rows.length - 1].textContent).toContain('Unknown');
    });

    it('handles all null sectors (single "Unknown" row)', () => {
      const positions = [
        makeOpenPosition(1, 'AAPL', null),
        makeOpenPosition(2, 'MSFT', null),
      ];
      render(<ArenaSectorBreakdown positions={positions} snapshot={null} />);
      // Should show one "Unknown" row
      const unknownCells = screen.getAllByText('Unknown');
      expect(unknownCells.length).toBe(1);
    });
  });

  // -------------------------------------------------------------------------
  describe('win rate calculation', () => {
    it('calculates win rate as winners / total (2 out of 3 = 66.7%)', () => {
      const positions = [
        makeClosedPosition(1, 'AAPL', 'Technology', '100.00', '10.00'),  // win
        makeClosedPosition(2, 'MSFT', 'Technology', '50.00', '5.00'),    // win
        makeClosedPosition(3, 'GOOG', 'Technology', '-30.00', '-3.00'),  // loss
      ];
      render(<ArenaSectorBreakdown positions={positions} snapshot={null} />);
      // 2/3 = 66.666...% → displayed as 66.7%
      expect(screen.getByText('66.7%')).toBeInTheDocument();
    });

    it('calculates win rate as 0.0% when all trades are losses', () => {
      const positions = [
        makeClosedPosition(1, 'AAPL', 'Technology', '-50.00', '-5.00'),
        makeClosedPosition(2, 'MSFT', 'Technology', '-80.00', '-8.00'),
      ];
      render(<ArenaSectorBreakdown positions={positions} snapshot={null} />);
      expect(screen.getByText('0.0%')).toBeInTheDocument();
    });

    it('calculates win rate as 100.0% when all trades are winners', () => {
      const positions = [
        makeClosedPosition(1, 'AAPL', 'Technology', '100.00', '10.00'),
        makeClosedPosition(2, 'MSFT', 'Technology', '200.00', '20.00'),
      ];
      render(<ArenaSectorBreakdown positions={positions} snapshot={null} />);
      expect(screen.getByText('100.0%')).toBeInTheDocument();
    });
  });

  // -------------------------------------------------------------------------
  describe('with snapshot prop', () => {
    it('renders correctly when snapshot is provided', () => {
      const positions = [makeOpenPosition(1, 'AAPL', 'Technology')];
      const snapshot = makeSnapshot();
      render(<ArenaSectorBreakdown positions={positions} snapshot={snapshot} />);
      expect(screen.getByText('Sector Breakdown')).toBeInTheDocument();
    });
  });
});
