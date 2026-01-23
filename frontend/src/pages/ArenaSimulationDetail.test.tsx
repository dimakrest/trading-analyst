import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { ArenaSimulationDetail } from './ArenaSimulationDetail';
import type { Position, Simulation, SimulationDetail, Snapshot } from '../types/arena';

// Mock useNavigate
const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

// Mock the arena service
const mockGetSimulation = vi.fn();
const mockCancelSimulation = vi.fn();
const mockDeleteSimulation = vi.fn();
vi.mock('../services/arenaService', () => ({
  getSimulation: (...args: unknown[]) => mockGetSimulation(...args),
  cancelSimulation: (...args: unknown[]) => mockCancelSimulation(...args),
  deleteSimulation: (...args: unknown[]) => mockDeleteSimulation(...args),
}));

// Mock sonner toast
vi.mock('sonner', () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}));

const mockSimulation: Simulation = {
  id: 1,
  name: 'Test Simulation',
  stock_list_id: null,
  stock_list_name: null,
  symbols: ['AAPL', 'NVDA'],
  start_date: '2024-01-01',
  end_date: '2024-01-31',
  initial_capital: '10000',
  position_size: '1000',
  agent_type: 'live20',
  trailing_stop_pct: '5.0',
  min_buy_score: 60,
  status: 'completed',
  current_day: 22,
  total_days: 22,
  final_equity: '10830',
  total_return_pct: '8.30',
  total_trades: 12,
  winning_trades: 7,
  max_drawdown_pct: '4.10',
  created_at: '2024-01-01T10:00:00Z',
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
  },
];

const mockSnapshots: Snapshot[] = [
  {
    id: 1,
    snapshot_date: '2024-01-10',
    day_number: 9,
    cash: '7156.50',
    positions_value: '3673.50',
    total_equity: '10830.00',
    daily_pnl: '150.00',
    daily_return_pct: '1.40',
    cumulative_return_pct: '8.30',
    open_position_count: 1,
    decisions: {
      AAPL: { action: 'HOLD', score: null, reasoning: 'Already holding' },
      NVDA: { action: 'BUY', score: 80, reasoning: 'Score: 80/100' },
    },
  },
];

const mockSimulationDetail: SimulationDetail = {
  simulation: mockSimulation,
  positions: mockPositions,
  snapshots: mockSnapshots,
};

const renderWithRouter = (simulationId: string = '1') => {
  return render(
    <MemoryRouter initialEntries={[`/arena/${simulationId}`]}>
      <Routes>
        <Route path="/arena/:id" element={<ArenaSimulationDetail />} />
      </Routes>
    </MemoryRouter>
  );
};

