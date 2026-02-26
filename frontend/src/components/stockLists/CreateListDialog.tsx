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
import { Textarea } from '../ui/textarea';
import type { CreateStockListRequest } from '../../services/stockListService';

interface CreateListDialogProps {
  /** Whether the dialog is open */
  open: boolean;
  /** Callback when dialog open state changes */
  onOpenChange: (open: boolean) => void;
  /** Callback when form is submitted */
  onSubmit: (data: CreateStockListRequest) => Promise<void>;
  /** Whether a submission is in progress */
  isSubmitting?: boolean;
}

/**
 * Parse comma-separated symbols input into array
 * - Splits by comma
 * - Trims whitespace
 * - Converts to uppercase
 * - Removes empty strings and duplicates
 */
const parseSymbols = (input: string): string[] => {
  const symbols = input
    .split(',')
    .map((s) => s.trim().toUpperCase())
    .filter((s) => s.length > 0);
  // Remove duplicates
  return [...new Set(symbols)];
};

/**
 * Dialog for creating a new stock list
 *
 * Form fields:
 * - List Name (required)
 * - Symbols (optional, comma-separated)
 */
export const CreateListDialog = ({
  open,
  onOpenChange,
  onSubmit,
  isSubmitting = false,
}: CreateListDialogProps) => {
  const [name, setName] = useState('');
  const [symbolsInput, setSymbolsInput] = useState('');
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    // Validate name
    const trimmedName = name.trim();
    if (!trimmedName) {
      setError('List name is required');
      return;
    }

    try {
      const symbols = parseSymbols(symbolsInput);
      await onSubmit({
        name: trimmedName,
        symbols: symbols.length > 0 ? symbols : undefined,
      });

      // Reset form on success
      setName('');
      setSymbolsInput('');
      onOpenChange(false);
    } catch (err: unknown) {
      // Extract error message from Axios error response or Error object
      let errorMessage = 'Failed to create list';
      if (err && typeof err === 'object') {
        // Check for Axios error response structure
        const axiosErr = err as { response?: { data?: { detail?: string } }; message?: string };
        if (axiosErr.response?.data?.detail) {
          errorMessage = axiosErr.response.data.detail;
        } else if (axiosErr.message) {
          errorMessage = axiosErr.message;
        }
      }
      setError(errorMessage);
    }
  };

  const handleCancel = () => {
    setName('');
    setSymbolsInput('');
    setError(null);
    onOpenChange(false);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[480px] bg-bg-secondary border-default">
        <DialogHeader>
          <DialogTitle className="font-display text-lg font-semibold text-text-primary">
            Create New List
          </DialogTitle>
          <DialogDescription className="text-sm text-text-muted">
            Create a new stock list to organize your watchlist
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit}>
          <div className="space-y-5 py-4">
            {/* List Name Field */}
            <div className="space-y-2">
              <Label
                htmlFor="list-name"
                className="text-xs font-semibold uppercase tracking-[0.06em] text-text-muted"
              >
                List Name
              </Label>
              <Input
                id="list-name"
                placeholder="e.g., Tech Leaders"
                value={name}
                onChange={(e) => setName(e.target.value)}
                disabled={isSubmitting}
                autoFocus
                className="bg-bg-tertiary border-default focus:border-accent-primary focus:ring-2 focus:ring-accent-primary-muted"
              />
            </div>

            {/* Symbols Field */}
            <div className="space-y-2">
              <Label
                htmlFor="symbols"
                className="text-xs font-semibold uppercase tracking-[0.06em] text-text-muted"
              >
                Symbols (Optional)
              </Label>
              <Textarea
                id="symbols"
                placeholder="AAPL, MSFT, GOOGL..."
                value={symbolsInput}
                onChange={(e) => setSymbolsInput(e.target.value)}
                disabled={isSubmitting}
                className="min-h-[100px] font-mono text-sm bg-bg-tertiary border-default focus:border-accent-primary focus:ring-2 focus:ring-accent-primary-muted resize-y"
              />
              <p className="text-xs text-text-muted">
                Comma-separated. You can add more symbols later.
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
              {isSubmitting ? 'Creating...' : 'Create List'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
};
