import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { Arena } from './Arena';
import type { Simulation } from '../types/arena';

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
const mockListSimulations = vi.fn();
const mockCreateSimulation = vi.fn();
vi.mock('../services/arenaService', () => ({
  listSimulations: (...args: unknown[]) => mockListSimulations(...args),
  createSimulation: (...args: unknown[]) => mockCreateSimulation(...args),
}));

// Mock sonner toast
vi.mock('sonner', () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}));

const mockSimulations: Simulation[] = [
  {
    id: 1,
    name: 'Test Simulation',
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
    status: 'completed',
    current_day: 22,
    total_days: 22,
    final_equity: '10500',
    total_return_pct: '5.00',
    total_trades: 5,
    winning_trades: 3,
    max_drawdown_pct: '2.50',
    created_at: '2024-01-01T10:00:00Z',
  },
];

const mockRunningSimulation: Simulation = {
  id: 2,
  name: 'Running Sim',
  stock_list_id: null,
  stock_list_name: null,
  symbols: ['NVDA'],
  start_date: '2024-02-01',
  end_date: '2024-02-29',
  initial_capital: '10000',
  position_size: '1000',
  agent_type: 'live20',
  trailing_stop_pct: '5.0',
  min_buy_score: 60,
  status: 'running',
  current_day: 10,
  total_days: 20,
  final_equity: null,
  total_return_pct: null,
  total_trades: 2,
  winning_trades: 1,
  max_drawdown_pct: null,
  created_at: '2024-02-01T10:00:00Z',
};

