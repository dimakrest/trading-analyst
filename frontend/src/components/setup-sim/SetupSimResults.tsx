/**
 * Setup Simulation Results
 *
 * Displays the overall summary metrics and per-setup collapsible trade tables
 * for a completed setup simulation.
 */
import { useState } from 'react';
import { ChevronDown, ChevronRight } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { cn } from '@/lib/utils';
import { formatPnL, formatPercent, formatCurrency } from '@/utils/formatters';
import type { SetupResult, SetupSimulationResponse } from '@/types/setupSim';

interface SetupSimResultsProps {
  results: SetupSimulationResponse;
}

interface MetricCardProps {
  label: string;
  value: string;
  valueClassName?: string;
}

/** A single metric card showing a label and its value — matches ArenaResultsTable pattern */
const MetricCard = ({ label, value, valueClassName }: MetricCardProps) => (
  <div className="flex flex-col gap-1 p-3 rounded-lg bg-muted/30">
    <p className="text-xs text-muted-foreground leading-none">{label}</p>
    <p className={cn('text-lg font-mono font-semibold leading-none', valueClassName)}>
      {value}
    </p>
  </div>
);

/** Format an exit reason label for display */
const formatExitReason = (reason: string): string => {
  switch (reason) {
    case 'stop_day1':
      return 'Day 1 Stop';
    case 'trailing_stop':
      return 'Trailing Stop';
    case 'simulation_end':
      return 'End of Sim';
    default:
      return reason;
  }
};

