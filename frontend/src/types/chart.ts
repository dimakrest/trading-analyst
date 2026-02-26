/**
 * Horizontal price line configuration
 */
export interface ChartPriceLine {
  price: number;
  color: string;
  lineWidth?: number;
  lineStyle?: 'solid' | 'dashed' | 'dotted';
  label?: string;
  labelVisible?: boolean;
}

/**
 * Point marker on a specific candle
 */
export interface ChartMarker {
  date: string;  // YYYY-MM-DD format
  position: 'aboveBar' | 'belowBar' | 'inBar';
  shape: 'circle' | 'square' | 'arrowUp' | 'arrowDown';
  color: string;
  text?: string;
  size?: number;
}