describe('Arena', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockListSimulations.mockResolvedValue({
      items: mockSimulations,
      total: mockSimulations.length,
      limit: 20,
      offset: 0,
    });
  });

  it('should render header', async () => {
    render(
      <MemoryRouter>
        <Arena />
      </MemoryRouter>
    );

    expect(screen.getByText('Arena')).toBeInTheDocument();
    expect(screen.getByText('Trading Agent Simulator')).toBeInTheDocument();
  });

  it('should render tabs', async () => {
    render(
      <MemoryRouter>
        <Arena />
      </MemoryRouter>
    );

    expect(screen.getByRole('tab', { name: /new simulation/i })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: /history/i })).toBeInTheDocument();
  });

  it('should show setup form by default', async () => {
    render(
      <MemoryRouter>
        <Arena />
      </MemoryRouter>
    );

    // Setup form is in New Simulation tab (default)
    expect(screen.getByRole('textbox', { name: /symbols/i })).toBeInTheDocument();
  });

  it('should switch to history tab and show simulations', async () => {
    const user = userEvent.setup();

    render(
      <MemoryRouter>
        <Arena />
      </MemoryRouter>
    );

    // Wait for simulations to load (mock resolves immediately)
    await waitFor(() => {
      expect(mockListSimulations).toHaveBeenCalled();
    });

    // Click history tab using userEvent for proper event handling
    const historyTab = screen.getByRole('tab', { name: /history/i });
    await user.click(historyTab);

    // Wait for the tab content to render and loading to complete
    // The simulation name should appear once loading is done
    await waitFor(() => {
      expect(screen.getByText('Test Simulation')).toBeInTheDocument();
    }, { timeout: 2000 });
  });

  it('should show active simulation banner when there is a running simulation', async () => {
    mockListSimulations.mockResolvedValue({
      items: [mockRunningSimulation, ...mockSimulations],
      total: mockSimulations.length + 1,
      limit: 20,
      offset: 0,
    });

    render(
      <MemoryRouter>
        <Arena />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText(/Simulation #2 is running/)).toBeInTheDocument();
    });

    expect(screen.getByRole('button', { name: /view progress/i })).toBeInTheDocument();
  });

  it('should navigate to detail page when View Progress is clicked', async () => {
    mockListSimulations.mockResolvedValue({
      items: [mockRunningSimulation],
      total: 1,
      limit: 20,
      offset: 0,
    });

    render(
      <MemoryRouter>
        <Arena />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText(/Simulation #2/)).toBeInTheDocument();
    });

    const viewProgressButton = screen.getByRole('button', { name: /view progress/i });
    fireEvent.click(viewProgressButton);

    expect(mockNavigate).toHaveBeenCalledWith('/arena/2');
  });

  it('should create simulation and navigate to detail', async () => {
    const newSimulation: Simulation = {
      id: 3,
      name: null,
      stock_list_id: null,
      stock_list_name: null,
      symbols: ['AAPL', 'NVDA'],
      start_date: '2024-03-01',
      end_date: '2024-03-15',
      initial_capital: '10000',
      position_size: '1000',
      agent_type: 'live20',
      trailing_stop_pct: '5.0',
      min_buy_score: 60,
      status: 'pending',
      current_day: 0,
      total_days: 10,
      final_equity: null,
      total_return_pct: null,
      total_trades: 0,
      winning_trades: 0,
      max_drawdown_pct: null,
      created_at: '2024-03-01T10:00:00Z',
    };

    mockCreateSimulation.mockResolvedValue(newSimulation);

    render(
      <MemoryRouter>
        <Arena />
      </MemoryRouter>
    );

    // Fill in form
    const textarea = screen.getByRole('textbox', { name: /symbols/i });
    fireEvent.change(textarea, { target: { value: 'AAPL, NVDA' } });

    const startDateInput = screen.getByLabelText(/start date/i);
    const endDateInput = screen.getByLabelText(/end date/i);
    fireEvent.change(startDateInput, { target: { value: '2024-03-01' } });
    fireEvent.change(endDateInput, { target: { value: '2024-03-15' } });

    // Submit
    const submitButton = screen.getByRole('button', { name: /start simulation/i });
    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(mockCreateSimulation).toHaveBeenCalledWith(
        expect.objectContaining({
          symbols: ['AAPL', 'NVDA'],
          start_date: '2024-03-01',
          end_date: '2024-03-15',
        })
      );
    });

    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledWith('/arena/3');
    });
  });

  it('should handle create simulation error', async () => {
    mockCreateSimulation.mockRejectedValue(new Error('API Error'));

    const { toast } = await import('sonner');

    render(
      <MemoryRouter>
        <Arena />
      </MemoryRouter>
    );

    // Fill in form
    const textarea = screen.getByRole('textbox', { name: /symbols/i });
    fireEvent.change(textarea, { target: { value: 'AAPL' } });

    const startDateInput = screen.getByLabelText(/start date/i);
    const endDateInput = screen.getByLabelText(/end date/i);
    fireEvent.change(startDateInput, { target: { value: '2024-03-01' } });
    fireEvent.change(endDateInput, { target: { value: '2024-03-15' } });

    // Submit
    const submitButton = screen.getByRole('button', { name: /start simulation/i });
    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith('Failed to create simulation');
    });
  });

  it('should refresh simulation list when refresh is clicked', async () => {
    const user = userEvent.setup();

    render(
      <MemoryRouter>
        <Arena />
      </MemoryRouter>
    );

    // Wait for initial load and simulations to appear
    await waitFor(() => {
      expect(mockListSimulations).toHaveBeenCalled();
    });

    const initialCallCount = mockListSimulations.mock.calls.length;

    // Switch to history tab using userEvent for proper event handling
    const historyTab = screen.getByRole('tab', { name: /history/i });
    await user.click(historyTab);

    // Wait for simulation list to be visible (loading complete)
    await waitFor(() => {
      expect(screen.getByText('Test Simulation')).toBeInTheDocument();
    }, { timeout: 2000 });

    // Click refresh
    const refreshButton = screen.getByRole('button', { name: /refresh/i });
    await user.click(refreshButton);

    await waitFor(() => {
      expect(mockListSimulations.mock.calls.length).toBeGreaterThan(initialCallCount);
    });
  });
});
