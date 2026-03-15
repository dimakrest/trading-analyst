/**
 * Alerts CRUD Hook
 *
 * Provides create, update, and delete operations for stock price alerts
 * with shared loading and error state.
 */

import { useState, useCallback } from 'react';
import * as alertService from '../services/alertService';
import type { StockAlert, CreateAlertRequest, UpdateAlertRequest } from '../types/alert';

/**
 * Hook for alert mutation operations (create / update / delete)
 *
 * Each operation sets isLoading while in-flight and captures any error.
 * Callers can also read the error to display inline feedback.
 *
 * @returns Mutation functions, isLoading flag, and last error message
 *
 * @example
 * const { createAlert, deleteAlert, isLoading, error } = useAlerts();
 *
 * const newAlerts = await createAlert({
 *   symbol: 'AAPL',
 *   alert_type: 'fibonacci',
 *   config: { levels: [0.382, 0.5, 0.618], tolerance_pct: 0.5, min_swing_pct: 5 },
 * });
 */
export function useAlerts() {
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const createAlert = useCallback(async (data: CreateAlertRequest): Promise<StockAlert[]> => {
    setIsLoading(true);
    setError(null);
    try {
      const alerts = await alertService.createAlert(data);
      return alerts;
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Failed to create alert';
      setError(msg);
      throw err;
    } finally {
      setIsLoading(false);
    }
  }, []);

  const updateAlert = useCallback(async (id: number, data: UpdateAlertRequest): Promise<StockAlert> => {
    setIsLoading(true);
    setError(null);
    try {
      const alert = await alertService.updateAlert(id, data);
      return alert;
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Failed to update alert';
      setError(msg);
      throw err;
    } finally {
      setIsLoading(false);
    }
  }, []);

  const deleteAlertById = useCallback(async (id: number): Promise<void> => {
    setIsLoading(true);
    setError(null);
    try {
      await alertService.deleteAlert(id);
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Failed to delete alert';
      setError(msg);
      throw err;
    } finally {
      setIsLoading(false);
    }
  }, []);

  return { createAlert, updateAlert, deleteAlert: deleteAlertById, isLoading, error };
}
