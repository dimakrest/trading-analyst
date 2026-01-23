import { useState, useEffect, useMemo } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft, Loader2, List, Target, Trash2, XCircle } from 'lucide-react';
import { toast } from 'sonner';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { CancelAnalysisDialog, DeleteAnalysisDialog } from '../components/common';
import { Live20Filters } from '../components/live20/Live20Filters';
import { Live20Table } from '../components/live20/Live20Table';
import { cancelRun, deleteRun, getRunDetail } from '../services/live20Service';
import type {
  Live20Counts,
  Live20Direction,
  Live20RunDetail as Live20RunDetailType,
} from '../types/live20';
import { getStrategyDisplayLabel, hasCustomAtrMultiplier } from '../utils/live20';

/**
 * Live20RunDetail - Analysis Run Detail Page
 *
 * Displays detailed information about a specific Live20 analysis run:
 * - Summary: timestamp, symbol counts by direction, configuration
 * - Source lists: single or multi-list source indicators
 * - Strategy configuration: entry/exit settings
 * - Results: filterable, searchable table of analysis results
 * - Actions: cancel (for active runs), delete (for completed runs)
 */
export function Live20RunDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  const [run, setRun] = useState<Live20RunDetailType | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [directionFilter, setDirectionFilter] = useState<Live20Direction | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [minScore, setMinScore] = useState(0);

  const [showCancelDialog, setShowCancelDialog] = useState(false);
  const [showDeleteDialog, setShowDeleteDialog] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);

  useEffect(() => {
    if (!id) return;

    const fetchRun = async () => {
      setIsLoading(true);
      setError(null);
      try {
        const data = await getRunDetail(parseInt(id, 10));
        setRun(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load run');
      } finally {
        setIsLoading(false);
      }
    };

    fetchRun();
  }, [id]);

  const filteredResults = useMemo(() => {
    if (!run) return [];
    let filtered = run.results;

    if (directionFilter) {
      filtered = filtered.filter((r) => r.direction === directionFilter);
    }
    if (searchQuery) {
      const query = searchQuery.toLowerCase();
      filtered = filtered.filter((r) => r.stock.toLowerCase().includes(query));
    }
    if (minScore > 0) {
      filtered = filtered.filter((r) => r.confidence_score >= minScore);
    }

    return filtered;
  }, [run, directionFilter, searchQuery, minScore]);

  const counts: Live20Counts = useMemo(() => {
    if (!run) return { long: 0, short: 0, no_setup: 0, total: 0 };
    return {
      long: run.long_count,
      short: run.short_count,
      no_setup: run.no_setup_count,
      total: run.symbol_count,
    };
  }, [run]);

  const isRunActive = run?.status === 'pending' || run?.status === 'running';

  const handleCancel = async () => {
    if (!id) return;

    setIsProcessing(true);
    try {
      await cancelRun(parseInt(id, 10));
      const data = await getRunDetail(parseInt(id, 10));
      setRun(data);
      setShowCancelDialog(false);
      toast.success('Analysis run cancelled');
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to cancel run';
      toast.error(errorMessage);
    } finally {
      setIsProcessing(false);
    }
  };

  const handleDelete = async () => {
    if (!id) return;

    setIsProcessing(true);
    try {
      await deleteRun(parseInt(id, 10));
      navigate('/live-20', { state: { tab: 'history' } });
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to delete run';
      toast.error(errorMessage);
      setShowDeleteDialog(false);
    } finally {
      setIsProcessing(false);
    }
  };

  const handleBack = () => {
    navigate('/live-20', { state: { tab: 'history' } });
  };

  const formatDate = (isoDate: string) => {
    const date = new Date(isoDate);
    return {
      date: date.toLocaleDateString('en-US', {
        month: 'short',
        day: 'numeric',
        year: 'numeric',
      }),
      time: date.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' }),
      full: date.toLocaleString('en-US', {
        month: 'short',
        day: 'numeric',
        year: 'numeric',
        hour: 'numeric',
        minute: '2-digit',
      }),
    };
  };

  if (isLoading) {
    return (
      <div className="container mx-auto px-6 py-6 md:py-8">
        <div className="flex items-center justify-center py-12">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        </div>
      </div>
    );
  }

  if (error || !run) {
    return (
      <div className="container mx-auto px-6 py-6 md:py-8">
        <div className="flex flex-col items-center justify-center py-12 space-y-4">
          <p className={`text-lg ${error ? 'text-destructive' : 'text-muted-foreground'}`}>
            {error || 'Run not found'}
          </p>
          <Button variant="outline" onClick={handleBack}>
            <ArrowLeft className="mr-2 h-4 w-4" />
            Back to History
          </Button>
        </div>
      </div>
    );
  }

  const formatted = formatDate(run.created_at);

  return (
    <div className="container mx-auto px-6 py-6 md:py-8">
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-4">
          <Button variant="outline" size="sm" onClick={handleBack}>
            <ArrowLeft className="mr-2 h-4 w-4" />
            Back
          </Button>
          <h1 className="text-xl md:text-2xl font-bold">
            Analysis Run — {formatted.full}
          </h1>
        </div>
        {isRunActive ? (
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

      {run.source_lists?.length ? (
        <div className="flex items-center gap-2 px-4 py-3 mb-4 rounded-md border border-[rgba(167,139,250,0.3)] bg-[rgba(167,139,250,0.12)]">
          <List className="h-4 w-4 text-[#c4b5fd]" aria-hidden="true" />
          <span className="text-sm text-muted-foreground">
            {run.source_lists.length === 1 ? 'From list:' : `Combined from ${run.source_lists.length} lists:`}
          </span>
          <div className="flex flex-wrap gap-2">
            {run.source_lists.map((list) => (
              <span key={list.id} className="text-sm font-semibold text-[#c4b5fd]">
                {list.name}
              </span>
            ))}
          </div>
        </div>
      ) : run.stock_list_name ? (
        <div className="flex items-center gap-2 px-4 py-3 mb-4 rounded-md border border-[rgba(167,139,250,0.3)] bg-[rgba(167,139,250,0.12)]">
          <List className="h-4 w-4 text-[#c4b5fd]" aria-hidden="true" />
          <span className="text-sm text-muted-foreground">From list:</span>
          <span className="text-sm font-semibold text-[#c4b5fd]">{run.stock_list_name}</span>
        </div>
      ) : null}

      {getStrategyDisplayLabel(run.strategy_config) && (
        <div className="flex items-center gap-2 px-4 py-3 mb-4 rounded-md border border-[rgba(245,158,11,0.35)] bg-[rgba(245,158,11,0.12)]">
          <Target className="h-4 w-4 text-[#fbbf24]" aria-hidden="true" />
          <span className="text-sm text-muted-foreground">Entry:</span>
          <span className="text-sm font-semibold text-[#fbbf24]">
            {getStrategyDisplayLabel(run.strategy_config)}
          </span>
          {hasCustomAtrMultiplier(run.strategy_config) && (
            <>
              <span className="text-muted-foreground mx-1">|</span>
              <span className="text-sm text-muted-foreground">Stop:</span>
              <span className="text-sm font-semibold text-[#fbbf24]">
                {run.strategy_config?.atr_multiplier}x ATR
              </span>
            </>
          )}
        </div>
      )}

      <Card className="mb-6">
        <CardHeader>
          <CardTitle>Run Summary</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4">
            <div className="text-center p-4 bg-secondary rounded-lg border">
              <p className="text-xs text-muted-foreground uppercase tracking-wide mb-2">
                Timestamp
              </p>
              <p className="text-sm font-semibold">
                {formatted.date}
                <br />
                {formatted.time}
              </p>
            </div>

            <div className="text-center p-4 bg-secondary rounded-lg border">
              <p className="text-xs text-muted-foreground uppercase tracking-wide mb-2">
                Total Symbols
              </p>
              <p className="text-2xl font-bold font-mono">{run.symbol_count}</p>
            </div>

            <div className="text-center p-4 bg-secondary rounded-lg border">
              <p className="text-xs text-muted-foreground uppercase tracking-wide mb-2">
                Long Setups
              </p>
              <p className="text-2xl font-bold font-mono text-signal-long">{run.long_count}</p>
            </div>

            <div className="text-center p-4 bg-secondary rounded-lg border">
              <p className="text-xs text-muted-foreground uppercase tracking-wide mb-2">
                Short Setups
              </p>
              <p className="text-2xl font-bold font-mono text-signal-short">{run.short_count}</p>
            </div>

            <div className="text-center p-4 bg-secondary rounded-lg border">
              <p className="text-xs text-muted-foreground uppercase tracking-wide mb-2">
                No Setup
              </p>
              <p className="text-2xl font-bold font-mono text-muted-foreground">
                {run.no_setup_count}
              </p>
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Results</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-6">
            <Live20Filters
              directionFilter={directionFilter}
              onDirectionChange={setDirectionFilter}
              counts={counts}
              searchQuery={searchQuery}
              onSearchChange={setSearchQuery}
              minScore={minScore}
              onMinScoreChange={setMinScore}
            />

            <Live20Table results={filteredResults} />
          </div>
        </CardContent>
      </Card>

      <CancelAnalysisDialog
        open={showCancelDialog}
        onOpenChange={setShowCancelDialog}
        onConfirm={handleCancel}
        isCancelling={isProcessing}
        analysisType="analysis"
      />

      <DeleteAnalysisDialog
        open={showDeleteDialog}
        onOpenChange={setShowDeleteDialog}
        onConfirm={handleDelete}
        isDeleting={isProcessing}
        analysisType="analysis run"
      />
    </div>
  );
}
