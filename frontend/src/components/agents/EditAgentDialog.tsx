import { useState, useEffect } from 'react';
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
import { ToggleGroup, ToggleGroupItem } from '../ui/toggle-group';
import type { AgentConfig, UpdateAgentConfigRequest } from '../../types/agentConfig';
import type { ScoringAlgorithm } from '../../types/live20';
import { extractErrorMessage } from '../../utils/errors';

interface EditAgentDialogProps {
  /** The agent config being edited */
  config: AgentConfig | null;
  /** Whether the dialog is open */
  open: boolean;
  /** Callback when dialog open state changes */
  onOpenChange: (open: boolean) => void;
  /** Callback when form is submitted */
  onSubmit: (id: number, data: UpdateAgentConfigRequest) => Promise<AgentConfig>;
  /** Whether a submission is in progress */
  isSubmitting?: boolean;
}

/**
 * Dialog for editing an existing agent configuration
 *
 * Features:
 * - Edit agent name
 * - Change scoring algorithm
 */
export const EditAgentDialog = ({
  config,
  open,
  onOpenChange,
  onSubmit,
  isSubmitting = false,
}: EditAgentDialogProps) => {
  const [name, setName] = useState('');
  const [scoringAlgorithm, setScoringAlgorithm] = useState<ScoringAlgorithm>('cci');
  const [volumeScore, setVolumeScore] = useState('25');
  const [candlePatternScore, setCandlePatternScore] = useState('25');
  const [cciScore, setCciScore] = useState('25');
  const [ma20DistanceScore, setMa20DistanceScore] = useState('25');
  const [error, setError] = useState<string | null>(null);

  const parsedVolumeScore = Number.parseInt(volumeScore, 10);
  const parsedCandlePatternScore = Number.parseInt(candlePatternScore, 10);
  const parsedCciScore = Number.parseInt(cciScore, 10);
  const parsedMa20DistanceScore = Number.parseInt(ma20DistanceScore, 10);
  const scoreValues = [
    parsedVolumeScore,
    parsedCandlePatternScore,
    parsedCciScore,
    parsedMa20DistanceScore,
  ];
  const areScoresValid = scoreValues.every(
    (score) => Number.isInteger(score) && score >= 0 && score <= 100
  );
  const totalScore = areScoresValid ? scoreValues.reduce((sum, score) => sum + score, 0) : null;

  // Reset form when config changes or dialog opens
  useEffect(() => {
    if (config && open) {
      setName(config.name);
      setScoringAlgorithm(config.scoring_algorithm);
      setVolumeScore((config.volume_score ?? 25).toString());
      setCandlePatternScore((config.candle_pattern_score ?? 25).toString());
      setCciScore((config.cci_score ?? 25).toString());
      setMa20DistanceScore((config.ma20_distance_score ?? 25).toString());
      setError(null);
    }
  }, [config, open]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!config) return;

    setError(null);

    // Validate name
    const trimmedName = name.trim();
    if (!trimmedName) {
      setError('Agent name is required');
      return;
    }
    if (!areScoresValid) {
      setError('All signal scores must be integers between 0 and 100');
      return;
    }
    if (totalScore !== 100) {
      setError(`Signal scores must sum to 100 (current total: ${totalScore})`);
      return;
    }

    try {
      await onSubmit(config.id, {
        name: trimmedName,
        scoring_algorithm: scoringAlgorithm,
        volume_score: parsedVolumeScore,
        candle_pattern_score: parsedCandlePatternScore,
        cci_score: parsedCciScore,
        ma20_distance_score: parsedMa20DistanceScore,
      });

      onOpenChange(false);
    } catch (err) {
      setError(extractErrorMessage(err, 'Failed to update agent configuration'));
    }
  };

  const handleCancel = () => {
    setError(null);
    onOpenChange(false);
  };

  if (!config) return null;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[480px] bg-bg-secondary border-default">
        <DialogHeader>
          <DialogTitle className="font-display text-lg font-semibold text-text-primary">
            Edit Agent
          </DialogTitle>
          <DialogDescription className="text-sm text-text-muted">
            Update agent name and scoring algorithm
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit}>
          <div className="space-y-5 py-4">
            {/* Agent Name Field */}
            <div className="space-y-2">
              <Label
                htmlFor="edit-agent-name"
                className="text-xs font-semibold uppercase tracking-[0.06em] text-text-muted"
              >
                Agent Name
              </Label>
              <Input
                id="edit-agent-name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                disabled={isSubmitting}
                className="bg-bg-tertiary border-default focus:border-accent-primary focus:ring-2 focus:ring-accent-primary-muted"
              />
            </div>

            {/* Scoring Algorithm Field */}
            <div className="space-y-2">
              <Label className="text-xs font-semibold uppercase tracking-[0.06em] text-text-muted">
                Scoring Algorithm
              </Label>
              <ToggleGroup
                type="single"
                value={scoringAlgorithm}
                onValueChange={(value) => value && setScoringAlgorithm(value as ScoringAlgorithm)}
                disabled={isSubmitting}
                className="justify-start gap-2"
              >
                <ToggleGroupItem
                  value="cci"
                  aria-label="Select CCI algorithm"
                  className="flex-1 data-[state=on]:bg-accent-primary data-[state=on]:text-white"
                >
                  CCI
                </ToggleGroupItem>
                <ToggleGroupItem
                  value="rsi2"
                  aria-label="Select RSI-2 algorithm"
                  className="flex-1 data-[state=on]:bg-accent-primary data-[state=on]:text-white"
                >
                  RSI-2
                </ToggleGroupItem>
              </ToggleGroup>
              <p className="text-xs text-text-muted">
                {scoringAlgorithm === 'cci'
                  ? 'CCI: Binary 20-point momentum scoring (default)'
                  : 'RSI-2: Graduated 0-20 point momentum scoring for mean-reversion'}
              </p>
            </div>

            {/* Signal Scores */}
            <div className="space-y-3">
              <Label className="text-xs font-semibold uppercase tracking-[0.06em] text-text-muted">
                Signal Scores (Total = 100)
              </Label>
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1">
                  <Label htmlFor="edit-volume-score" className="text-xs text-text-muted">
                    Volume
                  </Label>
                  <Input
                    id="edit-volume-score"
                    type="number"
                    min="0"
                    max="100"
                    step="1"
                    value={volumeScore}
                    onChange={(e) => setVolumeScore(e.target.value)}
                    disabled={isSubmitting}
                    className="bg-bg-tertiary border-default focus:border-accent-primary focus:ring-2 focus:ring-accent-primary-muted"
                  />
                </div>
                <div className="space-y-1">
                  <Label htmlFor="edit-candle-score" className="text-xs text-text-muted">
                    Candle Pattern
                  </Label>
                  <Input
                    id="edit-candle-score"
                    type="number"
                    min="0"
                    max="100"
                    step="1"
                    value={candlePatternScore}
                    onChange={(e) => setCandlePatternScore(e.target.value)}
                    disabled={isSubmitting}
                    className="bg-bg-tertiary border-default focus:border-accent-primary focus:ring-2 focus:ring-accent-primary-muted"
                  />
                </div>
                <div className="space-y-1">
                  <Label htmlFor="edit-cci-score" className="text-xs text-text-muted">
                    CCI / Momentum
                  </Label>
                  <Input
                    id="edit-cci-score"
                    type="number"
                    min="0"
                    max="100"
                    step="1"
                    value={cciScore}
                    onChange={(e) => setCciScore(e.target.value)}
                    disabled={isSubmitting}
                    className="bg-bg-tertiary border-default focus:border-accent-primary focus:ring-2 focus:ring-accent-primary-muted"
                  />
                </div>
                <div className="space-y-1">
                  <Label htmlFor="edit-ma20-score" className="text-xs text-text-muted">
                    MA20 Distance
                  </Label>
                  <Input
                    id="edit-ma20-score"
                    type="number"
                    min="0"
                    max="100"
                    step="1"
                    value={ma20DistanceScore}
                    onChange={(e) => setMa20DistanceScore(e.target.value)}
                    disabled={isSubmitting}
                    className="bg-bg-tertiary border-default focus:border-accent-primary focus:ring-2 focus:ring-accent-primary-muted"
                  />
                </div>
              </div>
              <p className="text-xs text-text-muted">
                Current total: <span className={totalScore === 100 ? 'text-text-primary' : 'text-accent-bearish'}>{totalScore ?? '-'}</span>
              </p>
            </div>

            {/* Error Display */}
            {error && (
              <p className="text-sm text-accent-bearish">{error}</p>
            )}
          </div>

          <DialogFooter className="gap-3 border-t border-subtle pt-5">
            <Button
              type="button"
              variant="outline"
              onClick={handleCancel}
              disabled={isSubmitting}
              className="border-default hover:bg-bg-tertiary"
            >
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
