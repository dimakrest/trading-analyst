import { useState, useCallback, useEffect } from 'react';
import type { Live20Result, Live20Counts, Live20Direction } from '@/types/live20';
import * as live20Service from '@/services/live20Service';
import { useLive20Polling } from './useLive20Polling';

interface AnalysisProgress {
  runId: number;
  total: number;
  processed: number;
  status: string;
}

interface UseLive20Return {
  results: Live20Result[];
  counts: Live20Counts;
  isLoading: boolean;
  isAnalyzing: boolean;
  error: string | null;
  analyzeSymbols: (
    symbols: string[],
    sourceLists?: Array<{ id: number; name: string }> | null,
    agentConfigId?: number
  ) => Promise<void>;
  fetchResults: (direction?: Live20Direction | null, minScore?: number) => Promise<void>;
  progress: AnalysisProgress | null;
  cancelAnalysis: () => Promise<void>;
  isCancelling: boolean;
  failedSymbols: Record<string, string>;
}

/**
 * Hook for Live 20 mean reversion analysis
 *
 * Manages state for analyzing symbols and fetching Live 20 results.
 * Analysis is now async - POST /analyze returns immediately with a run_id,
 * and we poll GET /runs/{id} until the run completes.
 *
 * @returns Object containing results, loading states, and action functions
 *
 * @example
 * const { analyzeSymbols, results, isAnalyzing, progress } = useLive20();
 *
 * // Analyze symbols (starts async processing)
 * await analyzeSymbols(['AAPL', 'MSFT']);
 *
 * // While isAnalyzing is true, show progress:
 * if (progress) {
 *   console.log(`${progress.processed}/${progress.total} symbols processed`);
 * }
 */
export function useLive20(): UseLive20Return {
  const [results, setResults] = useState<Live20Result[]>([]);
  const [counts, setCounts] = useState<Live20Counts>({ long: 0, short: 0, no_setup: 0, total: 0 });
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // State for async analysis
  const [activeRunId, setActiveRunId] = useState<number | null>(null);
  const [progress, setProgress] = useState<AnalysisProgress | null>(null);
  const [isCancelling, setIsCancelling] = useState(false);
  const [failedSymbols, setFailedSymbols] = useState<Record<string, string>>({});

  const { run, isPolling, error: pollingError } = useLive20Polling(activeRunId);

  useEffect(() => {
    if (!run) return;

    setProgress({
      runId: run.id,
      total: run.symbol_count,
      processed: run.processed_count,
      status: run.status,
    });

    // Update results progressively (not just on completion)
    if (run.results && run.results.length > 0) {
      setResults(run.results);
      setCounts({
        long: run.long_count,
        short: run.short_count,
        no_setup: run.no_setup_count,
        total: run.results.length,
      });
    }

    // Track failed symbols
    if (run.failed_symbols) {
      setFailedSymbols(run.failed_symbols);
    }

    // Handle terminal states (including cancelled)
    if (run.status === 'completed' || run.status === 'cancelled' || run.status === 'failed') {
      setActiveRunId(null);
      setProgress(null);
      setIsCancelling(false);

      if (run.status === 'failed') {
        setError(run.error_message || 'Analysis failed');
      }
    }
  }, [run]);

  useEffect(() => {
    if (pollingError) {
      setError(pollingError);
      setActiveRunId(null);
      setProgress(null);
    }
  }, [pollingError]);

  const analyzeSymbols = useCallback(
    async (
      symbols: string[],
      sourceLists: Array<{ id: number; name: string }> | null = null,
      agentConfigId?: number
    ) => {
      setError(null);
      setResults([]);
      setCounts({ long: 0, short: 0, no_setup: 0, total: 0 });
      setFailedSymbols({});

      try {
        const response = await live20Service.analyzeSymbols(symbols, sourceLists, agentConfigId);

        setActiveRunId(response.run_id);
        setProgress({
          runId: response.run_id,
          total: response.total,
          processed: 0,
          status: response.status,
        });
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to start analysis');
      }
    },
    []
  );

  const fetchResults = useCallback(
    async (direction?: Live20Direction | null, minScore?: number) => {
      setIsLoading(true);
      setError(null);

      try {
        const response = await live20Service.getResults({
          direction: direction || undefined,
          min_score: minScore,
        });
        setResults(response.results);
        setCounts({
          ...response.counts,
          total: response.counts.long + response.counts.short + response.counts.no_setup,
        });
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to fetch results');
      } finally {
        setIsLoading(false);
      }
    },
    []
  );

  const cancelAnalysis = useCallback(async () => {
    if (!activeRunId) return;

    setIsCancelling(true);
    try {
      await live20Service.cancelRun(activeRunId);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to cancel analysis');
      setIsCancelling(false);
    }
  }, [activeRunId]);

  const isAnalyzing = activeRunId !== null || isPolling;

  return {
    results,
    counts,
    isLoading,
    isAnalyzing,
    error,
    analyzeSymbols,
    fetchResults,
    progress,
    cancelAnalysis,
    isCancelling,
    failedSymbols,
  };
}
