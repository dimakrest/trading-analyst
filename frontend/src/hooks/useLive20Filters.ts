import { useState, useMemo } from 'react';
import type { Live20Direction, Live20Result } from '../types/live20';

/** Upper bound for the ATR% slider range. */
export const ATR_SLIDER_MAX = 15;

export function useLive20Filters(results: Live20Result[]) {
  const [directionFilter, setDirectionFilter] = useState<Live20Direction | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [minScore, setMinScore] = useState(0);
  const [minRvol, setMinRvol] = useState(0);
  const [atrRange, setAtrRange] = useState<[number, number]>([0, 0]);

  const isAtrFilterActive = atrRange[0] > 0 || atrRange[1] > 0;

  const filteredResults = useMemo(() => {
    let filtered = results;

    if (directionFilter) {
      filtered = filtered.filter((r) => r.direction === directionFilter);
    }

    if (searchQuery) {
      const query = searchQuery.toLowerCase();
      filtered = filtered.filter((r) => r.stock.toLowerCase().includes(query));
    }

    if (minScore > 0) {
      filtered = filtered.filter((r) => r.confidence_score >= minScore);
    }

    if (minRvol > 0) {
      filtered = filtered.filter((r) => (r.rvol ?? 0) >= minRvol);
    }

    // ATR range filter — stocks with null ATR always pass (never hide due to missing data)
    if (atrRange[0] > 0) {
      filtered = filtered.filter((r) => r.atr === null || r.atr >= atrRange[0]);
    }
    if (atrRange[1] > 0) {
      filtered = filtered.filter((r) => r.atr === null || r.atr <= atrRange[1]);
    }

    return filtered;
  }, [results, directionFilter, searchQuery, minScore, minRvol, atrRange]);

  return {
    directionFilter,
    setDirectionFilter,
    searchQuery,
    setSearchQuery,
    minScore,
    setMinScore,
    minRvol,
    setMinRvol,
    atrRange,
    setAtrRange,
    isAtrFilterActive,
    filteredResults,
  };
}
