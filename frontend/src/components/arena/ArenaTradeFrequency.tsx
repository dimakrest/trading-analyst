/**
 * ArenaTradeFrequency
 *
 * Trade frequency histogram chart showing how many positions were opened per
 * calendar month. Computed client-side from the positions array.
 *
 * Uses TradingView Lightweight Charts v5 HistogramSeries for high-performance
 * canvas rendering. Follows the exact same useRef + useEffect + ResizeObserver
 * + cleanup pattern as ArenaEquityChart.tsx.
 *
 * Renders nothing when positions.length < 1.
 */
import { useEffect, useRef } from 'react';
import {
  createChart,
  HistogramSeries,
  type IChartApi,
  type ISeriesApi,
  type UTCTimestamp,
} from 'lightweight-charts';
import { Card, CardContent, CardHeader, CardTitle } from '../ui/card';
import { useChartTheme } from '../../hooks/useChartTheme';
import { CHART_COLORS } from '../../constants/chartColors';
import type { Position } from '../../types/arena';

interface ArenaTradeFrequencyProps {
  positions: Position[];
}

/**
 * Parse an entry_date string "YYYY-MM-DD" to a "YYYY-MM" bucket key.
 * Slices the first 7 characters — avoids timezone drift from Date parsing.
 */
const toMonthKey = (dateStr: string): string => dateStr.slice(0, 7);

/**
 * Convert a "YYYY-MM" key to a UTC timestamp (seconds) for the first calendar
 * day of that month. lightweight-charts requires numeric UTCTimestamp values.
 */
const monthKeyToTimestamp = (key: string): UTCTimestamp => {
  return (new Date(`${key}-01`).getTime() / 1000) as UTCTimestamp;
};

interface MonthlyBucket {
  time: UTCTimestamp;
  value: number; // trade count
}

/**
 * Group positions by entry month and count trades per bucket.
 * Returns buckets sorted chronologically.
 */
const buildMonthlyBuckets = (positions: Position[]): MonthlyBucket[] => {
  const counts = new Map<string, number>();

  for (const position of positions) {
    if (!position.entry_date) continue;
    const key = toMonthKey(position.entry_date);
    counts.set(key, (counts.get(key) ?? 0) + 1);
  }

  return Array.from(counts.entries())
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([key, count]) => ({
      time: monthKeyToTimestamp(key),
      value: count,
    }));
};

/**
 * Trade frequency histogram chart for a completed Arena simulation.
 *
 * Each bar represents one calendar month, and its height equals the number of
 * positions opened during that month. Uses CHART_COLORS.EQUITY for visual
 * consistency with the equity curve chart rendered above.
 */
export const ArenaTradeFrequency = ({ positions }: ArenaTradeFrequencyProps) => {
  if (positions.length < 1) return null;

  return <ArenaTradeFrequencyChart positions={positions} />;
};

/**
 * Inner component that mounts the chart. Separated so the null check above
 * guarantees this component always has at least one position to work with,
 * keeping hook rules satisfied regardless of positions.length.
 */
const ArenaTradeFrequencyChart = ({ positions }: { positions: Position[] }) => {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const histSeriesRef = useRef<ISeriesApi<'Histogram'> | null>(null);

  const chartTheme = useChartTheme();

  // Initialize chart on mount; re-initialize if the theme changes.
  useEffect(() => {
    if (!chartContainerRef.current) return;

    const chart = createChart(chartContainerRef.current, {
      ...chartTheme,
      width: chartContainerRef.current.clientWidth,
      height: 200,
    });

    const histSeries = chart.addSeries(HistogramSeries, {
      color: CHART_COLORS.EQUITY,
      priceLineVisible: false,
      lastValueVisible: false,
    });

    chartRef.current = chart;
    histSeriesRef.current = histSeries;

    // Responsive resize
    const resizeObserver = new ResizeObserver((entries) => {
      const { width: containerWidth } = entries[0].contentRect;
      chart.applyOptions({ width: containerWidth });
    });

    resizeObserver.observe(chartContainerRef.current);

    return () => {
      resizeObserver.disconnect();
      chart.remove();
      chartRef.current = null;
      histSeriesRef.current = null;
    };
  }, [chartTheme]);

  // Populate histogram data whenever positions change.
  useEffect(() => {
    if (!histSeriesRef.current) return;

    const buckets = buildMonthlyBuckets(positions);
    histSeriesRef.current.setData(buckets);

    if (chartRef.current && buckets.length > 0) {
      chartRef.current.timeScale().fitContent();
    }
  }, [positions]);

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-sm font-semibold">Trade Frequency</CardTitle>
      </CardHeader>
      <CardContent>
        <div
          ref={chartContainerRef}
          className="w-full rounded-lg border border-gray-700 bg-black"
          style={{ height: '200px' }}
          role="img"
          aria-label="Trade frequency per month"
          data-testid="arena-trade-frequency-chart"
        />
      </CardContent>
    </Card>
  );
};
