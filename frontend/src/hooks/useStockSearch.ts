import { useState, useCallback, useEffect } from 'react';

interface UseStockSearchResult {
  symbol: string;
  setSymbol: (symbol: string) => void;
  handleSearch: (searchSymbol: string) => void;
}

export const useStockSearch = (initialSymbol?: string): UseStockSearchResult => {
  const [symbol, setSymbol] = useState<string>(initialSymbol || 'AAPL');

  // Update symbol when initialSymbol changes (e.g., from URL params)
  useEffect(() => {
    if (initialSymbol) {
      setSymbol(initialSymbol.toUpperCase());
    }
  }, [initialSymbol]);

  const handleSearch = useCallback((searchSymbol: string) => {
    const trimmedSymbol = searchSymbol.trim().toUpperCase();
    if (trimmedSymbol) {
      setSymbol(trimmedSymbol);
    }
  }, []);

  return { symbol, setSymbol, handleSearch };
};
