import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import { ArenaEquityChart } from './ArenaEquityChart';
import type { Snapshot } from '../../types/arena';

// ---------------------------------------------------------------------------
// Mock lightweight-charts — same pattern as CandlestickChart.test.tsx
// ---------------------------------------------------------------------------

const mockSetData = vi.fn();
const mockApplyOptions = vi.fn();
const mockFitContent = vi.fn();
const mockRemoveSeries = vi.fn();
const mockRemove = vi.fn();
const mockAddSeries = vi.fn();

vi.mock('lightweight-charts', () => {
  const mockAddSeriesImpl = vi.fn(() => ({
    setData: mockSetData,
    applyOptions: mockApplyOptions,
  }));

  return {
    createChart: vi.fn(() => ({
      addSeries: mockAddSeriesImpl,
      removeSeries: mockRemoveSeries,
      applyOptions: mockApplyOptions,
      timeScale: vi.fn(() => ({
        fitContent: mockFitContent,
        setVisibleRange: vi.fn(),
        subscribeVisibleLogicalRangeChange: vi.fn(),
      })),
      panes: vi.fn(() => []),
      remove: mockRemove,
    })),
    ColorType: {
      Solid: 0,
      VerticalGradient: 1,
    },
    LineSeries: 'Line',
    LineStyle: {
      Solid: 0,
      Dotted: 1,
      Dashed: 2,
      LargeDashed: 3,
      SparseDotted: 4,
    },
  };
});

// Expose the addSeries mock so individual tests can inspect calls
beforeEach(async () => {
  vi.clearAllMocks();
  // Reset the addSeries mock on the shared chart mock
  const { createChart } = await import('lightweight-charts');
  (createChart as ReturnType<typeof vi.fn>).mockImplementation(() => ({
    addSeries: mockAddSeries.mockImplementation(() => ({
      setData: mockSetData,
      applyOptions: mockApplyOptions,
    })),
    removeSeries: mockRemoveSeries,
    applyOptions: mockApplyOptions,
    timeScale: vi.fn(() => ({
      fitContent: mockFitContent,
      setVisibleRange: vi.fn(),
      subscribeVisibleLogicalRangeChange: vi.fn(),
    })),
    panes: vi.fn(() => []),
    remove: mockRemove,
  }));
});

// ---------------------------------------------------------------------------
// Mock arenaService.getBenchmarkData
// ---------------------------------------------------------------------------

vi.mock('../../services/arenaService', () => ({
  getBenchmarkData: vi.fn(),
}));

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const makeSnapshot = (date: string, totalEquity: string): Snapshot => ({
  id: 1,
  snapshot_date: date,
  day_number: 1,
  cash: '0',
  positions_value: '0',
  total_equity: totalEquity,
  daily_pnl: '0',
  daily_return_pct: '0',
  cumulative_return_pct: '0',
  open_position_count: 0,
  decisions: {},
});

const makeBenchmarkPoint = (date: string, cumReturn: string) => ({
  date,
  close: '450.00',
  cumulative_return_pct: cumReturn,
});

const twoSnapshots = [
  makeSnapshot('2024-01-01', '10000.00'),
  makeSnapshot('2024-01-02', '10150.00'),
];

