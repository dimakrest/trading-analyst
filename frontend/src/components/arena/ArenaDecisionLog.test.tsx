import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { ArenaDecisionLog } from './ArenaDecisionLog';
import type { AgentDecision, Snapshot } from '../../types/arena';

const mockDecisions: Record<string, AgentDecision> = {
  AAPL: {
    action: 'BUY',
    score: 80,
    reasoning: 'Score: 80/100 (4/5 criteria aligned); Aligned: trend, ma20, candle, volume; Not aligned: cci',
  },
  NVDA: {
    action: 'HOLD',
    score: null,
    reasoning: 'Already holding position',
  },
  TSLA: {
    action: 'NO_SIGNAL',
    score: 40,
    reasoning: 'Score: 40/100 (2/5 criteria aligned); Aligned: trend, ma20; Not aligned: candle, volume, cci',
  },
  AMD: {
    action: 'NO_DATA',
    score: null,
    reasoning: 'No price data available',
  },
};

const mockSnapshot: Snapshot = {
  id: 3,
  snapshot_date: '2024-01-10',
  day_number: 9,
  cash: '7156.50',
  positions_value: '3673.50',
  total_equity: '10830.00',
  daily_pnl: '150.00',
  daily_return_pct: '1.40',
  cumulative_return_pct: '8.30',
  open_position_count: 2,
  decisions: mockDecisions,
};

const mockSnapshots: Snapshot[] = [
  {
    id: 1,
    snapshot_date: '2024-01-08',
    day_number: 7,
    cash: '8000',
    positions_value: '2000',
    total_equity: '10000',
    daily_pnl: '0',
    daily_return_pct: '0',
    cumulative_return_pct: '0',
    open_position_count: 1,
    decisions: { AAPL: { action: 'HOLD', score: null, reasoning: 'Holding' } },
  },
  {
    id: 2,
    snapshot_date: '2024-01-09',
    day_number: 8,
    cash: '7500',
    positions_value: '2700',
    total_equity: '10200',
    daily_pnl: '200',
    daily_return_pct: '2.0',
    cumulative_return_pct: '2.0',
    open_position_count: 2,
    decisions: { NVDA: { action: 'BUY', score: 60, reasoning: 'Buy signal' } },
  },
  mockSnapshot,
];

describe('ArenaDecisionLog', () => {
  it('should show empty state when no snapshot', () => {
    const mockOnSelect = vi.fn();
    render(
      <ArenaDecisionLog
        snapshot={null}
        snapshots={[]}
        onSelectSnapshot={mockOnSelect}
      />
    );

    expect(screen.getByText('Decision Log')).toBeInTheDocument();
    expect(screen.getByText('No decisions yet')).toBeInTheDocument();
  });

  it('should render decision log card with title', () => {
    const mockOnSelect = vi.fn();
    render(
      <ArenaDecisionLog
        snapshot={mockSnapshot}
        snapshots={mockSnapshots}
        onSelectSnapshot={mockOnSelect}
      />
    );

    expect(screen.getByText('Decision Log')).toBeInTheDocument();
  });

  it('should display day selector', () => {
    const mockOnSelect = vi.fn();
    render(
      <ArenaDecisionLog
        snapshot={mockSnapshot}
        snapshots={mockSnapshots}
        onSelectSnapshot={mockOnSelect}
      />
    );

    // Should have a select trigger
    const trigger = screen.getByRole('combobox');
    expect(trigger).toBeInTheDocument();
  });

  it('should display all symbols from decisions', () => {
    const mockOnSelect = vi.fn();
    render(
      <ArenaDecisionLog
        snapshot={mockSnapshot}
        snapshots={mockSnapshots}
        onSelectSnapshot={mockOnSelect}
      />
    );

    expect(screen.getByText('AAPL')).toBeInTheDocument();
    expect(screen.getByText('NVDA')).toBeInTheDocument();
    expect(screen.getByText('TSLA')).toBeInTheDocument();
    expect(screen.getByText('AMD')).toBeInTheDocument();
  });

  it('should display action badges', () => {
    const mockOnSelect = vi.fn();
    render(
      <ArenaDecisionLog
        snapshot={mockSnapshot}
        snapshots={mockSnapshots}
        onSelectSnapshot={mockOnSelect}
      />
    );

    expect(screen.getByText('BUY')).toBeInTheDocument();
    expect(screen.getByText('HOLD')).toBeInTheDocument();
    expect(screen.getByText('NO_SIGNAL')).toBeInTheDocument();
    expect(screen.getByText('NO_DATA')).toBeInTheDocument();
  });

  it('should display score when available', () => {
    const mockOnSelect = vi.fn();
    render(
      <ArenaDecisionLog
        snapshot={mockSnapshot}
        snapshots={mockSnapshots}
        onSelectSnapshot={mockOnSelect}
      />
    );

    // Score is displayed as "80/100" within a span
    expect(screen.getByText('80/100')).toBeInTheDocument();
    expect(screen.getByText('40/100')).toBeInTheDocument();
  });

  it('should display reasoning when available', () => {
    const mockOnSelect = vi.fn();
    render(
      <ArenaDecisionLog
        snapshot={mockSnapshot}
        snapshots={mockSnapshots}
        onSelectSnapshot={mockOnSelect}
      />
    );

    expect(screen.getByText(/4\/5 criteria aligned/)).toBeInTheDocument();
    expect(screen.getByText('Already holding position')).toBeInTheDocument();
  });

  it('should call onSelectSnapshot when day is changed', async () => {
    const mockOnSelect = vi.fn();
    render(
      <ArenaDecisionLog
        snapshot={mockSnapshot}
        snapshots={mockSnapshots}
        onSelectSnapshot={mockOnSelect}
      />
    );

    // Open the select dropdown
    const trigger = screen.getByRole('combobox');
    fireEvent.click(trigger);

    // Find and click a different day option
    const option = await screen.findByRole('option', { name: /Day 8/i });
    fireEvent.click(option);

    expect(mockOnSelect).toHaveBeenCalledWith(mockSnapshots[0]);
  });

  it('should show empty decisions message when snapshot has no decisions', () => {
    const mockOnSelect = vi.fn();
    const emptySnapshot: Snapshot = {
      ...mockSnapshot,
      decisions: {},
    };
    render(
      <ArenaDecisionLog
        snapshot={emptySnapshot}
        snapshots={[emptySnapshot]}
        onSelectSnapshot={mockOnSelect}
      />
    );

    expect(screen.getByText('No decisions for this day')).toBeInTheDocument();
  });

  it('should highlight BUY decision cards with green border', () => {
    const mockOnSelect = vi.fn();
    const buyOnlySnapshot: Snapshot = {
      ...mockSnapshot,
      decisions: {
        AAPL: { action: 'BUY', score: 80, reasoning: 'Buy signal' },
      },
    };
    render(
      <ArenaDecisionLog
        snapshot={buyOnlySnapshot}
        snapshots={[buyOnlySnapshot]}
        onSelectSnapshot={mockOnSelect}
      />
    );

    // Find the decision card (div with border and rounded-lg classes)
    const aaplCard = screen.getByText('AAPL').closest('.rounded-lg');
    expect(aaplCard).toHaveClass('border-accent-bullish/30');
  });
});
