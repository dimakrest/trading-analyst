/**
 * Stock API Contract Tests
 *
 * These tests validate the contract for Stock-related APIs only.
 * They run against the REAL backend (no mocks) to catch:
 * - Schema mismatches (field names, types)
 * - Date format inconsistencies
 * - Response structure changes
 * - Error response formats
 *
 * IMPORTANT: Backend must be running (./scripts/dc.sh up -d)
 */

import { test, expect } from '@playwright/test';
import { TEST_CONFIG } from './config';

const BACKEND_URL = TEST_CONFIG.BACKEND_URL;

test.describe('Stock API Contracts', () => {
  test.beforeAll(async () => {
    // Verify backend is running
    const response = await fetch(`${BACKEND_URL}/docs`);
    if (!response.ok) {
      throw new Error('Backend is not running. Start it with: ./scripts/dc.sh up -d');
    }
  });

  test('stock data API returns expected structure', async () => {
    const response = await fetch(`${BACKEND_URL}/api/v1/stocks/AAPL/prices?period=6mo`);

    expect(response.status).toBe(200);

    const data = await response.json();

    // Validate top-level structure
    expect(data).toHaveProperty('symbol');
    expect(data).toHaveProperty('data');
    expect(data).toHaveProperty('total_records');
    expect(data).toHaveProperty('start_date');
    expect(data).toHaveProperty('end_date');

    expect(data.symbol).toBe('AAPL');
    expect(Array.isArray(data.data)).toBe(true);
    expect(data.data.length).toBeGreaterThan(0);

    // Validate price data structure
    const firstPrice = data.data[0];
    expect(firstPrice).toHaveProperty('date');
    expect(firstPrice).toHaveProperty('open');
    expect(firstPrice).toHaveProperty('high');
    expect(firstPrice).toHaveProperty('low');
    expect(firstPrice).toHaveProperty('close');
    expect(firstPrice).toHaveProperty('volume');

    // Validate data types
    expect(typeof firstPrice.date).toBe('string');
    expect(typeof firstPrice.open).toBe('number');
    expect(typeof firstPrice.high).toBe('number');
    expect(typeof firstPrice.low).toBe('number');
    expect(typeof firstPrice.close).toBe('number');
    expect(typeof firstPrice.volume).toBe('number');

    // Validate date format (should be YYYY-MM-DD without time)
    expect(firstPrice.date).toMatch(/^\d{4}-\d{2}-\d{2}$/);

    // Verify NO indicator fields (prices endpoint should return OHLCV only)
    expect(firstPrice).not.toHaveProperty('ma_20');
    expect(firstPrice).not.toHaveProperty('cci');
    expect(firstPrice).not.toHaveProperty('cci_signal');
  });

  test('indicators API returns expected structure', async () => {
    const response = await fetch(`${BACKEND_URL}/api/v1/stocks/AAPL/indicators?period=6mo`);

    expect(response.status).toBe(200);

    const data = await response.json();

    // Validate top-level structure
    expect(data).toHaveProperty('symbol');
    expect(data).toHaveProperty('data');
    expect(data).toHaveProperty('indicators');
    expect(data.indicators).toContain('MA-20');

    expect(data.symbol).toBe('AAPL');
    expect(Array.isArray(data.data)).toBe(true);
    expect(data.data.length).toBeGreaterThan(0);

    // Validate indicator data structure
    const firstIndicator = data.data[0];
    expect(firstIndicator).toHaveProperty('date');
    expect(firstIndicator).toHaveProperty('ma_20');
    expect(firstIndicator).toHaveProperty('cci');
    expect(firstIndicator).toHaveProperty('cci_signal');

    // Validate date format (should be YYYY-MM-DD without time)
    expect(typeof firstIndicator.date).toBe('string');
    expect(firstIndicator.date).toMatch(/^\d{4}-\d{2}-\d{2}$/);

    // Find a data point with non-null values for type validation
    const indicatorWithData = data.data.find((d: { ma_20: number | null; cci: number | null }) => d.ma_20 !== null && d.cci !== null);
    if (indicatorWithData) {
      expect(typeof indicatorWithData.ma_20).toBe('number');
      expect(typeof indicatorWithData.cci).toBe('number');
      // cci_signal can be null or a string
      if (indicatorWithData.cci_signal !== null) {
        expect(typeof indicatorWithData.cci_signal).toBe('string');
        expect(['momentum_bullish', 'momentum_bearish', 'reversal_buy', 'reversal_sell']).toContain(indicatorWithData.cci_signal);
      }
    }
  });

  test('error responses have consistent structure', async () => {
    // Test error response for invalid symbol
    // Backend returns 503 (Service Unavailable) when external data provider
    // returns no data, since it can't distinguish between "symbol doesn't exist"
    // and "external service temporarily unavailable"
    const errorResponse = await fetch(`${BACKEND_URL}/api/v1/stocks/INVALID999/prices?period=6mo`);
    expect(errorResponse.status).toBe(503);

    const errorBody = await errorResponse.json();
    expect(errorBody).toHaveProperty('detail');
    expect(typeof errorBody.detail).toBe('string');
    expect(errorBody.detail).toContain('INVALID999'); // Error message should reference the symbol
  });

  test('stock data date range matches request parameters', async () => {
    const response = await fetch(`${BACKEND_URL}/api/v1/stocks/AAPL/prices?period=1mo`);
    expect(response.status).toBe(200);

    const data = await response.json();

    // Validate date range is approximately 1 month
    const firstDate = new Date(data.data[0].date);
    const lastDate = new Date(data.data[data.data.length - 1].date);

    const daysDiff = Math.floor((lastDate.getTime() - firstDate.getTime()) / (1000 * 60 * 60 * 24));

    // Should be roughly 30 days (allow some variance for weekends/holidays)
    expect(daysDiff).toBeGreaterThan(20);
    expect(daysDiff).toBeLessThan(40);
  });

});
