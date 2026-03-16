/**
 * Alerts API Contract Tests
 *
 * Pure API tests — no browser navigation, just fetch() calls.
 * Runs under Playwright's test runner for consistent organisation
 * alongside the other E2E tests.
 *
 * Uses well-known liquid symbols (AAPL, MSFT, etc.) so that the backend's
 * Yahoo Finance price fetch succeeds during alert creation.
 * Created alert IDs are tracked and deleted in afterAll for cleanup.
 *
 * Valid MA periods: 20, 50, 150, 200 (anything else → 422).
 * Fibonacci levels are percentages: 38.2, 50.0, 61.8 etc.
 */

import { test, expect } from '@playwright/test';
import { TEST_CONFIG } from './config';

const BACKEND_URL = TEST_CONFIG.BACKEND_URL;
const ALERTS_URL = `${BACKEND_URL}/api/v1/alerts`;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** IDs of every alert created during this test run; cleaned up in afterAll. */
const createdAlertIds: number[] = [];

async function createFibAlert(symbol: string = 'AAPL') {
  const res = await fetch(`${ALERTS_URL}/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      symbol,
      alert_type: 'fibonacci',
      config: {
        levels: [38.2, 50.0],
        tolerance_pct: 0.5,
        min_swing_pct: 10.0,
      },
    }),
  });
  if (res.ok) {
    const data = await res.clone().json();
    if (Array.isArray(data)) {
      for (const alert of data as Array<{ id: number }>) {
        createdAlertIds.push(alert.id);
      }
    }
  }
  return res;
}

// ---------------------------------------------------------------------------
// Suite
// ---------------------------------------------------------------------------

test.describe('Alerts API Contracts', () => {
  test.beforeAll(async () => {
    const res = await fetch(`${BACKEND_URL}/docs`);
    if (!res.ok) {
      throw new Error('Backend is not running. Start it with: ./scripts/dc.sh up -d');
    }
  });

  test.afterAll(async () => {
    // Delete every alert that was created during this test run
    for (const id of createdAlertIds) {
      await fetch(`${ALERTS_URL}/${id}`, { method: 'DELETE' });
    }
  });

  // -------------------------------------------------------------------------
  // 1. GET /api/v1/alerts/ — list structure
  // -------------------------------------------------------------------------

  test('GET /api/v1/alerts/ returns 200 with items array and total number', async () => {
    const res = await fetch(`${ALERTS_URL}/`);

    expect(res.status).toBe(200);

    const data = await res.json();
    expect(Array.isArray(data.items)).toBe(true);
    expect(typeof data.total).toBe('number');
  });

  // -------------------------------------------------------------------------
  // 2. POST — create Fibonacci alert
  // -------------------------------------------------------------------------

  test('POST /api/v1/alerts/ creates Fibonacci alert with status 201', async () => {
    const res = await createFibAlert('AAPL');

    expect(res.status).toBe(201);

    const data = await res.json();
    expect(Array.isArray(data)).toBe(true);
    expect(data).toHaveLength(1);

    const alert = data[0];
    expect(typeof alert.id).toBe('number');
    expect(alert.symbol).toBe('AAPL');
    expect(alert.alert_type).toBe('fibonacci');
    expect(typeof alert.status).toBe('string');
    expect(alert.is_active).toBe(true);
    expect(alert.is_paused).toBe(false);
    expect(typeof alert.config).toBe('object');
    expect(alert.config).not.toBeNull();
    // computed_state may be null until first price check — just assert the key exists
    expect('computed_state' in alert).toBe(true);
    expect(typeof alert.created_at).toBe('string');
    expect(typeof alert.updated_at).toBe('string');
  });

  // -------------------------------------------------------------------------
  // 3. POST — MA fan-out creates one row per period
  // -------------------------------------------------------------------------

  test('POST /api/v1/alerts/ with moving_average fans out to one row per period', async () => {
    const res = await fetch(`${ALERTS_URL}/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        symbol: 'MSFT',
        alert_type: 'moving_average',
        config: {
          ma_periods: [50, 200],
          tolerance_pct: 0.5,
          direction: 'both',
        },
      }),
    });

    expect(res.status).toBe(201);

    const data = await res.json();
    expect(Array.isArray(data)).toBe(true);
    expect(data).toHaveLength(2);

    for (const alert of data as Array<{ id: number }>) {
      createdAlertIds.push(alert.id);
    }

    const periods = data.map((a: { config: { ma_period: number } }) => a.config.ma_period);
    expect(periods).toContain(50);
    expect(periods).toContain(200);
  });

  // -------------------------------------------------------------------------
  // 4. POST — invalid MA period returns 422
  // -------------------------------------------------------------------------

  test('POST /api/v1/alerts/ returns 422 for invalid MA period 100', async () => {
    const res = await fetch(`${ALERTS_URL}/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        symbol: 'AAPL',
        alert_type: 'moving_average',
        config: {
          ma_periods: [100],
          tolerance_pct: 0.5,
          direction: 'both',
        },
      }),
    });

    expect(res.status).toBe(422);
  });

  // -------------------------------------------------------------------------
  // 5. GET /api/v1/alerts/{id} — single alert with computed_state
  // -------------------------------------------------------------------------

  test('GET /api/v1/alerts/{id} returns single alert with required fields', async () => {
    const createRes = await createFibAlert('GOOGL');
    expect(createRes.status).toBe(201);
    const created = await createRes.json();
    const alertId: number = created[0].id;

    const res = await fetch(`${ALERTS_URL}/${alertId}`);

    expect(res.status).toBe(200);

    const alert = await res.json();
    expect(typeof alert.id).toBe('number');
    expect(typeof alert.symbol).toBe('string');
    expect(typeof alert.alert_type).toBe('string');
    expect(typeof alert.status).toBe('string');
    expect('computed_state' in alert).toBe(true);
  });

  // -------------------------------------------------------------------------
  // 6. GET non-existent alert → 404
  // -------------------------------------------------------------------------

  test('GET /api/v1/alerts/99999 returns 404 with detail field', async () => {
    const res = await fetch(`${ALERTS_URL}/99999`);

    expect(res.status).toBe(404);

    const data = await res.json();
    expect('detail' in data).toBe(true);
  });

  // -------------------------------------------------------------------------
  // 7. PATCH — toggle is_paused
  // -------------------------------------------------------------------------

  test('PATCH /api/v1/alerts/{id} toggles is_paused to true', async () => {
    const createRes = await createFibAlert('NVDA');
    expect(createRes.status).toBe(201);
    const created = await createRes.json();
    const alertId: number = created[0].id;

    const res = await fetch(`${ALERTS_URL}/${alertId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ is_paused: true }),
    });

    expect(res.status).toBe(200);

    const alert = await res.json();
    expect(alert.is_paused).toBe(true);
  });

  // -------------------------------------------------------------------------
  // 8. DELETE — soft-delete; subsequent GET returns 404
  // -------------------------------------------------------------------------

  test('DELETE /api/v1/alerts/{id} soft-deletes; GET afterwards returns 404', async () => {
    const createRes = await createFibAlert('TSLA');
    expect(createRes.status).toBe(201);
    const created = await createRes.json();
    const alertId: number = created[0].id;

    const deleteRes = await fetch(`${ALERTS_URL}/${alertId}`, { method: 'DELETE' });

    expect(deleteRes.status).toBe(200);

    const deleteData = await deleteRes.json();
    expect('deleted' in deleteData).toBe(true);

    // The alert should now be gone
    const getRes = await fetch(`${ALERTS_URL}/${alertId}`);
    expect(getRes.status).toBe(404);
  });

  // -------------------------------------------------------------------------
  // 9. GET /{id}/events — event history schema
  // -------------------------------------------------------------------------

  test('GET /api/v1/alerts/{id}/events returns an array; validates schema when non-empty', async () => {
    const createRes = await createFibAlert('AAPL');
    expect(createRes.status).toBe(201);
    const created = await createRes.json();
    const alertId: number = created[0].id;

    const res = await fetch(`${ALERTS_URL}/${alertId}/events`);

    expect(res.status).toBe(200);

    const data = await res.json();
    expect(Array.isArray(data)).toBe(true);

    if (data.length > 0) {
      const event = data[0];
      expect(typeof event.id).toBe('number');
      expect(typeof event.alert_id).toBe('number');
      expect(typeof event.event_type).toBe('string');
      expect(typeof event.new_status).toBe('string');
      expect(typeof event.price_at_event).toBe('number');
      expect(typeof event.created_at).toBe('string');
    }
  });

  // -------------------------------------------------------------------------
  // 10. GET /?status=no_structure — filter by status
  // -------------------------------------------------------------------------

  test('GET /api/v1/alerts/?status=no_structure returns only no_structure items', async () => {
    // New fibonacci alerts begin in no_structure status
    const createRes = await createFibAlert('MSFT');
    expect(createRes.status).toBe(201);

    const res = await fetch(`${ALERTS_URL}/?status=no_structure`);

    expect(res.status).toBe(200);

    const data = await res.json();
    expect(Array.isArray(data.items)).toBe(true);

    for (const item of data.items as Array<{ status: string }>) {
      expect(item.status).toBe('no_structure');
    }
  });

  // -------------------------------------------------------------------------
  // 11. GET /?alert_type=fibonacci — filter by type
  // -------------------------------------------------------------------------

  test('GET /api/v1/alerts/?alert_type=fibonacci returns only fibonacci alerts', async () => {
    const res = await fetch(`${ALERTS_URL}/?alert_type=fibonacci`);

    expect(res.status).toBe(200);

    const data = await res.json();
    expect(Array.isArray(data.items)).toBe(true);

    for (const item of data.items as Array<{ alert_type: string }>) {
      expect(item.alert_type).toBe('fibonacci');
    }
  });

  // -------------------------------------------------------------------------
  // 12. GET /?symbol=GOOGL — filter by exact symbol
  // -------------------------------------------------------------------------

  test('GET /api/v1/alerts/?symbol=GOOGL returns only matching symbol', async () => {
    // Create a GOOGL alert so there is at least one result to assert on
    const createRes = await createFibAlert('GOOGL');
    expect(createRes.status).toBe(201);

    const res = await fetch(`${ALERTS_URL}/?symbol=GOOGL`);

    expect(res.status).toBe(200);

    const data = await res.json();
    expect(Array.isArray(data.items)).toBe(true);
    expect(data.items.length).toBeGreaterThan(0);

    for (const item of data.items as Array<{ symbol: string }>) {
      expect(item.symbol).toBe('GOOGL');
    }
  });

  // -------------------------------------------------------------------------
  // 13. GET /{id}/events after soft-delete returns 404
  // -------------------------------------------------------------------------

  test('GET /api/v1/alerts/{id}/events returns 404 for soft-deleted alert', async () => {
    const createRes = await createFibAlert('AAPL');
    expect(createRes.status).toBe(201);
    const created = await createRes.json();
    const alertId: number = created[0].id;

    // Soft-delete first
    const deleteRes = await fetch(`${ALERTS_URL}/${alertId}`, { method: 'DELETE' });
    expect(deleteRes.status).toBe(200);

    // Events endpoint must also 404 for deleted alerts
    const eventsRes = await fetch(`${ALERTS_URL}/${alertId}/events`);
    expect(eventsRes.status).toBe(404);
  });

  // -------------------------------------------------------------------------
  // 14. GET /{id}/price-data — OHLCV with timestamp field
  // -------------------------------------------------------------------------

  test('GET /api/v1/alerts/{id}/price-data returns data array with OHLCV + timestamp', async () => {
    const createRes = await createFibAlert('AAPL');
    expect(createRes.status).toBe(201);
    const created = await createRes.json();
    const alertId: number = created[0].id;

    const res = await fetch(`${ALERTS_URL}/${alertId}/price-data`);

    expect(res.status).toBe(200);

    const body = await res.json();
    expect(Array.isArray(body.data)).toBe(true);

    if (body.data.length > 0) {
      const candle = body.data[0];
      expect(typeof candle.timestamp).toBe('string');
      expect(typeof candle.open).toBe('number');
      expect(typeof candle.high).toBe('number');
      expect(typeof candle.low).toBe('number');
      expect(typeof candle.close).toBe('number');
      expect(typeof candle.volume).toBe('number');
    }
  });
});
