import { List, Pencil, Trash2 } from 'lucide-react';
import { Button } from '../ui/button';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '../ui/table';
import { Skeleton } from '../ui/skeleton';
import { useResponsive } from '../../hooks/useResponsive';
import type { StockList } from '../../services/stockListService';

interface StockListsTableProps {
  /** Array of stock lists to display */
  lists: StockList[];
  /** Whether the table is in loading state */
  isLoading: boolean;
  /** Error message to display */
  error: string | null;
  /** Total symbols count across all lists */
  totalSymbols?: number;
  /** Callback when edit button is clicked */
  onEdit: (list: StockList) => void;
  /** Callback when delete button is clicked */
  onDelete: (list: StockList) => void;
}

/**
 * Empty state component for when there are no lists
 */
const EmptyState = () => (
  <div className="flex flex-col items-center justify-center py-20 px-10 text-center">
    <div className="w-20 h-20 rounded-[20px] bg-bg-tertiary flex items-center justify-center mb-6">
      <List className="w-10 h-10 text-text-muted" />
    </div>
    <h3 className="font-display text-lg font-semibold text-text-primary mb-2">
      No stock lists yet
    </h3>
    <p className="text-sm text-text-muted max-w-[360px]">
      Create your first list to organize symbols for quick analysis
    </p>
  </div>
);

/**
 * Table component for displaying stock lists
 *
 * Features:
 * - Desktop: Standard table layout with icon, count badge, preview chips, and action buttons
 * - Mobile: Compact layout with sticky name column and icon buttons
 * - Loading state with skeletons
 * - Error state display
 * - Empty state when no lists exist
 */
