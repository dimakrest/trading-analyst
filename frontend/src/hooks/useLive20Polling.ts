import { useState, useEffect, useCallback, useRef } from 'react';
import { getRunDetail } from '../services/live20Service';
import type { Live20RunDetail } from '../types/live20';

const POLL_INTERVAL_MS = 2000; // 2 seconds

interface UseLive20PollingReturn {
  /** Current run data (null if no run) */
  run: Live20RunDetail | null;
  /** Whether polling is active */
  isPolling: boolean;
  /** Error from polling */
  error: string | null;
  /** Reset the polling state */
  reset: () => void;
}

/**
 * Hook to poll a Live 20 analysis run until it reaches a terminal state
 *
 * Automatically polls the run status every 2 seconds until the run reaches
 * one of the terminal states: 'completed', 'cancelled', or 'failed'.
 *
 * @param runId - Run ID to poll (null to disable polling)
 * @returns Object with run data, polling state, and error state
 *
 * @example
 * const { run, isPolling, error } = useLive20Polling(123);
 *
 * if (isPolling) {
 *   // Show progress UI with run.processed_count / run.symbol_count
 * }
 *
 * if (run?.status === 'completed') {
 *   // Show results from run.results
 * }
 */
export const useLive20Polling = (runId: number | null): UseLive20PollingReturn => {
  const [run, setRun] = useState<Live20RunDetail | null>(null);
  const [isPolling, setIsPolling] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const pollingIntervalRef = useRef<NodeJS.Timeout | null>(null);

  // Clear polling interval
  const clearPolling = useCallback(() => {
    if (pollingIntervalRef.current) {
      clearInterval(pollingIntervalRef.current);
      pollingIntervalRef.current = null;
    }
    setIsPolling(false);
  }, []);

  // Reset state
  const reset = useCallback(() => {
    clearPolling();
    setRun(null);
    setError(null);
  }, [clearPolling]);

  // Fetch run status
  const fetchRunStatus = useCallback(async () => {
    if (!runId) return;

    try {
      const data = await getRunDetail(runId);
      setRun(data);
      setError(null);

      // Stop polling if run reached terminal state
      if (data.status === 'completed' || data.status === 'failed' || data.status === 'cancelled') {
        clearPolling();
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch run status');
      clearPolling();
    }
  }, [runId, clearPolling]);

  // Start/stop polling based on runId
  useEffect(() => {
    // Reset state when runId changes to null
    if (!runId) {
      clearPolling();
      // Don't clear run data - keep last results visible
      return;
    }

    // Reset for new runId
    setRun(null);
    setError(null);

    // Initial fetch
    fetchRunStatus();

    // Start polling
    setIsPolling(true);
    pollingIntervalRef.current = setInterval(fetchRunStatus, POLL_INTERVAL_MS);

    // Cleanup on unmount or runId change
    return () => {
      clearPolling();
    };
  }, [runId, fetchRunStatus, clearPolling]);

  return {
    run,
    isPolling,
    error,
    reset,
  };
};
