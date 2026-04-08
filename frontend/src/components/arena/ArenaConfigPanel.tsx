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
  Layers,
  LayoutGrid,
  Settings2,
  Target,
  TrendingDown,
} from 'lucide-react';
import { Button } from '../ui/button';
import { Card, CardContent } from '../ui/card';
import { formatTrailingStop } from '../../utils/arena';
import { PORTFOLIO_STRATEGIES } from '../../constants/portfolio';
import type { Simulation } from '../../types/arena';

/** Default number of symbols shown before expansion */
const SYMBOLS_PREVIEW_COUNT = 8;

/** Human-readable labels for sizing modes */
const SIZING_MODE_LABEL: Record<string, string> = {
  fixed: 'Fixed $',
  fixed_pct: 'Fixed %',
  risk_based: 'Risk-Based',
};

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
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-4" data-testid="config-grid">
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

        {/* Portfolio Strategy Row — only shown when a non-default strategy is configured */}
        {simulation.portfolio_strategy && simulation.portfolio_strategy !== 'none' && (
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-4 mb-4 pt-3 border-t border-border-subtle">
            <ConfigItem
              icon={<LayoutGrid className="h-3.5 w-3.5" />}
              label="Portfolio Strategy"
              value={
                <span className="text-text-primary">
                  {PORTFOLIO_STRATEGIES.find((s) => s.name === simulation.portfolio_strategy)
                    ?.label ?? simulation.portfolio_strategy}
                </span>
              }
            />
            <ConfigItem
              icon={<LayoutGrid className="h-3.5 w-3.5" />}
              label="Max Per Sector"
              value={
                simulation.max_per_sector != null ? (
                  <span className="text-text-primary">{simulation.max_per_sector}</span>
                ) : (
                  <span className="text-text-muted">—</span>
                )
              }
            />
            <ConfigItem
              icon={<LayoutGrid className="h-3.5 w-3.5" />}
              label="Max Positions"
              value={
                simulation.max_open_positions != null ? (
                  <span className="text-text-primary">{simulation.max_open_positions}</span>
                ) : (
                  <span className="text-text-muted">Unlimited</span>
                )
              }
            />
            {(simulation.portfolio_strategy === 'enriched_score' ||
              simulation.portfolio_strategy === 'enriched_score_high_atr') &&
              simulation.ma_sweet_spot_center != null && (
                <ConfigItem
                  icon={<LayoutGrid className="h-3.5 w-3.5" />}
                  label="Pullback Depth"
                  value={
                    <span className="text-text-primary">{simulation.ma_sweet_spot_center}</span>
                  }
                />
              )}
          </div>
        )}

        {/* Sizing Mode Row — only shown when a non-default (non-fixed) sizing mode is configured */}
        {simulation.sizing_mode && simulation.sizing_mode !== 'fixed' && (
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-4 mb-4 pt-3 border-t border-border-subtle">
            <ConfigItem
              icon={<Layers className="h-3.5 w-3.5" />}
              label="Sizing Mode"
              value={
                <span className="text-text-primary">
                  {SIZING_MODE_LABEL[simulation.sizing_mode] ?? simulation.sizing_mode}
                </span>
              }
            />
            {simulation.sizing_mode === 'fixed_pct' && (
              <ConfigItem
                icon={<Layers className="h-3.5 w-3.5" />}
                label="Position Size"
                value={
                  simulation.position_size_pct != null ? (
                    <span className="text-text-primary">{simulation.position_size_pct}%</span>
                  ) : (
                    <span className="text-text-muted">—</span>
                  )
                }
              />
            )}
            {simulation.sizing_mode === 'risk_based' && (
              <>
                <ConfigItem
                  icon={<Layers className="h-3.5 w-3.5" />}
                  label="Risk Per Trade"
                  value={
                    simulation.risk_per_trade_pct != null ? (
                      <span className="text-text-primary">{simulation.risk_per_trade_pct}%</span>
                    ) : (
                      <span className="text-text-muted">—</span>
                    )
                  }
                />
                <ConfigItem
                  icon={<Layers className="h-3.5 w-3.5" />}
                  label="Win Streak Bonus"
                  value={
                    simulation.win_streak_bonus_pct != null ? (
                      <span className="text-text-primary">{simulation.win_streak_bonus_pct}%</span>
                    ) : (
                      <span className="text-text-muted">—</span>
                    )
                  }
                />
                <ConfigItem
                  icon={<Layers className="h-3.5 w-3.5" />}
                  label="Max Risk Cap"
                  value={
                    simulation.max_risk_pct != null ? (
                      <span className="text-text-primary">{simulation.max_risk_pct}%</span>
                    ) : (
                      <span className="text-text-muted">—</span>
                    )
                  }
                />
              </>
            )}
          </div>
        )}

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
