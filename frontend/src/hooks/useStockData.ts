import { useState, useEffect, useCallback } from 'react';
import { fetchStockData, fetchIndicators } from '../services/stockService';
import type { StockData, Interval, StockPrice, IndicatorData } from '../types/stock';

interface UseStockDataResult {
  data: StockData | null;
  loading: boolean;
  error: string | null;
  refetch: () => Promise<void>;
}

export const useStockData = (symbol: string, interval: Interval = '1d'): UseStockDataResult => {
  const [data, setData] = useState<StockData | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    if (!symbol) return;

    setLoading(true);
    setError(null);

    try {
      // Fetch prices and indicators in parallel
      const [pricesData, indicatorsData] = await Promise.all([
        fetchStockData(symbol, interval),
        fetchIndicators(symbol, interval),
      ]);

      // Create a map of date -> indicator values for fast lookup
      const indicatorMap = new Map<string, IndicatorData>();
      indicatorsData.data.forEach((indicator) => {
        indicatorMap.set(indicator.date, indicator);
      });

      // Merge indicator data into price data by matching dates
      const mergedPrices: StockPrice[] = pricesData.prices.map((price) => {
        const indicators = indicatorMap.get(price.date);
        return {
          ...price,
          ma_20: indicators?.ma_20,
          cci: indicators?.cci,
          cci_signal: indicators?.cci_signal,
        };
      });

      // Return the complete stock data with merged prices
      setData({
        ...pricesData,
        prices: mergedPrices,
      });
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to fetch stock data';
      setError(errorMessage);
      setData(null);
    } finally {
      setLoading(false);
    }
  }, [symbol, interval]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  return { data, loading, error, refetch: fetchData };
};
