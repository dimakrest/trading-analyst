/**
 * Active Arena Simulation Hook
 *
 * Detects PENDING or RUNNING simulations on page load.
 */
import { useCallback, useEffect, useState } from 'react';
import { listSimulations } from '../services/arenaService';
import type { Simulation } from '../types/arena';

interface UseActiveArenaSimulationReturn {
  /** Active simulation (PENDING or RUNNING) found on mount */
  activeSimulation: Simulation | null;
  /** Whether initial check is loading */
  isLoading: boolean;
  /** Error from fetching simulations */
  error: Error | null;
  /** Clear the active simulation (dismiss banner) */
  clearActiveSimulation: () => void;
}

/**
 * Hook to detect active arena simulations on page load
 *
 * Checks for PENDING or RUNNING simulations when the component mounts.
 * This enables users to resume monitoring a simulation after page refresh.
 *
 * @returns Object with active simulation, loading state, error, and clear function
 *
 * @example
 * const { activeSimulation, isLoading, error, clearActiveSimulation } = useActiveArenaSimulation();
 *
 * if (activeSimulation) {
 *   // Show banner with "View Progress" button
 * }
 */
export const useActiveArenaSimulation = (): UseActiveArenaSimulationReturn => {
  const [activeSimulation, setActiveSimulation] = useState<Simulation | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const clearActiveSimulation = useCallback(() => {
    setActiveSimulation(null);
  }, []);

  useEffect(() => {
    const checkForActiveSimulation = async () => {
      try {
        // Fetch recent simulations
        const response = await listSimulations();

        // Find first PENDING or RUNNING simulation
        const active = response.items.find(
          (sim) => sim.status === 'pending' || sim.status === 'running'
        );

        setActiveSimulation(active || null);
        setError(null);
      } catch (err) {
        setError(err instanceof Error ? err : new Error('Failed to fetch simulations'));
      } finally {
        setIsLoading(false);
      }
    };

    checkForActiveSimulation();
  }, []); // Only run on mount

  return {
    activeSimulation,
    isLoading,
    error,
    clearActiveSimulation,
  };
};