describe('ArenaSimulationDetail', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockGetSimulation.mockResolvedValue(mockSimulationDetail);
    mockCancelSimulation.mockResolvedValue(undefined);
    mockDeleteSimulation.mockResolvedValue(undefined);
  });

  it('should show loading state initially', () => {
    // Make getSimulation hang to keep loading state
    mockGetSimulation.mockImplementation(() => new Promise(() => {}));

    renderWithRouter();

    // Check for the loading spinner (svg with animate-spin class)
    const spinner = document.querySelector('.animate-spin');
    expect(spinner).toBeInTheDocument();
  });

  it('should render simulation detail after loading', async () => {
    renderWithRouter();

    await waitFor(() => {
      expect(screen.getByText('Test Simulation')).toBeInTheDocument();
    });

    // Symbols are now displayed as individual badges in the configuration panel
    expect(screen.getAllByText('AAPL').length).toBeGreaterThan(0);
    expect(screen.getAllByText('NVDA').length).toBeGreaterThan(0);
    expect(screen.getByText('completed')).toBeInTheDocument();
  });

  it('should display results table', async () => {
    renderWithRouter();

    await waitFor(() => {
      expect(screen.getByText('Results')).toBeInTheDocument();
    });

    expect(screen.getByText('Live20')).toBeInTheDocument();
    // Return appears in both results table and portfolio, use getAllBy
    expect(screen.getAllByText('+8.30%').length).toBeGreaterThan(0);
    expect(screen.getByText('58.3%')).toBeInTheDocument(); // Win rate
  });

  it('should display portfolio section', async () => {
    renderWithRouter();

    await waitFor(() => {
      expect(screen.getByText('Portfolio')).toBeInTheDocument();
    });

    expect(screen.getByText('Cash')).toBeInTheDocument();
    expect(screen.getByText('Total Equity')).toBeInTheDocument();
    // 'Return' appears multiple times (header and value), use getAllBy
    expect(screen.getAllByText(/Return/).length).toBeGreaterThan(0);
  });

  it('should display open positions', async () => {
    renderWithRouter();

    await waitFor(() => {
      // AAPL appears in positions table
      const aaplElements = screen.getAllByText('AAPL');
      expect(aaplElements.length).toBeGreaterThan(0);
    });

    await waitFor(() => {
      expect(screen.getByText('$195.00')).toBeInTheDocument();
      expect(screen.getByText('$185.25')).toBeInTheDocument();
    });
  });

  it('should display decision log', async () => {
    renderWithRouter();

    await waitFor(() => {
      expect(screen.getByText('Decision Log')).toBeInTheDocument();
    });

    // The decisions include AAPL with HOLD action and NVDA with BUY action
    // Check for the decision cards by looking for the symbols
    await waitFor(() => {
      const decisionLog = screen.getByText('Decision Log').closest('.rounded-xl');
      expect(decisionLog).toBeInTheDocument();
    });
    // Check for day selector
    expect(screen.getByRole('combobox')).toBeInTheDocument();
  });

  it('should show progress bar for running simulation', async () => {
    const runningSimDetail: SimulationDetail = {
      ...mockSimulationDetail,
      simulation: {
        ...mockSimulation,
        status: 'running',
        current_day: 10,
      },
    };
    mockGetSimulation.mockResolvedValue(runningSimDetail);

    renderWithRouter();

    await waitFor(() => {
      // Progress percentage should be visible
      expect(screen.getByText('45%')).toBeInTheDocument(); // 10/22 = ~45%
      expect(screen.getByText('Processing in background...')).toBeInTheDocument();
    });
  });

  it('should show cancel button for running simulation', async () => {
    const runningSimDetail: SimulationDetail = {
      ...mockSimulationDetail,
      simulation: {
        ...mockSimulation,
        status: 'running',
      },
    };
    mockGetSimulation.mockResolvedValue(runningSimDetail);

    renderWithRouter();

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /cancel/i })).toBeInTheDocument();
    });
  });

  it('should show delete button for completed simulation', async () => {
    renderWithRouter();

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /delete/i })).toBeInTheDocument();
    });
  });

  it('should navigate back when back button is clicked', async () => {
    renderWithRouter();

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /back to arena/i })).toBeInTheDocument();
    });

    const backButton = screen.getByRole('button', { name: /back to arena/i });
    fireEvent.click(backButton);

    expect(mockNavigate).toHaveBeenCalledWith('/arena');
  });

  it('should cancel simulation when cancel is clicked', async () => {
    const runningSimDetail: SimulationDetail = {
      ...mockSimulationDetail,
      simulation: {
        ...mockSimulation,
        status: 'running',
      },
    };
    mockGetSimulation.mockResolvedValue(runningSimDetail);

    const { toast } = await import('sonner');
    const user = userEvent.setup();

    renderWithRouter();

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /cancel/i })).toBeInTheDocument();
    });

    const cancelButton = screen.getByRole('button', { name: /cancel/i });
    await user.click(cancelButton);

    // Dialog should appear
    await waitFor(() => {
      expect(screen.getByText(/stop simulation\?/i)).toBeInTheDocument();
    });

    // Click the confirm button in the dialog
    const confirmButton = screen.getByRole('button', { name: /stop simulation/i });
    await user.click(confirmButton);

    await waitFor(() => {
      expect(mockCancelSimulation).toHaveBeenCalledWith(1);
    });

    expect(toast.success).toHaveBeenCalledWith('Simulation cancelled');
  });

  it('should not cancel if user declines confirmation', async () => {
    const runningSimDetail: SimulationDetail = {
      ...mockSimulationDetail,
      simulation: {
        ...mockSimulation,
        status: 'running',
      },
    };
    mockGetSimulation.mockResolvedValue(runningSimDetail);

    const user = userEvent.setup();

    renderWithRouter();

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /cancel/i })).toBeInTheDocument();
    });

    const cancelButton = screen.getByRole('button', { name: /cancel/i });
    await user.click(cancelButton);

    // Dialog should appear
    await waitFor(() => {
      expect(screen.getByText(/stop simulation\?/i)).toBeInTheDocument();
    });

    // Click the "Continue" button (cancel the dialog)
    const continueButton = screen.getByRole('button', { name: /continue/i });
    await user.click(continueButton);

    // Should not have called the cancel API
    expect(mockCancelSimulation).not.toHaveBeenCalled();
  });

  it('should delete and navigate back when delete is clicked', async () => {
    const user = userEvent.setup();

    renderWithRouter();

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /delete/i })).toBeInTheDocument();
    });

    const deleteButton = screen.getByRole('button', { name: /delete/i });
    await user.click(deleteButton);

    // Dialog should appear
    await waitFor(() => {
      expect(screen.getByText(/delete simulation\?/i)).toBeInTheDocument();
    });

    // Click the confirm button in the dialog
    const confirmButton = screen.getByRole('button', { name: /^delete$/i });
    await user.click(confirmButton);

    await waitFor(() => {
      expect(mockDeleteSimulation).toHaveBeenCalledWith(1);
    });

    expect(mockNavigate).toHaveBeenCalledWith('/arena');
  });

  it('should show error state when loading fails', async () => {
    mockGetSimulation.mockRejectedValue(new Error('API Error'));

    renderWithRouter();

    await waitFor(() => {
      expect(screen.getByText(/failed to load simulation/i)).toBeInTheDocument();
    });

    expect(screen.getByRole('button', { name: /back to arena/i })).toBeInTheDocument();
  });

  it('should show simulation complete message for completed simulations', async () => {
    renderWithRouter();

    await waitFor(() => {
      expect(screen.getByText('Simulation Complete')).toBeInTheDocument();
    });
  });

  it('should show cancelled message for cancelled simulations', async () => {
    const cancelledSimDetail: SimulationDetail = {
      ...mockSimulationDetail,
      simulation: {
        ...mockSimulation,
        status: 'cancelled',
      },
    };
    mockGetSimulation.mockResolvedValue(cancelledSimDetail);

    renderWithRouter();

    await waitFor(() => {
      expect(screen.getByText('Simulation was cancelled')).toBeInTheDocument();
    });
  });

  it('should show failed message for failed simulations', async () => {
    const failedSimDetail: SimulationDetail = {
      ...mockSimulationDetail,
      simulation: {
        ...mockSimulation,
        status: 'failed',
      },
    };
    mockGetSimulation.mockResolvedValue(failedSimDetail);

    renderWithRouter();

    await waitFor(() => {
      expect(screen.getByText('Simulation failed')).toBeInTheDocument();
    });
  });

  it('should use default name when simulation has no name', async () => {
    const noNameSimDetail: SimulationDetail = {
      ...mockSimulationDetail,
      simulation: {
        ...mockSimulation,
        name: null,
      },
    };
    mockGetSimulation.mockResolvedValue(noNameSimDetail);

    renderWithRouter();

    await waitFor(() => {
      expect(screen.getByText('Simulation #1')).toBeInTheDocument();
    });
  });
});

describe('ArenaSimulationDetail replay', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockGetSimulation.mockResolvedValue(mockSimulationDetail);
    mockCancelSimulation.mockResolvedValue(undefined);
    mockDeleteSimulation.mockResolvedValue(undefined);
  });

  it('should navigate to Arena with replay state when replay button is clicked', async () => {
    const user = userEvent.setup();

    // Setup - simulation must be loaded
    renderWithRouter();

    // Wait for simulation to load
    await waitFor(() => {
      expect(screen.getByText('Test Simulation')).toBeInTheDocument();
    });

    // Find and click replay button
    const replayButton = screen.getByRole('button', { name: /replay simulation/i });
    await user.click(replayButton);

    // Verify navigation with state
    expect(mockNavigate).toHaveBeenCalledWith('/arena', {
      state: { replaySimulation: mockSimulation },
    });
  });
});
