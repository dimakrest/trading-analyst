import { useState, useEffect } from 'react';
import { X } from 'lucide-react';
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
import { ScrollArea } from '../ui/scroll-area';
import type { StockList, UpdateStockListRequest } from '../../services/stockListService';

interface EditListDialogProps {
  /** The stock list being edited */
  list: StockList | null;
  /** Whether the dialog is open */
  open: boolean;
  /** Callback when dialog open state changes */
  onOpenChange: (open: boolean) => void;
  /** Callback when form is submitted */
  onSubmit: (id: number, data: UpdateStockListRequest) => Promise<void>;
  /** Whether a submission is in progress */
  isSubmitting?: boolean;
}

/**
 * Parse comma-separated symbols input into array
 */
const parseSymbols = (input: string): string[] => {
  const symbols = input
    .split(',')
    .map((s) => s.trim().toUpperCase())
    .filter((s) => s.length > 0);
  return [...new Set(symbols)];
};

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
  return 'Failed to update list';
};

/**
 * Dialog for editing an existing stock list
 *
 * Features:
 * - Edit list name
 * - View and remove existing symbols
 * - Add new symbols via comma-separated input
 */
export const EditListDialog = ({
  list,
  open,
  onOpenChange,
  onSubmit,
  isSubmitting = false,
}: EditListDialogProps) => {
  const [name, setName] = useState('');
  const [symbols, setSymbols] = useState<string[]>([]);
  const [addSymbolsInput, setAddSymbolsInput] = useState('');
  const [error, setError] = useState<string | null>(null);

  // Reset form when list changes or dialog opens
  useEffect(() => {
    if (list && open) {
      setName(list.name);
      setSymbols([...list.symbols]);
      setAddSymbolsInput('');
      setError(null);
    }
  }, [list, open]);

  const handleRemoveSymbol = (symbolToRemove: string) => {
    setSymbols((prev) => prev.filter((s) => s !== symbolToRemove));
  };

  const handleAddSymbols = () => {
    const newSymbols = parseSymbols(addSymbolsInput);
    if (newSymbols.length > 0) {
      // Merge with existing, removing duplicates
      setSymbols((prev) => [...new Set([...prev, ...newSymbols])]);
      setAddSymbolsInput('');
    }
  };

  const handleAddSymbolsKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      handleAddSymbols();
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!list) return;

    setError(null);

    // Validate name
    const trimmedName = name.trim();
    if (!trimmedName) {
      setError('List name is required');
      return;
    }

    try {
      await onSubmit(list.id, {
        name: trimmedName,
        symbols,
      });

      onOpenChange(false);
    } catch (err) {
      setError(extractErrorMessage(err));
    }
  };

  const handleCancel = () => {
    setError(null);
    onOpenChange(false);
  };

  if (!list) return null;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[500px] bg-bg-secondary border-default">
        <DialogHeader>
          <DialogTitle className="font-display text-lg font-semibold text-text-primary">
            Edit List
          </DialogTitle>
          <DialogDescription className="text-sm text-text-muted">
            Update list name and manage symbols
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit}>
          <div className="space-y-5 py-4">
            {/* List Name Field */}
            <div className="space-y-2">
              <Label
                htmlFor="edit-list-name"
                className="text-xs font-semibold uppercase tracking-[0.06em] text-text-muted"
              >
                List Name
              </Label>
              <Input
                id="edit-list-name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                disabled={isSubmitting}
                className="bg-bg-tertiary border-default focus:border-accent-primary focus:ring-2 focus:ring-accent-primary-muted"
              />
            </div>

            {/* Current Symbols Section */}
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <Label className="text-xs font-semibold uppercase tracking-[0.06em] text-text-muted">
                  Current Symbols
                </Label>
                <span className="font-mono text-[11px] text-text-secondary">
                  {symbols.length} symbol{symbols.length !== 1 ? 's' : ''}
                </span>
              </div>
              <ScrollArea className="h-[120px] rounded-lg bg-bg-tertiary p-3">
                {symbols.length === 0 ? (
                  <p className="text-sm text-text-muted text-center py-4">
                    No symbols in this list
                  </p>
                ) : (
                  <div className="flex flex-wrap gap-2">
                    {symbols.map((symbol) => (
                      <div
                        key={symbol}
                        className="flex items-center gap-1.5 px-2.5 py-1.5 bg-bg-elevated border border-default rounded-md"
                      >
                        <span className="font-mono text-xs font-semibold text-text-primary">
                          {symbol}
                        </span>
                        <button
                          type="button"
                          onClick={() => handleRemoveSymbol(symbol)}
                          disabled={isSubmitting}
                          className="w-3.5 h-3.5 flex items-center justify-center text-text-muted hover:text-accent-bearish transition-colors"
                          aria-label={`Remove ${symbol}`}
                        >
                          <X className="w-3 h-3" />
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </ScrollArea>
            </div>

            {/* Add Symbols Field */}
            <div className="space-y-2">
              <Label
                htmlFor="add-symbols"
                className="text-xs font-semibold uppercase tracking-[0.06em] text-text-muted"
              >
                Add Symbols
              </Label>
              <div className="flex gap-2">
                <Input
                  id="add-symbols"
                  placeholder="NFLX, CRM, INTC..."
                  value={addSymbolsInput}
                  onChange={(e) => setAddSymbolsInput(e.target.value)}
                  onKeyDown={handleAddSymbolsKeyDown}
                  disabled={isSubmitting}
                  className="flex-1 bg-bg-tertiary border-default focus:border-accent-primary focus:ring-2 focus:ring-accent-primary-muted"
                />
                <Button
                  type="button"
                  variant="outline"
                  onClick={handleAddSymbols}
                  disabled={isSubmitting || !addSymbolsInput.trim()}
                  className="border-default hover:bg-accent-primary-muted hover:border-accent-primary hover:text-accent-primary"
                >
                  Add
                </Button>
              </div>
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
