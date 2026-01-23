import { describe, it, expect } from 'vitest';
import { formatCurrency, formatPercentage, formatLargeNumber, formatVolumeWithComparison, formatDate, formatPercent, formatPnL } from './formatters';

describe('formatCurrency', () => {
  it('formats positive numbers correctly', () => {
    expect(formatCurrency(150.25)).toBe('$150.25');
    expect(formatCurrency(1234.5)).toBe('$1,234.50');
  });

  it('formats negative numbers correctly', () => {
    expect(formatCurrency(-50.75)).toBe('-$50.75');
    expect(formatCurrency(-1234.56)).toBe('-$1,234.56');
  });

  it('always shows 2 decimal places', () => {
    expect(formatCurrency(100)).toBe('$100.00');
    expect(formatCurrency(0)).toBe('$0.00');
  });

  it('handles very large numbers', () => {
    expect(formatCurrency(1000000)).toBe('$1,000,000.00');
    expect(formatCurrency(1234567.89)).toBe('$1,234,567.89');
  });

  it('handles zero correctly', () => {
    expect(formatCurrency(0)).toBe('$0.00');
  });

  it('rounds to 2 decimal places', () => {
    expect(formatCurrency(123.456)).toBe('$123.46');
    expect(formatCurrency(123.454)).toBe('$123.45');
  });
});

describe('formatPercentage', () => {
  it('formats decimal to percentage with default 1 decimal place', () => {
    expect(formatPercentage(0.05)).toBe('5.0%');
    expect(formatPercentage(0.12345)).toBe('12.3%');
  });

  it('supports custom decimal places', () => {
    expect(formatPercentage(0.12345, 2)).toBe('12.35%');
    expect(formatPercentage(0.12345, 0)).toBe('12%');
    expect(formatPercentage(0.12345, 3)).toBe('12.345%');
  });

  it('handles negative percentages', () => {
    expect(formatPercentage(-0.05)).toBe('-5.0%');
    expect(formatPercentage(-0.12345, 2)).toBe('-12.35%');
  });

  it('handles zero correctly', () => {
    expect(formatPercentage(0)).toBe('0.0%');
    expect(formatPercentage(0, 2)).toBe('0.00%');
  });

  it('handles very small percentages', () => {
    expect(formatPercentage(0.001)).toBe('0.1%');
    expect(formatPercentage(0.0001, 2)).toBe('0.01%');
  });

  it('handles values greater than 1', () => {
    expect(formatPercentage(1)).toBe('100.0%');
    expect(formatPercentage(1.5)).toBe('150.0%');
  });

  it('rounds correctly', () => {
    expect(formatPercentage(0.12345)).toBe('12.3%');
    expect(formatPercentage(0.12355)).toBe('12.4%');
  });
});

describe('formatLargeNumber', () => {
  it('formats thousands with K', () => {
    expect(formatLargeNumber(1234)).toBe('1.2K');
    expect(formatLargeNumber(5678)).toBe('5.7K');
    expect(formatLargeNumber(999000)).toBe('999.0K');
  });

  it('formats millions with M', () => {
    expect(formatLargeNumber(1234567)).toBe('1.2M');
    expect(formatLargeNumber(50000000)).toBe('50.0M');
    expect(formatLargeNumber(999000000)).toBe('999.0M');
  });

  it('formats billions with B', () => {
    expect(formatLargeNumber(1234567890)).toBe('1.2B');
    expect(formatLargeNumber(50000000000)).toBe('50.0B');
    expect(formatLargeNumber(999000000000)).toBe('999.0B');
  });

  it('returns small numbers as-is', () => {
    expect(formatLargeNumber(999)).toBe('999');
    expect(formatLargeNumber(500)).toBe('500');
    expect(formatLargeNumber(0)).toBe('0');
  });

  it('handles edge cases at boundaries', () => {
    expect(formatLargeNumber(1000)).toBe('1.0K');
    expect(formatLargeNumber(1000000)).toBe('1.0M');
    expect(formatLargeNumber(1000000000)).toBe('1.0B');
  });

  it('rounds to 1 decimal place', () => {
    expect(formatLargeNumber(1234)).toBe('1.2K');
    expect(formatLargeNumber(1289)).toBe('1.3K');
    expect(formatLargeNumber(1250000)).toBe('1.3M');
  });

  it('handles very large numbers', () => {
    expect(formatLargeNumber(1500000000000)).toBe('1500.0B');
    expect(formatLargeNumber(9999999999999)).toBe('10000.0B');
  });
});

describe('formatVolumeWithComparison', () => {
  it('formats volume with comparison to average', () => {
    expect(formatVolumeWithComparison(1500000, 1000000)).toBe('1.5M (150% of avg)');
  });

  it('handles null actual volume', () => {
    expect(formatVolumeWithComparison(null, 1000000)).toBe('Avg: 1.0M');
  });

  it('handles null average volume', () => {
    expect(formatVolumeWithComparison(1500000, null)).toBe('1.5M');
  });

  it('handles both null', () => {
    expect(formatVolumeWithComparison(null, null)).toBe('-');
  });

  it('handles zero average', () => {
    expect(formatVolumeWithComparison(1500000, 0)).toBe('1.5M');
  });
});

