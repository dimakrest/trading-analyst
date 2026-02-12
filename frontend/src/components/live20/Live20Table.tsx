import { useMemo, useState, Fragment } from 'react';
import {
  useReactTable,
  getCoreRowModel,
  getSortedRowModel,
  getExpandedRowModel,
  flexRender,
  type ColumnDef,
  type SortingState,
  type ExpandedState,
} from '@tanstack/react-table';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '../ui/table';
import { Badge } from '../ui/badge';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '../ui/tooltip';
import { CheckCircle, XCircle, MinusCircle, ArrowUpDown, TrendingUp, TrendingDown, Minus, ChevronDown, ChevronRight } from 'lucide-react';
import type { Live20Result, Live20Direction, VolumeApproach } from '../../types/live20';
import { CandlestickIcon } from './CandlestickIcon';
import { getCandlePatternLabel } from './candlestickUtils';
import { cn } from '@/lib/utils';
import { ExpandedRowContent } from './ExpandedRowContent';

interface Live20TableProps {
  /** Results to display in the table */
  results: Live20Result[];
}

/**
 * Badge component for displaying direction (LONG/SHORT/NO_SETUP)
 * Uses teal for Long and orange for Short (screener signal colors)
 */
function DirectionBadge({ direction }: { direction: Live20Direction | null }) {
  if (!direction) return <Badge variant="secondary">-</Badge>;

  const variants: Record<Live20Direction, { className: string; label: string }> = {
    LONG: {
      className: 'bg-[var(--signal-long-muted)] text-[var(--signal-long)] border border-[var(--signal-long)] hover:bg-[var(--signal-long-muted)]',
      label: 'LONG',
    },
    SHORT: {
      className: 'bg-[var(--signal-short-muted)] text-[var(--signal-short)] border border-[var(--signal-short)] hover:bg-[var(--signal-short-muted)]',
      label: 'SHORT',
    },
    NO_SETUP: {
      className: 'bg-[rgba(100,116,139,0.15)] text-text-secondary border border-default hover:bg-[rgba(100,116,139,0.15)]',
      label: 'NO SETUP',
    },
  };

  const { className, label } = variants[direction];

  return (
    <span className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full font-mono text-[11px] font-semibold uppercase tracking-wide ${className}`}>
      <span className="badge-dot" />
      {label}
    </span>
  );
}

/**
 * Icon component for displaying alignment status (aligned/not aligned/null)
 */
function AlignmentIcon({ aligned }: { aligned: boolean | null }) {
  if (aligned === null) return <MinusCircle className="h-4 w-4 text-muted-foreground" />;
  return aligned ? (
    <CheckCircle className="h-4 w-4 text-accent-bullish" />
  ) : (
    <XCircle className="h-4 w-4 text-muted-foreground" />
  );
}

/**
 * Get color class for ATR percentage based on volatility thresholds
 */
function getAtrColorClass(atr: number | null): string {
  if (atr === null) return '';

  // Low volatility: < 3%
  if (atr < 3) return 'text-accent-bullish';

  // Moderate volatility: 3-6%
  if (atr < 6) return 'text-score-medium';

  // High volatility: >= 6%
  return 'text-accent-bearish';
}

/**
 * Score bar component with color gradient based on score value
 */
function ScoreBar({ score }: { score: number }) {
  const getColorClass = () => {
    if (score >= 70) return 'high';
    if (score >= 40) return 'medium';
    return 'low';
  };

  const colorClass = getColorClass();
  const textColor = colorClass === 'high' ? 'text-accent-bullish' :
                   colorClass === 'medium' ? 'text-score-medium' : 'text-accent-bearish';
  const bgGradient = colorClass === 'high' ? 'bg-gradient-to-r from-accent-bullish to-emerald-400' :
                    colorClass === 'medium' ? 'bg-gradient-to-r from-score-medium to-yellow-300' :
                    'bg-gradient-to-r from-accent-bearish to-red-400';

  return (
    <div className="flex items-center gap-2.5 min-w-[140px]">
      <div className="flex-1 h-1.5 bg-bg-elevated rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full transition-all ${bgGradient}`}
          style={{ width: `${score}%` }}
        />
      </div>
      <span className={`font-mono text-xs font-semibold min-w-[28px] text-right ${textColor}`}>
        {score}
      </span>
    </div>
  );
}

/**
 * Get volume approach display info (badge text and tooltip description)
 */
function getVolumeApproachInfo(approach: VolumeApproach): {
  badge: string;
  title: string;
  description: string;
} | null {
  if (!approach) return null;

  const info = {
    exhaustion: {
      badge: 'EXH',
      title: 'Exhaustion',
      description: 'Volume declining while trend continues',
    },
    accumulation: {
      badge: 'ACC',
      title: 'Accumulation',
      description: 'Buyers entering on reversal candle',
    },
    distribution: {
      badge: 'DIST',
      title: 'Distribution',
      description: 'Sellers entering on reversal candle',
    },
  };

  return info[approach];
}

