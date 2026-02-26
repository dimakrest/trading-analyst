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
import type { StockList } from '../../services/stockListService';

/**
 * Extract user-friendly error message from various error types
 */
const extractErrorMessage = (err: unknown): string => {
  if (err && typeof err === 'object') {
    // Check for Axios error response structure
    const axiosErr = err as { response?: { data?: { detail?: string } }; message?: string };
    if (axiosErr.response?.data?.detail) {
      return axiosErr.response.data.detail;
    }
    if (axiosErr.message) {
      return axiosErr.message;
    }
  }
  return 'Failed to delete list';
};

interface DeleteListDialogProps {
  /** The stock list to delete */
  list: StockList | null;
  /** Whether the dialog is open */
  open: boolean;
  /** Callback when dialog open state changes */
  onOpenChange: (open: boolean) => void;
  /** Callback when delete is confirmed */
  onConfirm: (list: StockList) => Promise<void>;
  /** Whether deletion is in progress */
  isDeleting?: boolean;
}

/**
 * Confirmation dialog for deleting a stock list
 *
 * Uses AlertDialog component for destructive action pattern:
 * - Clear warning message with icon
 * - Shows list name being deleted
 * - Red/danger delete button
 */
export const DeleteListDialog = ({
  list,
  open,
  onOpenChange,
  onConfirm,
  isDeleting = false,
}: DeleteListDialogProps) => {
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

    if (!list) return;

    setError(null);
    try {
      await onConfirm(list);
      onOpenChange(false);
    } catch (err) {
      setError(extractErrorMessage(err));
    }
  };

  const handleOpenChange = (newOpen: boolean) => {
    if (!newOpen) {
      setError(null);
    }
    onOpenChange(newOpen);
  };

  if (!list) return null;

  return (
    <AlertDialog open={open} onOpenChange={handleOpenChange}>
      <AlertDialogContent className="sm:max-w-[440px] bg-bg-secondary border-default">
        <AlertDialogHeader>
          <AlertDialogTitle className="font-display text-lg font-semibold text-text-primary">
            Delete List
          </AlertDialogTitle>
          <AlertDialogDescription className="text-sm text-text-muted">
            This action cannot be undone.
          </AlertDialogDescription>
        </AlertDialogHeader>

        {/* Warning Box */}
        <div className="flex items-start gap-3 p-4 bg-accent-bearish-muted border border-accent-bearish rounded-[10px]">
          <AlertTriangle className="w-5 h-5 text-accent-bearish flex-shrink-0 mt-0.5" />
          <p className="text-sm text-text-primary leading-relaxed">
            Are you sure you want to delete{' '}
            <strong className="text-accent-bearish">&quot;{list.name}&quot;</strong>?
            This will permanently remove the list and all {list.symbol_count} symbol{list.symbol_count !== 1 ? 's' : ''} in it.
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
            {isDeleting ? 'Deleting...' : 'Delete List'}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
};
