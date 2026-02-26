/**
 * Arena Results Table
 *
 * Displays simulation performance metrics as a card-based metrics grid.
 * Row 1 (key ratios): Return, Win Rate, Profit Factor, Sharpe Ratio
 * Row 2 (trade stats): Total Trades, Avg Hold Time, Avg Win, Avg Loss,
 *                      Max DD, Final Equity, Realized P&L
 */
import { Card, CardContent, CardHeader, CardTitle } from '../ui/card';
import { cn } from '../../lib/utils';
import type { Simulation } from '../../types/arena';

interface ArenaResultsTableProps {
  /** Simulation to display results for */
  simulation: Simulation;
}

/** Format a currency value as $X,XXX.XX (negative values as -$X,XXX.XX) */
const formatCurrency = (value: string | null): string => {
  if (!value) return '-';
  const num = parseFloat(value);
  const abs = Math.abs(num).toLocaleString('en-US', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
  return num < 0 ? `-$${abs}` : `$${abs}`;
};

/** Format a decimal value to 2 decimal places */
const formatDecimal = (value: string | null): string => {
  if (!value) return '-';
  return parseFloat(value).toFixed(2);
};

/** Format avg_hold_days as "X.X days" */
const formatHoldDays = (value: string | null): string => {
  if (!value) return '-';
  return `${parseFloat(value).toFixed(1)} days`;
};

/** Resolve profit_factor display value per null-display rules */
const resolveProfitFactor = (simulation: Simulation): string => {
  if (simulation.profit_factor !== null) {
    return parseFloat(simulation.profit_factor).toFixed(2);
  }
  // null profit_factor: determine context from avg_win_pnl / avg_loss_pnl
  if (simulation.avg_win_pnl !== null && simulation.avg_loss_pnl === null) {
    // All winners, no losses — infinite profit factor
    return '∞';
  }
  // No closed trades at all
  return '-';
};

interface MetricCardProps {
  label: string;
  value: string;
  valueClassName?: string;
}

/** A single metric card showing a label and its value */
const MetricCard = ({ label, value, valueClassName }: MetricCardProps) => (
  <div className="flex flex-col gap-1 p-3 rounded-lg bg-muted/30">
    <p className="text-xs text-muted-foreground leading-none">{label}</p>
    <p className={cn('text-lg font-mono font-semibold leading-none', valueClassName)}>
      {value}
    </p>
  </div>
);

/**
 * Arena Results Metrics Grid
 *
 * Replaces the old single-row table with two rows of metric cards:
 * - Row 1: Return, Win Rate, Profit Factor, Sharpe Ratio
 * - Row 2: Total Trades, Avg Hold Time, Avg Win, Avg Loss, Max DD,
 *          Final Equity, Realized P&L
 */
export const ArenaResultsTable = ({ simulation }: ArenaResultsTableProps) => {
  // --- Return ---
  const returnPct = simulation.total_return_pct !== null
    ? parseFloat(simulation.total_return_pct)
    : null;
  const returnDisplay = returnPct !== null
    ? `${returnPct >= 0 ? '+' : ''}${returnPct.toFixed(1)}%`
    : '-';
  const returnClass =
    returnPct !== null
      ? returnPct >= 0
        ? 'text-accent-bullish'
        : 'text-accent-bearish'
      : undefined;

  // --- Win Rate ---
  const winRateNum =
    simulation.total_trades > 0
      ? (simulation.winning_trades / simulation.total_trades) * 100
      : null;
  const winRateDisplay = winRateNum !== null ? `${winRateNum.toFixed(1)}%` : '0.0%';
  const effectiveWinRate = winRateNum ?? 0;
  const winRateClass = effectiveWinRate >= 50 ? 'text-accent-bullish' : 'text-accent-bearish';

  // --- Profit Factor ---
  const profitFactorDisplay = resolveProfitFactor(simulation);

  // --- Sharpe Ratio ---
  const sharpeDisplay = formatDecimal(simulation.sharpe_ratio);

  // --- Max Drawdown ---
  const maxDdDisplay = simulation.max_drawdown_pct
    ? `-${parseFloat(simulation.max_drawdown_pct).toFixed(1)}%`
    : '-';

  // --- Realized P&L ---
  const realizedPnl = simulation.total_realized_pnl !== null
    ? parseFloat(simulation.total_realized_pnl)
    : null;
  const realizedPnlDisplay = formatCurrency(simulation.total_realized_pnl);
  const realizedPnlClass =
    realizedPnl !== null
      ? realizedPnl >= 0
        ? 'text-accent-bullish'
        : 'text-accent-bearish'
      : undefined;

  return (
    <Card>
      <CardHeader>
        <CardTitle>Results</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {/* Row 1: Key ratios */}
        <div className="grid grid-cols-4 gap-3">
          <MetricCard
            label="Return"
            value={returnDisplay}
            valueClassName={returnClass}
          />
          <MetricCard
            label="Win Rate"
            value={winRateDisplay}
            valueClassName={winRateClass}
          />
          <MetricCard
            label="Profit Factor"
            value={profitFactorDisplay}
          />
          <MetricCard
            label="Sharpe Ratio"
            value={sharpeDisplay}
          />
        </div>

        {/* Row 2: Trade statistics */}
        <div className="grid grid-cols-4 lg:grid-cols-7 gap-3">
          <MetricCard
            label="Total Trades"
            value={String(simulation.total_trades)}
          />
          <MetricCard
            label="Avg Hold Time"
            value={formatHoldDays(simulation.avg_hold_days)}
          />
          <MetricCard
            label="Avg Win"
            value={formatCurrency(simulation.avg_win_pnl)}
            valueClassName={simulation.avg_win_pnl !== null ? 'text-accent-bullish' : undefined}
          />
          <MetricCard
            label="Avg Loss"
            value={formatCurrency(simulation.avg_loss_pnl)}
            valueClassName={simulation.avg_loss_pnl !== null ? 'text-accent-bearish' : undefined}
          />
          <MetricCard
            label="Max DD"
            value={maxDdDisplay}
            valueClassName="text-accent-bearish"
          />
          <MetricCard
            label="Final Equity"
            value={formatCurrency(simulation.final_equity)}
          />
          <MetricCard
            label="Realized P&L"
            value={realizedPnlDisplay}
            valueClassName={realizedPnlClass}
          />
        </div>
      </CardContent>
    </Card>
  );
};
