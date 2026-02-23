import { useEffect, useState } from 'react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '../ui/dialog';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../ui/select';
import { PORTFOLIO_STRATEGIES } from '../../constants/portfolio';
import type {
  PortfolioConfig,
  UpdatePortfolioConfigRequest,
} from '../../types/portfolioConfig';
import { extractErrorMessage } from '../../utils/errors';

interface EditPortfolioDialogProps {
  config: PortfolioConfig | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSubmit: (id: number, data: UpdatePortfolioConfigRequest) => Promise<PortfolioConfig>;
  isSubmitting?: boolean;
}

export const EditPortfolioDialog = ({
  config,
  open,
  onOpenChange,
  onSubmit,
  isSubmitting = false,
}: EditPortfolioDialogProps) => {
  const [name, setName] = useState('');
  const [portfolioStrategy, setPortfolioStrategy] = useState('none');
  const [positionSize, setPositionSize] = useState('1000');
  const [minBuyScore, setMinBuyScore] = useState('60');
  const [trailingStopPct, setTrailingStopPct] = useState('5');
  const [maxPerSector, setMaxPerSector] = useState('');
  const [maxOpenPositions, setMaxOpenPositions] = useState('');
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (config && open) {
      setName(config.name);
      setPortfolioStrategy(config.portfolio_strategy);
      setPositionSize(config.position_size.toString());
      setMinBuyScore(config.min_buy_score.toString());
      setTrailingStopPct(config.trailing_stop_pct.toString());
      setMaxPerSector(config.max_per_sector?.toString() ?? '');
      setMaxOpenPositions(config.max_open_positions?.toString() ?? '');
      setError(null);
    }
  }, [config, open]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!config) return;

    setError(null);

    const trimmedName = name.trim();
    if (!trimmedName) {
      setError('Setup name is required');
      return;
    }

    const parsedMaxPerSector = maxPerSector ? Number.parseInt(maxPerSector, 10) : null;
    const parsedMaxOpenPositions = maxOpenPositions ? Number.parseInt(maxOpenPositions, 10) : null;
    const parsedPositionSize = Number.parseInt(positionSize, 10);
    const parsedMinBuyScore = Number.parseInt(minBuyScore, 10);
    const parsedTrailingStopPct = Number.parseFloat(trailingStopPct);

    if (maxPerSector && Number.isNaN(parsedMaxPerSector)) {
      setError('Max per sector must be a whole number');
      return;
    }
    if (maxOpenPositions && Number.isNaN(parsedMaxOpenPositions)) {
      setError('Max open positions must be a whole number');
      return;
    }
    if (parsedMaxPerSector !== null && parsedMaxPerSector < 1) {
      setError('Max per sector must be 1 or greater');
      return;
    }
    if (parsedMaxOpenPositions !== null && parsedMaxOpenPositions < 1) {
      setError('Max open positions must be 1 or greater');
      return;
    }
    if (!Number.isInteger(parsedPositionSize) || parsedPositionSize < 1) {
      setError('Position size must be 1 or greater');
      return;
    }
    if (!Number.isInteger(parsedMinBuyScore) || parsedMinBuyScore < 5 || parsedMinBuyScore > 100) {
      setError('Min buy score must be between 5 and 100');
      return;
    }
    if (!Number.isFinite(parsedTrailingStopPct) || parsedTrailingStopPct <= 0 || parsedTrailingStopPct > 100) {
      setError('Trailing stop must be greater than 0 and at most 100');
      return;
    }

    try {
      await onSubmit(config.id, {
        name: trimmedName,
        portfolio_strategy: portfolioStrategy,
        position_size: parsedPositionSize,
        min_buy_score: parsedMinBuyScore,
        trailing_stop_pct: parsedTrailingStopPct,
        max_per_sector: portfolioStrategy === 'none' ? null : parsedMaxPerSector,
        max_open_positions: portfolioStrategy === 'none' ? null : parsedMaxOpenPositions,
      });

      onOpenChange(false);
    } catch (err) {
      setError(extractErrorMessage(err, 'Failed to update portfolio setup'));
    }
  };

  if (!config) return null;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[520px] bg-bg-secondary border-default">
        <DialogHeader>
          <DialogTitle className="font-display text-lg font-semibold text-text-primary">
            Edit Portfolio Setup
          </DialogTitle>
          <DialogDescription className="text-sm text-text-muted">
            Update saved portfolio constraints
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit}>
          <div className="space-y-5 py-4">
            <div className="space-y-2">
              <Label htmlFor="edit-portfolio-name">Setup Name</Label>
              <Input
                id="edit-portfolio-name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                disabled={isSubmitting}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="edit-portfolio-strategy">Strategy</Label>
              <Select
                value={portfolioStrategy}
                onValueChange={setPortfolioStrategy}
                disabled={isSubmitting}
              >
                <SelectTrigger id="edit-portfolio-strategy">
                  <SelectValue placeholder="Select strategy..." />
                </SelectTrigger>
                <SelectContent>
                  {PORTFOLIO_STRATEGIES.map((strategy) => (
                    <SelectItem key={strategy.name} value={strategy.name}>
                      {strategy.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <p className="text-xs text-text-muted">
                {PORTFOLIO_STRATEGIES.find((s) => s.name === portfolioStrategy)?.description}
              </p>
            </div>

            <div className="grid grid-cols-3 gap-3">
              <div className="space-y-2">
                <Label htmlFor="edit-portfolio-position-size">Position Size ($)</Label>
                <Input
                  id="edit-portfolio-position-size"
                  type="number"
                  min="1"
                  value={positionSize}
                  onChange={(e) => setPositionSize(e.target.value)}
                  disabled={isSubmitting}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="edit-portfolio-min-buy-score">Min Buy Score</Label>
                <Input
                  id="edit-portfolio-min-buy-score"
                  type="number"
                  min="5"
                  max="100"
                  step="5"
                  value={minBuyScore}
                  onChange={(e) => setMinBuyScore(e.target.value)}
                  disabled={isSubmitting}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="edit-portfolio-trailing-stop">Trailing Stop (%)</Label>
                <Input
                  id="edit-portfolio-trailing-stop"
                  type="number"
                  min="0.1"
                  max="100"
                  step="0.5"
                  value={trailingStopPct}
                  onChange={(e) => setTrailingStopPct(e.target.value)}
                  disabled={isSubmitting}
                />
              </div>
            </div>

            {portfolioStrategy !== 'none' && (
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-2">
                  <Label htmlFor="edit-portfolio-max-per-sector">Max Per Sector</Label>
                  <Input
                    id="edit-portfolio-max-per-sector"
                    type="number"
                    min="1"
                    value={maxPerSector}
                    onChange={(e) => setMaxPerSector(e.target.value)}
                    disabled={isSubmitting}
                    placeholder="Optional"
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="edit-portfolio-max-open">Max Open Positions</Label>
                  <Input
                    id="edit-portfolio-max-open"
                    type="number"
                    min="1"
                    value={maxOpenPositions}
                    onChange={(e) => setMaxOpenPositions(e.target.value)}
                    disabled={isSubmitting}
                    placeholder="Optional"
                  />
                </div>
              </div>
            )}

            {error && <p className="text-sm text-accent-bearish">{error}</p>}
          </div>

          <DialogFooter className="gap-3 border-t border-subtle pt-5">
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)} disabled={isSubmitting}>
              Cancel
            </Button>
            <Button type="submit" disabled={isSubmitting}>
              {isSubmitting ? 'Saving...' : 'Save Changes'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
};
