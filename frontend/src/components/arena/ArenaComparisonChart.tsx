/**
 * ArenaComparisonChart
 *
 * Multi-series equity chart overlaying all completed strategies on one axis.
 * Each strategy gets a solid line from STRATEGY_COLORS. Benchmarks (SPY/QQQ)
 * are shown as dashed lines with independent toggles.
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
import { useChartTheme } from '../../hooks/useChartTheme';
import { CHART_COLORS, STRATEGY_COLORS } from '../../constants/chartColors';
import { getBenchmarkData, getSimulation } from '../../services/arenaService';
import { ToggleGroup, ToggleGroupItem } from '../ui/toggle-group';
import type { Simulation, SimulationDetail } from '../../types/arena';

interface ArenaComparisonChartProps {
  /** All completed simulations in the comparison group */
  simulations: Simulation[];
}

type BenchmarkSymbol = 'SPY' | 'QQQ';

const BENCHMARK_CONFIG: Record<BenchmarkSymbol, { color: string; label: string }> = {
  SPY: { color: CHART_COLORS.SPY, label: 'S&P 500' },
  QQQ: { color: CHART_COLORS.QQQ, label: 'QQQ' },
};

const PERCENT_PRICE_FORMAT = {
  type: 'custom' as const,
  formatter: (price: number) => price.toFixed(2) + '%',
};

const CHART_HEIGHT = 320;

