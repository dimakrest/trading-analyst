import { Card, CardContent } from '../ui/card';
import { Progress } from '../ui/progress';
import { Button } from '../ui/button';
import { TrendingUp, Loader2 } from 'lucide-react';

interface Live20LoadingProps {
  /** Number of symbols being analyzed */
  symbolCount: number;
  /** Number of symbols processed so far */
  processedCount?: number;
  /** Current status */
  status?: string;
  /** Number of results found so far */
  resultsCount?: number;
  /** Callback to cancel the analysis */
  onCancel?: () => void;
  /** Whether cancellation is in progress */
  isCancelling?: boolean;
}

/**
 * Loading indicator for Live 20 analysis
 *
 * Displays a progress indicator with symbol count and processing status
 * while Live 20 mean reversion analysis is in progress.
 *
 * When processedCount is provided, shows a determinate progress bar.
 * Otherwise, shows an indeterminate progress bar.
 *
 * @param props - Component props
 * @param props.symbolCount - Total number of symbols being analyzed
 * @param props.processedCount - Number of symbols processed so far (optional)
 * @param props.status - Current status: 'pending', 'running', etc (optional)
 * @param props.resultsCount - Number of setups found so far (optional)
 * @param props.onCancel - Callback to cancel the analysis (optional)
 * @param props.isCancelling - Whether cancellation is in progress (optional)
 */
export function Live20Loading({ symbolCount, processedCount, status, resultsCount, onCancel, isCancelling }: Live20LoadingProps) {
  const hasProgress = processedCount !== undefined && processedCount > 0;
  const progressPercent = hasProgress ? Math.round((processedCount / symbolCount) * 100) : 0;

  // Determine the status message
  const statusMessage = status === 'pending'
    ? 'Queued for processing...'
    : status === 'running'
      ? 'Evaluating mean reversion criteria'
      : 'Starting analysis...';

  return (
    <Card>
      <CardContent className="py-12">
        <div className="flex flex-col items-center justify-center space-y-4">
          <TrendingUp className="h-12 w-12 text-primary animate-pulse" />
          <p className="text-lg font-medium">
            Analyzing {symbolCount} symbol{symbolCount !== 1 ? 's' : ''}...
          </p>
          {hasProgress ? (
            <>
              <Progress value={progressPercent} className="w-64 h-2" />
              <p className="text-sm font-medium text-muted-foreground">
                {processedCount} of {symbolCount} processed ({progressPercent}%)
              </p>
            </>
          ) : (
            <Progress indeterminate className="w-64 h-2" />
          )}
          <p className="text-sm text-muted-foreground">
            {statusMessage}
          </p>
          {resultsCount !== undefined && resultsCount > 0 && (
            <p className="text-sm font-medium text-primary">
              {resultsCount} setup{resultsCount !== 1 ? 's' : ''} found
            </p>
          )}
          {onCancel && (
            <Button
              variant="outline"
              onClick={onCancel}
              disabled={isCancelling}
              className="mt-2"
            >
              {isCancelling ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Cancelling...
                </>
              ) : (
                'Cancel Analysis'
              )}
            </Button>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
