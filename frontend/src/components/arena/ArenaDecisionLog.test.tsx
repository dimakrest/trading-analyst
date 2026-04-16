import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { ArenaDecisionLog } from './ArenaDecisionLog';
import type { DecisionEntry, Snapshot } from '../../types/arena';

const mockDecisions: Record<string, DecisionEntry> = {
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
  circuit_breaker_state: 'disabled',
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
    circuit_breaker_state: 'disabled',
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
    circuit_breaker_state: 'disabled',
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

  it('should show IBS FILTERED badge when ibs_filtered is true', () => {
    const mockOnSelect = vi.fn();
    const ibsFilteredSnapshot: Snapshot = {
      ...mockSnapshot,
      decisions: {
        AAPL: { action: 'BUY', score: 75, reasoning: null, ibs_filtered: true, ibs_value: 0.72 },
      },
    };
    render(
      <ArenaDecisionLog
        snapshot={ibsFilteredSnapshot}
        snapshots={[ibsFilteredSnapshot]}
        onSelectSnapshot={mockOnSelect}
      />
    );

    expect(screen.getByText('IBS FILTERED')).toBeInTheDocument();
  });

  it('should display ibs_value when present in decision entry', () => {
    const mockOnSelect = vi.fn();
    const ibsValueSnapshot: Snapshot = {
      ...mockSnapshot,
      decisions: {
        NVDA: { action: 'BUY', score: 65, reasoning: null, ibs_filtered: true, ibs_value: 0.72 },
      },
    };
    render(
      <ArenaDecisionLog
        snapshot={ibsValueSnapshot}
        snapshots={[ibsValueSnapshot]}
        onSelectSnapshot={mockOnSelect}
      />
    );

    expect(screen.getByText('0.72')).toBeInTheDocument();
    // The IBS value is rendered with a label prefix
    expect(screen.getByText(/IBS:/)).toBeInTheDocument();
  });

  it('should not show IBS FILTERED badge when ibs_filtered is absent', () => {
    const mockOnSelect = vi.fn();
    const normalSnapshot: Snapshot = {
      ...mockSnapshot,
      decisions: {
        AAPL: { action: 'BUY', score: 80, reasoning: 'Buy signal' },
      },
    };
    render(
      <ArenaDecisionLog
        snapshot={normalSnapshot}
        snapshots={[normalSnapshot]}
        onSelectSnapshot={mockOnSelect}
      />
    );

    expect(screen.queryByText('IBS FILTERED')).not.toBeInTheDocument();
  });

  describe('Phase 5: Market Conditions Banner', () => {
    it('banner hidden when circuit_breaker_state is disabled', () => {
      const mockOnSelect = vi.fn();
      const snap: Snapshot = {
        ...mockSnapshot,
        circuit_breaker_state: 'disabled',
        decisions: { AAPL: { action: 'BUY', score: 80, reasoning: null } },
      };
      render(
        <ArenaDecisionLog snapshot={snap} snapshots={[snap]} onSelectSnapshot={mockOnSelect} />
      );
      expect(screen.queryByTestId('cb-banner-clear')).not.toBeInTheDocument();
      expect(screen.queryByTestId('cb-banner-triggered')).not.toBeInTheDocument();
      expect(screen.queryByTestId('cb-banner-data-unavailable')).not.toBeInTheDocument();
    });

    it('banner renders with neutral/info style when state is clear', () => {
      const mockOnSelect = vi.fn();
      const snap: Snapshot = {
        ...mockSnapshot,
        circuit_breaker_state: 'clear',
        circuit_breaker_atr_pct: '1.5000',
        decisions: { AAPL: { action: 'BUY', score: 80, reasoning: null } },
      };
      render(
        <ArenaDecisionLog snapshot={snap} snapshots={[snap]} onSelectSnapshot={mockOnSelect} />
      );
      expect(screen.getByTestId('cb-banner-clear')).toBeInTheDocument();
      expect(screen.getByText(/1\.50%/)).toBeInTheDocument();
      expect(screen.getByText(/clear/i)).toBeInTheDocument();
    });

    it('banner renders with alert style when state is triggered', () => {
      const mockOnSelect = vi.fn();
      const snap: Snapshot = {
        ...mockSnapshot,
        circuit_breaker_state: 'triggered',
        circuit_breaker_atr_pct: '3.2000',
        decisions: {},
      };
      render(
        <ArenaDecisionLog snapshot={snap} snapshots={[snap]} onSelectSnapshot={mockOnSelect} />
      );
      const banner = screen.getByTestId('cb-banner-triggered');
      expect(banner).toBeInTheDocument();
      expect(banner).toHaveAttribute('role', 'alert');
      expect(screen.getByText(/circuit breaker triggered/i)).toBeInTheDocument();
      expect(screen.getByText(/3\.20%/)).toBeInTheDocument();
      expect(screen.getByText(/all entries blocked/i)).toBeInTheDocument();
    });

    it('banner renders before symbol rows when state is triggered', () => {
      const mockOnSelect = vi.fn();
      const snap: Snapshot = {
        ...mockSnapshot,
        circuit_breaker_state: 'triggered',
        circuit_breaker_atr_pct: '3.2000',
        decisions: { AAPL: { action: 'BUY', score: 80, reasoning: null } },
      };
      render(
        <ArenaDecisionLog snapshot={snap} snapshots={[snap]} onSelectSnapshot={mockOnSelect} />
      );
      const banner = screen.getByTestId('market-conditions-banner');
      const symbolBadge = screen.getByText('AAPL');
      // Banner's parent should appear before the symbol in the DOM
      expect(banner.compareDocumentPosition(symbolBadge) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    });

    it('banner renders when decisions is empty (keyed on state, not decisions)', () => {
      const mockOnSelect = vi.fn();
      const snap: Snapshot = {
        ...mockSnapshot,
        circuit_breaker_state: 'triggered',
        circuit_breaker_atr_pct: '3.2000',
        decisions: {},
      };
      render(
        <ArenaDecisionLog snapshot={snap} snapshots={[snap]} onSelectSnapshot={mockOnSelect} />
      );
      expect(screen.getByTestId('cb-banner-triggered')).toBeInTheDocument();
    });

    it('banner renders with clear state even when decisions is empty', () => {
      const mockOnSelect = vi.fn();
      const snap: Snapshot = {
        ...mockSnapshot,
        circuit_breaker_state: 'clear',
        circuit_breaker_atr_pct: '1.8000',
        decisions: {},
      };
      render(
        <ArenaDecisionLog snapshot={snap} snapshots={[snap]} onSelectSnapshot={mockOnSelect} />
      );
      expect(screen.getByTestId('cb-banner-clear')).toBeInTheDocument();
    });

    it('banner renders with distinct warning style for data_unavailable (not red, not neutral)', () => {
      const mockOnSelect = vi.fn();
      const snap: Snapshot = {
        ...mockSnapshot,
        circuit_breaker_state: 'data_unavailable',
        decisions: {},
      };
      render(
        <ArenaDecisionLog snapshot={snap} snapshots={[snap]} onSelectSnapshot={mockOnSelect} />
      );
      const banner = screen.getByTestId('cb-banner-data-unavailable');
      expect(banner).toBeInTheDocument();
      expect(banner).toHaveAttribute('role', 'alert');
      expect(screen.getByText(/circuit breaker bypassed/i)).toBeInTheDocument();
      expect(screen.getByText(/market data unavailable/i)).toBeInTheDocument();
      // amber styling (not red/destructive, not neutral/blue)
      expect(banner.className).toMatch(/amber/);
      expect(banner.className).not.toMatch(/destructive/);
      expect(banner.className).not.toMatch(/blue/);
    });

    it('shows regime_state when present', () => {
      const mockOnSelect = vi.fn();
      const snap: Snapshot = {
        ...mockSnapshot,
        circuit_breaker_state: 'clear',
        circuit_breaker_atr_pct: '1.5000',
        regime_state: 'bull',
        decisions: {},
      };
      render(
        <ArenaDecisionLog snapshot={snap} snapshots={[snap]} onSelectSnapshot={mockOnSelect} />
      );
      expect(screen.getByText(/market regime/i)).toBeInTheDocument();
      expect(screen.getByText(/bull/i)).toBeInTheDocument();
    });
  });

  describe('Phase 5: Per-symbol badges', () => {
    it('shows MA50 FILTERED badge when ma50_filtered is true', () => {
      const mockOnSelect = vi.fn();
      const snap: Snapshot = {
        ...mockSnapshot,
        circuit_breaker_state: 'disabled',
        decisions: {
          AAPL: { action: 'BUY', score: 70, reasoning: null, ma50_filtered: true },
        },
      };
      render(
        <ArenaDecisionLog snapshot={snap} snapshots={[snap]} onSelectSnapshot={mockOnSelect} />
      );
      expect(screen.getByText('MA50 FILTERED')).toBeInTheDocument();
    });

    it('does not show MA50 FILTERED badge when ma50_filtered is absent', () => {
      const mockOnSelect = vi.fn();
      const snap: Snapshot = {
        ...mockSnapshot,
        circuit_breaker_state: 'disabled',
        decisions: {
          AAPL: { action: 'BUY', score: 70, reasoning: null },
        },
      };
      render(
        <ArenaDecisionLog snapshot={snap} snapshots={[snap]} onSelectSnapshot={mockOnSelect} />
      );
      expect(screen.queryByText('MA50 FILTERED')).not.toBeInTheDocument();
    });

    it('shows CIRCUIT BREAKER badge when circuit_breaker_filtered is true', () => {
      const mockOnSelect = vi.fn();
      const snap: Snapshot = {
        ...mockSnapshot,
        circuit_breaker_state: 'triggered',
        decisions: {
          AAPL: { action: 'BUY', score: 70, reasoning: null, circuit_breaker_filtered: true },
        },
      };
      render(
        <ArenaDecisionLog snapshot={snap} snapshots={[snap]} onSelectSnapshot={mockOnSelect} />
      );
      expect(screen.getByText('CIRCUIT BREAKER')).toBeInTheDocument();
    });

    it('shows IBS tooltip when ibs_filtered is true and ma50_filtered is absent', () => {
      const mockOnSelect = vi.fn();
      const snap: Snapshot = {
        ...mockSnapshot,
        circuit_breaker_state: 'disabled',
        decisions: {
          AAPL: { action: 'BUY', score: 75, reasoning: null, ibs_filtered: true, ibs_value: 0.72 },
        },
      };
      render(
        <ArenaDecisionLog snapshot={snap} snapshots={[snap]} onSelectSnapshot={mockOnSelect} />
      );
      const ibsBadge = screen.getByText('IBS FILTERED');
      const ibsBadgeContainer = ibsBadge.closest('[title]');
      expect(ibsBadgeContainer).toHaveAttribute(
        'title',
        'IBS filter caught this symbol before MA50 was evaluated. MA50 status unknown.'
      );
    });

    it('does not show IBS tooltip when both ibs_filtered and ma50_filtered are present', () => {
      const mockOnSelect = vi.fn();
      const snap: Snapshot = {
        ...mockSnapshot,
        circuit_breaker_state: 'disabled',
        decisions: {
          AAPL: {
            action: 'BUY',
            score: 75,
            reasoning: null,
            ibs_filtered: true,
            ibs_value: 0.72,
            ma50_filtered: true,
          },
        },
      };
      render(
        <ArenaDecisionLog snapshot={snap} snapshots={[snap]} onSelectSnapshot={mockOnSelect} />
      );
      const ibsBadge = screen.getByText('IBS FILTERED');
      const ibsBadgeContainer = ibsBadge.closest('[title]');
      expect(ibsBadgeContainer).toBeNull();
    });

    it('uses DecisionEntry types (not AgentDecision) in mocks', () => {
      // DecisionEntry has portfolio_selected, ibs_filtered, ma50_filtered, circuit_breaker_filtered
      // This test validates that the mock data uses the correct extended type.
      const decisionEntryMock: DecisionEntry = {
        action: 'BUY',
        score: 80,
        reasoning: null,
        portfolio_selected: true,
        ibs_filtered: false,
        ma50_filtered: false,
        circuit_breaker_filtered: false,
      };
      const snap: Snapshot = {
        ...mockSnapshot,
        circuit_breaker_state: 'disabled',
        decisions: { AAPL: decisionEntryMock },
      };
      const mockOnSelect = vi.fn();
      render(
        <ArenaDecisionLog snapshot={snap} snapshots={[snap]} onSelectSnapshot={mockOnSelect} />
      );
      expect(screen.getByText('AAPL')).toBeInTheDocument();
    });
  });

  describe('Phase 5: circuit_breaker_atr_pct display', () => {
    it('shows formatted ATR% in the clear banner', () => {
      const mockOnSelect = vi.fn();
      const snap: Snapshot = {
        ...mockSnapshot,
        circuit_breaker_state: 'clear',
        circuit_breaker_atr_pct: '2.8000',
        decisions: {},
      };
      render(
        <ArenaDecisionLog snapshot={snap} snapshots={[snap]} onSelectSnapshot={mockOnSelect} />
      );
      expect(screen.getByText(/2\.80%/)).toBeInTheDocument();
    });

    it('shows dash when circuit_breaker_atr_pct is null in triggered banner', () => {
      const mockOnSelect = vi.fn();
      const snap: Snapshot = {
        ...mockSnapshot,
        circuit_breaker_state: 'triggered',
        circuit_breaker_atr_pct: null,
        decisions: {},
      };
      render(
        <ArenaDecisionLog snapshot={snap} snapshots={[snap]} onSelectSnapshot={mockOnSelect} />
      );
      expect(screen.getByTestId('cb-banner-triggered')).toBeInTheDocument();
      expect(screen.getByText(/—/)).toBeInTheDocument();
    });
  });
});
