import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { CandlestickChart } from './CandlestickChart';

// Mock lightweight-charts
// Create panes dynamically to support any number of indicator panes
const createMockPane = () => ({ setHeight: vi.fn() });
const mockPanes: ReturnType<typeof createMockPane>[] = [];
const getMockPanes = () => mockPanes;

vi.mock('lightweight-charts', () => ({
  createChart: vi.fn(() => ({
    addSeries: vi.fn((_seriesType, _options, paneIndex?: number) => {
      // Ensure panes array has enough elements for the requested pane index
      if (paneIndex !== undefined) {
        while (mockPanes.length <= paneIndex) {
          mockPanes.push(createMockPane());
        }
      }
      return {
        setData: vi.fn(),
        applyOptions: vi.fn(),
        createPriceLine: vi.fn(() => ({ id: 'mock-price-line' })),
        removePriceLine: vi.fn(),
        priceScale: vi.fn(() => ({
          applyOptions: vi.fn(),
        })),
        setMarkers: vi.fn(),
      };
    }),
    removeSeries: vi.fn(),
    applyOptions: vi.fn(),
    timeScale: vi.fn(() => ({
      subscribeVisibleLogicalRangeChange: vi.fn(),
      setVisibleRange: vi.fn(),
      fitContent: vi.fn(),
      coordinateToTime: vi.fn(),
    })),
    priceScale: vi.fn(() => ({
      applyOptions: vi.fn(),
    })),
    panes: vi.fn(() => getMockPanes()),
    remove: vi.fn(),
  })),
  createSeriesMarkers: vi.fn(() => ({
    setMarkers: vi.fn(),
    markers: vi.fn().mockReturnValue([]),
    detach: vi.fn(),
  })),
  ColorType: {
    Solid: 0,
    VerticalGradient: 1,
  },
  CandlestickSeries: 'Candlestick',
  LineSeries: 'Line',
  HistogramSeries: 'Histogram',
}));

// Reset dynamic panes array before each test
beforeEach(() => {
  mockPanes.length = 0;
});

describe('CandlestickChart - MA 20 Controls', () => {
  const mockData = [
    {
      date: '2024-01-20',
      open: 150,
      high: 155,
      low: 148,
      close: 152,
      volume: 1000000,
      ma_20: 151.5,
    },
    {
      date: '2024-01-21',
      open: 152,
      high: 156,
      low: 150,
      close: 154,
      volume: 1100000,
      ma_20: 152.0,
    },
  ];

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('should render MA 20 toggle button', () => {
    // Arrange & Act
    render(<CandlestickChart data={mockData} symbol="AAPL" />);

    // Assert
    const toggleButton = screen.getByRole('button', { name: /MA 20 indicator/i });
    expect(toggleButton).toBeInTheDocument();
    expect(toggleButton).toHaveAttribute('aria-pressed', 'true'); // Default: visible
  });

  it('should toggle MA 20 visibility when button clicked', async () => {
    // Arrange
    const user = userEvent.setup();
    render(<CandlestickChart data={mockData} symbol="AAPL" />);
    const toggleButton = screen.getByRole('button', { name: /hide MA 20/i });

    // Act
    await user.click(toggleButton);

    // Assert
    expect(toggleButton).toHaveAttribute('aria-pressed', 'false');
    expect(screen.getByRole('button', { name: /show MA 20/i })).toBeInTheDocument();
  });

  it('should render chart legend', () => {
    // Arrange & Act
    render(<CandlestickChart data={mockData} symbol="AAPL" />);

    // Assert
    expect(screen.getByText(/bullish/i)).toBeInTheDocument();
    expect(screen.getByText(/bearish/i)).toBeInTheDocument();
    // MA 20 appears twice: in legend and toggle button
    expect(screen.getAllByText(/MA 20/i).length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText(/wicks/i)).toBeInTheDocument();
  });
});

describe('CandlestickChart - Volume Controls', () => {
  const mockData = [
    {
      date: '2024-01-20',
      open: 150,
      high: 155,
      low: 148,
      close: 152,
      volume: 1000000,
      ma_20: 151.5,
    },
    {
      date: '2024-01-21',
      open: 152,
      high: 156,
      low: 150,
      close: 154,
      volume: 1100000,
      ma_20: 152.0,
    },
  ];

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('should render volume toggle button', () => {
    // Arrange & Act
    render(<CandlestickChart data={mockData} symbol="AAPL" />);

    // Assert
    const volumeButton = screen.getByRole('button', { name: /volume/i });
    expect(volumeButton).toBeInTheDocument();
  });

  it('should have volume toggle enabled by default', () => {
    // Arrange & Act
    render(<CandlestickChart data={mockData} symbol="AAPL" />);

    // Assert
    const volumeButton = screen.getByRole('button', { name: /volume/i });
    expect(volumeButton).toHaveAttribute('aria-pressed', 'true');
  });

  it('should toggle volume visibility when button clicked', async () => {
    // Arrange
    const user = userEvent.setup();
    render(<CandlestickChart data={mockData} symbol="AAPL" />);

    // Act
    const volumeButton = screen.getByRole('button', { name: /volume/i });
    expect(volumeButton).toHaveAttribute('aria-pressed', 'true');

    await user.click(volumeButton);

    // Assert
    expect(volumeButton).toHaveAttribute('aria-pressed', 'false');
  });
});

