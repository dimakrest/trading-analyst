/**
 * ArenaComparisonTable
 *
 * Sortable summary table with one row per simulation in a comparison group.
 * Highlights the best and worst value in each metric column.
 * In-progress simulations appear at the bottom with metric columns showing "—".
 * Click a row to navigate to the individual simulation detail page.
 */
import { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ChevronUp, ChevronDown } from 'lucide-react';
import { Badge } from '../ui/badge';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '../ui/table';
import { getStatusBadgeClass } from '../../utils/arena';
import type { Simulation } from '../../types/arena';

interface ArenaComparisonTableProps {
  simulations: Simulation[];
}

type SortField =
  | 'total_return_pct'
  | 'max_drawdown_pct'
  | 'sharpe_ratio'
  | 'profit_factor'
  | 'win_rate'
  | 'total_trades'
  | 'avg_hold_days'
  | 'avg_win_pnl'
  | 'avg_loss_pnl';

type SortDirection = 'asc' | 'desc';

const TERMINAL_STATUSES = new Set(['completed', 'cancelled', 'failed']);

/** Extract portfolio_strategy from agent_config JSON, falling back to the top-level field. */
const getStrategy = (sim: Simulation): string =>
  sim.portfolio_strategy ?? '—';

/** Compute win rate as a number (0–100) or null when total_trades === 0. */
const computeWinRate = (sim: Simulation): number | null => {
  if (sim.total_trades === 0) return null;
  return (sim.winning_trades / sim.total_trades) * 100;
};

/** Parse a nullable string metric to number or null. */
const parseMetric = (v: string | null): number | null =>
  v !== null ? parseFloat(v) : null;

/** Format a number to a fixed decimal string, or "—" when null. */
const fmt = (v: number | null, decimals: number): string =>
  v !== null ? v.toFixed(decimals) : '—';

/** Format return percentage with sign. */
const fmtReturn = (v: number | null): string => {
  if (v === null) return '—';
  return v >= 0 ? `+${v.toFixed(1)}%` : `${v.toFixed(1)}%`;
};

/**
 * Get the metric value used for sorting / best-worst comparison.
 * Returns null for non-completed simulations (they sort last).
 */
const getMetricValue = (sim: Simulation, field: SortField): number | null => {
  if (sim.status !== 'completed') return null;

  switch (field) {
    case 'win_rate':
      return computeWinRate(sim);
    case 'total_return_pct':
      return parseMetric(sim.total_return_pct);
    case 'max_drawdown_pct':
      return parseMetric(sim.max_drawdown_pct);
    case 'sharpe_ratio':
      return parseMetric(sim.sharpe_ratio);
    case 'profit_factor':
      return parseMetric(sim.profit_factor);
    case 'total_trades':
      return sim.total_trades;
    case 'avg_hold_days':
      return parseMetric(sim.avg_hold_days);
    case 'avg_win_pnl':
      return parseMetric(sim.avg_win_pnl);
    case 'avg_loss_pnl':
      return parseMetric(sim.avg_loss_pnl);
  }
};

/**
 * For each sortable field, define whether a higher value is "better" (true)
 * or lower is "better" (false). Used to determine best/worst highlighting.
 */
const HIGHER_IS_BETTER: Record<SortField, boolean> = {
  total_return_pct: true,
  max_drawdown_pct: false, // less drawdown is better (values are negative)
  sharpe_ratio: true,
  profit_factor: true,
  win_rate: true,
  total_trades: true,
  avg_hold_days: false,
  avg_win_pnl: true,
  avg_loss_pnl: true, // avg_loss is negative; less negative = better (closer to 0)
};

interface ColumnDef {
  field: SortField;
  label: string;
  render: (sim: Simulation) => string;
}

const COLUMNS: ColumnDef[] = [
  {
    field: 'total_return_pct',
    label: 'Return',
    render: (sim) =>
      sim.status === 'completed' ? fmtReturn(parseMetric(sim.total_return_pct)) : '—',
  },
  {
    field: 'max_drawdown_pct',
    label: 'Max DD',
    render: (sim) => {
      if (sim.status !== 'completed') return '—';
      const v = parseMetric(sim.max_drawdown_pct);
      return v !== null ? `-${Math.abs(v).toFixed(1)}%` : '—';
    },
  },
  {
    field: 'sharpe_ratio',
    label: 'Sharpe',
    render: (sim) =>
      sim.status === 'completed' ? fmt(parseMetric(sim.sharpe_ratio), 2) : '—',
  },
  {
    field: 'profit_factor',
    label: 'Profit Factor',
    render: (sim) =>
      sim.status === 'completed' ? fmt(parseMetric(sim.profit_factor), 2) : '—',
  },
  {
    field: 'win_rate',
    label: 'Win Rate',
    render: (sim) => {
      if (sim.status !== 'completed') return '—';
      const v = computeWinRate(sim);
      return v !== null ? `${v.toFixed(1)}%` : '—';
    },
  },
  {
    field: 'total_trades',
    label: 'Total Trades',
    render: (sim) => (sim.status === 'completed' ? String(sim.total_trades) : '—'),
  },
  {
    field: 'avg_hold_days',
    label: 'Avg Hold',
    render: (sim) => {
      if (sim.status !== 'completed') return '—';
      const v = parseMetric(sim.avg_hold_days);
      return v !== null ? `${v.toFixed(1)} days` : '—';
    },
  },
  {
    field: 'avg_win_pnl',
    label: 'Avg Win',
    render: (sim) => {
      if (sim.status !== 'completed') return '—';
      const v = parseMetric(sim.avg_win_pnl);
      return v !== null ? `$${v.toFixed(2)}` : '—';
    },
  },
  {
    field: 'avg_loss_pnl',
    label: 'Avg Loss',
    render: (sim) => {
      if (sim.status !== 'completed') return '—';
      const v = parseMetric(sim.avg_loss_pnl);
      return v !== null ? `$${v.toFixed(2)}` : '—';
    },
  },
];

