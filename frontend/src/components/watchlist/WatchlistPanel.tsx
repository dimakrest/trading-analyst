import { ScrollArea } from '@/components/ui/scroll-area';
import { Skeleton } from '@/components/ui/skeleton';
import type { StockList } from '@/services/stockListService';
import { WatchlistHeader } from './WatchlistHeader';
import { WatchlistItem } from './WatchlistItem';

/**
 * Props for the WatchlistPanel component
 */
export interface WatchlistPanelProps {
  /** Array of available stock lists */
  lists: StockList[];
  /** Currently selected list ID, or null if no list is selected */
  selectedListId: number | null;
  /** Callback fired when a list is selected */
  onListChange: (listId: number) => void;
  /** Array of symbols from the selected list */
  symbols: string[];
  /** Currently selected symbol, or null if none selected */
  selectedSymbol: string | null;
  /** Callback fired when a symbol is selected */
  onSymbolSelect: (symbol: string) => void;
  /** Whether the panel is in a loading state */
  isLoading?: boolean;
}

/**
 * WatchlistPanel Component
 *
 * Secondary sidebar for the Analysis page showing a list of stocks.
 * Contains a header with list selector and a scrollable area of stock items.
 *
 * The panel is designed to:
 * - Display a dropdown to switch between stock lists
 * - Show all symbols from the selected list
 * - Highlight the currently selected symbol
 * - Handle loading and empty states gracefully
 *
 * @example
 * ```tsx
 * <WatchlistPanel
 *   lists={stockLists}
 *   selectedListId={selectedListId}
 *   onListChange={handleListChange}
 *   symbols={['AAPL', 'MSFT', 'GOOGL']}
 *   selectedSymbol={selectedSymbol}
 *   onSymbolSelect={handleSymbolSelect}
 *   isLoading={false}
 * />
 * ```
 */
export const WatchlistPanel = ({
  lists,
  selectedListId,
  onListChange,
  symbols,
  selectedSymbol,
  onSymbolSelect,
  isLoading = false,
}: WatchlistPanelProps) => {
  return (
    <div
      className="bg-bg-secondary border-r border-subtle flex flex-col"
      style={{ height: 'calc(100vh - var(--status-bar-height))' }}
    >
      {/* Header with list selector */}
      <WatchlistHeader
        lists={lists}
        selectedListId={selectedListId}
        onListChange={onListChange}
      />

      {/* Scrollable items area */}
      <ScrollArea className="flex-1">
        <div className="p-2">
          {isLoading ? (
            // Loading skeleton state
            <div className="space-y-2" data-testid="watchlist-loading">
              {Array.from({ length: 6 }).map((_, index) => (
                <div key={index} className="p-3 space-y-2">
                  <Skeleton className="h-4 w-16" />
                  <Skeleton className="h-3 w-12" />
                </div>
              ))}
            </div>
          ) : symbols.length === 0 ? (
            // Empty state
            <div
              className="p-4 text-center text-text-muted text-sm"
              data-testid="watchlist-empty"
            >
              {selectedListId === null
                ? 'Select a list to view symbols'
                : 'No symbols in this list'}
            </div>
          ) : (
            // Symbol list
            <div data-testid="watchlist-items">
              {symbols.map((symbol) => (
                <WatchlistItem
                  key={symbol}
                  symbol={symbol}
                  isActive={symbol === selectedSymbol}
                  onClick={() => onSymbolSelect(symbol)}
                />
              ))}
            </div>
          )}
        </div>
      </ScrollArea>
    </div>
  );
};
