import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import type { StockList } from '@/services/stockListService';

/**
 * Props for the WatchlistHeader component
 */
export interface WatchlistHeaderProps {
  /** Array of available stock lists */
  lists: StockList[];
  /** Currently selected list ID, or null if no list is selected */
  selectedListId: number | null;
  /** Callback fired when a list is selected */
  onListChange: (listId: number) => void;
}

/**
 * WatchlistHeader Component
 *
 * Header section of the watchlist panel containing the title and list selector dropdown.
 * Uses ShadCN Select component with custom styling to match the trading terminal aesthetic.
 *
 * @example
 * ```tsx
 * <WatchlistHeader
 *   lists={stockLists}
 *   selectedListId={selectedListId}
 *   onListChange={handleListChange}
 * />
 * ```
 */
export const WatchlistHeader = ({
  lists,
  selectedListId,
  onListChange,
}: WatchlistHeaderProps) => {
  /**
   * Handle select value change.
   * Converts string value back to number for the callback.
   */
  const handleValueChange = (value: string) => {
    onListChange(Number(value));
  };

  // Convert selectedListId to string for Radix Select
  const selectValue = selectedListId !== null ? String(selectedListId) : undefined;

  return (
    <div className="p-4 pb-3 border-b border-subtle">
      {/* Section title */}
      <h2 className="text-[11px] font-semibold uppercase tracking-[0.1em] text-text-muted mb-3">
        Watchlist
      </h2>

      {/* List selector dropdown */}
      <Select value={selectValue} onValueChange={handleValueChange}>
        <SelectTrigger
          className="w-full h-10 bg-bg-tertiary border-default hover:border-accent-primary hover:bg-bg-elevated transition-colors"
          aria-label="Select a watchlist"
        >
          <SelectValue placeholder="Select a list" />
        </SelectTrigger>
        <SelectContent>
          {lists.length === 0 ? (
            <div className="py-2 px-3 text-sm text-text-muted">
              No lists available
            </div>
          ) : (
            lists.map((list) => (
              <SelectItem key={list.id} value={String(list.id)}>
                {list.name}
              </SelectItem>
            ))
          )}
        </SelectContent>
      </Select>
    </div>
  );
};
