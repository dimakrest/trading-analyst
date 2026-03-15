/**
 * Alert Polling Hook
 *
 * Polls the alerts list on a fixed interval and fires browser/toast
 * notifications when an alert transitions to an actionable status.
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import { listAlerts } from '../services/alertService';
import { useNotifications } from './useNotifications';
import { isFibAlert, isMAAlert } from '../types/alert';
import type { StockAlert } from '../types/alert';

const POLL_INTERVAL_MS = 30_000; // 30 seconds

/**
 * Build a rich notification body for a Fibonacci alert that just hit a level.
 *
 * Uses computed_state to include the specific level percentage, current price,
 * and the swing range so the user has full context at a glance.
 */
function buildFibAtLevelMessage(alert: StockAlert): string {
  if (!isFibAlert(alert)) return `${alert.symbol} hit a Fibonacci level`;

  const cs = alert.computed_state;
  if (!cs) return `${alert.symbol} hit a Fibonacci level`;

  // Find the most recently triggered level by looking for triggered fib levels
  const triggeredEntries = Object.entries(cs.fib_levels).filter(
    ([, lvl]) => lvl.status === 'triggered'
  );

  // Sort by triggered_at descending to find the latest one, fall back to next_level pct
  let levelPct: string | null = null;
  if (triggeredEntries.length > 0) {
    const sorted = triggeredEntries.sort((a, b) => {
      const tA = a[1].triggered_at ?? '';
      const tB = b[1].triggered_at ?? '';
      return tB.localeCompare(tA);
    });
    levelPct = sorted[0][0];
  } else if (cs.next_level) {
    levelPct = String(cs.next_level.pct);
  }

  const levelStr = levelPct !== null ? `${levelPct}% Fibonacci` : 'a Fibonacci level';
  const priceStr = `$${cs.current_price.toFixed(2)}`;
  const swingStr = `swing: $${cs.swing_low.toFixed(2)}→$${cs.swing_high.toFixed(2)}`;

  return `${alert.symbol} hit ${levelStr} at ${priceStr} (${swingStr})`;
}

/**
 * Build a rich notification body for a Fibonacci alert that was invalidated.
 *
 * Shows the swing low that was broken so the user understands the context.
 */
function buildFibInvalidatedMessage(alert: StockAlert): string {
  if (!isFibAlert(alert)) return `${alert.symbol} — Fibonacci setup invalidated`;

  const cs = alert.computed_state;
  if (!cs) return `${alert.symbol} — Fibonacci setup invalidated`;

  const swingOrigin =
    cs.trend_direction === 'uptrend'
      ? `swing low $${cs.swing_low.toFixed(2)}`
      : `swing high $${cs.swing_high.toFixed(2)}`;

  const direction = cs.trend_direction === 'uptrend' ? 'broke below' : 'broke above';

  return `${alert.symbol} ${direction} ${swingOrigin} — Fibonacci setup invalidated`;
}

/**
 * Build a rich notification body for an MA alert that just touched the MA.
 *
 * Shows the MA period, MA value, and distance so the user sees the full picture.
 */
function buildMAAtMaMessage(alert: StockAlert): string {
  if (!isMAAlert(alert)) return `${alert.symbol} touched moving average`;

  const cs = alert.computed_state;
  if (!cs) return `${alert.symbol} touched MA${alert.config.ma_period}`;

  const distStr = `${cs.distance_pct.toFixed(1)}% away`;

  return `${alert.symbol} touched MA${cs.ma_period} at $${cs.ma_value.toFixed(2)} (${distStr})`;
}

/**
 * Hook that continuously polls the alert list and notifies on status changes.
 *
 * Status change notifications are suppressed on the initial fetch to avoid
 * a flood of notifications when the page first loads (B3).
 *
 * Notifies when an alert transitions to:
 * - 'at_level'   (Fibonacci) with level details from computed_state
 * - 'at_ma'      (Moving Average) with MA value and distance
 * - 'invalidated' (Fibonacci) when the setup is broken
 *
 * @param interval - Poll interval in milliseconds (default: 30 000)
 * @returns alerts array, loading state, error message, and manual refetch
 *
 * @example
 * const { alerts, isLoading, error, refetch } = useAlertPolling();
 */
export function useAlertPolling(interval = POLL_INTERVAL_MS) {
  const [alerts, setAlerts] = useState<StockAlert[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const previousAlertsRef = useRef<StockAlert[]>([]);
  const isFirstFetchRef = useRef(true);

  const { notify } = useNotifications();

  const fetchAlerts = useCallback(async () => {
    try {
      const response = await listAlerts();
      const newAlerts = response.items;
      setAlerts(newAlerts);
      setError(null);

      // Skip change detection on the initial fetch (B3)
      if (isFirstFetchRef.current) {
        isFirstFetchRef.current = false;
        previousAlertsRef.current = newAlerts;
        return;
      }

      // Detect status transitions and fire notifications for actionable states
      for (const alert of newAlerts) {
        const prev = previousAlertsRef.current.find((a) => a.id === alert.id);
        if (!prev || prev.status === alert.status) continue;

        if (alert.status === 'at_level') {
          notify(
            `${alert.symbol} — Fibonacci Alert`,
            buildFibAtLevelMessage(alert),
            alert.id
          );
        } else if (alert.status === 'at_ma') {
          notify(
            `${alert.symbol} — MA Alert`,
            buildMAAtMaMessage(alert),
            alert.id
          );
        } else if (alert.status === 'invalidated') {
          notify(
            `${alert.symbol} — Setup Invalidated`,
            buildFibInvalidatedMessage(alert),
            alert.id
          );
        }
      }

      previousAlertsRef.current = newAlerts;
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load alerts');
    } finally {
      setIsLoading(false);
    }
  }, [notify]);

  useEffect(() => {
    fetchAlerts();
    const intervalId = setInterval(fetchAlerts, interval);
    return () => clearInterval(intervalId);
  }, [fetchAlerts, interval]);

  return { alerts, isLoading, error, refetch: fetchAlerts };
}
