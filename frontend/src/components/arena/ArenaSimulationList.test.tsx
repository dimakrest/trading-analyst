import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { ArenaSimulationList } from './ArenaSimulationList';
import type { Simulation } from '../../types/arena';

// Mock useNavigate
const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

const mockSimulations: Simulation[] = [
  {
    id: 1,
    name: 'Test Simulation 1',
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
    status: 'completed',
    current_day: 22,
    total_days: 22,
    final_equity: '10500',
    total_return_pct: '5.00',
    total_trades: 5,
    winning_trades: 3,
    max_drawdown_pct: '2.50',
    avg_hold_days: null,
    avg_win_pnl: null,
    avg_loss_pnl: null,
    profit_factor: null,
    sharpe_ratio: null,
    total_realized_pnl: null,
    created_at: '2024-01-01T10:00:00Z',
  },
  {
    id: 2,
    name: null,
    stock_list_id: null,
    stock_list_name: null,
    symbols: ['AMD', 'MSFT', 'GOOG', 'META', 'AMZN'],
    start_date: '2024-02-01',
    end_date: '2024-02-29',
    initial_capital: '20000',
    position_size: '2000',
    agent_type: 'live20',
    trailing_stop_pct: '5.0',
    min_buy_score: 60,
    scoring_algorithm: null,
    portfolio_strategy: null,
    max_per_sector: null,
    max_open_positions: null,
    status: 'running',
    current_day: 10,
    total_days: 20,
    final_equity: null,
    total_return_pct: null,
    total_trades: 2,
    winning_trades: 1,
    max_drawdown_pct: null,
    avg_hold_days: null,
    avg_win_pnl: null,
    avg_loss_pnl: null,
    profit_factor: null,
    sharpe_ratio: null,
    total_realized_pnl: null,
    created_at: '2024-02-01T10:00:00Z',
  },
  {
    id: 3,
    name: 'Failed Test',
    stock_list_id: null,
    stock_list_name: null,
    symbols: ['AAPL'],
    start_date: '2024-03-01',
    end_date: '2024-03-15',
    initial_capital: '5000',
    position_size: '500',
    agent_type: 'live20',
    trailing_stop_pct: '5.0',
    min_buy_score: 60,
    scoring_algorithm: null,
    portfolio_strategy: null,
    max_per_sector: null,
    max_open_positions: null,
    status: 'failed',
    current_day: 5,
    total_days: 10,
    final_equity: '4800',
    total_return_pct: '-4.00',
    total_trades: 1,
    winning_trades: 0,
    max_drawdown_pct: '5.00',
    avg_hold_days: null,
    avg_win_pnl: null,
    avg_loss_pnl: null,
    profit_factor: null,
    sharpe_ratio: null,
    total_realized_pnl: null,
    created_at: '2024-03-01T10:00:00Z',
  },
];

