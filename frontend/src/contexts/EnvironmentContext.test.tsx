import { render, screen, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { EnvironmentProvider, useEnvironment } from './EnvironmentContext';
import { apiClient } from '@/lib/apiClient';

// Mock apiClient
vi.mock('@/lib/apiClient', () => ({
  apiClient: {
    get: vi.fn(),
  },
}));

// Test component that displays environment
function TestComponent() {
  const { environment, isLoading } = useEnvironment();
  return (
    <div>
      <span data-testid="loading">{isLoading.toString()}</span>
      <span data-testid="environment">{environment}</span>
    </div>
  );
}

describe('EnvironmentContext', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('fetches environment from health endpoint', async () => {
    vi.mocked(apiClient.get).mockResolvedValue({
      data: { environment: 'development' },
    });

    render(
      <EnvironmentProvider>
        <TestComponent />
      </EnvironmentProvider>
    );

    await waitFor(() => {
      expect(screen.getByTestId('loading')).toHaveTextContent('false');
    });

    expect(screen.getByTestId('environment')).toHaveTextContent('development');
    expect(apiClient.get).toHaveBeenCalledWith('/v1/health');
  });

  it('handles production environment', async () => {
    vi.mocked(apiClient.get).mockResolvedValue({
      data: { environment: 'production' },
    });

    render(
      <EnvironmentProvider>
        <TestComponent />
      </EnvironmentProvider>
    );

    await waitFor(() => {
      expect(screen.getByTestId('environment')).toHaveTextContent('production');
    });
  });

  it('handles API error gracefully', async () => {
    vi.mocked(apiClient.get).mockRejectedValue(new Error('Network error'));

    render(
      <EnvironmentProvider>
        <TestComponent />
      </EnvironmentProvider>
    );

    await waitFor(() => {
      expect(screen.getByTestId('loading')).toHaveTextContent('false');
    });

    expect(screen.getByTestId('environment')).toHaveTextContent('unknown');
  });
});
