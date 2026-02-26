import { useMemo } from 'react';
import { ColorType } from 'lightweight-charts';

/**
 * Custom hook to provide dark theme configuration for Lightweight Charts
 *
 * @returns Chart options with dark theme configuration
 */
export const useChartTheme = () => {
  return useMemo(
    () => ({
      layout: {
        background: {
          type: ColorType.Solid,
          color: '#0a0a0a', // Near black (bg-black)
        },
        textColor: '#d1d5db', // Gray-300
        fontSize: 12,
        fontFamily:
          'ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
        attributionLogo: false, // Hide TradingView logo
      },
      grid: {
        vertLines: {
          color: '#1f2937', // Gray-800
          style: 1, // Solid line
          visible: true,
        },
        horzLines: {
          color: '#1f2937', // Gray-800
          style: 1, // Solid line
          visible: true,
        },
      },
      crosshair: {
        mode: 0, // Normal
        vertLine: {
          color: '#4b5563', // Gray-600
          style: 3, // Dashed line
          labelBackgroundColor: '#374151', // Gray-700
        },
        horzLine: {
          color: '#4b5563', // Gray-600
          style: 3, // Dashed line
          labelBackgroundColor: '#374151', // Gray-700
        },
      },
      rightPriceScale: {
        borderColor: '#374151', // Gray-700
        textColor: '#d1d5db', // Gray-300
        scaleMargins: {
          top: 0.1,
          bottom: 0.1,
        },
      },
      timeScale: {
        borderColor: '#374151', // Gray-700
        textColor: '#d1d5db', // Gray-300
        timeVisible: true,
        secondsVisible: false,
      },
      handleScroll: {
        mouseWheel: true,
        pressedMouseMove: true,
        horzTouchDrag: true,
        vertTouchDrag: false,
      },
      handleScale: {
        axisPressedMouseMove: true,
        mouseWheel: true,
        pinch: true,
      },
    }),
    []
  );
};

/**
 * Candlestick series style configuration
 */
export const useCandlestickStyle = () => {
  return useMemo(
    () => ({
      upColor: '#10b981', // Green-500 (bullish)
      downColor: '#ef4444', // Red-500 (bearish)
      borderVisible: false,
      wickUpColor: '#10b981', // Green-500
      wickDownColor: '#ef4444', // Red-500
      borderUpColor: '#10b981',
      borderDownColor: '#ef4444',
      wickVisible: true,
    }),
    []
  );
};