const threeSnapshots = [
  makeSnapshot('2024-01-01', '10000.00'),
  makeSnapshot('2024-01-02', '10250.00'),
  makeSnapshot('2024-01-03', '10500.00'),
];

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('ArenaEquityChart', () => {
  describe('when snapshots.length === 0', () => {
    it('renders "Not enough data" placeholder and does not crash', () => {
      render(<ArenaEquityChart snapshots={[]} simulationId={1} />);

      expect(screen.getByText('Not enough data')).toBeInTheDocument();
      expect(screen.queryByTestId('arena-equity-chart')).not.toBeInTheDocument();
    });
  });

  describe('when snapshots.length === 1', () => {
    it('renders "Not enough data" placeholder (single point is invisible)', () => {
      const snapshots = [makeSnapshot('2024-01-01', '10000.00')];
      render(<ArenaEquityChart snapshots={snapshots} simulationId={1} />);

      expect(screen.getByText('Not enough data')).toBeInTheDocument();
      expect(screen.queryByTestId('arena-equity-chart')).not.toBeInTheDocument();
    });
  });

  describe('when snapshots.length >= 2', () => {
    it('renders the chart container div', () => {
      render(<ArenaEquityChart snapshots={twoSnapshots} simulationId={1} />);

      expect(screen.getByTestId('arena-equity-chart')).toBeInTheDocument();
      expect(screen.queryByText('Not enough data')).not.toBeInTheDocument();
    });

    it('calls createChart when the component mounts', async () => {
      const { createChart } = await import('lightweight-charts');

      render(<ArenaEquityChart snapshots={threeSnapshots} simulationId={1} />);

      expect(createChart).toHaveBeenCalledTimes(1);
    });

    it('renders SPY and QQQ benchmark toggle buttons', () => {
      render(<ArenaEquityChart snapshots={twoSnapshots} simulationId={1} />);

      expect(screen.getByTestId('benchmark-toggle-spy')).toBeInTheDocument();
      expect(screen.getByTestId('benchmark-toggle-qqq')).toBeInTheDocument();
    });

    it('does not show the legend when no benchmark is active', () => {
      render(<ArenaEquityChart snapshots={twoSnapshots} simulationId={1} />);

      expect(screen.queryByTestId('benchmark-legend')).not.toBeInTheDocument();
    });
  });

  describe('cleanup on unmount', () => {
    it('calls chart.remove() when the component unmounts', async () => {
      const { createChart } = await import('lightweight-charts');
      const localRemove = vi.fn();

      (createChart as ReturnType<typeof vi.fn>).mockReturnValueOnce({
        addSeries: vi.fn(() => ({ setData: vi.fn(), applyOptions: vi.fn() })),
        removeSeries: vi.fn(),
        applyOptions: vi.fn(),
        timeScale: vi.fn(() => ({
          fitContent: vi.fn(),
          setVisibleRange: vi.fn(),
          subscribeVisibleLogicalRangeChange: vi.fn(),
        })),
        panes: vi.fn(() => []),
        remove: localRemove,
      });

      const { unmount } = render(
        <ArenaEquityChart snapshots={twoSnapshots} simulationId={1} />,
      );
      unmount();

      expect(localRemove).toHaveBeenCalledTimes(1);
    });
  });

  describe('benchmark toggle ON', () => {
    it('calls getBenchmarkData with the correct simulationId and symbol when SPY is toggled', async () => {
      const { getBenchmarkData } = await import('../../services/arenaService');
      (getBenchmarkData as ReturnType<typeof vi.fn>).mockResolvedValue([
        makeBenchmarkPoint('2024-01-01', '0.00'),
        makeBenchmarkPoint('2024-01-02', '1.50'),
      ]);

      render(<ArenaEquityChart snapshots={twoSnapshots} simulationId={42} />);

      fireEvent.click(screen.getByTestId('benchmark-toggle-spy'));

      await waitFor(() => {
        expect(getBenchmarkData).toHaveBeenCalledWith(42, 'SPY');
      });
    });

    it('calls getBenchmarkData with QQQ when QQQ is toggled', async () => {
      const { getBenchmarkData } = await import('../../services/arenaService');
      (getBenchmarkData as ReturnType<typeof vi.fn>).mockResolvedValue([
        makeBenchmarkPoint('2024-01-01', '0.00'),
        makeBenchmarkPoint('2024-01-02', '2.00'),
      ]);

      render(<ArenaEquityChart snapshots={twoSnapshots} simulationId={7} />);

      fireEvent.click(screen.getByTestId('benchmark-toggle-qqq'));

      await waitFor(() => {
        expect(getBenchmarkData).toHaveBeenCalledWith(7, 'QQQ');
      });
    });

    it('shows legend with portfolio and benchmark labels after successful fetch', async () => {
      const { getBenchmarkData } = await import('../../services/arenaService');
      (getBenchmarkData as ReturnType<typeof vi.fn>).mockResolvedValue([
        makeBenchmarkPoint('2024-01-01', '0.00'),
        makeBenchmarkPoint('2024-01-02', '1.50'),
      ]);

      render(<ArenaEquityChart snapshots={twoSnapshots} simulationId={1} />);

      fireEvent.click(screen.getByTestId('benchmark-toggle-spy'));

      const legend = await screen.findByTestId('benchmark-legend');
      expect(legend).toBeInTheDocument();

      // The legend contains "Portfolio" and the benchmark name inside the legend element
      expect(legend).toHaveTextContent('Portfolio');
      expect(legend).toHaveTextContent('SPY');
    });

    it('shows a loading spinner on the active toggle item while fetch is in flight', async () => {
      const { getBenchmarkData } = await import('../../services/arenaService');

      // Delay resolution so we can assert the loading state
      let resolve!: (v: unknown) => void;
      (getBenchmarkData as ReturnType<typeof vi.fn>).mockImplementation(
        () =>
          new Promise((res) => {
            resolve = res;
          }),
      );

      render(<ArenaEquityChart snapshots={twoSnapshots} simulationId={1} />);

      fireEvent.click(screen.getByTestId('benchmark-toggle-spy'));

      // Spinner should appear
      expect(await screen.findByLabelText('Loading SPY benchmark')).toBeInTheDocument();

      // Resolve to finish
      await act(async () => {
        resolve([makeBenchmarkPoint('2024-01-01', '0.00')]);
      });
    });
  });

  describe('benchmark toggle OFF', () => {
    it('restores absolute equity view and hides legend when active benchmark is clicked again', async () => {
      const { getBenchmarkData } = await import('../../services/arenaService');
      (getBenchmarkData as ReturnType<typeof vi.fn>).mockResolvedValue([
        makeBenchmarkPoint('2024-01-01', '0.00'),
        makeBenchmarkPoint('2024-01-02', '1.50'),
      ]);

      render(<ArenaEquityChart snapshots={twoSnapshots} simulationId={1} />);

      // Activate SPY
      fireEvent.click(screen.getByTestId('benchmark-toggle-spy'));
      await waitFor(() =>
        expect(screen.getByTestId('benchmark-legend')).toBeInTheDocument(),
      );

      // Deactivate SPY by clicking again
      fireEvent.click(screen.getByTestId('benchmark-toggle-spy'));

      await waitFor(() =>
        expect(screen.queryByTestId('benchmark-legend')).not.toBeInTheDocument(),
      );
    });
  });

  describe('error state', () => {
    it('applies error class to the toggle item when fetch fails', async () => {
      const { getBenchmarkData } = await import('../../services/arenaService');
      (getBenchmarkData as ReturnType<typeof vi.fn>).mockRejectedValue(
        new Error('Network error'),
      );

      render(<ArenaEquityChart snapshots={twoSnapshots} simulationId={1} />);

      fireEvent.click(screen.getByTestId('benchmark-toggle-spy'));

      await waitFor(() => {
        const toggleItem = screen.getByTestId('benchmark-toggle-spy');
        expect(toggleItem).toHaveClass('text-accent-bearish');
      });
    });

    it('does not show legend after a failed benchmark fetch', async () => {
      const { getBenchmarkData } = await import('../../services/arenaService');
      (getBenchmarkData as ReturnType<typeof vi.fn>).mockRejectedValue(
        new Error('Network error'),
      );

      render(<ArenaEquityChart snapshots={twoSnapshots} simulationId={1} />);

      fireEvent.click(screen.getByTestId('benchmark-toggle-spy'));

      await waitFor(() => {
        expect(screen.queryByTestId('benchmark-legend')).not.toBeInTheDocument();
      });
    });
  });
});
