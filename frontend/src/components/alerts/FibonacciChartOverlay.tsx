import type { ChartPriceLine, ChartMarker } from '../../types/chart';
import type { FibonacciComputedState } from '../../types/alert';

/**
 * Convert Fibonacci computed state to ChartPriceLine[] for CandlestickChart overlay.
 *
 * Triggered levels render as solid red lines; pending levels as dashed gray.
 *
 * @param state - Computed Fibonacci state from the alert
 * @param configLevels - The alert's configured level percentages (e.g. [38.2, 50, 61.8])
 */
export function getFibPriceLines(
  state: FibonacciComputedState,
  configLevels: number[]
): ChartPriceLine[] {
  const lines: ChartPriceLine[] = [];

  for (const [levelKey, levelState] of Object.entries(state.fib_levels)) {
    const pct = parseFloat(levelKey);
    if (!configLevels.includes(pct)) continue;

    const isTriggered = levelState.status === 'triggered';
    lines.push({
      price: levelState.price,
      color: isTriggered ? '#ef4444' : '#6b7280',
      lineWidth: isTriggered ? 2 : 1,
      lineStyle: isTriggered ? 'solid' : 'dashed',
      label: `${pct}% — $${levelState.price.toFixed(2)}`,
      labelVisible: true,
    });
  }

  return lines;
}

/**
 * Convert Fibonacci computed state to ChartMarker[] for swing high/low arrows.
 *
 * Swing high: red arrowDown above bar
 * Swing low: green arrowUp below bar
 *
 * @param state - Computed Fibonacci state from the alert
 */
export function getFibMarkers(state: FibonacciComputedState): ChartMarker[] {
  const markers: ChartMarker[] = [];

  if (state.swing_high_date) {
    markers.push({
      date: state.swing_high_date,
      position: 'aboveBar',
      shape: 'arrowDown',
      color: '#ef4444',
      text: `SH $${state.swing_high.toFixed(2)}`,
    });
  }

  if (state.swing_low_date) {
    markers.push({
      date: state.swing_low_date,
      position: 'belowBar',
      shape: 'arrowUp',
      color: '#22c55e',
      text: `SL $${state.swing_low.toFixed(2)}`,
    });
  }

  return markers;
}
