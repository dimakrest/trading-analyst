/**
 * Comparison Polling Hook
 *
 * Polls a comparison group's status until all simulations reach a terminal state.
 * Keeps polling on transient network errors — error is surfaced in the return value
 * so the UI can show a warning without stopping updates.
 */
import { useEffect, useRef, useState } from 'react';
import { getComparison } from '../services/arenaService';
import type { ComparisonResponse } from '../types/arena';

const POLL_INTERVAL_MS = 3000;
const TERMINAL_STATUSES = new Set(['completed', 'cancelled', 'failed']);

export const useComparisonPolling = (groupId: string) => {
  const [data, setData] = useState<ComparisonResponse | null>(null);
  const [isPolling, setIsPolling] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    // Reset state when groupId changes
    setData(null);
    setError(null);
    setIsPolling(true);

    let cancelled = false;

    const fetchData = async () => {
      try {
        const result = await getComparison(groupId);
        if (cancelled) return;
        setData(result);
        setError(null);
        // Stop polling only when every simulation has reached a terminal state
        const allDone = result.simulations.every((s) => TERMINAL_STATUSES.has(s.status));
        if (allDone) {
          if (intervalRef.current !== null) {
            clearInterval(intervalRef.current);
            intervalRef.current = null;
          }
          setIsPolling(false);
        }
      } catch {
        if (cancelled) return;
        // Surface the error but keep polling — transient network errors should not
        // permanently stop the comparison page from refreshing.
        setError('Failed to load comparison');
      }
    };

    fetchData();
    intervalRef.current = setInterval(fetchData, POLL_INTERVAL_MS);

    return () => {
      cancelled = true;
      if (intervalRef.current !== null) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    };
  }, [groupId]);

  return { data, isPolling, error };
};
