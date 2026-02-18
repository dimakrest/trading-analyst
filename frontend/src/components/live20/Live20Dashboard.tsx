import { useState, useMemo, useEffect } from 'react';
import { useLocation } from 'react-router-dom';
import { toast } from 'sonner';
import { Card, CardContent } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { PullToRefresh } from '@/components/ui/pull-to-refresh';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { AlertCircle, BarChart2 } from 'lucide-react';
import type { Live20Direction } from '@/types/live20';
import { useLive20 } from '@/hooks/useLive20';
import { useResponsive } from '@/hooks/useResponsive';
import { useAgentConfigs } from '@/hooks/useAgentConfigs';
import { Live20Input } from './Live20Input';
import { Live20Filters } from './Live20Filters';
import { Live20Table } from './Live20Table';
import { Live20Loading } from './Live20Loading';
import { Live20HistoryTab } from './Live20HistoryTab';
import { RecommendPortfolioDialog } from './RecommendPortfolioDialog';

/**
 * Live 20 Dashboard
 *
 * Main page for Live 20 mean reversion analysis. Provides:
 * - Symbol input for analysis
 * - Loading state during analysis
 * - Filters (direction, search, min score)
 * - Results table with sortable columns
 * - Error handling and empty states
 * - Mobile-responsive layout with pull-to-refresh
 *
 * Uses the useLive20 hook for state management and API interactions.
 */
