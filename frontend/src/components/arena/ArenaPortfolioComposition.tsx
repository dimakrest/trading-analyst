/**
 * Arena Portfolio Composition Component
 *
 * Displays portfolio composition analytics computed client-side from positions data:
 * - Biggest Winners (top 5 closed positions by return_pct)
 * - Biggest Losers (bottom 5 closed positions by return_pct)
 * - Realized vs Unrealized P&L
 * - Position Concentration (open positions as % of total equity)
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
import { Badge } from '../ui/badge';
import { cn } from '../../lib/utils';
import { formatCurrency } from '../../utils/formatters';
import type { Position, Simulation, Snapshot } from '../../types/arena';

interface ArenaPortfolioCompositionProps {
  positions: Position[];
  /** Latest snapshot (snapshots.at(-1)) — NOT the day-selector's currentSnapshot */
  snapshot: Snapshot | null;
  simulation: Simulation;
}

/** Format return_pct from a string | null field */
const formatReturnPct = (value: string | null): string => {
  if (value === null) return '-';
  const num = parseFloat(value);
  return `${num >= 0 ? '+' : ''}${num.toFixed(2)}%`;
};

/** Format a date string as YYYY-MM-DD (already in that format from the API) */
const formatDate = (value: string | null): string => value ?? '-';

/**
 * Comparator for sorting closed positions by return_pct.
 * Positions with null return_pct always sort to the bottom.
 */
const compareByReturnPct = (
  a: Position,
  b: Position,
  direction: 'asc' | 'desc',
): number => {
  if (a.return_pct === null && b.return_pct === null) return 0;
  if (a.return_pct === null) return 1;  // null sinks to bottom
  if (b.return_pct === null) return -1; // null sinks to bottom
  const diff = parseFloat(a.return_pct) - parseFloat(b.return_pct);
  return direction === 'desc' ? -diff : diff;
};

/** Table showing a list of closed positions (winners or losers) */
const PositionRankTable = ({
  positions,
  colorClass,
}: {
  positions: Position[];
  colorClass: string;
}) => (
  <Table>
    <TableHeader>
      <TableRow>
        <TableHead>Symbol</TableHead>
        <TableHead className="text-right">Return</TableHead>
        <TableHead className="text-right">Realized P&L</TableHead>
        <TableHead className="text-right">Entry</TableHead>
        <TableHead className="text-right">Exit</TableHead>
      </TableRow>
    </TableHeader>
    <TableBody>
      {positions.map((pos) => (
        <TableRow key={pos.id}>
          <TableCell>
            <Badge variant="outline">{pos.symbol}</Badge>
          </TableCell>
          <TableCell className={cn('text-right font-mono font-medium', colorClass)}>
            {formatReturnPct(pos.return_pct)}
          </TableCell>
          <TableCell className="text-right font-mono">
            {pos.realized_pnl !== null
              ? formatCurrency(parseFloat(pos.realized_pnl))
              : '-'}
          </TableCell>
          <TableCell className="text-right font-mono text-muted-foreground">
            {formatDate(pos.entry_date)}
          </TableCell>
          <TableCell className="text-right font-mono text-muted-foreground">
            {formatDate(pos.exit_date)}
          </TableCell>
        </TableRow>
      ))}
    </TableBody>
  </Table>
);

/**
 * Arena Portfolio Composition
 *
 * Features:
 * - Biggest Winners / Biggest Losers side-by-side (or stacked on small screens)
 * - Realized vs Unrealized P&L (mode depends on simulation.status)
 * - Position Concentration table with horizontal bar visualization
 */
