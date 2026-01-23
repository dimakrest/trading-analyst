/**
 * Arena Results Table
 *
 * Displays simulation performance metrics including return, trades,
 * win rate, max drawdown, and final equity.
 */
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
import type { Simulation } from '../../types/arena';

interface ArenaResultsTableProps {
  /** Simulation to display results for */
  simulation: Simulation;
}

/** Format a percentage value with sign */
const formatPct = (value: string | null): string => {
  if (!value) return '-';
  const num = parseFloat(value);
  return `${num >= 0 ? '+' : ''}${num.toFixed(2)}%`;
};

/** Format a currency value */
const formatCurrency = (value: string | null): string => {
  if (!value) return '-';
  return `$${parseFloat(value).toLocaleString('en-US', { minimumFractionDigits: 2 })}`;
};

/**
 * Arena Results Table Component
 *
 * Shows a table row with agent performance metrics:
 * - Agent name
 * - Total return percentage
 * - Number of trades
 * - Win rate percentage
 * - Maximum drawdown
 * - Final equity
 */
export const ArenaResultsTable = ({ simulation }: ArenaResultsTableProps) => {
  const winRate =
    simulation.total_trades > 0
      ? ((simulation.winning_trades / simulation.total_trades) * 100).toFixed(1)
      : '0.0';

  const returnPct = simulation.total_return_pct
    ? parseFloat(simulation.total_return_pct)
    : null;

  return (
    <Card>
      <CardHeader>
        <CardTitle>Results</CardTitle>
      </CardHeader>
      <CardContent>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Agent</TableHead>
              <TableHead className="text-right">Return</TableHead>
              <TableHead className="text-right">Trades</TableHead>
              <TableHead className="text-right">Win Rate</TableHead>
              <TableHead className="text-right">Max DD</TableHead>
              <TableHead className="text-right">Final Equity</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            <TableRow>
              <TableCell className="font-medium">Live20</TableCell>
              <TableCell
                className={cn(
                  'text-right font-mono font-medium',
                  returnPct !== null
                    ? returnPct >= 0
                      ? 'text-accent-bullish'
                      : 'text-accent-bearish'
                    : ''
                )}
              >
                {formatPct(simulation.total_return_pct)}
              </TableCell>
              <TableCell className="text-right font-mono">{simulation.total_trades}</TableCell>
              <TableCell className="text-right font-mono">{winRate}%</TableCell>
              <TableCell className="text-right font-mono text-accent-bearish">
                {simulation.max_drawdown_pct
                  ? `-${parseFloat(simulation.max_drawdown_pct).toFixed(2)}%`
                  : '-'}
              </TableCell>
              <TableCell className="text-right font-mono">
                {formatCurrency(simulation.final_equity)}
              </TableCell>
            </TableRow>
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
};
