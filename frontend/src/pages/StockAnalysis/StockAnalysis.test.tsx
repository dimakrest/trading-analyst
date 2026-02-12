import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { StockAnalysis } from './StockAnalysis';
import * as useStockDataHook from '../../hooks/useStockData';
import * as useStockSearchHook from '../../hooks/useStockSearch';
import * as useStockListsHook from '../../hooks/useStockLists';
import * as useStockInfoHook from '../../hooks/useStockInfo';
import type { StockData } from '../../types/stock';

vi.mock('../../hooks/useStockData');
vi.mock('../../hooks/useStockSearch');
vi.mock('../../hooks/useStockLists');
vi.mock('../../hooks/useStockInfo');

// Mock lightweight-charts
vi.mock('lightweight-charts', () => ({
  createChart: vi.fn().mockReturnValue({
    addSeries: vi.fn().mockReturnValue({
      setData: vi.fn(),
      update: vi.fn(),
      applyOptions: vi.fn(),
      createPriceLine: vi.fn(),
    }),
    removeSeries: vi.fn(),
    timeScale: vi.fn().mockReturnValue({
      fitContent: vi.fn(),
      scrollToPosition: vi.fn(),
      setVisibleRange: vi.fn(),
      subscribeVisibleLogicalRangeChange: vi.fn(),
      coordinateToTime: vi.fn(),
    }),
    priceScale: vi.fn().mockReturnValue({
      applyOptions: vi.fn(),
    }),
    applyOptions: vi.fn(),
    resize: vi.fn(),
    panes: vi.fn(() => [
      { setHeight: vi.fn() },
      { setHeight: vi.fn() },
      { setHeight: vi.fn() },
    ]),
    remove: vi.fn(),
  }),
  createSeriesMarkers: vi.fn().mockReturnValue({
    setMarkers: vi.fn(),
    markers: vi.fn().mockReturnValue([]),
  }),
  ColorType: {
    Solid: 0,
    VerticalGradient: 1,
  },
  CandlestickSeries: 'candlestick',
  LineSeries: 'Line',
  HistogramSeries: 'Histogram',
}));

