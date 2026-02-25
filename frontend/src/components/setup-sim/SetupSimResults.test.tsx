import { describe, expect, it } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { SetupSimResults } from './SetupSimResults';
import type { SetupSimulationResponse } from '@/types/setupSim';

// ---------------------------------------------------------------------------
// Mock data helpers
// ---------------------------------------------------------------------------

const mockResponseWithTrades: SetupSimulationResponse = {
  summary: {
    total_pnl: '125.50',
    total_pnl_pct: '12.55',
    total_capital_deployed: '1000.00',
    total_trades: 3,
    winning_trades: 2,
    losing_trades: 1,
    win_rate: '66.67',
    avg_gain: '100.00',
    avg_loss: '-74.50',
    position_size: '1000',
  },
  setups: [
    {
      symbol: 'AAPL',
      entry_price: '150.00',
      stop_loss_day1: '145.00',
      trailing_stop_pct: '5.00',
      start_date: '2024-01-01',
      times_triggered: 2,
      pnl: '200.00',
      trades: [
        {
          entry_date: '2024-01-10',
          entry_price: '150.00',
          exit_date: '2024-01-20',
          exit_price: '165.00',
          shares: 6,
          pnl: '90.00',
          return_pct: '10.00',
          exit_reason: 'trailing_stop',
        },
        {
          entry_date: '2024-02-01',
          entry_price: '150.00',
          exit_date: '2024-02-05',
          exit_price: '166.67',
          shares: 6,
          pnl: '110.00',
          return_pct: '11.11',
          exit_reason: 'simulation_end',
        },
      ],
    },
    {
      symbol: 'MSFT',
      entry_price: '400.00',
      stop_loss_day1: '390.00',
      trailing_stop_pct: '5.00',
      start_date: '2024-01-01',
      times_triggered: 1,
      pnl: '-74.50',
      trades: [
        {
          entry_date: '2024-01-15',
          entry_price: '400.00',
          exit_date: '2024-01-15',
          exit_price: '390.00',
          shares: 2,
          pnl: '-74.50',
          return_pct: '-2.50',
          exit_reason: 'stop_day1',
        },
      ],
    },
  ],
};

const mockResponseNoTrades: SetupSimulationResponse = {
  summary: {
    total_pnl: '0',
    total_pnl_pct: '0',
    total_capital_deployed: '0',
    total_trades: 0,
    winning_trades: 0,
    losing_trades: 0,
    win_rate: null,
    avg_gain: null,
    avg_loss: null,
    position_size: '1000',
  },
  setups: [
    {
      symbol: 'XYZ',
      entry_price: '500.00',
      stop_loss_day1: '490.00',
      trailing_stop_pct: '5.00',
      start_date: '2024-01-01',
      times_triggered: 0,
      pnl: '0',
      trades: [],
    },
  ],
};

// ---------------------------------------------------------------------------
// Empty state tests
// ---------------------------------------------------------------------------

