/**
 * Recommend Portfolio Dialog
 *
 * Triggered from the Live 20 results view. Allows users to set parameters
 * (min score, strategy, sector cap, position cap) and fetch a prioritized
 * portfolio recommendation from the backend. Read-only — does not auto-execute.
 */
import { useState } from 'react';
import { AlertCircle, BarChart2, Loader2 } from 'lucide-react';
import { Alert, AlertDescription } from '../ui/alert';
import { Button } from '../ui/button';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from '../ui/dialog';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../ui/select';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '../ui/table';
import { PORTFOLIO_STRATEGIES } from '../../constants/portfolio';
import { recommendPortfolio } from '../../services/live20Service';
import type { PortfolioRecommendResponse } from '../../types/live20';

/** Preset min-score options shown in the select dropdown */
const MIN_SCORE_OPTIONS = [40, 50, 60, 70, 80, 90] as const;

interface RecommendPortfolioDialogProps {
  /** Whether the dialog is currently open */
  open: boolean;
  /** Callback to close the dialog */
  onOpenChange: (open: boolean) => void;
  /** The ID of the completed Live 20 run to recommend from */
  runId: number;
}

/**
 * Format ATR percentage for display.
 * Returns "—" when null, otherwise rounds to 1 decimal place with "%" suffix.
 */
function formatAtrPct(value: number | null): string {
  if (value === null) return '—';
  return `${value.toFixed(1)}%`;
}

/**
 * Recommend Portfolio Dialog Component
 *
 * Features:
 * - Min score dropdown (preset options 40–90, default 60)
 * - Strategy dropdown (4 options matching backend)
 * - Max Per Sector number input (default 2)
 * - Max Positions optional number input (default empty = unlimited)
 * - "Get Recommendations" action button with loading state
 * - Summary badge: "N qualifying → M selected"
 * - Results table: Symbol, Score, Sector, ATR%
 * - Error alert when API fails
 * - Empty state when no qualifying signals
 */
