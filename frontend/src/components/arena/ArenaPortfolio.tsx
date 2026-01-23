/**
 * Arena Portfolio Component
 *
 * Displays portfolio summary (cash, equity, return) and open positions table.
 */
import { Badge } from '../ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '../ui/card';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '../ui/table';
import { cn } from '../../lib/utils';
import type { Position, Simulation, Snapshot } from '../../types/arena';

interface ArenaPortfolioProps {
  /** Simulation data */
  simulation: Simulation;
  /** Open positions to display */
  positions: Position[];
  /** Current snapshot for portfolio values (or null for initial state) */
  snapshot: Snapshot | null;
}

/** Format a currency value */
const formatCurrency = (value: string | null): string => {
  if (!value) return '-';
  return `$${parseFloat(value).toLocaleString('en-US', { minimumFractionDigits: 2 })}`;
};

/**
 * Arena Portfolio Component
 *
 * Features:
 * - Summary row with Cash, Total Equity, Return
 * - Open positions table with Symbol, Shares, Entry, Stop
 * - Empty state when no positions
 */
export const ArenaPortfolio = ({
  simulation,
  positions,
  snapshot,
}: ArenaPortfolioProps) => {
  const cumulativeReturn = snapshot ? parseFloat(snapshot.cumulative_return_pct) : 0;
  const isPositiveReturn = cumulativeReturn >= 0;

  return (
    <Card>
      <CardHeader>
        <CardTitle>Portfolio</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Summary */}
        <div className="grid grid-cols-3 gap-4 text-center">
          <div>
            <p className="text-sm text-muted-foreground">Cash</p>
            <p className="text-lg font-mono font-semibold">
              {snapshot
                ? formatCurrency(snapshot.cash)
                : formatCurrency(simulation.initial_capital)}
            </p>
          </div>
          <div>
            <p className="text-sm text-muted-foreground">Total Equity</p>
            <p className="text-lg font-mono font-semibold">
              {snapshot
                ? formatCurrency(snapshot.total_equity)
                : formatCurrency(simulation.initial_capital)}
            </p>
          </div>
          <div>
            <p className="text-sm text-muted-foreground">Return</p>
            <p
              className={cn(
                'text-lg font-mono font-semibold',
                isPositiveReturn
                  ? 'text-accent-bullish'
                  : 'text-accent-bearish'
              )}
            >
              {snapshot
                ? `${isPositiveReturn ? '+' : ''}${cumulativeReturn.toFixed(2)}%`
                : '0.00%'}
            </p>
          </div>
        </div>

        {/* Open Positions */}
        {positions.length > 0 ? (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Symbol</TableHead>
                <TableHead className="text-right">Shares</TableHead>
                <TableHead className="text-right">Entry</TableHead>
                <TableHead className="text-right">Stop</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {positions.map((pos) => (
                <TableRow key={pos.id}>
                  <TableCell>
                    <Badge variant="outline">{pos.symbol}</Badge>
                  </TableCell>
                  <TableCell className="text-right font-mono">{pos.shares ?? '-'}</TableCell>
                  <TableCell className="text-right font-mono">
                    {pos.entry_price
                      ? `$${parseFloat(pos.entry_price).toFixed(2)}`
                      : '-'}
                  </TableCell>
                  <TableCell className="text-right font-mono text-accent-bearish">
                    {pos.current_stop
                      ? `$${parseFloat(pos.current_stop).toFixed(2)}`
                      : '-'}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        ) : (
          <p className="text-sm text-muted-foreground text-center py-4">
            No open positions
          </p>
        )}
      </CardContent>
    </Card>
  );
};