/** Per-setup collapsible section showing symbol summary and trade table */
const SetupSection = ({ setup }: { setup: SetupResult }) => {
  const [isOpen, setIsOpen] = useState(false);
  const pnl = formatPnL(setup.pnl);

  return (
    <Collapsible open={isOpen} onOpenChange={setIsOpen}>
      <CollapsibleTrigger asChild>
        <button
          className="w-full flex items-center justify-between p-3 rounded-lg bg-muted/20 hover:bg-muted/40 transition-colors text-left"
          aria-expanded={isOpen}
          data-testid={`setup-section-${setup.symbol}`}
        >
          <div className="flex items-center gap-3">
            {isOpen ? (
              <ChevronDown className="h-4 w-4 text-muted-foreground shrink-0" />
            ) : (
              <ChevronRight className="h-4 w-4 text-muted-foreground shrink-0" />
            )}
            <span className="font-mono font-semibold">{setup.symbol}</span>
            <span className="text-xs text-muted-foreground">
              {setup.times_triggered} trade{setup.times_triggered !== 1 ? 's' : ''}
            </span>
            <span className="text-xs text-muted-foreground">
              entry {formatCurrency(parseFloat(setup.entry_price))}
            </span>
          </div>
          <span className={cn('font-mono text-sm font-semibold', pnl.className)}>
            {pnl.symbol} {pnl.text}
          </span>
        </button>
      </CollapsibleTrigger>

      <CollapsibleContent>
        {setup.trades.length === 0 ? (
          <p className="text-sm text-muted-foreground px-3 py-4">
            No trades triggered for this setup.
          </p>
        ) : (
          <div className="mt-2 rounded-lg border border-border overflow-hidden">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Entry Date</TableHead>
                  <TableHead>Entry Price</TableHead>
                  <TableHead>Exit Date</TableHead>
                  <TableHead>Exit Price</TableHead>
                  <TableHead className="text-right">Shares</TableHead>
                  <TableHead className="text-right">P&amp;L</TableHead>
                  <TableHead className="text-right">Return %</TableHead>
                  <TableHead>Exit Reason</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {setup.trades.map((trade, i) => {
                  const tradePnl = formatPnL(trade.pnl);
                  const returnPct = parseFloat(trade.return_pct);
                  const returnFormatted = formatPercent(returnPct, 2);
                  const returnClass =
                    returnPct > 0
                      ? 'text-accent-bullish'
                      : returnPct < 0
                        ? 'text-accent-bearish'
                        : 'text-muted-foreground';

                  return (
                    <TableRow key={i}>
                      <TableCell className="font-mono text-xs">{trade.entry_date}</TableCell>
                      <TableCell className="font-mono text-xs">
                        {formatCurrency(parseFloat(trade.entry_price))}
                      </TableCell>
                      <TableCell className="font-mono text-xs">{trade.exit_date}</TableCell>
                      <TableCell className="font-mono text-xs">
                        {formatCurrency(parseFloat(trade.exit_price))}
                      </TableCell>
                      <TableCell className="font-mono text-xs text-right">
                        {trade.shares}
                      </TableCell>
                      <TableCell className={cn('font-mono text-xs text-right', tradePnl.className)}>
                        {tradePnl.text}
                      </TableCell>
                      <TableCell className={cn('font-mono text-xs text-right', returnClass)}>
                        {returnFormatted}
                      </TableCell>
                      <TableCell className="text-xs">{formatExitReason(trade.exit_reason)}</TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </div>
        )}
      </CollapsibleContent>
    </Collapsible>
  );
};

/**
 * Setup Simulation Results Component
 *
 * Shows a summary metrics grid and per-setup collapsible trade tables.
 * Renders an empty state when no setups were triggered.
 */
export const SetupSimResults = ({ results }: SetupSimResultsProps) => {
  const { summary, setups } = results;

  // Empty state: no trades triggered across all setups
  if (summary.total_trades === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Results</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-muted-foreground text-sm">
            No setups were triggered during this period.
          </p>
        </CardContent>
      </Card>
    );
  }

  // Summary metric values
  const totalPnl = formatPnL(summary.total_pnl);
  const totalPnlPct = parseFloat(summary.total_pnl_pct);
  const totalPnlPctClass =
    totalPnlPct > 0
      ? 'text-accent-bullish'
      : totalPnlPct < 0
        ? 'text-accent-bearish'
        : 'text-muted-foreground';

  const winRateDisplay = summary.win_rate !== null
    ? `${parseFloat(summary.win_rate).toFixed(1)}%`
    : '—';
  const winRateNum = summary.win_rate !== null ? parseFloat(summary.win_rate) : null;
  const winRateClass =
    winRateNum !== null
      ? winRateNum >= 50
        ? 'text-accent-bullish'
        : 'text-accent-bearish'
      : 'text-muted-foreground';

  const avgGain = formatPnL(summary.avg_gain);
  const avgLoss = formatPnL(summary.avg_loss);

  return (
    <div className="space-y-6">
      {/* Summary Metrics */}
      <Card>
        <CardHeader>
          <CardTitle>Results</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
            <MetricCard
              label="Total P&L"
              value={totalPnl.text}
              valueClassName={totalPnl.className}
            />
            <MetricCard
              label="Total P&L %"
              value={formatPercent(totalPnlPct, 2)}
              valueClassName={totalPnlPctClass}
            />
            <MetricCard
              label="Win Rate"
              value={winRateDisplay}
              valueClassName={winRateClass}
            />
            <MetricCard
              label="Avg Gain"
              value={summary.avg_gain !== null ? avgGain.text : '—'}
              valueClassName={summary.avg_gain !== null ? avgGain.className : 'text-muted-foreground'}
            />
            <MetricCard
              label="Avg Loss"
              value={summary.avg_loss !== null ? avgLoss.text : '—'}
              valueClassName={summary.avg_loss !== null ? avgLoss.className : 'text-muted-foreground'}
            />
            <MetricCard
              label="Total Trades"
              value={String(summary.total_trades)}
            />
          </div>
        </CardContent>
      </Card>

      {/* Per-Setup Sections */}
      <Card>
        <CardHeader>
          <CardTitle>Per-Setup Breakdown</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          {setups.map((setup) => (
            <SetupSection key={`${setup.symbol}-${setup.start_date}-${setup.entry_price}`} setup={setup} />
          ))}
        </CardContent>
      </Card>
    </div>
  );
};
