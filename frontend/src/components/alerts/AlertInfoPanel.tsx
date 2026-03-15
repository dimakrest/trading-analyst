import { Card, CardContent, CardHeader, CardTitle } from '../ui/card';
import { AlertStatusBadge } from './AlertStatusBadge';
import type { StockAlert, AlertEvent, FibonacciAlert, MAAlert } from '../../types/alert';
import { isFibAlert, isMAAlert } from '../../types/alert';

interface AlertInfoPanelProps {
  alert: StockAlert;
  events: AlertEvent[];
}

/** Format a date string to a readable local timestamp */
function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

/** Format a short relative date (e.g. "Mar 15, 2026 at 10:42 AM") */
function formatShortDate(dateStr: string): string {
  return new Date(dateStr).toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

const EVENT_TYPE_LABELS: Record<string, string> = {
  level_hit: 'Level Hit',
  invalidated: 'Invalidated',
  re_anchored: 'Re-anchored',
  status_change: 'Status Change',
};

const LEVEL_STATUS_COLORS: Record<string, string> = {
  triggered: 'text-red-400',
  active: 'text-yellow-400',
  pending: 'text-text-muted',
};

function FibonacciInfoSection({ alert }: { alert: FibonacciAlert }) {
  const cs = alert.computed_state;
  if (!cs) {
    return (
      <p className="text-sm text-text-muted italic">Awaiting first computation...</p>
    );
  }

  const swingMove =
    cs.swing_high > 0 && cs.swing_low > 0
      ? (((cs.swing_high - cs.swing_low) / cs.swing_low) * 100).toFixed(1)
      : null;

  return (
    <div className="space-y-4">
      {/* Current state summary */}
      <div className="grid grid-cols-2 gap-3">
        <div>
          <p className="text-xs text-text-muted mb-0.5">Swing Range</p>
          <p className="text-sm font-medium text-text-primary">
            ${cs.swing_low.toFixed(2)} → ${cs.swing_high.toFixed(2)}
          </p>
          {swingMove && (
            <p className="text-xs text-text-muted">{swingMove}% move</p>
          )}
        </div>

        <div>
          <p className="text-xs text-text-muted mb-0.5">Current Price</p>
          <p className="text-sm font-medium text-text-primary">
            ${cs.current_price.toFixed(2)}
          </p>
          <p className="text-xs text-text-muted">
            {cs.retracement_pct.toFixed(1)}% retraced
          </p>
        </div>

        <div>
          <p className="text-xs text-text-muted mb-0.5">Trend Direction</p>
          <p className="text-sm font-medium text-text-primary capitalize">
            {cs.trend_direction.replace('_', ' ')}
          </p>
        </div>

        {cs.next_level && (
          <div>
            <p className="text-xs text-text-muted mb-0.5">Next Level</p>
            <p className="text-sm font-medium text-text-primary">
              {cs.next_level.pct}% @ ${cs.next_level.price.toFixed(2)}
            </p>
          </div>
        )}
      </div>

      {/* Level status table */}
      <div>
        <p className="text-xs font-medium text-text-muted uppercase tracking-wide mb-2">
          Fibonacci Levels
        </p>
        <div className="space-y-1">
          {Object.entries(cs.fib_levels)
            .filter(([key]) => alert.config.levels.includes(parseFloat(key)))
            .sort(([a], [b]) => parseFloat(a) - parseFloat(b))
            .map(([key, level]) => (
              <div
                key={key}
                className="flex items-center justify-between py-1 px-2 rounded bg-bg-secondary text-sm"
              >
                <span className="text-text-muted">{key}%</span>
                <span className="font-mono text-text-primary">${level.price.toFixed(2)}</span>
                <span className={`text-xs capitalize ${LEVEL_STATUS_COLORS[level.status] ?? 'text-text-muted'}`}>
                  {level.status}
                </span>
              </div>
            ))}
        </div>
      </div>
    </div>
  );
}

function MAInfoSection({ alert }: { alert: MAAlert }) {
  const cs = alert.computed_state;
  if (!cs) {
    return (
      <p className="text-sm text-text-muted italic">Awaiting first computation...</p>
    );
  }

  const aboveBelow = cs.distance_pct >= 0 ? 'above' : 'below';
  const distanceAbs = Math.abs(cs.distance_pct);

  return (
    <div className="grid grid-cols-2 gap-3">
      <div>
        <p className="text-xs text-text-muted mb-0.5">MA{cs.ma_period} Value</p>
        <p className="text-sm font-medium text-text-primary">
          ${cs.ma_value.toFixed(2)}
        </p>
      </div>

      <div>
        <p className="text-xs text-text-muted mb-0.5">Current Price</p>
        <p className="text-sm font-medium text-text-primary">
          ${cs.current_price.toFixed(2)}
        </p>
      </div>

      <div>
        <p className="text-xs text-text-muted mb-0.5">Distance</p>
        <p className="text-sm font-medium text-text-primary">
          {distanceAbs.toFixed(1)}% {aboveBelow} MA
        </p>
      </div>

      <div>
        <p className="text-xs text-text-muted mb-0.5">MA Slope</p>
        <p className="text-sm font-medium text-text-primary capitalize">
          {cs.ma_slope}
        </p>
      </div>

      <div>
        <p className="text-xs text-text-muted mb-0.5">Direction Filter</p>
        <p className="text-sm font-medium text-text-primary capitalize">
          {alert.config.direction}
        </p>
      </div>

      <div>
        <p className="text-xs text-text-muted mb-0.5">Tolerance</p>
        <p className="text-sm font-medium text-text-primary">
          ±{alert.config.tolerance_pct}%
        </p>
      </div>
    </div>
  );
}

/**
 * Alert info panel displayed below/beside the chart.
 *
 * Shows alert configuration, current computed state, and event history.
 */
export function AlertInfoPanel({ alert, events }: AlertInfoPanelProps) {
  const sortedEvents = [...events].sort(
    (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
  );

  return (
    <div className="space-y-4">
      {/* Alert state card */}
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between gap-3">
            <CardTitle className="text-base">
              {isFibAlert(alert) ? 'Fibonacci Retracement' : `MA${alert.config.ma_period} Alert`}
            </CardTitle>
            <AlertStatusBadge status={alert.status} />
          </div>
          <div className="flex flex-wrap gap-4 text-xs text-text-muted mt-1">
            <span>Created {formatDate(alert.created_at)}</span>
            {alert.last_triggered_at && (
              <span>Last triggered {formatShortDate(alert.last_triggered_at)}</span>
            )}
            {alert.is_paused && (
              <span className="text-yellow-500 font-medium">Paused</span>
            )}
          </div>
        </CardHeader>
        <CardContent className="pt-0">
          {isFibAlert(alert) && <FibonacciInfoSection alert={alert} />}
          {isMAAlert(alert) && <MAInfoSection alert={alert} />}
        </CardContent>
      </Card>

      {/* Event history card */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">Alert History</CardTitle>
        </CardHeader>
        <CardContent className="pt-0">
          {sortedEvents.length === 0 ? (
            <p className="text-sm text-text-muted italic">No events recorded yet.</p>
          ) : (
            <div className="space-y-2">
              {sortedEvents.map((event) => (
                <div
                  key={event.id}
                  className="flex items-start gap-3 py-2 border-b border-default last:border-0"
                >
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-sm font-medium text-text-primary">
                        {EVENT_TYPE_LABELS[event.event_type] ?? event.event_type}
                      </span>
                      {event.previous_status && (
                        <span className="text-xs text-text-muted">
                          {event.previous_status} → {event.new_status}
                        </span>
                      )}
                    </div>
                    <p className="text-xs text-text-muted mt-0.5">
                      ${event.price_at_event.toFixed(2)} &middot; {formatShortDate(event.created_at)}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
