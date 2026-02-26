import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/react';
import { CandlestickIcon } from './CandlestickIcon';
import { getCandlePatternLabel } from './candlestickUtils';

describe('CandlestickIcon', () => {
  describe('color based on bullish prop', () => {
    it('renders green when bullish is true', () => {
      const { container } = render(<CandlestickIcon pattern="hammer" bullish={true} />);
      const rect = container.querySelector('rect');
      expect(rect).toHaveAttribute('fill', '#22c55e');
    });

    it('renders red when bullish is false', () => {
      const { container } = render(<CandlestickIcon pattern="hammer" bullish={false} />);
      const rect = container.querySelector('rect');
      expect(rect).toHaveAttribute('fill', '#ef4444');
    });

    it('renders gray when bullish is null', () => {
      const { container } = render(<CandlestickIcon pattern="hammer" bullish={null} />);
      const rect = container.querySelector('rect');
      expect(rect).toHaveAttribute('fill', '#6b7280');
    });

    it('renders gray when bullish is undefined', () => {
      const { container } = render(<CandlestickIcon pattern="hammer" />);
      const rect = container.querySelector('rect');
      expect(rect).toHaveAttribute('fill', '#6b7280');
    });
  });

  describe('pattern shapes', () => {
    it('renders hammer pattern shape', () => {
      const { container } = render(<CandlestickIcon pattern="hammer" bullish={true} />);
      const svg = container.querySelector('svg');
      expect(svg).toBeInTheDocument();
      // Hammer has a long lower wick
      const lines = container.querySelectorAll('line');
      expect(lines.length).toBe(2); // upper and lower wick
    });

    it('renders doji pattern shape', () => {
      const { container } = render(<CandlestickIcon pattern="doji" bullish={true} />);
      const rect = container.querySelector('rect');
      expect(rect).toBeInTheDocument();
      // Doji has very small body height
    });

    it('renders shooting_star pattern shape', () => {
      const { container } = render(<CandlestickIcon pattern="shooting_star" bullish={false} />);
      const svg = container.querySelector('svg');
      expect(svg).toBeInTheDocument();
    });

    it('renders engulfing_bullish pattern shape', () => {
      const { container } = render(<CandlestickIcon pattern="engulfing_bullish" bullish={true} />);
      const rect = container.querySelector('rect');
      expect(rect).toBeInTheDocument();
    });

    it('renders engulfing_bearish pattern shape', () => {
      const { container } = render(<CandlestickIcon pattern="engulfing_bearish" bullish={false} />);
      const rect = container.querySelector('rect');
      expect(rect).toBeInTheDocument();
    });

    it('renders marubozu_bullish pattern (no wicks)', () => {
      const { container } = render(<CandlestickIcon pattern="marubozu_bullish" bullish={true} />);
      const lines = container.querySelectorAll('line');
      expect(lines.length).toBe(0); // No wicks
    });

    it('renders marubozu_bearish pattern (no wicks)', () => {
      const { container } = render(<CandlestickIcon pattern="marubozu_bearish" bullish={false} />);
      const lines = container.querySelectorAll('line');
      expect(lines.length).toBe(0); // No wicks
    });

    it('renders spinning_top pattern shape', () => {
      const { container } = render(<CandlestickIcon pattern="spinning_top" bullish={null} />);
      const svg = container.querySelector('svg');
      expect(svg).toBeInTheDocument();
    });

    it('renders standard pattern for unknown patterns', () => {
      const { container } = render(<CandlestickIcon pattern="unknown_pattern" bullish={true} />);
      const svg = container.querySelector('svg');
      expect(svg).toBeInTheDocument();
    });

    it('renders standard pattern when pattern is null', () => {
      const { container } = render(<CandlestickIcon pattern={null} bullish={true} />);
      const svg = container.querySelector('svg');
      expect(svg).toBeInTheDocument();
    });
  });

  describe('size prop', () => {
    it('uses default size of 24', () => {
      const { container } = render(<CandlestickIcon pattern="hammer" />);
      const svg = container.querySelector('svg');
      expect(svg).toHaveAttribute('width', '24');
      expect(svg).toHaveAttribute('height', '24');
    });

    it('uses custom size when provided', () => {
      const { container } = render(<CandlestickIcon pattern="hammer" size={32} />);
      const svg = container.querySelector('svg');
      expect(svg).toHaveAttribute('width', '32');
      expect(svg).toHaveAttribute('height', '32');
    });
  });

  describe('className prop', () => {
    it('applies custom className', () => {
      const { container } = render(<CandlestickIcon pattern="hammer" className="custom-class" />);
      const wrapper = container.querySelector('span');
      expect(wrapper).toHaveClass('custom-class');
    });
  });
});

describe('getCandlePatternLabel', () => {
  it('returns correct labels for known patterns', () => {
    expect(getCandlePatternLabel('doji')).toBe('Doji');
    expect(getCandlePatternLabel('hammer')).toBe('Hammer');
    expect(getCandlePatternLabel('shooting_star')).toBe('Shooting Star');
    expect(getCandlePatternLabel('engulfing_bullish')).toBe('Bullish Engulfing');
    expect(getCandlePatternLabel('engulfing_bearish')).toBe('Bearish Engulfing');
    expect(getCandlePatternLabel('marubozu_bullish')).toBe('Bullish Marubozu');
    expect(getCandlePatternLabel('marubozu_bearish')).toBe('Bearish Marubozu');
    expect(getCandlePatternLabel('spinning_top')).toBe('Spinning Top');
    expect(getCandlePatternLabel('standard')).toBe('Standard');
  });

  it('handles case-insensitive pattern names', () => {
    expect(getCandlePatternLabel('HAMMER')).toBe('Hammer');
    expect(getCandlePatternLabel('Doji')).toBe('Doji');
    expect(getCandlePatternLabel('SHOOTING_STAR')).toBe('Shooting Star');
  });

  it('returns "Unknown" for null pattern', () => {
    expect(getCandlePatternLabel(null)).toBe('Unknown');
  });

  it('returns pattern name for unknown patterns', () => {
    expect(getCandlePatternLabel('some_unknown_pattern')).toBe('some_unknown_pattern');
  });
});
