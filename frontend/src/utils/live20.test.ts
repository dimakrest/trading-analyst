import { describe, it, expect } from 'vitest';
import { getStrategyDisplayLabel, hasCustomAtrMultiplier } from './live20';

describe('getStrategyDisplayLabel', () => {
  it('returns null for null config (legacy runs)', () => {
    expect(getStrategyDisplayLabel(null)).toBeNull();
  });

  it('returns null for empty config object', () => {
    expect(getStrategyDisplayLabel({})).toBeNull();
  });

  it('returns null for current_price strategy (default)', () => {
    expect(getStrategyDisplayLabel({ entry_strategy: 'current_price' })).toBeNull();
  });

  it('returns "Breakout +2%" for breakout_confirmation with default percentage', () => {
    expect(getStrategyDisplayLabel({ entry_strategy: 'breakout_confirmation' })).toBe('Breakout +2%');
  });

  it('returns "Breakout +2%" for breakout_confirmation with explicit 2.0', () => {
    expect(getStrategyDisplayLabel({
      entry_strategy: 'breakout_confirmation',
      breakout_offset_pct: 2.0,
    })).toBe('Breakout +2%');
  });

  it('returns "Breakout +1.5%" for breakout_confirmation with custom percentage', () => {
    expect(getStrategyDisplayLabel({
      entry_strategy: 'breakout_confirmation',
      breakout_offset_pct: 1.5,
    })).toBe('Breakout +1.5%');
  });

  it('returns "Breakout +3%" for breakout_confirmation with 3% offset', () => {
    expect(getStrategyDisplayLabel({
      entry_strategy: 'breakout_confirmation',
      breakout_offset_pct: 3.0,
    })).toBe('Breakout +3%');
  });
});

describe('hasCustomAtrMultiplier', () => {
  it('returns false for null config', () => {
    expect(hasCustomAtrMultiplier(null)).toBe(false);
  });

  it('returns false for empty config', () => {
    expect(hasCustomAtrMultiplier({})).toBe(false);
  });

  it('returns false for default 0.5 multiplier', () => {
    expect(hasCustomAtrMultiplier({ atr_multiplier: 0.5 })).toBe(false);
  });

  it('returns true for custom multiplier 1.0', () => {
    expect(hasCustomAtrMultiplier({ atr_multiplier: 1.0 })).toBe(true);
  });

  it('returns true for custom multiplier 0.75', () => {
    expect(hasCustomAtrMultiplier({ atr_multiplier: 0.75 })).toBe(true);
  });
});
