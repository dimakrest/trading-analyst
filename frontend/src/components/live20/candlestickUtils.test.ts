import { describe, it, expect } from 'vitest';
import { getCandlePatternLabel } from './candlestickUtils';

describe('candlestickUtils', () => {
  describe('getCandlePatternLabel', () => {
    it('returns correct label for doji', () => {
      expect(getCandlePatternLabel('doji')).toBe('Doji');
    });

    it('returns correct label for hammer', () => {
      expect(getCandlePatternLabel('hammer')).toBe('Hammer');
    });

    it('returns correct label for hanging_man', () => {
      expect(getCandlePatternLabel('hanging_man')).toBe('Hanging Man');
    });

    it('returns correct label for shooting_star', () => {
      expect(getCandlePatternLabel('shooting_star')).toBe('Shooting Star');
    });

    it('returns correct label for inverted_hammer', () => {
      expect(getCandlePatternLabel('inverted_hammer')).toBe('Inverted Hammer');
    });

    it('returns correct label for engulfing_bullish', () => {
      expect(getCandlePatternLabel('engulfing_bullish')).toBe('Bullish Engulfing');
    });

    it('returns correct label for engulfing_bearish', () => {
      expect(getCandlePatternLabel('engulfing_bearish')).toBe('Bearish Engulfing');
    });

    it('returns correct label for marubozu_bullish', () => {
      expect(getCandlePatternLabel('marubozu_bullish')).toBe('Bullish Marubozu');
    });

    it('returns correct label for marubozu_bearish', () => {
      expect(getCandlePatternLabel('marubozu_bearish')).toBe('Bearish Marubozu');
    });

    it('returns correct label for spinning_top', () => {
      expect(getCandlePatternLabel('spinning_top')).toBe('Spinning Top');
    });

    it('returns correct label for standard', () => {
      expect(getCandlePatternLabel('standard')).toBe('Standard');
    });

    it('handles case-insensitive input', () => {
      expect(getCandlePatternLabel('HAMMER')).toBe('Hammer');
      expect(getCandlePatternLabel('Doji')).toBe('Doji');
      expect(getCandlePatternLabel('ShOoTiNg_StAr')).toBe('Shooting Star');
    });

    it('returns Unknown for null', () => {
      expect(getCandlePatternLabel(null)).toBe('Unknown');
    });

    it('returns original pattern for unknown patterns', () => {
      expect(getCandlePatternLabel('unknown_pattern')).toBe('unknown_pattern');
      expect(getCandlePatternLabel('custom')).toBe('custom');
    });
  });
});