describe('CandlestickChart - Price Lines and Markers', () => {
  const mockData = [
    {
      date: '2024-01-20',
      open: 150,
      high: 155,
      low: 148,
      close: 152,
      volume: 1000000,
      ma_20: 151.5,
    },
    {
      date: '2024-01-21',
      open: 152,
      high: 156,
      low: 150,
      close: 154,
      volume: 1100000,
      ma_20: 152.0,
    },
  ];

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('should render correctly with priceLines prop', () => {
    // Arrange
    const priceLines = [
      {
        price: 150,
        color: '#f59e0b',
        lineStyle: 'dashed' as const,
        label: 'Trigger',
        labelVisible: true,
      },
      {
        price: 145,
        color: '#ef4444',
        lineStyle: 'dashed' as const,
        label: 'Stop Loss',
        labelVisible: true,
      },
    ];

    // Act & Assert - Should render without errors
    render(<CandlestickChart data={mockData} symbol="AAPL" priceLines={priceLines} />);
    expect(screen.getByTestId('candlestick-chart')).toBeInTheDocument();
  });

  it('should render correctly with markers prop', () => {
    // Arrange
    const markers = [
      {
        date: '2024-01-20',
        position: 'belowBar' as const,
        shape: 'arrowUp' as const,
        color: '#22c55e',
        text: 'Entry',
      },
      {
        date: '2024-01-21',
        position: 'aboveBar' as const,
        shape: 'arrowDown' as const,
        color: '#ef4444',
        text: 'Exit',
      },
    ];

    // Act & Assert - Should render without errors
    render(<CandlestickChart data={mockData} symbol="AAPL" markers={markers} />);
    expect(screen.getByTestId('candlestick-chart')).toBeInTheDocument();
  });

  it('should render with both priceLines and markers', () => {
    // Arrange
    const priceLines = [
      {
        price: 150,
        color: '#f59e0b',
        lineStyle: 'dashed' as const,
        label: 'Trigger',
        labelVisible: true,
      },
    ];
    const markers = [
      {
        date: '2024-01-20',
        position: 'belowBar' as const,
        shape: 'arrowUp' as const,
        color: '#22c55e',
        text: 'Entry',
      },
    ];

    // Act & Assert - Should render without errors
    render(
      <CandlestickChart data={mockData} symbol="AAPL" priceLines={priceLines} markers={markers} />
    );
    expect(screen.getByTestId('candlestick-chart')).toBeInTheDocument();
  });

  it('should maintain backwards compatibility (works without new props)', () => {
    // Arrange & Act
    render(<CandlestickChart data={mockData} symbol="AAPL" />);

    // Assert - Should render without errors
    expect(screen.getByTestId('candlestick-chart')).toBeInTheDocument();
  });

  it('should handle empty priceLines array without errors', () => {
    // Arrange & Act
    render(<CandlestickChart data={mockData} symbol="AAPL" priceLines={[]} />);

    // Assert - Should render without errors
    expect(screen.getByTestId('candlestick-chart')).toBeInTheDocument();
  });

  it('should handle empty markers array without errors', () => {
    // Arrange & Act
    render(<CandlestickChart data={mockData} symbol="AAPL" markers={[]} />);

    // Assert - Should render without errors
    expect(screen.getByTestId('candlestick-chart')).toBeInTheDocument();
  });

  it('should handle undefined priceLines prop', () => {
    // Arrange & Act
    render(<CandlestickChart data={mockData} symbol="AAPL" priceLines={undefined} />);

    // Assert - Should render without errors
    expect(screen.getByTestId('candlestick-chart')).toBeInTheDocument();
  });

  it('should handle undefined markers prop', () => {
    // Arrange & Act
    render(<CandlestickChart data={mockData} symbol="AAPL" markers={undefined} />);

    // Assert - Should render without errors
    expect(screen.getByTestId('candlestick-chart')).toBeInTheDocument();
  });

  it('should handle prop updates correctly', () => {
    // Arrange - Initial render with priceLines
    const initialPriceLines = [
      {
        price: 150,
        color: '#f59e0b',
        lineStyle: 'dashed' as const,
        label: 'Trigger',
        labelVisible: true,
      },
    ];
    const { rerender } = render(
      <CandlestickChart data={mockData} symbol="AAPL" priceLines={initialPriceLines} />
    );
    expect(screen.getByTestId('candlestick-chart')).toBeInTheDocument();

    // Act - Update with different priceLines
    const updatedPriceLines = [
      {
        price: 155,
        color: '#3b82f6',
        lineStyle: 'solid' as const,
        label: 'Target',
        labelVisible: true,
      },
    ];
    rerender(<CandlestickChart data={mockData} symbol="AAPL" priceLines={updatedPriceLines} />);

    // Assert - Should still render without errors
    expect(screen.getByTestId('candlestick-chart')).toBeInTheDocument();
  });
});
