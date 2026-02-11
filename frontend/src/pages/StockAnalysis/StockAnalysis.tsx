import { useState } from 'react';
import { useParams } from 'react-router-dom';
import { List } from 'lucide-react';
import { useStockData } from '../../hooks/useStockData';
import { useStockInfo } from '../../hooks/useStockInfo';
import { useStockSearch } from '../../hooks/useStockSearch';
import { useStockLists } from '../../hooks/useStockLists';
import { SearchBar } from '../../components/molecules/SearchBar/SearchBar';
import { WatchlistPanel } from '../../components/watchlist';
import { StockHero } from '../../components/molecules/StockHero';
import { CandlestickChart } from '../../components/organisms/CandlestickChart/CandlestickChart';
import { IntervalSelector } from '../../components/molecules/IntervalSelector';
import { Button } from '../../components/ui/button';
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from '../../components/ui/sheet';
import type { Interval, StockData } from '../../types/stock';
import type { StockHeroStats } from '../../components/molecules/StockHero';

/**
 * Extract stats from StockData for the StockHero component.
 * Uses the latest price entry for current day stats.
 */
function getStatsFromData(data: StockData): StockHeroStats {
  const latestPrice = data.prices[data.prices.length - 1];
  const prevPrice = data.prices.length > 1 ? data.prices[data.prices.length - 2] : null;

  return {
    dayHigh: latestPrice?.high,
    dayLow: latestPrice?.low,
    volume: latestPrice?.volume,
    prevClose: prevPrice?.close,
    ma20: latestPrice?.ma_20,
    cci: latestPrice?.cci,
  };
}

export const StockAnalysis = () => {
  const { symbol: urlSymbol } = useParams<{ symbol?: string }>();
  const { symbol, setSymbol, handleSearch } = useStockSearch(urlSymbol);
  const [interval, setInterval] = useState<Interval>('1d');
  const { data, loading, error } = useStockData(symbol, interval);
  const { stockInfo } = useStockInfo(symbol);

  // Stock lists state
  const { lists, isLoading: listsLoading } = useStockLists();
  const [selectedListId, setSelectedListId] = useState<number | null>(null);
  const selectedList = lists.find((l) => l.id === selectedListId);

  // Mobile watchlist sheet state
  const [isMobileWatchlistOpen, setIsMobileWatchlistOpen] = useState(false);

  /**
   * Handle list selection.
   * When a list is selected, auto-loads the first symbol from that list.
   */
  const handleListSelect = (listId: number) => {
    setSelectedListId(listId);
    const list = lists.find((l) => l.id === listId);
    if (list && list.symbols.length > 0) {
      // Auto-select first symbol from the list
      handleSearch(list.symbols[0]);
    }
  };

  /**
   * Handle symbol selection from watchlist.
   * Switches to the selected symbol and closes mobile sheet if open.
   */
  const handleSymbolSelect = (sym: string) => {
    handleSearch(sym);
    setIsMobileWatchlistOpen(false);
  };

  return (
    <div className="flex flex-1">
      {/* Watchlist Panel - hidden below 1024px */}
      <aside className="hidden lg:block w-[260px] flex-shrink-0 border-r border-subtle">
        <WatchlistPanel
          lists={lists}
          selectedListId={selectedListId}
          onListChange={handleListSelect}
          symbols={selectedList?.symbols ?? []}
          selectedSymbol={symbol}
          onSymbolSelect={handleSymbolSelect}
          isLoading={listsLoading}
        />
      </aside>

      {/* Main content */}
      <main className="flex-1 p-6 flex flex-col gap-5">
        {/* Top bar: search + interval toggle */}
        <div className="flex items-center gap-4">
          {/* Mobile watchlist trigger - visible only below lg */}
          <Button
            variant="outline"
            size="icon"
            className="lg:hidden flex-shrink-0"
            onClick={() => setIsMobileWatchlistOpen(true)}
            aria-label="Open watchlist"
            data-testid="mobile-watchlist-trigger"
          >
            <List className="h-5 w-5" />
          </Button>
          <SearchBar
            value={symbol}
            onChange={setSymbol}
            onSearch={handleSearch}
          />
          <IntervalSelector interval={interval} onIntervalChange={setInterval} />
        </div>

        {/* Mobile watchlist sheet */}
        <Sheet open={isMobileWatchlistOpen} onOpenChange={setIsMobileWatchlistOpen}>
          <SheetContent side="left" className="w-[280px] p-0 bg-bg-secondary">
            <SheetHeader className="px-4 py-3 border-b border-subtle">
              <SheetTitle className="text-sm font-semibold text-text-secondary">
                Watchlist
              </SheetTitle>
              <SheetDescription className="sr-only">
                Select a stock list and symbol to analyze
              </SheetDescription>
            </SheetHeader>
            <div className="h-[calc(100vh-60px)]">
              <WatchlistPanel
                lists={lists}
                selectedListId={selectedListId}
                onListChange={handleListSelect}
                symbols={selectedList?.symbols ?? []}
                selectedSymbol={symbol}
                onSymbolSelect={handleSymbolSelect}
                isLoading={listsLoading}
              />
            </div>
          </SheetContent>
        </Sheet>

        {/* Loading state */}
        {loading && (
          <StockHero
            isLoading
            symbol=""
            price={0}
            change={0}
            changePercent={0}
            direction="neutral"
            stats={{}}
          />
        )}

        {/* Error state */}
        {error && (
          <div className="text-center py-8">
            <p className="text-destructive">Error: {error}</p>
          </div>
        )}

        {/* Stock data display */}
        {data && !loading && !error && (
          <>
            <StockHero
              symbol={data.symbol}
              price={data.current_price}
              change={data.price_change}
              changePercent={data.price_change_percent}
              direction={data.price_change >= 0 ? 'bullish' : 'bearish'}
              stats={getStatsFromData(data)}
              sectorEtf={stockInfo?.sector_etf}
            />

            {/* Chart section */}
            <div className="flex-1 flex flex-col gap-2.5">
              <CandlestickChart
                data={data.prices}
                symbol={data.symbol}
                height={500}
              />
            </div>
          </>
        )}
      </main>
    </div>
  );
};
