import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { Live20Table } from './Live20Table';
import type { Live20Result } from '../../types/live20';

const createMockResult = (overrides: Partial<Live20Result> = {}): Live20Result => ({
  id: 1,
  stock: 'TEST',
  created_at: '2025-12-22T00:00:00Z',
  recommendation: 'LONG',
  confidence_score: 80,
  entry_price: 100.0,
  stop_loss: null,
  entry_strategy: null,
  exit_strategy: null,
  trend_direction: 'bearish',
  trend_aligned: true,
  ma20_distance_pct: -7.0,
  ma20_aligned: true,
  candle_pattern: 'hammer',
  candle_bullish: true,
  candle_aligned: true,
  candle_explanation: null,
  volume_trend: '1.5x',
  volume_aligned: true,
  volume_approach: 'accumulation',
  cci_direction: 'rising',
  cci_value: -86.1,
  cci_zone: 'neutral',
  cci_aligned: true,
  criteria_aligned: 5,
  direction: 'LONG',
  ...overrides,
});

describe('Live20Table', () => {
  describe('CCI column', () => {
    it('displays CCI value', () => {
      const result = createMockResult({ cci_value: -86.1 });
      render(<Live20Table results={[result]} />);

      expect(screen.getByText('-86')).toBeInTheDocument();
    });

    it('displays rising direction with up-indicator color (blue)', () => {
      const result = createMockResult({ cci_direction: 'rising' });
      render(<Live20Table results={[result]} />);

      // The TrendingUp icon should have up-indicator color class
      const cciCell = screen.getByText('-86').closest('div');
      expect(cciCell).toBeInTheDocument();
      // Check for the trending up icon (SVG with specific class)
      const icon = cciCell?.querySelector('svg.text-up-indicator');
      expect(icon).toBeInTheDocument();
    });

    it('displays falling direction with down-indicator color (purple)', () => {
      const result = createMockResult({ cci_direction: 'falling', cci_value: 120 });
      render(<Live20Table results={[result]} />);

      const cciCell = screen.getByText('120').closest('div');
      const icon = cciCell?.querySelector('svg.text-down-indicator');
      expect(icon).toBeInTheDocument();
    });

    it('displays flat direction with muted color', () => {
      const result = createMockResult({ cci_direction: 'flat', cci_value: 0 });
      render(<Live20Table results={[result]} />);

      const cciCell = screen.getByText('0').closest('div');
      const icon = cciCell?.querySelector('svg.text-muted-foreground');
      expect(icon).toBeInTheDocument();
    });

    it('handles null direction gracefully', () => {
      const result = createMockResult({ cci_direction: null, cci_value: 50 });
      render(<Live20Table results={[result]} />);

      // Should show muted color (Minus icon) when direction is null
      const cciCell = screen.getByText('50').closest('div');
      const icon = cciCell?.querySelector('svg.text-muted-foreground');
      expect(icon).toBeInTheDocument();
    });
  });

  describe('Candle column', () => {
    it('displays green candle when bullish (close > open)', () => {
      const result = createMockResult({ candle_bullish: true, candle_pattern: 'hammer' });
      render(<Live20Table results={[result]} />);

      // Find the candlestick SVG - it should have green fill
      const candleCell = screen.getByRole('row', { name: /TEST/ });
      const candleSvg = candleCell.querySelector('svg rect[fill="#22c55e"]');
      expect(candleSvg).toBeInTheDocument();
    });

    it('displays red candle when bearish (close < open)', () => {
      const result = createMockResult({ candle_bullish: false, candle_pattern: 'shooting_star' });
      render(<Live20Table results={[result]} />);

      const candleCell = screen.getByRole('row', { name: /TEST/ });
      const candleSvg = candleCell.querySelector('svg rect[fill="#ef4444"]');
      expect(candleSvg).toBeInTheDocument();
    });

    it('displays gray candle when bullish is null', () => {
      const result = createMockResult({ candle_bullish: null, candle_pattern: 'standard' });
      render(<Live20Table results={[result]} />);

      const candleCell = screen.getByRole('row', { name: /TEST/ });
      const candleSvg = candleCell.querySelector('svg rect[fill="#6b7280"]');
      expect(candleSvg).toBeInTheDocument();
    });
  });

  describe('Volume column', () => {
    it('displays accumulation badge (ACC)', () => {
      const result = createMockResult({ volume_approach: 'accumulation' });
      render(<Live20Table results={[result]} />);

      expect(screen.getByText('ACC')).toBeInTheDocument();
    });

    it('displays exhaustion badge (EXH)', () => {
      const result = createMockResult({ volume_approach: 'exhaustion' });
      render(<Live20Table results={[result]} />);

      expect(screen.getByText('EXH')).toBeInTheDocument();
    });

    it('displays distribution badge (DIST)', () => {
      const result = createMockResult({ volume_approach: 'distribution' });
      render(<Live20Table results={[result]} />);

      expect(screen.getByText('DIST')).toBeInTheDocument();
    });

    it('does not display badge when approach is null', () => {
      const result = createMockResult({ volume_approach: null });
      render(<Live20Table results={[result]} />);

      expect(screen.queryByText('ACC')).not.toBeInTheDocument();
      expect(screen.queryByText('EXH')).not.toBeInTheDocument();
      expect(screen.queryByText('DIST')).not.toBeInTheDocument();
    });
  });

  describe('Direction badge', () => {
    it('displays LONG badge with teal (signal-long) styling', () => {
      const result = createMockResult({ direction: 'LONG' });
      render(<Live20Table results={[result]} />);

      const badge = screen.getByText('LONG');
      // Uses CSS variable for signal color
      expect(badge).toHaveClass('text-[var(--signal-long)]');
      expect(badge).toHaveClass('bg-[var(--signal-long-muted)]');
    });

    it('displays SHORT badge with orange (signal-short) styling', () => {
      const result = createMockResult({ direction: 'SHORT', recommendation: 'SHORT' });
      render(<Live20Table results={[result]} />);

      const badge = screen.getByText('SHORT');
      // Uses CSS variable for signal color
      expect(badge).toHaveClass('text-[var(--signal-short)]');
      expect(badge).toHaveClass('bg-[var(--signal-short-muted)]');
    });

    it('displays NO SETUP badge with neutral styling', () => {
      const result = createMockResult({ direction: 'NO_SETUP', recommendation: 'NO_SETUP' });
      render(<Live20Table results={[result]} />);

      const badge = screen.getByText('NO SETUP');
      expect(badge).toHaveClass('text-text-secondary');
      expect(badge).toHaveClass('bg-[rgba(100,116,139,0.15)]');
    });
  });

  describe('Alignment icons', () => {
    it('displays check icon when aligned', () => {
      const result = createMockResult({ trend_aligned: true });
      render(<Live20Table results={[result]} />);

      // CheckCircle icons should be present for aligned criteria (uses accent-bullish)
      const checkIcons = document.querySelectorAll('svg.text-accent-bullish');
      expect(checkIcons.length).toBeGreaterThan(0);
    });

    it('displays X icon when not aligned', () => {
      const result = createMockResult({
        trend_aligned: false,
        ma20_aligned: false,
        candle_aligned: false,
        volume_aligned: false,
        cci_aligned: false,
      });
      render(<Live20Table results={[result]} />);

      // XCircle icons should be present for non-aligned criteria
      const xIcons = document.querySelectorAll('svg.text-muted-foreground');
      expect(xIcons.length).toBeGreaterThan(0);
    });
  });

  describe('Empty state', () => {
    it('displays no results message when empty', () => {
      render(<Live20Table results={[]} />);

      expect(screen.getByText('No results found')).toBeInTheDocument();
    });
  });

  describe('Score bar', () => {
    it('displays score value', () => {
      const result = createMockResult({ confidence_score: 80 });
      render(<Live20Table results={[result]} />);

      expect(screen.getByText('80')).toBeInTheDocument();
    });

    it('displays gradient bar for high score (>=70)', () => {
      const result = createMockResult({ confidence_score: 80 });
      render(<Live20Table results={[result]} />);

      // Score bar uses gradient - check for the text color
      const scoreText = screen.getByText('80');
      expect(scoreText).toHaveClass('text-accent-bullish');
    });

    it('displays gradient bar for medium score (40-69)', () => {
      const result = createMockResult({ confidence_score: 50 });
      render(<Live20Table results={[result]} />);

      // Score bar uses semantic score-medium color token
      const scoreText = screen.getByText('50');
      expect(scoreText).toHaveClass('text-score-medium');
    });

    it('displays gradient bar for low score (<40)', () => {
      const result = createMockResult({ confidence_score: 20 });
      render(<Live20Table results={[result]} />);

      // Score bar uses gradient - check for the text color
      const scoreText = screen.getByText('20');
      expect(scoreText).toHaveClass('text-accent-bearish');
    });
  });
});
