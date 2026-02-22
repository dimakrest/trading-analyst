/**
 * Arena Simulation List
 *
 * Table displaying simulation history with status badges and navigation.
 */
import { useNavigate } from 'react-router-dom';
import { RefreshCw, RotateCcw } from 'lucide-react';
import { Badge } from '../ui/badge';
import { Button } from '../ui/button';
import { Card, CardContent } from '../ui/card';
import { Skeleton } from '../ui/skeleton';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '../ui/table';
import { cn } from '../../lib/utils';
import { formatTrailingStop, getStatusBadgeClass } from '../../utils/arena';
import type { Simulation } from '../../types/arena';

/** Border color classes cycled per group_id to visually cluster grouped simulations. */
const GROUP_BORDER_COLORS = [
  'border-l-blue-500',
  'border-l-orange-500',
  'border-l-green-500',
  'border-l-purple-500',
  'border-l-pink-500',
  'border-l-yellow-500',
];

/**
 * Returns a stable Tailwind border-color class for a given group_id.
 * Uses a simple polynomial hash to distribute UUIDs across the color palette.
 */
function getGroupColorClass(groupId: string): string {
  let hash = 0;
  for (let i = 0; i < groupId.length; i++) {
    hash = (hash * 31 + groupId.charCodeAt(i)) & 0xffffffff;
  }
  return GROUP_BORDER_COLORS[Math.abs(hash) % GROUP_BORDER_COLORS.length];
}

interface ArenaSimulationListProps {
  /** Array of simulations to display */
  simulations: Simulation[];
  /** Whether the list is loading */
  isLoading: boolean;
  /** Callback to refresh the list */
  onRefresh: () => void;
  /** Callback when replay is clicked */
  onReplay: (simulation: Simulation) => void;
}

/**
 * Arena Simulation List Component
 *
 * Features:
 * - Table with Name, Symbols, Date Range, Status, Return columns
 * - Status badges with colors
 * - Click row to navigate to detail
 * - Loading skeleton
 * - Empty state
 * - Refresh button
 */
export const ArenaSimulationList = ({
  simulations,
  isLoading,
  onRefresh,
  onReplay,
}: ArenaSimulationListProps) => {
  const navigate = useNavigate();

  // Loading state
  if (isLoading) {
    return (
      <div className="space-y-3">
        {[...Array(3)].map((_, i) => (
          <Skeleton key={i} className="h-12 w-full" />
        ))}
      </div>
    );
  }

  // Empty state
  if (simulations.length === 0) {
    return (
      <Card>
        <CardContent className="py-12 text-center">
          <p className="text-muted-foreground">No simulations yet</p>
          <p className="text-sm text-muted-foreground mt-1">
            Create your first simulation to get started
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      {/* Refresh Button */}
      <div className="flex justify-end">
        <Button variant="outline" size="sm" onClick={onRefresh}>
          <RefreshCw className="h-4 w-4 mr-2" />
          Refresh
        </Button>
      </div>

      {/* Simulations Table */}
      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Name</TableHead>
              <TableHead>Symbols</TableHead>
              <TableHead>Date Range</TableHead>
              <TableHead>Trailing Stop</TableHead>
              <TableHead>Min Score</TableHead>
              <TableHead>Status</TableHead>
              <TableHead className="text-right">Return</TableHead>
              <TableHead className="w-12"></TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {simulations.map((sim) => {
              const returnPct = sim.total_return_pct ? parseFloat(sim.total_return_pct) : null;
              const isPositive = returnPct !== null && returnPct >= 0;
              const groupColorClass = sim.group_id ? getGroupColorClass(sim.group_id) : null;

              return (
                <TableRow
                  key={sim.id}
                  className={cn(
                    'cursor-pointer hover:bg-muted/50',
                    groupColorClass ? `border-l-2 ${groupColorClass}` : 'border-l-2 border-l-transparent',
                  )}
                  onClick={() => navigate(`/arena/${sim.id}`)}
                >
                  <TableCell className="font-medium">
                    {sim.name || `Simulation #${sim.id}`}
                    {sim.stock_list_name && (
                      <div className="text-xs text-muted-foreground font-normal">
                        List: {sim.stock_list_name}
                      </div>
                    )}
                    {sim.portfolio_strategy && sim.portfolio_strategy !== 'none' && (
                      <div className="mt-0.5">
                        <Badge
                          variant="secondary"
                          className="text-[10px] px-1.5 py-0 font-mono"
                        >
                          {sim.portfolio_strategy}
                        </Badge>
                      </div>
                    )}
                    {sim.group_id && (
                      <div className="mt-0.5">
                        <Badge
                          variant="outline"
                          className="text-[10px] px-1.5 py-0 cursor-pointer hover:bg-accent"
                          onClick={(e) => {
                            e.stopPropagation();
                            navigate(`/arena/compare/${sim.group_id}`);
                          }}
                        >
                          Compare
                        </Badge>
                      </div>
                    )}
                  </TableCell>
                  <TableCell>
                    <span className="text-sm font-mono">
                      {sim.symbols.slice(0, 3).join(', ')}
                      {sim.symbols.length > 3 && (
                        <span className="text-muted-foreground">
                          {' '}+{sim.symbols.length - 3}
                        </span>
                      )}
                    </span>
                  </TableCell>
                  <TableCell className="text-sm font-mono">
                    {sim.start_date} - {sim.end_date}
                  </TableCell>
                  <TableCell className="text-sm font-mono">
                    {formatTrailingStop(sim.trailing_stop_pct)}
                  </TableCell>
                  <TableCell className="text-sm font-mono text-center">
                    {sim.min_buy_score ?? '-'}
                  </TableCell>
                  <TableCell>
                    <Badge className={getStatusBadgeClass(sim.status)}>
                      {sim.status}
                    </Badge>
                  </TableCell>
                  <TableCell
                    className={cn(
                      'text-right font-mono font-medium',
                      returnPct !== null
                        ? isPositive
                          ? 'text-accent-bullish'
                          : 'text-accent-bearish'
                        : 'text-muted-foreground'
                    )}
                  >
                    {returnPct !== null
                      ? `${isPositive ? '+' : ''}${returnPct.toFixed(2)}%`
                      : '-'}
                  </TableCell>
                  <TableCell className="text-right">
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={(e) => {
                        e.stopPropagation();
                        onReplay(sim);
                      }}
                      aria-label={`Replay simulation ${sim.name || `#${sim.id}`}`}
                      title="Replay with these parameters"
                    >
                      <RotateCcw className="h-4 w-4" />
                    </Button>
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </div>
    </div>
  );
};
