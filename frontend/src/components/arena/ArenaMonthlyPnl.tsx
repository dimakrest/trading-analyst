/**
 * ArenaMonthlyPnl
 *
 * Monthly P&L heatmap computed client-side from daily snapshots.
 * Groups snapshots by YYYY-MM, sums daily_pnl per group, then renders one row
 * per month with a colored intensity bar showing relative magnitude.
 *
 * Renders nothing when snapshots.length < 20 (less than one full trading month).
 */
import { Card, CardContent, CardHeader, CardTitle } from '../ui/card';
import { formatCurrency } from '../../utils/formatters';
import type { Snapshot } from '../../types/arena';

interface ArenaMonthlyPnlProps {
  snapshots: Snapshot[];
}

/**
 * Parse "YYYY-MM-DD" → "YYYY-MM" bucket key.
 * Slices the first 7 characters — no Date parsing required, avoids timezone
 * issues that can shift dates by one day when converting UTC strings to local
 * Date objects.
 */
const toMonthKey = (dateStr: string): string => dateStr.slice(0, 7);

/**
 * Format a "YYYY-MM" key to a human-readable label like "Mar 2024".
 */
const formatMonthLabel = (key: string): string => {
  const [year, month] = key.split('-');
  const date = new Date(Number(year), Number(month) - 1, 1);
  return date.toLocaleString('en-US', { month: 'short', year: 'numeric' });
};

interface MonthlyBucket {
  key: string;    // "YYYY-MM"
  label: string;  // "Mar 2024"
  pnl: number;    // sum of daily_pnl for that month
}

/**
 * Group snapshots by month and sum daily_pnl values.
 * Returns buckets sorted chronologically by key.
 */
const buildMonthlyBuckets = (snapshots: Snapshot[]): MonthlyBucket[] => {
  const totals = new Map<string, number>();

  for (const snapshot of snapshots) {
    const key = toMonthKey(snapshot.snapshot_date);
    const pnl = parseFloat(snapshot.daily_pnl);
    totals.set(key, (totals.get(key) ?? 0) + pnl);
  }

  return Array.from(totals.entries())
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([key, pnl]) => ({
      key,
      label: formatMonthLabel(key),
      pnl,
    }));
};

/**
 * Monthly P&L heatmap for a completed Arena simulation.
 *
 * Color scheme:
 * - Positive months: green (#00d26a / --accent-bullish) with opacity scaled to magnitude
 * - Negative months: red (#ff4757 / --accent-bearish) with opacity scaled to magnitude
 *
 * Inline `style` is used for the bar background because Tailwind cannot generate
 * arbitrary opacity values at runtime, and `rgba(var(--css-variable), opacity)` is
 * invalid (CSS variables resolve to hex strings, not channel values).
 */
export const ArenaMonthlyPnl = ({ snapshots }: ArenaMonthlyPnlProps) => {
  if (snapshots.length < 20) return null;

  const monthlyPnl = buildMonthlyBuckets(snapshots);

  if (monthlyPnl.length === 0) return null;

  const maxAbs = Math.max(...monthlyPnl.map((m) => Math.abs(m.pnl)));

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-sm font-semibold">Monthly P&amp;L</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-2" data-testid="monthly-pnl-rows">
          {monthlyPnl.map(({ key, label, pnl }) => {
            const opacity = maxAbs > 0 ? Math.min(Math.abs(pnl) / maxAbs, 1) : 1;
            // --accent-bullish = #00d26a → rgb(0, 210, 106)
            // --accent-bearish = #ff4757 → rgb(255, 71, 87)
            const barColor =
              pnl >= 0
                ? `rgba(0, 210, 106, ${opacity})`
                : `rgba(255, 71, 87, ${opacity})`;

            const barWidthPct = maxAbs > 0 ? (Math.abs(pnl) / maxAbs) * 100 : 100;

            return (
              <div
                key={key}
                className="flex items-center gap-3"
                data-testid={`monthly-pnl-row-${key}`}
              >
                {/* Month label */}
                <span className="w-20 shrink-0 text-xs text-muted-foreground font-mono">
                  {label}
                </span>

                {/* P&L value */}
                <span
                  className={`w-24 shrink-0 text-xs font-mono text-right ${
                    pnl >= 0 ? 'text-accent-bullish' : 'text-accent-bearish'
                  }`}
                  data-testid={`monthly-pnl-value-${key}`}
                >
                  {formatCurrency(pnl)}
                </span>

                {/* Intensity bar */}
                <div className="flex-1 h-4 rounded overflow-hidden bg-muted/20">
                  <div
                    className="h-full rounded"
                    style={{
                      width: `${barWidthPct}%`,
                      backgroundColor: barColor,
                    }}
                    data-testid={`monthly-pnl-bar-${key}`}
                    aria-hidden="true"
                  />
                </div>
              </div>
            );
          })}
        </div>
      </CardContent>
    </Card>
  );
};
