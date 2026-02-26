import { AlertCircle, Loader2 } from 'lucide-react';
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

interface CancelAnalysisDialogProps {
  /** Whether the dialog is open */
  open: boolean;
  /** Callback when dialog open state changes */
  onOpenChange: (open: boolean) => void;
  /** Callback when cancel is confirmed */
  onConfirm: () => Promise<void>;
  /** Whether cancellation is in progress */
  isCancelling: boolean;
  /** Type of analysis being cancelled (e.g., "analysis", "simulation") */
  analysisType?: string;
}

/**
 * Confirmation dialog for cancelling a running analysis
 *
 * Uses AlertDialog component for cancellation pattern:
 * - Informational tone with info icon
 * - Reassures user that results will be saved
 * - Secondary button styling (not destructive)
 * - Shows loading state during cancellation
 *
 * Note: Error handling is the responsibility of the parent component.
 * This dialog will close on successful confirmation - errors should be
 * caught and displayed by the caller using their preferred method
 * (toast, page-level error state, etc.)
 */
export const CancelAnalysisDialog = ({
  open,
  onOpenChange,
  onConfirm,
  isCancelling,
  analysisType = 'analysis',
}: CancelAnalysisDialogProps) => {
  const handleConfirm = async (e: React.MouseEvent) => {
    e.preventDefault();
    try {
      await onConfirm();
      onOpenChange(false);
    } catch {
      // Error handling is parent's responsibility
      // Parent should catch errors and display them appropriately
    }
  };

  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent className="sm:max-w-[440px] bg-bg-secondary border-default">
        <AlertDialogHeader>
          <AlertDialogTitle className="font-display text-lg font-semibold text-text-primary">
            Stop {analysisType}?
          </AlertDialogTitle>
          <AlertDialogDescription className="text-sm text-text-muted">
            This will stop the running {analysisType}.
          </AlertDialogDescription>
        </AlertDialogHeader>

        <div className="flex items-start gap-3 p-4 bg-accent-primary-muted border border-accent-primary rounded-[10px]">
          <AlertCircle className="w-5 h-5 text-accent-primary flex-shrink-0 mt-0.5" />
          <p className="text-sm text-text-primary leading-relaxed">
            The {analysisType} will stop immediately. Any results already processed will be saved.
          </p>
        </div>

        <AlertDialogFooter className="gap-3 border-t border-subtle pt-5">
          <AlertDialogCancel
            disabled={isCancelling}
            className="border-default hover:bg-bg-tertiary"
          >
            Continue
          </AlertDialogCancel>
          <AlertDialogAction
            onClick={handleConfirm}
            disabled={isCancelling}
            className="bg-secondary text-secondary-foreground hover:bg-secondary/80"
          >
            {isCancelling && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            {isCancelling ? 'Stopping...' : `Stop ${analysisType}`}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
};
