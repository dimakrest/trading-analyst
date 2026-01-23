/**
 * Arena Polling Hook
 *
 * Polls a simulation's status until it reaches a terminal state.
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import { cancelSimulation, getSimulation } from '../services/arenaService';
import type { SimulationDetail } from '../types/arena';

const POLL_INTERVAL_MS = 2000; // 2 seconds

interface UseArenaPollingReturn {
  /** Current simulation detail (null if no simulation) */
  detail: SimulationDetail | null;
  /** Whether polling is active */
  isPolling: boolean;
  /** Error from polling or cancellation */
  error: Error | null;
  /** Cancel the simulation */
  cancel: () => Promise<void>;
  /** Whether cancellation is in progress */
  isCancelling: boolean;
  /** Manually refetch the simulation */
  refetch: () => Promise<void>;
}

/**
 * Hook to poll an arena simulation until it reaches a terminal state
 *
 * Automatically polls the simulation status every 2 seconds until the
 * simulation reaches one of the terminal states: 'completed', 'cancelled', or 'failed'.
 *
 * @param simulationId - Simulation ID to poll (null to disable polling)
 * @returns Object with detail data, polling state, cancel function, and error state
 *
 * @example
 * const { detail, isPolling, error, cancel, isCancelling, refetch } = useArenaPolling(123);
 *
 * if (isPolling) {
 *   // Show progress UI
 * }
 *
 * if (detail?.simulation.status === 'completed') {
 *   // Show results
 * }
 */
export const useArenaPolling = (
  simulationId: number | null
): UseArenaPollingReturn => {
  const [detail, setDetail] = useState<SimulationDetail | null>(null);
  const [isPolling, setIsPolling] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const [isCancelling, setIsCancelling] = useState(false);
  const pollingIntervalRef = useRef<NodeJS.Timeout | null>(null);

  // Clear polling interval
  const clearPolling = useCallback(() => {
    if (pollingIntervalRef.current) {
      clearInterval(pollingIntervalRef.current);
      pollingIntervalRef.current = null;
    }
    setIsPolling(false);
  }, []);

  // Fetch simulation status
  const fetchStatus = useCallback(async () => {
    if (!simulationId) return;

    try {
      const data = await getSimulation(simulationId);
      setDetail(data);
      setError(null);

      // Stop polling if simulation reached terminal state
      const terminalStates = ['completed', 'cancelled', 'failed'];
      if (terminalStates.includes(data.simulation.status)) {
        clearPolling();
      }
    } catch (err) {
      setError(err instanceof Error ? err : new Error('Failed to fetch simulation'));
      clearPolling();
    }
  }, [simulationId, clearPolling]);

  // Cancel simulation
  const cancel = useCallback(async () => {
    if (!simulationId) return;

    setIsCancelling(true);
    try {
      await cancelSimulation(simulationId);
      // Immediately fetch updated status
      await fetchStatus();
    } catch (err) {
      setError(err instanceof Error ? err : new Error('Failed to cancel simulation'));
    } finally {
      setIsCancelling(false);
    }
  }, [simulationId, fetchStatus]);

  // Start/stop polling based on simulationId
  useEffect(() => {
    // Reset state when simulationId changes
    if (!simulationId) {
      clearPolling();
      setDetail(null);
      setError(null);
      setIsCancelling(false);
      return;
    }

    // Initial fetch
    fetchStatus();

    // Start polling
    setIsPolling(true);
    pollingIntervalRef.current = setInterval(fetchStatus, POLL_INTERVAL_MS);

    // Cleanup on unmount or simulationId change
    return () => {
      clearPolling();
    };
  }, [simulationId, fetchStatus, clearPolling]);

  return {
    detail,
    isPolling,
    error,
    cancel,
    isCancelling,
    refetch: fetchStatus,
  };
};
