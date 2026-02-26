import { useEffect, useRef, useState } from 'react';
import {
  createChart,
  createSeriesMarkers,
  CandlestickSeries,
  LineSeries,
  HistogramSeries,
  type IChartApi,
  type ISeriesApi,
  type IPriceLine,
  type ISeriesMarkersPluginApi,
  type UTCTimestamp,
  type Time,
  type LineWidth,
} from 'lightweight-charts';
import type { StockPrice } from '../../../types/stock';
import type { ChartPriceLine, ChartMarker } from '../../../types/chart';
import { useChartTheme, useCandlestickStyle } from '../../../hooks/useChartTheme';
import { useChartZoom } from '../../../hooks/useChartZoom';
import { ChartLegend } from '../../molecules/ChartLegend/ChartLegend';
import { CHART_COLORS, CHART_PANE_CONFIG } from '../../../constants/chartColors';

interface CandlestickChartProps {
  data: StockPrice[];
  symbol: string;
  height?: number;
  className?: string;
  priceLines?: ChartPriceLine[];
  markers?: ChartMarker[];
  showMA20?: boolean;
}

/**
 * Professional candlestick chart component using TradingView Lightweight Charts
 *
 * Features:
 * - Mouse wheel zoom in/out
 * - High-performance canvas rendering
 * - Dark theme with improved visibility
 * - Zoom level persistence across sessions
 * - Professional grid lines and axis labels
 *
 * @param data - Array of OHLC stock price data
 * @param symbol - Stock symbol (for zoom persistence)
 * @param height - Chart height in pixels (default: 500)
 * @param className - Optional CSS classes
 */
