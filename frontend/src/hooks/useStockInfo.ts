import { useState, useEffect, useCallback } from 'react';
import { fetchStockInfo } from '../services/stockService';
import type { StockInfo } from '../types/stock';

interface UseStockInfoResult {
  stockInfo: StockInfo | null;
  isLoading: boolean;
  error: string | null;
  refetch: () => Promise<void>;
}

/**
 * Hook for fetching stock metadata (sector, industry, etc.)
 *
 * Separate from useStockData to avoid concern pollution -
 * stock info doesn't depend on interval and changes rarely.
 *
 * @param symbol - Stock symbol to fetch info for
 * @returns Stock info data, loading state, error, and refetch function
 */
export const useStockInfo = (symbol: string): UseStockInfoResult => {
  const [stockInfo, setStockInfo] = useState<StockInfo | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    if (!symbol) return;

    setIsLoading(true);
    setError(null);

    try {
      const data = await fetchStockInfo(symbol);
      setStockInfo(data);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to fetch stock info';
      setError(errorMessage);
      setStockInfo(null);
    } finally {
      setIsLoading(false);
    }
  }, [symbol]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  return { stockInfo, isLoading, error, refetch: fetchData };
};
