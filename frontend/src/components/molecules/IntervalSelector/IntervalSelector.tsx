import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group';
import type { Interval } from '../../../types/stock';

interface IntervalSelectorProps {
  interval: Interval;
  onIntervalChange: (interval: Interval) => void;
}

/**
 * IntervalSelector Component
 *
 * Pill-style toggle for selecting chart interval (1D/1H).
 * Uses ToggleGroup component with custom styling to match Trading Terminal design.
 */
export const IntervalSelector = ({
  interval,
  onIntervalChange,
}: IntervalSelectorProps) => {
  return (
    <ToggleGroup
      type="single"
      value={interval}
      onValueChange={(value) => {
        // Only update if a value is selected (prevents deselection)
        if (value) {
          onIntervalChange(value as Interval);
        }
      }}
      className="bg-bg-secondary rounded-lg p-0.5 border border-default"
      aria-label="Chart interval"
    >
      <ToggleGroupItem
        value="1d"
        className="px-4 py-2 font-mono text-xs font-semibold rounded-md text-text-muted hover:text-text-primary hover:bg-bg-tertiary data-[state=on]:bg-accent-primary data-[state=on]:text-white"
        aria-label="Daily candles"
      >
        1D
      </ToggleGroupItem>
      <ToggleGroupItem
        value="1h"
        className="px-4 py-2 font-mono text-xs font-semibold rounded-md text-text-muted hover:text-text-primary hover:bg-bg-tertiary data-[state=on]:bg-accent-primary data-[state=on]:text-white"
        aria-label="Hourly candles"
      >
        1H
      </ToggleGroupItem>
    </ToggleGroup>
  );
};
