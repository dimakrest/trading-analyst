import { useState, useRef } from 'react';
import { Upload } from 'lucide-react';
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
import { parseTradingViewFile } from '../../utils/tradingViewParser';

interface ImportListDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSubmit: (data: { name: string; symbols: string[] }) => Promise<void>;
  isSubmitting?: boolean;
}

export const ImportListDialog = ({
  open,
  onOpenChange,
  onSubmit,
  isSubmitting = false,
}: ImportListDialogProps) => {
  const [symbols, setSymbols] = useState<string[] | null>(null);
  const [name, setName] = useState('');
  const [fileName, setFileName] = useState('');
  const [parseError, setParseError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setFileName(file.name);

    const reader = new FileReader();
    reader.onload = (event) => {
      const text = event.target?.result as string;
      const result = parseTradingViewFile(text);
      if (!result) {
        setSymbols(null);
        setName('');
        setParseError('No recognisable symbols found. Please export a watchlist from TradingView.');
      } else {
        setSymbols(result.symbols);
        setName(result.name || file.name.replace(/\.[^.]+$/, ''));
        setParseError(null);
      }
      setError(null);
    };
    reader.readAsText(file);
  };

  const handleImport = async () => {
    if (!symbols) return;
    const trimmedName = name.trim();
    if (!trimmedName) return;

    setError(null);
    try {
      await onSubmit({ name: trimmedName, symbols });
      handleClose();
    } catch (err: unknown) {
      let message = 'Failed to import list';
      if (err && typeof err === 'object') {
        const axiosErr = err as { response?: { data?: { detail?: string } }; message?: string };
        if (axiosErr.response?.data?.detail) {
          message = axiosErr.response.data.detail;
        } else if (axiosErr.message) {
          message = axiosErr.message;
        }
      }
      setError(message);
    }
  };

  const handleClose = () => {
    setSymbols(null);
    setName('');
    setFileName('');
    setParseError(null);
    setError(null);
    if (fileInputRef.current) fileInputRef.current.value = '';
    onOpenChange(false);
  };

  const PREVIEW_LIMIT = 5;
  const canImport = symbols !== null && name.trim().length > 0;

  return (
    <Dialog open={open} onOpenChange={(o) => !o && handleClose()}>
      <DialogContent className="sm:max-w-[480px] bg-bg-secondary border-default">
        <DialogHeader>
          <DialogTitle className="font-display text-lg font-semibold text-text-primary">
            Import from TradingView
          </DialogTitle>
          <DialogDescription className="text-sm text-text-muted">
            Select a TradingView watchlist export (.txt) to import as a new list
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-5 py-4">
          {/* File Input */}
          <div className="space-y-2">
            <Label
              htmlFor="tv-file"
              className="text-xs font-semibold uppercase tracking-[0.06em] text-text-muted"
            >
              Watchlist File
            </Label>
            <label
              htmlFor="tv-file"
              className="flex items-center gap-3 px-4 py-3 rounded-lg border border-dashed border-default bg-bg-tertiary hover:border-accent-primary hover:bg-accent-primary-muted cursor-pointer transition-colors duration-150"
            >
              <Upload className="w-4 h-4 text-text-muted flex-shrink-0" />
              <span className="text-sm text-text-muted truncate">
                {fileName || 'Choose .txt file\u2026'}
              </span>
              <input
                id="tv-file"
                ref={fileInputRef}
                type="file"
                accept=".txt"
                className="sr-only"
                onChange={handleFileChange}
                disabled={isSubmitting}
              />
            </label>
          </div>

          {/* Parse Error */}
          {parseError && (
            <p className="text-sm text-accent-bearish">{parseError}</p>
          )}

          {/* Name + Preview — shown once file is parsed */}
          {symbols !== null && (
            <>
              {/* List Name */}
              <div className="space-y-2">
                <Label
                  htmlFor="import-name"
                  className="text-xs font-semibold uppercase tracking-[0.06em] text-text-muted"
                >
                  List Name
                </Label>
                <Input
                  id="import-name"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  disabled={isSubmitting}
                  className="bg-bg-tertiary border-default focus:border-accent-primary focus:ring-2 focus:ring-accent-primary-muted"
                />
              </div>

              {/* Symbol Preview */}
              <div className="space-y-2 p-4 rounded-lg bg-bg-tertiary border border-default">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold uppercase tracking-[0.06em] text-text-muted">
                    Symbols detected
                  </span>
                  <span className="px-2.5 py-1 bg-bg-elevated rounded-md font-mono text-[13px] font-semibold">
                    {symbols.length}
                  </span>
                </div>
                <div className="flex flex-wrap gap-1.5">
                  {symbols.slice(0, PREVIEW_LIMIT).map((symbol) => (
                    <span
                      key={symbol}
                      className="px-2.5 py-1 bg-bg-secondary border border-default rounded-md font-mono text-[11px] font-semibold text-text-secondary"
                    >
                      {symbol}
                    </span>
                  ))}
                  {symbols.length > PREVIEW_LIMIT && (
                    <span className="px-2.5 py-1 border border-dashed border-default rounded-md font-mono text-[11px] text-text-muted">
                      +{symbols.length - PREVIEW_LIMIT} more
                    </span>
                  )}
                </div>
              </div>
            </>
          )}

          {/* Import Error */}
          {error && (
            <p className="text-sm text-accent-bearish">{error}</p>
          )}
        </div>

        <DialogFooter className="gap-3 border-t border-subtle pt-5">
          <Button
            type="button"
            variant="outline"
            onClick={handleClose}
            disabled={isSubmitting}
            className="border-default hover:bg-bg-tertiary"
          >
            Cancel
          </Button>
          <Button
            type="button"
            onClick={handleImport}
            disabled={!canImport || isSubmitting}
          >
            {isSubmitting ? 'Importing\u2026' : 'Import'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};
