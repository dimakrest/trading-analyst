import { cn } from '@/lib/utils';

/**
 * Props for the WatchlistItem component
 */
export interface WatchlistItemProps {
  /** Stock ticker symbol */
  symbol: string;
  /** Whether this item is currently selected */
  isActive: boolean;
  /** Callback fired when the item is clicked */
  onClick: () => void;
}

/**
 * WatchlistItem Component
 *
 * A single stock row in the watchlist panel showing the symbol.
 * Supports active/hover states.
 *
 * @example
 * ```tsx
 * <WatchlistItem
 *   symbol="AAPL"
 *   isActive={false}
 *   onClick={() => handleSymbolSelect('AAPL')}
 * />
 * ```
 */
export const WatchlistItem = ({
  symbol,
  isActive,
  onClick,
}: WatchlistItemProps) => {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        'w-full flex items-center gap-2.5 p-3 rounded-lg cursor-pointer transition-all duration-150',
        'border border-transparent mb-0.5',
        'hover:bg-bg-tertiary',
        isActive && 'bg-accent-primary-muted border-accent-primary'
      )}
      aria-pressed={isActive}
      aria-label={`Select ${symbol}`}
    >
      {/* Symbol */}
      <div className="flex-1 min-w-0 text-left">
        <div className="font-mono font-bold text-[13px] text-text-primary">
          {symbol}
        </div>
      </div>
    </button>
  );
};
