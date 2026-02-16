/**
 * Arena Configuration Panel
 *
 * Displays simulation parameters including date range, agent type,
 * trailing stop, min score, and expandable symbols list.
 */
import { type ReactNode, useState } from 'react';
import {
  Calendar,
  ChevronDown,
  ChevronUp,
  Settings2,
  Target,
  TrendingDown,
} from 'lucide-react';
import { Button } from '../ui/button';
import { Card, CardContent } from '../ui/card';
import { formatTrailingStop } from '../../utils/arena';
import type { Simulation } from '../../types/arena';

/** Default number of symbols shown before expansion */
const SYMBOLS_PREVIEW_COUNT = 8;

interface ArenaConfigPanelProps {
  /** Simulation configuration to display */
  simulation: Simulation;
}

/**
 * Configuration item component
 * Displays a labeled value with icon in a consistent grid cell format
 */
interface ConfigItemProps {
  icon: ReactNode;
  label: string;
  value: ReactNode;
}

const ConfigItem = ({ icon, label, value }: ConfigItemProps) => (
  <div className="space-y-1">
    <div className="flex items-center gap-1.5 text-text-muted">
      {icon}
      <span className="text-[11px] font-medium uppercase tracking-wider">
        {label}
      </span>
    </div>
    <p className="font-mono text-sm">{value}</p>
  </div>
);

/**
 * Arena Configuration Panel Component
 *
 * Shows simulation parameters in a grid layout:
 * - Date range (start → end)
 * - Agent type
 * - Trailing stop percentage
 * - Minimum buy score
 * - Expandable symbols list
 */
export const ArenaConfigPanel = ({ simulation }: ArenaConfigPanelProps) => {
  const [symbolsExpanded, setSymbolsExpanded] = useState(false);

  const hasMoreSymbols = simulation.symbols.length > SYMBOLS_PREVIEW_COUNT;
  const displayedSymbols = symbolsExpanded
    ? simulation.symbols
    : simulation.symbols.slice(0, SYMBOLS_PREVIEW_COUNT);

  return (
    <Card className="bg-bg-secondary border-border-subtle">
      <CardContent className="pt-5 pb-4">
        {/* Configuration Grid */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-4">
          <ConfigItem
            icon={<Calendar className="h-3.5 w-3.5" />}
            label="Date Range"
            value={
              <span className="text-text-primary">
                {simulation.start_date} → {simulation.end_date}
              </span>
            }
          />

          <ConfigItem
            icon={<Settings2 className="h-3.5 w-3.5" />}
            label="Agent"
            value={
              <div className="flex flex-col gap-0.5">
                <span className="text-text-primary">{simulation.agent_type}</span>
                {simulation.scoring_algorithm && (
                  <span className="text-[10px] uppercase text-text-muted font-mono">
                    {simulation.scoring_algorithm}
                  </span>
                )}
              </div>
            }
          />

          <ConfigItem
            icon={<TrendingDown className="h-3.5 w-3.5" />}
            label="Trailing Stop"
            value={
              <span
                className={
                  simulation.trailing_stop_pct != null
                    ? 'text-accent-bearish'
                    : 'text-text-muted'
                }
              >
                {formatTrailingStop(simulation.trailing_stop_pct)}
              </span>
            }
          />

          <ConfigItem
            icon={<Target className="h-3.5 w-3.5" />}
            label="Min Score"
            value={
              simulation.min_buy_score != null ? (
                <span className="text-accent-primary">{simulation.min_buy_score}</span>
              ) : (
                <span className="text-text-muted">—</span>
              )
            }
          />
        </div>

        {/* Symbols Section */}
        <div className="pt-3 border-t border-border-subtle">
          <div className="flex items-center justify-between mb-2">
            <span className="text-[11px] font-medium uppercase tracking-wider text-text-muted">
              Symbols ({simulation.symbols.length})
            </span>
            {hasMoreSymbols && (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setSymbolsExpanded(!symbolsExpanded)}
                className="h-6 px-2 text-xs text-muted-foreground hover:text-foreground"
              >
                {symbolsExpanded ? (
                  <>
                    <ChevronUp className="h-3 w-3 mr-1" />
                    Show less
                  </>
                ) : (
                  <>
                    <ChevronDown className="h-3 w-3 mr-1" />
                    Show all {simulation.symbols.length}
                  </>
                )}
              </Button>
            )}
          </div>
          <div className="flex flex-wrap gap-1.5">
            {displayedSymbols.map((symbol) => (
              <span
                key={symbol}
                className="px-2 py-0.5 text-xs font-mono bg-bg-tertiary text-text-secondary rounded border border-border-subtle"
              >
                {symbol}
              </span>
            ))}
            {!symbolsExpanded && hasMoreSymbols && (
              <span className="px-2 py-0.5 text-xs font-mono text-text-muted">
                +{simulation.symbols.length - SYMBOLS_PREVIEW_COUNT} more
              </span>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  );
};
