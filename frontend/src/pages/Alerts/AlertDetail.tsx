import { useMemo, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft, Pause, Play, Trash2, RefreshCw, Loader2 } from 'lucide-react';
import { toast } from 'sonner';
import type { UTCTimestamp } from 'lightweight-charts';

import { Button } from '../../components/ui/button';
import { Skeleton } from '../../components/ui/skeleton';
import { Alert, AlertDescription, AlertTitle } from '../../components/ui/alert';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from '../../components/ui/alert-dialog';
import { CandlestickChart } from '../../components/organisms/CandlestickChart/CandlestickChart';
import { AlertInfoPanel } from '../../components/alerts/AlertInfoPanel';
import { getFibPriceLines, getFibMarkers } from '../../components/alerts/FibonacciChartOverlay';
import { useAlertDetail } from '../../hooks/useAlertDetail';
import { useAlerts } from '../../hooks/useAlerts';
import { isFibAlert, isMAAlert } from '../../types/alert';
import type { StockPrice } from '../../types/stock';
import type { ChartPriceLine, ChartMarker } from '../../types/chart';

/** Map raw API price records to the StockPrice shape CandlestickChart expects */
function toPriceData(raw: Record<string, unknown>[]): StockPrice[] {
  return raw.map((item) => ({
    date: (item.date ?? (item.timestamp as string)?.split('T')[0] ?? '') as string,
    open: Number(item.open),
    high: Number(item.high),
    low: Number(item.low),
    close: Number(item.close),
    volume: Number(item.volume ?? 0),
    ma_20: item.ma_20 != null ? Number(item.ma_20) : undefined,
    cci: item.cci != null ? Number(item.cci) : undefined,
    cci_signal: item.cci_signal as StockPrice['cci_signal'] | undefined,
  }));
}

/**
 * Compute a Simple Moving Average series from price data.
 *
 * Returns only data points where we have enough prior values (i.e., index >= period - 1).
 */
function computeMA(
  prices: StockPrice[],
  period: number
): { time: UTCTimestamp; value: number }[] {
  const result: { time: UTCTimestamp; value: number }[] = [];
  for (let i = period - 1; i < prices.length; i++) {
    let sum = 0;
    for (let j = i - period + 1; j <= i; j++) {
      sum += prices[j].close;
    }
    result.push({
      time: (new Date(prices[i].date).getTime() / 1000) as UTCTimestamp,
      value: sum / period,
    });
  }
  return result;
}

/** MA series color palette — cycle when there are multiple MA periods */
const MA_COLORS = ['#f59e0b', '#a78bfa', '#34d399', '#fb923c', '#60a5fa'];

/**
 * Alert Detail page
 *
 * Shows the full chart with alert overlays (Fibonacci levels / MA lines) and
 * an info panel with current state and event history.
 */
