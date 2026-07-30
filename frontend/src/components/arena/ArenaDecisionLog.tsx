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
import type { CircuitBreakerState, DecisionEntry, Snapshot } from '../../types/arena';

interface ArenaDecisionLogProps {
  /** Currently selected snapshot (or null if none) */
  snapshot: Snapshot | null;
  /** All available snapshots for day selection */
  snapshots: Snapshot[];
  /** Callback when user selects a different snapshot */
  onSelectSnapshot: (snapshot: Snapshot) => void;
  /** Configured circuit breaker market symbol (for data_unavailable banner) */
  circuitBreakerSymbol?: string;
  /** Whether this simulation ran with the MA50 filter enabled. Undefined for
   * legacy/pre-Phase-5 runs where the setting is unknown. Needed to explain
   * filter interactions honestly: an IBS badge may only claim it pre-empted
   * MA50 when MA50 was actually configured for the run. */
  ma50FilterEnabled?: boolean;
}

interface MarketConditionsBannerProps {
  circuitBreakerState: CircuitBreakerState;
  circuitBreakerAtrPct?: string | null;
  regimeState?: string | null;
  circuitBreakerSymbol?: string;
}

/** Why the MA50 filter could not be applied to a symbol that still entered. */
const MA50_SKIP_REASONS: Record<NonNullable<DecisionEntry['ma50_skipped']>, string> = {
  no_data: 'MA50 was not applied: no price history was cached for this symbol.',
  // "Proceeded to portfolio selection", not "entered": ma50_skipped only means the
  // gate was bypassed — the signal can still be dropped by portfolio selection or
  // its pending open cancelled.
  insufficient_history:
    'MA50 was not applied: fewer than 50 bars of history (e.g. a recent listing). The signal proceeded to portfolio selection without the trend filter.',
  stale_bar: 'MA50 was not applied: the most recent cached bar predates this date.',
};

/** Presentation for one circuit breaker state's banner. */
interface BannerSpec {
  /** Tone classes layered onto the shared banner box. */
  className: string;
  Icon: typeof Info;
  role?: 'alert';
  testId: string;
  content: React.ReactNode;
}

/** Market Conditions banner rendered before symbol rows.
 * Hidden only when the circuit breaker is 'disabled' AND no regime state is set —
 * a regime state alone still renders the regime row. */
const MarketConditionsBanner = ({
  circuitBreakerState,
  circuitBreakerAtrPct,
  regimeState,
  circuitBreakerSymbol,
}: MarketConditionsBannerProps) => {
  if (circuitBreakerState === 'disabled' && !regimeState) return null;

  // Rendered at the column's full stored precision, trailing zeros dropped by
  // Number formatting ("2.800000" -> "2.8", "2.799960" -> "2.79996"). Rounding to
  // 2dp here would undo the Numeric(10,6) widening: 2.79996 would print as
  // "Market ATR: 2.80% (clear)" against a 2.8 threshold — an audit line that
  // contradicts itself.
  const atrDisplay = circuitBreakerAtrPct ? `${Number(circuitBreakerAtrPct)}%` : null;

  // One entry per state. Typing this as a total Record is the exhaustiveness check:
  // adding a CircuitBreakerState variant without a banner is a compile error.
  // 'disabled' renders nothing — it only reaches here when regimeState is set, since
  // the early return above handles the fully-hidden case.
  // 'clear' is a passive indicator with no role/live-region; firing role="status" on
  // every day-change during fast replay is spammy for screen readers.
  const banners: Record<CircuitBreakerState, BannerSpec | null> = {
    disabled: null,
    clear: {
      className: 'border-blue-500/30 bg-blue-500/10 text-blue-700',
      Icon: Info,
      testId: 'cb-banner-clear',
      content: (
        <>
          Market ATR: {atrDisplay ?? '—'} <span className="font-medium">(clear)</span>
        </>
      ),
    },
    triggered: {
      className: 'border-destructive/30 bg-destructive/10 text-destructive',
      Icon: ShieldAlert,
      role: 'alert',
      testId: 'cb-banner-triggered',
      content: (
        <>
          <span className="font-medium">Circuit breaker triggered:</span> Market ATR{' '}
          {atrDisplay ?? '—'} &ge; threshold. New buy signals blocked.
        </>
      ),
    },
    data_unavailable: {
      className: 'border-amber-500/40 bg-amber-500/10 text-amber-700',
      Icon: ShieldOff,
      role: 'alert',
      testId: 'cb-banner-data-unavailable',
      content: (
        <>
          <span className="font-medium">Circuit breaker bypassed:</span> market data unavailable
          for {circuitBreakerSymbol ?? 'market symbol'} on this date. Entries proceeded without the safety gate.
        </>
      ),
    },
  };

  const banner = banners[circuitBreakerState];
  const renderBannerContent = () =>
    banner && (
      <div
        className={`flex items-start gap-2 rounded-md border px-3 py-2 text-xs ${banner.className}`}
        role={banner.role}
        data-testid={banner.testId}
      >
        <banner.Icon className="mt-0.5 h-3.5 w-3.5 flex-shrink-0" aria-hidden="true" />
        <span>{banner.content}</span>
      </div>
    );

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
  ma50FilterEnabled,
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
                      // The engine runs IBS first and removes filtered symbols
                      // from buy_signals, so ma50_filtered is never set here.
                      // Only claim that pre-emption when this run actually had
                      // the MA50 filter enabled; when it was off (or unknown,
                      // for legacy runs) there is no interaction to explain.
                      <span
                        title={
                          ma50FilterEnabled
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
                    {decision.ma50_skipped && (
                      // This symbol entered WITHOUT the MA50 gate. Without this badge it
                      // is indistinguishable from one that passed, while the config panel
                      // still reports "MA50 Filter: On".
                      <span title={MA50_SKIP_REASONS[decision.ma50_skipped]}>
                        <Badge className="bg-amber-500/15 text-amber-700 border border-amber-500/30 text-[10px]">
                          MA50 NOT APPLIED
                        </Badge>
                      </span>
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
