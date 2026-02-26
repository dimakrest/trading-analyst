import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ArenaMonthlyPnl } from './ArenaMonthlyPnl';
import type { Snapshot } from '../../types/arena';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

let snapshotIdCounter = 0;

const makeSnapshot = (
  date: string,
  dailyPnl: string,
  overrides: Partial<Snapshot> = {},
): Snapshot => ({
  id: ++snapshotIdCounter,
  snapshot_date: date,
  day_number: 1,
  cash: '10000',
  positions_value: '0',
  total_equity: '10000',
  daily_pnl: dailyPnl,
  daily_return_pct: '0',
  cumulative_return_pct: '0',
  open_position_count: 0,
  decisions: {},
  ...overrides,
});

/**
 * Generate n snapshots spread across different months starting from the given
 * date string "YYYY-MM-DD". Consecutive snapshots increment the day.
 */
const makeSnapshots = (
  count: number,
  startDate = '2024-01-02',
  dailyPnl = '100',
): Snapshot[] => {
  const base = new Date(startDate);
  return Array.from({ length: count }, (_, i) => {
    const d = new Date(base);
    d.setDate(base.getDate() + i);
    const dateStr = d.toISOString().slice(0, 10);
    return makeSnapshot(dateStr, dailyPnl);
  });
};

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('ArenaMonthlyPnl', () => {
  describe('below threshold (< 20 snapshots)', () => {
    it('renders nothing when given 0 snapshots', () => {
      const { container } = render(<ArenaMonthlyPnl snapshots={[]} />);
      expect(container.firstChild).toBeNull();
    });

    it('renders nothing when given 19 snapshots', () => {
      const snapshots = makeSnapshots(19);
      const { container } = render(<ArenaMonthlyPnl snapshots={snapshots} />);
      expect(container.firstChild).toBeNull();
    });
  });

  describe('at threshold (>= 20 snapshots)', () => {
    it('renders the monthly P&L section with 20 snapshots', () => {
      const snapshots = makeSnapshots(20);
      render(<ArenaMonthlyPnl snapshots={snapshots} />);
      expect(screen.getByTestId('monthly-pnl-rows')).toBeInTheDocument();
    });

    it('renders one row per unique YYYY-MM month', () => {
      // 20 snapshots all in January 2024 → should produce exactly 1 row
      const snapshots = makeSnapshots(20, '2024-01-02');
      render(<ArenaMonthlyPnl snapshots={snapshots} />);

      // All 20 fall within Jan 2024 — only the Jan 2024 row key should exist
      expect(screen.getByTestId('monthly-pnl-row-2024-01')).toBeInTheDocument();
    });
  });

  describe('monthly grouping and summing', () => {
    it('sums daily_pnl values within the same month', () => {
      // 20 snapshots: first 10 in Jan 2024 (+$50 each = $500), next 10 in Feb 2024 (+$30 each = $300)
      const janSnapshots = Array.from({ length: 10 }, (_, i) =>
        makeSnapshot(`2024-01-${String(i + 2).padStart(2, '0')}`, '50'),
      );
      const febSnapshots = Array.from({ length: 10 }, (_, i) =>
        makeSnapshot(`2024-02-${String(i + 1).padStart(2, '0')}`, '30'),
      );
      const snapshots = [...janSnapshots, ...febSnapshots];

      render(<ArenaMonthlyPnl snapshots={snapshots} />);

      const janValue = screen.getByTestId('monthly-pnl-value-2024-01');
      const febValue = screen.getByTestId('monthly-pnl-value-2024-02');

      expect(janValue).toHaveTextContent('$500.00');
      expect(febValue).toHaveTextContent('$300.00');
    });

    it('handles snapshots across three distinct months', () => {
      const jan = Array.from({ length: 7 }, (_, i) =>
        makeSnapshot(`2024-01-${String(i + 2).padStart(2, '0')}`, '100'),
      );
      const feb = Array.from({ length: 7 }, (_, i) =>
        makeSnapshot(`2024-02-${String(i + 1).padStart(2, '0')}`, '-50'),
      );
      const mar = Array.from({ length: 6 }, (_, i) =>
        makeSnapshot(`2024-03-${String(i + 1).padStart(2, '0')}`, '200'),
      );
      const snapshots = [...jan, ...feb, ...mar];

      render(<ArenaMonthlyPnl snapshots={snapshots} />);

      expect(screen.getByTestId('monthly-pnl-row-2024-01')).toBeInTheDocument();
      expect(screen.getByTestId('monthly-pnl-row-2024-02')).toBeInTheDocument();
      expect(screen.getByTestId('monthly-pnl-row-2024-03')).toBeInTheDocument();
    });
  });

  describe('bar colors', () => {
    const buildTwoMonthSnapshots = () => {
      const jan = Array.from({ length: 10 }, (_, i) =>
        makeSnapshot(`2024-01-${String(i + 2).padStart(2, '0')}`, '100'),
      );
      const feb = Array.from({ length: 10 }, (_, i) =>
        makeSnapshot(`2024-02-${String(i + 1).padStart(2, '0')}`, '-100'),
      );
      return [...jan, ...feb];
    };

    it('positive month bar has green-ish color (rgba with 0, 210, 106)', () => {
      render(<ArenaMonthlyPnl snapshots={buildTwoMonthSnapshots()} />);

      const janBar = screen.getByTestId('monthly-pnl-bar-2024-01');
      const bgColor = janBar.style.backgroundColor;
      // rgba(0, 210, 106, ...) — only check the green channel presence
      expect(bgColor).toContain('0, 210, 106');
    });

    it('negative month bar has red-ish color (rgba with 255, 71, 87)', () => {
      render(<ArenaMonthlyPnl snapshots={buildTwoMonthSnapshots()} />);

      const febBar = screen.getByTestId('monthly-pnl-bar-2024-02');
      const bgColor = febBar.style.backgroundColor;
      // rgba(255, 71, 87, ...) — only check the red channel presence
      expect(bgColor).toContain('255, 71, 87');
    });

    it('maximum magnitude month bar has 100% width (opacity equals 1 at maxAbs)', () => {
      // Jan: $1000, Feb: -$200 → Jan should have width 100% (maxAbs = Jan pnl)
      const jan = Array.from({ length: 10 }, (_, i) =>
        makeSnapshot(`2024-01-${String(i + 2).padStart(2, '0')}`, '100'),
      );
      const feb = Array.from({ length: 10 }, (_, i) =>
        makeSnapshot(`2024-02-${String(i + 1).padStart(2, '0')}`, '-20'),
      );
      const snapshots = [...jan, ...feb];

      render(<ArenaMonthlyPnl snapshots={snapshots} />);

      const janBar = screen.getByTestId('monthly-pnl-bar-2024-01');
      // Jan sum = $1000 = maxAbs → width should be 100% (full bar)
      expect(janBar.style.width).toBe('100%');
    });
  });
});
