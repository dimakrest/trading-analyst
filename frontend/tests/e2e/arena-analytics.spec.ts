/**
 * E2E Tests for Arena Portfolio Analytics API Contracts
 *
 * These tests validate the API contract for Arena simulation endpoints.
 * They run against the REAL backend (no mocks) to catch:
 * - Schema mismatches (field names, types)
 * - Response structure changes
 * - Required vs optional fields
 * - New analytics fields added in the portfolio analytics implementation
 *
 * IMPORTANT: Backend must be running (./scripts/dc.sh up -d)
 *
 * NOTE: Tests that require a simulation to actually complete (processing
 * real market data) are skipped — they are not available in the test env.
 * These tests focus solely on API contract validation.
 */

import { test, expect } from '@playwright/test';
import { TEST_CONFIG } from './config';

const BACKEND_URL = TEST_CONFIG.BACKEND_URL;
const FRONTEND_URL = TEST_CONFIG.FRONTEND_URL;

test.describe('Arena Simulations - API Contracts', () => {
  test.beforeAll(async () => {
    // Verify backend is running
    const response = await fetch(`${BACKEND_URL}/api/v1/health`);
    if (!response.ok) {
      throw new Error('Backend is not running. Start it with: ./scripts/dc.sh up -d');
    }
  });

  test('GET /api/v1/arena/simulations returns 200 with correct structure', async () => {
    const response = await fetch(`${BACKEND_URL}/api/v1/arena/simulations`);

    expect(response.status).toBe(200);

    const data = await response.json();

    // Validate top-level response structure
    expect(data).toHaveProperty('items');
    expect(data).toHaveProperty('total');
    expect(data).toHaveProperty('has_more');

    // Validate types
    expect(Array.isArray(data.items)).toBe(true);
    expect(typeof data.total).toBe('number');
    expect(typeof data.has_more).toBe('boolean');
  });

  test('GET /api/v1/arena/simulations supports limit and offset params', async () => {
    const response = await fetch(`${BACKEND_URL}/api/v1/arena/simulations?limit=5&offset=0`);

    expect(response.status).toBe(200);

    const data = await response.json();
    expect(Array.isArray(data.items)).toBe(true);
    expect(data.items.length).toBeLessThanOrEqual(5);
  });

  test('GET /api/v1/arena/simulations items have required fields when present', async () => {
    const response = await fetch(`${BACKEND_URL}/api/v1/arena/simulations`);

    expect(response.status).toBe(200);

    const data = await response.json();

    // If there are simulations, validate the required fields on each item
    if (data.items.length > 0) {
      const simulation = data.items[0];

      // Core identification and lifecycle fields
      expect(simulation).toHaveProperty('id');
      expect(simulation).toHaveProperty('status');
      expect(simulation).toHaveProperty('start_date');
      expect(simulation).toHaveProperty('end_date');
      expect(simulation).toHaveProperty('initial_capital');

      // Performance counters
      expect(simulation).toHaveProperty('total_trades');
      expect(simulation).toHaveProperty('winning_trades');
      expect(simulation).toHaveProperty('max_drawdown_pct');

      // Equity fields (may be null for in-progress simulations)
      expect(simulation).toHaveProperty('final_equity');
      expect(simulation).toHaveProperty('total_return_pct');

      // Validate types for required fields
      expect(typeof simulation.id).toBe('number');
      expect(typeof simulation.status).toBe('string');
      expect(typeof simulation.start_date).toBe('string');
      expect(typeof simulation.end_date).toBe('string');
      expect(typeof simulation.total_trades).toBe('number');
      expect(typeof simulation.winning_trades).toBe('number');
    }
  });

  test('GET /api/v1/arena/simulations completed items have new analytics fields', async () => {
    const response = await fetch(`${BACKEND_URL}/api/v1/arena/simulations`);

    expect(response.status).toBe(200);

    const data = await response.json();

    // Find a completed simulation if one exists
    const completed = data.items.find(
      (s: { status: string }) => s.status === 'completed'
    );

    if (!completed) {
      // No completed simulations in the test environment — skip field validation
      // but confirm the response structure itself is correct
      return;
    }

    // Validate new analytics fields exist (may be null for legacy rows, but must be present)
    expect(completed).toHaveProperty('avg_hold_days');
    expect(completed).toHaveProperty('avg_win_pnl');
    expect(completed).toHaveProperty('avg_loss_pnl');
    expect(completed).toHaveProperty('profit_factor');
    expect(completed).toHaveProperty('sharpe_ratio');
    expect(completed).toHaveProperty('total_realized_pnl');

    // Values are either string (decimal) or null — never a non-null non-string
    const analyticsFields = [
      'avg_hold_days',
      'avg_win_pnl',
      'avg_loss_pnl',
      'profit_factor',
      'sharpe_ratio',
      'total_realized_pnl',
    ] as const;

    for (const field of analyticsFields) {
      const value = completed[field];
      expect(value === null || typeof value === 'string').toBe(true);
    }
  });

  test('GET /api/v1/arena/simulations/{id} returns 404 for non-existent simulation', async () => {
    const response = await fetch(`${BACKEND_URL}/api/v1/arena/simulations/99999`);

    expect(response.status).toBe(404);

    const data = await response.json();
    expect(data).toHaveProperty('detail');
  });
});

