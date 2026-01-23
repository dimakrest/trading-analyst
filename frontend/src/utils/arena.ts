/**
 * Arena Utility Functions
 *
 * Shared utilities for the Trading Agent Arena feature.
 */
import type { Position, SimulationStatus, Snapshot } from '../types/arena';

/**
 * Format trailing stop percentage for display
 *
 * @param value - Trailing stop percentage as string (from API) or null
 * @returns Formatted string like "5.0%" or "—" for null values
 */
export const formatTrailingStop = (value: string | null): string =>
  value ? `${parseFloat(value).toFixed(1)}%` : '—';

/**
 * Get badge styling classes for simulation status
 *
 * @param status - The simulation status
 * @returns Tailwind CSS classes for the status badge
 *
 * @example
 * getStatusBadgeClass('completed') // 'bg-accent-bullish/15 text-accent-bullish border border-accent-bullish/30'
 * getStatusBadgeClass('running') // 'bg-accent-primary/15 text-accent-primary border border-accent-primary/30'
 */
export const getStatusBadgeClass = (status: SimulationStatus): string => {
  const variants: Record<SimulationStatus, string> = {
    pending: 'bg-amber-500/15 text-amber-500 border border-amber-500/30',
    running: 'bg-accent-primary/15 text-accent-primary border border-accent-primary/30',
    paused: 'bg-orange-500/15 text-orange-500 border border-orange-500/30',
    completed: 'bg-accent-bullish/15 text-accent-bullish border border-accent-bullish/30',
    cancelled: 'bg-bg-tertiary text-text-muted border border-subtle',
    failed: 'bg-accent-bearish/15 text-accent-bearish border border-accent-bearish/30',
  };
  return variants[status] || variants.pending;
};

/**
 * Filter positions to show those that were open at End-of-Day on the snapshot date.
 *
 * A position was open at EOD on a given date if:
 * 1. It had been entered on or before that date (entry_date <= snapshot_date)
 * 2. It had NOT been exited on or before that date (exit_date is null OR exit_date > snapshot_date)
 *
 * IMPORTANT: Use strict > for exit_date comparison because:
 * - Snapshots represent End-of-Day state (after all trades are settled)
 * - If a position was sold on Day 5, the Day 5 snapshot shows cash AFTER the sale
 * - Including the sold position would cause double-counting (cash + position)
 *
 * @param positions - All positions from the simulation
 * @param snapshot - The snapshot representing the selected day (or null for initial state)
 * @returns Positions that were open at EOD on the snapshot date
 */
export const getPositionsForSnapshot = (
  positions: Position[],
  snapshot: Snapshot | null
): Position[] => {
  // If no snapshot, return empty array (no positions exist yet)
  if (!snapshot) {
    return [];
  }

  const snapshotDate = snapshot.snapshot_date;

  return positions.filter((position) => {
    // Position must have been entered (entry_date is required for filtering)
    // Pending positions (entry_date is null) are not yet open
    if (!position.entry_date) {
      return false;
    }

    // Position must have been entered on or before snapshot date
    if (position.entry_date > snapshotDate) {
      return false;
    }

    // Position must not have been closed on or before snapshot date
    // If exit_date is null, position is still open (include it)
    // If exit_date exists, it must be > snapshot_date (strict greater than)
    // Use > because snapshot is EOD state - position sold today is no longer held at EOD
    if (position.exit_date && position.exit_date <= snapshotDate) {
      return false;
    }

    return true;
  });
};
