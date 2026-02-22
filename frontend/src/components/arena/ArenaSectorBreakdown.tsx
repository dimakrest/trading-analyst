/**
 * Arena Sector Breakdown Component
 *
 * Displays sector-level analytics computed client-side from positions data:
 * - Sector Allocation: groups open positions by sector, showing cost basis distribution
 * - Sector Performance: groups closed positions by sector, showing win rate and P&L
 *
 * Positions with null sector are grouped as "Unknown" and sorted last in both tables.
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
import { formatCurrency } from '../../utils/formatters';
import type { Position, Snapshot } from '../../types/arena';

interface ArenaSectorBreakdownProps {
  positions: Position[];
  snapshot: Snapshot | null;
}

/** Resolve null sector to the display label "Unknown" */
const resolveSector = (sector: string | null): string => sector ?? 'Unknown';

/**
 * Sort sector row keys so that "Unknown" always appears last, and all other
 * sectors are sorted by a numeric value (descending) provided by the caller.
 */
const sortSectorKeys = (
  keys: string[],
  valueMap: Record<string, number>,
): string[] => {
  return keys.slice().sort((a, b) => {
    if (a === 'Unknown' && b !== 'Unknown') return 1;
    if (b === 'Unknown' && a !== 'Unknown') return -1;
    return valueMap[b] - valueMap[a]; // descending by value
  });
};

// ---------------------------------------------------------------------------
// Sector Allocation (open positions)
// ---------------------------------------------------------------------------

interface AllocationRow {
  sector: string;
  count: number;
  costBasis: number;
  pct: number;
}

const SectorAllocationTable = ({ rows }: { rows: AllocationRow[] }) => (
  <Table>
    <TableHeader>
      <TableRow>
        <TableHead>Sector</TableHead>
        <TableHead className="text-right">Positions</TableHead>
        <TableHead className="text-right">Cost Basis</TableHead>
        <TableHead className="text-right">% of Total Cost Basis</TableHead>
      </TableRow>
    </TableHeader>
    <TableBody>
      {rows.map((row) => (
        <TableRow key={row.sector}>
          <TableCell
            className={cn(
              'font-medium',
              row.sector === 'Unknown' && 'text-muted-foreground italic',
            )}
          >
            {row.sector}
          </TableCell>
          <TableCell className="text-right font-mono">{row.count}</TableCell>
          <TableCell className="text-right font-mono">
            {formatCurrency(row.costBasis)}
          </TableCell>
          <TableCell className="text-right font-mono">
            {row.pct.toFixed(1)}%
          </TableCell>
        </TableRow>
      ))}
    </TableBody>
  </Table>
);

// ---------------------------------------------------------------------------
// Sector Performance (closed positions)
// ---------------------------------------------------------------------------

interface PerformanceRow {
  sector: string;
  tradeCount: number;
  winRate: number;
  totalPnl: number;
}

const SectorPerformanceTable = ({ rows }: { rows: PerformanceRow[] }) => (
  <Table>
    <TableHeader>
      <TableRow>
        <TableHead>Sector</TableHead>
        <TableHead className="text-right">Trades</TableHead>
        <TableHead className="text-right">Win Rate</TableHead>
        <TableHead className="text-right">Total P&L</TableHead>
      </TableRow>
    </TableHeader>
    <TableBody>
      {rows.map((row) => (
        <TableRow key={row.sector}>
          <TableCell
            className={cn(
              'font-medium',
              row.sector === 'Unknown' && 'text-muted-foreground italic',
            )}
          >
            {row.sector}
          </TableCell>
          <TableCell className="text-right font-mono">{row.tradeCount}</TableCell>
          <TableCell className="text-right font-mono">
            {(row.winRate * 100).toFixed(1)}%
          </TableCell>
          <TableCell
            className={cn(
              'text-right font-mono font-medium',
              row.totalPnl >= 0 ? 'text-accent-bullish' : 'text-accent-bearish',
            )}
          >
            {formatCurrency(row.totalPnl)}
          </TableCell>
        </TableRow>
      ))}
    </TableBody>
  </Table>
);

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