export const ArenaComparisonTable = ({ simulations }: ArenaComparisonTableProps) => {
  const navigate = useNavigate();
  const [sortField, setSortField] = useState<SortField>('total_return_pct');
  const [sortDirection, setSortDirection] = useState<SortDirection>('desc');

  const handleHeaderClick = (field: SortField) => {
    if (field === sortField) {
      setSortDirection((prev) => (prev === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortField(field);
      setSortDirection('desc');
    }
  };

  const sortedSimulations = useMemo(() => {
    return [...simulations].sort((a, b) => {
      const av = getMetricValue(a, sortField);
      const bv = getMetricValue(b, sortField);

      // Non-completed sims sort last regardless of direction
      const aIsTerminal = TERMINAL_STATUSES.has(a.status);
      const bIsTerminal = TERMINAL_STATUSES.has(b.status);
      if (!aIsTerminal && bIsTerminal) return 1;
      if (aIsTerminal && !bIsTerminal) return -1;

      // Nulls sort last within their group
      if (av === null && bv === null) return 0;
      if (av === null) return 1;
      if (bv === null) return -1;

      const diff = av - bv;
      return sortDirection === 'desc' ? -diff : diff;
    });
  }, [simulations, sortField, sortDirection]);

  // Compute per-column min/max over COMPLETED simulations only
  const columnExtremes = useMemo(() => {
    const completed = simulations.filter((s) => s.status === 'completed');

    return Object.fromEntries(
      COLUMNS.map((col) => {
        const values = completed
          .map((s) => getMetricValue(s, col.field))
          .filter((v): v is number => v !== null);

        const extremes =
          values.length === 0
            ? { min: null, max: null }
            : { min: Math.min(...values), max: Math.max(...values) };

        return [col.field, extremes];
      }),
    ) as Record<SortField, { min: number | null; max: number | null }>;
  }, [simulations]);

  /**
   * Get the CSS class for a metric cell value.
   * Returns 'text-accent-bullish' for the best value, 'text-accent-bearish' for worst.
   * Returns '' when there is no distinction (all equal, null, or non-completed sim).
   */
  const getCellClass = (sim: Simulation, field: SortField): string => {
    if (sim.status !== 'completed') return '';
    const v = getMetricValue(sim, field);
    if (v === null) return '';

    const { min, max } = columnExtremes[field];
    if (min === null || max === null) return '';
    // No highlight when all values are the same
    if (min === max) return '';

    const higherIsBetter = HIGHER_IS_BETTER[field];
    const isBest = higherIsBetter ? v === max : v === min;
    const isWorst = higherIsBetter ? v === min : v === max;

    if (isBest) return 'text-accent-bullish';
    if (isWorst) return 'text-accent-bearish';
    return '';
  };

  return (
    <div className="rounded-md border border-border overflow-hidden">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="w-[140px]">Strategy</TableHead>
            {COLUMNS.map((col) => (
              <TableHead
                key={col.field}
                className="cursor-pointer select-none whitespace-nowrap"
                onClick={() => handleHeaderClick(col.field)}
                aria-sort={
                  sortField === col.field
                    ? sortDirection === 'asc'
                      ? 'ascending'
                      : 'descending'
                    : 'none'
                }
              >
                <span className="flex items-center gap-1">
                  {col.label}
                  {sortField === col.field ? (
                    sortDirection === 'desc' ? (
                      <ChevronDown className="h-3 w-3" aria-hidden="true" />
                    ) : (
                      <ChevronUp className="h-3 w-3" aria-hidden="true" />
                    )
                  ) : null}
                </span>
              </TableHead>
            ))}
          </TableRow>
        </TableHeader>
        <TableBody>
          {sortedSimulations.map((sim) => {
            const strategy = getStrategy(sim);
            const isCompleted = sim.status === 'completed';

            return (
              <TableRow
                key={sim.id}
                className="cursor-pointer hover:bg-muted/50"
                onClick={() => navigate(`/arena/${sim.id}`)}
                role="row"
              >
                <TableCell>
                  <div className="flex flex-col gap-1">
                    <Badge variant="secondary" className="w-fit text-xs">
                      {strategy}
                    </Badge>
                    {!isCompleted && (
                      <Badge
                        className={`w-fit text-[10px] px-1.5 py-0 ${getStatusBadgeClass(sim.status)}`}
                      >
                        {sim.status}
                      </Badge>
                    )}
                  </div>
                </TableCell>
                {COLUMNS.map((col) => (
                  <TableCell
                    key={col.field}
                    className={`font-mono text-xs ${getCellClass(sim, col.field)}`}
                  >
                    {col.render(sim)}
                  </TableCell>
                ))}
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
    </div>
  );
};