export function Live20Dashboard() {
  const location = useLocation();
  // Support navigation state from delete redirect
  const defaultTab = location.state?.tab === 'history' ? 'history' : 'analyze';

  const [directionFilter, setDirectionFilter] = useState<Live20Direction | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [minScore, setMinScore] = useState(0);
  const [minRvol, setMinRvol] = useState(0);
  const [symbolCount, setSymbolCount] = useState(0);
  const [wasCancelled, setWasCancelled] = useState(false);
  const [isRecommendDialogOpen, setIsRecommendDialogOpen] = useState(false);
  const { isMobile } = useResponsive();

  // Agent configs state
  const {
    configs: agentConfigs,
    selectedConfigId: selectedAgentConfigId,
    setSelectedConfigId: setSelectedAgentConfigId,
    isLoading: isLoadingConfigs,
    error: configsError,
  } = useAgentConfigs();

  // Show toast if configs fail to load
  useEffect(() => {
    if (configsError) {
      toast.error(configsError);
    }
  }, [configsError]);

  const {
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
  } = useLive20();

  const handleAnalyze = async (
    symbols: string[],
    sourceLists: Array<{ id: number; name: string }> | null
  ) => {
    setSymbolCount(symbols.length);
    setWasCancelled(false);
    await analyzeSymbols(symbols, sourceLists, selectedAgentConfigId);
  };

  // Track if the current analysis was cancelled
  useEffect(() => {
    if (progress?.status === 'cancelled') {
      setWasCancelled(true);
    }
  }, [progress?.status]);

  // Filter results by search query and direction (client-side)
  const filteredResults = useMemo(() => {
    let filtered = results;

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

    if (minRvol > 0) {
      filtered = filtered.filter((r) => (r.rvol ?? 0) >= minRvol);
    }

    return filtered;
  }, [results, directionFilter, searchQuery, minScore, minRvol]);

  const analyzeContent = (
    <div className="space-y-6">
      {/* Accessibility Status Region */}
      <div
        role="status"
        aria-live="polite"
        aria-atomic="true"
        className="sr-only"
      >
        {isAnalyzing && progress && (
          `Analyzing symbols: ${progress.processed} of ${progress.total} complete. ${results.length} setups found.`
        )}
        {wasCancelled && !isAnalyzing && (
          `Analysis cancelled. ${results.length} results available.`
        )}
      </div>

      {/* Input Section */}
      <Live20Input
        onAnalyze={handleAnalyze}
        isAnalyzing={isAnalyzing}
        agentConfigs={agentConfigs}
        selectedAgentConfigId={selectedAgentConfigId}
        onAgentConfigChange={setSelectedAgentConfigId}
        isLoadingConfigs={isLoadingConfigs}
      />

      {/* Cancelled State Alert */}
      {wasCancelled && !isAnalyzing && results.length > 0 && (
        <Alert className="border-amber-500 bg-amber-50 dark:bg-amber-950">
          <AlertCircle className="h-4 w-4 text-amber-600 dark:text-amber-400" />
          <AlertDescription className="text-amber-800 dark:text-amber-200">
            Analysis was cancelled. Showing {results.length} result{results.length !== 1 ? 's' : ''} found before cancellation.
          </AlertDescription>
        </Alert>
      )}

      {/* Failed Symbols Alert */}
      {Object.keys(failedSymbols).length > 0 && !isAnalyzing && (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>
            {Object.keys(failedSymbols).length} symbol{Object.keys(failedSymbols).length !== 1 ? 's' : ''} failed to analyze:
            <ul className="mt-2 list-disc list-inside">
              {Object.entries(failedSymbols).slice(0, 5).map(([symbol, error]) => (
                <li key={symbol}>
                  {symbol}: {error}
                </li>
              ))}
              {Object.keys(failedSymbols).length > 5 && (
                <li>...and {Object.keys(failedSymbols).length - 5} more</li>
              )}
            </ul>
          </AlertDescription>
        </Alert>
      )}

      {/* Loading State */}
      {isAnalyzing && (
        <Live20Loading
          symbolCount={progress?.total ?? symbolCount}
          processedCount={progress?.processed}
          status={progress?.status}
          resultsCount={results.length}
          onCancel={cancelAnalysis}
          isCancelling={isCancelling}
        />
      )}

      {/* Results Section */}
      {results.length > 0 && (
        <>
          {/* Results Toolbar: filters + actions */}
          <div className="flex flex-wrap items-start justify-between gap-3">
            <Live20Filters
              directionFilter={directionFilter}
              onDirectionChange={setDirectionFilter}
              counts={counts}
              searchQuery={searchQuery}
              onSearchChange={setSearchQuery}
              minScore={minScore}
              onMinScoreChange={setMinScore}
              minRvol={minRvol}
              onMinRvolChange={setMinRvol}
            />

            {/* Recommend Portfolio button — only when analysis is complete */}
            {!isAnalyzing && progress?.runId != null && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => setIsRecommendDialogOpen(true)}
                aria-label="Recommend portfolio from current run"
              >
                <BarChart2 className="h-4 w-4" />
                Recommend Portfolio
              </Button>
            )}
          </div>

          <Live20Table results={filteredResults} />

          {/* Recommend Portfolio Dialog */}
          {progress?.runId != null && (
            <RecommendPortfolioDialog
              open={isRecommendDialogOpen}
              onOpenChange={setIsRecommendDialogOpen}
              runId={progress.runId}
            />
          )}
        </>
      )}

      {/* Empty State */}
      {!isAnalyzing && results.length === 0 && !error && (
        <Card>
          <CardContent className="py-12 text-center">
            <p className="text-lg font-medium text-muted-foreground">No symbols analyzed yet</p>
            <p className="text-sm text-muted-foreground mt-2">
              Enter stock symbols above and click Analyze to get started
            </p>
            <p className="text-xs text-muted-foreground mt-2">
              Try: AAPL, MSFT, NVDA
            </p>
          </CardContent>
        </Card>
      )}

      {/* Error State */}
      {error && (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}
    </div>
  );

  return (
    <div className="px-6 py-6 md:py-8 flex flex-col gap-5">
      <Tabs defaultValue={defaultTab} className="w-full">
        {/* Page Header with Tabs */}
        <div className="flex items-center justify-between gap-6 flex-wrap">
          <h1 className="font-display text-2xl font-bold tracking-tight">
            Live 20 Screener
          </h1>
          <TabsList className="bg-bg-secondary border border-default rounded-[10px] p-1">
            <TabsTrigger
              value="analyze"
              className="px-5 py-2.5 text-[13px] font-semibold rounded-lg data-[state=active]:bg-accent-primary data-[state=active]:text-white"
            >
              Analyze
            </TabsTrigger>
            <TabsTrigger
              value="history"
              className="px-5 py-2.5 text-[13px] font-semibold rounded-lg data-[state=active]:bg-accent-primary data-[state=active]:text-white"
            >
              History
            </TabsTrigger>
          </TabsList>
        </div>

        <TabsContent value="analyze" className="mt-5">
          {isMobile ? (
            <PullToRefresh onRefresh={() => fetchResults(directionFilter, minScore)} disabled={isLoading}>
              {analyzeContent}
            </PullToRefresh>
          ) : (
            analyzeContent
          )}
        </TabsContent>

        <TabsContent value="history" className="mt-5">
          <Live20HistoryTab />
        </TabsContent>
      </Tabs>
    </div>
  );
}
