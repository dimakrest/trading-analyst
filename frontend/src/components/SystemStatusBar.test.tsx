import { render, screen } from '@testing-library/react';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import { SystemStatusBar } from './SystemStatusBar';
import * as AccountContext from '@/contexts/AccountContext';
import type { SystemStatus } from '@/types/account';

vi.mock('@/contexts/AccountContext');

const createMockStatus = (
  overrides: Partial<{
    brokerConnected: boolean;
    dataProviderConnected: boolean;
    accountType: 'PAPER' | 'LIVE' | 'UNKNOWN';
    brokerError: string | null;
    dataProviderError: string | null;
    unrealizedPnl: string | null;
    realizedPnl: string | null;
  }> = {}
): SystemStatus => {
  const {
    brokerConnected = true,
    dataProviderConnected = true,
    accountType = 'PAPER',
    brokerError = null,
    dataProviderError = null,
    unrealizedPnl = '150.50',
    realizedPnl = '-25.00',
  } = overrides;

  return {
    broker: {
      connection_status: brokerConnected ? 'CONNECTED' : 'DISCONNECTED',
      error_message: brokerError,
      account_id: brokerConnected ? 'DU1234567' : null,
      account_type: brokerConnected ? accountType : null,
      net_liquidation: brokerConnected ? '25000.00' : null,
      buying_power: brokerConnected ? '50000.00' : null,
      unrealized_pnl: brokerConnected ? unrealizedPnl : null,
      realized_pnl: brokerConnected ? realizedPnl : null,
      daily_pnl: brokerConnected ? '125.50' : null,
    },
    data_provider: {
      connection_status: dataProviderConnected ? 'CONNECTED' : 'DISCONNECTED',
      error_message: dataProviderError,
    },
  };
};

