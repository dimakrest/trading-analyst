/**
 * ArenaEquityChart
 *
 * Line chart showing portfolio total equity over time for a completed simulation.
 * Both S&P 500 (SPY) and QQQ benchmarks are shown by default as normalized %
 * return overlays. Each benchmark can be toggled independently.
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

type BenchmarkSymbol = 'SPY' | 'QQQ';

const BENCHMARK_CONFIG: Record<BenchmarkSymbol, { color: string; label: string }> = {
  SPY: { color: CHART_COLORS.SPY, label: 'S&P 500' },
  QQQ: { color: CHART_COLORS.QQQ, label: 'QQQ' },
};

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
 * Portfolio equity curve chart with optional SPY / QQQ benchmark overlays.
 *
 * Both benchmarks are shown by default in normalized % return mode so all
 * three series share the same Y-axis scale.
 *
 * Each benchmark toggle is independent — turning both off restores the
 * absolute dollar equity view.
 *
 * All three series remain mounted throughout; only their data is swapped.
 * isNormalizedRef tracks the current Y-axis mode so the snapshot-update
 * effect can write the correct data format without stale-closure issues.
 */
export const ArenaEquityChart = ({
  snapshots,
  simulationId,
}: ArenaEquityChartProps) => {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const equitySeriesRef = useRef<ISeriesApi<'Line'> | null>(null);
  const spySeriesRef = useRef<ISeriesApi<'Line'> | null>(null);
  const qqqSeriesRef = useRef<ISeriesApi<'Line'> | null>(null);

  // Tracks whether the equity series is in normalized-% mode (vs absolute $).
  // Stored as a ref to avoid stale closures in the snapshots effect.
  const isNormalizedRef = useRef(true);

  const chartTheme = useChartTheme();

  // Both benchmarks active by default
  const [activeBenchmarks, setActiveBenchmarks] = useState<Set<BenchmarkSymbol>>(
    () => new Set<BenchmarkSymbol>(['SPY', 'QQQ']),
  );
  const [loadingBenchmarks, setLoadingBenchmarks] = useState<Set<BenchmarkSymbol>>(
    () => new Set<BenchmarkSymbol>(),
  );
  const [errorBenchmarks, setErrorBenchmarks] = useState<Set<BenchmarkSymbol>>(
    () => new Set<BenchmarkSymbol>(),
  );

  // Guard against double-fetching on mount when snapshots prop is stable
  const initialFetchDoneRef = useRef(false);

  // Pre-compute both data representations from current snapshots.
  const absoluteData = snapshots.map((s) => ({
    time: (new Date(s.snapshot_date).getTime() / 1000) as UTCTimestamp,
    value: parseFloat(s.total_equity),
  }));

  const firstEquity = snapshots.length > 0 ? (parseFloat(snapshots[0].total_equity) || 1) : 1;
  const normalizedPortfolio = snapshots.map((s) => ({
    time: (new Date(s.snapshot_date).getTime() / 1000) as UTCTimestamp,
    value: ((parseFloat(s.total_equity) - firstEquity) / firstEquity) * 100,
  }));

  // Initialize chart and all three series on mount.
  // chartTheme is the only dependency — data effects handle population.
  useEffect(() => {
    if (!chartContainerRef.current) return;

    const chart = createChart(chartContainerRef.current, {
      ...chartTheme,
      width: chartContainerRef.current.clientWidth,
      height: 280,
    });

    // Equity series — solid line, starts in % format (both benchmarks on by default)
    const equitySeries = chart.addSeries(LineSeries, {
      color: CHART_COLORS.EQUITY,
      lineWidth: 2,
      priceLineVisible: false,
      lastValueVisible: false,
      crosshairMarkerVisible: true,
      priceFormat: PERCENT_PRICE_FORMAT,
    });

    // SPY series — dashed line, always mounted but starts empty
    const spySeries = chart.addSeries(LineSeries, {
      color: CHART_COLORS.SPY,
      lineWidth: 2,
      lineStyle: LineStyle.Dashed,
      priceLineVisible: false,
      lastValueVisible: false,
      crosshairMarkerVisible: true,
      priceFormat: PERCENT_PRICE_FORMAT,
    });

    // QQQ series — dashed line, always mounted but starts empty
    const qqqSeries = chart.addSeries(LineSeries, {
      color: CHART_COLORS.QQQ,
      lineWidth: 2,
      lineStyle: LineStyle.Dashed,
      priceLineVisible: false,
      lastValueVisible: false,
      crosshairMarkerVisible: true,
      priceFormat: PERCENT_PRICE_FORMAT,
    });

    chartRef.current = chart;
    equitySeriesRef.current = equitySeries;
    spySeriesRef.current = spySeries;
    qqqSeriesRef.current = qqqSeries;

    const resizeObserver = new ResizeObserver((entries) => {
      const { width } = entries[0].contentRect;
      chart.applyOptions({ width });
    });

    resizeObserver.observe(chartContainerRef.current);

    return () => {
      resizeObserver.disconnect();
      if (qqqSeriesRef.current) { chart.removeSeries(qqqSeriesRef.current); qqqSeriesRef.current = null; }
      if (spySeriesRef.current) { chart.removeSeries(spySeriesRef.current); spySeriesRef.current = null; }
      if (equitySeriesRef.current) { chart.removeSeries(equitySeriesRef.current); equitySeriesRef.current = null; }
      chart.remove();
      chartRef.current = null;
    };
  }, [chartTheme]);

  const getSeriesRef = (symbol: BenchmarkSymbol) =>
    symbol === 'SPY' ? spySeriesRef : qqqSeriesRef;

  /** Fetch benchmark data and populate the appropriate series. */
  const fetchBenchmark = useCallback(
    async (symbol: BenchmarkSymbol) => {
      const seriesRef = getSeriesRef(symbol);
      if (!seriesRef.current) return;

      setLoadingBenchmarks((prev) => new Set(prev).add(symbol));
      setErrorBenchmarks((prev) => { const n = new Set(prev); n.delete(symbol); return n; });

      try {
        const data = await getBenchmarkData(simulationId, symbol);
        if (data.length === 0) {
          throw new Error('No data');
        }
        const timeData = data.map((p) => ({
          time: (new Date(p.date).getTime() / 1000) as UTCTimestamp,
          value: parseFloat(p.cumulative_return_pct),
        }));
        seriesRef.current.setData(timeData);
        chartRef.current?.timeScale().fitContent();
      } catch {
        setErrorBenchmarks((prev) => new Set(prev).add(symbol));
        toast.error(`Failed to load ${symbol} benchmark data`);
        setActiveBenchmarks((prev) => { const n = new Set(prev); n.delete(symbol); return n; });
        seriesRef.current?.setData([]);
      } finally {
        setLoadingBenchmarks((prev) => { const n = new Set(prev); n.delete(symbol); return n; });
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [simulationId],
  );

  /** Switch equity series between normalized-% and absolute-$ mode. */
  const setEquityMode = useCallback(
    (normalized: boolean) => {
      if (!equitySeriesRef.current) return;
      isNormalizedRef.current = normalized;
      if (normalized) {
        equitySeriesRef.current.setData(normalizedPortfolio);
        equitySeriesRef.current.applyOptions({ priceFormat: PERCENT_PRICE_FORMAT });
      } else {
        equitySeriesRef.current.setData(absoluteData);
        equitySeriesRef.current.applyOptions({ priceFormat: CURRENCY_PRICE_FORMAT });
      }
      chartRef.current?.timeScale().fitContent();
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [snapshots],
  );

  // Populate equity series on snapshot updates; auto-fetch benchmarks on first load.
  useEffect(() => {
    if (!equitySeriesRef.current || snapshots.length < 2) return;

    // Refresh equity series with up-to-date data in the current mode
    if (isNormalizedRef.current) {
      equitySeriesRef.current.setData(normalizedPortfolio);
    } else {
      equitySeriesRef.current.setData(absoluteData);
    }
    chartRef.current?.timeScale().fitContent();

    // Fetch both benchmarks on first load
    if (!initialFetchDoneRef.current) {
      initialFetchDoneRef.current = true;
      fetchBenchmark('SPY');
      fetchBenchmark('QQQ');
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [snapshots]);

  /** Handle independent benchmark toggle (multi-select). */
  const handleToggle = useCallback(
    (values: string[]) => {
      const newActive = new Set(values as BenchmarkSymbol[]);
      const wasAnyActive = activeBenchmarks.size > 0;
      const isAnyNowActive = newActive.size > 0;

      for (const symbol of ['SPY', 'QQQ'] as const) {
        if (newActive.has(symbol) && !activeBenchmarks.has(symbol)) {
          // Newly activated — fetch data
          fetchBenchmark(symbol);
        } else if (!newActive.has(symbol) && activeBenchmarks.has(symbol)) {
          // Deactivated — clear series
          getSeriesRef(symbol).current?.setData([]);
        }
      }

      // Switch equity view mode if the "any benchmark active" state changed
      if (wasAnyActive !== isAnyNowActive) {
        setEquityMode(isAnyNowActive);
      }

      setActiveBenchmarks(newActive);
    },
    [activeBenchmarks, fetchBenchmark, setEquityMode],
  );

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

  const isAnyBenchmarkActive = activeBenchmarks.size > 0;
  const isAnyLoading = loadingBenchmarks.size > 0;

  return (
    <div className="space-y-3">
      {/* Controls row */}
      <div className="flex items-center justify-between">
        <span className="text-xs text-muted-foreground">
          {isAnyBenchmarkActive
            ? 'Cumulative return % — portfolio vs benchmark'
            : 'Portfolio equity (absolute)'}
        </span>

        <div className="flex items-center gap-2">
          <span className="text-xs text-muted-foreground">Benchmark</span>
          <ToggleGroup
            type="multiple"
            size="sm"
            value={[...activeBenchmarks]}
            onValueChange={handleToggle}
            aria-label="Toggle benchmark overlays"
          >
            {(['SPY', 'QQQ'] as const).map((symbol) => {
              const isActive = activeBenchmarks.has(symbol);
              const isLoading = loadingBenchmarks.has(symbol);
              const isErrored = errorBenchmarks.has(symbol);

              return (
                <ToggleGroupItem
                  key={symbol}
                  value={symbol}
                  aria-label={`Toggle ${BENCHMARK_CONFIG[symbol].label} benchmark`}
                  aria-pressed={isActive}
                  disabled={isAnyLoading}
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
          isAnyBenchmarkActive
            ? `Portfolio equity vs ${[...activeBenchmarks].join(' & ')} benchmark`
            : 'Portfolio equity over time'
        }
        data-testid="arena-equity-chart"
      />

      {/* Legend — always visible */}
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

        {/* Active benchmark series */}
        {(['SPY', 'QQQ'] as const).map((symbol) =>
          activeBenchmarks.has(symbol) && !loadingBenchmarks.has(symbol) ? (
            <div key={symbol} className="flex items-center gap-1.5">
              <span
                className="inline-block w-5"
                style={{
                  height: '2px',
                  backgroundImage: `repeating-linear-gradient(to right, ${BENCHMARK_CONFIG[symbol].color} 0, ${BENCHMARK_CONFIG[symbol].color} 4px, transparent 4px, transparent 7px)`,
                }}
                aria-hidden="true"
              />
              <span>{BENCHMARK_CONFIG[symbol].label}</span>
            </div>
          ) : null,
        )}
      </div>
    </div>
  );
};
