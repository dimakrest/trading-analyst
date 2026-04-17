/**
 * Arena Decision Log Component
 *
 * Displays agent decisions for each symbol, organized by snapshot/day.
 * Allows selecting different days to view historical decisions.
 */
import { AlertTriangle, Info, ShieldAlert, ShieldOff } from 'lucide-react';
import { Badge } from '../ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '../ui/card';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../ui/select';
import { cn } from '../../lib/utils';
import type { CircuitBreakerState, Snapshot } from '../../types/arena';

interface ArenaDecisionLogProps {
  /** Currently selected snapshot (or null if none) */
  snapshot: Snapshot | null;
  /** All available snapshots for day selection */
  snapshots: Snapshot[];
  /** Callback when user selects a different snapshot */
  onSelectSnapshot: (snapshot: Snapshot) => void;
  /** Configured circuit breaker market symbol (for data_unavailable banner) */
  circuitBreakerSymbol?: string;
}

interface MarketConditionsBannerProps {
  circuitBreakerState: CircuitBreakerState;
  circuitBreakerAtrPct?: string | null;
  regimeState?: string | null;
  circuitBreakerSymbol?: string;
}

/** Market Conditions banner rendered before symbol rows.
 * Hidden when circuit_breaker_state is 'disabled'. */
const MarketConditionsBanner = ({
  circuitBreakerState,
  circuitBreakerAtrPct,
  regimeState,
  circuitBreakerSymbol,
}: MarketConditionsBannerProps) => {
  if (circuitBreakerState === 'disabled' && !regimeState) return null;

  const atrDisplay = circuitBreakerAtrPct
    ? `${parseFloat(circuitBreakerAtrPct).toFixed(2)}%`
    : null;

  const renderBannerContent = () => {
    switch (circuitBreakerState) {
      case 'clear':
        // Passive indicator — no role/live-region; firing role="status" on every
        // day-change during fast replay is spammy for screen readers.
        return (
          <div
            className="flex items-start gap-2 rounded-md border border-blue-500/30 bg-blue-500/10 px-3 py-2 text-xs text-blue-700"
            data-testid="cb-banner-clear"
          >
            <Info className="mt-0.5 h-3.5 w-3.5 flex-shrink-0" aria-hidden="true" />
            <span>
              Market ATR: {atrDisplay ?? '—'} <span className="font-medium">(clear)</span>
            </span>
          </div>
        );
      case 'triggered':
        return (
          <div
            className="flex items-start gap-2 rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-xs text-destructive"
            role="alert"
            data-testid="cb-banner-triggered"
          >
            <ShieldAlert className="mt-0.5 h-3.5 w-3.5 flex-shrink-0" aria-hidden="true" />
            <span>
              <span className="font-medium">Circuit breaker triggered:</span> Market ATR {atrDisplay ?? '—'} &ge; threshold. All entries blocked.
            </span>
          </div>
        );
      case 'data_unavailable':
        return (
          <div
            className="flex items-start gap-2 rounded-md border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-xs text-amber-700"
            role="alert"
            data-testid="cb-banner-data-unavailable"
          >
            <ShieldOff className="mt-0.5 h-3.5 w-3.5 flex-shrink-0" aria-hidden="true" />
            <span>
              <span className="font-medium">Circuit breaker bypassed:</span> market data unavailable
              for {circuitBreakerSymbol ?? 'market symbol'} on this date. Entries proceeded without the safety gate.
            </span>
          </div>
        );
      case 'disabled':
        // 'disabled' reaches here only when regimeState is set (the early-return guard
        // at the top of the component handles the fully-hidden case).
        return null;
      default: {
        // Exhaustiveness check: TypeScript will error here if a new
        // CircuitBreakerState variant is added without a matching case.
        const _exhaustive: never = circuitBreakerState;
        return _exhaustive;
      }
    }
  };

  return (
    <div className="space-y-1.5 mb-3" data-testid="market-conditions-banner">
      {renderBannerContent()}
      {regimeState && (
        <div className="flex items-center gap-1.5 text-xs text-muted-foreground px-1">
          <AlertTriangle className="h-3 w-3 flex-shrink-0" aria-hidden="true" />
          <span>Market Regime: <span className="font-medium capitalize">{regimeState}</span></span>
        </div>
      )}
    </div>
  );
};

