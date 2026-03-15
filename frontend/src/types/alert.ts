/**
 * Stock Price Alert types
 *
 * Type definitions for the Stock Price Alerts feature.
 * Covers Fibonacci retracement and moving average alert types.
 */

export type AlertType = 'fibonacci' | 'moving_average';
export type FibonacciStatus = 'no_structure' | 'rallying' | 'pullback_started' | 'retracing' | 'at_level' | 'bouncing' | 'invalidated';
export type MAStatus = 'above_ma' | 'approaching' | 'at_ma' | 'below_ma' | 'insufficient_data';

interface StockAlertBase {
  id: number;
  symbol: string;
  is_active: boolean;
  is_paused: boolean;
  last_triggered_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface FibonacciAlert extends StockAlertBase {
  alert_type: 'fibonacci';
  status: FibonacciStatus;
  config: FibonacciConfig;
  computed_state: FibonacciComputedState | null;
}

export interface MAAlert extends StockAlertBase {
  alert_type: 'moving_average';
  status: MAStatus;
  config: MAConfig;
  computed_state: MAComputedState | null;
}

export type StockAlert = FibonacciAlert | MAAlert;

/** Type guard for Fibonacci alerts */
export function isFibAlert(alert: StockAlert): alert is FibonacciAlert {
  return alert.alert_type === 'fibonacci';
}

/** Type guard for Moving Average alerts */
export function isMAAlert(alert: StockAlert): alert is MAAlert {
  return alert.alert_type === 'moving_average';
}

export interface FibonacciConfig {
  levels: number[];
  tolerance_pct: number;
  min_swing_pct: number;
}

export interface MAConfig {
  ma_period: number;
  tolerance_pct: number;
  direction: 'above' | 'below' | 'both';
}

export interface FibLevelState {
  price: number;
  status: 'pending' | 'active' | 'triggered';
  triggered_at: string | null;
}

export interface FibonacciComputedState {
  swing_high: number;
  swing_low: number;
  swing_high_date: string;
  swing_low_date: string;
  trend_direction: 'uptrend' | 'downtrend';
  current_price: number;
  retracement_pct: number;
  fib_levels: Record<string, FibLevelState>;
  next_level: { pct: number; price: number } | null;
}

export interface MAComputedState {
  ma_value: number;
  ma_period: number;
  current_price: number;
  distance_pct: number;
  ma_slope: 'rising' | 'falling' | 'flat';
}

export interface AlertEvent {
  id: number;
  alert_id: number;
  event_type: 'level_hit' | 'invalidated' | 're_anchored' | 'status_change';
  previous_status: string | null;
  new_status: string;
  price_at_event: number;
  details: Record<string, unknown> | null;
  created_at: string;
}

/** View model for table rendering */
export interface AlertTableRow {
  id: number;
  symbol: string;
  alertTypeLabel: string;
  currentPrice: number | null;
  status: string;
  detailsText: string;
  lastTriggeredAt: string | null;
}

/** Transform a StockAlert into a flat table row for display */
export function toAlertTableRow(alert: StockAlert): AlertTableRow {
  if (isFibAlert(alert)) {
    const cs = alert.computed_state;
    return {
      id: alert.id,
      symbol: alert.symbol,
      alertTypeLabel: 'Fibonacci Retracement',
      currentPrice: cs?.current_price ?? null,
      status: alert.status,
      detailsText: cs
        ? `$${cs.swing_low.toFixed(2)} → $${cs.swing_high.toFixed(2)} | ${cs.retracement_pct.toFixed(1)}%${cs.next_level ? ` | Next: ${cs.next_level.pct}% @ $${cs.next_level.price.toFixed(2)}` : ''}`
        : 'Awaiting data',
      lastTriggeredAt: alert.last_triggered_at,
    };
  }
  if (isMAAlert(alert)) {
    const cs = alert.computed_state;
    return {
      id: alert.id,
      symbol: alert.symbol,
      alertTypeLabel: `MA${alert.config.ma_period}`,
      currentPrice: cs?.current_price ?? null,
      status: alert.status,
      detailsText: cs
        ? `MA${cs.ma_period} @ $${cs.ma_value.toFixed(2)} | ${cs.distance_pct > 0 ? '+' : ''}${cs.distance_pct.toFixed(1)}% ${cs.ma_slope}`
        : 'Awaiting data',
      lastTriggeredAt: alert.last_triggered_at,
    };
  }
  // Unknown alert type fallback
  return {
    id: alert.id,
    symbol: alert.symbol,
    alertTypeLabel: 'Unknown',
    currentPrice: null,
    status: (alert as StockAlertBase & { status: string }).status,
    detailsText: '--',
    lastTriggeredAt: alert.last_triggered_at,
  };
}

/** Request body for creating a Fibonacci retracement alert */
export interface CreateFibonacciAlertRequest {
  symbol: string;
  alert_type: 'fibonacci';
  config: {
    levels: number[];
    tolerance_pct: number;
    min_swing_pct: number;
  };
}

/** Request body for creating a moving average alert */
export interface CreateMAAlertRequest {
  symbol: string;
  alert_type: 'moving_average';
  config: {
    ma_periods: number[];
    tolerance_pct: number;
    direction: 'above' | 'below' | 'both';
  };
}

export type CreateAlertRequest = CreateFibonacciAlertRequest | CreateMAAlertRequest;

export interface UpdateAlertRequest {
  config?: FibonacciConfig | MAConfig;
  is_paused?: boolean;
}

export interface AlertListResponse {
  items: StockAlert[];
  total: number;
}

export interface AlertPriceDataResponse {
  symbol: string;
  alert_id: number;
  data: Record<string, unknown>[];
  days: number;
}
