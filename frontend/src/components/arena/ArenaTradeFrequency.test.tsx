import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ArenaTradeFrequency } from './ArenaTradeFrequency';
import type { Position } from '../../types/arena';

// ---------------------------------------------------------------------------
// Mock lightweight-charts — same pattern as ArenaEquityChart.test.tsx
// ---------------------------------------------------------------------------

const mockSetData = vi.fn();
const mockApplyOptions = vi.fn();
const mockFitContent = vi.fn();
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
      removeSeries: vi.fn(),
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
    HistogramSeries: 'Histogram',
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
  // Reset createChart implementation for each test
  const { createChart } = await import('lightweight-charts');
  (createChart as ReturnType<typeof vi.fn>).mockImplementation(() => ({
    addSeries: mockAddSeries.mockImplementation(() => ({
      setData: mockSetData,
      applyOptions: mockApplyOptions,
    })),
    removeSeries: vi.fn(),
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
// Helpers
// ---------------------------------------------------------------------------

let positionIdCounter = 0;

const makePosition = (entryDate: string | null, overrides: Partial<Position> = {}): Position => ({
  id: ++positionIdCounter,
  symbol: 'AAPL',
  status: 'closed',
  signal_date: '2024-01-01',
  entry_date: entryDate,
  entry_price: '150.00',
  shares: 10,
  highest_price: null,
  current_stop: null,
  exit_date: null,
  exit_price: null,
  exit_reason: null,
  realized_pnl: null,
  return_pct: null,
  agent_reasoning: null,
  agent_score: null,
  sector: null,
  ...overrides,
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('ArenaTradeFrequency', () => {
  describe('no positions', () => {
    it('renders nothing when positions is empty', () => {
      const { container } = render(<ArenaTradeFrequency positions={[]} />);
      expect(container.firstChild).toBeNull();
    });
  });

  describe('with positions', () => {
    it('renders the chart container when at least one position exists', () => {
      const positions = [makePosition('2024-03-15')];
      render(<ArenaTradeFrequency positions={positions} />);
      expect(screen.getByTestId('arena-trade-frequency-chart')).toBeInTheDocument();
    });

    it('calls createChart when the component mounts', async () => {
      const { createChart } = await import('lightweight-charts');

      const positions = [makePosition('2024-03-15'), makePosition('2024-04-02')];
      render(<ArenaTradeFrequency positions={positions} />);

      expect(createChart).toHaveBeenCalledTimes(1);
    });

    it('calls addSeries with HistogramSeries constructor', async () => {
      const { HistogramSeries } = await import('lightweight-charts');

      const positions = [makePosition('2024-03-15')];
      render(<ArenaTradeFrequency positions={positions} />);

      expect(mockAddSeries).toHaveBeenCalledWith(
        HistogramSeries,
        expect.any(Object),
      );
    });

    it('calls setData with the correct monthly buckets', () => {
      // 3 positions all in March 2024 → one bucket with value 3
      const positions = [
        makePosition('2024-03-01'),
        makePosition('2024-03-15'),
        makePosition('2024-03-28'),
      ];
      render(<ArenaTradeFrequency positions={positions} />);

      expect(mockSetData).toHaveBeenCalledWith(
        expect.arrayContaining([
          expect.objectContaining({ value: 3 }),
        ]),
      );
    });
  });

  describe('monthly grouping', () => {
    it('groups 3 positions in 2024-03 into one bucket with value 3', () => {
      const positions = [
        makePosition('2024-03-01'),
        makePosition('2024-03-10'),
        makePosition('2024-03-25'),
      ];
      render(<ArenaTradeFrequency positions={positions} />);

      const calls = mockSetData.mock.calls;
      // setData is called once (from the positions useEffect)
      const dataArg: Array<{ time: number; value: number }> = calls[calls.length - 1][0];

      expect(dataArg).toHaveLength(1);
      expect(dataArg[0].value).toBe(3);
    });

    it('produces separate buckets for positions in different months', () => {
      const positions = [
        makePosition('2024-02-10'),
        makePosition('2024-02-20'),
        makePosition('2024-03-05'),
      ];
      render(<ArenaTradeFrequency positions={positions} />);

      const calls = mockSetData.mock.calls;
      const dataArg: Array<{ time: number; value: number }> = calls[calls.length - 1][0];

      expect(dataArg).toHaveLength(2);

      // Buckets are sorted chronologically → Feb first, then Mar
      expect(dataArg[0].value).toBe(2); // Feb: 2 positions
      expect(dataArg[1].value).toBe(1); // Mar: 1 position
    });

    it('skips positions with null entry_date', () => {
      const positions = [
        makePosition(null),          // should be excluded
        makePosition('2024-03-15'),  // included
        makePosition('2024-03-20'),  // included
      ];
      render(<ArenaTradeFrequency positions={positions} />);

      const calls = mockSetData.mock.calls;
      const dataArg: Array<{ time: number; value: number }> = calls[calls.length - 1][0];

      // Only the March bucket should appear with count 2
      expect(dataArg).toHaveLength(1);
      expect(dataArg[0].value).toBe(2);
    });

    it('uses the first calendar day of the month as the bucket timestamp', () => {
      // 2024-03-01 00:00:00 UTC in seconds
      const expectedTimestamp = new Date('2024-03-01').getTime() / 1000;

      const positions = [makePosition('2024-03-15')];
      render(<ArenaTradeFrequency positions={positions} />);

      const calls = mockSetData.mock.calls;
      const dataArg: Array<{ time: number; value: number }> = calls[calls.length - 1][0];

      expect(dataArg[0].time).toBe(expectedTimestamp);
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
        <ArenaTradeFrequency positions={[makePosition('2024-03-15')]} />,
      );
      unmount();

      expect(localRemove).toHaveBeenCalledTimes(1);
    });
  });
});