describe('ArenaSimulationList', () => {
  const mockOnRefresh = vi.fn();
  const mockOnReplay = vi.fn();

  beforeEach(() => {
    mockNavigate.mockClear();
    mockOnRefresh.mockClear();
    mockOnReplay.mockClear();
  });

  it('should show loading skeletons when loading', () => {
    render(
      <MemoryRouter>
        <ArenaSimulationList
          simulations={[]}
          isLoading={true}
          onRefresh={mockOnRefresh}
          onReplay={mockOnReplay}
        />
      </MemoryRouter>
    );

    // Should show skeleton elements (check for the Skeleton component with animate-pulse)
    const skeletons = document.querySelectorAll('[class*="animate-pulse"]');
    expect(skeletons.length).toBeGreaterThan(0);
  });

  it('should show empty state when no simulations', () => {
    render(
      <MemoryRouter>
        <ArenaSimulationList
          simulations={[]}
          isLoading={false}
          onRefresh={mockOnRefresh}
          onReplay={mockOnReplay}
        />
      </MemoryRouter>
    );

    expect(screen.getByText(/no simulations yet/i)).toBeInTheDocument();
  });

  it('should render simulation table with data', () => {
    render(
      <MemoryRouter>
        <ArenaSimulationList
          simulations={mockSimulations}
          isLoading={false}
          onRefresh={mockOnRefresh}
          onReplay={mockOnReplay}
        />
      </MemoryRouter>
    );

    // Table headers
    expect(screen.getByText('Name')).toBeInTheDocument();
    expect(screen.getByText('Symbols')).toBeInTheDocument();
    expect(screen.getByText('Date Range')).toBeInTheDocument();
    expect(screen.getByText('Status')).toBeInTheDocument();
    expect(screen.getByText('Return')).toBeInTheDocument();

    // First simulation
    expect(screen.getByText('Test Simulation 1')).toBeInTheDocument();
    expect(screen.getByText(/AAPL, NVDA, TSLA/)).toBeInTheDocument();
    expect(screen.getByText('completed')).toBeInTheDocument();
    expect(screen.getByText('+5.00%')).toBeInTheDocument();
  });

  it('should show default name for simulation without name', () => {
    render(
      <MemoryRouter>
        <ArenaSimulationList
          simulations={mockSimulations}
          isLoading={false}
          onRefresh={mockOnRefresh}
          onReplay={mockOnReplay}
        />
      </MemoryRouter>
    );

    expect(screen.getByText('Simulation #2')).toBeInTheDocument();
  });

  it('should truncate symbols list and show count', () => {
    render(
      <MemoryRouter>
        <ArenaSimulationList
          simulations={mockSimulations}
          isLoading={false}
          onRefresh={mockOnRefresh}
          onReplay={mockOnReplay}
        />
      </MemoryRouter>
    );

    // Second simulation has 5 symbols, should show first 3 + count
    expect(screen.getByText(/AMD, MSFT, GOOG/)).toBeInTheDocument();
    expect(screen.getByText(/\+2/)).toBeInTheDocument();
  });

  it('should show status badges with correct styling', () => {
    render(
      <MemoryRouter>
        <ArenaSimulationList
          simulations={mockSimulations}
          isLoading={false}
          onRefresh={mockOnRefresh}
          onReplay={mockOnReplay}
        />
      </MemoryRouter>
    );

    expect(screen.getByText('completed')).toBeInTheDocument();
    expect(screen.getByText('running')).toBeInTheDocument();
    expect(screen.getByText('failed')).toBeInTheDocument();
  });

  it('should show negative return with proper formatting', () => {
    render(
      <MemoryRouter>
        <ArenaSimulationList
          simulations={mockSimulations}
          isLoading={false}
          onRefresh={mockOnRefresh}
          onReplay={mockOnReplay}
        />
      </MemoryRouter>
    );

    expect(screen.getByText('-4.00%')).toBeInTheDocument();
  });

  it('should show dash for null return', () => {
    render(
      <MemoryRouter>
        <ArenaSimulationList
          simulations={mockSimulations}
          isLoading={false}
          onRefresh={mockOnRefresh}
          onReplay={mockOnReplay}
        />
      </MemoryRouter>
    );

    // Second simulation has null total_return_pct
    expect(screen.getByText('-')).toBeInTheDocument();
  });

  it('should navigate to detail page when row is clicked', () => {
    render(
      <MemoryRouter>
        <ArenaSimulationList
          simulations={mockSimulations}
          isLoading={false}
          onRefresh={mockOnRefresh}
          onReplay={mockOnReplay}
        />
      </MemoryRouter>
    );

    const row = screen.getByText('Test Simulation 1').closest('tr');
    fireEvent.click(row!);

    expect(mockNavigate).toHaveBeenCalledWith('/arena/1');
  });

  it('should call onRefresh when refresh button is clicked', () => {
    render(
      <MemoryRouter>
        <ArenaSimulationList
          simulations={mockSimulations}
          isLoading={false}
          onRefresh={mockOnRefresh}
          onReplay={mockOnReplay}
        />
      </MemoryRouter>
    );

    const refreshButton = screen.getByRole('button', { name: /refresh/i });
    fireEvent.click(refreshButton);

    expect(mockOnRefresh).toHaveBeenCalled();
  });

  it('should show stock list name when available', () => {
    const simulationWithStockList: Simulation[] = [
      {
        ...mockSimulations[0],
        stock_list_id: 1,
        stock_list_name: 'Tech Stocks',
      },
    ];

    render(
      <MemoryRouter>
        <ArenaSimulationList
          simulations={simulationWithStockList}
          isLoading={false}
          onRefresh={mockOnRefresh}
          onReplay={mockOnReplay}
        />
      </MemoryRouter>
    );

    expect(screen.getByText('List: Tech Stocks')).toBeInTheDocument();
  });

  it('should not show stock list info when null', () => {
    render(
      <MemoryRouter>
        <ArenaSimulationList
          simulations={mockSimulations}
          isLoading={false}
          onRefresh={mockOnRefresh}
          onReplay={mockOnReplay}
        />
      </MemoryRouter>
    );

    // All mockSimulations have stock_list_name: null
    expect(screen.queryByText(/List:/)).not.toBeInTheDocument();
  });
});
