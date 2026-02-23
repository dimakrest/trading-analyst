import { useEffect, useState } from 'react';
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
import type { PortfolioConfig } from '../../types/portfolioConfig';
import { extractErrorMessage } from '../../utils/errors';

interface DeletePortfolioDialogProps {
  config: PortfolioConfig | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onConfirm: (config: PortfolioConfig) => Promise<void>;
  isDeleting?: boolean;
}

export const DeletePortfolioDialog = ({
  config,
  open,
  onOpenChange,
  onConfirm,
  isDeleting = false,
}: DeletePortfolioDialogProps) => {
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (open) {
      setError(null);
    }
  }, [open]);

  const handleConfirm = async (e: React.MouseEvent) => {
    e.preventDefault();
    if (!config) return;

    setError(null);
    try {
      await onConfirm(config);
      onOpenChange(false);
    } catch (err) {
      setError(extractErrorMessage(err, 'Failed to delete portfolio setup'));
    }
  };

  if (!config) return null;

  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent className="sm:max-w-[440px] bg-bg-secondary border-default">
        <AlertDialogHeader>
          <AlertDialogTitle className="font-display text-lg font-semibold text-text-primary">
            Delete Portfolio Setup
          </AlertDialogTitle>
          <AlertDialogDescription className="text-sm text-text-muted">
            This action cannot be undone. Existing simulations will keep their saved parameters.
          </AlertDialogDescription>
        </AlertDialogHeader>

        <div className="flex items-start gap-3 p-4 bg-accent-bearish-muted border border-accent-bearish rounded-[10px]">
          <AlertTriangle className="w-5 h-5 text-accent-bearish flex-shrink-0 mt-0.5" />
          <p className="text-sm text-text-primary leading-relaxed">
            Delete{' '}
            <strong className="text-accent-bearish">&quot;{config.name}&quot;</strong>?
          </p>
        </div>

        {error && <p className="text-sm text-accent-bearish">{error}</p>}

        <AlertDialogFooter className="gap-3 border-t border-subtle pt-5">
          <AlertDialogCancel disabled={isDeleting}>Cancel</AlertDialogCancel>
          <AlertDialogAction
            onClick={handleConfirm}
            disabled={isDeleting}
            className="bg-accent-bearish text-white hover:bg-accent-bearish/90"
          >
            {isDeleting ? 'Deleting...' : 'Delete Setup'}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
};