export const ArenaComparisonChart = ({ simulations }: ArenaComparisonChartProps) => {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  // Strategy series keyed by simulation id
  const strategySeriesRef = useRef<Map<number, ISeriesApi<'Line'>>>(new Map());
  const spySeriesRef = useRef<ISeriesApi<'Line'> | null>(null);
  const qqqSeriesRef = useRef<ISeriesApi<'Line'> | null>(null);

  const chartTheme = useChartTheme();

  const [isLoading, setIsLoading] = useState(true);
  const [failedStrategies, setFailedStrategies] = useState<string[]>([]);
  // Track loaded details so we know which simulation to use for benchmark date range
  const [benchmarkSimId, setBenchmarkSimId] = useState<number | null>(null);

  const [activeBenchmarks, setActiveBenchmarks] = useState<Set<BenchmarkSymbol>>(
    () => new Set<BenchmarkSymbol>(['SPY', 'QQQ']),
  );
  const [loadingBenchmarks, setLoadingBenchmarks] = useState<Set<BenchmarkSymbol>>(
    () => new Set<BenchmarkSymbol>(),
  );
  const [errorBenchmarks, setErrorBenchmarks] = useState<Set<BenchmarkSymbol>>(
    () => new Set<BenchmarkSymbol>(),
  );

  // Initialize chart on mount
  useEffect(() => {
    if (!chartContainerRef.current) return;

    const chart = createChart(chartContainerRef.current, {
      ...chartTheme,
      width: chartContainerRef.current.clientWidth,
      height: CHART_HEIGHT,
    });

    // Add one strategy series per simulation
    simulations.forEach((sim, idx) => {
      const color = STRATEGY_COLORS[idx % STRATEGY_COLORS.length];
      const series = chart.addSeries(LineSeries, {
        color,
        lineWidth: 2,
        priceLineVisible: false,
        lastValueVisible: false,
        crosshairMarkerVisible: true,
        priceFormat: PERCENT_PRICE_FORMAT,
      });
      strategySeriesRef.current.set(sim.id, series);
    });

    // SPY series — dashed
    const spySeries = chart.addSeries(LineSeries, {
      color: CHART_COLORS.SPY,
      lineWidth: 2,
      lineStyle: LineStyle.Dashed,
      priceLineVisible: false,
      lastValueVisible: false,
      crosshairMarkerVisible: true,
      priceFormat: PERCENT_PRICE_FORMAT,
    });

    // QQQ series — dashed
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
    spySeriesRef.current = spySeries;
    qqqSeriesRef.current = qqqSeries;

    const resizeObserver = new ResizeObserver((entries) => {
      const { width } = entries[0].contentRect;
      chart.applyOptions({ width });
    });
    resizeObserver.observe(chartContainerRef.current);

    return () => {
      resizeObserver.disconnect();
      strategySeriesRef.current.forEach((series) => {
        try {
          chart.removeSeries(series);
        } catch {
          // chart may already be removed
        }
      });
      strategySeriesRef.current.clear();
      if (qqqSeriesRef.current) {
        chart.removeSeries(qqqSeriesRef.current);
        qqqSeriesRef.current = null;
      }
      if (spySeriesRef.current) {
        chart.removeSeries(spySeriesRef.current);
        spySeriesRef.current = null;
      }
      chart.remove();
      chartRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [chartTheme]);

  // Fetch all simulation details in parallel and populate series
  useEffect(() => {
    if (simulations.length === 0) return;
    let cancelled = false;

    const fetchAll = async () => {
      setIsLoading(true);

      const results = await Promise.allSettled(
        simulations.map((sim) => getSimulation(sim.id)),
      );

      if (cancelled) return;

      const failed: string[] = [];
      let firstSuccessSimId: number | null = null;

      results.forEach((result, idx) => {
        const sim = simulations[idx];
        const series = strategySeriesRef.current.get(sim.id);
        if (!series) return;

        if (result.status === 'rejected') {
          failed.push(sim.portfolio_strategy ?? `Simulation #${sim.id}`);
          return;
        }

        const detail: SimulationDetail = result.value;
        const snapshots = detail.snapshots;
        if (snapshots.length < 2) return;

        const firstEquity = parseFloat(snapshots[0].total_equity) || 1;
        const normalizedData = snapshots.map((s) => ({
          time: (new Date(s.snapshot_date).getTime() / 1000) as UTCTimestamp,
          value: ((parseFloat(s.total_equity) - firstEquity) / firstEquity) * 100,
        }));

        series.setData(normalizedData);

        if (firstSuccessSimId === null) {
          firstSuccessSimId = sim.id;
        }
      });

      setFailedStrategies(failed);
      setBenchmarkSimId(firstSuccessSimId);
      setIsLoading(false);

      chartRef.current?.timeScale().fitContent();
    };

    fetchAll();
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [simulations]);

  const getSeriesRef = (symbol: BenchmarkSymbol) =>
    symbol === 'SPY' ? spySeriesRef : qqqSeriesRef;

  const fetchBenchmark = useCallback(
    async (symbol: BenchmarkSymbol) => {
      if (benchmarkSimId === null) return;
      const seriesRef = getSeriesRef(symbol);
      if (!seriesRef.current) return;

      setLoadingBenchmarks((prev) => new Set(prev).add(symbol));
      setErrorBenchmarks((prev) => {
        const next = new Set(prev);
        next.delete(symbol);
        return next;
      });

      try {
        const data = await getBenchmarkData(benchmarkSimId, symbol);
        if (data.length === 0) throw new Error('No data');
        const timeData = data.map((p) => ({
          time: (new Date(p.date).getTime() / 1000) as UTCTimestamp,
          value: parseFloat(p.cumulative_return_pct),
        }));
        seriesRef.current.setData(timeData);
        chartRef.current?.timeScale().fitContent();
      } catch {
        setErrorBenchmarks((prev) => new Set(prev).add(symbol));
        setActiveBenchmarks((prev) => {
          const next = new Set(prev);
          next.delete(symbol);
          return next;
        });
        seriesRef.current?.setData([]);
      } finally {
        setLoadingBenchmarks((prev) => {
          const next = new Set(prev);
          next.delete(symbol);
          return next;
        });
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [benchmarkSimId],
  );

  // Auto-fetch benchmarks once the simulation data is ready
  const initialBenchmarkFetchDoneRef = useRef(false);
  useEffect(() => {
    if (benchmarkSimId === null) return;
    if (initialBenchmarkFetchDoneRef.current) return;
    initialBenchmarkFetchDoneRef.current = true;
    fetchBenchmark('SPY');
    fetchBenchmark('QQQ');
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [benchmarkSimId]);

  const handleToggle = useCallback(
    (values: string[]) => {
      const newActive = new Set(values as BenchmarkSymbol[]);

      for (const symbol of ['SPY', 'QQQ'] as const) {
        if (newActive.has(symbol) && !activeBenchmarks.has(symbol)) {
          fetchBenchmark(symbol);
        } else if (!newActive.has(symbol) && activeBenchmarks.has(symbol)) {
          getSeriesRef(symbol).current?.setData([]);
        }
      }

      setActiveBenchmarks(newActive);
    },
    [activeBenchmarks, fetchBenchmark],
  );

  if (isLoading) {
    return (
      <div
        className="flex items-center justify-center rounded-lg border border-gray-700 bg-black"
        style={{ height: `${CHART_HEIGHT}px` }}
        role="status"
        aria-label="Loading comparison chart"
        data-testid="comparison-chart-loading"
      >
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  const isAnyLoading = loadingBenchmarks.size > 0;

  return (
    <div className="space-y-3">
      {/* Partial failure warning */}
      {failedStrategies.length > 0 && (
        <p className="text-xs text-accent-bearish" role="alert">
          Failed to load data for: {failedStrategies.join(', ')}
        </p>
      )}

      {/* Controls row */}
      <div className="flex items-center justify-between">
        <span className="text-xs text-muted-foreground">
          Cumulative return % — all strategies vs benchmark
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
              const isSymbolLoading = loadingBenchmarks.has(symbol);
              const isErrored = errorBenchmarks.has(symbol);

              return (
                <ToggleGroupItem
                  key={symbol}
                  value={symbol}
                  aria-label={`Toggle ${BENCHMARK_CONFIG[symbol].label} benchmark`}
                  aria-pressed={isActive}
                  disabled={isAnyLoading}
                  className={isErrored ? 'text-accent-bearish' : undefined}
                  data-testid={`comparison-benchmark-toggle-${symbol.toLowerCase()}`}
                >
                  {isSymbolLoading ? (
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
        style={{ height: `${CHART_HEIGHT}px` }}
        role="img"
        aria-label="Strategy comparison equity curves"
        data-testid="arena-comparison-chart"
      />

      {/* Legend */}
      <div
        className="flex flex-wrap items-center gap-4 text-xs text-muted-foreground"
        data-testid="comparison-chart-legend"
      >
        {simulations.map((sim, idx) => {
          const color = STRATEGY_COLORS[idx % STRATEGY_COLORS.length];
          const strategy = sim.portfolio_strategy ?? `Simulation #${sim.id}`;
          return (
            <div key={sim.id} className="flex items-center gap-1.5">
              <span
                className="inline-block h-0.5 w-5 rounded-full"
                style={{ backgroundColor: color }}
                aria-hidden="true"
              />
              <span>{strategy}</span>
            </div>
          );
        })}

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
