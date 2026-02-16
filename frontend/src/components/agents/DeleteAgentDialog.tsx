import { useState, useEffect } from 'react';
import { AlertTriangle } from 'lucide-react';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '../ui/alert-dialog';
import type { AgentConfig } from '../../types/agentConfig';
import { extractErrorMessage } from '../../utils/errors';

interface DeleteAgentDialogProps {
  /** The agent config to delete */
  config: AgentConfig | null;
  /** Whether the dialog is open */
  open: boolean;
  /** Callback when dialog open state changes */
  onOpenChange: (open: boolean) => void;
  /** Callback when delete is confirmed */
  onConfirm: (config: AgentConfig) => Promise<void>;
  /** Whether deletion is in progress */
  isDeleting?: boolean;
}

/**
 * Confirmation dialog for deleting an agent configuration
 *
 * Uses AlertDialog component for destructive action pattern:
 * - Clear warning message with icon
 * - Shows agent name and algorithm being deleted
 * - Red/danger delete button
 */
export const DeleteAgentDialog = ({
  config,
  open,
  onOpenChange,
  onConfirm,
  isDeleting = false,
}: DeleteAgentDialogProps) => {
  const [error, setError] = useState<string | null>(null);

  // Clear error when dialog opens (including re-opens)
  useEffect(() => {
    if (open) {
      setError(null);
    }
  }, [open]);

  const handleConfirm = async (e: React.MouseEvent) => {
    // Prevent AlertDialogAction from auto-closing the dialog
    e.preventDefault();

    if (!config) return;

    setError(null);
    try {
      await onConfirm(config);
      onOpenChange(false);
    } catch (err) {
      setError(extractErrorMessage(err, 'Failed to delete agent configuration'));
    }
  };

  const handleOpenChange = (newOpen: boolean) => {
    if (!newOpen) {
      setError(null);
    }
    onOpenChange(newOpen);
  };

  if (!config) return null;

  return (
    <AlertDialog open={open} onOpenChange={handleOpenChange}>
      <AlertDialogContent className="sm:max-w-[440px] bg-bg-secondary border-default">
        <AlertDialogHeader>
          <AlertDialogTitle className="font-display text-lg font-semibold text-text-primary">
            Delete Agent
          </AlertDialogTitle>
          <AlertDialogDescription className="text-sm text-text-muted">
            This action cannot be undone. Existing runs will keep their settings.
          </AlertDialogDescription>
        </AlertDialogHeader>

        {/* Warning Box */}
        <div className="flex items-start gap-3 p-4 bg-accent-bearish-muted border border-accent-bearish rounded-[10px]">
          <AlertTriangle className="w-5 h-5 text-accent-bearish flex-shrink-0 mt-0.5" />
          <p className="text-sm text-text-primary leading-relaxed">
            Are you sure you want to delete{' '}
            <strong className="text-accent-bearish">&quot;{config.name}&quot;</strong>
            {' '}({config.scoring_algorithm.toUpperCase()})? This will permanently remove the agent configuration.
          </p>
        </div>

        {/* Error Display */}
        {error && (
          <p className="text-sm text-accent-bearish">{error}</p>
        )}

        <AlertDialogFooter className="gap-3 border-t border-subtle pt-5">
          <AlertDialogCancel
            disabled={isDeleting}
            className="border-default hover:bg-bg-tertiary"
          >
            Cancel
          </AlertDialogCancel>
          <AlertDialogAction
            onClick={handleConfirm}
            disabled={isDeleting}
            className="bg-accent-bearish text-white hover:bg-accent-bearish/90"
          >
            {isDeleting ? 'Deleting...' : 'Delete Agent'}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
};