export const StockListsTable = ({
  lists,
  isLoading,
  error,
  totalSymbols = 0,
  onEdit,
  onDelete,
}: StockListsTableProps) => {
  const { isMobile, mounted } = useResponsive();

  // Loading state
  if (isLoading) {
    return (
      <div className="bg-bg-secondary rounded-xl border border-default overflow-hidden">
        <div className="px-5 py-4 border-b border-subtle flex items-center justify-between">
          <span className="font-display text-sm font-semibold text-text-secondary">Your Lists</span>
          <Skeleton className="h-4 w-32" />
        </div>
        <div className="p-4 space-y-3">
          {[...Array(3)].map((_, i) => (
            <Skeleton key={i} className="h-16 w-full" />
          ))}
        </div>
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div className="bg-bg-secondary rounded-xl border border-default overflow-hidden">
        <div className="text-center py-8 text-accent-bearish">
          {error}
        </div>
      </div>
    );
  }

  // Empty state
  if (lists.length === 0) {
    return (
      <div className="bg-bg-secondary rounded-xl border border-default overflow-hidden">
        <EmptyState />
      </div>
    );
  }

  // Prevent hydration mismatch
  if (!mounted) {
    return (
      <div className="bg-bg-secondary rounded-xl border border-default overflow-hidden">
        <div className="p-8 text-center text-text-muted">
          Loading lists...
        </div>
      </div>
    );
  }

  // Mobile layout: Compact with sticky first column and icon buttons
  if (isMobile) {
    return (
      <div className="bg-bg-secondary rounded-xl border border-default overflow-hidden">
        <div className="px-5 py-4 border-b border-subtle flex items-center justify-between">
          <span className="font-display text-sm font-semibold text-text-secondary">Your Lists</span>
          <span className="font-mono text-xs text-text-muted">
            {lists.length} list{lists.length !== 1 ? 's' : ''}
          </span>
        </div>
        {/* Header Row */}
        <div className="flex border-b border-subtle bg-bg-tertiary">
          <div className="flex-shrink-0 w-32 h-10 flex items-center px-4 text-[10px] font-semibold uppercase tracking-[0.08em] text-text-muted border-r border-subtle sticky left-0 z-10 bg-bg-tertiary">
            Name
          </div>
          <div className="flex overflow-x-auto">
            <div className="flex-shrink-0 w-20 h-10 flex items-center px-3 text-[10px] font-semibold uppercase tracking-[0.08em] text-text-muted border-r border-subtle">
              Count
            </div>
            <div className="flex-shrink-0 w-24 h-10 flex items-center justify-end px-3 text-[10px] font-semibold uppercase tracking-[0.08em] text-text-muted">
              Actions
            </div>
          </div>
        </div>

        {/* Data Rows */}
        {lists.map((list) => (
          <div
            key={list.id}
            className="flex border-b border-subtle last:border-b-0 hover:bg-bg-tertiary transition-colors duration-150"
          >
            {/* Sticky Name Cell */}
            <div className="flex-shrink-0 w-32 h-14 flex items-center px-4 font-display font-semibold text-sm border-r border-subtle sticky left-0 z-10 bg-bg-secondary">
              {list.name}
            </div>

            {/* Scrollable Cells */}
            <div className="flex overflow-x-auto">
              <div className="flex-shrink-0 w-20 h-14 flex items-center gap-2 px-3 border-r border-subtle">
                <span className="px-2.5 py-1 bg-bg-elevated rounded-md font-mono text-[13px] font-semibold">
                  {list.symbol_count}
                </span>
              </div>
              <div className="flex-shrink-0 w-24 h-14 flex items-center justify-end px-3 gap-2">
                <Button
                  variant="ghost"
                  size="icon"
                  className="w-9 h-9 bg-bg-tertiary border border-default hover:bg-accent-primary-muted hover:text-accent-primary hover:border-accent-primary"
                  onClick={() => onEdit(list)}
                  aria-label={`Edit ${list.name}`}
                >
                  <Pencil className="h-4 w-4" />
                </Button>
                <Button
                  variant="ghost"
                  size="icon"
                  className="w-9 h-9 bg-bg-tertiary border border-default hover:bg-accent-bearish-muted hover:text-accent-bearish hover:border-accent-bearish"
                  onClick={() => onDelete(list)}
                  aria-label={`Delete ${list.name}`}
                >
                  <Trash2 className="h-4 w-4" />
                </Button>
              </div>
            </div>
          </div>
        ))}
      </div>
    );
  }

  // Desktop layout: Full table with preview chips
  return (
    <div className="bg-bg-secondary rounded-xl border border-default overflow-hidden">
      <div className="px-5 py-4 border-b border-subtle flex items-center justify-between">
        <span className="font-display text-sm font-semibold text-text-secondary">Your Lists</span>
        <span className="font-mono text-xs text-text-muted">
          {lists.length} list{lists.length !== 1 ? 's' : ''} &bull; {totalSymbols} symbol{totalSymbols !== 1 ? 's' : ''} total
        </span>
      </div>
      <div className="overflow-x-auto">
        <Table>
          <TableHeader>
            <TableRow className="border-subtle hover:bg-transparent">
              <TableHead className="bg-bg-tertiary text-[10px] font-semibold uppercase tracking-[0.08em] text-text-muted h-11 px-5">
                List Name
              </TableHead>
              <TableHead className="bg-bg-tertiary text-[10px] font-semibold uppercase tracking-[0.08em] text-text-muted h-11 px-5">
                Symbols
              </TableHead>
              <TableHead className="bg-bg-tertiary text-[10px] font-semibold uppercase tracking-[0.08em] text-text-muted h-11 px-5">
                Preview
              </TableHead>
              <TableHead className="bg-bg-tertiary text-[10px] font-semibold uppercase tracking-[0.08em] text-text-muted h-11 px-5 text-right">
                Actions
              </TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {lists.map((list) => (
              <TableRow
                key={list.id}
                className="border-subtle hover:bg-bg-tertiary transition-colors duration-150"
              >
                {/* List Name with Icon */}
                <TableCell className="px-5 py-4">
                  <div className="flex items-center gap-3">
                    <div className="w-9 h-9 rounded-lg bg-accent-primary-muted flex items-center justify-center flex-shrink-0">
                      <List className="w-[18px] h-[18px] text-accent-primary" />
                    </div>
                    <span className="font-display font-semibold text-sm text-text-primary">
                      {list.name}
                    </span>
                  </div>
                </TableCell>

                {/* Symbol Count Badge */}
                <TableCell className="px-5 py-4">
                  <div className="flex items-center gap-2">
                    <span className="px-2.5 py-1 bg-bg-elevated rounded-md font-mono text-[13px] font-semibold">
                      {list.symbol_count}
                    </span>
                    <span className="text-xs text-text-muted">
                      symbol{list.symbol_count !== 1 ? 's' : ''}
                    </span>
                  </div>
                </TableCell>

                {/* Preview Chips */}
                <TableCell className="px-5 py-4">
                  <div className="flex flex-wrap gap-1.5 max-w-[400px]">
                    {list.symbols.slice(0, 4).map((symbol) => (
                      <span
                        key={symbol}
                        className="px-2.5 py-1 bg-bg-tertiary border border-default rounded-md font-mono text-[11px] font-semibold text-text-secondary"
                      >
                        {symbol}
                      </span>
                    ))}
                    {list.symbols.length > 4 && (
                      <span className="px-2.5 py-1 border border-dashed border-default rounded-md font-mono text-[11px] text-text-muted">
                        +{list.symbols.length - 4} more
                      </span>
                    )}
                    {list.symbols.length === 0 && (
                      <span className="text-xs text-text-muted italic">No symbols</span>
                    )}
                  </div>
                </TableCell>

                {/* Action Buttons */}
                <TableCell className="px-5 py-4">
                  <div className="flex gap-2 justify-end">
                    <Button
                      variant="ghost"
                      size="icon"
                      className="w-9 h-9 bg-bg-tertiary border border-default hover:bg-accent-primary-muted hover:text-accent-primary hover:border-accent-primary transition-colors"
                      onClick={() => onEdit(list)}
                      aria-label={`Edit ${list.name}`}
                    >
                      <Pencil className="w-4 h-4" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="w-9 h-9 bg-bg-tertiary border border-default hover:bg-accent-bearish-muted hover:text-accent-bearish hover:border-accent-bearish transition-colors"
                      onClick={() => onDelete(list)}
                      aria-label={`Delete ${list.name}`}
                    >
                      <Trash2 className="w-4 h-4" />
                    </Button>
                  </div>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </div>
  );
};
