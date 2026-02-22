/**
 * ArenaComparison Page
 *
 * Displays a multi-strategy comparison group at /arena/compare/:groupId.
 * Shows live progress cards for all simulations, then reveals the summary
 * table when at least one is completed, and the equity chart when all are done.
 */
import { useNavigate, useParams } from 'react-router-dom';
import { ArrowLeft, Loader2 } from 'lucide-react';
import { Badge } from '../components/ui/badge';
import { Button } from '../components/ui/button';
import { Card, CardContent } from '../components/ui/card';
import { Progress } from '../components/ui/progress';
import { ArenaComparisonTable } from '../components/arena/ArenaComparisonTable';
import { ArenaComparisonChart } from '../components/arena/ArenaComparisonChart';
import { useComparisonPolling } from '../hooks/useComparisonPolling';
import { getStatusBadgeClass } from '../utils/arena';
import type { Simulation } from '../types/arena';

const TERMINAL_STATUSES = new Set(['completed', 'cancelled', 'failed']);

const getStrategy = (sim: Simulation): string => sim.portfolio_strategy ?? '—';

export const ArenaComparison = () => {
  const { groupId } = useParams<{ groupId: string }>();
  const navigate = useNavigate();

  const { data, isPolling, error } = useComparisonPolling(groupId ?? '');

  // Loading state — no data yet
  if (!data && !error) {
    return (
      <div className="container mx-auto px-6 py-8 flex items-center justify-center min-h-[400px]">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  // Hard error (e.g. 404) with no prior data
  if (!data) {
    return (
      <div className="container mx-auto px-6 py-8 flex items-center justify-center min-h-[400px]">
        <div className="text-center space-y-4">
          <p className="text-destructive">
            {error === 'Failed to load comparison'
              ? 'Comparison not found or failed to load.'
              : error}
          </p>
          <Button variant="outline" onClick={() => navigate('/arena')}>
            Back to Arena
          </Button>
        </div>
      </div>
    );
  }

  const simulations = data.simulations;

  const completedSims = simulations.filter((s) => s.status === 'completed');
  const allTerminal = simulations.every((s) => TERMINAL_STATUSES.has(s.status));
  const allCompleted = simulations.every((s) => s.status === 'completed');
  const allFailed = simulations.every(
    (s) => s.status === 'failed' || s.status === 'cancelled',
  );
  const someCompletedSomeCancelled =
    completedSims.length > 0 &&
    simulations.some((s) => s.status === 'cancelled' || s.status === 'failed') &&
    allTerminal;

  return (
    <div className="container mx-auto px-6 py-6 md:py-8 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => navigate('/arena')}
            aria-label="Back to Arena"
          >
            <ArrowLeft className="h-4 w-4 mr-1" />
            Back to Arena
          </Button>
          <h1 className="text-2xl font-bold font-display tracking-tight">
            Strategy Comparison
          </h1>
          {isPolling && (
            <Loader2
              className="h-4 w-4 animate-spin text-muted-foreground"
              aria-label="Polling for updates"
            />
          )}
        </div>
      </div>

      {/* Transient network error banner (keep polling) */}
      {error && data && (
        <div className="text-xs text-accent-bearish" role="alert">
          {error} — retrying...
        </div>
      )}

      {/* All failed / cancelled edge case */}
      {allFailed && (
        <Card>
          <CardContent className="pt-6">
            <p className="text-accent-bearish text-sm">
              All simulations in this comparison failed or were cancelled. No results are
              available.
            </p>
          </CardContent>
        </Card>
      )}

      {/* Mixed completion warning */}
      {someCompletedSomeCancelled && (
        <div className="text-xs text-amber-500 bg-amber-500/10 border border-amber-500/30 rounded-md px-3 py-2" role="alert">
          Some simulations were cancelled or failed. Partial results are shown below.
        </div>
      )}

      {/* Progress Cards */}
      <div
        className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4"
        data-testid="progress-cards"
      >
        {simulations.map((sim) => {
          const progress =
            sim.total_days > 0 ? (sim.current_day / sim.total_days) * 100 : 0;
          const strategy = getStrategy(sim);

          return (
            <Card key={sim.id} data-testid={`progress-card-${sim.id}`}>
              <CardContent className="pt-4 pb-4 space-y-2">
                <div className="flex items-center justify-between gap-2">
                  <span className="text-sm font-medium truncate">{strategy}</span>
                  <Badge className={`shrink-0 text-[10px] px-1.5 py-0 ${getStatusBadgeClass(sim.status)}`}>
                    {sim.status}
                  </Badge>
                </div>
                <Progress value={progress} className="h-1.5" />
                <p className="text-xs text-muted-foreground font-mono">
                  {sim.total_days > 0
                    ? `${sim.current_day} / ${sim.total_days} days`
                    : 'Initializing...'}
                </p>
              </CardContent>
            </Card>
          );
        })}
      </div>

      {/* Summary Table — shown when at least 1 simulation is completed */}
      {completedSims.length > 0 && (
        <div className="space-y-2">
          <h2 className="text-sm font-semibold">Performance Summary</h2>
          <ArenaComparisonTable simulations={simulations} />
        </div>
      )}

      {/* Equity Chart — shown only when ALL simulations are completed */}
      {allCompleted && (
        <Card>
          <CardContent className="pt-6">
            <h2 className="text-sm font-semibold mb-4">Equity Curve Comparison</h2>
            <ArenaComparisonChart simulations={completedSims} />
          </CardContent>
        </Card>
      )}
    </div>
  );
};
