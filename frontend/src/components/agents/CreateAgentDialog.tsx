import { useState } from 'react';
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
import type { CreateAgentConfigRequest, AgentConfig } from '../../types/agentConfig';
import type { ScoringAlgorithm } from '../../types/live20';
import { extractErrorMessage } from '../../utils/errors';

const DEFAULT_SIGNAL_SCORES = {
  volume_score: '25',
  candle_pattern_score: '25',
  cci_score: '25',
  ma20_distance_score: '25',
} as const;

interface CreateAgentDialogProps {
  /** Whether the dialog is open */
  open: boolean;
  /** Callback when dialog open state changes */
  onOpenChange: (open: boolean) => void;
  /** Callback when form is submitted */
  onSubmit: (data: CreateAgentConfigRequest) => Promise<AgentConfig>;
  /** Whether a submission is in progress */
  isSubmitting?: boolean;
}

/**
 * Dialog for creating a new agent configuration
 *
 * Form fields:
 * - Agent Name (required)
 * - Scoring Algorithm (ToggleGroup: CCI or RSI-2)
 */
export const CreateAgentDialog = ({
  open,
  onOpenChange,
  onSubmit,
  isSubmitting = false,
}: CreateAgentDialogProps) => {
  const [name, setName] = useState('');
  const [scoringAlgorithm, setScoringAlgorithm] = useState<ScoringAlgorithm>('cci');
  const [volumeScore, setVolumeScore] = useState(DEFAULT_SIGNAL_SCORES.volume_score);
  const [candlePatternScore, setCandlePatternScore] = useState(DEFAULT_SIGNAL_SCORES.candle_pattern_score);
  const [cciScore, setCciScore] = useState(DEFAULT_SIGNAL_SCORES.cci_score);
  const [ma20DistanceScore, setMa20DistanceScore] = useState(DEFAULT_SIGNAL_SCORES.ma20_distance_score);
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

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
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
      await onSubmit({
        name: trimmedName,
        scoring_algorithm: scoringAlgorithm,
        volume_score: parsedVolumeScore,
        candle_pattern_score: parsedCandlePatternScore,
        cci_score: parsedCciScore,
        ma20_distance_score: parsedMa20DistanceScore,
      });

      // Reset form on success
      setName('');
      setScoringAlgorithm('cci');
      setVolumeScore(DEFAULT_SIGNAL_SCORES.volume_score);
      setCandlePatternScore(DEFAULT_SIGNAL_SCORES.candle_pattern_score);
      setCciScore(DEFAULT_SIGNAL_SCORES.cci_score);
      setMa20DistanceScore(DEFAULT_SIGNAL_SCORES.ma20_distance_score);
      onOpenChange(false);
    } catch (err: unknown) {
      setError(extractErrorMessage(err, 'Failed to create agent configuration'));
    }
  };

  const handleCancel = () => {
    setName('');
    setScoringAlgorithm('cci');
    setVolumeScore(DEFAULT_SIGNAL_SCORES.volume_score);
    setCandlePatternScore(DEFAULT_SIGNAL_SCORES.candle_pattern_score);
    setCciScore(DEFAULT_SIGNAL_SCORES.cci_score);
    setMa20DistanceScore(DEFAULT_SIGNAL_SCORES.ma20_distance_score);
    setError(null);
    onOpenChange(false);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[480px] bg-bg-secondary border-default">
        <DialogHeader>
          <DialogTitle className="font-display text-lg font-semibold text-text-primary">
            Create New Agent
          </DialogTitle>
          <DialogDescription className="text-sm text-text-muted">
            Create a new agent configuration with a scoring algorithm preset
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit}>
          <div className="space-y-5 py-4">
            {/* Agent Name Field */}
            <div className="space-y-2">
              <Label
                htmlFor="agent-name"
                className="text-xs font-semibold uppercase tracking-[0.06em] text-text-muted"
              >
                Agent Name
              </Label>
              <Input
                id="agent-name"
                placeholder="e.g., RSI-2 Strategy"
                value={name}
                onChange={(e) => setName(e.target.value)}
                disabled={isSubmitting}
                autoFocus
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
                  <Label htmlFor="volume-score" className="text-xs text-text-muted">
                    Volume
                  </Label>
                  <Input
                    id="volume-score"
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
                  <Label htmlFor="candle-score" className="text-xs text-text-muted">
                    Candle Pattern
                  </Label>
                  <Input
                    id="candle-score"
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
                  <Label htmlFor="cci-score" className="text-xs text-text-muted">
                    CCI / Momentum
                  </Label>
                  <Input
                    id="cci-score"
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
                  <Label htmlFor="ma20-score" className="text-xs text-text-muted">
                    MA20 Distance
                  </Label>
                  <Input
                    id="ma20-score"
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
              {isSubmitting ? 'Creating...' : 'Create Agent'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
};
