export type Interval = '1d' | '1h';

export interface StockPrice {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  ma_20?: number;  // 20-day Simple Moving Average (null for first 19 days)
  cci?: number;    // Commodity Channel Index (20-period)
  cci_signal?: 'momentum_bullish' | 'momentum_bearish' | 'reversal_buy' | 'reversal_sell';
}

export interface IndicatorData {
  date: string;
  ma_20?: number;
  cci?: number;
  cci_signal?: 'momentum_bullish' | 'momentum_bearish' | 'reversal_buy' | 'reversal_sell';
}

export interface IndicatorsResponse {
  symbol: string;
  data: IndicatorData[];
  total_records: number;
  start_date: string;
  end_date: string;
  interval: string;
  indicators: string[];
}

export interface StockInfo {
  symbol: string;
  name: string;
  sector: string | null;
  sector_etf: string | null;
  industry: string | null;
  exchange: string | null;
}

export interface StockData {
  symbol: string;
  company_name: string;
  current_price: number;
  price_change: number;
  price_change_percent: number;
  prices: StockPrice[];
}