describe('SystemStatusBar', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('shows skeleton during initial loading', () => {
    vi.mocked(AccountContext.useAccount).mockReturnValue({
      status: null,
      isLoading: true,
      error: null,
      refresh: vi.fn(),
    });

    render(<SystemStatusBar />);

    // Loading skeleton should be present
    const header = screen.getByRole('banner');
    expect(header).toBeInTheDocument();
  });

  it('shows both broker and data provider connected', () => {
    vi.mocked(AccountContext.useAccount).mockReturnValue({
      status: createMockStatus(),
      isLoading: false,
      error: null,
      refresh: vi.fn(),
    });

    render(<SystemStatusBar />);

    expect(screen.getByTestId('data-provider-status')).toBeInTheDocument();
    expect(screen.getByText('Broker')).toBeInTheDocument();
    expect(screen.getByText('Data')).toBeInTheDocument();
    expect(screen.getByText('PAPER')).toBeInTheDocument();
  });

  it('shows broker disconnected with error message', () => {
    vi.mocked(AccountContext.useAccount).mockReturnValue({
      status: createMockStatus({
        brokerConnected: false,
        brokerError: 'Broker connection lost',
      }),
      isLoading: false,
      error: null,
      refresh: vi.fn(),
    });

    render(<SystemStatusBar />);

    // The new design shows "Disconnected" as part of ConnectionDot
    expect(screen.getByText('Disconnected')).toBeInTheDocument();
    expect(screen.getByText('Broker connection lost')).toBeInTheDocument();
  });

  it('shows data provider status', () => {
    vi.mocked(AccountContext.useAccount).mockReturnValue({
      status: createMockStatus({
        dataProviderConnected: false,
        dataProviderError: 'Data provider offline',
      }),
      isLoading: false,
      error: null,
      refresh: vi.fn(),
    });

    render(<SystemStatusBar />);

    expect(screen.getByText('Broker')).toBeInTheDocument();
    expect(screen.getByTestId('data-provider-status')).toBeInTheDocument();
  });

  it('shows both disconnected when both have issues', () => {
    vi.mocked(AccountContext.useAccount).mockReturnValue({
      status: createMockStatus({
        brokerConnected: false,
        dataProviderConnected: false,
        brokerError: 'Broker error',
        dataProviderError: 'Data error',
      }),
      isLoading: false,
      error: null,
      refresh: vi.fn(),
    });

    render(<SystemStatusBar />);

    // Should show disconnected state
    const disconnectedElements = screen.getAllByText('Disconnected');
    expect(disconnectedElements.length).toBeGreaterThanOrEqual(1);
  });

  it('shows LIVE badge with live styling', () => {
    vi.mocked(AccountContext.useAccount).mockReturnValue({
      status: createMockStatus({ accountType: 'LIVE' }),
      isLoading: false,
      error: null,
      refresh: vi.fn(),
    });

    render(<SystemStatusBar />);

    const badge = screen.getByTestId('account-type-badge');
    expect(badge).toHaveTextContent('LIVE');
    // Now uses CSS class from index.css
    expect(badge).toHaveClass('status-badge-live');
  });

  it('shows PAPER badge with paper styling', () => {
    vi.mocked(AccountContext.useAccount).mockReturnValue({
      status: createMockStatus({ accountType: 'PAPER' }),
      isLoading: false,
      error: null,
      refresh: vi.fn(),
    });

    render(<SystemStatusBar />);

    const badge = screen.getByTestId('account-type-badge');
    expect(badge).toHaveTextContent('PAPER');
    // Now uses CSS class from index.css
    expect(badge).toHaveClass('status-badge-paper');
  });

  it('shows P&L with correct symbols', () => {
    vi.mocked(AccountContext.useAccount).mockReturnValue({
      status: createMockStatus({
        unrealizedPnl: '150.50',
        realizedPnl: '-25.00',
      }),
      isLoading: false,
      error: null,
      refresh: vi.fn(),
    });

    render(<SystemStatusBar />);

    const unrealizedPnl = screen.getByTestId('unrealized-pnl');
    expect(unrealizedPnl).toHaveTextContent('$150.50');

    const realizedPnl = screen.getByTestId('realized-pnl');
    expect(realizedPnl).toHaveTextContent('-$25.00');
  });

  it('has proper accessibility attributes', () => {
    vi.mocked(AccountContext.useAccount).mockReturnValue({
      status: createMockStatus(),
      isLoading: false,
      error: null,
      refresh: vi.fn(),
    });

    render(<SystemStatusBar />);

    const banner = screen.getByRole('banner');
    expect(banner).toBeInTheDocument();
    expect(banner).toHaveAttribute('aria-label', 'System status');

    const statusIndicators = screen.getAllByRole('status');
    expect(statusIndicators.length).toBeGreaterThan(0);
  });

  it('uses bg-bg-secondary background styling', () => {
    vi.mocked(AccountContext.useAccount).mockReturnValue({
      status: createMockStatus(),
      isLoading: false,
      error: null,
      refresh: vi.fn(),
    });

    render(<SystemStatusBar />);

    const banner = screen.getByRole('banner');
    expect(banner).toHaveClass('bg-bg-secondary');
  });

  it('handles null P&L values with em dash', () => {
    vi.mocked(AccountContext.useAccount).mockReturnValue({
      status: createMockStatus({
        unrealizedPnl: null,
        realizedPnl: null,
      }),
      isLoading: false,
      error: null,
      refresh: vi.fn(),
    });

    render(<SystemStatusBar />);

    const unrealizedPnl = screen.getByTestId('unrealized-pnl');
    expect(unrealizedPnl).toHaveTextContent('\u2014'); // em-dash

    const realizedPnl = screen.getByTestId('realized-pnl');
    expect(realizedPnl).toHaveTextContent('\u2014'); // em-dash
  });

  it('displays account ID', () => {
    vi.mocked(AccountContext.useAccount).mockReturnValue({
      status: createMockStatus(),
      isLoading: false,
      error: null,
      refresh: vi.fn(),
    });

    render(<SystemStatusBar />);

    const accountId = screen.getByTestId('account-id');
    expect(accountId).toHaveTextContent('DU1234567');
  });

  it('displays account balance', () => {
    vi.mocked(AccountContext.useAccount).mockReturnValue({
      status: createMockStatus(),
      isLoading: false,
      error: null,
      refresh: vi.fn(),
    });

    render(<SystemStatusBar />);

    const balance = screen.getByTestId('account-balance');
    expect(balance).toHaveTextContent('$25,000.00');
  });

  it('shows zero P&L without symbols', () => {
    vi.mocked(AccountContext.useAccount).mockReturnValue({
      status: createMockStatus({
        unrealizedPnl: '0',
        realizedPnl: '0',
      }),
      isLoading: false,
      error: null,
      refresh: vi.fn(),
    });

    render(<SystemStatusBar />);

    const unrealizedPnl = screen.getByTestId('unrealized-pnl');
    expect(unrealizedPnl).toHaveTextContent('$0.00');

    const realizedPnl = screen.getByTestId('realized-pnl');
    expect(realizedPnl).toHaveTextContent('$0.00');
  });

  it('shows UNKNOWN with paper styling for unknown account type', () => {
    vi.mocked(AccountContext.useAccount).mockReturnValue({
      status: createMockStatus({ accountType: 'UNKNOWN' }),
      isLoading: false,
      error: null,
      refresh: vi.fn(),
    });

    render(<SystemStatusBar />);

    const badge = screen.getByTestId('account-type-badge');
    expect(badge).toHaveTextContent('UNKNOWN');
    // Falls back to paper styling when not paper or live
    expect(badge).toHaveClass('status-badge-paper');
  });

  it('does not crash when status is null', () => {
    vi.mocked(AccountContext.useAccount).mockReturnValue({
      status: null,
      isLoading: false,
      error: null,
      refresh: vi.fn(),
    });

    const { container } = render(<SystemStatusBar />);
    expect(container).toBeInTheDocument();
  });
});
