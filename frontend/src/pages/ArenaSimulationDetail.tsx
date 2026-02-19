/**
 * Arena Simulation Detail Page
 *
 * Displays simulation progress, portfolio status, positions, and results.
 * Worker processes simulation in background; this page polls for updates.
 */
import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  ArrowLeft,
  Loader2,
  RotateCcw,
  Trash2,
  XCircle,
} from 'lucide-react';
import { toast } from 'sonner';
import { ArenaConfigPanel } from '../components/arena/ArenaConfigPanel';
import { ArenaDecisionLog } from '../components/arena/ArenaDecisionLog';
import { ArenaEquityChart } from '../components/arena/ArenaEquityChart';
import { ArenaMonthlyPnl } from '../components/arena/ArenaMonthlyPnl';
import { ArenaPortfolio } from '../components/arena/ArenaPortfolio';
import { ArenaPortfolioComposition } from '../components/arena/ArenaPortfolioComposition';
import { ArenaSectorBreakdown } from '../components/arena/ArenaSectorBreakdown';
import { ArenaResultsTable } from '../components/arena/ArenaResultsTable';
import { ArenaTradeFrequency } from '../components/arena/ArenaTradeFrequency';
import { CancelAnalysisDialog, DeleteAnalysisDialog } from '../components/common';
import { Badge } from '../components/ui/badge';
import { Button } from '../components/ui/button';
import { Card, CardContent } from '../components/ui/card';
import { Progress } from '../components/ui/progress';
import { useArenaPolling } from '../hooks/useArenaPolling';
import { cancelSimulation, deleteSimulation } from '../services/arenaService';
import { getPositionsForSnapshot, getStatusBadgeClass } from '../utils/arena';
import type { Snapshot } from '../types/arena';

/**
 * Arena Simulation Detail Page
 *
 * Features:
 * - Header with navigation, simulation name, status badge
 * - Progress bar showing current day / total days
 * - Results table with metrics
 * - Portfolio summary with open positions
 * - Decision log with day selector
 * - Cancel button for active simulations
 * - Delete button for completed simulations
 */
