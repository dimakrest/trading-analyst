import { useAccount } from '@/contexts/AccountContext';
import { Skeleton } from '@/components/ui/skeleton';
import { Tooltip, TooltipContent, TooltipTrigger, TooltipProvider } from '@/components/ui/tooltip';
import { cn } from '@/lib/utils';
import { formatCurrency, formatPnL } from '@/utils/formatters';

/**
 * Connection status indicator component with LED-style glow
 * Uses the .status-led CSS class from index.css
 */
function ConnectionDot({
  connected,
  label,
}: {
  connected: boolean;
  label: string;
}) {
  return (
    <div className="flex items-center gap-2 shrink-0">
      <div
        className={cn(
          'status-led',
          !connected && 'status-led-disconnected'
        )}
        role="status"
        aria-label={connected ? 'Connected' : 'Disconnected'}
      />
      <span className="text-xs text-text-muted">{label}</span>
      <span className="font-mono text-xs font-medium text-text-primary">
        {connected ? 'Connected' : 'Disconnected'}
      </span>
    </div>
  );
}

/**
 * Data value display with monospace font for numerical consistency
 */
function DataValue({
  label,
  value,
  testId,
  className,
  children
}: {
  label?: string;
  value?: string | React.ReactNode;
  testId?: string;
  className?: string;
  children?: React.ReactNode;
}) {
  return (
    <div
      className={cn("flex items-center gap-2 shrink-0", className)}
      data-testid={testId}
    >
      {label && (
        <span className="text-xs text-text-muted">{label}</span>
      )}
      <span className="font-mono text-sm font-semibold text-text-primary">
        {children || value}
      </span>
    </div>
  );
}

export function SystemStatusBar() {
  const { status, isLoading } = useAccount();

  // Loading state with refined skeleton
  if (isLoading && !status) {
    return (
      <header className="bg-bg-secondary border-b border-subtle px-6 py-3">
        <div className="flex items-center gap-6">
          <Skeleton className="h-4 w-24 bg-bg-tertiary" />
          <Skeleton className="h-5 w-16 bg-bg-tertiary" />
          <Skeleton className="h-4 w-32 bg-bg-tertiary" />
          <div className="ml-auto">
            <Skeleton className="h-4 w-24 bg-bg-tertiary" />
          </div>
        </div>
      </header>
    );
  }

  const broker = status?.broker;
  const dataProvider = status?.data_provider;

  const brokerConnected = broker?.connection_status === 'CONNECTED';
  const dataProviderConnected = dataProvider?.connection_status === 'CONNECTED';
  const isPaper = broker?.account_type === 'PAPER';
  const isLive = broker?.account_type === 'LIVE';

  // Format P&L values with consistent null handling
  const unrealizedPnl = formatPnL(broker?.unrealized_pnl ?? null);
  const realizedPnl = formatPnL(broker?.realized_pnl ?? null);

  return (
    <TooltipProvider>
      <header
        role="banner"
        aria-label="System status"
        className="bg-bg-secondary border-b border-subtle px-6 py-3"
      >
        <div className="flex items-center gap-6">
          {/* Broker connection indicator */}
          <ConnectionDot
            connected={brokerConnected}
            label="Broker"
          />

          {brokerConnected && (
            <>
              {/* Account type badge */}
              <span
                data-testid="account-type-badge"
                className={cn(
                  isPaper && 'status-badge-paper',
                  isLive && 'status-badge-live',
                  !isPaper && !isLive && 'status-badge-paper'
                )}
              >
                {broker?.account_type || 'UNKNOWN'}
              </span>

              {/* Account ID - hide on mobile */}
              <Tooltip>
                <TooltipTrigger asChild>
                  <span
                    className="hidden sm:inline text-text-muted font-mono text-xs truncate max-w-[100px] cursor-help"
                    data-testid="account-id"
                  >
                    {broker?.account_id || '-'}
                  </span>
                </TooltipTrigger>
                <TooltipContent className="bg-bg-elevated border-default text-text-primary font-mono">
                  <p>{broker?.account_id}</p>
                </TooltipContent>
              </Tooltip>

              {/* Balance */}
              <DataValue
                label="Balance"
                testId="account-balance"
              >
                {formatCurrency(parseFloat(broker?.net_liquidation ?? '0'))}
              </DataValue>
            </>
          )}

          {!brokerConnected && broker?.error_message && (
            <span
              className="text-xs text-accent-bearish font-medium truncate max-w-xs"
              title={broker.error_message}
            >
              {broker.error_message}
            </span>
          )}

          {/* P&L section - aligned right */}
          <div className="ml-auto flex items-center gap-5 hidden lg:flex">
            {brokerConnected && (
              <>
                {/* Unrealized P&L */}
                <div className="text-right" data-testid="unrealized-pnl">
                  <div className="text-[10px] uppercase tracking-[0.05em] text-text-muted mb-0.5">
                    Unrealized
                  </div>
                  <div className={cn('font-mono text-sm font-semibold', unrealizedPnl.className)}>
                    {unrealizedPnl.symbol && unrealizedPnl.symbol}
                    {unrealizedPnl.text}
                  </div>
                </div>

                {/* Realized P&L */}
                <div className="text-right" data-testid="realized-pnl">
                  <div className="text-[10px] uppercase tracking-[0.05em] text-text-muted mb-0.5">
                    Realized
                  </div>
                  <div className={cn('font-mono text-sm font-semibold', realizedPnl.className)}>
                    {realizedPnl.symbol && realizedPnl.symbol}
                    {realizedPnl.text}
                  </div>
                </div>
              </>
            )}

            {/* Data provider connection indicator */}
            <div
              className="flex items-center gap-2 shrink-0"
              data-testid="data-provider-status"
            >
              <div
                className={cn(
                  'status-led',
                  !dataProviderConnected && 'status-led-disconnected'
                )}
                role="status"
                aria-label={dataProviderConnected ? 'Data Connected' : 'Data Disconnected'}
              />
              <span className="text-xs text-text-muted">Data</span>

              {!dataProviderConnected && dataProvider?.error_message && (
                <Tooltip>
                  <TooltipTrigger asChild>
                    <span className="text-[10px] text-accent-bearish font-semibold uppercase cursor-help">
                      (error)
                    </span>
                  </TooltipTrigger>
                  <TooltipContent className="bg-bg-elevated border-default text-accent-bearish">
                    <p>{dataProvider.error_message}</p>
                  </TooltipContent>
                </Tooltip>
              )}
            </div>
          </div>
        </div>
      </header>
    </TooltipProvider>
  );
}
