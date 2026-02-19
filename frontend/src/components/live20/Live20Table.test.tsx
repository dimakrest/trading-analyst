import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Live20Table } from './Live20Table';
import type { Live20Result } from '../../types/live20';

// Mock the ExpandedRowContent to avoid async complexity in these tests
vi.mock('./ExpandedRowContent', () => ({
  ExpandedRowContent: ({ result }: { result: Live20Result }) => (
    <div data-testid="expanded-content">Expanded content for {result.stock}</div>
  ),
}));

const createMockResult = (overrides: Partial<Live20Result> = {}): Live20Result => ({
  id: 1,
  stock: 'TEST',
  created_at: '2025-12-22T00:00:00Z',
  recommendation: 'LONG',
  confidence_score: 80,
  atr: 2.35,
  sector_etf: 'XLK',
  trend_direction: 'bearish',
  trend_aligned: true,
  ma20_distance_pct: -7.0,
  ma20_aligned: true,
  candle_pattern: 'hammer',
  candle_bullish: true,
  candle_aligned: true,
  candle_explanation: null,
  volume_aligned: true,
  volume_approach: 'accumulation',
  rvol: 1.5,
  cci_direction: 'rising',
  cci_value: -86.1,
  cci_zone: 'neutral',
  cci_aligned: true,
  criteria_aligned: 5,
  direction: 'LONG',
  ...overrides,
});

