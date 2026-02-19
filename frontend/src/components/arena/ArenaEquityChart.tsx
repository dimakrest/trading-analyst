/**
 * ArenaEquityChart
 *
 * Line chart showing portfolio total equity over time for a completed simulation.
 * Supports an optional SPY / QQQ benchmark overlay that toggles the Y-axis between
 * absolute dollar values and normalized percentage returns so both series share the
 * same scale.
 *
 * Uses TradingView Lightweight Charts v5 for high-performance canvas rendering.
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import {
  createChart,
  LineSeries,
  LineStyle,
  type IChartApi,
  type ISeriesApi,
  type UTCTimestamp,
} from 'lightweight-charts';
import { Loader2 } from 'lucide-react';
import { toast } from 'sonner';
import { useChartTheme } from '../../hooks/useChartTheme';
import { CHART_COLORS } from '../../constants/chartColors';
import { getBenchmarkData } from '../../services/arenaService';
import { ToggleGroup, ToggleGroupItem } from '../ui/toggle-group';
import type { Snapshot } from '../../types/arena';

interface ArenaEquityChartProps {
  snapshots: Snapshot[];
  simulationId: number;
}

/** Absolute-dollar price format used when no benchmark is active. */
const CURRENCY_PRICE_FORMAT = {
  type: 'custom' as const,
  formatter: (price: number) =>
    '$' +
    price.toLocaleString('en-US', {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }),
};

/** Percentage price format used when a benchmark overlay is active. */
const PERCENT_PRICE_FORMAT = {
  type: 'custom' as const,
  formatter: (price: number) => price.toFixed(2) + '%',
};

/**
 * Portfolio equity curve chart with optional SPY / QQQ benchmark overlay.
 *
 * When a benchmark is selected:
 * - The equity series is switched to a normalized % return view so both lines
 *   share the same Y-axis scale.
 * - The benchmark cumulative-return series is overlaid as a dashed line.
 * - The Y-axis label format is updated to show '%' values.
 *
 * Both series remain mounted throughout — only their data is swapped. This
 * avoids flickering from series removal / re-addition.
 *
 * The data swap is atomic: absolute equity is kept displayed while the fetch
 * is in flight so the user never sees a %-scale chart with a single line.
 */
