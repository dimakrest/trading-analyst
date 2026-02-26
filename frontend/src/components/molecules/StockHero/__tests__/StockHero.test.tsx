import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { StockHero, type StockHeroStats } from '../StockHero';

describe('StockHero', () => {
  const defaultStats: StockHeroStats = {
    dayHigh: 180.5,
    dayLow: 176.25,
    volume: 48200000,
    prevClose: 176.11,
    ma20: 175.8,
    cci: 125.3,
  };

  const defaultProps = {
    symbol: 'AAPL',
    price: 178.45,
    change: 2.34,
    changePercent: 1.33,
    direction: 'bullish' as const,
    stats: defaultStats,
  };

  describe('Bullish state', () => {
    it('should render with bullish data and green glow', () => {
      // Arrange & Act
      render(<StockHero {...defaultProps} />);

      // Assert - component renders
      expect(screen.getByTestId('stock-hero')).toBeInTheDocument();

      // Assert - symbol displays
      expect(screen.getByTestId('stock-hero-symbol')).toHaveTextContent('AAPL');

      // Assert - bullish badge shows
      const badge = screen.getByTestId('stock-hero-badge');
      expect(badge).toHaveTextContent('Bullish');
      expect(badge).toHaveClass('text-accent-bullish');
      expect(badge).toHaveClass('border-accent-bullish');
    });

    it('should display positive change in bullish color', () => {
      // Arrange & Act
      render(<StockHero {...defaultProps} />);

      // Assert
      const changeElement = screen.getByTestId('stock-hero-change');
      expect(changeElement).toHaveTextContent('+$2.34');
      expect(changeElement).toHaveClass('text-accent-bullish');
    });

    it('should apply bullish glow effect', () => {
      // Arrange & Act
      const { container } = render(<StockHero {...defaultProps} />);

      // Assert
      const glowElement = container.querySelector('.hero-glow-bullish');
      expect(glowElement).toBeInTheDocument();
    });
  });

  describe('Bearish state', () => {
    it('should render with bearish data and red glow', () => {
      // Arrange
      const bearishProps = {
        ...defaultProps,
        change: -3.21,
        changePercent: -1.78,
        direction: 'bearish' as const,
      };

      // Act
      render(<StockHero {...bearishProps} />);

      // Assert - bearish badge shows
      const badge = screen.getByTestId('stock-hero-badge');
      expect(badge).toHaveTextContent('Bearish');
      expect(badge).toHaveClass('text-accent-bearish');
      expect(badge).toHaveClass('border-accent-bearish');
    });

    it('should display negative change in bearish color', () => {
      // Arrange
      const bearishProps = {
        ...defaultProps,
        change: -3.21,
        changePercent: -1.78,
        direction: 'bearish' as const,
      };

      // Act
      render(<StockHero {...bearishProps} />);

      // Assert
      const changeElement = screen.getByTestId('stock-hero-change');
      expect(changeElement).toHaveTextContent('-$3.21');
      expect(changeElement).toHaveClass('text-accent-bearish');
    });

    it('should apply bearish glow effect', () => {
      // Arrange
      const bearishProps = {
        ...defaultProps,
        direction: 'bearish' as const,
      };

      // Act
      const { container } = render(<StockHero {...bearishProps} />);

      // Assert
      const glowElement = container.querySelector('.hero-glow-bearish');
      expect(glowElement).toBeInTheDocument();
    });
  });

  describe('Neutral state', () => {
    it('should not display badge when direction is neutral', () => {
      // Arrange
      const neutralProps = {
        ...defaultProps,
        direction: 'neutral' as const,
      };

      // Act
      render(<StockHero {...neutralProps} />);

      // Assert - no badge rendered
      expect(screen.queryByTestId('stock-hero-badge')).not.toBeInTheDocument();
    });

    it('should not display glow effect when direction is neutral', () => {
      // Arrange
      const neutralProps = {
        ...defaultProps,
        direction: 'neutral' as const,
      };

      // Act
      const { container } = render(<StockHero {...neutralProps} />);

      // Assert - no glow elements
      expect(container.querySelector('.hero-glow-bullish')).not.toBeInTheDocument();
      expect(container.querySelector('.hero-glow-bearish')).not.toBeInTheDocument();
    });
  });

  describe('Price display', () => {
    it('should display large price with 48px styling', () => {
      // Arrange & Act
      render(<StockHero {...defaultProps} />);

      // Assert
      const priceElement = screen.getByTestId('stock-hero-price');
      expect(priceElement).toBeInTheDocument();
      expect(priceElement).toHaveClass('text-[48px]');
      expect(priceElement).toHaveClass('font-mono');
      expect(priceElement).toHaveClass('font-bold');
    });

    it('should split price into dollars and cents', () => {
      // Arrange & Act
      render(<StockHero {...defaultProps} />);

      // Assert - price contains dollar sign and formatted value
      const priceElement = screen.getByTestId('stock-hero-price');
      expect(priceElement).toHaveTextContent('$178');
      expect(priceElement).toHaveTextContent('.45');
    });

    it('should handle prices with no cents correctly', () => {
      // Arrange
      const noCentsProps = {
        ...defaultProps,
        price: 178.0,
      };

      // Act
      render(<StockHero {...noCentsProps} />);

      // Assert
      const priceElement = screen.getByTestId('stock-hero-price');
      expect(priceElement).toHaveTextContent('$178');
      expect(priceElement).toHaveTextContent('.00');
    });

    it('should handle large prices with comma formatting', () => {
      // Arrange
      const largePriceProps = {
        ...defaultProps,
        price: 1234.56,
      };

      // Act
      render(<StockHero {...largePriceProps} />);

      // Assert
      const priceElement = screen.getByTestId('stock-hero-price');
      expect(priceElement).toHaveTextContent('$1,234');
      expect(priceElement).toHaveTextContent('.56');
    });
  });

  describe('Stats grid', () => {
    it('should display all 6 stats correctly', () => {
      // Arrange & Act
      render(<StockHero {...defaultProps} />);

      // Assert - stats grid exists
      const statsGrid = screen.getByTestId('stock-hero-stats');
      expect(statsGrid).toBeInTheDocument();
      expect(statsGrid).toHaveClass('grid-cols-3');

      // Assert - all labels present
      expect(screen.getByText('Day High')).toBeInTheDocument();
      expect(screen.getByText('Day Low')).toBeInTheDocument();
      expect(screen.getByText('Volume')).toBeInTheDocument();
      expect(screen.getByText('Prev Close')).toBeInTheDocument();
      expect(screen.getByText('MA 20')).toBeInTheDocument();
      expect(screen.getByText('CCI')).toBeInTheDocument();
    });

    it('should format currency values correctly', () => {
      // Arrange & Act
      render(<StockHero {...defaultProps} />);

      // Assert - currency formatting
      expect(screen.getByText('$180.50')).toBeInTheDocument(); // Day High
      expect(screen.getByText('$176.25')).toBeInTheDocument(); // Day Low
      expect(screen.getByText('$176.11')).toBeInTheDocument(); // Prev Close
      expect(screen.getByText('$175.80')).toBeInTheDocument(); // MA 20
    });

    it('should format volume with abbreviation', () => {
      // Arrange & Act
      render(<StockHero {...defaultProps} />);

      // Assert - volume shows as 48.2M
      expect(screen.getByText('48.2M')).toBeInTheDocument();
    });

    it('should format CCI with one decimal place', () => {
      // Arrange & Act
      render(<StockHero {...defaultProps} />);

      // Assert
      expect(screen.getByText('125.3')).toBeInTheDocument();
    });

    it('should apply bullish color to Day High', () => {
      // Arrange & Act
      render(<StockHero {...defaultProps} />);

      // Assert
      const dayHighValue = screen.getByText('$180.50');
      expect(dayHighValue).toHaveClass('text-accent-bullish');
    });

    it('should apply bearish color to Day Low', () => {
      // Arrange & Act
      render(<StockHero {...defaultProps} />);

      // Assert
      const dayLowValue = screen.getByText('$176.25');
      expect(dayLowValue).toHaveClass('text-accent-bearish');
    });

    it('should apply bullish color to positive CCI', () => {
      // Arrange & Act
      render(<StockHero {...defaultProps} />);

      // Assert
      const cciValue = screen.getByText('125.3');
      expect(cciValue).toHaveClass('text-accent-bullish');
    });

    it('should apply bearish color to negative CCI', () => {
      // Arrange
      const negativeCciProps = {
        ...defaultProps,
        stats: { ...defaultStats, cci: -85.2 },
      };

      // Act
      render(<StockHero {...negativeCciProps} />);

      // Assert
      const cciValue = screen.getByText('-85.2');
      expect(cciValue).toHaveClass('text-accent-bearish');
    });

    it('should apply default color to zero CCI', () => {
      // Arrange
      const zeroCciProps = {
        ...defaultProps,
        stats: { ...defaultStats, cci: 0 },
      };

      // Act
      render(<StockHero {...zeroCciProps} />);

      // Assert
      const cciValue = screen.getByText('0.0');
      expect(cciValue).toHaveClass('text-text-primary');
    });
  });

  describe('Sector ETF badge', () => {
    it('should display sector ETF badge when sectorEtf is provided', () => {
      // Arrange & Act
      render(<StockHero {...defaultProps} sectorEtf="XLK" />);

      // Assert
      expect(screen.getByText('XLK')).toBeInTheDocument();
    });

    it('should not display sector badge when sectorEtf is null', () => {
      // Arrange & Act
      render(<StockHero {...defaultProps} sectorEtf={null} />);

      // Assert - no sector badge rendered
      expect(screen.queryByText('XLK')).not.toBeInTheDocument();
    });

    it('should not display sector badge when sectorEtf is undefined', () => {
      // Arrange & Act
      render(<StockHero {...defaultProps} />);

      // Assert - no sector badge rendered (no extra spans in the symbol row)
      const symbolRow = screen.getByTestId('stock-hero-symbol').parentElement;
      const sectorBadge = symbolRow?.querySelector('.font-mono.text-xs.bg-bg-elevated');
      expect(sectorBadge).not.toBeInTheDocument();
    });

    it('should apply correct styling to sector badge', () => {
      // Arrange & Act
      render(<StockHero {...defaultProps} sectorEtf="XLE" />);

      // Assert
      const sectorBadge = screen.getByText('XLE');
      expect(sectorBadge).toHaveClass('font-mono');
      expect(sectorBadge).toHaveClass('text-xs');
      expect(sectorBadge).toHaveClass('bg-bg-elevated');
      expect(sectorBadge).toHaveClass('text-text-muted');
      expect(sectorBadge).toHaveClass('border-subtle');
    });
  });

  describe('Badge animation', () => {
    it('should have badge-dot class for pulse animation', () => {
      // Arrange & Act
      const { container } = render(<StockHero {...defaultProps} />);

      // Assert
      const badgeDot = container.querySelector('.badge-dot');
      expect(badgeDot).toBeInTheDocument();
    });
  });

  describe('Loading state', () => {
    it('should render loading skeleton when isLoading is true', () => {
      // Arrange & Act
      render(<StockHero {...defaultProps} isLoading />);

      // Assert
      expect(screen.getByTestId('stock-hero-loading')).toBeInTheDocument();
      expect(screen.queryByTestId('stock-hero')).not.toBeInTheDocument();
    });

    it('should not render symbol when loading', () => {
      // Arrange & Act
      render(<StockHero {...defaultProps} isLoading />);

      // Assert
      expect(screen.queryByText('AAPL')).not.toBeInTheDocument();
    });

    it('should show animated skeleton elements', () => {
      // Arrange & Act
      const { container } = render(<StockHero {...defaultProps} isLoading />);

      // Assert - check for animate-pulse class
      const animatedElements = container.querySelectorAll('.animate-pulse');
      expect(animatedElements.length).toBeGreaterThan(0);
    });
  });

  describe('Missing stat values', () => {
    it('should display em-dash for null stat values', () => {
      // Arrange
      const nullStatsProps = {
        ...defaultProps,
        stats: {
          dayHigh: null,
          dayLow: null,
          volume: null,
          prevClose: null,
          ma20: null,
          cci: null,
        },
      };

      // Act
      render(<StockHero {...nullStatsProps} />);

      // Assert - em-dashes displayed for missing values
      const emDashes = screen.getAllByText('\u2014');
      expect(emDashes).toHaveLength(6);
    });

    it('should display em-dash for undefined stat values', () => {
      // Arrange
      const undefinedStatsProps = {
        ...defaultProps,
        stats: {},
      };

      // Act
      render(<StockHero {...undefinedStatsProps} />);

      // Assert - em-dashes displayed for missing values
      const emDashes = screen.getAllByText('\u2014');
      expect(emDashes).toHaveLength(6);
    });

    it('should handle partial stats gracefully', () => {
      // Arrange
      const partialStatsProps = {
        ...defaultProps,
        stats: {
          dayHigh: 180.5,
          // dayLow: missing
          volume: 48200000,
          // prevClose: missing
          // ma20: missing
          cci: 125.3,
        },
      };

      // Act
      render(<StockHero {...partialStatsProps} />);

      // Assert - some values present, some em-dashes
      expect(screen.getByText('$180.50')).toBeInTheDocument();
      expect(screen.getByText('48.2M')).toBeInTheDocument();
      expect(screen.getByText('125.3')).toBeInTheDocument();
      const emDashes = screen.getAllByText('\u2014');
      expect(emDashes).toHaveLength(3);
    });
  });

  describe('Change percentage display', () => {
    it('should display positive change percentage', () => {
      // Arrange & Act
      render(<StockHero {...defaultProps} />);

      // Assert
      const percentElement = screen.getByTestId('stock-hero-change-percent');
      expect(percentElement).toHaveTextContent('+1.33%');
    });

    it('should display negative change percentage', () => {
      // Arrange
      const negativeProps = {
        ...defaultProps,
        change: -2.34,
        changePercent: -1.33,
        direction: 'bearish' as const,
      };

      // Act
      render(<StockHero {...negativeProps} />);

      // Assert
      const percentElement = screen.getByTestId('stock-hero-change-percent');
      expect(percentElement).toHaveTextContent('-1.33%');
    });
  });

  describe('CSS classes and styling', () => {
    it('should have gradient background', () => {
      // Arrange & Act
      render(<StockHero {...defaultProps} />);

      // Assert
      const hero = screen.getByTestId('stock-hero');
      expect(hero).toHaveClass('bg-gradient-to-br');
      expect(hero).toHaveClass('from-bg-secondary');
      expect(hero).toHaveClass('to-bg-tertiary');
    });

    it('should have rounded corners', () => {
      // Arrange & Act
      render(<StockHero {...defaultProps} />);

      // Assert
      const hero = screen.getByTestId('stock-hero');
      expect(hero).toHaveClass('rounded-lg');
    });

    it('should have border', () => {
      // Arrange & Act
      render(<StockHero {...defaultProps} />);

      // Assert
      const hero = screen.getByTestId('stock-hero');
      expect(hero).toHaveClass('border');
      expect(hero).toHaveClass('border-default');
    });

    it('should have overflow hidden for glow effect', () => {
      // Arrange & Act
      render(<StockHero {...defaultProps} />);

      // Assert
      const hero = screen.getByTestId('stock-hero');
      expect(hero).toHaveClass('overflow-hidden');
    });

    it('should apply custom className when provided', () => {
      // Arrange & Act
      render(<StockHero {...defaultProps} className="custom-class" />);

      // Assert
      const hero = screen.getByTestId('stock-hero');
      expect(hero).toHaveClass('custom-class');
    });
  });

  describe('Typography', () => {
    it('should use font-display for symbol', () => {
      // Arrange & Act
      render(<StockHero {...defaultProps} />);

      // Assert
      const symbol = screen.getByTestId('stock-hero-symbol');
      expect(symbol).toHaveClass('font-display');
      expect(symbol).toHaveClass('text-4xl');
      expect(symbol).toHaveClass('font-bold');
    });

    it('should use font-mono for price', () => {
      // Arrange & Act
      render(<StockHero {...defaultProps} />);

      // Assert
      const price = screen.getByTestId('stock-hero-price');
      expect(price).toHaveClass('font-mono');
    });

    it('should use font-mono for change value', () => {
      // Arrange & Act
      render(<StockHero {...defaultProps} />);

      // Assert
      const change = screen.getByTestId('stock-hero-change');
      expect(change).toHaveClass('font-mono');
    });
  });

  describe('Responsive layout', () => {
    it('should have responsive grid columns', () => {
      // Arrange & Act
      render(<StockHero {...defaultProps} />);

      // Assert
      const hero = screen.getByTestId('stock-hero');
      expect(hero).toHaveClass('grid-cols-1');
      expect(hero).toHaveClass('lg:grid-cols-[1fr_auto]');
    });

    it('should have responsive padding', () => {
      // Arrange & Act
      render(<StockHero {...defaultProps} />);

      // Assert
      const hero = screen.getByTestId('stock-hero');
      expect(hero).toHaveClass('p-6');
      expect(hero).toHaveClass('lg:p-7');
    });
  });
});