export function AlertDetail() {
  const { alertId } = useParams<{ alertId: string }>();
  const navigate = useNavigate();
  const id = alertId ? Number(alertId) : null;

  const { alert, events, priceData, isLoading, error, refetch } = useAlertDetail(id);
  const { updateAlert, deleteAlert, isLoading: isMutating } = useAlerts();

  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);

  // --- Derived chart data ---

  const prices = useMemo<StockPrice[]>(
    () => (priceData ? toPriceData(priceData.data) : []),
    [priceData]
  );

  const fibPriceLines = useMemo<ChartPriceLine[]>(() => {
    if (!alert || !isFibAlert(alert) || !alert.computed_state) return [];
    return getFibPriceLines(alert.computed_state, alert.config.levels);
  }, [alert]);

  const fibMarkers = useMemo<ChartMarker[]>(() => {
    if (!alert || !isFibAlert(alert) || !alert.computed_state) return [];
    return getFibMarkers(alert.computed_state);
  }, [alert]);

  /** Extra MA line series for MA alerts */
  const maLineSeries = useMemo(() => {
    if (!alert || !isMAAlert(alert) || prices.length === 0) return undefined;

    const period = alert.config.ma_period;

    // If we already have ma_20 in the price data and the period is 20, skip (chart shows it natively)
    if (period === 20) return undefined;

    const data = computeMA(prices, period);
    if (data.length === 0) return undefined;

    return [
      {
        label: `MA${period}`,
        color: MA_COLORS[0],
        data,
      },
    ];
  }, [alert, prices]);

  // --- Actions ---

  const handlePauseResume = async () => {
    if (!alert) return;
    const newPaused = !alert.is_paused;
    try {
      await updateAlert(alert.id, { is_paused: newPaused });
      toast.success(newPaused ? 'Alert paused' : 'Alert resumed');
      await refetch();
    } catch {
      toast.error(newPaused ? 'Failed to pause alert' : 'Failed to resume alert');
    }
  };

  const handleDelete = async () => {
    if (!alert) return;
    try {
      await deleteAlert(alert.id);
      toast.success(`Alert for ${alert.symbol} deleted`);
      navigate('/alerts');
    } catch {
      toast.error('Failed to delete alert');
    }
  };

  // --- Render states ---

  if (isLoading) {
    return (
      <div className="flex-1 p-6 flex flex-col gap-5 max-w-[1200px] mx-auto w-full">
        {/* Back + actions skeleton */}
        <div className="flex items-center justify-between gap-4">
          <Skeleton className="h-9 w-28 rounded-md" />
          <div className="flex gap-2">
            <Skeleton className="h-9 w-24 rounded-md" />
            <Skeleton className="h-9 w-20 rounded-md" />
          </div>
        </div>

        {/* Chart skeleton */}
        <Skeleton className="h-[480px] w-full rounded-lg" />

        {/* Info panel skeleton */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <Skeleton className="h-48 w-full rounded-lg" />
          <Skeleton className="h-48 w-full rounded-lg" />
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex-1 p-6 flex flex-col gap-5 max-w-[1200px] mx-auto w-full">
        <Button
          variant="ghost"
          size="sm"
          onClick={() => navigate('/alerts')}
          className="self-start flex items-center gap-1.5 text-text-muted"
        >
          <ArrowLeft className="w-4 h-4" />
          Back to Alerts
        </Button>

        <Alert variant="destructive">
          <AlertTitle>Failed to load alert</AlertTitle>
          <AlertDescription className="mt-2 flex items-center gap-3">
            <span>{error}</span>
            <Button
              variant="outline"
              size="sm"
              onClick={refetch}
              className="shrink-0 flex items-center gap-1.5"
            >
              <RefreshCw className="w-3.5 h-3.5" />
              Retry
            </Button>
          </AlertDescription>
        </Alert>
      </div>
    );
  }

  if (!alert) {
    return (
      <div className="flex-1 p-6 flex flex-col gap-5 max-w-[1200px] mx-auto w-full">
        <Button
          variant="ghost"
          size="sm"
          onClick={() => navigate('/alerts')}
          className="self-start flex items-center gap-1.5 text-text-muted"
        >
          <ArrowLeft className="w-4 h-4" />
          Back to Alerts
        </Button>

        <div className="py-16 text-center">
          <p className="text-text-primary font-medium text-lg mb-2">Alert not found</p>
          <p className="text-text-muted text-sm mb-6">
            This alert may have been deleted or the ID is invalid.
          </p>
          <Button onClick={() => navigate('/alerts')}>Back to Alerts</Button>
        </div>
      </div>
    );
  }

  const isPaused = alert.is_paused;

  return (
    <div className="flex-1 p-6 flex flex-col gap-5 max-w-[1200px] mx-auto w-full">
      {/* Header row: back button + symbol + quick actions */}
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <div className="flex items-center gap-3">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => navigate('/alerts')}
            className="flex items-center gap-1.5 text-text-muted"
            aria-label="Back to alerts"
          >
            <ArrowLeft className="w-4 h-4" />
            Alerts
          </Button>

          <div className="text-text-muted select-none">/</div>

          <h1 className="font-display text-xl font-bold tracking-tight text-text-primary">
            {alert.symbol}
          </h1>
        </div>

        <div className="flex items-center gap-2">
          {/* Pause / Resume */}
          <Button
            variant="outline"
            size="sm"
            onClick={handlePauseResume}
            disabled={isMutating}
            className="flex items-center gap-1.5"
            aria-label={isPaused ? 'Resume alert' : 'Pause alert'}
          >
            {isMutating && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
            {!isMutating && isPaused && <Play className="w-3.5 h-3.5" />}
            {!isMutating && !isPaused && <Pause className="w-3.5 h-3.5" />}
            {isPaused ? 'Resume' : 'Pause'}
          </Button>

          {/* Delete with confirmation */}
          <AlertDialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
            <AlertDialogTrigger asChild>
              <Button
                variant="outline"
                size="sm"
                disabled={isMutating}
                className="flex items-center gap-1.5 text-destructive border-destructive/50 hover:bg-destructive/10"
                aria-label="Delete alert"
              >
                <Trash2 className="w-3.5 h-3.5" />
                Delete
              </Button>
            </AlertDialogTrigger>
            <AlertDialogContent>
              <AlertDialogHeader>
                <AlertDialogTitle>Delete alert?</AlertDialogTitle>
                <AlertDialogDescription>
                  This will permanently delete the {alert.symbol} alert and all its event history.
                  This action cannot be undone.
                </AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogCancel>Cancel</AlertDialogCancel>
                <AlertDialogAction
                  onClick={handleDelete}
                  className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                >
                  Delete
                </AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>
        </div>
      </div>

      {/* Chart */}
      <CandlestickChart
        data={prices}
        symbol={alert.symbol}
        height={480}
        priceLines={isFibAlert(alert) ? fibPriceLines : undefined}
        markers={isFibAlert(alert) ? fibMarkers : undefined}
        extraLineSeries={isMAAlert(alert) ? maLineSeries : undefined}
        showMA20={(isMAAlert(alert) && alert.config.ma_period === 20) || undefined}
      />

      {/* Info panel */}
      <AlertInfoPanel alert={alert} events={events} />

      {/* Mutation loading indicator */}
      {isMutating && (
        <div
          className="fixed bottom-6 right-6 flex items-center gap-2 px-3 py-2 rounded-md bg-bg-secondary border border-default shadow-lg text-sm text-text-muted z-50"
          role="status"
          aria-label="Saving..."
        >
          <Loader2 className="w-4 h-4 animate-spin" />
          Saving...
        </div>
      )}
    </div>
  );
}
