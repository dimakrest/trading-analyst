import { createContext, useContext, useEffect, useState, type ReactNode } from 'react';
import { apiClient } from '@/lib/apiClient';

type Environment = 'development' | 'production' | 'unknown';

interface EnvironmentContextType {
  environment: Environment;
  isLoading: boolean;
}

const EnvironmentContext = createContext<EnvironmentContextType>({
  environment: 'unknown',
  isLoading: true,
});

export function EnvironmentProvider({ children }: { children: ReactNode }) {
  const [environment, setEnvironment] = useState<Environment>('unknown');
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const fetchEnvironment = async () => {
      try {
        const response = await apiClient.get('/v1/health');
        const env = response.data.environment?.toLowerCase();
        if (env === 'development' || env === 'production') {
          setEnvironment(env);
        } else {
          setEnvironment('unknown');
        }
      } catch (error) {
        console.error('Failed to fetch environment:', error);
        setEnvironment('unknown');
      } finally {
        setIsLoading(false);
      }
    };

    fetchEnvironment();
  }, []);

  return (
    <EnvironmentContext.Provider value={{ environment, isLoading }}>
      {children}
    </EnvironmentContext.Provider>
  );
}

// eslint-disable-next-line react-refresh/only-export-components -- Custom hook pattern requires export alongside provider
export function useEnvironment() {
  return useContext(EnvironmentContext);
}
