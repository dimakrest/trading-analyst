import { cn } from '@/lib/utils';
import { formatCurrency, formatLargeNumber } from '@/utils/formatters';

/**
 * Props for individual stat items in the StockHero stats grid
 */
interface StatItemProps {
  /** Label text displayed above the value */
  label: string;
  /** Value to display (formatted string or number) */
  value?: string | number | null;
  /** Color variant for the value */
  variant?: 'bullish' | 'bearish' | 'default';
}

/**
 * StatItem Component
 *
 * Displays a single stat in the hero section's 3x2 grid.
 * Right-aligned with uppercase label and mono-spaced value.
 */
function StatItem({ label, value, variant = 'default' }: StatItemProps) {
  return (
    <div className="text-right">
      <div className="text-[10px] font-medium uppercase tracking-[0.08em] text-text-muted mb-1">
        {label}
      </div>
      <div
        className={cn(
          'font-mono text-sm font-semibold',
          variant === 'bullish' && 'text-accent-bullish',
          variant === 'bearish' && 'text-accent-bearish',
          variant === 'default' && 'text-text-primary'
        )}
      >
        {value ?? '\u2014'}
      </div>
    </div>
  );
}

/**
 * Stats configuration for the hero section
 */
export interface StockHeroStats {
  /** Highest price of the day */
  dayHigh?: number | null;
  /** Lowest price of the day */
  dayLow?: number | null;
  /** Trading volume */
  volume?: number | null;
  /** Previous day's closing price */
  prevClose?: number | null;
  /** 20-day moving average */
  ma20?: number | null;
  /** Commodity Channel Index */
  cci?: number | null;
}

/**
 * Props for the StockHero component
 */
export interface StockHeroProps {
  /** Stock ticker symbol (e.g., "AAPL") */
  symbol: string;
  /** Current stock price */
  price: number;
  /** Absolute price change from previous close */
  change: number;
  /** Percentage change from previous close */
  changePercent: number;
  /** Market direction (bullish/bearish/neutral) */
  direction: 'bullish' | 'bearish' | 'neutral';
  /** Stats grid data */
  stats: StockHeroStats;
  /** Whether the component is in a loading state */
  isLoading?: boolean;
  /** Additional CSS classes */
  className?: string;
}

/**
 * Format price into dollars and cents parts
 */
const splitPrice = (price: number): { dollars: string; cents: string } => {
  const dollars = Math.floor(price);
  const cents = ((price % 1) * 100).toFixed(0).padStart(2, '0');
  return {
    dollars: dollars.toLocaleString('en-US'),
    cents,
  };
};

/**
 * Format change value with sign
 */
const formatChange = (change: number): string => {
  const sign = change >= 0 ? '+' : '';
  return `${sign}${formatCurrency(change)}`;
};

/**
 * Format percentage change with sign
 */
const formatChangePercent = (percent: number): string => {
  const sign = percent >= 0 ? '+' : '';
  return `${sign}${percent.toFixed(2)}%`;
};

/**
 * StockHero Component
 *
 * Hero section displaying stock symbol, large price display with glow effect,
 * and a 6-item stats grid. Used as the focal point of the Analysis page.
 *
 * @example
 * ```tsx
 * <StockHero
 *   symbol="AAPL"
 *   price={178.45}
 *   change={2.34}
 *   changePercent={1.33}
 *   direction="bullish"
 *   stats={{
 *     dayHigh: 180.50,
 *     dayLow: 176.25,
 *     volume: 48200000,
 *     prevClose: 176.11,
 *     ma20: 175.80,
 *     cci: 125.3
 *   }}
 * />
 * ```
 */