export const ArenaSimulationDetail = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const simulationId = id ? parseInt(id, 10) : null;

  // Poll for updates
  const { detail, isPolling, error, refetch } = useArenaPolling(simulationId);

  // Track currently selected snapshot for decision log
  const [currentSnapshot, setCurrentSnapshot] = useState<Snapshot | null>(null);

  // Cancel/Delete state
  const [showCancelDialog, setShowCancelDialog] = useState(false);
  const [showDeleteDialog, setShowDeleteDialog] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);

  // Update current snapshot when detail changes (auto-select latest)
  useEffect(() => {
    if (detail?.snapshots.length) {
      setCurrentSnapshot(detail.snapshots[detail.snapshots.length - 1]);
    }
  }, [detail?.snapshots]);

  // Show completion toast
  useEffect(() => {
    if (detail?.simulation.status === 'completed' && !isPolling) {
      toast.success('Simulation complete!');
    }
  }, [detail?.simulation.status, isPolling]);

  // Check if simulation is active (can be cancelled)
  const isSimulationActive =
    detail?.simulation.status === 'pending' ||
    detail?.simulation.status === 'running' ||
    detail?.simulation.status === 'paused';

  // Handle cancel
  const handleCancel = async () => {
    if (!id) return;

    setIsProcessing(true);
    try {
      await cancelSimulation(parseInt(id, 10));
      await refetch(); // Immediately refresh for instant UI feedback
      setShowCancelDialog(false);
      toast.success('Simulation cancelled');
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to cancel simulation';
      toast.error(errorMessage);
    } finally {
      setIsProcessing(false);
    }
  };

  // Handle delete
  const handleDelete = async () => {
    if (!id) return;

    setIsProcessing(true);
    try {
      await deleteSimulation(parseInt(id, 10));
      navigate('/arena');
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to delete simulation';
      toast.error(errorMessage);
      setShowDeleteDialog(false);
    } finally {
      setIsProcessing(false);
    }
  };

  // Handle replay - navigate to Arena with simulation parameters
  const handleReplay = () => {
    if (detail?.simulation) {
      navigate('/arena', { state: { replaySimulation: detail.simulation } });
    }
  };

  // Loading state
  if (!detail) {
    return (
      <div className="container mx-auto px-6 py-8 flex items-center justify-center min-h-[400px]">
        {error ? (
          <div className="text-center">
            <p className="text-destructive mb-4">Failed to load simulation</p>
            <Button variant="outline" onClick={() => navigate('/arena')}>
              Back to Arena
            </Button>
          </div>
        ) : (
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        )}
      </div>
    );
  }

  const { simulation, positions, snapshots } = detail;
  const progress =
    simulation.total_days > 0
      ? (simulation.current_day / simulation.total_days) * 100
      : 0;

  const isActive = simulation.status === 'pending' || simulation.status === 'running';
  const isComplete = simulation.status === 'completed';
  const isCancelled = simulation.status === 'cancelled';
  const isFailed = simulation.status === 'failed';

  // Filter positions to show those open at EOD on the selected snapshot date
  const openPositions = getPositionsForSnapshot(positions, currentSnapshot);

  // Latest snapshot — fixed reference independent of the day-selector.
  // Used by ArenaPortfolioComposition so position concentration stays stable
  // regardless of which day the user is browsing in ArenaDecisionLog.
  const latestSnapshot = snapshots.at(-1) ?? null;

  return (
    <div className="container mx-auto px-6 py-6 md:py-8 space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-start gap-4">
          <Button
            variant="ghost"
            size="icon"
            onClick={() => navigate('/arena')}
            aria-label="Back to Arena"
            className="mt-1"
          >
            <ArrowLeft className="h-5 w-5" />
          </Button>
          <div className="space-y-1">
            <div className="flex items-center gap-3">
              <h1 className="text-2xl font-bold font-display tracking-tight">
                {simulation.name || `Simulation #${simulation.id}`}
              </h1>
              <Badge className={getStatusBadgeClass(simulation.status)}>
                {simulation.status}
              </Badge>
              {isPolling && (
                <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
              )}
            </div>
            {simulation.stock_list_name && (
              <p className="text-sm text-muted-foreground">
                {simulation.stock_list_name}
              </p>
            )}
          </div>
        </div>
        <div className="flex gap-2 shrink-0">
          {/* Replay button - always visible when we have data */}
          <Button
            variant="outline"
            onClick={handleReplay}
            aria-label="Replay simulation with these parameters"
          >
            <RotateCcw className="h-4 w-4 mr-2" />
            Replay
          </Button>
          {isSimulationActive ? (
            <Button
              variant="outline"
              size="sm"
              onClick={() => setShowCancelDialog(true)}
              disabled={isProcessing}
            >
              <XCircle className="mr-2 h-4 w-4" />
              Cancel
            </Button>
          ) : (
            <Button
              variant="destructive"
              size="sm"
              onClick={() => setShowDeleteDialog(true)}
              disabled={isProcessing}
            >
              <Trash2 className="mr-2 h-4 w-4" />
              Delete
            </Button>
          )}
        </div>
      </div>

      {/* Configuration Panel */}
      <ArenaConfigPanel simulation={simulation} />

      {/* Progress */}
      <Card>
        <CardContent className="pt-6">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm">
              Day <span className="font-mono">{simulation.current_day}</span> of <span className="font-mono">{simulation.total_days || '?'}</span>
            </span>
            <span className="text-sm font-mono font-medium">
              {simulation.total_days > 0
                ? `${Math.round(progress)}%`
                : 'Initializing...'}
            </span>
          </div>
          <Progress value={progress} className="h-2" />

          <div className="mt-4 text-sm text-muted-foreground">
            {isActive && 'Processing in background...'}
            {isComplete && (
              <span className="text-accent-bullish font-medium">
                Simulation Complete
              </span>
            )}
            {isCancelled && (
              <span className="text-text-muted">
                Simulation was cancelled
              </span>
            )}
            {isFailed && (
              <span className="text-accent-bearish">
                Simulation failed
              </span>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Results Table */}
      <ArenaResultsTable simulation={simulation} />

      {/* Portfolio & Decisions */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <ArenaPortfolio
          simulation={simulation}
          positions={openPositions}
          snapshot={currentSnapshot}
        />
        <ArenaDecisionLog
          snapshot={currentSnapshot}
          snapshots={snapshots}
          onSelectSnapshot={setCurrentSnapshot}
        />
      </div>

      {/* Portfolio Composition Analytics */}
      {positions.length > 0 && (
        <ArenaPortfolioComposition
          positions={positions}
          snapshot={latestSnapshot}
          simulation={simulation}
        />
      )}

      {/* Sector Breakdown */}
      {positions.length > 0 && (
        <ArenaSectorBreakdown
          positions={positions}
          snapshot={latestSnapshot}
        />
      )}

      {/* Equity Curve Chart */}
      {isComplete && snapshots.length > 0 && (
        <Card>
          <CardContent className="pt-6">
            <h2 className="text-sm font-semibold mb-4">Portfolio Equity</h2>
            <ArenaEquityChart snapshots={snapshots} simulationId={simulation.id} />
          </CardContent>
        </Card>
      )}

      {/* Monthly P&L Heatmap + Trade Frequency */}
      {(() => {
        const showMonthly = isComplete && snapshots.length >= 20;
        const showFrequency = isComplete && positions.length >= 1;

        if (!showMonthly && !showFrequency) return null;

        return (
          <div className={showMonthly && showFrequency ? 'grid grid-cols-2 gap-4' : ''}>
            {showMonthly && <ArenaMonthlyPnl snapshots={snapshots} />}
            {showFrequency && <ArenaTradeFrequency positions={positions} />}
          </div>
        );
      })()}

      {/* Cancel Confirmation Dialog */}
      <CancelAnalysisDialog
        open={showCancelDialog}
        onOpenChange={setShowCancelDialog}
        onConfirm={handleCancel}
        isCancelling={isProcessing}
        analysisType="simulation"
      />

      {/* Delete Confirmation Dialog */}
      <DeleteAnalysisDialog
        open={showDeleteDialog}
        onOpenChange={setShowDeleteDialog}
        onConfirm={handleDelete}
        isDeleting={isProcessing}
        analysisType="simulation"
      />
    </div>
  );
};
