import { apiClient } from '../lib/apiClient';
import type { StockData, StockPrice, Interval, IndicatorsResponse, StockInfo } from '../types/stock';

interface BackendStockResponse {
  symbol: string;
  data: StockPrice[];
  total_records: number;
  start_date: string;
  end_date: string;
}

export const fetchStockData = async (symbol: string, interval: Interval = '1d'): Promise<StockData> => {
  // Adjust period based on interval: 5d for 1h (IBKR limitation), 1y for 1d
  const period = interval === '1h' ? '5d' : '1y';

  const response = await apiClient.get<BackendStockResponse>(`/v1/stocks/${symbol}/prices/`, {
    params: {
      period,
      interval,
    },
  });

  const { symbol: stockSymbol, data } = response.data;

  if (!data || data.length === 0) {
    throw new Error('No price data available');
  }

  // Calculate current price and changes
  const currentPrice = data[data.length - 1].close;
  const previousPrice = data.length > 1 ? data[0].close : currentPrice;
  const priceChange = currentPrice - previousPrice;
  const priceChangePercent = ((priceChange / previousPrice) * 100);

  return {
    symbol: stockSymbol,
    company_name: stockSymbol, // Using symbol as placeholder - company name requires separate API endpoint
    current_price: currentPrice,
    price_change: priceChange,
    price_change_percent: priceChangePercent,
    prices: data,
  };
};

interface FetchStockDataByDateRangeOptions {
  symbol: string;
  startDate: string;  // YYYY-MM-DD
  endDate: string;    // YYYY-MM-DD
  interval?: Interval;  // Optional, defaults to '1d'
}

export const fetchStockDataByDateRange = async ({
  symbol,
  startDate,
  endDate,
  interval = '1d',
}: FetchStockDataByDateRangeOptions): Promise<StockData> => {
  const response = await apiClient.get<BackendStockResponse>(`/v1/stocks/${symbol}/prices/`, {
    params: {
      start_date: startDate,
      end_date: endDate,
      interval,
    },
  });

  const { symbol: stockSymbol, data } = response.data;

  if (!data || data.length === 0) {
    throw new Error('No price data available for the specified date range');
  }

  // Calculate current price and changes
  const currentPrice = data[data.length - 1].close;
  const previousPrice = data.length > 1 ? data[0].close : currentPrice;
  const priceChange = currentPrice - previousPrice;
  const priceChangePercent = ((priceChange / previousPrice) * 100);

  return {
    symbol: stockSymbol,
    company_name: stockSymbol,
    current_price: currentPrice,
    price_change: priceChange,
    price_change_percent: priceChangePercent,
    prices: data,
  };
};

export const fetchIndicators = async (
  symbol: string,
  interval: Interval = '1d'
): Promise<IndicatorsResponse> => {
  const period = interval === '1h' ? '5d' : '1y';
  const response = await apiClient.get<IndicatorsResponse>(`/v1/stocks/${symbol}/indicators/`, {
    params: {
      period,
      interval,
    },
  });

  return response.data;
};

export const fetchStockInfo = async (symbol: string): Promise<StockInfo> => {
  const response = await apiClient.get<StockInfo>(`/v1/stocks/${symbol}/info`);
  return response.data;
};

/**
 * Stock service with all stock-related API functions
 */
export const stockService = {
  fetchStockData,
  fetchStockDataByDateRange,
  fetchIndicators,
  fetchStockInfo,
};
