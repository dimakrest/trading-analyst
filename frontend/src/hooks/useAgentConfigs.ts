import { useState, useEffect } from 'react';
import { agentConfigService } from '@/services/agentConfigService';
import type { AgentConfig } from '@/types/agentConfig';

/**
 * Custom hook for managing agent configuration state
 *
 * Fetches available agent configurations on mount and provides
 * state management for config selection.
 *
 * Auto-selects the first config if none is currently selected.
 *
 * @returns Agent configs state and selection handlers
 *
 * @example
 * ```tsx
 * const {
 *   configs,
 *   selectedConfigId,
 *   setSelectedConfigId,
 *   isLoading,
 *   error
 * } = useAgentConfigs();
 * ```
 */
export function useAgentConfigs() {
  const [configs, setConfigs] = useState<AgentConfig[]>([]);
  const [selectedConfigId, setSelectedConfigId] = useState<number | undefined>();
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const loadConfigs = async () => {
      setIsLoading(true);
      setError(null);
      try {
        const response = await agentConfigService.getConfigs();
        setConfigs(response.items);

        // Auto-select first config if none selected
        if (response.items.length > 0 && !selectedConfigId) {
          setSelectedConfigId(response.items[0].id);
        }
      } catch (err) {
        const errorMessage = err instanceof Error ? err.message : 'Failed to load agent configurations';
        setError(errorMessage);
        console.error('Failed to load agent configs:', err);
      } finally {
        setIsLoading(false);
      }
    };

    loadConfigs();
  }, []); // Only run on mount

  return {
    configs,
    selectedConfigId,
    setSelectedConfigId,
    isLoading,
    error,
  };
}
