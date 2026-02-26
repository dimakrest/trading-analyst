import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, useLocation } from 'react-router-dom';
import { MobileBottomTabs } from './MobileBottomTabs';

// Helper component to display current location for testing
const LocationDisplay = () => {
  const location = useLocation();
  return <div data-testid="location">{location.pathname}</div>;
};

describe('MobileBottomTabs', () => {
  const renderWithRouter = (initialPath = '/') => {
    return render(
      <MemoryRouter initialEntries={[initialPath]}>
        <MobileBottomTabs />
        <LocationDisplay />
      </MemoryRouter>
    );
  };

  describe('Navigation Structure', () => {
    it('renders mobile navigation with correct aria-label', () => {
      renderWithRouter();

      const nav = screen.getByRole('navigation', { name: /mobile navigation/i });
      expect(nav).toBeInTheDocument();
    });

    it('renders Analysis navigation item as a link', () => {
      renderWithRouter();

      expect(screen.getByRole('link', { name: /analysis/i })).toBeInTheDocument();
    });

    it('uses 1-column grid layout', () => {
      renderWithRouter();

      const nav = screen.getByRole('navigation', { name: /mobile navigation/i });
      const grid = nav.querySelector('.grid-cols-1');
      expect(grid).toBeInTheDocument();
    });
  });

  describe('Active State', () => {
    it('highlights Analysis when on root path', () => {
      renderWithRouter('/');

      const analysisLink = screen.getByRole('link', { name: /analysis/i });
      expect(analysisLink).toHaveAttribute('aria-current', 'page');
      expect(analysisLink).toHaveClass('text-accent-primary');
    });

    it('highlights Analysis when on stock detail path', () => {
      renderWithRouter('/stock/AAPL');

      const analysisLink = screen.getByRole('link', { name: /analysis/i });
      expect(analysisLink).toHaveAttribute('aria-current', 'page');
    });

    it('applies stroke-[2.5] to active icons', () => {
      renderWithRouter('/');

      const analysisLink = screen.getByRole('link', { name: /analysis/i });
      const icon = analysisLink.querySelector('svg');
      expect(icon).toHaveClass('stroke-[2.5]');
    });
  });

  describe('Accessibility', () => {
    it('has minimum touch target height of 44px for tabs', () => {
      renderWithRouter();

      const analysisLink = screen.getByRole('link', { name: /analysis/i });
      expect(analysisLink).toHaveClass('min-h-[44px]');
    });

    it('includes safe area inset for bottom padding', () => {
      renderWithRouter();

      const nav = screen.getByRole('navigation', { name: /mobile navigation/i });
      expect(nav).toHaveStyle({ paddingBottom: 'env(safe-area-inset-bottom)' });
    });
  });

  describe('Touch Feedback', () => {
    it('has active scale animation class on links', () => {
      renderWithRouter();

      const analysisLink = screen.getByRole('link', { name: /analysis/i });
      expect(analysisLink).toHaveClass('active:scale-95');
    });
  });

  describe('Icon Sizing', () => {
    it('uses 22x22px icons', () => {
      renderWithRouter();

      const analysisLink = screen.getByRole('link', { name: /analysis/i });
      const icon = analysisLink.querySelector('svg');
      expect(icon).toHaveClass('w-[22px]', 'h-[22px]');
    });
  });

  describe('Styling', () => {
    it('uses bg-bg-secondary for background', () => {
      renderWithRouter();

      const nav = screen.getByRole('navigation', { name: /mobile navigation/i });
      expect(nav).toHaveClass('bg-bg-secondary');
    });

    it('uses border-subtle for top border', () => {
      renderWithRouter();

      const nav = screen.getByRole('navigation', { name: /mobile navigation/i });
      expect(nav).toHaveClass('border-subtle');
    });

    it('hides on desktop (md:hidden)', () => {
      renderWithRouter();

      const nav = screen.getByRole('navigation', { name: /mobile navigation/i });
      expect(nav).toHaveClass('md:hidden');
    });
  });
});
