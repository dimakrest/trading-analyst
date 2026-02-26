export type ConnectionStatus = 'CONNECTED' | 'DISCONNECTED';
export type AccountType = 'PAPER' | 'LIVE' | 'UNKNOWN';

/** Broker connection status with account info */
export interface BrokerStatus {
  connection_status: ConnectionStatus;
  error_message: string | null;
  account_id: string | null;
  account_type: AccountType | null;
  net_liquidation: string | null;
  buying_power: string | null;
  unrealized_pnl: string | null;
  realized_pnl: string | null;
  daily_pnl: string | null;
}

/** Data provider connection status (no account info) */
export interface DataProviderStatus {
  connection_status: ConnectionStatus;
  error_message: string | null;
}

/** Combined system status */
export interface SystemStatus {
  broker: BrokerStatus;
  data_provider: DataProviderStatus;
}
