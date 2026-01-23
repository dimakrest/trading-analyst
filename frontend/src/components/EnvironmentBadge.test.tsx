import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { EnvironmentBadge } from './EnvironmentBadge';

// Mock the useEnvironment hook
vi.mock('@/contexts/EnvironmentContext', () => ({
  useEnvironment: vi.fn(),
}));

import { useEnvironment } from '@/contexts/EnvironmentContext';

describe('EnvironmentBadge', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders DEV badge for development environment', () => {
    vi.mocked(useEnvironment).mockReturnValue({
      environment: 'development',
      isLoading: false,
    });

    render(<EnvironmentBadge />);

    const badge = screen.getByText('DEV');
    expect(badge).toBeInTheDocument();
    // Now uses nav-env-badge class for consistent Trading Terminal aesthetic
    expect(badge).toHaveClass('nav-env-badge');
  });

  it('renders PROD badge for production environment', () => {
    vi.mocked(useEnvironment).mockReturnValue({
      environment: 'production',
      isLoading: false,
    });

    render(<EnvironmentBadge />);

    const badge = screen.getByText('PROD');
    expect(badge).toBeInTheDocument();
    // PROD uses semantic env-prod color token
    expect(badge).toHaveClass('nav-env-badge');
    expect(badge).toHaveClass('text-env-prod');
  });

  it('renders nothing when loading', () => {
    vi.mocked(useEnvironment).mockReturnValue({
      environment: 'unknown',
      isLoading: true,
    });

    const { container } = render(<EnvironmentBadge />);
    expect(container).toBeEmptyDOMElement();
  });

  it('renders nothing for unknown environment', () => {
    vi.mocked(useEnvironment).mockReturnValue({
      environment: 'unknown',
      isLoading: false,
    });

    const { container } = render(<EnvironmentBadge />);
    expect(container).toBeEmptyDOMElement();
  });
});
