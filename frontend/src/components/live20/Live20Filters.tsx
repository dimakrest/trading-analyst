import { Input } from '../ui/input';
import { Slider } from '../ui/slider';
import { Search } from 'lucide-react';
import type { Live20Direction, Live20Counts } from '../../types/live20';
import { cn } from '../../lib/utils';
import { ATR_SLIDER_MAX } from '../../hooks/useLive20Filters';

interface Live20FiltersProps {
  /** Current direction filter selection */
  directionFilter: Live20Direction | null;
  /** Callback when direction filter changes */
  onDirectionChange: (direction: Live20Direction | null) => void;
  /** Counts of results by direction */
  counts: Live20Counts;
  /** Current search query */
  searchQuery: string;
  /** Callback when search query changes */
  onSearchChange: (query: string) => void;
  /** Current minimum score filter */
  minScore: number;
  /** Callback when minimum score changes */
  onMinScoreChange: (score: number) => void;
  /** Current minimum rvol filter */
  minRvol: number;
  /** Callback when minimum rvol changes */
  onMinRvolChange: (rvol: number) => void;
  /** Current ATR% range filter [min, max]. [0,0] means no filtering. */
  atrRange: [number, number];
  /** Callback when ATR% range changes */
  onAtrRangeChange: (range: [number, number]) => void;
  /** Whether the ATR filter is actively restricting results */
  isAtrFilterActive: boolean;
}

/**
 * Filter button component for direction selection
 */
function FilterButton({
  active,
  variant,
  count,
  label,
  onClick,
}: {
  active: boolean;
  variant: 'all' | 'long' | 'none';
  count: number;
  label: string;
  onClick: () => void;
}) {
  const getActiveStyles = () => {
    switch (variant) {
      case 'long':
        return 'bg-[var(--signal-long-muted)] text-[var(--signal-long)]';
      case 'none':
        return 'bg-[rgba(100,116,139,0.15)] text-text-secondary';
      default:
        return 'bg-bg-elevated text-text-primary';
    }
  };

  return (
    <button
      type="button"
      onClick={onClick}
      className={`
        flex items-center gap-1.5 px-3.5 py-2 rounded-md text-xs font-medium transition-all
        ${active ? getActiveStyles() : 'text-text-muted hover:text-text-primary hover:bg-bg-tertiary'}
      `}
    >
      {label}
      <span className="font-mono text-[11px] font-semibold px-1.5 py-0.5 rounded bg-white/10">
        {count}
      </span>
    </button>
  );
}

/**
 * Filters for Live 20 results
 *
 * Provides direction filter buttons, symbol search, minimum score slider,
 * minimum rvol filter, and ATR% range filter. Direction buttons show counts
 * for each category (All, Long, No Setup).
 *
 * @param props - Component props
 */
export function Live20Filters({
  directionFilter,
  onDirectionChange,
  counts,
  searchQuery,
  onSearchChange,
  minScore,
  onMinScoreChange,
  minRvol,
  onMinRvolChange,
  atrRange,
  onAtrRangeChange,
  isAtrFilterActive,
}: Live20FiltersProps) {
  return (
    <div className="flex flex-wrap items-center gap-4">
      {/* Direction Filter Buttons */}
      <div className="flex gap-1 bg-bg-secondary p-1 rounded-lg border border-default">
        <FilterButton
          active={directionFilter === null}
          variant="all"
          count={counts.total}
          label="All"
          onClick={() => onDirectionChange(null)}
        />
        <FilterButton
          active={directionFilter === 'LONG'}
          variant="long"
          count={counts.long}
          label="Long"
          onClick={() => onDirectionChange('LONG')}
        />
        <FilterButton
          active={directionFilter === 'NO_SETUP'}
          variant="none"
          count={counts.no_setup}
          label="No Setup"
          onClick={() => onDirectionChange('NO_SETUP')}
        />
      </div>

      {/* Symbol Search */}
      <div className="relative flex-1 min-w-[200px] max-w-[240px]">
        <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-text-muted" />
        <Input
          placeholder="Search symbols..."
          value={searchQuery}
          onChange={(e) => onSearchChange(e.target.value)}
          className="pl-10 bg-bg-secondary border-default font-mono text-sm"
        />
      </div>

      {/* Min Score Slider */}
      <div className="flex items-center gap-3">
        <span className="text-xs text-text-muted whitespace-nowrap">Min Score:</span>
        <Slider
          value={[minScore]}
          onValueChange={([value]) => onMinScoreChange(value)}
          min={0}
          max={100}
          step={10}
          className="w-[120px]"
        />
        <span className="font-mono text-xs font-semibold text-text-primary min-w-[28px]">
          {minScore}
        </span>
      </div>

      {/* Min Rvol Slider */}
      <div className="flex items-center gap-3">
        <span className="text-xs text-text-muted whitespace-nowrap">Min Rvol:</span>
        <Slider
          value={[minRvol]}
          onValueChange={([value]) => onMinRvolChange(value)}
          min={0}
          max={3}
          step={0.1}
          className="w-[120px]"
        />
        <Input
          type="number"
          min={0}
          max={3}
          step={0.1}
          value={minRvol === 0 ? '0' : minRvol.toFixed(1)}
          onChange={(e) => {
            const value = parseFloat(e.target.value);
            if (!isNaN(value) && value >= 0 && value <= 3) {
              onMinRvolChange(value);
            }
          }}
          className="w-[60px] h-7 px-2 py-1 bg-bg-secondary border-default font-mono text-xs text-center"
        />
      </div>

      {/* ATR% Range Filter */}
      <div className={cn(
        "flex items-center gap-3 rounded-md px-2 py-1 transition-colors",
        isAtrFilterActive && "bg-accent-primary/10 ring-1 ring-accent-primary/30"
      )}>
        <span className="text-xs text-text-muted whitespace-nowrap">ATR%:</span>
        <span className="font-mono text-xs font-semibold text-text-primary min-w-[28px] text-right">
          {atrRange[0].toFixed(1)}
        </span>
        <Slider
          value={atrRange}
          onValueChange={(value) => onAtrRangeChange(value as [number, number])}
          min={0}
          max={ATR_SLIDER_MAX}
          step={0.5}
          minStepsBetweenThumbs={0}
          className="w-[140px]"
        />
        <span className="font-mono text-xs font-semibold text-text-primary min-w-[28px]">
          {atrRange[1] === 0 ? '∞' : atrRange[1].toFixed(1)}
        </span>
      </div>
    </div>
  );
}
