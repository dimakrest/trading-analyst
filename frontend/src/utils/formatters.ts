/**
 * Format a number as USD currency
 *
 * @param value - The numeric value to format
 * @returns Formatted currency string (e.g., "$150.25")
 *
 * @example
 * formatCurrency(150.25) // "$150.25"
 * formatCurrency(1234.5) // "$1,234.50"
 */
export const formatCurrency = (value: number): string => {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value);
};

/**
 * Format a decimal as percentage
 *
 * @param value - Decimal value (e.g., 0.05 for 5%)
 * @param decimals - Number of decimal places (default: 1)
 * @returns Formatted percentage string (e.g., "5.0%")
 *
 * @example
 * formatPercentage(0.05) // "5.0%"
 * formatPercentage(0.12345, 2) // "12.35%"
 */
export const formatPercentage = (value: number, decimals: number = 1): string => {
  return `${(value * 100).toFixed(decimals)}%`;
};

/**
 * Format a large number with abbreviations (K, M, B)
 *
 * @param value - The numeric value to format
 * @returns Abbreviated number string (e.g., "1.2M")
 *
 * @example
 * formatLargeNumber(1234) // "1.2K"
 * formatLargeNumber(1234567) // "1.2M"
 */
export const formatLargeNumber = (value: number): string => {
  if (value >= 1_000_000_000) {
    return `${(value / 1_000_000_000).toFixed(1)}B`;
  }
  if (value >= 1_000_000) {
    return `${(value / 1_000_000).toFixed(1)}M`;
  }
  if (value >= 1_000) {
    return `${(value / 1_000).toFixed(1)}K`;
  }
  return value.toString();
};

/**
 * Format volume with comparison to average
 *
 * @param actual - Actual volume
 * @param average - Average volume (e.g., 20-day SMA)
 * @returns Formatted string like "1.2M (150% of avg)"
 */
export const formatVolumeWithComparison = (
  actual: number | null | undefined,
  average: number | null | undefined
): string => {
  if (actual == null) {
    if (average == null) return '-';
    return `Avg: ${formatLargeNumber(average)}`;
  }

  const formattedActual = formatLargeNumber(actual);

  if (average == null || average === 0) {
    return formattedActual;
  }

  const percentOfAvg = Math.round((actual / average) * 100);
  return `${formattedActual} (${percentOfAvg}% of avg)`;
};

/**
 * Format a date string for display
 *
 * @param dateStr - ISO date string
 * @param options - Intl.DateTimeFormatOptions to customize formatting
 * @returns Formatted date string (e.g., "Nov 27, 14:30")
 *
 * @example
 * formatDate('2025-11-27T14:30:00Z') // "Nov 27, 14:30"
 * formatDate('2025-11-27', { year: 'numeric' }) // "Nov 27, 2025"
 */
export const formatDate = (
  dateStr: string,
  options?: Intl.DateTimeFormatOptions
): string => {
  const defaultOptions: Intl.DateTimeFormatOptions = {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
    ...options,
  };
  return new Date(dateStr).toLocaleDateString('en-US', defaultOptions);
};

/**
 * Format a number as percentage with optional sign
 *
 * @param value - The numeric value (as percentage, not decimal)
 * @param decimals - Number of decimal places (default: 1)
 * @returns Formatted percentage string with sign (e.g., "+5.2%", "-3.1%")
 *
 * @example
 * formatPercent(5.2) // "+5.2%"
 * formatPercent(-3.1) // "-3.1%"
 * formatPercent(12.345, 2) // "+12.35%"
 */
export const formatPercent = (value: number, decimals: number = 1): string => {
  const prefix = value > 0 ? '+' : '';
  return `${prefix}${value.toFixed(decimals)}%`;
};

/**
 * Format P&L value with color coding and directional symbol.
 * Returns text, className, and symbol for accessibility (color-blind users).
 *
 * @param value - The P&L value as a string (from API) or null
 * @returns Object with formatted text, CSS className, and directional symbol
 *
 * @example
 * formatPnL('150.50') // { text: '$150.50', className: 'text-accent-bullish', symbol: '▲' }
 * formatPnL('-25.00') // { text: '$-25.00', className: 'text-accent-bearish', symbol: '▼' }
 * formatPnL('0') // { text: '$0.00', className: 'text-muted-foreground', symbol: '' }
 * formatPnL(null) // { text: '—', className: 'text-muted-foreground', symbol: '' }
 */
export function formatPnL(value: string | null): {
  text: string;
  className: string;
  symbol: string;
} {
  if (value === null || value === undefined) {
    return { text: '—', className: 'text-muted-foreground', symbol: '' };
  }

  const num = parseFloat(value);

  if (isNaN(num)) {
    return { text: '—', className: 'text-muted-foreground', symbol: '' };
  }

  const formatted = formatCurrency(num);

  if (num > 0) {
    return { text: formatted, className: 'text-accent-bullish', symbol: '▲' };
  }

  if (num < 0) {
    return { text: formatted, className: 'text-accent-bearish', symbol: '▼' };
  }

  return { text: formatted, className: 'text-muted-foreground', symbol: '' };
}
