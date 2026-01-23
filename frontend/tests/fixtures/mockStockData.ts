/**
 * Mock API responses for E2E testing
 * Provides realistic stock data for various test scenarios
 */

export const mockAAPLData = {
  symbol: 'AAPL',
  data: [
    {
      date: '2024-10-01',
      open: 220.0,
      high: 225.0,
      low: 218.0,
      close: 223.0,
      volume: 50000000,
    },
    {
      date: '2024-10-02',
      open: 223.0,
      high: 228.0,
      low: 222.0,
      close: 226.0,
      volume: 52000000,
    },
    {
      date: '2024-10-03',
      open: 226.0,
      high: 230.0,
      low: 225.0,
      close: 227.5,
      volume: 48000000,
    },
    {
      date: '2024-10-04',
      open: 227.5,
      high: 229.0,
      low: 224.0,
      close: 225.0,
      volume: 51000000,
    },
    {
      date: '2024-10-05',
      open: 225.0,
      high: 227.0,
      low: 223.0,
      close: 224.5,
      volume: 49000000,
    },
    {
      date: '2024-10-08',
      open: 224.5,
      high: 228.5,
      low: 223.5,
      close: 227.0,
      volume: 53000000,
    },
    {
      date: '2024-10-09',
      open: 227.0,
      high: 231.0,
      low: 226.0,
      close: 229.5,
      volume: 55000000,
    },
    {
      date: '2024-10-10',
      open: 229.5,
      high: 232.0,
      low: 228.0,
      close: 230.0,
      volume: 54000000,
    },
    {
      date: '2024-10-11',
      open: 230.0,
      high: 233.5,
      low: 229.0,
      close: 232.0,
      volume: 56000000,
    },
    {
      date: '2024-10-12',
      open: 232.0,
      high: 235.0,
      low: 231.0,
      close: 233.5,
      volume: 58000000,
    },
    {
      date: '2024-10-15',
      open: 233.5,
      high: 236.0,
      low: 232.5,
      close: 234.0,
      volume: 52000000,
    },
    {
      date: '2024-10-16',
      open: 234.0,
      high: 237.5,
      low: 233.0,
      close: 236.0,
      volume: 57000000,
    },
  ],
  total_records: 12,
  start_date: '2024-10-01',
  end_date: '2024-10-16',
};

export const mockTSLAData = {
  symbol: 'TSLA',
  data: [
    {
      date: '2024-10-01',
      open: 250.0,
      high: 260.0,
      low: 245.0,
      close: 255.0,
      volume: 80000000,
    },
    {
      date: '2024-10-02',
      open: 255.0,
      high: 265.0,
      low: 250.0,
      close: 260.0,
      volume: 85000000,
    },
    {
      date: '2024-10-03',
      open: 260.0,
      high: 270.0,
      low: 258.0,
      close: 265.0,
      volume: 90000000,
    },
    {
      date: '2024-10-04',
      open: 265.0,
      high: 268.0,
      low: 260.0,
      close: 262.0,
      volume: 75000000,
    },
    {
      date: '2024-10-05',
      open: 262.0,
      high: 267.0,
      low: 259.0,
      close: 264.0,
      volume: 78000000,
    },
  ],
  total_records: 5,
  start_date: '2024-10-01',
  end_date: '2024-10-05',
};

export const mockErrorResponse = {
  detail: 'Stock symbol not found',
};

export const mockEmptyDataResponse = {
  symbol: 'EMPTY',
  data: [],
  total_records: 0,
  start_date: '',
  end_date: '',
};

/**
 * Mock indicator responses for E2E testing
 * These must be mocked alongside prices for the chart to render
 */
export const mockAAPLIndicators = {
  symbol: 'AAPL',
  data: mockAAPLData.data.map((price, index) => ({
    date: price.date,
    ma_20: index >= 10 ? 228.0 + index * 0.5 : undefined,
    cci: 50 + (index * 5),
    cci_signal: index % 2 === 0 ? 'momentum_bullish' : 'momentum_bearish' as const,
  })),
  total_records: mockAAPLData.data.length,
  start_date: mockAAPLData.start_date,
  end_date: mockAAPLData.end_date,
  interval: '1d',
  indicators: ['ma_20', 'cci'],
};

export const mockTSLAIndicators = {
  symbol: 'TSLA',
  data: mockTSLAData.data.map((price, index) => ({
    date: price.date,
    ma_20: index >= 2 ? 258.0 + index * 2 : undefined,
    cci: 30 + (index * 10),
    cci_signal: index % 2 === 0 ? 'momentum_bullish' : 'momentum_bearish' as const,
  })),
  total_records: mockTSLAData.data.length,
  start_date: mockTSLAData.start_date,
  end_date: mockTSLAData.end_date,
  interval: '1d',
  indicators: ['ma_20', 'cci'],
};
