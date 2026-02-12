import { useState, useEffect, useCallback } from 'react';
import { fetchSectorTrend, type SectorTrend } from '../../services/live20Service';
import { fetchStockDataByDateRange, fetchIndicators } from '../../services/stockService';
import type { Live20Result } from '../../types/live20';
import type { StockPrice, IndicatorData } from '../../types/stock';
import { CandlestickChart } from '../organisms/CandlestickChart/CandlestickChart';
import { Badge } from '../ui/badge';
import { Button } from '../ui/button';
import { Loader2, AlertCircle, TrendingUp, TrendingDown, Minus } from 'lucide-react';

interface ExpandedRowContentProps {
  result: Live20Result;
}

/**
 * Render trend direction icon with appropriate color
 */
function getTrendIcon(direction: SectorTrend['trend_direction']) {
  if (direction === 'up') return <TrendingUp className="h-4 w-4 text-accent-bullish" />;
  if (direction === 'down') return <TrendingDown className="h-4 w-4 text-accent-bearish" />;
  return <Minus className="h-4 w-4 text-text-muted" />;
}

/**
 * Get badge variant based on MA position relative to price
 */
function getMaBadgeVariant(position: 'above' | 'below'): 'default' | 'secondary' {
  return position === 'above' ? 'default' : 'secondary';
}

/**
 * Expandable row content showing sector trend indicators and stock chart
 *
 * Fetches:
 * - Sector trend data from the sector ETF (if available)
 * - 3 months of stock price data with indicators
 *
 * Displays:
 * - Left: Sector trend indicators (trend direction, MA positions)
 * - Right: Stock candlestick chart (all panes: candles+MA20, volume, CCI)
 */
