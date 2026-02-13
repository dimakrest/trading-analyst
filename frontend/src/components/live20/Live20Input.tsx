import { useState, useRef, useEffect, useMemo } from 'react';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { MultiListSelector } from '@/components/molecules/MultiListSelector';
import { TrendingUp, Info } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useStockLists } from '@/hooks/useStockLists';

/** Maximum allowed symbols */
const MAX_SYMBOLS = 500;

interface Live20InputProps {
  /**
   * Callback when analyze button is clicked.
   * @param symbols - Parsed symbols from textarea (may differ from original lists)
   * @param sourceLists - The lists to associate with this run, or null if symbols
   *                      were modified or manually entered
   */
  onAnalyze: (
    symbols: string[],
    sourceLists: Array<{ id: number; name: string }> | null
  ) => void;
  /** Whether analysis is currently in progress */
  isAnalyzing: boolean;
}

/**
 * Input component for Live 20 symbol analysis
 *
 * Provides a textarea for entering comma/space/newline-separated stock symbols
 * with validation (max 500 symbols, max 10 chars per symbol). Shows symbol count
 * and validation feedback. Optionally allows selecting multiple stock lists to
 * populate symbols from (with deduplication).
 */
export function Live20Input({ onAnalyze, isAnalyzing }: Live20InputProps) {
  const [input, setInput] = useState('');
  const [selectedListIds, setSelectedListIds] = useState<number[]>([]);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Fetch stock lists
  const { lists, isLoading: listsLoading, error: listsError } = useStockLists();

  // Compute selected lists
  const selectedLists = useMemo(() => {
    return lists.filter((l) => selectedListIds.includes(l.id));
  }, [lists, selectedListIds]);

  const parseSymbols = (text: string): string[] => {
    return text
      .split(/[,\s\n]+/)
      .map((s) => s.trim().toUpperCase())
      .filter((s) => s.length > 0 && s.length <= 10);
  };

  const symbolSetsMatch = (a: string[], b: string[]): boolean => {
    const setA = new Set(a.map((s) => s.toUpperCase()));
    const setB = new Set(b.map((s) => s.toUpperCase()));
    return setA.size === setB.size && [...setA].every((s) => setB.has(s));
  };

  const symbols = parseSymbols(input);

  const combinedSymbolCount = useMemo(() => {
    if (selectedLists.length === 0) return 0;
    const uniqueSymbols = new Set<string>();
    selectedLists.forEach((list) => {
      list.symbols.forEach((symbol) => uniqueSymbols.add(symbol.toUpperCase()));
    });
    return uniqueSymbols.size;
  }, [selectedLists]);

  // Validation states
  const isOverLimit = symbols.length > MAX_SYMBOLS;
  const isNearLimit = symbols.length > MAX_SYMBOLS * 0.9 && !isOverLimit;
  const isValid = symbols.length > 0 && symbols.length <= MAX_SYMBOLS;

  const handleListSelectionChange = (listIds: number[]) => {
    setSelectedListIds(listIds);
    if (listIds.length > 0) {
      const uniqueSymbols = new Set<string>();
      listIds.forEach((listId) => {
        const list = lists.find((l) => l.id === listId);
        if (list) {
          list.symbols.forEach((symbol) => uniqueSymbols.add(symbol.toUpperCase()));
        }
      });

      const combinedSymbols = Array.from(uniqueSymbols).sort();
      setInput(combinedSymbols.join(', '));

      setTimeout(() => textareaRef.current?.focus(), 0);
    } else {
      setInput('');
    }
  };

  const symbolsMatchLists = useMemo(() => {
    if (selectedLists.length === 0) return false;

    const listSymbols = new Set<string>();
    selectedLists.forEach((list) => {
      list.symbols.forEach((symbol) => listSymbols.add(symbol.toUpperCase()));
    });

    return symbolSetsMatch(symbols, Array.from(listSymbols));
  }, [symbols, selectedLists]);

  const effectiveSourceLists = symbolsMatchLists
    ? selectedLists.map((l) => ({ id: l.id, name: l.name }))
    : null;

  useEffect(() => {
    if (selectedListIds.length === 0 || symbolsMatchLists) {
      return;
    }

    const timeoutId = setTimeout(() => {
      setSelectedListIds([]);
    }, 300);

    return () => clearTimeout(timeoutId);
  }, [selectedListIds.length, symbolsMatchLists]);

  const handleSubmit = () => {
    if (isValid) {
      onAnalyze(symbols, effectiveSourceLists);
    }
  };

  const getSymbolCountBadgeClass = () => {
    if (isOverLimit) {
      return 'border-destructive text-destructive';
    }
    if (isNearLimit) {
      return 'border-[#fbbf24] bg-[rgba(245,158,11,0.12)] text-[#fbbf24]';
    }
    return 'border-[rgba(167,139,250,0.3)] bg-[rgba(167,139,250,0.12)] text-[#c4b5fd]';
  };

  return (
    <div className="bg-bg-secondary rounded-xl border border-default p-5">
      <div className="grid grid-cols-1 lg:grid-cols-[1fr_320px] gap-5">
        {/* Left Column - Textarea */}
        <div className="flex flex-col gap-3">
          <div className="flex items-center justify-between">
            <label className="text-[11px] font-semibold uppercase tracking-wider text-text-muted">
              Enter Symbols
            </label>
            {symbols.length > 0 && (
              <Badge
                variant="outline"
                className={cn('font-mono text-xs', getSymbolCountBadgeClass())}
                aria-label={`${symbols.length} of ${MAX_SYMBOLS} symbols entered`}
              >
                {symbols.length}/{MAX_SYMBOLS}
              </Badge>
            )}
          </div>
          <Textarea
            ref={textareaRef}
            placeholder="AAPL, MSFT, GOOGL, TSLA...
or paste one symbol per line"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            className="min-h-[120px] bg-bg-tertiary border-default font-mono text-sm resize-y focus:border-accent-primary focus:ring-accent-primary-muted"
            disabled={isAnalyzing}
          />
          <p className="text-xs text-text-muted">
            {symbols.length > 0 ? (
              <>
                <strong className="text-text-secondary">{symbols.length}</strong> symbol{symbols.length !== 1 ? 's' : ''} entered (max {MAX_SYMBOLS})
              </>
            ) : (
              selectedLists.length > 0
                ? 'Symbols populated from lists. You can modify them before analyzing.'
                : 'Example: AAPL, MSFT, TSLA, NVDA, AMD'
            )}
          </p>
          {isOverLimit && (
            <p className="text-xs text-destructive">Max {MAX_SYMBOLS} symbols allowed</p>
          )}
        </div>

        {/* Right Column - Sidebar Controls */}
        <div className="flex flex-col gap-4 lg:border-l lg:border-subtle lg:pl-5 pt-4 lg:pt-0 border-t lg:border-t-0 border-subtle">
          {/* Multi-List Selector */}
          <div className="flex flex-col gap-2">
            <label className="text-[11px] font-semibold uppercase tracking-wider text-text-muted">
              Load from Lists
            </label>
            <MultiListSelector
              lists={lists}
              selectedListIds={selectedListIds}
              onSelectionChange={handleListSelectionChange}
              uniqueSymbolCount={combinedSymbolCount}
              maxSymbols={MAX_SYMBOLS}
              isLoading={listsLoading}
              disabled={isAnalyzing}
            />
          </div>

          {/* List fetch error */}
          {listsError && (
            <p className="text-sm text-destructive">Failed to load stock lists</p>
          )}

          {/* Info banner when multiple lists are combined */}
          {effectiveSourceLists && effectiveSourceLists.length > 1 && (
            <Alert className="border-[rgba(167,139,250,0.3)] bg-[rgba(167,139,250,0.08)]">
              <Info className="h-4 w-4 text-[#c4b5fd]" />
              <AlertDescription className="text-xs text-text-secondary">
                Combined {effectiveSourceLists.length} lists ({symbols.length} unique symbols)
              </AlertDescription>
            </Alert>
          )}

          {/* Analyze Button */}
          <Button
            onClick={handleSubmit}
            disabled={!isValid || isAnalyzing}
            className="bg-accent-primary hover:bg-accent-primary/90 text-white font-semibold py-3.5 rounded-[10px] mt-auto"
          >
            <TrendingUp className="w-[18px] h-[18px] mr-2" />
            {isAnalyzing ? 'Analyzing...' : 'Analyze Symbols'}
          </Button>
        </div>
      </div>
    </div>
  );
}