export const CandlestickChart = ({
  data,
  symbol,
  height = 600,
  className = '',
  priceLines,
  markers,
  showMA20: showMA20Prop,
}: CandlestickChartProps) => {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null);
  const ma20SeriesRef = useRef<ISeriesApi<'Line'> | null>(null);
  const volumeSeriesRef = useRef<ISeriesApi<'Histogram'> | null>(null);
  const cciSeriesRef = useRef<ISeriesApi<'Line'> | null>(null);
  const cciMarkersRef = useRef<ISeriesMarkersPluginApi<Time> | null>(null);
  const resizeObserverRef = useRef<ResizeObserver | null>(null);
  const priceLineRefs = useRef<IPriceLine[]>([]);
  const markersPluginRef = useRef<ISeriesMarkersPluginApi<Time> | null>(null);

  const chartTheme = useChartTheme();
  const candlestickStyle = useCandlestickStyle();
  const { visibleRange, saveZoomState } = useChartZoom(symbol);

  const [isChartReady, setIsChartReady] = useState(false);
  // Default to true for backwards compatibility, but allow explicit override
  const [showMA20, setShowMA20] = useState(showMA20Prop !== false);
  const [showVolume, setShowVolume] = useState(true);
  const [showCCI, setShowCCI] = useState(true);

  // Initialize chart
  useEffect(() => {
    if (!chartContainerRef.current) return;

    // Create chart instance with pane separator styling
    const chart = createChart(chartContainerRef.current, {
      ...chartTheme,
      width: chartContainerRef.current.clientWidth,
      height,
      layout: {
        ...chartTheme.layout,
        panes: {
          separatorColor: '#374151',
          separatorHoverColor: '#4b5563',
          enableResize: true,
        },
      },
    });

    // Add candlestick series (pane 0 - main pane)
    const candlestickSeries = chart.addSeries(CandlestickSeries, {
      ...candlestickStyle,
      priceLineVisible: false,
      lastValueVisible: false,
    });

    // Add MA 20 line series (pane 0 - same as candlesticks)
    const ma20Series = chart.addSeries(LineSeries, {
      color: CHART_COLORS.MA_20,
      lineWidth: 2,
      priceLineVisible: false,
      lastValueVisible: false,
      crosshairMarkerVisible: false,
      title: 'MA 20',
    });

    // Add volume histogram series in SEPARATE PANE (pane 1)
    const volumeSeries = chart.addSeries(
      HistogramSeries,
      {
        color: CHART_COLORS.BULLISH, // Default green, will be overridden per-bar
        priceFormat: {
          type: 'volume',
        },
        priceLineVisible: false,
        lastValueVisible: false,
      },
      1 // paneIndex: 1 = separate pane for volume
    );

    // Set volume pane height
    const volumePane = chart.panes()[1];
    if (volumePane) {
      volumePane.setHeight(CHART_PANE_CONFIG.VOLUME_PANE_HEIGHT);
    }

    // Add CCI line series in SEPARATE PANE (pane 2)
    const cciSeries = chart.addSeries(
      LineSeries,
      {
        color: CHART_COLORS.CCI,
        lineWidth: 2,
        priceLineVisible: false,
        lastValueVisible: false,
        crosshairMarkerVisible: true,
      },
      2 // paneIndex: 2 = separate pane for CCI
    );

    // Set CCI pane height
    const cciPane = chart.panes()[2];
    if (cciPane) {
      cciPane.setHeight(CHART_PANE_CONFIG.CCI_PANE_HEIGHT);
    }

    // Add reference lines at +100 and -100
    cciSeries.createPriceLine({
      price: 100,
      color: CHART_COLORS.CCI_REFERENCE,
      lineWidth: 1,
      lineStyle: 2, // Dashed
      axisLabelVisible: false,
    });

    cciSeries.createPriceLine({
      price: -100,
      color: CHART_COLORS.CCI_REFERENCE,
      lineWidth: 1,
      lineStyle: 2, // Dashed
      axisLabelVisible: false,
    });

    cciSeries.createPriceLine({
      price: 0,
      color: CHART_COLORS.CCI_REFERENCE,
      lineWidth: 1,
      lineStyle: 0, // Solid
      axisLabelVisible: false,
    });

    // Store refs
    chartRef.current = chart;
    seriesRef.current = candlestickSeries;
    ma20SeriesRef.current = ma20Series;
    volumeSeriesRef.current = volumeSeries;
    cciSeriesRef.current = cciSeries;

    setIsChartReady(true);

    // Subscribe to visible range changes (for zoom persistence)
    chart.timeScale().subscribeVisibleLogicalRangeChange((range) => {
      if (range) {
        const timeScale = chart.timeScale();
        const from = timeScale.coordinateToTime(0) as number;
        const to = timeScale.coordinateToTime(chartContainerRef.current!.clientWidth) as number;

        // Calculate zoom level (0-1 based on visible range vs total range)
        const totalRange = data.length;
        const visibleCandles = range.to - range.from;
        const zoomLevel = Math.max(0, Math.min(1, 1 - visibleCandles / totalRange));

        saveZoomState(zoomLevel, { from, to });
      }
    });

    // Handle resize
    const resizeObserver = new ResizeObserver((entries) => {
      const { width: containerWidth } = entries[0].contentRect;
      chart.applyOptions({ width: containerWidth });
    });

    resizeObserver.observe(chartContainerRef.current);
    resizeObserverRef.current = resizeObserver;

    // Cleanup
    return () => {
      resizeObserver.disconnect();

      // Clear CCI markers
      if (cciMarkersRef.current) {
        cciMarkersRef.current.setMarkers([]);
        cciMarkersRef.current = null;
      }

      // Explicitly remove series before removing chart to prevent memory leaks
      if (cciSeriesRef.current) {
        chart.removeSeries(cciSeriesRef.current);
      }
      if (volumeSeriesRef.current) {
        chart.removeSeries(volumeSeriesRef.current);
      }
      if (ma20SeriesRef.current) {
        chart.removeSeries(ma20SeriesRef.current);
      }
      if (seriesRef.current) {
        chart.removeSeries(seriesRef.current);
      }

      cciSeriesRef.current = null;
      volumeSeriesRef.current = null;
      ma20SeriesRef.current = null;
      seriesRef.current = null;
      chart.remove();
    };
  }, [chartTheme, candlestickStyle, height, symbol, saveZoomState, data.length]);

  // Update data when it changes
  useEffect(() => {
    if (!seriesRef.current || !data || data.length === 0) return;

    // Convert StockPrice[] to Lightweight Charts format
    const chartData = data.map((item) => ({
      time: (new Date(item.date).getTime() / 1000) as UTCTimestamp,
      open: item.open,
      high: item.high,
      low: item.low,
      close: item.close,
    }));

    seriesRef.current.setData(chartData);

    // Update MA 20 series
    if (ma20SeriesRef.current) {
      const ma20Data = data
        .filter(item => item.ma_20 !== null && item.ma_20 !== undefined)
        .map(item => ({
          time: (new Date(item.date).getTime() / 1000) as UTCTimestamp,
          value: item.ma_20!,
        }));

      ma20SeriesRef.current.setData(ma20Data);
    }

    // Update volume series
    if (volumeSeriesRef.current) {
      const volumeData = data.map((item) => {
        // Determine if this is an up or down day
        const isUp = item.close >= item.open;
        return {
          time: (new Date(item.date).getTime() / 1000) as UTCTimestamp,
          value: item.volume,
          color: isUp ? CHART_COLORS.BULLISH : CHART_COLORS.BEARISH,
        };
      });

      volumeSeriesRef.current.setData(volumeData);
    }

    // Update CCI series
    if (cciSeriesRef.current) {
      const cciData = data
        .filter(item => item.cci !== null && item.cci !== undefined)
        .map(item => ({
          time: (new Date(item.date).getTime() / 1000) as UTCTimestamp,
          value: item.cci!,
        }));

      cciSeriesRef.current.setData(cciData);

      // Add signal markers using createSeriesMarkers (v5 API)
      const cciSignalMarkers = data
        .filter(item => item.cci_signal)
        .map(item => {
          const isBullish = item.cci_signal === 'momentum_bullish' || item.cci_signal === 'reversal_buy';
          return {
            time: (new Date(item.date).getTime() / 1000) as UTCTimestamp,
            position: 'inBar' as const,
            color: isBullish ? CHART_COLORS.CCI_BULLISH : CHART_COLORS.CCI_BEARISH,
            shape: 'circle' as const,
            size: 1,
          };
        });

      // Remove existing markers plugin if it exists
      if (cciMarkersRef.current) {
        cciMarkersRef.current.setMarkers([]);
      }

      // Create new markers plugin with markers
      if (cciSignalMarkers.length > 0) {
        cciMarkersRef.current = createSeriesMarkers(cciSeriesRef.current, cciSignalMarkers);
      }
    }

    // Restore visible range if available
    if (visibleRange && chartRef.current) {
      try {
        chartRef.current.timeScale().setVisibleRange({
          from: visibleRange.from as UTCTimestamp,
          to: visibleRange.to as UTCTimestamp,
        });
      } catch {
        // Silent fail - range is invalid (e.g., new data doesn't include saved range)
        // This is expected behavior when switching between stocks
      }
    } else if (chartRef.current) {
      // Fit content to show all data
      chartRef.current.timeScale().fitContent();
    }
  }, [data, visibleRange]);

  // Toggle MA 20 visibility
  useEffect(() => {
    if (!ma20SeriesRef.current) return;

    ma20SeriesRef.current.applyOptions({
      visible: showMA20,
    });
  }, [showMA20]);

  // Toggle volume visibility
  useEffect(() => {
    if (!volumeSeriesRef.current) return;

    volumeSeriesRef.current.applyOptions({
      visible: showVolume,
    });
  }, [showVolume]);

  // Toggle CCI visibility
  useEffect(() => {
    if (!cciSeriesRef.current) return;

    cciSeriesRef.current.applyOptions({
      visible: showCCI,
    });
  }, [showCCI]);

  // Create price lines
  useEffect(() => {
    if (!seriesRef.current || !priceLines) return;

    // Clean up existing price lines
    priceLineRefs.current.forEach((line) => {
      seriesRef.current?.removePriceLine(line);
    });
    priceLineRefs.current = [];

    // Create new price lines
    if (priceLines.length > 0) {
      priceLines.forEach((line) => {
        const priceLine = seriesRef.current!.createPriceLine({
          price: line.price,
          color: line.color,
          lineWidth: (line.lineWidth ?? 1) as LineWidth,
          lineStyle: line.lineStyle === 'dashed' ? 2 : line.lineStyle === 'dotted' ? 1 : 0,
          axisLabelVisible: line.labelVisible ?? true,
          title: line.label ?? '',
        });
        priceLineRefs.current.push(priceLine);
      });
    }

    return () => {
      // Cleanup on unmount
      priceLineRefs.current.forEach((line) => {
        seriesRef.current?.removePriceLine(line);
      });
      priceLineRefs.current = [];
    };
  }, [priceLines]);

  // Set markers using v5 plugin API
  useEffect(() => {
    if (!seriesRef.current || !markers) return;

    // Clean up existing markers plugin
    if (markersPluginRef.current) {
      markersPluginRef.current.detach();
      markersPluginRef.current = null;
    }

    // Create markers if provided
    if (markers.length > 0) {
      const chartMarkers = markers.map((marker) => ({
        time: (new Date(marker.date).getTime() / 1000) as UTCTimestamp,
        position: marker.position,
        shape: marker.shape,
        color: marker.color,
        text: marker.text ?? '',
        size: marker.size ?? 1,
      }));

      markersPluginRef.current = createSeriesMarkers(
        seriesRef.current,
        chartMarkers
      );
    }

    return () => {
      // Cleanup on unmount
      if (markersPluginRef.current) {
        markersPluginRef.current.detach();
        markersPluginRef.current = null;
      }
    };
  }, [markers]);

  // Empty state
  if (!data || data.length === 0) {
    return (
      <div
        className={`flex items-center justify-center ${className}`}
        style={{ height: `${height}px` }}
        role="status"
        aria-live="polite"
      >
        <div className="bg-black/40 p-8 rounded-lg border border-gray-700 w-full h-full flex items-center justify-center">
          <p className="text-gray-400">No data available</p>
        </div>
      </div>
    );
  }

  return (
    <div className={className}>
      {/* Chart controls header */}
      <div className="flex items-center justify-between mb-2">
        <ChartLegend />

        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowMA20(!showMA20)}
            className={`px-3 py-1.5 text-xs rounded-md transition-colors ${
              showMA20
                ? 'bg-blue-700 text-white hover:bg-blue-800'
                : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
            }`}
            aria-label={showMA20 ? 'Hide MA 20 indicator' : 'Show MA 20 indicator'}
            aria-pressed={showMA20}
          >
            MA 20
          </button>
          <button
            onClick={() => setShowVolume(!showVolume)}
            className={`px-3 py-1.5 text-xs rounded-md transition-colors ${
              showVolume
                ? 'bg-emerald-700 text-white hover:bg-emerald-800'
                : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
            }`}
            aria-label={showVolume ? 'Hide volume bars' : 'Show volume bars'}
            aria-pressed={showVolume}
          >
            Vol
          </button>
          <button
            onClick={() => setShowCCI(!showCCI)}
            className={`px-3 py-1.5 text-xs rounded-md transition-colors ${
              showCCI
                ? 'bg-purple-600 text-white hover:bg-purple-700'
                : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
            }`}
            aria-label={showCCI ? 'Hide CCI indicator' : 'Show CCI indicator'}
            aria-pressed={showCCI}
          >
            CCI
          </button>
        </div>
      </div>

      {/* Chart container */}
      <div
        ref={chartContainerRef}
        className="w-full rounded-lg border border-gray-700 bg-black"
        style={{ height: `${height}px` }}
        role="img"
        aria-label={`Candlestick chart for ${symbol}`}
        data-testid="candlestick-chart"
      />

      {!isChartReady && (
        <div className="absolute inset-0 flex items-center justify-center bg-black/50">
          <p className="text-gray-400">Loading chart...</p>
        </div>
      )}
    </div>
  );
};