export function ExpandedRowContent({ result }: ExpandedRowContentProps) {
  const [sectorTrend, setSectorTrend] = useState<SectorTrend | null>(null);
  const [stockData, setStockData] = useState<StockPrice[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [retryCount, setRetryCount] = useState(0);

  const fetchData = useCallback(async (signal: AbortSignal) => {
    setLoading(true);
    setError(null);

    try {
      // Calculate date range: 3 months back from today
      const endDate = new Date();
      const startDate = new Date();
      startDate.setMonth(startDate.getMonth() - 3);

      const startDateStr = startDate.toISOString().split('T')[0];
      const endDateStr = endDate.toISOString().split('T')[0];

      // Fetch sector trend and stock data in parallel
      const promises: [
        Promise<SectorTrend | null>,
        Promise<StockPrice[]>
      ] = [
        // Fetch sector trend if available
        result.sector_etf
          ? fetchSectorTrend(result.sector_etf).catch(() => null)
          : Promise.resolve(null),
        // Fetch stock prices and indicators, then merge
        (async () => {
          const [pricesData, indicatorsData] = await Promise.all([
            fetchStockDataByDateRange({
              symbol: result.stock,
              startDate: startDateStr,
              endDate: endDateStr,
              interval: '1d',
            }),
            fetchIndicators(result.stock, '1d'),
          ]);

          // Create a map of date -> indicator values for fast lookup
          const indicatorMap = new Map<string, IndicatorData>();
          indicatorsData.data.forEach((indicator) => {
            indicatorMap.set(indicator.date, indicator);
          });

          // Merge indicator data into price data by matching dates
          return pricesData.prices.map((price) => {
            const indicators = indicatorMap.get(price.date);
            return {
              ...price,
              ma_20: indicators?.ma_20,
              cci: indicators?.cci,
              cci_signal: indicators?.cci_signal,
            };
          });
        })(),
      ];

      const [trend, prices] = await Promise.all(promises);

      if (signal.aborted) return;

      setSectorTrend(trend);
      setStockData(prices);
    } catch (err) {
      if (signal.aborted) return;
      const errorMessage = err instanceof Error ? err.message : 'Failed to fetch data';
      setError(errorMessage);
    } finally {
      if (!signal.aborted) {
        setLoading(false);
      }
    }
  }, [result.stock, result.sector_etf]);

  useEffect(() => {
    const abortController = new AbortController();
    fetchData(abortController.signal);

    return () => {
      abortController.abort();
    };
  }, [fetchData, retryCount]);

  // Loading state
  if (loading) {
    return (
      <div className="px-6 py-8 bg-bg-tertiary">
        <div className="flex items-center justify-center gap-2 text-text-secondary">
          <Loader2 className="h-5 w-5 animate-spin" />
          <span>Loading sector trend and chart data...</span>
        </div>
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div className="px-6 py-8 bg-bg-tertiary">
        <div className="flex items-center justify-center gap-4">
          <div className="flex items-center gap-2 text-accent-bearish">
            <AlertCircle className="h-5 w-5" />
            <span>{error}</span>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={() => setRetryCount((c) => c + 1)}
          >
            Retry
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="px-6 py-6 bg-bg-tertiary border-t border-subtle">
      <div className="grid grid-cols-1 lg:grid-cols-[280px_1fr] gap-6">
        {/* Left: Sector Trend Indicators */}
        <div className="space-y-4">
          <h4 className="font-display text-sm font-semibold text-text-primary">
            Sector Trend Analysis
          </h4>

          {result.sector_etf && sectorTrend ? (
            <div className="space-y-3 text-sm">
              {/* Sector ETF */}
              <div className="flex items-center justify-between">
                <span className="text-text-secondary">Sector ETF</span>
                <span className="font-mono font-semibold text-text-primary">
                  {result.sector_etf}
                </span>
              </div>

              {/* Trend Direction */}
              <div className="flex items-center justify-between">
                <span className="text-text-secondary">Trend</span>
                <div className="flex items-center gap-1.5">
                  {getTrendIcon(sectorTrend.trend_direction)}
                  <span className="font-medium capitalize">{sectorTrend.trend_direction}</span>
                </div>
              </div>

              {/* MA20 Position */}
              <div className="flex items-center justify-between">
                <span className="text-text-secondary">MA20</span>
                <div className="flex items-center gap-2">
                  <Badge variant={getMaBadgeVariant(sectorTrend.ma20_position)}>
                    {sectorTrend.ma20_position}
                  </Badge>
                  <span
                    className={`font-mono text-xs ${
                      sectorTrend.ma20_distance_pct > 0
                        ? 'text-accent-bullish'
                        : 'text-accent-bearish'
                    }`}
                  >
                    {sectorTrend.ma20_distance_pct > 0 ? '+' : ''}
                    {sectorTrend.ma20_distance_pct.toFixed(1)}%
                  </span>
                </div>
              </div>

              {/* MA50 Position */}
              <div className="flex items-center justify-between">
                <span className="text-text-secondary">MA50</span>
                <div className="flex items-center gap-2">
                  <Badge variant={getMaBadgeVariant(sectorTrend.ma50_position)}>
                    {sectorTrend.ma50_position}
                  </Badge>
                  <span
                    className={`font-mono text-xs ${
                      sectorTrend.ma50_distance_pct > 0
                        ? 'text-accent-bullish'
                        : 'text-accent-bearish'
                    }`}
                  >
                    {sectorTrend.ma50_distance_pct > 0 ? '+' : ''}
                    {sectorTrend.ma50_distance_pct.toFixed(1)}%
                  </span>
                </div>
              </div>

              {/* 5-day change */}
              <div className="flex items-center justify-between">
                <span className="text-text-secondary">5-day change</span>
                <span
                  className={`font-mono text-xs ${
                    sectorTrend.price_change_5d_pct > 0
                      ? 'text-accent-bullish'
                      : 'text-accent-bearish'
                  }`}
                >
                  {sectorTrend.price_change_5d_pct > 0 ? '+' : ''}
                  {sectorTrend.price_change_5d_pct.toFixed(2)}%
                </span>
              </div>

              {/* 20-day change */}
              <div className="flex items-center justify-between">
                <span className="text-text-secondary">20-day change</span>
                <span
                  className={`font-mono text-xs ${
                    sectorTrend.price_change_20d_pct > 0
                      ? 'text-accent-bullish'
                      : 'text-accent-bearish'
                  }`}
                >
                  {sectorTrend.price_change_20d_pct > 0 ? '+' : ''}
                  {sectorTrend.price_change_20d_pct.toFixed(2)}%
                </span>
              </div>
            </div>
          ) : (
            <p className="text-sm text-text-muted italic">Sector info not available</p>
          )}
        </div>

        {/* Right: Stock Chart */}
        <div className="min-w-[400px]">
          <h4 className="font-display text-sm font-semibold text-text-primary mb-3">
            {result.stock} Chart (3 Months)
          </h4>
          {stockData.length > 0 ? (
            <CandlestickChart
              data={stockData}
              symbol={result.stock}
              height={600}
            />
          ) : (
            <div className="flex items-center justify-center h-[600px] border border-subtle rounded-lg bg-bg-secondary">
              <p className="text-text-muted">No chart data available</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
