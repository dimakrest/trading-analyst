import { AlertTriangle, Loader2 } from 'lucide-react';
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

interface DeleteAnalysisDialogProps {
  /** Whether the dialog is open */
  open: boolean;
  /** Callback when dialog open state changes */
  onOpenChange: (open: boolean) => void;
  /** Callback when delete is confirmed */
  onConfirm: () => Promise<void>;
  /** Whether deletion is in progress */
  isDeleting: boolean;
  /** Type of analysis being deleted (e.g., "analysis run", "simulation") */
  analysisType?: string;
}

/**
 * Confirmation dialog for permanently deleting an analysis
 *
 * Uses AlertDialog component for destructive action pattern:
 * - Clear warning message with icon
 * - Red/danger delete button
 * - Shows loading state during deletion
 *
 * Note: Error handling is the responsibility of the parent component.
 * This dialog will close on successful confirmation - errors should be
 * caught and displayed by the caller using their preferred method
 * (toast, page-level error state, etc.)
 */
export const DeleteAnalysisDialog = ({
  open,
  onOpenChange,
  onConfirm,
  isDeleting,
  analysisType = 'analysis run',
}: DeleteAnalysisDialogProps) => {
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
            Delete {analysisType}?
          </AlertDialogTitle>
          <AlertDialogDescription className="text-sm text-text-muted">
            This action cannot be undone.
          </AlertDialogDescription>
        </AlertDialogHeader>

        <div className="flex items-start gap-3 p-4 bg-accent-bearish-muted border border-accent-bearish rounded-[10px]">
          <AlertTriangle className="w-5 h-5 text-accent-bearish flex-shrink-0 mt-0.5" />
          <p className="text-sm text-text-primary leading-relaxed">
            This will permanently remove this {analysisType} and all its results from your history.
          </p>
        </div>

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
            {isDeleting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            {isDeleting ? 'Deleting...' : 'Delete'}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
};
