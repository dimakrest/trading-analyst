/**
 * Alert Detail Hook
 *
 * Fetches a single alert, its event history, and historical price data
 * in parallel for the alert detail view.
 */

import { useState, useEffect, useCallback } from 'react';
import { getAlert, getAlertEvents, getAlertPriceData } from '../services/alertService';
import type { StockAlert, AlertEvent, AlertPriceDataResponse } from '../types/alert';

/**
 * Hook for loading full alert detail including events and price data
 *
 * All three requests are issued in parallel via Promise.all. Passing
 * alertId as null disables the fetch (useful while a modal is closed).
 *
 * @param alertId - ID of the alert to load, or null to skip fetching
 * @returns alert, events, priceData, loading state, error, and refetch
 *
 * @example
 * const { alert, events, priceData, isLoading, error, refetch } = useAlertDetail(42);
 *
 * if (isLoading) return <Spinner />;
 * if (error) return <ErrorMessage message={error} />;
 */
export function useAlertDetail(alertId: number | null) {
  const [alert, setAlert] = useState<StockAlert | null>(null);
  const [events, setEvents] = useState<AlertEvent[]>([]);
  const [priceData, setPriceData] = useState<AlertPriceDataResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchDetail = useCallback(async () => {
    if (alertId === null) return;

    setIsLoading(true);
    setError(null);

    try {
      const [alertData, eventsData, priceDataResult] = await Promise.all([
        getAlert(alertId),
        getAlertEvents(alertId),
        getAlertPriceData(alertId),
      ]);
      setAlert(alertData);
      setEvents(eventsData);
      setPriceData(priceDataResult);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load alert detail');
    } finally {
      setIsLoading(false);
    }
  }, [alertId]);

  useEffect(() => {
    fetchDetail();
  }, [fetchDetail]);

  return { alert, events, priceData, isLoading, error, refetch: fetchDetail };
}