export const ArenaEquityChart = ({
  snapshots,
  simulationId,
}: ArenaEquityChartProps) => {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const equitySeriesRef = useRef<ISeriesApi<'Line'> | null>(null);
  const benchmarkSeriesRef = useRef<ISeriesApi<'Line'> | null>(null);

  const chartTheme = useChartTheme();

  // Which benchmark is currently active (null = absolute equity view)
  const [activeBenchmark, setActiveBenchmark] = useState<'SPY' | 'QQQ' | null>(null);
  // True while the benchmark fetch is in flight
  const [benchmarkLoading, setBenchmarkLoading] = useState(false);
  // True if the last benchmark fetch failed (used to style the toggle item)
  const [benchmarkError, setBenchmarkError] = useState(false);

  // Pre-compute both data representations from current snapshots.
  // absoluteData: raw dollar equity values.
  // normalizedPortfolio: cumulative % return from the first snapshot.
  const absoluteData = snapshots.map((s) => ({
    time: (new Date(s.snapshot_date).getTime() / 1000) as UTCTimestamp,
    value: parseFloat(s.total_equity),
  }));

  const firstEquity = snapshots.length > 0 ? parseFloat(snapshots[0].total_equity) : 1;
  const normalizedPortfolio = snapshots.map((s) => ({
    time: (new Date(s.snapshot_date).getTime() / 1000) as UTCTimestamp,
    value: ((parseFloat(s.total_equity) - firstEquity) / firstEquity) * 100,
  }));

  // Initialize chart and both series on mount.
  // chartTheme is the only dependency — the data useEffect handles data updates.
  useEffect(() => {
    if (!chartContainerRef.current) return;

    const chart = createChart(chartContainerRef.current, {
      ...chartTheme,
      width: chartContainerRef.current.clientWidth,
      height: 280,
    });

    // Equity series — solid line, currency format by default
    const equitySeries = chart.addSeries(LineSeries, {
      color: CHART_COLORS.EQUITY,
      lineWidth: 2,
      priceLineVisible: false,
      lastValueVisible: false,
      crosshairMarkerVisible: true,
      priceFormat: CURRENCY_PRICE_FORMAT,
    });

    // Benchmark series — dashed line, always mounted but starts empty
    const benchmarkSeries = chart.addSeries(LineSeries, {
      color: CHART_COLORS.MA_50,
      lineWidth: 2,
      lineStyle: LineStyle.Dashed,
      priceLineVisible: false,
      lastValueVisible: false,
      crosshairMarkerVisible: true,
      priceFormat: PERCENT_PRICE_FORMAT,
    });

    chartRef.current = chart;
    equitySeriesRef.current = equitySeries;
    benchmarkSeriesRef.current = benchmarkSeries;

    // Responsive resize
    const resizeObserver = new ResizeObserver((entries) => {
      const { width: containerWidth } = entries[0].contentRect;
      chart.applyOptions({ width: containerWidth });
    });

    resizeObserver.observe(chartContainerRef.current);

    return () => {
      resizeObserver.disconnect();

      if (benchmarkSeriesRef.current) {
        chart.removeSeries(benchmarkSeriesRef.current);
        benchmarkSeriesRef.current = null;
      }
      if (equitySeriesRef.current) {
        chart.removeSeries(equitySeriesRef.current);
        equitySeriesRef.current = null;
      }

      chart.remove();
      chartRef.current = null;
    };
  }, [chartTheme]);

  // Populate equity series when snapshots change (and no benchmark is active).
  // When a benchmark is active the data is already in normalized form — don't
  // overwrite it here.
  useEffect(() => {
    if (!equitySeriesRef.current || snapshots.length < 2) return;

    // Only update if we are in the absolute view; benchmark toggle manages its
    // own data swap.
    if (activeBenchmark === null) {
      equitySeriesRef.current.setData(absoluteData);

      if (chartRef.current) {
        chartRef.current.timeScale().fitContent();
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [snapshots]);

  /**
   * Restore the chart to absolute-dollar equity mode.
   * Clears benchmark data and resets the Y-axis format.
   */
  const restoreAbsoluteView = useCallback(() => {
    if (!equitySeriesRef.current || !benchmarkSeriesRef.current) return;

    equitySeriesRef.current.setData(absoluteData);
    equitySeriesRef.current.applyOptions({ priceFormat: CURRENCY_PRICE_FORMAT });
    benchmarkSeriesRef.current.setData([]);

    if (chartRef.current) {
      chartRef.current.timeScale().fitContent();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [snapshots]);

  /**
   * Fetch benchmark data and swap the chart to normalized % view atomically.
   * Keeps the absolute equity displayed until the fetch succeeds to avoid
   * showing an empty %-scale chart.
   */
  const activateBenchmark = useCallback(
    async (symbol: 'SPY' | 'QQQ') => {
      if (!equitySeriesRef.current || !benchmarkSeriesRef.current) return;

      setBenchmarkLoading(true);
      setBenchmarkError(false);

      try {
        const data = await getBenchmarkData(simulationId, symbol);

        const benchmarkTimeData = data.map((p) => ({
          time: (new Date(p.date).getTime() / 1000) as UTCTimestamp,
          value: parseFloat(p.cumulative_return_pct),
        }));

        // Atomic swap: normalized portfolio + benchmark + format change all at once
        equitySeriesRef.current.setData(normalizedPortfolio);
        equitySeriesRef.current.applyOptions({ priceFormat: PERCENT_PRICE_FORMAT });
        benchmarkSeriesRef.current.setData(benchmarkTimeData);

        if (chartRef.current) {
          chartRef.current.timeScale().fitContent();
        }
      } catch {
        setBenchmarkError(true);
        toast.error(`Failed to load ${symbol} benchmark data`);
      } finally {
        setBenchmarkLoading(false);
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [simulationId, snapshots],
  );

  /**
   * Handle toggle group value change.
   * - Clicking an inactive item activates that benchmark.
   * - Clicking the currently active item deactivates it (restores absolute view).
   * - An empty string value means the user deselected everything.
   */
  const handleBenchmarkToggle = useCallback(
    (value: string) => {
      const newBenchmark = value as 'SPY' | 'QQQ' | '';

      if (newBenchmark === '' || newBenchmark === activeBenchmark) {
        // Deactivate: restore absolute view
        setActiveBenchmark(null);
        setBenchmarkError(false);
        restoreAbsoluteView();
      } else {
        const symbol = newBenchmark as 'SPY' | 'QQQ';
        setActiveBenchmark(symbol);
        activateBenchmark(symbol);
      }
    },
    [activeBenchmark, activateBenchmark, restoreAbsoluteView],
  );

  // Not enough data placeholder (< 2 points = invisible line in lightweight-charts)
  if (snapshots.length < 2) {
    return (
      <div
        className="flex items-center justify-center rounded-lg border border-gray-700 bg-black"
        style={{ height: '280px' }}
        role="status"
        aria-label="Equity chart — not enough data"
        data-testid="arena-equity-chart-placeholder"
      >
        <p className="text-muted-foreground text-sm">Not enough data</p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {/* Controls row */}
      <div className="flex items-center justify-between">
        <span className="text-xs text-muted-foreground">
          {activeBenchmark
            ? 'Cumulative return % — portfolio vs benchmark'
            : 'Portfolio equity (absolute)'}
        </span>

        <div className="flex items-center gap-2">
          <span className="text-xs text-muted-foreground">Benchmark</span>
          <ToggleGroup
            type="single"
            size="sm"
            value={activeBenchmark ?? ''}
            onValueChange={handleBenchmarkToggle}
            aria-label="Select benchmark overlay"
          >
            {(['SPY', 'QQQ'] as const).map((symbol) => {
              const isActive = activeBenchmark === symbol;
              const isLoading = isActive && benchmarkLoading;
              const isErrored = isActive && benchmarkError;

              return (
                <ToggleGroupItem
                  key={symbol}
                  value={symbol}
                  aria-label={`Toggle ${symbol} benchmark`}
                  aria-pressed={isActive}
                  disabled={benchmarkLoading}
                  className={isErrored ? 'text-accent-bearish' : undefined}
                  data-testid={`benchmark-toggle-${symbol.toLowerCase()}`}
                >
                  {isLoading ? (
                    <Loader2
                      className="h-3 w-3 animate-spin"
                      aria-label={`Loading ${symbol} benchmark`}
                    />
                  ) : (
                    symbol
                  )}
                </ToggleGroupItem>
              );
            })}
          </ToggleGroup>
        </div>
      </div>

      {/* Chart canvas */}
      <div
        ref={chartContainerRef}
        className="w-full rounded-lg border border-gray-700 bg-black"
        style={{ height: '280px' }}
        role="img"
        aria-label={
          activeBenchmark
            ? `Portfolio equity vs ${activeBenchmark} benchmark`
            : 'Portfolio equity over time'
        }
        data-testid="arena-equity-chart"
      />

      {/* Legend — only visible when a benchmark is active */}
      {activeBenchmark && !benchmarkLoading && (
        <div
          className="flex items-center gap-4 text-xs text-muted-foreground"
          data-testid="benchmark-legend"
        >
          {/* Portfolio: solid line */}
          <div className="flex items-center gap-1.5">
            <span
              className="inline-block h-0.5 w-5 rounded-full"
              style={{ backgroundColor: CHART_COLORS.EQUITY }}
              aria-hidden="true"
            />
            <span>Portfolio</span>
          </div>

          {/* Benchmark: dashed line */}
          <div className="flex items-center gap-1.5">
            <span
              className="inline-block w-5"
              style={{
                height: '2px',
                backgroundImage: `repeating-linear-gradient(to right, ${CHART_COLORS.MA_50} 0, ${CHART_COLORS.MA_50} 4px, transparent 4px, transparent 7px)`,
              }}
              aria-hidden="true"
            />
            <span>{activeBenchmark}</span>
          </div>
        </div>
      )}
    </div>
  );
};
