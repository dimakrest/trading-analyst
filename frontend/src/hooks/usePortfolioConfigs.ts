import { useEffect, useState } from 'react';
import type { PortfolioConfig } from '@/types/portfolioConfig';
import { portfolioConfigService } from '@/services/portfolioConfigService';

/**
 * Fetches portfolio configurations and provides loading/error state.
 */
export function usePortfolioConfigs() {
  const [configs, setConfigs] = useState<PortfolioConfig[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const loadConfigs = async () => {
      setIsLoading(true);
      setError(null);
      try {
        const response = await portfolioConfigService.getConfigs();
        setConfigs(response.items);
      } catch (err) {
        const message =
          err instanceof Error
            ? err.message
            : 'Failed to load portfolio configurations';
        setError(message);
        console.error('Failed to load portfolio configs:', err);
      } finally {
        setIsLoading(false);
      }
    };

    loadConfigs();
  }, []);

  return {
    configs,
    setConfigs,
    isLoading,
    error,
  };
}