describe('Live20Table', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('Row expansion', () => {
    it('renders expand button in first column', () => {
      const result = createMockResult({ stock: 'AAPL' });
      render(<Live20Table results={[result]} />);

      const expandButton = screen.getByLabelText('Expand details for AAPL');
      expect(expandButton).toBeInTheDocument();
    });

    it('expand button has correct aria-expanded attribute', () => {
      const result = createMockResult({ stock: 'AAPL' });
      render(<Live20Table results={[result]} />);

      const expandButton = screen.getByLabelText('Expand details for AAPL');
      expect(expandButton).toHaveAttribute('aria-expanded', 'false');
    });

    it('expands row when expand button is clicked', async () => {
      const user = userEvent.setup();
      const result = createMockResult({ stock: 'AAPL' });
      render(<Live20Table results={[result]} />);

      const expandButton = screen.getByLabelText('Expand details for AAPL');

      // Initially not expanded
      expect(screen.queryByTestId('expanded-content')).not.toBeInTheDocument();

      // Click to expand
      await user.click(expandButton);

      // Should be expanded now
      await waitFor(() => {
        expect(screen.getByTestId('expanded-content')).toBeInTheDocument();
        expect(screen.getByText('Expanded content for AAPL')).toBeInTheDocument();
      });

      // Aria attribute should update
      expect(expandButton).toHaveAttribute('aria-expanded', 'true');
    });

    it('collapses row when expand button is clicked again', async () => {
      const user = userEvent.setup();
      const result = createMockResult({ stock: 'AAPL' });
      render(<Live20Table results={[result]} />);

      const expandButton = screen.getByLabelText('Expand details for AAPL');

      // Expand
      await user.click(expandButton);
      await waitFor(() => {
        expect(screen.getByTestId('expanded-content')).toBeInTheDocument();
      });

      // Collapse
      await user.click(expandButton);
      await waitFor(() => {
        expect(screen.queryByTestId('expanded-content')).not.toBeInTheDocument();
      });

      expect(expandButton).toHaveAttribute('aria-expanded', 'false');
    });

    it('shows chevron right when collapsed', () => {
      const result = createMockResult({ stock: 'AAPL' });
      render(<Live20Table results={[result]} />);

      const expandButton = screen.getByLabelText('Expand details for AAPL');
      // ChevronRight icon should be present
      const chevronRight = expandButton.querySelector('svg');
      expect(chevronRight).toBeInTheDocument();
    });

    it('shows chevron down when expanded', async () => {
      const user = userEvent.setup();
      const result = createMockResult({ stock: 'AAPL' });
      render(<Live20Table results={[result]} />);

      const expandButton = screen.getByLabelText('Expand details for AAPL');

      // Expand
      await user.click(expandButton);

      await waitFor(() => {
        // ChevronDown icon should be present (still an svg, but different icon)
        const chevronDown = expandButton.querySelector('svg');
        expect(chevronDown).toBeInTheDocument();
      });
    });

    it('allows multiple rows to be expanded simultaneously', async () => {
      const user = userEvent.setup();
      const results = [
        createMockResult({ stock: 'AAPL', id: 1 }),
        createMockResult({ stock: 'MSFT', id: 2 }),
        createMockResult({ stock: 'NVDA', id: 3 }),
      ];
      render(<Live20Table results={results} />);

      const aaplButton = screen.getByLabelText('Expand details for AAPL');
      const msftButton = screen.getByLabelText('Expand details for MSFT');

      // Expand both
      await user.click(aaplButton);
      await user.click(msftButton);

      await waitFor(() => {
        expect(screen.getByText('Expanded content for AAPL')).toBeInTheDocument();
        expect(screen.getByText('Expanded content for MSFT')).toBeInTheDocument();
      });
    });
  });

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

  describe('Sector column', () => {
    it('displays sector ETF symbol', () => {
      const result = createMockResult({ sector_etf: 'XLK' });
      render(<Live20Table results={[result]} />);

      expect(screen.getByText('XLK')).toBeInTheDocument();
    });

    it('displays dash when sector_etf is null', () => {
      const result = createMockResult({ sector_etf: null });
      render(<Live20Table results={[result]} />);

      // Find the sector cell (3rd column - Expand, Symbol, Sector)
      const row = screen.getByText('TEST').closest('tr');
      expect(row).toBeInTheDocument();
      const sectorCell = row?.querySelector('td:nth-child(3) span');
      expect(sectorCell).toBeInTheDocument();
      expect(sectorCell).toHaveTextContent('-');
    });

    it('applies correct styling', () => {
      const result = createMockResult({ sector_etf: 'XLE' });
      render(<Live20Table results={[result]} />);

      const sectorText = screen.getByText('XLE');
      expect(sectorText).toHaveClass('text-xs');
      expect(sectorText).toHaveClass('font-mono');
      expect(sectorText).toHaveClass('text-text-secondary');
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

  describe('Volume sorting', () => {
    it('sorts by rvol in ascending order', async () => {
      const user = userEvent.setup();
      const results = [
        createMockResult({ stock: 'LOW', rvol: 0.8 }),
        createMockResult({ stock: 'HIGH', rvol: 2.5 }),
        createMockResult({ stock: 'MID', rvol: 1.5 }),
      ];
      render(<Live20Table results={results} />);

      // Click Volume header to sort ascending
      const volumeHeader = screen.getByRole('button', { name: /volume/i });
      await user.click(volumeHeader);

      // Wait for re-render and check order: LOW (0.8), MID (1.5), HIGH (2.5)
      await waitFor(() => {
        const symbols = screen.getAllByText(/^(LOW|MID|HIGH)$/);
        expect(symbols[0]).toHaveTextContent('LOW');
        expect(symbols[1]).toHaveTextContent('MID');
        expect(symbols[2]).toHaveTextContent('HIGH');
      });
    });

    it('sorts by rvol in descending order', async () => {
      const user = userEvent.setup();
      const results = [
        createMockResult({ stock: 'LOW', rvol: 0.8 }),
        createMockResult({ stock: 'HIGH', rvol: 2.5 }),
        createMockResult({ stock: 'MID', rvol: 1.5 }),
      ];
      render(<Live20Table results={results} />);

      // Click Volume header twice to sort descending
      const volumeHeader = screen.getByRole('button', { name: /volume/i });
      await user.click(volumeHeader);
      await user.click(volumeHeader);

      // Wait for re-render and check order: HIGH (2.5), MID (1.5), LOW (0.8)
      await waitFor(() => {
        const symbols = screen.getAllByText(/^(LOW|MID|HIGH)$/);
        expect(symbols[0]).toHaveTextContent('HIGH');
        expect(symbols[1]).toHaveTextContent('MID');
        expect(symbols[2]).toHaveTextContent('LOW');
      });
    });

    it('handles null rvol values by treating them as 0', async () => {
      const user = userEvent.setup();
      const results = [
        createMockResult({ stock: 'NULL', rvol: null }),
        createMockResult({ stock: 'HIGH', rvol: 2.5 }),
        createMockResult({ stock: 'LOW', rvol: 0.8 }),
      ];
      render(<Live20Table results={results} />);

      // Click Volume header to sort ascending
      const volumeHeader = screen.getByRole('button', { name: /volume/i });
      await user.click(volumeHeader);

      // Wait for re-render and check order: NULL (0), LOW (0.8), HIGH (2.5)
      await waitFor(() => {
        const symbols = screen.getAllByText(/^(NULL|LOW|HIGH)$/);
        expect(symbols[0]).toHaveTextContent('NULL');
        expect(symbols[1]).toHaveTextContent('LOW');
        expect(symbols[2]).toHaveTextContent('HIGH');
      });
    });
  });

  describe('ATR column', () => {
    it('displays ATR value formatted as percentage', () => {
      const result = createMockResult({ atr: 2.35 });
      render(<Live20Table results={[result]} />);

      expect(screen.getByText('2.35%')).toBeInTheDocument();
    });

    it('displays dash when ATR is null', () => {
      const result = createMockResult({ atr: null });
      render(<Live20Table results={[result]} />);

      // Find the ATR cell (6th column - Expand, Symbol, Sector, Direction, Score, ATR) and verify it displays a dash
      const row = screen.getByText('TEST').closest('tr');
      expect(row).toBeInTheDocument();
      const atrCell = row?.querySelector('td:nth-child(6) span');
      expect(atrCell).toBeInTheDocument();
      expect(atrCell).toHaveTextContent('-');
    });

    describe('color coding', () => {
      it('displays green for low volatility (< 3%)', () => {
        const result = createMockResult({ atr: 2.5 });
        render(<Live20Table results={[result]} />);

        const atrCell = screen.getByText('2.50%');
        expect(atrCell).toHaveClass('text-accent-bullish');
      });

      it('displays orange for moderate volatility (3-6%)', () => {
        const result = createMockResult({ atr: 4.5 });
        render(<Live20Table results={[result]} />);

        const atrCell = screen.getByText('4.50%');
        expect(atrCell).toHaveClass('text-score-medium');
      });

      it('displays red for high volatility (>= 6%)', () => {
        const result = createMockResult({ atr: 7.2 });
        render(<Live20Table results={[result]} />);

        const atrCell = screen.getByText('7.20%');
        expect(atrCell).toHaveClass('text-accent-bearish');
      });

      it('displays no color for null ATR', () => {
        const result = createMockResult({ atr: null });
        render(<Live20Table results={[result]} />);

        // Find the ATR cell in the row
        const row = screen.getByText('TEST').closest('tr');
        const atrCell = row?.querySelector('td:nth-child(6) span'); // ATR is 6th column (Expand, Symbol, Sector, Direction, Score, ATR)

        expect(atrCell).toBeInTheDocument();
        expect(atrCell).not.toHaveClass('text-accent-bullish');
        expect(atrCell).not.toHaveClass('text-score-medium');
        expect(atrCell).not.toHaveClass('text-accent-bearish');
      });

      it('applies font-semibold for better color visibility', () => {
        const result = createMockResult({ atr: 4.5 });
        render(<Live20Table results={[result]} />);

        const atrCell = screen.getByText('4.50%');
        expect(atrCell).toHaveClass('font-semibold');
      });

      it('handles edge case at 3% threshold (should be orange)', () => {
        const result = createMockResult({ atr: 3.0 });
        render(<Live20Table results={[result]} />);

        const atrCell = screen.getByText('3.00%');
        expect(atrCell).toHaveClass('text-score-medium');
      });

      it('handles edge case at 6% threshold (should be red)', () => {
        const result = createMockResult({ atr: 6.0 });
        render(<Live20Table results={[result]} />);

        const atrCell = screen.getByText('6.00%');
        expect(atrCell).toHaveClass('text-accent-bearish');
      });
    });
  });
});