/** Get badge styling for decision action */
const getActionBadgeClass = (action: string): string => {
  switch (action) {
    case 'BUY':
      return 'bg-accent-bullish/15 text-accent-bullish border border-accent-bullish/30';
    case 'HOLD':
      return 'bg-accent-primary/15 text-accent-primary border border-accent-primary/30';
    case 'NO_SIGNAL':
      return 'bg-bg-tertiary text-text-muted border border-subtle';
    case 'NO_DATA':
      return 'bg-amber-500/15 text-amber-500 border border-amber-500/30';
    default:
      return 'bg-bg-tertiary text-text-muted border border-subtle';
  }
};

/**
 * Arena Decision Log Component
 *
 * Features:
 * - Day selector dropdown to navigate between snapshots
 * - Decision cards for each symbol showing action, score, reasoning
 * - Color-coded action badges (BUY=green, HOLD=blue, etc.)
 * - Scrollable decision list
 */
export const ArenaDecisionLog = ({
  snapshot,
  snapshots,
  onSelectSnapshot,
  circuitBreakerSymbol,
}: ArenaDecisionLogProps) => {
  // Empty state - no snapshots yet
  if (!snapshot) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Decision Log</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground text-center py-4">
            No decisions yet
          </p>
        </CardContent>
      </Card>
    );
  }

  const decisions = Object.entries(snapshot.decisions);
  const cbState = snapshot.circuit_breaker_state ?? 'disabled';

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle>Decision Log</CardTitle>
        <Select
          value={String(snapshot.day_number)}
          onValueChange={(value) => {
            const day = parseInt(value, 10);
            const selected = snapshots.find((s) => s.day_number === day);
            if (selected) {
              onSelectSnapshot(selected);
            }
          }}
        >
          <SelectTrigger className="w-[180px]">
            <SelectValue placeholder="Select day" />
          </SelectTrigger>
          <SelectContent className="max-h-[300px]" position="popper" side="bottom">
            {[...snapshots]
              .sort((a, b) => a.day_number - b.day_number)
              .map((s) => (
                <SelectItem key={s.id} value={String(s.day_number)}>
                  Day <span className="font-mono">{s.day_number + 1}</span> - <span className="font-mono">{s.snapshot_date}</span>
                </SelectItem>
              ))}
          </SelectContent>
        </Select>
      </CardHeader>
      <CardContent>
        <div className="max-h-[300px] overflow-y-auto space-y-3">
          {/* Market Conditions banner — renders BEFORE symbol rows, keyed on state not decisions */}
          <MarketConditionsBanner
            circuitBreakerState={cbState}
            circuitBreakerAtrPct={snapshot.circuit_breaker_atr_pct}
            regimeState={snapshot.regime_state}
            circuitBreakerSymbol={circuitBreakerSymbol}
          />
          {decisions.length === 0 ? (
            <p className="text-sm text-muted-foreground text-center py-4">
              No decisions for this day
            </p>
          ) : (
            decisions.map(([symbol, decision]) => (
              <div
                key={symbol}
                className={cn(
                  'border rounded-lg p-3',
                  decision.action === 'BUY' && 'border-accent-bullish/30'
                )}
              >
                <div className="flex items-center justify-between mb-1">
                  <Badge variant="outline">{symbol}</Badge>
                  <div className="flex items-center gap-1.5">
                    {decision.circuit_breaker_filtered && (
                      <Badge className="bg-destructive/15 text-destructive border border-destructive/30 text-[10px]">
                        CIRCUIT BREAKER
                      </Badge>
                    )}
                    {decision.ibs_filtered && (
                      <span
                        title={
                          decision.ma50_filtered === undefined
                            ? 'IBS filter caught this symbol before MA50 was evaluated. MA50 status unknown.'
                            : undefined
                        }
                      >
                        <Badge className="bg-amber-500/15 text-amber-600 border border-amber-500/30 text-[10px]">
                          IBS FILTERED
                        </Badge>
                      </span>
                    )}
                    {decision.ma50_filtered && (
                      <Badge className="bg-purple-500/15 text-purple-600 border border-purple-500/30 text-[10px]">
                        MA50 FILTERED
                      </Badge>
                    )}
                    <Badge className={getActionBadgeClass(decision.action)}>
                      {decision.action}
                    </Badge>
                  </div>
                </div>
                {decision.score !== null && (
                  <p className="text-sm">
                    Score: <span className="font-mono font-medium">{decision.score}/100</span>
                  </p>
                )}
                {decision.ibs_value !== undefined && (
                  <p className="text-xs text-muted-foreground mt-1">
                    IBS: <span className="font-mono">{decision.ibs_value}</span>
                  </p>
                )}
                {decision.reasoning && (
                  <p className="text-xs text-muted-foreground mt-1 break-words">
                    {decision.reasoning}
                  </p>
                )}
              </div>
            ))
          )}
        </div>
      </CardContent>
    </Card>
  );
};
