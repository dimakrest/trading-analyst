import { describe, it, expect } from 'vitest';
import {
  formatTrailingStop,
  getPositionsForSnapshot,
  getStatusBadgeClass,
} from './arena';
import type { Position, SimulationStatus, Snapshot } from '../types/arena';

// Helper to create a minimal position for testing
const createPosition = (overrides: Partial<Position>): Position => ({
  id: 1,
  symbol: 'TEST',
  status: 'open',
  signal_date: '2024-01-01',
  entry_date: null,
  entry_price: null,
  shares: null,
  highest_price: null,
  current_stop: null,
  exit_date: null,
  exit_price: null,
  exit_reason: null,
  realized_pnl: null,
  return_pct: null,
  agent_reasoning: null,
  agent_score: null,
  ...overrides,
});

// Helper to create a minimal snapshot for testing
const createSnapshot = (overrides: Partial<Snapshot>): Snapshot => ({
  id: 1,
  snapshot_date: '2024-01-05',
  day_number: 4,
  cash: '5000.00',
  positions_value: '5000.00',
  total_equity: '10000.00',
  daily_pnl: '100.00',
  daily_return_pct: '1.00',
  cumulative_return_pct: '2.00',
  open_position_count: 2,
  decisions: {},
  ...overrides,
});

describe('formatTrailingStop', () => {
  it('returns formatted percentage for valid string value', () => {
    expect(formatTrailingStop('5.0')).toBe('5.0%');
  });

  it('formats to one decimal place', () => {
    expect(formatTrailingStop('7.5')).toBe('7.5%');
    expect(formatTrailingStop('10')).toBe('10.0%');
    expect(formatTrailingStop('3.14159')).toBe('3.1%');
  });

  it('returns em-dash for null value', () => {
    expect(formatTrailingStop(null)).toBe('—');
  });

  it('returns em-dash for empty string', () => {
    expect(formatTrailingStop('')).toBe('—');
  });
});