export const StockHero = ({
  symbol,
  price,
  change,
  changePercent,
  direction,
  stats,
  isLoading = false,
  className,
}: StockHeroProps) => {
  const { dollars, cents } = splitPrice(price);
  const isBullish = direction === 'bullish';
  const isBearish = direction === 'bearish';

  // Determine CCI variant based on its value
  const cciVariant: 'bullish' | 'bearish' | 'default' =
    stats.cci != null ? (stats.cci > 0 ? 'bullish' : stats.cci < 0 ? 'bearish' : 'default') : 'default';

  if (isLoading) {
    return (
      <div
        className={cn(
          'relative grid grid-cols-1 lg:grid-cols-[1fr_auto] gap-8 p-6 lg:p-7',
          'bg-gradient-to-br from-bg-secondary to-bg-tertiary',
          'rounded-lg border border-default overflow-hidden',
          className
        )}
        data-testid="stock-hero-loading"
      >
        {/* Loading skeleton */}
        <div className="animate-pulse space-y-4">
          <div className="h-10 w-32 bg-bg-elevated rounded" />
          <div className="h-12 w-48 bg-bg-elevated rounded" />
        </div>
        <div className="grid grid-cols-3 gap-5">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="animate-pulse text-right">
              <div className="h-3 w-12 bg-bg-elevated rounded mb-2 ml-auto" />
              <div className="h-4 w-16 bg-bg-elevated rounded ml-auto" />
            </div>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div
      className={cn(
        'relative grid grid-cols-1 lg:grid-cols-[1fr_auto] gap-8 p-6 lg:p-7',
        'bg-gradient-to-br from-bg-secondary to-bg-tertiary',
        'rounded-lg border border-default overflow-hidden',
        className
      )}
      data-testid="stock-hero"
    >
      {/* Glow effect - positioned in top right corner */}
      <div
        className={cn(
          isBullish && 'hero-glow-bullish',
          isBearish && 'hero-glow-bearish'
        )}
        aria-hidden="true"
      />

      {/* Main content: symbol, price, change */}
      <div className="flex flex-col gap-1.5 relative z-[1]">
        {/* Symbol row with badge */}
        <div className="flex items-center gap-3.5">
          <span
            className="font-display text-4xl font-bold tracking-tight text-text-primary"
            data-testid="stock-hero-symbol"
          >
            {symbol}
          </span>
          {direction !== 'neutral' && (
            <span
              className={cn(
                'inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full',
                'font-mono text-[11px] font-semibold uppercase tracking-wide border',
                isBullish && 'bg-accent-bullish/15 text-accent-bullish border-accent-bullish',
                isBearish && 'bg-accent-bearish/15 text-accent-bearish border-accent-bearish'
              )}
              data-testid="stock-hero-badge"
            >
              <span className="badge-dot" />
              {isBullish ? 'Bullish' : 'Bearish'}
            </span>
          )}
        </div>

        {/* Price container */}
        <div className="flex items-baseline gap-3.5 mt-0.5">
          {/* Hero price with split dollars/cents */}
          <div
            className="font-mono text-[48px] font-bold tracking-tight text-text-primary leading-none"
            data-testid="stock-hero-price"
          >
            ${dollars}
            <span className="text-[28px] opacity-70">.{cents}</span>
          </div>

          {/* Change display */}
          <div className="flex flex-col gap-0.5">
            <span
              className={cn(
                'font-mono text-lg font-semibold',
                change >= 0 ? 'text-accent-bullish' : 'text-accent-bearish'
              )}
              data-testid="stock-hero-change"
            >
              {formatChange(change)}
            </span>
            <span
              className="font-mono text-xs text-text-muted"
              data-testid="stock-hero-change-percent"
            >
              {formatChangePercent(changePercent)}
            </span>
          </div>
        </div>
      </div>

      {/* Stats grid: 3x2 layout */}
      <div
        className="grid grid-cols-3 gap-5 relative z-[1]"
        data-testid="stock-hero-stats"
      >
        <StatItem
          label="Day High"
          value={stats.dayHigh != null ? formatCurrency(stats.dayHigh) : null}
          variant="bullish"
        />
        <StatItem
          label="Day Low"
          value={stats.dayLow != null ? formatCurrency(stats.dayLow) : null}
          variant="bearish"
        />
        <StatItem
          label="Volume"
          value={stats.volume != null ? formatLargeNumber(stats.volume) : null}
        />
        <StatItem
          label="Prev Close"
          value={stats.prevClose != null ? formatCurrency(stats.prevClose) : null}
        />
        <StatItem
          label="MA 20"
          value={stats.ma20 != null ? formatCurrency(stats.ma20) : null}
        />
        <StatItem
          label="CCI"
          value={stats.cci != null ? stats.cci.toFixed(1) : null}
          variant={cciVariant}
        />
      </div>
    </div>
  );
};