/**
 * Live 20 results table
 *
 * Displays analysis results in a sortable table with columns for symbol, direction,
 * score, price, and each criterion (Trend, MA20, Candle, Volume, CCI) with alignment
 * indicators. Supports sorting by score (default: descending).
 *
 * @param props - Component props
 */
export function Live20Table({ results }: Live20TableProps) {
  const [sorting, setSorting] = useState<SortingState>([{ id: 'confidence_score', desc: true }]);
  const [expanded, setExpanded] = useState<ExpandedState>({});

  const columns = useMemo<ColumnDef<Live20Result>[]>(
    () => [
      {
        id: 'expand',
        header: () => null,
        cell: ({ row }) => (
          <button
            onClick={() => row.toggleExpanded()}
            className="p-1 hover:bg-bg-elevated rounded transition-colors"
            aria-expanded={row.getIsExpanded()}
            aria-label={`Expand details for ${row.original.stock}`}
          >
            {row.getIsExpanded() ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
          </button>
        ),
      },
      {
        accessorKey: 'stock',
        header: 'Symbol',
        cell: ({ row }) => (
          <span className="font-mono font-semibold">{row.original.stock}</span>
        ),
      },
      {
        accessorKey: 'sector_etf',
        header: 'Sector',
        cell: ({ row }) => (
          <span className="text-xs font-mono text-text-secondary">
            {row.original.sector_etf ?? '-'}
          </span>
        ),
      },
      {
        accessorKey: 'direction',
        header: 'Direction',
        cell: ({ row }) => <DirectionBadge direction={row.original.direction} />,
      },
      {
        accessorKey: 'confidence_score',
        header: ({ column }) => (
          <button
            className="flex items-center gap-1 hover:text-foreground"
            onClick={() => column.toggleSorting(column.getIsSorted() === 'asc')}
          >
            Score
            <ArrowUpDown className="h-4 w-4" />
          </button>
        ),
        cell: ({ row }) => <ScoreBar score={row.original.confidence_score} />,
      },
      {
        accessorKey: 'entry_price',
        header: 'Price',
        cell: ({ row }) => (
          <span className="font-mono">
            ${row.original.entry_price?.toFixed(2) ?? '-'}
          </span>
        ),
      },
      {
        accessorKey: 'atr',
        header: ({ column }) => (
          <button
            className="flex items-center gap-1 hover:text-foreground"
            onClick={() => column.toggleSorting(column.getIsSorted() === 'asc')}
          >
            ATR
            <ArrowUpDown className="h-4 w-4" />
          </button>
        ),
        cell: ({ row }) => {
          const atr = row.original.atr;
          const colorClass = getAtrColorClass(atr);

          return (
            <span className={cn('font-mono font-semibold', colorClass)}>
              {atr != null ? `${atr.toFixed(2)}%` : '-'}
            </span>
          );
        },
      },
      {
        accessorKey: 'trend_aligned',
        header: 'Trend',
        cell: ({ row }) => (
          <div className="flex items-center gap-1">
            <AlignmentIcon aligned={row.original.trend_aligned} />
            <span className="text-xs text-muted-foreground">
              {row.original.trend_direction}
            </span>
          </div>
        ),
      },
      {
        accessorKey: 'ma20_aligned',
        header: 'MA20',
        cell: ({ row }) => (
          <div className="flex items-center gap-1">
            <AlignmentIcon aligned={row.original.ma20_aligned} />
            <span className="text-xs text-muted-foreground">
              {row.original.ma20_distance_pct?.toFixed(1)}%
            </span>
          </div>
        ),
      },
      {
        accessorKey: 'candle_aligned',
        header: 'Candle',
        cell: ({ row }) => (
          <Tooltip>
            <TooltipTrigger asChild>
              <div className="flex items-center gap-1.5 cursor-help">
                <AlignmentIcon aligned={row.original.candle_aligned} />
                <CandlestickIcon
                  pattern={row.original.candle_pattern}
                  bullish={row.original.candle_bullish}
                  size={20}
                />
              </div>
            </TooltipTrigger>
            <TooltipContent className="max-w-xs">
              <p className="font-medium">{getCandlePatternLabel(row.original.candle_pattern)}</p>
              {row.original.candle_explanation && (
                <p className="text-sm text-muted-foreground mt-1">
                  {row.original.candle_explanation}
                </p>
              )}
            </TooltipContent>
          </Tooltip>
        ),
      },
      {
        accessorKey: 'volume_aligned',
        header: ({ column }) => (
          <button
            className="flex items-center gap-1 hover:text-foreground"
            onClick={() => column.toggleSorting(column.getIsSorted() === 'asc')}
          >
            Volume
            <ArrowUpDown className="h-4 w-4" />
          </button>
        ),
        sortingFn: (rowA, rowB) => (rowA.original.rvol ?? 0) - (rowB.original.rvol ?? 0),
        cell: ({ row }) => {
          const approachInfo = getVolumeApproachInfo(row.original.volume_approach);

          return (
            <div className="flex items-center gap-1">
              <AlignmentIcon aligned={row.original.volume_aligned} />
              <span className="text-xs text-muted-foreground">
                {row.original.rvol != null ? `${row.original.rvol.toFixed(1)}x` : '-'}
              </span>
              {approachInfo && (
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Badge
                      variant="outline"
                      className="text-[10px] px-1 py-0 h-4 cursor-help"
                    >
                      {approachInfo.badge}
                    </Badge>
                  </TooltipTrigger>
                  <TooltipContent>
                    <p className="font-medium">{approachInfo.title}</p>
                    <p className="text-xs text-muted-foreground">
                      {approachInfo.description}
                    </p>
                  </TooltipContent>
                </Tooltip>
              )}
            </div>
          );
        },
      },
      {
        accessorKey: 'cci_aligned',
        header: 'CCI',
        cell: ({ row }) => {
          const direction = row.original.cci_direction;
          const DirectionIcon = direction === 'rising' ? TrendingUp :
                               direction === 'falling' ? TrendingDown : Minus;
          const directionColor = direction === 'rising' ? 'text-up-indicator' :
                                direction === 'falling' ? 'text-down-indicator' : 'text-muted-foreground';

          return (
            <Tooltip>
              <TooltipTrigger asChild>
                <div className="flex items-center gap-1 cursor-help">
                  <AlignmentIcon aligned={row.original.cci_aligned} />
                  <DirectionIcon className={`h-3.5 w-3.5 ${directionColor}`} />
                  <span className="font-mono text-xs">
                    {row.original.cci_value?.toFixed(0) ?? '-'}
                  </span>
                </div>
              </TooltipTrigger>
              <TooltipContent>
                <p className="font-medium">CCI: {row.original.cci_value?.toFixed(1) ?? '-'}</p>
                <p className="text-xs text-muted-foreground">
                  Zone: {row.original.cci_zone ?? '-'} | Direction: {direction ?? '-'}
                </p>
              </TooltipContent>
            </Tooltip>
          );
        },
      },
    ],
    []
  );

  const table = useReactTable({
    data: results,
    columns,
    state: { sorting, expanded },
    onSortingChange: setSorting,
    onExpandedChange: setExpanded,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getExpandedRowModel: getExpandedRowModel(),
  });

  return (
    <TooltipProvider>
      <div className="bg-bg-secondary rounded-xl border border-default overflow-hidden">
        {/* Results Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-subtle">
          <span className="font-display text-sm font-semibold text-text-secondary">
            Analysis Results
          </span>
          <span className="font-mono text-xs text-text-muted">
            Showing {results.length} result{results.length !== 1 ? 's' : ''}
          </span>
        </div>

        <div className="overflow-x-auto">
          <Table>
            <TableHeader>
              {table.getHeaderGroups().map((headerGroup) => (
                <TableRow key={headerGroup.id} className="border-b border-subtle bg-bg-tertiary">
                  {headerGroup.headers.map((header) => (
                    <TableHead
                      key={header.id}
                      className="text-[10px] font-semibold uppercase tracking-wider text-text-muted whitespace-nowrap"
                    >
                      {header.isPlaceholder
                        ? null
                        : flexRender(header.column.columnDef.header, header.getContext())}
                    </TableHead>
                  ))}
                </TableRow>
              ))}
            </TableHeader>
            <TableBody>
              {table.getRowModel().rows.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={columns.length} className="h-24 text-center">
                    <p className="text-muted-foreground">No results found</p>
                  </TableCell>
                </TableRow>
              ) : (
                table.getRowModel().rows.map((row) => (
                  <Fragment key={row.id}>
                    <TableRow className="border-b border-subtle hover:bg-bg-tertiary transition-colors">
                      {row.getVisibleCells().map((cell) => (
                        <TableCell key={cell.id} className="text-[13px]">
                          {flexRender(cell.column.columnDef.cell, cell.getContext())}
                        </TableCell>
                      ))}
                    </TableRow>
                    {row.getIsExpanded() && (
                      <TableRow>
                        <TableCell colSpan={columns.length} className="p-0">
                          <ExpandedRowContent result={row.original} />
                        </TableCell>
                      </TableRow>
                    )}
                  </Fragment>
                ))
              )}
            </TableBody>
          </Table>
        </div>
      </div>
    </TooltipProvider>
  );
}
