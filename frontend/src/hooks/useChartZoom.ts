import { useState, useEffect, useCallback } from 'react';

interface ChartState {
  symbol: string;
  zoomLevel: number;
  visibleRange: {
    from: number;
    to: number;
  };
  lastUpdated: string;
}

const STORAGE_PREFIX = 'chart-state-';
const EXPIRATION_DAYS = 7;

/**
 * Custom hook to persist and restore chart zoom state
 *
 * @param symbol - Stock symbol (e.g., 'AAPL')
 * @returns Object with zoom state and setter functions
 */
export const useChartZoom = (symbol: string) => {
  const [zoomLevel, setZoomLevel] = useState<number>(0.5); // 0 = max zoom out, 1 = max zoom in
  const [visibleRange, setVisibleRange] = useState<{ from: number; to: number } | null>(null);

  const storageKey = `${STORAGE_PREFIX}${symbol.toUpperCase()}`;

  // Load zoom state from localStorage on mount or symbol change
  useEffect(() => {
    try {
      const storedState = localStorage.getItem(storageKey);
      if (storedState) {
        const state: ChartState = JSON.parse(storedState);

        // Check if state is expired (older than 7 days)
        const lastUpdated = new Date(state.lastUpdated);
        const daysSinceUpdate = (Date.now() - lastUpdated.getTime()) / (1000 * 60 * 60 * 24);

        if (daysSinceUpdate < EXPIRATION_DAYS) {
          setZoomLevel(state.zoomLevel);
          setVisibleRange(state.visibleRange);
        } else {
          // Clear expired state
          localStorage.removeItem(storageKey);
        }
      }
    } catch {
      // Silent fail - invalid localStorage state, clear it
      localStorage.removeItem(storageKey);
    }
  }, [symbol, storageKey]);

  // Save zoom state to localStorage
  const saveZoomState = useCallback(
    (newZoomLevel: number, newVisibleRange: { from: number; to: number }) => {
      try {
        const state: ChartState = {
          symbol: symbol.toUpperCase(),
          zoomLevel: newZoomLevel,
          visibleRange: newVisibleRange,
          lastUpdated: new Date().toISOString(),
        };

        localStorage.setItem(storageKey, JSON.stringify(state));
        setZoomLevel(newZoomLevel);
        setVisibleRange(newVisibleRange);
      } catch {
        // Silent fail - localStorage quota exceeded or unavailable
      }
    },
    [symbol, storageKey]
  );

  // Clear zoom state (useful when switching symbols)
  const clearZoomState = useCallback(() => {
    try {
      localStorage.removeItem(storageKey);
      setZoomLevel(0.5);
      setVisibleRange(null);
    } catch {
      // Silent fail - localStorage unavailable
    }
  }, [storageKey]);

  return {
    zoomLevel,
    visibleRange,
    saveZoomState,
    clearZoomState,
  };
};
