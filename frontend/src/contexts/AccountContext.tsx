import { createContext, useContext, useEffect, useState, useCallback } from 'react';
import type { ReactNode } from 'react';
import { getSystemStatus } from '@/services/accountService';
import type { SystemStatus, BrokerStatus, DataProviderStatus } from '@/types/account';

interface AccountContextType {
  status: SystemStatus | null;
  isLoading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
}

const defaultBrokerStatus: BrokerStatus = {
  connection_status: 'DISCONNECTED',
  error_message: 'Loading...',
  account_id: null,
  account_type: null,
  net_liquidation: null,
  buying_power: null,
  unrealized_pnl: null,
  realized_pnl: null,
  daily_pnl: null,
};

const defaultDataProviderStatus: DataProviderStatus = {
  connection_status: 'DISCONNECTED',
  error_message: 'Loading...',
};

const AccountContext = createContext<AccountContextType>({
  status: null,
  isLoading: true,
  error: null,
  refresh: async () => {},
});

const POLLING_INTERVAL = 30000; // 30 seconds

export function AccountProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<SystemStatus | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchStatus = useCallback(async (signal?: AbortSignal) => {
    try {
      setError(null);
      const data = await getSystemStatus(signal);
      setStatus(data);
    } catch (err) {
      // Ignore abort errors (component unmounted or new request started)
      if (err instanceof Error && err.name === 'CanceledError') {
        return;
      }
      const errorMessage = err instanceof Error ? err.message : 'Failed to fetch system status';
      setError(errorMessage);
      // Set disconnected status on fetch error
      setStatus({
        broker: {
          ...defaultBrokerStatus,
          error_message: errorMessage,
        },
        data_provider: {
          ...defaultDataProviderStatus,
          error_message: errorMessage,
        },
      });
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    let mounted = true;
    let abortController = new AbortController();

    const fetch = async () => {
      if (!mounted) return;

      // Cancel previous request if still in flight
      abortController.abort();
      abortController = new AbortController();

      await fetchStatus(abortController.signal);
    };

    // Initial fetch
    fetch();

    // Set up polling
    const intervalId = setInterval(fetch, POLLING_INTERVAL);

    // Cleanup: cancel in-flight requests and stop polling
    return () => {
      mounted = false;
      abortController.abort();
      clearInterval(intervalId);
    };
  }, [fetchStatus]);

  const refresh = useCallback(async () => {
    setIsLoading(true);
    await fetchStatus();
  }, [fetchStatus]);

  return (
    <AccountContext.Provider value={{ status, isLoading, error, refresh }}>
      {children}
    </AccountContext.Provider>
  );
}

// eslint-disable-next-line react-refresh/only-export-components -- Custom hook pattern requires export alongside provider
export function useAccount() {
  return useContext(AccountContext);
}
