/**
 * Arena Decision Log Component
 *
 * Displays agent decisions for each symbol, organized by snapshot/day.
 * Allows selecting different days to view historical decisions.
 */
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
import type { Snapshot } from '../../types/arena';

interface ArenaDecisionLogProps {
  /** Currently selected snapshot (or null if none) */
  snapshot: Snapshot | null;
  /** All available snapshots for day selection */
  snapshots: Snapshot[];
  /** Callback when user selects a different snapshot */
  onSelectSnapshot: (snapshot: Snapshot) => void;
}

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
                  <Badge className={getActionBadgeClass(decision.action)}>
                    {decision.action}
                  </Badge>
                </div>
                {decision.score !== null && (
                  <p className="text-sm">
                    Score: <span className="font-mono font-medium">{decision.score}/100</span>
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
