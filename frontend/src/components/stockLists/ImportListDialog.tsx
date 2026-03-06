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
import { stockListService } from '../../services/stockListService';

interface ImportListDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSuccess: (name: string) => void;
}

interface ParsedWatchlist {
  /** Name from ###header### or empty string when absent (user must fill in) */
  name: string;
  symbols: string[];
}

// Matches a valid ticker: 1–10 uppercase letters only (after stripping exchange prefix)
const SYMBOL_RE = /^[A-Z]{1,10}$/;

/**
 * Parse a TradingView exported watchlist file.
 *
 * Handles two formats:
 *   1. With header:  "###My List###\nNASDAQ:AAPL,NYSE:MSFT,..."
 *   2. Without header (most exports): "NASDAQ:AAPL,NYSE:MSFT,..."
 *
 * Tokens may be comma- or space-separated; exchange prefixes are stripped.
 * Invalid tokens (punctuation, URLs, notes) are silently ignored.
 *
 * Returns null only when no recognisable symbols are found at all.
 */
const parseTradingViewFile = (text: string): ParsedWatchlist | null => {
  const lines = text.trim().split('\n').filter(Boolean);
  if (lines.length === 0) return null;

  let name = '';
  let symbolLines = lines;

  const header = lines[0].match(/^###(.+)###$/);
  if (header) {
    name = header[1].trim();
    symbolLines = lines.slice(1);
  }

  const symbols = [
    ...new Set(
      symbolLines
        .join(',')
        .split(/[,\s]+/)                          // split on commas or whitespace
        .map((token) => {
          const stripped = token
            .split(':').pop()!                    // strip exchange prefix
            .replace(/[^A-Za-z]/g, '')            // remove punctuation / dots
            .toUpperCase();
          return stripped;
        })
        .filter((s) => SYMBOL_RE.test(s))
    ),
  ];

  if (symbols.length === 0) return null;
  return { name, symbols };
};

export const ImportListDialog = ({ open, onOpenChange, onSuccess }: ImportListDialogProps) => {
  const [symbols, setSymbols] = useState<string[] | null>(null);
  const [name, setName] = useState('');
  const [fileName, setFileName] = useState('');
  const [parseError, setParseError] = useState<string | null>(null);
  const [isImporting, setIsImporting] = useState(false);
  const [importError, setImportError] = useState<string | null>(null);
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
        // Pre-fill name from header if present, else use filename without extension
        setName(result.name || file.name.replace(/\.[^.]+$/, ''));
        setParseError(null);
      }
      setImportError(null);
    };
    reader.readAsText(file);
  };

  const handleImport = async () => {
    if (!symbols) return;
    const trimmedName = name.trim();
    if (!trimmedName) return;

    setIsImporting(true);
    setImportError(null);
    try {
      await stockListService.createList({ name: trimmedName, symbols });
      onSuccess(trimmedName);
      handleClose();
    } catch (err: unknown) {
      let message = 'Failed to import list';
      if (err && typeof err === 'object') {
        const axiosErr = err as { response?: { data?: { detail?: unknown } }; message?: string };
        const detail = axiosErr.response?.data?.detail;
        if (typeof detail === 'string') {
          message = detail;
        } else if (Array.isArray(detail)) {
          // FastAPI 422: array of Pydantic validation error objects
          message = detail
            .map((e) => (e && typeof e === 'object' && 'msg' in e ? String(e.msg) : String(e)))
            .join('; ');
        } else if (axiosErr.message) {
          message = axiosErr.message;
        }
      }
      setImportError(message);
    } finally {
      setIsImporting(false);
    }
  };

  const handleClose = () => {
    setSymbols(null);
    setName('');
    setFileName('');
    setParseError(null);
    setImportError(null);
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
                {fileName || 'Choose .txt file…'}
              </span>
              <input
                id="tv-file"
                ref={fileInputRef}
                type="file"
                accept=".txt"
                className="sr-only"
                onChange={handleFileChange}
                disabled={isImporting}
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
                  disabled={isImporting}
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
          {importError && (
            <p className="text-sm text-accent-bearish">{importError}</p>
          )}
        </div>

        <DialogFooter className="gap-3 border-t border-subtle pt-5">
          <Button
            type="button"
            variant="outline"
            onClick={handleClose}
            disabled={isImporting}
            className="border-default hover:bg-bg-tertiary"
          >
            Cancel
          </Button>
          <Button
            type="button"
            onClick={handleImport}
            disabled={!canImport || isImporting}
          >
            {isImporting ? 'Importing…' : 'Import'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};
