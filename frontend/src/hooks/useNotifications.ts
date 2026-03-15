/**
 * Web Notifications Hook
 *
 * Wraps the browser Notification API with a sonner toast fallback for
 * environments where notifications are unavailable or denied.
 */

import { useState, useCallback } from 'react';
import { toast } from 'sonner';

const getInitialPermission = (): NotificationPermission => {
  if (typeof Notification === 'undefined') return 'default';
  return Notification.permission;
};

/**
 * Hook for requesting and sending browser notifications
 *
 * Falls back to sonner toast when the Notification API is unavailable
 * (e.g., SSR, user denied permission).
 *
 * @returns permission state, requestPermission function, and notify function
 *
 * @example
 * const { permission, requestPermission, notify } = useNotifications();
 *
 * // Request permission on user gesture
 * await requestPermission();
 *
 * // Send a notification (toast fallback if no permission)
 * notify('AAPL Alert', 'AAPL hit a Fibonacci level', alertId);
 */
export function useNotifications() {
  const [permission, setPermission] = useState<NotificationPermission>(getInitialPermission);

  const requestPermission = useCallback(async (): Promise<NotificationPermission> => {
    if (typeof Notification === 'undefined') return 'denied';
    const result = await Notification.requestPermission();
    setPermission(result);
    return result;
  }, []);

  const notify = useCallback(
    (title: string, body: string, alertId?: number) => {
      if (typeof Notification !== 'undefined' && permission === 'granted') {
        const n = new Notification(title, { body, icon: '/favicon.ico' });
        if (alertId !== undefined) {
          n.onclick = () => {
            window.focus();
            window.history.pushState({}, '', `/alerts/${alertId}`);
            window.dispatchEvent(new PopStateEvent('popstate'));
          };
        }
      } else {
        toast(title, { description: body });
      }
    },
    [permission]
  );

  return { permission, requestPermission, notify };
}
