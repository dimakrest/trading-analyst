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
  const [error, setError] = useState<string | null>(null);

  // Reset form when config changes or dialog opens
  useEffect(() => {
    if (config && open) {
      setName(config.name);
      setScoringAlgorithm(config.scoring_algorithm);
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

    try {
      await onSubmit(config.id, {
        name: trimmedName,
        scoring_algorithm: scoringAlgorithm,
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