export const ArenaPortfolioComposition = ({
  positions,
  snapshot,
  simulation,
}: ArenaPortfolioCompositionProps) => {
  // --- Closed positions ---
  const closedPositions = positions.filter((p) => p.realized_pnl !== null);

  // Top 5 winners: descending by return_pct (null at bottom)
  const winners = closedPositions
    .slice()
    .sort((a, b) => compareByReturnPct(a, b, 'desc'))
    .slice(0, 5);

  // Bottom 5 losers: ascending by return_pct (null at bottom)
  const losers = closedPositions
    .slice()
    .sort((a, b) => compareByReturnPct(a, b, 'asc'))
    .slice(0, 5);

  // Only show losers that have a negative return (or null return); filter to avoid
  // duplicating winners when the entire portfolio is profitable
  const trueLosers = losers.filter(
    (p) => p.return_pct === null || parseFloat(p.return_pct) < 0,
  );

  const hasClosedPositions = closedPositions.length > 0;

  // --- Open positions ---
  const openPositions = positions.filter((p) => p.realized_pnl === null);
  const hasOpenPositions = openPositions.length > 0;

  // --- Realized P&L ---
  const isCompleted = simulation.status === 'completed';

  const computedRealizedPnl = closedPositions.reduce(
    (sum, p) => sum + parseFloat(p.realized_pnl!),
    0,
  );

  // For completed simulations use the persisted total_realized_pnl; fall back to
  // client-side computation when total_realized_pnl is null (e.g. pre-migration rows).
  const realizedPnl = isCompleted
    ? simulation.total_realized_pnl !== null
      ? parseFloat(simulation.total_realized_pnl)
      : computedRealizedPnl
    : computedRealizedPnl;

  // --- Unrealized estimate (in-progress only) ---
  // Market value gain ≈ snapshot positions_value − sum of open position cost bases
  let unrealizedEstimate: number | null = null;
  if (!isCompleted && snapshot !== null && hasOpenPositions) {
    const openCostBasis = openPositions.reduce((sum, p) => {
      if (p.entry_price === null || p.shares === null) return sum;
      return sum + parseFloat(p.entry_price) * p.shares;
    }, 0);
    unrealizedEstimate = parseFloat(snapshot.positions_value) - openCostBasis;
  }

  // --- Position concentration ---
  // Only meaningful when there's a snapshot with non-zero total_equity
  const totalEquity = snapshot ? parseFloat(snapshot.total_equity) : 0;
  const concentrationRows = hasOpenPositions && snapshot && totalEquity > 0
    ? openPositions
        .filter((p) => p.entry_price !== null && p.shares !== null)
        .map((p) => {
          const costBasis = parseFloat(p.entry_price!) * p.shares!;
          const pct = (costBasis / totalEquity) * 100;
          return { position: p, costBasis, pct };
        })
        .sort((a, b) => b.pct - a.pct) // largest concentration first
    : [];

  const showConcentration = concentrationRows.length > 0;

  return (
    <Card>
      <CardHeader>
        <CardTitle>Portfolio Composition</CardTitle>
      </CardHeader>
      <CardContent className="space-y-6">

        {/* Winners & Losers */}
        {hasClosedPositions ? (
          <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
            {/* Biggest Winners */}
            <div>
              <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide mb-3">
                Biggest Winners
              </h3>
              <PositionRankTable
                positions={winners}
                colorClass="text-accent-bullish"
              />
            </div>

            {/* Biggest Losers */}
            <div>
              <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide mb-3">
                Biggest Losers
              </h3>
              {trueLosers.length > 0 ? (
                <PositionRankTable
                  positions={trueLosers}
                  colorClass="text-accent-bearish"
                />
              ) : (
                <p className="text-sm text-muted-foreground py-4">
                  No losing trades
                </p>
              )}
            </div>
          </div>
        ) : null}

        {/* Realized vs Unrealized P&L */}
        {hasClosedPositions || (!isCompleted && hasOpenPositions && snapshot) ? (
          <div>
            <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide mb-3">
              P&L Summary
            </h3>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              {/* Realized P&L */}
              {hasClosedPositions && (
                <div className="p-4 rounded-lg bg-muted/30">
                  <p className="text-xs text-muted-foreground mb-1">Realized P&L</p>
                  <p
                    className={cn(
                      'text-2xl font-mono font-semibold',
                      realizedPnl >= 0 ? 'text-accent-bullish' : 'text-accent-bearish',
                    )}
                  >
                    {formatCurrency(realizedPnl)}
                  </p>
                </div>
              )}

              {/* Unrealized estimate (in-progress only) */}
              {!isCompleted && unrealizedEstimate !== null && (
                <div className="p-4 rounded-lg bg-muted/30">
                  <p className="text-xs text-muted-foreground mb-1">
                    Market Value Gain (est.)
                  </p>
                  <p
                    className={cn(
                      'text-2xl font-mono font-semibold',
                      unrealizedEstimate >= 0
                        ? 'text-accent-bullish'
                        : 'text-accent-bearish',
                    )}
                  >
                    {formatCurrency(unrealizedEstimate)}
                  </p>
                  <p className="text-xs text-muted-foreground mt-1 leading-relaxed">
                    snapshot market value minus open position cost basis — approximate
                  </p>
                </div>
              )}
            </div>
          </div>
        ) : null}

        {/* Position Concentration */}
        {showConcentration && (
          <div>
            <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide mb-3">
              Position Concentration
            </h3>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Symbol</TableHead>
                  <TableHead className="text-right">Cost Basis</TableHead>
                  <TableHead className="text-right">% of Portfolio</TableHead>
                  <TableHead className="w-32">Allocation</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {concentrationRows.map(({ position, costBasis, pct }) => (
                  <TableRow key={position.id}>
                    <TableCell>
                      <Badge variant="outline">{position.symbol}</Badge>
                    </TableCell>
                    <TableCell className="text-right font-mono">
                      {formatCurrency(costBasis)}
                    </TableCell>
                    <TableCell className="text-right font-mono">
                      {pct.toFixed(1)}%
                    </TableCell>
                    <TableCell>
                      <div
                        className="h-2 rounded-full bg-primary/60"
                        style={{ width: `${Math.min(pct, 100)}%` }}
                        role="meter"
                        aria-valuenow={Math.round(pct)}
                        aria-valuemin={0}
                        aria-valuemax={100}
                        aria-label={`${position.symbol} concentration: ${pct.toFixed(1)}%`}
                      />
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}

        {/* Empty state: no closed or open positions to show */}
        {!hasClosedPositions && !showConcentration && (
          <p className="text-sm text-muted-foreground text-center py-4">
            No position data available
          </p>
        )}
      </CardContent>
    </Card>
  );
};
