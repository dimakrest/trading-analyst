import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Badge } from '../ui/badge';
import { Search, ChevronRight, List } from 'lucide-react';
import type { Live20RunSummary } from '../../types/live20';
import { listRuns, type ListRunsParams } from '../../services/live20Service';

const PAGE_SIZE = 20;

type DateRange = '7days' | '30days' | 'all';
type DirectionFilter = 'all' | 'LONG' | 'NO_SETUP';

/**
 * Live 20 History Tab
 *
 * Displays a paginated list of past Live 20 analysis runs with filtering capabilities.
 * Provides filters for date range, direction, and symbol search.
 * Users can click on a run to view its details.
 */
export function Live20HistoryTab() {
  const navigate = useNavigate();

  // Filter state
  const [dateRange, setDateRange] = useState<DateRange>('7days');
  const [directionFilter, setDirectionFilter] = useState<DirectionFilter>('all');
  const [symbolSearch, setSymbolSearch] = useState('');
  const [debouncedSymbol, setDebouncedSymbol] = useState('');

  // Pagination state
  const [currentPage, setCurrentPage] = useState(1);
  const [totalRuns, setTotalRuns] = useState(0);

  // Data state
  const [runs, setRuns] = useState<Live20RunSummary[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Debounce symbol search
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSymbol(symbolSearch);
    }, 300);

    return () => clearTimeout(timer);
  }, [symbolSearch]);

  // Reset to page 1 when filters change
  useEffect(() => {
    setCurrentPage(1);
  }, [dateRange, directionFilter, debouncedSymbol]);

  // Fetch runs when filters or page changes
  const fetchRuns = useCallback(async () => {
    setIsLoading(true);
    setError(null);

    try {
      // Calculate date_from based on date range
      let date_from: string | undefined;
      const now = new Date();

      if (dateRange === '7days') {
        const sevenDaysAgo = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
        date_from = sevenDaysAgo.toISOString();
      } else if (dateRange === '30days') {
        const thirtyDaysAgo = new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000);
        date_from = thirtyDaysAgo.toISOString();
      }

      const params: ListRunsParams = {
        limit: PAGE_SIZE,
        offset: (currentPage - 1) * PAGE_SIZE,
        date_from,
        has_direction: directionFilter === 'all' ? undefined : directionFilter,
        symbol: debouncedSymbol || undefined,
      };

      const response = await listRuns(params);
      setRuns(response.items);
      setTotalRuns(response.total);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch runs');
    } finally {
      setIsLoading(false);
    }
  }, [dateRange, directionFilter, debouncedSymbol, currentPage]);

  useEffect(() => {
    fetchRuns();
  }, [fetchRuns]);

  // Format date for display
  const formatDate = (isoString: string): string => {
    const date = new Date(isoString);
    const dateStr = date.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    });
    const timeStr = date.toLocaleTimeString('en-US', {
      hour: 'numeric',
      minute: '2-digit',
      hour12: true,
    });
    return `${dateStr} · ${timeStr}`;
  };

  // Handle row click
  const handleRunClick = (runId: number) => {
    navigate(`/live-20/runs/${runId}`);
  };

  // Pagination helpers
  const startIndex = (currentPage - 1) * PAGE_SIZE + 1;
  const endIndex = Math.min(currentPage * PAGE_SIZE, totalRuns);
  const totalPages = Math.ceil(totalRuns / PAGE_SIZE);
  const hasPrevious = currentPage > 1;
  const hasNext = currentPage < totalPages;

  return (
    <div className="space-y-5">
      {/* Filters Section */}
      <div className="bg-bg-secondary rounded-xl border border-default p-5">
        <div className="flex flex-wrap gap-4 items-end">
          {/* Date Range Filter */}
          <div className="flex flex-col gap-2">
            <label className="text-[11px] font-semibold uppercase tracking-wider text-text-muted">
              Date Range
            </label>
            <select
              value={dateRange}
              onChange={(e) => setDateRange(e.target.value as DateRange)}
              className="px-3 py-2 bg-bg-tertiary border border-default rounded-lg text-sm text-text-primary focus:border-accent-primary focus:outline-none"
            >
              <option value="7days">Last 7 days</option>
              <option value="30days">Last 30 days</option>
              <option value="all">All time</option>
            </select>
          </div>

          {/* Direction Filter */}
          <div className="flex flex-col gap-2">
            <label className="text-[11px] font-semibold uppercase tracking-wider text-text-muted">
              Direction
            </label>
            <div className="flex gap-1 bg-bg-tertiary p-1 rounded-lg border border-default">
              <button
                type="button"
                onClick={() => setDirectionFilter('all')}
                className={`px-3 py-1.5 rounded-md text-xs font-medium transition-all ${
                  directionFilter === 'all'
                    ? 'bg-bg-elevated text-text-primary'
                    : 'text-text-muted hover:text-text-primary'
                }`}
              >
                All
              </button>
              <button
                type="button"
                onClick={() => setDirectionFilter('LONG')}
                className={`px-3 py-1.5 rounded-md text-xs font-medium transition-all ${
                  directionFilter === 'LONG'
                    ? 'bg-[var(--signal-long-muted)] text-[var(--signal-long)]'
                    : 'text-text-muted hover:text-text-primary'
                }`}
              >
                Long
              </button>
              <button
                type="button"
                onClick={() => setDirectionFilter('NO_SETUP')}
                className={`px-3 py-1.5 rounded-md text-xs font-medium transition-all ${
                  directionFilter === 'NO_SETUP'
                    ? 'bg-[rgba(100,116,139,0.15)] text-text-secondary'
                    : 'text-text-muted hover:text-text-primary'
                }`}
              >
                No Setup
              </button>
            </div>
          </div>

          {/* Symbol Search */}
          <div className="relative flex-1 min-w-[200px] max-w-[240px]">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-text-muted" />
            <Input
              placeholder="Search by symbol..."
              value={symbolSearch}
              onChange={(e) => setSymbolSearch(e.target.value)}
              className="pl-10 bg-bg-tertiary border-default font-mono text-sm"
            />
          </div>
        </div>
      </div>

      {/* History Table Section */}
      <div className="bg-bg-secondary rounded-xl border border-default overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-subtle">
          <span className="font-display text-sm font-semibold text-text-secondary">
            Analysis Run History
          </span>
          <span className="font-mono text-xs text-text-muted">
            {totalRuns} run{totalRuns !== 1 ? 's' : ''} total
          </span>
        </div>

        {/* Loading State */}
        {isLoading && (
          <div className="py-12 text-center">
            <p className="text-text-muted">Loading runs...</p>
          </div>
        )}

        {/* Error State */}
        {error && !isLoading && (
          <div className="py-12 text-center">
            <p className="text-destructive">{error}</p>
          </div>
        )}

        {/* Empty State */}
        {!isLoading && !error && runs.length === 0 && (
          <div className="py-12 text-center">
            <p className="text-base font-medium text-text-secondary">No runs found</p>
            <p className="text-sm text-text-muted mt-2">
              Try adjusting your filters or run a new analysis
            </p>
          </div>
        )}

        {/* Runs Table */}
        {!isLoading && !error && runs.length > 0 && (
          <>
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="bg-bg-tertiary border-b border-subtle">
                    <th className="text-left text-[10px] font-semibold uppercase tracking-wider text-text-muted px-5 py-3">
                      Date / Time
                    </th>
                    <th className="text-left text-[10px] font-semibold uppercase tracking-wider text-text-muted px-5 py-3">
                      Symbols
                    </th>
                    <th className="text-left text-[10px] font-semibold uppercase tracking-wider text-[var(--signal-long)] px-5 py-3">
                      Long
                    </th>
                    <th className="text-left text-[10px] font-semibold uppercase tracking-wider text-text-muted px-5 py-3">
                      No Setup
                    </th>
                    <th className="w-12"></th>
                  </tr>
                </thead>
                <tbody>
                  {runs.map((run) => (
                    <tr
                      key={run.id}
                      onClick={() => handleRunClick(run.id)}
                      className="border-b border-subtle hover:bg-bg-tertiary cursor-pointer transition-colors"
                    >
                      <td className="px-5 py-4 whitespace-nowrap">
                        <div className="flex flex-col gap-1">
                          <span className="text-[13px] text-text-secondary">
                            {formatDate(run.created_at)}
                          </span>
                          <div className="flex items-center gap-1.5">
                            <Badge
                              variant="outline"
                              className="text-[10px] px-1.5 font-mono"
                            >
                              {run.scoring_algorithm?.toUpperCase() || 'CCI'}
                            </Badge>
                            {run.source_lists?.length ? (
                              run.source_lists.length === 1 ? (
                                <Badge
                                  variant="outline"
                                  className="text-xs inline-flex items-center gap-1 border-[rgba(167,139,250,0.3)] bg-[rgba(167,139,250,0.12)] text-[#c4b5fd]"
                                >
                                  <List className="h-3 w-3" aria-hidden="true" />
                                  {run.source_lists[0].name}
                                </Badge>
                              ) : (
                                <Badge
                                  variant="outline"
                                  className="text-xs inline-flex items-center gap-1 border-[rgba(167,139,250,0.3)] bg-[rgba(167,139,250,0.12)] text-[#c4b5fd]"
                                  title={run.source_lists.map((list) => list.name).join(', ')}
                                >
                                  <List className="h-3 w-3" aria-hidden="true" />
                                  {run.source_lists.length} lists combined
                                </Badge>
                              )
                            ) : run.stock_list_name ? (
                              <Badge
                                variant="outline"
                                className="text-xs inline-flex items-center gap-1 border-[rgba(167,139,250,0.3)] bg-[rgba(167,139,250,0.12)] text-[#c4b5fd]"
                              >
                                <List className="h-3 w-3" aria-hidden="true" />
                                {run.stock_list_name}
                              </Badge>
                            ) : null}
                          </div>
                        </div>
                      </td>
                      <td className="px-5 py-4 whitespace-nowrap font-mono text-[13px] font-semibold text-text-primary">
                        {run.symbol_count}
                      </td>
                      <td className="px-5 py-4 whitespace-nowrap font-mono text-[13px] font-semibold text-[var(--signal-long)]">
                        {run.long_count}
                      </td>
                      <td className="px-5 py-4 whitespace-nowrap font-mono text-[13px] text-text-muted">
                        {run.no_setup_count}
                      </td>
                      <td className="px-5 py-4 whitespace-nowrap">
                        <ChevronRight className="h-4 w-4 text-text-muted" />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Pagination */}
            <div className="flex justify-between items-center px-5 py-4 border-t border-subtle">
              <p className="text-xs text-text-muted">
                Showing {startIndex}-{endIndex} of {totalRuns} runs
              </p>
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setCurrentPage((p) => p - 1)}
                  disabled={!hasPrevious}
                  className="text-xs"
                >
                  Previous
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setCurrentPage((p) => p + 1)}
                  disabled={!hasNext}
                  className="text-xs"
                >
                  Next
                </Button>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