describe('getPositionsForSnapshot', () => {
  it('returns empty array when snapshot is null', () => {
    const positions = [createPosition({ id: 1, entry_date: '2024-01-02' })];
    expect(getPositionsForSnapshot(positions, null)).toEqual([]);
  });

  it('excludes positions with null entry_date (pending)', () => {
    const positions = [
      createPosition({ id: 1, entry_date: null, status: 'pending' }),
    ];
    const snapshot = createSnapshot({ snapshot_date: '2024-01-05' });
    expect(getPositionsForSnapshot(positions, snapshot)).toEqual([]);
  });

  it('excludes positions entered after snapshot date', () => {
    const positions = [
      createPosition({ id: 1, entry_date: '2024-01-06' }), // After snapshot
    ];
    const snapshot = createSnapshot({ snapshot_date: '2024-01-05' });
    expect(getPositionsForSnapshot(positions, snapshot)).toEqual([]);
  });

  it('includes positions entered on snapshot date', () => {
    const positions = [
      createPosition({ id: 1, entry_date: '2024-01-05' }), // Same as snapshot
    ];
    const snapshot = createSnapshot({ snapshot_date: '2024-01-05' });
    expect(getPositionsForSnapshot(positions, snapshot)).toHaveLength(1);
  });

  it('includes positions entered before snapshot date', () => {
    const positions = [
      createPosition({ id: 1, entry_date: '2024-01-03' }), // Before snapshot
    ];
    const snapshot = createSnapshot({ snapshot_date: '2024-01-05' });
    expect(getPositionsForSnapshot(positions, snapshot)).toHaveLength(1);
  });

  it('excludes positions closed before snapshot date', () => {
    const positions = [
      createPosition({
        id: 1,
        entry_date: '2024-01-02',
        exit_date: '2024-01-04', // Before snapshot
        status: 'closed',
      }),
    ];
    const snapshot = createSnapshot({ snapshot_date: '2024-01-05' });
    expect(getPositionsForSnapshot(positions, snapshot)).toEqual([]);
  });

  it('excludes positions closed on snapshot date (EOD shows post-sale state)', () => {
    // CRITICAL: Snapshot is EOD state. If sold on Day 5, Day 5 snapshot shows cash after sale.
    // Including the position would double-count (cash + position).
    const positions = [
      createPosition({
        id: 1,
        entry_date: '2024-01-02',
        exit_date: '2024-01-05', // Same as snapshot - sold today
        status: 'closed',
      }),
    ];
    const snapshot = createSnapshot({ snapshot_date: '2024-01-05' });
    expect(getPositionsForSnapshot(positions, snapshot)).toEqual([]);
  });

  it('includes positions closed after snapshot date (still held at EOD)', () => {
    const positions = [
      createPosition({
        id: 1,
        entry_date: '2024-01-02',
        exit_date: '2024-01-07', // After snapshot - still held on snapshot day
        status: 'closed',
      }),
    ];
    const snapshot = createSnapshot({ snapshot_date: '2024-01-05' });
    expect(getPositionsForSnapshot(positions, snapshot)).toHaveLength(1);
  });

  it('includes positions with no exit date (still open)', () => {
    const positions = [
      createPosition({
        id: 1,
        entry_date: '2024-01-02',
        exit_date: null,
        status: 'open',
      }),
    ];
    const snapshot = createSnapshot({ snapshot_date: '2024-01-05' });
    expect(getPositionsForSnapshot(positions, snapshot)).toHaveLength(1);
  });

  it('filters correctly with multiple positions', () => {
    const positions = [
      createPosition({ id: 1, symbol: 'AAPL', entry_date: '2024-01-02', exit_date: null }), // Include (still open)
      createPosition({ id: 2, symbol: 'GOOG', entry_date: '2024-01-03', exit_date: '2024-01-04' }), // Exclude (closed before)
      createPosition({ id: 3, symbol: 'MSFT', entry_date: '2024-01-06', exit_date: null }), // Exclude (entered after)
      createPosition({ id: 4, symbol: 'AMZN', entry_date: '2024-01-04', exit_date: '2024-01-05' }), // Exclude (closed on date - EOD state)
      createPosition({ id: 5, symbol: 'META', entry_date: null }), // Exclude (pending)
      createPosition({ id: 6, symbol: 'NVDA', entry_date: '2024-01-03', exit_date: '2024-01-06' }), // Include (closed after)
    ];
    const snapshot = createSnapshot({ snapshot_date: '2024-01-05' });

    const result = getPositionsForSnapshot(positions, snapshot);

    expect(result).toHaveLength(2);
    expect(result.map((p) => p.symbol)).toEqual(['AAPL', 'NVDA']);
  });
});

describe('getStatusBadgeClass', () => {
  it('returns amber styling for pending status', () => {
    expect(getStatusBadgeClass('pending')).toBe(
      'bg-amber-500/15 text-amber-500 border border-amber-500/30'
    );
  });

  it('returns primary accent styling for running status', () => {
    expect(getStatusBadgeClass('running')).toBe(
      'bg-accent-primary/15 text-accent-primary border border-accent-primary/30'
    );
  });

  it('returns orange styling for paused status', () => {
    expect(getStatusBadgeClass('paused')).toBe(
      'bg-orange-500/15 text-orange-500 border border-orange-500/30'
    );
  });

  it('returns bullish accent styling for completed status', () => {
    expect(getStatusBadgeClass('completed')).toBe(
      'bg-accent-bullish/15 text-accent-bullish border border-accent-bullish/30'
    );
  });

  it('returns muted styling for cancelled status', () => {
    expect(getStatusBadgeClass('cancelled')).toBe(
      'bg-bg-tertiary text-text-muted border border-subtle'
    );
  });

  it('returns bearish accent styling for failed status', () => {
    expect(getStatusBadgeClass('failed')).toBe(
      'bg-accent-bearish/15 text-accent-bearish border border-accent-bearish/30'
    );
  });

  it('returns pending styling for unknown status', () => {
    // TypeScript would normally prevent this, but testing runtime fallback behavior
    const unknownStatus = 'unknown' as SimulationStatus;
    expect(getStatusBadgeClass(unknownStatus)).toBe(
      'bg-amber-500/15 text-amber-500 border border-amber-500/30'
    );
  });
});
