import { cn } from '@/lib/utils';

/**
 * Props for the SymbolChips component
 */
interface SymbolChipsProps {
  /** Array of stock symbols to display as chips */
  symbols: string[];
  /** Currently active symbol (highlighted) */
  activeSymbol: string;
  /** Callback fired when a symbol chip is clicked */
  onSymbolSelect: (symbol: string) => void;
}

/**
 * SymbolChips Component
 *
 * A horizontal scrollable row of symbol chips for quick symbol switching.
 * The active symbol is highlighted with primary color styling.
 *
 * Features:
 * - Horizontal scroll with overflow for many symbols
 * - Active chip highlighted with green background
 * - Monospace font for consistent symbol display
 * - Keyboard accessible (focusable buttons)
 *
 * @example
 * ```tsx
 * <SymbolChips
 *   symbols={['AAPL', 'MSFT', 'GOOGL']}
 *   activeSymbol="AAPL"
 *   onSymbolSelect={setSymbol}
 * />
 * ```
 */
export const SymbolChips = ({
  symbols,
  activeSymbol,
  onSymbolSelect,
}: SymbolChipsProps) => {
  // Normalize active symbol for comparison
  const normalizedActiveSymbol = activeSymbol.toUpperCase();

  return (
    <div className="p-4 bg-muted/30 border border-border rounded-lg">
      <p className="text-xs text-muted-foreground uppercase font-semibold mb-3 tracking-wide">
        Quick Switch
      </p>
      <div
        className="flex gap-2 overflow-x-auto pb-1 scrollbar-thin"
        role="group"
        aria-label="Symbol quick switch"
      >
        {symbols.map((symbol) => {
          const isActive = symbol.toUpperCase() === normalizedActiveSymbol;
          return (
            <button
              key={symbol}
              type="button"
              onClick={() => onSymbolSelect(symbol)}
              className={cn(
                // Base styles
                'px-4 py-1.5 rounded-md font-mono font-semibold text-sm',
                'border whitespace-nowrap transition-colors duration-150',
                'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2',
                // Active vs inactive states
                isActive
                  ? 'bg-primary text-primary-foreground border-primary'
                  : 'bg-muted text-muted-foreground border-border hover:bg-muted/80 hover:text-foreground'
              )}
              aria-pressed={isActive}
              aria-label={`Switch to ${symbol}${isActive ? ' (currently selected)' : ''}`}
            >
              {symbol}
            </button>
          );
        })}
      </div>
    </div>
  );
};