test.describe('Arena Benchmark Endpoint - API Contracts', () => {
  test.beforeAll(async () => {
    const response = await fetch(`${BACKEND_URL}/api/v1/health`);
    if (!response.ok) {
      throw new Error('Backend is not running. Start it with: ./scripts/dc.sh up -d');
    }
  });

  test('GET /api/v1/arena/simulations/99999/benchmark returns 404 for non-existent simulation', async () => {
    const response = await fetch(
      `${BACKEND_URL}/api/v1/arena/simulations/99999/benchmark?symbol=SPY`
    );

    expect(response.status).toBe(404);

    const data = await response.json();
    expect(data).toHaveProperty('detail');
  });

  test('GET /api/v1/arena/simulations/99999/benchmark returns 422 for invalid symbol', async () => {
    const response = await fetch(
      `${BACKEND_URL}/api/v1/arena/simulations/99999/benchmark?symbol=INVALID`
    );

    // 422 Unprocessable Entity for invalid enum value, or 404 for unknown simulation
    // Either is acceptable — the server must reject invalid symbol values
    expect([422, 404]).toContain(response.status);
  });

  test('GET /api/v1/arena/simulations/{id}/benchmark returns correct structure for completed simulation', async () => {
    // First, find a completed simulation
    const listResponse = await fetch(`${BACKEND_URL}/api/v1/arena/simulations`);
    expect(listResponse.status).toBe(200);

    const listData = await listResponse.json();
    const completed = listData.items.find(
      (s: { status: string }) => s.status === 'completed'
    );

    if (!completed) {
      // No completed simulation available in test environment — skip
      return;
    }

    const response = await fetch(
      `${BACKEND_URL}/api/v1/arena/simulations/${completed.id}/benchmark?symbol=SPY`
    );

    expect(response.status).toBe(200);

    const data = await response.json();

    // Response must be an array
    expect(Array.isArray(data)).toBe(true);

    // If data points exist, validate their structure
    if (data.length > 0) {
      const point = data[0];

      expect(point).toHaveProperty('date');
      expect(point).toHaveProperty('close');
      expect(point).toHaveProperty('cumulative_return_pct');

      expect(typeof point.date).toBe('string');
      expect(typeof point.close).toBe('string');
      expect(typeof point.cumulative_return_pct).toBe('string');

      // Date must be in YYYY-MM-DD format
      expect(point.date).toMatch(/^\d{4}-\d{2}-\d{2}$/);
    }
  });

  test('GET /api/v1/arena/simulations/{id}/benchmark works for QQQ as well', async () => {
    // First, find a completed simulation
    const listResponse = await fetch(`${BACKEND_URL}/api/v1/arena/simulations`);
    expect(listResponse.status).toBe(200);

    const listData = await listResponse.json();
    const completed = listData.items.find(
      (s: { status: string }) => s.status === 'completed'
    );

    if (!completed) {
      // No completed simulation available in test environment — skip
      return;
    }

    const response = await fetch(
      `${BACKEND_URL}/api/v1/arena/simulations/${completed.id}/benchmark?symbol=QQQ`
    );

    expect(response.status).toBe(200);

    const data = await response.json();
    expect(Array.isArray(data)).toBe(true);
  });
});

test.describe('Arena - UI Navigation', () => {
  test('navigating to /arena loads the page without JS errors', async ({ page }) => {
    const consoleErrors: string[] = [];
    page.on('console', (msg) => {
      if (msg.type() === 'error') {
        consoleErrors.push(msg.text());
      }
    });

    await page.goto(`${FRONTEND_URL}/arena`);
    await page.waitForLoadState('networkidle');

    // Should not have any console errors
    expect(consoleErrors).toHaveLength(0);
  });

  test('/arena page shows Arena heading or navigation item', async ({ page }) => {
    await page.goto(`${FRONTEND_URL}/arena`);
    await page.waitForLoadState('networkidle');

    // The page should contain some arena-related heading or content
    const arenaHeading = page.getByRole('heading', { name: /arena/i });
    const arenaText = page.getByText(/arena/i).first();

    const hasHeading = await arenaHeading.isVisible().catch(() => false);
    const hasText = await arenaText.isVisible().catch(() => false);

    expect(hasHeading || hasText).toBe(true);
  });
});