describe('SetupSimResults — empty state', () => {
  it('shows "No setups were triggered" when total_trades is 0', () => {
    render(<SetupSimResults results={mockResponseNoTrades} />);
    expect(
      screen.getByText(/no setups were triggered during this period/i)
    ).toBeInTheDocument();
  });

  it('does not render summary metrics grid when total_trades is 0', () => {
    render(<SetupSimResults results={mockResponseNoTrades} />);
    expect(screen.queryByText('Total P&L')).not.toBeInTheDocument();
    expect(screen.queryByText('Win Rate')).not.toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Summary metrics tests
// ---------------------------------------------------------------------------

describe('SetupSimResults — summary metrics', () => {
  it('renders the Results card title', () => {
    render(<SetupSimResults results={mockResponseWithTrades} />);
    expect(screen.getByText('Results')).toBeInTheDocument();
  });

  it('renders all metric labels', () => {
    render(<SetupSimResults results={mockResponseWithTrades} />);
    expect(screen.getByText('Total P&L')).toBeInTheDocument();
    expect(screen.getByText('Total P&L %')).toBeInTheDocument();
    expect(screen.getByText('Win Rate')).toBeInTheDocument();
    expect(screen.getByText('Avg Gain')).toBeInTheDocument();
    expect(screen.getByText('Avg Loss')).toBeInTheDocument();
    expect(screen.getByText('Total Trades')).toBeInTheDocument();
  });

  it('formats Total P&L using formatPnL (currency)', () => {
    render(<SetupSimResults results={mockResponseWithTrades} />);
    expect(screen.getByText('$125.50')).toBeInTheDocument();
  });

  it('applies bullish class to positive Total P&L', () => {
    render(<SetupSimResults results={mockResponseWithTrades} />);
    const pnlValue = screen.getByText('$125.50');
    expect(pnlValue.className).toContain('text-accent-bullish');
  });

  it('applies bearish class to negative Total P&L', () => {
    const negativeResults: SetupSimulationResponse = {
      ...mockResponseWithTrades,
      summary: {
        ...mockResponseWithTrades.summary,
        total_pnl: '-50.00',
        total_pnl_pct: '-5.00',
      },
    };
    render(<SetupSimResults results={negativeResults} />);
    const pnlValue = screen.getByText('-$50.00');
    expect(pnlValue.className).toContain('text-accent-bearish');
  });

  it('formats Win Rate as a percentage with 1 decimal', () => {
    render(<SetupSimResults results={mockResponseWithTrades} />);
    expect(screen.getByText('66.7%')).toBeInTheDocument();
  });

  it('applies bullish class to win rate >= 50%', () => {
    render(<SetupSimResults results={mockResponseWithTrades} />);
    const winRateValue = screen.getByText('66.7%');
    expect(winRateValue.className).toContain('text-accent-bullish');
  });

  it('applies bearish class to win rate < 50%', () => {
    const lowWinRate: SetupSimulationResponse = {
      ...mockResponseWithTrades,
      summary: {
        ...mockResponseWithTrades.summary,
        win_rate: '33.33',
      },
    };
    render(<SetupSimResults results={lowWinRate} />);
    const winRateValue = screen.getByText('33.3%');
    expect(winRateValue.className).toContain('text-accent-bearish');
  });

  it('shows em dash for null avg_gain', () => {
    const noGain: SetupSimulationResponse = {
      ...mockResponseWithTrades,
      summary: { ...mockResponseWithTrades.summary, avg_gain: null },
    };
    render(<SetupSimResults results={noGain} />);
    // Avg Gain label is present
    expect(screen.getByText('Avg Gain')).toBeInTheDocument();
    // Value cell shows em dash
    const emDashes = screen.getAllByText('—');
    expect(emDashes.length).toBeGreaterThan(0);
  });

  it('shows em dash for null avg_loss', () => {
    const noLoss: SetupSimulationResponse = {
      ...mockResponseWithTrades,
      summary: { ...mockResponseWithTrades.summary, avg_loss: null },
    };
    render(<SetupSimResults results={noLoss} />);
    expect(screen.getByText('Avg Loss')).toBeInTheDocument();
    const emDashes = screen.getAllByText('—');
    expect(emDashes.length).toBeGreaterThan(0);
  });

  it('formats Total Trades as an integer', () => {
    render(<SetupSimResults results={mockResponseWithTrades} />);
    expect(screen.getByText('3')).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Per-setup sections
// ---------------------------------------------------------------------------

describe('SetupSimResults — per-setup sections', () => {
  it('renders the Per-Setup Breakdown card title', () => {
    render(<SetupSimResults results={mockResponseWithTrades} />);
    expect(screen.getByText('Per-Setup Breakdown')).toBeInTheDocument();
  });

  it('renders a section for each setup', () => {
    render(<SetupSimResults results={mockResponseWithTrades} />);
    expect(screen.getByTestId('setup-section-AAPL')).toBeInTheDocument();
    expect(screen.getByTestId('setup-section-MSFT')).toBeInTheDocument();
  });

  it('shows symbol name in each section header', () => {
    render(<SetupSimResults results={mockResponseWithTrades} />);
    // Symbol names appear in the collapsible triggers
    const sectionAAPL = screen.getByTestId('setup-section-AAPL');
    expect(sectionAAPL).toHaveTextContent('AAPL');

    const sectionMSFT = screen.getByTestId('setup-section-MSFT');
    expect(sectionMSFT).toHaveTextContent('MSFT');
  });

  it('shows trade count in section header', () => {
    render(<SetupSimResults results={mockResponseWithTrades} />);
    const sectionAAPL = screen.getByTestId('setup-section-AAPL');
    expect(sectionAAPL).toHaveTextContent('2 trades');

    const sectionMSFT = screen.getByTestId('setup-section-MSFT');
    expect(sectionMSFT).toHaveTextContent('1 trade');
  });

  it('trade table is not visible before expanding', () => {
    render(<SetupSimResults results={mockResponseWithTrades} />);
    // Table headers should not be visible before expanding
    expect(screen.queryByText('Entry Date')).not.toBeInTheDocument();
  });

  it('expands to show trade table on click', () => {
    render(<SetupSimResults results={mockResponseWithTrades} />);

    const sectionAAPL = screen.getByTestId('setup-section-AAPL');
    fireEvent.click(sectionAAPL);

    // Table headers should now be visible
    expect(screen.getByText('Entry Date')).toBeInTheDocument();
    expect(screen.getByText('Entry Price')).toBeInTheDocument();
    expect(screen.getByText('Exit Date')).toBeInTheDocument();
    expect(screen.getByText('Exit Price')).toBeInTheDocument();
    expect(screen.getByText('Shares')).toBeInTheDocument();
    expect(screen.getByText('Exit Reason')).toBeInTheDocument();
  });

  it('shows trade dates after expanding', () => {
    render(<SetupSimResults results={mockResponseWithTrades} />);

    fireEvent.click(screen.getByTestId('setup-section-AAPL'));

    expect(screen.getByText('2024-01-10')).toBeInTheDocument();
    expect(screen.getByText('2024-01-20')).toBeInTheDocument();
  });

  it('shows formatted exit reasons after expanding', () => {
    render(<SetupSimResults results={mockResponseWithTrades} />);

    fireEvent.click(screen.getByTestId('setup-section-MSFT'));

    expect(screen.getByText('Day 1 Stop')).toBeInTheDocument();
  });

  it('collapses again on second click', () => {
    render(<SetupSimResults results={mockResponseWithTrades} />);

    const sectionAAPL = screen.getByTestId('setup-section-AAPL');
    fireEvent.click(sectionAAPL);
    expect(screen.getByText('Entry Date')).toBeInTheDocument();

    fireEvent.click(sectionAAPL);
    expect(screen.queryByText('Entry Date')).not.toBeInTheDocument();
  });

  it('renders "Trailing Stop" exit reason label correctly', () => {
    render(<SetupSimResults results={mockResponseWithTrades} />);

    fireEvent.click(screen.getByTestId('setup-section-AAPL'));

    expect(screen.getAllByText('Trailing Stop').length).toBeGreaterThan(0);
  });

  it('renders "End of Sim" exit reason label correctly', () => {
    render(<SetupSimResults results={mockResponseWithTrades} />);

    fireEvent.click(screen.getByTestId('setup-section-AAPL'));

    expect(screen.getByText('End of Sim')).toBeInTheDocument();
  });

  it('shows "No trades triggered" message when setup has 0 trades but overall trades > 0', () => {
    const mixedResults: SetupSimulationResponse = {
      ...mockResponseWithTrades,
      setups: [
        ...mockResponseWithTrades.setups,
        {
          symbol: 'NVDA',
          entry_price: '800.00',
          stop_loss_day1: '780.00',
          trailing_stop_pct: '5.00',
          start_date: '2024-01-01',
          times_triggered: 0,
          pnl: '0',
          trades: [],
        },
      ],
    };
    render(<SetupSimResults results={mixedResults} />);

    fireEvent.click(screen.getByTestId('setup-section-NVDA'));

    expect(screen.getByText(/no trades triggered for this setup/i)).toBeInTheDocument();
  });
});