describe('formatDate', () => {
  it('formats date with default options (month, day, hour, minute)', () => {
    const date = '2025-11-27T14:30:00Z';
    const result = formatDate(date);
    // Format will be "Nov 27, 14:30" (24-hour format)
    expect(result).toMatch(/Nov 27/);
  });

  it('accepts custom formatting options', () => {
    const date = '2025-11-27T14:30:00Z';
    const result = formatDate(date, { year: 'numeric', month: 'short', day: 'numeric' });
    expect(result).toMatch(/Nov 27, 2025/);
  });

  it('handles ISO date strings', () => {
    const date = '2025-11-27T10:00:00Z';
    const result = formatDate(date);
    expect(result).toBeTruthy();
    expect(result).toMatch(/Nov 27/);
  });

  it('formats different dates correctly', () => {
    const date1 = '2025-01-15T12:00:00Z';
    const date2 = '2025-12-31T12:00:00Z';

    expect(formatDate(date1)).toMatch(/Jan 15/);
    expect(formatDate(date2)).toMatch(/Dec 31/);
  });
});

describe('formatPercent', () => {
  it('formats positive percentages with plus sign', () => {
    expect(formatPercent(5.2)).toBe('+5.2%');
    expect(formatPercent(12.5)).toBe('+12.5%');
  });

  it('formats negative percentages without plus sign', () => {
    expect(formatPercent(-3.1)).toBe('-3.1%');
    expect(formatPercent(-8.7)).toBe('-8.7%');
  });

  it('formats zero without sign', () => {
    expect(formatPercent(0)).toBe('0.0%');
  });

  it('supports custom decimal places', () => {
    expect(formatPercent(12.345, 2)).toBe('+12.35%');
    expect(formatPercent(-8.123, 2)).toBe('-8.12%');
    expect(formatPercent(5.5, 0)).toBe('+6%');
  });

  it('uses default 1 decimal place', () => {
    expect(formatPercent(5.234)).toBe('+5.2%');
    expect(formatPercent(-3.789)).toBe('-3.8%');
  });

  it('handles very small values', () => {
    expect(formatPercent(0.1)).toBe('+0.1%');
    expect(formatPercent(-0.05)).toBe('-0.1%');
  });

  it('handles large values', () => {
    expect(formatPercent(150.5)).toBe('+150.5%');
    expect(formatPercent(-200.25)).toBe('-200.3%');
  });
});

describe('formatPnL', () => {
  it('formats positive P&L with up arrow', () => {
    const result = formatPnL('100.50');
    expect(result.text).toBe('$100.50');
    expect(result.className).toBe('text-accent-bullish');
    expect(result.symbol).toBe('▲');
  });

  it('formats negative P&L with down arrow', () => {
    const result = formatPnL('-50.25');
    expect(result.text).toBe('-$50.25');
    expect(result.className).toBe('text-accent-bearish');
    expect(result.symbol).toBe('▼');
  });

  it('formats zero with no symbol', () => {
    const result = formatPnL('0');
    expect(result.text).toBe('$0.00');
    expect(result.className).toBe('text-muted-foreground');
    expect(result.symbol).toBe('');
  });

  it('returns em dash for null', () => {
    const result = formatPnL(null);
    expect(result.text).toBe('—');
    expect(result.className).toBe('text-muted-foreground');
    expect(result.symbol).toBe('');
  });

  it('returns em dash for undefined', () => {
    const result = formatPnL(undefined!);
    expect(result.text).toBe('—');
    expect(result.className).toBe('text-muted-foreground');
    expect(result.symbol).toBe('');
  });

  it('returns em dash for invalid string', () => {
    const result = formatPnL('not-a-number');
    expect(result.text).toBe('—');
    expect(result.className).toBe('text-muted-foreground');
    expect(result.symbol).toBe('');
  });

  it('formats large positive P&L', () => {
    const result = formatPnL('1234.56');
    expect(result.text).toBe('$1,234.56');
    expect(result.className).toBe('text-accent-bullish');
    expect(result.symbol).toBe('▲');
  });

  it('formats large negative P&L', () => {
    const result = formatPnL('-9876.54');
    expect(result.text).toBe('-$9,876.54');
    expect(result.className).toBe('text-accent-bearish');
    expect(result.symbol).toBe('▼');
  });

  it('handles very small positive values', () => {
    const result = formatPnL('0.01');
    expect(result.text).toBe('$0.01');
    expect(result.className).toBe('text-accent-bullish');
    expect(result.symbol).toBe('▲');
  });

  it('handles very small negative values', () => {
    const result = formatPnL('-0.01');
    expect(result.text).toBe('-$0.01');
    expect(result.className).toBe('text-accent-bearish');
    expect(result.symbol).toBe('▼');
  });
});