/**
 * Arena Sector Breakdown
 *
 * Two sections — each is conditionally rendered:
 *  - Sector Allocation: shown when there are open positions (realized_pnl === null)
 *  - Sector Performance: shown when there are closed positions (realized_pnl !== null)
 *
 * Returns null when there are no positions at all.
 */
export const ArenaSectorBreakdown = ({
  positions,
}: ArenaSectorBreakdownProps) => {
  if (positions.length === 0) return null;

  // Open positions: used for Sector Allocation
  const openPositions = positions.filter((p) => p.realized_pnl === null);

  // Closed positions: used for Sector Performance
  const closedPositions = positions.filter((p) => p.realized_pnl !== null);

  // -------------------------------------------------------------------------
  // Build Sector Allocation rows
  // -------------------------------------------------------------------------
  const allocationRows: AllocationRow[] = (() => {
    if (openPositions.length === 0) return [];

    // Group by sector, accumulate cost basis
    const grouped: Record<string, { count: number; costBasis: number }> = {};
    for (const pos of openPositions) {
      const sector = resolveSector(pos.sector);
      if (!grouped[sector]) {
        grouped[sector] = { count: 0, costBasis: 0 };
      }
      grouped[sector].count += 1;
      if (pos.entry_price !== null && pos.shares !== null) {
        grouped[sector].costBasis += parseFloat(pos.entry_price) * pos.shares;
      }
    }

    const totalCostBasis = Object.values(grouped).reduce(
      (sum, g) => sum + g.costBasis,
      0,
    );

    const valueMap: Record<string, number> = {};
    for (const [sector, g] of Object.entries(grouped)) {
      valueMap[sector] = g.costBasis;
    }

    return sortSectorKeys(Object.keys(grouped), valueMap).map((sector) => ({
      sector,
      count: grouped[sector].count,
      costBasis: grouped[sector].costBasis,
      pct: totalCostBasis > 0
        ? (grouped[sector].costBasis / totalCostBasis) * 100
        : 0,
    }));
  })();

  // -------------------------------------------------------------------------
  // Build Sector Performance rows
  // -------------------------------------------------------------------------
  const performanceRows: PerformanceRow[] = (() => {
    if (closedPositions.length === 0) return [];

    // Group by sector
    const grouped: Record<string, { trades: Position[] }> = {};
    for (const pos of closedPositions) {
      const sector = resolveSector(pos.sector);
      if (!grouped[sector]) {
        grouped[sector] = { trades: [] };
      }
      grouped[sector].trades.push(pos);
    }

    const valueMap: Record<string, number> = {};
    for (const [sector, g] of Object.entries(grouped)) {
      const totalPnl = g.trades.reduce(
        (sum, p) => sum + parseFloat(p.realized_pnl!),
        0,
      );
      valueMap[sector] = totalPnl;
    }

    return sortSectorKeys(Object.keys(grouped), valueMap).map((sector) => {
      const trades = grouped[sector].trades;
      const tradeCount = trades.length;
      const winCount = trades.filter(
        (p) => p.realized_pnl !== null && parseFloat(p.realized_pnl) > 0,
      ).length;
      const winRate = tradeCount > 0 ? winCount / tradeCount : 0;
      const totalPnl = valueMap[sector];

      return { sector, tradeCount, winRate, totalPnl };
    });
  })();

  const hasAllocation = allocationRows.length > 0;
  const hasPerformance = performanceRows.length > 0;

  return (
    <Card>
      <CardHeader>
        <CardTitle>Sector Breakdown</CardTitle>
      </CardHeader>
      <CardContent className="space-y-6">

        {/* Sector Allocation — open positions */}
        {hasAllocation && (
          <div>
            <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide mb-3">
              Cost Basis Allocation
            </h3>
            <SectorAllocationTable rows={allocationRows} />
          </div>
        )}

        {/* Sector Performance — closed positions */}
        {hasPerformance && (
          <div>
            <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide mb-3">
              Sector Performance
            </h3>
            <SectorPerformanceTable rows={performanceRows} />
          </div>
        )}

      </CardContent>
    </Card>
  );
};