describe('StockAnalysis', () => {
  const mockStockData: StockData = {
    symbol: 'AAPL',
    company_name: 'Apple Inc.',
    current_price: 150.0,
    price_change: 15.23,
    price_change_percent: 10.25,
    prices: [
      {
        date: '2024-01-01',
        open: 140,
        high: 145,
        low: 138,
        close: 142,
        volume: 1000000,
      },
      {
        date: '2024-02-01',
        open: 142,
        high: 148,
        low: 141,
        close: 146,
        volume: 1100000,
      },
    ],
  };

  // Helper function to render with router context
  const renderWithRouter = (initialState?: Record<string, unknown>) => {
    return render(
      <MemoryRouter initialEntries={[{ pathname: '/stock/AAPL', state: initialState }]}>
        <StockAnalysis />
      </MemoryRouter>
    );
  };

  beforeEach(() => {
    vi.clearAllMocks();

    // Default mock implementations
    vi.spyOn(useStockSearchHook, 'useStockSearch').mockReturnValue({
      symbol: 'AAPL',
      setSymbol: vi.fn(),
      handleSearch: vi.fn(),
    });

    vi.spyOn(useStockDataHook, 'useStockData').mockReturnValue({
      data: mockStockData,
      loading: false,
      error: null,
      refetch: vi.fn(),
    });

    vi.spyOn(useStockListsHook, 'useStockLists').mockReturnValue({
      lists: [],
      isLoading: false,
      error: null,
      createList: vi.fn(),
      updateList: vi.fn(),
      deleteList: vi.fn(),
      refetch: vi.fn(),
    });

    vi.spyOn(useStockInfoHook, 'useStockInfo').mockReturnValue({
      stockInfo: {
        symbol: 'AAPL',
        name: 'Apple Inc.',
        sector: 'Technology',
        sector_etf: 'XLK',
        industry: 'Consumer Electronics',
        exchange: 'NASDAQ',
      },
      isLoading: false,
      error: null,
      refetch: vi.fn(),
    });
  });

  it('should render search bar', () => {
    // Act
    renderWithRouter();

    // Assert
    expect(screen.getByLabelText('Stock symbol search')).toBeInTheDocument();
  });

  it('should render stock hero when data is available', () => {
    // Act
    renderWithRouter();

    // Assert - StockHero shows symbol and price
    expect(screen.getByTestId('stock-hero-symbol')).toHaveTextContent('AAPL');
    expect(screen.getByTestId('stock-hero')).toBeInTheDocument();
  });

  it('should render stock chart when data is available', () => {
    // Act
    renderWithRouter();

    // Assert - New CandlestickChart uses canvas, not SVG
    expect(screen.getByRole('img', { name: 'Candlestick chart for AAPL' })).toBeInTheDocument();
  });

  it('should render loading state', () => {
    // Arrange
    vi.spyOn(useStockDataHook, 'useStockData').mockReturnValue({
      data: null,
      loading: true,
      error: null,
      refetch: vi.fn(),
    });

    // Act
    renderWithRouter();

    // Assert - StockHero shows loading skeleton
    expect(screen.getByTestId('stock-hero-loading')).toBeInTheDocument();
  });

  it('should render error state', () => {
    // Arrange
    vi.spyOn(useStockDataHook, 'useStockData').mockReturnValue({
      data: null,
      loading: false,
      error: 'Failed to fetch data',
      refetch: vi.fn(),
    });

    // Act
    renderWithRouter();

    // Assert
    expect(screen.getByText('Error: Failed to fetch data')).toBeInTheDocument();
  });

  it('should not render chart when loading', () => {
    // Arrange
    vi.spyOn(useStockDataHook, 'useStockData').mockReturnValue({
      data: null,
      loading: true,
      error: null,
      refetch: vi.fn(),
    });

    // Act
    renderWithRouter();

    // Assert - Chart should not be visible when loading
    expect(screen.queryByRole('img', { name: /Candlestick chart/ })).not.toBeInTheDocument();
  });

  it('should not render chart when error occurs', () => {
    // Arrange
    vi.spyOn(useStockDataHook, 'useStockData').mockReturnValue({
      data: null,
      loading: false,
      error: 'Error',
      refetch: vi.fn(),
    });

    // Act
    renderWithRouter();

    // Assert - Chart should not be visible when error occurs
    expect(screen.queryByRole('img', { name: /Candlestick chart/ })).not.toBeInTheDocument();
    expect(screen.queryByTestId('stock-hero')).not.toBeInTheDocument();
  });

  it('should render search functionality', async () => {
    // Arrange
    const mockHandleSearch = vi.fn();
    const mockSetSymbol = vi.fn();
    vi.spyOn(useStockSearchHook, 'useStockSearch').mockReturnValue({
      symbol: 'AAPL',
      setSymbol: mockSetSymbol,
      handleSearch: mockHandleSearch,
    });

    const user = userEvent.setup();

    // Act
    renderWithRouter();
    const input = screen.getByLabelText('Stock symbol search');

    // Clear existing value and type new one
    await user.clear(input);
    await user.type(input, 'TSLA');

    // Assert - Verify the input can be typed into
    expect(input).toHaveValue('TSLA');
  });

  describe('WatchlistPanel integration', () => {
    it('should call handleSearch when clicking a symbol in the mobile watchlist', async () => {
      // Arrange
      const mockHandleSearch = vi.fn();
      vi.spyOn(useStockSearchHook, 'useStockSearch').mockReturnValue({
        symbol: 'AAPL',
        setSymbol: vi.fn(),
        handleSearch: mockHandleSearch,
      });

      vi.spyOn(useStockListsHook, 'useStockLists').mockReturnValue({
        lists: [
          { id: 1, name: 'Tech Stocks', symbols: ['AAPL', 'MSFT', 'GOOGL'], symbol_count: 3 },
          { id: 2, name: 'Healthcare', symbols: ['JNJ', 'PFE'], symbol_count: 2 },
        ],
        isLoading: false,
        error: null,
        createList: vi.fn(),
        updateList: vi.fn(),
        deleteList: vi.fn(),
        refetch: vi.fn(),
      });

      const user = userEvent.setup();

      // Act
      renderWithRouter();

      // Open mobile watchlist sheet
      const mobileWatchlistTrigger = screen.getByTestId('mobile-watchlist-trigger');
      await user.click(mobileWatchlistTrigger);

      // Select a list first (Tech Stocks)
      const listSelector = await screen.findByRole('combobox');
      await user.click(listSelector);
      const techStocksOption = await screen.findByRole('option', { name: 'Tech Stocks' });
      await user.click(techStocksOption);

      // Now click on MSFT in the watchlist
      const msftButton = await screen.findByRole('button', { name: 'Select MSFT' });
      await user.click(msftButton);

      // Assert - handleSearch should be called with MSFT
      expect(mockHandleSearch).toHaveBeenCalledWith('MSFT');
    });

    it('should auto-select first symbol when selecting a list', async () => {
      // Arrange
      const mockHandleSearch = vi.fn();
      vi.spyOn(useStockSearchHook, 'useStockSearch').mockReturnValue({
        symbol: 'AAPL',
        setSymbol: vi.fn(),
        handleSearch: mockHandleSearch,
      });

      vi.spyOn(useStockListsHook, 'useStockLists').mockReturnValue({
        lists: [
          { id: 1, name: 'Tech Stocks', symbols: ['NVDA', 'AMD', 'INTC'], symbol_count: 3 },
        ],
        isLoading: false,
        error: null,
        createList: vi.fn(),
        updateList: vi.fn(),
        deleteList: vi.fn(),
        refetch: vi.fn(),
      });

      const user = userEvent.setup();

      // Act
      renderWithRouter();

      // Open mobile watchlist sheet
      const mobileWatchlistTrigger = screen.getByTestId('mobile-watchlist-trigger');
      await user.click(mobileWatchlistTrigger);

      // Select Tech Stocks list
      const listSelector = await screen.findByRole('combobox');
      await user.click(listSelector);
      const techStocksOption = await screen.findByRole('option', { name: 'Tech Stocks' });
      await user.click(techStocksOption);

      // Assert - handleSearch should be called with first symbol (NVDA)
      expect(mockHandleSearch).toHaveBeenCalledWith('NVDA');
    });
  });

});