export function RecommendPortfolioDialog({
  open,
  onOpenChange,
  runId,
}: RecommendPortfolioDialogProps) {
  // Form state
  const [minScore, setMinScore] = useState<number>(60);
  const [strategy, setStrategy] = useState<string>('score_sector_low_atr');
  const [maxPerSector, setMaxPerSector] = useState<string>('2');
  const [maxPositions, setMaxPositions] = useState<string>('');

  // Request state
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<PortfolioRecommendResponse | null>(null);

  const handleGetRecommendations = async () => {
    setIsLoading(true);
    setError(null);
    setResult(null);

    try {
      const parsedMaxPerSector = maxPerSector ? parseInt(maxPerSector, 10) : null;
      const parsedMaxPositions = maxPositions ? parseInt(maxPositions, 10) : null;

      const response = await recommendPortfolio(runId, {
        min_score: minScore,
        strategy,
        max_per_sector: parsedMaxPerSector,
        max_positions: parsedMaxPositions,
      });

      setResult(response);
    } catch (err) {
      const message =
        err instanceof Error ? err.message : 'Failed to fetch recommendations';
      setError(message);
    } finally {
      setIsLoading(false);
    }
  };

  const selectedStrategyDescription = PORTFOLIO_STRATEGIES.find(
    (s) => s.name === strategy
  )?.description;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <BarChart2 className="h-5 w-5" />
            Recommend Portfolio
          </DialogTitle>
          <DialogDescription>
            Filter and rank today's signals to build a prioritized trade list.
            This is a read-only recommendation — no trades will be executed.
          </DialogDescription>
        </DialogHeader>

        {/* Parameters Section */}
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            {/* Min Score */}
            <div className="space-y-2">
              <Label htmlFor="recommend-min-score">Min Score</Label>
              <Select
                value={minScore.toString()}
                onValueChange={(value) => setMinScore(parseInt(value, 10))}
              >
                <SelectTrigger id="recommend-min-score">
                  <SelectValue placeholder="Select minimum score..." />
                </SelectTrigger>
                <SelectContent>
                  {MIN_SCORE_OPTIONS.map((score) => (
                    <SelectItem key={score} value={score.toString()}>
                      {score}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <p className="text-xs text-muted-foreground">
                Only signals at or above this score qualify
              </p>
            </div>

            {/* Strategy */}
            <div className="space-y-2">
              <Label htmlFor="recommend-strategy">Strategy</Label>
              <Select value={strategy} onValueChange={setStrategy}>
                <SelectTrigger id="recommend-strategy">
                  <SelectValue placeholder="Select strategy..." />
                </SelectTrigger>
                <SelectContent>
                  {PORTFOLIO_STRATEGIES.map((s) => (
                    <SelectItem key={s.name} value={s.name}>
                      {s.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {selectedStrategyDescription && (
                <p className="text-xs text-muted-foreground">
                  {selectedStrategyDescription}
                </p>
              )}
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            {/* Max Per Sector */}
            <div className="space-y-2">
              <Label htmlFor="recommend-max-per-sector">Max Per Sector</Label>
              <Input
                id="recommend-max-per-sector"
                type="number"
                min="1"
                value={maxPerSector}
                onChange={(e) => setMaxPerSector(e.target.value)}
                placeholder="2"
              />
              <p className="text-xs text-muted-foreground">
                Max positions from the same sector
              </p>
            </div>

            {/* Max Positions */}
            <div className="space-y-2">
              <Label htmlFor="recommend-max-positions">Max Positions</Label>
              <Input
                id="recommend-max-positions"
                type="number"
                min="1"
                value={maxPositions}
                onChange={(e) => setMaxPositions(e.target.value)}
                placeholder="Unlimited"
              />
              <p className="text-xs text-muted-foreground">
                Overall position cap (optional)
              </p>
            </div>
          </div>

          {/* Action Button */}
          <Button
            onClick={handleGetRecommendations}
            disabled={isLoading}
            className="w-full"
          >
            {isLoading ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Fetching Recommendations...
              </>
            ) : (
              'Get Recommendations'
            )}
          </Button>
        </div>

        {/* Error State */}
        {error && (
          <Alert variant="destructive">
            <AlertCircle className="h-4 w-4" />
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        {/* Results Section */}
        {result && (
          <div className="space-y-3" data-testid="recommendations-result">
            {/* Summary */}
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <span>
                <span className="font-semibold text-foreground">
                  {result.total_qualifying}
                </span>{' '}
                qualifying signals
              </span>
              <span className="text-muted-foreground">→</span>
              <span>
                <span className="font-semibold text-foreground">
                  {result.total_selected}
                </span>{' '}
                selected
              </span>
            </div>

            {/* Empty State */}
            {result.items.length === 0 ? (
              <div className="rounded-md border border-dashed py-8 text-center">
                <p className="text-sm font-medium text-muted-foreground">
                  No qualifying signals
                </p>
                <p className="text-xs text-muted-foreground mt-1">
                  Try lowering the minimum score threshold
                </p>
              </div>
            ) : (
              /* Results Table */
              <div className="rounded-md border">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead className="w-[40px] text-center">#</TableHead>
                      <TableHead>Symbol</TableHead>
                      <TableHead className="text-right">Score</TableHead>
                      <TableHead>Sector</TableHead>
                      <TableHead className="text-right">ATR%</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {result.items.map((item, index) => (
                      <TableRow key={item.symbol}>
                        <TableCell className="text-center font-mono text-xs text-muted-foreground">
                          {index + 1}
                        </TableCell>
                        <TableCell className="font-mono font-semibold">
                          {item.symbol}
                        </TableCell>
                        <TableCell className="text-right font-mono font-semibold">
                          {item.score}
                        </TableCell>
                        <TableCell className="text-sm text-muted-foreground">
                          {item.sector ?? '—'}
                        </TableCell>
                        <TableCell className="text-right font-mono text-sm">
                          {formatAtrPct(item.atr_pct)}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            )}
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
