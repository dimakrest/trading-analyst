# Stock Price Alerts -- E2E Test Plan

## Overview

End-to-end and UI test coverage for the stock price alerts feature. Tests validate the full user journey: creating alerts, viewing them in the dashboard, inspecting detail views with chart overlays, performing CRUD operations, filtering, responsive layout, and browser notification integration.

Two test categories:

- **UI tests** (`frontend/tests/ui/`) -- mocked backend via `page.route()`, fast, isolated, cover rendering and interaction logic.
- **E2E tests** (`frontend/tests/e2e/`) -- real backend, cover full-stack integration including API contracts, data persistence, and navigation.

## Current State

### Existing Test Infrastructure

- **Playwright config**: `frontend/playwright.config.ts` -- three projects: `ui` (mock, 30s timeout), `e2e` (real backend, 60s timeout), `responsive` (real backend, 60s timeout). Ports from `.env.dev`.
- **E2E config**: `frontend/tests/e2e/config.ts` -- exports `TEST_CONFIG.FRONTEND_URL` and `TEST_CONFIG.BACKEND_URL`.
- **Page Object Model**: `frontend/tests/pages/StockAnalysisPage.ts` -- accessibility-first selectors, action methods, state queries.
- **Mock fixtures**: `frontend/tests/fixtures/mockStockData.ts` -- OHLCV data, indicator data, error/empty responses.
- **Existing UI tests**: `tests/ui/arena-analytics.spec.ts` (route mocking, `setupMocks` helper, scoped assertions), `tests/ui/stock-search.spec.ts` (POM usage), `tests/ui/navigation.spec.ts` (responsive nav, aria attributes), `tests/ui/error-handling.spec.ts` (error/loading states).
- **Existing E2E tests**: `tests/e2e/stock-lists.spec.ts` (CRUD via API seeding, cleanup with prefix convention, dialog interactions), `tests/e2e/arena-analytics.spec.ts` (API contract validation, conditional skip for missing data).
- **Responsive tests**: `tests/responsive/stock-analysis.spec.ts` (viewport switching, horizontal scroll check).
- **Testing guide**: `docs/guides/testing.md` -- AAA pattern, accessible queries, 100% pass rate required.

### Key Frontend Selectors (from researcher)

| Element | Selector |
|---------|----------|
| Dashboard heading | `page.getByRole('heading', { name: 'Alerts' })` |
| Add Alert button | `page.getByRole('button', { name: 'Add Alert' })` |
| Dialog | `page.getByRole('dialog')` |
| Symbol input | `page.locator('#alert-symbol')` |
| Fibonacci type toggle | `page.getByRole('button', { name: 'Fibonacci retracement alert' })` |
| MA type toggle | `page.getByRole('button', { name: 'Moving average alert' })` |
| Fib level checkbox | `page.getByRole('checkbox', { name: '38.2%' })` |
| MA period checkbox | `page.getByRole('checkbox', { name: 'MA200' })` |
| Submit (in dialog) | `page.getByRole('button', { name: 'Add Alert' })` (scoped to dialog) |
| Table row | `page.getByRole('button', { name: /View details for AAPL/ })` |
| Back button (detail) | `page.getByRole('button', { name: 'Back to alerts' })` |
| Pause/Resume | `page.getByRole('button', { name: /Pause alert\|Resume alert/ })` |
| Delete button | `page.getByRole('button', { name: 'Delete alert' })` |
| Chart container | `page.getByTestId('candlestick-chart')` |
| Filter type combobox | `page.getByRole('combobox', { name: /type/i })` (requires `aria-label="Filter by type"` on element) |
| Filter status combobox | `page.getByRole('combobox', { name: /status/i })` (requires `aria-label="Filter by status"` on element) |
| Notification banner | `page.locator('[role="status"]')` containing bell/notification text |

### Backend API Endpoints

| Method | Path | Notes |
|--------|------|-------|
| POST | `/api/v1/alerts/` | Creates alert(s). MA fan-out: one row per period. Returns `list[AlertResponse]` (201). |
| GET | `/api/v1/alerts/` | List alerts. Query params: `status`, `alert_type`, `symbol`. Returns `AlertListResponse`. |
| GET | `/api/v1/alerts/{alert_id}` | Single alert with computed_state. 404 if not found/deleted. |
| PATCH | `/api/v1/alerts/{alert_id}` | Update config or `is_paused`. |
| DELETE | `/api/v1/alerts/{alert_id}` | Soft-delete. Returns `{"deleted": id}`. |
| GET | `/api/v1/alerts/{alert_id}/events` | Event history, newest first. |
| GET | `/api/v1/alerts/{alert_id}/price-data?days=365` | OHLCV data for chart. |

### Backend OHLCV Field Name

The backend serializes price data with `timestamp` (not `date`) as the key field. See `backend/app/api/v1/alerts.py:373`. All mock price data and assertions must use `timestamp`.

## What We're Testing

1. **Alerts Dashboard** -- rendering, empty/loading/error states, table and card layouts, filtering, sorting, status badges for ALL statuses (7 Fibonacci + 5 MA), navigation to detail view, `computed_state: null` graceful rendering.
2. **Create Alert Dialog** -- form validation, Fibonacci and MA creation flows, zero-level error, dialog lifecycle.
3. **Alert Detail View** -- chart rendering, info panel content (Fibonacci and MA), back navigation, pause/resume, delete with confirmation.
4. **CRUD Operations (E2E)** -- full lifecycle against real backend: create, list, pause, resume, delete. Uses dedicated `E2ETST` symbol prefix for isolation.
5. **API Contract Validation (E2E)** -- response schema, status codes, field types, query parameter filtering.
6. **Responsive Layout** -- desktop table vs mobile cards, navigation access, no horizontal scroll.
7. **Notification Banners** -- permission state banners on dashboard.

## What We're NOT Testing

- **Browser Notification API firing**: Playwright cannot intercept the `Notification` constructor or `Notification.requestPermission()` in a meaningful way. Browser notification delivery is tested via unit tests on `useNotifications` hook. The E2E plan covers the **toast fallback** and **notification permission banners** which are DOM-observable.
- **Alert monitor service execution**: The background polling service is backend-only. Its behavior is covered by backend unit tests (`test_alert_monitor.py`). E2E tests verify the computed_state is present after creation (initial computation), not that the monitor runs on interval.
- **Real market data fetching**: E2E tests use the backend with `MockMarketDataProvider`. No Yahoo Finance calls.
- **Chart canvas internals**: TradingView Lightweight Charts renders to canvas. Tests verify the chart container and canvas element exist, not pixel-level content.
- **Service worker / push notifications**: Not in v1 scope.
- **Notification click navigation**: The `pushState` + `popstate` pattern cannot be reliably tested in Playwright without a service worker. Covered by unit tests.
- **Invalid symbol in E2E**: `MockMarketDataProvider` accepts any symbol string and generates fake data -- it never raises `SymbolNotFoundError`. The 400-on-invalid-symbol path is covered by (a) UI test `alerts-create.spec.ts` test #5 (mocked 400) and (b) backend integration test `test_create_alert_invalid_symbol`.
- **Duplicate alert creation**: The backend has no unique constraint on symbol + alert_type. Duplicate creation returns 201. No error to test.

## Implementation

### Implementation Prerequisites

These changes are required in the feature implementation (not in test files) to support testability:

1. **Filter combobox aria-labels** (`frontend/src/components/alerts/AlertFilters.tsx`): The two `<Select>` combobox elements must have `aria-label="Filter by type"` and `aria-label="Filter by status"` respectively. Without these, test selectors would rely on positional indexing (`getByRole('combobox').first()`) which breaks silently on DOM reorder.

2. **Navigation test update** (`frontend/tests/ui/navigation.spec.ts`): The existing nav link count assertion must be updated when the Alerts nav item is added. Adding `/alerts` as NAV_ITEMS[5] increases the count from 5 to 6. Replace the count assertion with: `await expect(page.getByRole('link', { name: 'Alerts' })).toBeVisible()` to verify the new link exists without hardcoding a count.

### New Files

| File | Type | Purpose |
|------|------|---------|
| `frontend/tests/fixtures/mockAlertData.ts` | Fixture | Mock alert objects for UI tests |
| `frontend/tests/pages/AlertsPage.ts` | Page Object | Locators and actions for alerts dashboard |
| `frontend/tests/pages/AlertDetailPage.ts` | Page Object | Locators and actions for alert detail view |
| `frontend/tests/ui/alerts-dashboard.spec.ts` | UI Test | Dashboard rendering, states, filters, badges |
| `frontend/tests/ui/alerts-create.spec.ts` | UI Test | Create alert dialog flows |
| `frontend/tests/ui/alerts-detail.spec.ts` | UI Test | Detail view rendering for both alert types |
| `frontend/tests/e2e/alerts-crud.spec.ts` | E2E Test | Full CRUD lifecycle against real backend |
| `frontend/tests/e2e/alerts-api-contracts.spec.ts` | E2E Test | API schema and status code validation |
| `frontend/tests/ui/alerts-responsive.spec.ts` | UI Test | Desktop table vs mobile card layout |

### Files to Modify

| File | Change |
|------|--------|
| `frontend/tests/ui/navigation.spec.ts` | Update nav link count assertion to account for new Alerts nav item (5 -> 6), or replace with `getByRole('link', { name: 'Alerts' })` visibility check |
| `frontend/src/components/alerts/AlertFilters.tsx` | Add `aria-label="Filter by type"` and `aria-label="Filter by status"` to the two `<Select>` elements |

### File 1: `frontend/tests/fixtures/mockAlertData.ts`

Mock data objects matching the backend `AlertResponse` schema. Covers all 7 Fibonacci statuses and all 5 MA statuses.

```typescript
// --- Fibonacci alerts: all 7 statuses ---

// no_structure -- no valid swing detected yet
export const mockFibNoStructureAlert = {
  id: 10,
  symbol: 'META',
  alert_type: 'fibonacci',
  status: 'no_structure',
  is_active: true,
  is_paused: false,
  config: { levels: [38.2, 50.0, 61.8], tolerance_pct: 0.5, min_swing_pct: 10.0 },
  computed_state: null,
  last_triggered_at: null,
  created_at: '2026-03-15T12:00:00Z',
  updated_at: '2026-03-15T12:00:00Z',
};

// rallying -- price making new highs, no confirmed swing high yet
export const mockFibRallyingAlert = {
  id: 11,
  symbol: 'CRM',
  alert_type: 'fibonacci',
  status: 'rallying',
  is_active: true,
  is_paused: false,
  config: { levels: [38.2, 50.0, 61.8], tolerance_pct: 0.5, min_swing_pct: 10.0 },
  computed_state: {
    swing_high: 320.0,
    swing_low: 280.0,
    swing_high_date: '2026-03-14',
    swing_low_date: '2026-02-20',
    trend_direction: 'uptrend',
    current_price: 325.00,
    retracement_pct: 0.0,
    fib_levels: {
      '38.2': { price: 304.72, status: 'pending', triggered_at: null },
      '50.0': { price: 300.00, status: 'pending', triggered_at: null },
      '61.8': { price: 295.28, status: 'pending', triggered_at: null },
    },
    next_level: { pct: 38.2, price: 304.72 },
  },
  last_triggered_at: null,
  created_at: '2026-03-10T08:00:00Z',
  updated_at: '2026-03-15T08:00:00Z',
};

// pullback_started -- swing high confirmed, price pulling back but above 23.6%
export const mockFibPullbackStartedAlert = {
  id: 12,
  symbol: 'AMD',
  alert_type: 'fibonacci',
  status: 'pullback_started',
  is_active: true,
  is_paused: false,
  config: { levels: [38.2, 50.0, 61.8], tolerance_pct: 0.5, min_swing_pct: 10.0 },
  computed_state: {
    swing_high: 180.0,
    swing_low: 150.0,
    swing_high_date: '2026-03-05',
    swing_low_date: '2026-02-10',
    trend_direction: 'uptrend',
    current_price: 176.00,
    retracement_pct: 13.3,
    fib_levels: {
      '38.2': { price: 168.54, status: 'pending', triggered_at: null },
      '50.0': { price: 165.00, status: 'pending', triggered_at: null },
      '61.8': { price: 161.46, status: 'pending', triggered_at: null },
    },
    next_level: { pct: 38.2, price: 168.54 },
  },
  last_triggered_at: null,
  created_at: '2026-03-06T10:00:00Z',
  updated_at: '2026-03-15T08:00:00Z',
};

// retracing -- price between 23.6% and 78.6%
export const mockFibAlert = {
  id: 1,
  symbol: 'AAPL',
  alert_type: 'fibonacci',
  status: 'retracing',
  is_active: true,
  is_paused: false,
  config: { levels: [38.2, 50.0, 61.8], tolerance_pct: 0.5, min_swing_pct: 10.0 },
  computed_state: {
    swing_high: 140.0,
    swing_low: 110.0,
    swing_high_date: '2026-03-01',
    swing_low_date: '2026-02-15',
    trend_direction: 'uptrend',
    current_price: 128.50,
    retracement_pct: 38.3,
    fib_levels: {
      '38.2': { price: 128.54, status: 'active', triggered_at: null },
      '50.0': { price: 125.00, status: 'pending', triggered_at: null },
      '61.8': { price: 121.46, status: 'pending', triggered_at: null },
    },
    next_level: { pct: 50.0, price: 125.00 },
  },
  last_triggered_at: null,
  created_at: '2026-03-10T10:00:00Z',
  updated_at: '2026-03-15T08:00:00Z',
};

// at_level -- price within tolerance of a Fibonacci level (actionable)
export const mockFibAtLevelAlert = {
  id: 3,
  symbol: 'MSFT',
  alert_type: 'fibonacci',
  status: 'at_level',
  is_active: true,
  is_paused: false,
  config: { levels: [38.2, 50.0, 61.8], tolerance_pct: 0.5, min_swing_pct: 10.0 },
  computed_state: {
    swing_high: 420.0,
    swing_low: 370.0,
    swing_high_date: '2026-02-20',
    swing_low_date: '2026-01-15',
    trend_direction: 'uptrend',
    current_price: 400.90,
    retracement_pct: 38.2,
    fib_levels: {
      '38.2': { price: 400.90, status: 'active', triggered_at: null },
      '50.0': { price: 395.00, status: 'pending', triggered_at: null },
      '61.8': { price: 389.10, status: 'pending', triggered_at: null },
    },
    next_level: { pct: 50.0, price: 395.00 },
  },
  last_triggered_at: '2026-03-14T16:30:00Z',
  created_at: '2026-03-08T09:00:00Z',
  updated_at: '2026-03-15T08:00:00Z',
};

// bouncing -- price touched level and moving back toward trend
export const mockFibBouncingAlert = {
  id: 13,
  symbol: 'NFLX',
  alert_type: 'fibonacci',
  status: 'bouncing',
  is_active: true,
  is_paused: false,
  config: { levels: [38.2, 50.0, 61.8], tolerance_pct: 0.5, min_swing_pct: 10.0 },
  computed_state: {
    swing_high: 700.0,
    swing_low: 600.0,
    swing_high_date: '2026-02-28',
    swing_low_date: '2026-01-20',
    trend_direction: 'uptrend',
    current_price: 668.00,
    retracement_pct: 32.0,
    fib_levels: {
      '38.2': { price: 661.80, status: 'triggered', triggered_at: '2026-03-10T14:00:00Z' },
      '50.0': { price: 650.00, status: 'pending', triggered_at: null },
      '61.8': { price: 638.20, status: 'pending', triggered_at: null },
    },
    next_level: { pct: 50.0, price: 650.00 },
  },
  last_triggered_at: '2026-03-10T14:00:00Z',
  created_at: '2026-03-01T09:00:00Z',
  updated_at: '2026-03-15T08:00:00Z',
};

// invalidated -- price broke below swing low
export const mockInvalidatedAlert = {
  id: 6,
  symbol: 'AMZN',
  alert_type: 'fibonacci',
  status: 'invalidated',
  is_active: true,
  is_paused: false,
  config: { levels: [38.2, 50.0, 61.8], tolerance_pct: 0.5, min_swing_pct: 10.0 },
  computed_state: {
    swing_high: 200.0,
    swing_low: 175.0,
    swing_high_date: '2026-02-01',
    swing_low_date: '2026-01-10',
    trend_direction: 'uptrend',
    current_price: 170.00,
    retracement_pct: 120.0,
    fib_levels: {
      '38.2': { price: 190.45, status: 'triggered', triggered_at: '2026-02-20T14:00:00Z' },
      '50.0': { price: 187.50, status: 'triggered', triggered_at: '2026-02-25T10:00:00Z' },
      '61.8': { price: 184.55, status: 'triggered', triggered_at: '2026-03-01T09:00:00Z' },
    },
    next_level: null,
  },
  last_triggered_at: '2026-03-05T11:00:00Z',
  created_at: '2026-02-01T08:00:00Z',
  updated_at: '2026-03-15T08:00:00Z',
};

// --- MA alerts: all 5 statuses ---

// above_ma
export const mockMAAboveAlert = {
  id: 14,
  symbol: 'COST',
  alert_type: 'moving_average',
  status: 'above_ma',
  is_active: true,
  is_paused: false,
  config: { ma_period: 50, tolerance_pct: 0.5, direction: 'both' },
  computed_state: {
    ma_value: 900.00,
    ma_period: 50,
    current_price: 940.00,
    distance_pct: 4.4,
    ma_slope: 'rising',
  },
  last_triggered_at: null,
  created_at: '2026-03-12T10:00:00Z',
  updated_at: '2026-03-15T08:00:00Z',
};

// approaching
export const mockMAAlert = {
  id: 2,
  symbol: 'NVDA',
  alert_type: 'moving_average',
  status: 'approaching',
  is_active: true,
  is_paused: false,
  config: { ma_period: 200, tolerance_pct: 0.5, direction: 'both' },
  computed_state: {
    ma_value: 125.50,
    ma_period: 200,
    current_price: 128.00,
    distance_pct: 2.0,
    ma_slope: 'rising',
  },
  last_triggered_at: null,
  created_at: '2026-03-12T14:00:00Z',
  updated_at: '2026-03-15T08:00:00Z',
};

// at_ma (actionable)
export const mockMAAtMAAlert = {
  id: 4,
  symbol: 'GOOGL',
  alert_type: 'moving_average',
  status: 'at_ma',
  is_active: true,
  is_paused: false,
  config: { ma_period: 50, tolerance_pct: 0.5, direction: 'both' },
  computed_state: {
    ma_value: 175.20,
    ma_period: 50,
    current_price: 175.50,
    distance_pct: 0.17,
    ma_slope: 'rising',
  },
  last_triggered_at: '2026-03-15T07:00:00Z',
  created_at: '2026-03-05T11:00:00Z',
  updated_at: '2026-03-15T08:00:00Z',
};

// below_ma
export const mockMABelowMAAlert = {
  id: 15,
  symbol: 'INTC',
  alert_type: 'moving_average',
  status: 'below_ma',
  is_active: true,
  is_paused: false,
  config: { ma_period: 200, tolerance_pct: 0.5, direction: 'both' },
  computed_state: {
    ma_value: 32.00,
    ma_period: 200,
    current_price: 28.50,
    distance_pct: -10.9,
    ma_slope: 'falling',
  },
  last_triggered_at: null,
  created_at: '2026-03-11T09:00:00Z',
  updated_at: '2026-03-15T08:00:00Z',
};

// insufficient_data
export const mockInsufficientDataAlert = {
  id: 7,
  symbol: 'IPO',
  alert_type: 'moving_average',
  status: 'insufficient_data',
  is_active: true,
  is_paused: false,
  config: { ma_period: 200, tolerance_pct: 0.5, direction: 'both' },
  computed_state: { error: 'Insufficient price history for MA200 (need 205 candles, have 45)' },
  last_triggered_at: null,
  created_at: '2026-03-14T10:00:00Z',
  updated_at: '2026-03-15T08:00:00Z',
};

// --- Special states ---

// Paused alert (computed_state: null -- tests graceful rendering of Details column)
export const mockPausedAlert = {
  id: 5,
  symbol: 'TSLA',
  alert_type: 'fibonacci',
  status: 'retracing',
  is_active: true,
  is_paused: true,
  config: { levels: [50.0, 61.8], tolerance_pct: 0.5, min_swing_pct: 10.0 },
  computed_state: null,
  last_triggered_at: null,
  created_at: '2026-03-01T12:00:00Z',
  updated_at: '2026-03-10T15:00:00Z',
};

// --- Aggregate lists ---

// Full alert list for dashboard (all 12 statuses + paused)
export const mockAlertList = {
  items: [
    mockFibNoStructureAlert,
    mockFibRallyingAlert,
    mockFibPullbackStartedAlert,
    mockFibAlert,
    mockFibAtLevelAlert,
    mockFibBouncingAlert,
    mockInvalidatedAlert,
    mockMAAboveAlert,
    mockMAAlert,
    mockMAAtMAAlert,
    mockMABelowMAAlert,
    mockInsufficientDataAlert,
    mockPausedAlert,
  ],
  total: 13,
};

// Empty list
export const mockEmptyAlertList = { items: [], total: 0 };

// --- Alert events for detail view ---

export const mockAlertEvents = [
  {
    id: 10,
    alert_id: 3,
    event_type: 'level_hit',
    previous_status: 'retracing',
    new_status: 'at_level',
    price_at_event: 400.90,
    details: { level_pct: 38.2, level_price: 400.90 },
    created_at: '2026-03-14T16:30:00Z',
  },
  {
    id: 9,
    alert_id: 3,
    event_type: 'status_change',
    previous_status: 'pullback_started',
    new_status: 'retracing',
    price_at_event: 410.00,
    details: null,
    created_at: '2026-03-12T09:00:00Z',
  },
];

// --- Mock price data for chart (minimal -- 5 candles) ---
// NOTE: Backend uses `timestamp` field (not `date`). See backend/app/api/v1/alerts.py:373.

export const mockAlertPriceData = {
  symbol: 'MSFT',
  alert_id: 3,
  data: [
    { timestamp: '2026-03-10T00:00:00', open: 415.0, high: 418.0, low: 412.0, close: 414.0, volume: 30000000 },
    { timestamp: '2026-03-11T00:00:00', open: 414.0, high: 416.0, low: 408.0, close: 410.0, volume: 32000000 },
    { timestamp: '2026-03-12T00:00:00', open: 410.0, high: 412.0, low: 405.0, close: 407.0, volume: 35000000 },
    { timestamp: '2026-03-13T00:00:00', open: 407.0, high: 409.0, low: 402.0, close: 403.0, volume: 33000000 },
    { timestamp: '2026-03-14T00:00:00', open: 403.0, high: 404.0, low: 399.0, close: 400.90, volume: 38000000 },
  ],
  days: 365,
};

// --- Created alert responses (from POST) ---

export const mockCreatedFibResponse = [
  {
    id: 100,
    symbol: 'AAPL',
    alert_type: 'fibonacci',
    status: 'no_structure',
    is_active: true,
    is_paused: false,
    config: { levels: [38.2, 50.0, 61.8], tolerance_pct: 0.5, min_swing_pct: 10.0 },
    computed_state: null,
    last_triggered_at: null,
    created_at: '2026-03-15T12:00:00Z',
    updated_at: '2026-03-15T12:00:00Z',
  },
];

export const mockCreatedMAResponse = [
  {
    id: 101,
    symbol: 'NVDA',
    alert_type: 'moving_average',
    status: 'above_ma',
    is_active: true,
    is_paused: false,
    config: { ma_period: 50, tolerance_pct: 0.5, direction: 'both' },
    computed_state: null,
    last_triggered_at: null,
    created_at: '2026-03-15T12:00:00Z',
    updated_at: '2026-03-15T12:00:00Z',
  },
  {
    id: 102,
    symbol: 'NVDA',
    alert_type: 'moving_average',
    status: 'above_ma',
    is_active: true,
    is_paused: false,
    config: { ma_period: 200, tolerance_pct: 0.5, direction: 'both' },
    computed_state: null,
    last_triggered_at: null,
    created_at: '2026-03-15T12:00:00Z',
    updated_at: '2026-03-15T12:00:00Z',
  },
];
```

### File 2: `frontend/tests/pages/AlertsPage.ts`

Page Object for the alerts dashboard.

```typescript
import { Page, Locator } from '@playwright/test';

export class AlertsPage {
  readonly page: Page;
  readonly heading: Locator;
  readonly addAlertButton: Locator;
  readonly alertsTable: Locator;
  readonly emptyState: Locator;
  readonly loadingSkeleton: Locator;
  readonly errorState: Locator;
  readonly retryButton: Locator;
  readonly filterTypeCombobox: Locator;
  readonly filterStatusCombobox: Locator;
  readonly alertCountLabel: Locator;
  readonly emptyFilterState: Locator;

  constructor(page: Page) {
    this.page = page;
    this.heading = page.getByRole('heading', { name: 'Alerts' });
    this.addAlertButton = page.getByRole('button', { name: 'Add Alert' });
    this.alertsTable = page.locator('table');
    this.emptyState = page.getByText('No alerts configured');
    this.loadingSkeleton = page.locator('[data-slot="skeleton"]').first();
    this.errorState = page.getByText('Failed to load alerts');
    this.retryButton = page.getByRole('button', { name: /retry/i });
    this.filterTypeCombobox = page.getByRole('combobox', { name: /type/i });
    this.filterStatusCombobox = page.getByRole('combobox', { name: /status/i });
    this.alertCountLabel = page.getByText(/\d+ of \d+ alert/);
    this.emptyFilterState = page.getByText('No alerts match the current filters');
  }

  async goto() {
    await this.page.goto('/alerts');
    await this.heading.waitFor({ state: 'visible' });
  }

  async clickAddAlert() {
    await this.addAlertButton.click();
  }

  async getAlertRow(symbol: string) {
    return this.page.getByRole('button', { name: new RegExp(`View details for ${symbol}`) });
  }

  async navigateToDetail(symbol: string) {
    const row = await this.getAlertRow(symbol);
    await row.click();
  }

  async filterByType(type: string) {
    await this.filterTypeCombobox.click();
    await this.page.getByRole('option', { name: new RegExp(type, 'i') }).click();
  }

  async filterByStatus(status: string) {
    await this.filterStatusCombobox.click();
    await this.page.getByRole('option', { name: new RegExp(status, 'i') }).click();
  }
}
```

### File 3: `frontend/tests/pages/AlertDetailPage.ts`

Page Object for alert detail view.

```typescript
import { Page, Locator } from '@playwright/test';

export class AlertDetailPage {
  readonly page: Page;
  readonly backButton: Locator;
  readonly symbolHeading: Locator;
  readonly pauseButton: Locator;
  readonly resumeButton: Locator;
  readonly deleteButton: Locator;
  readonly chart: Locator;
  readonly loadingSkeleton: Locator;
  readonly errorState: Locator;
  readonly notFoundState: Locator;
  readonly retryButton: Locator;

  constructor(page: Page) {
    this.page = page;
    this.backButton = page.getByRole('button', { name: 'Back to alerts' });
    this.symbolHeading = page.getByRole('heading', { level: 1 });
    this.pauseButton = page.getByRole('button', { name: 'Pause alert' });
    this.resumeButton = page.getByRole('button', { name: 'Resume alert' });
    this.deleteButton = page.getByRole('button', { name: 'Delete alert' });
    this.chart = page.getByTestId('candlestick-chart');
    this.loadingSkeleton = page.locator('[data-slot="skeleton"]').first();
    this.errorState = page.getByRole('alert');
    this.notFoundState = page.getByText('Alert not found');
    this.retryButton = page.getByRole('button', { name: /retry/i });
  }

  async goto(alertId: number) {
    await this.page.goto(`/alerts/${alertId}`);
    await this.symbolHeading.waitFor({ state: 'visible' });
  }

  async clickBack() {
    await this.backButton.click();
  }

  async clickDelete() {
    await this.deleteButton.click();
  }

  async confirmDelete() {
    await this.page.getByRole('alertdialog').getByRole('button', { name: 'Delete' }).click();
  }
}
```

---

### File 4: `frontend/tests/ui/alerts-dashboard.spec.ts`

**Mocked backend. 24 tests.**

```
test.describe('Alerts Dashboard - Page States')
  1. renders loading skeletons before data arrives
     - Mock GET /api/v1/alerts/ with 2s delay
     - Navigate to /alerts
     - Assert skeleton visible
     - Assert table NOT visible

  2. renders empty state when no alerts exist
     - Mock GET /api/v1/alerts/ returning mockEmptyAlertList
     - Navigate to /alerts
     - Assert "No alerts configured" visible
     - Assert "Add Alert" button visible in empty state card

  3. renders error state when API fails
     - Mock GET /api/v1/alerts/ to return 500
     - Navigate to /alerts
     - Assert "Failed to load alerts" visible
     - Assert retry button visible

  4. retrying after error re-fetches alerts
     - Mock GET /api/v1/alerts/ to return 500 first, then 200 with mockAlertList
     - Navigate, see error, click retry
     - Assert table visible with alert rows

  5. renders page heading and Add Alert button
     - Mock GET /api/v1/alerts/ returning mockAlertList
     - Navigate to /alerts
     - Assert h1 "Alerts" visible
     - Assert "Add Alert" button visible

  6. renders all alert rows in the table
     - Mock GET returning mockAlertList (13 alerts)
     - Navigate to /alerts
     - Assert 13 rows visible (one per alert)
     - Assert symbols visible: META, CRM, AMD, AAPL, MSFT, NFLX, AMZN, COST, NVDA, GOOGL, INTC, IPO, TSLA

  7. displays correct status badges for ALL Fibonacci statuses
     - Mock GET returning mockAlertList
     - Assert badge text:
       - META: "No Structure"
       - CRM: "Rallying"
       - AMD: "Pullback"
       - AAPL: "Retracing"
       - MSFT: "At Level"
       - NFLX: "Bouncing"
       - AMZN: "Invalidated"

  8. displays correct status badges for ALL MA statuses
     - Mock GET returning mockAlertList
     - Assert badge text:
       - COST: "Above MA"
       - NVDA: "Approaching"
       - GOOGL: "At MA"
       - INTC: "Below MA"
       - IPO: "No Data"

  9. at_level and at_ma badges have pulse animation
     - Mock GET returning mockAlertList
     - Find badge for MSFT (at_level) -- assert has class "animate-pulse"
     - Find badge for GOOGL (at_ma) -- assert has class "animate-pulse"

  10. displays Fibonacci details column (swing range, retracement, next level)
      - Mock GET returning mockAlertList
      - Assert AAPL row contains "$110" and "$140" (swing range), "38.3%" (retracement), "$125.00" (next level)

  11. displays MA details column (MA value, distance)
      - Assert NVDA row contains "MA200", "$125.50", "2.0%"

  12. computed_state: null renders gracefully in Details column
      - Assert TSLA row (paused, computed_state: null) is visible
      - Assert TSLA row does not throw -- renders some non-empty content or placeholder (e.g., dash)
      - Assert META row (no_structure, computed_state: null) also renders gracefully

  13. clicking a row navigates to detail view
      - Mock GET returning mockAlertList
      - Click AAPL row
      - Assert URL contains /alerts/1

  14. displays Last Alert timestamp for alerts with last_triggered_at
      - Assert MSFT row shows formatted timestamp from last_triggered_at '2026-03-14T16:30:00Z'

  15. displays Price column from computed_state.current_price
      - Assert AAPL row shows "$128.50" (from computed_state.current_price)

  16. page loads without console errors
      - Attach console error listener
      - Mock GET returning mockAlertList
      - Navigate, wait for heading visible
      - Assert 0 errors (filtering known nesting warnings)

test.describe('Alerts Dashboard - Filtering')
  17. filter by alert type shows only matching alerts
      - Mock GET returning mockAlertList
      - Navigate, select "Fibonacci" in type filter
      - Assert Fibonacci alerts visible (META, CRM, AMD, AAPL, MSFT, NFLX, AMZN, TSLA)
      - Assert MA alerts NOT visible (COST, NVDA, GOOGL, INTC, IPO)

  18. filter by status shows only matching alerts
      - Navigate, select a specific status (e.g., "Retracing")
      - Assert only AAPL and TSLA rows visible (both have status: retracing)

  19. combined type + status filter
      - Select "Fibonacci" type + "At Level" status
      - Assert only MSFT visible

  20. empty filter result shows message
      - Select filters that match nothing (e.g., "Moving Average" + "Invalidated")
      - Assert "No alerts match the current filters" visible

  21. alert count label updates with filter
      - No filter: "13 of 13 alerts"
      - After filtering to Fibonacci: assert count reflects 8 of 13

test.describe('Alerts Dashboard - Sorting')
  22. actionable statuses appear first in default sort
      - Mock GET returning mockAlertList
      - Assert first rows are at_level (MSFT) and at_ma (GOOGL) before non-actionable statuses

test.describe('Alerts Dashboard - Notification Banners')
  23. notification granted banner visible when permission is granted
      - Mock Notification.permission = 'granted' via page.addInitScript
      - Navigate to /alerts
      - Assert banner with "tab" text and role="status" visible

  24. notification denied banner visible when permission is denied
      - Mock Notification.permission = 'denied' via page.addInitScript
      - Navigate to /alerts
      - Assert denied banner visible
```

### File 5: `frontend/tests/ui/alerts-create.spec.ts`

**Mocked backend. 12 tests.**

All tests mock GET /api/v1/alerts/ returning mockAlertList for initial dashboard load.

```
test.describe('Create Alert Dialog - Fibonacci')
  1. opens dialog when clicking Add Alert
     - Navigate to /alerts, click "Add Alert"
     - Assert dialog visible with heading "Add Alert"
     - Assert symbol input visible
     - Assert Fibonacci type toggle selected by default (or first available)

  2. creates Fibonacci alert with default levels
     - Mock POST /api/v1/alerts/ returning mockCreatedFibResponse
     - Mock GET (after creation) returning updated list with new alert
     - Open dialog, fill symbol "AAPL", select Fibonacci type
     - Assert 38.2%, 50%, 61.8% checkboxes checked by default
     - Click "Add Alert" submit button
     - Assert dialog closes
     - Assert new AAPL row appears in table

  3. prevents submission when no symbol entered
     - Open dialog, leave symbol empty, click "Add Alert"
     - Assert error message visible in dialog (role="alert")

  4. prevents submission when zero Fibonacci levels selected
     - Open dialog, fill symbol "AAPL", select Fibonacci type
     - Uncheck all 3 default levels (38.2%, 50%, 61.8%)
     - Click "Add Alert"
     - Assert error message: /select at least one fibonacci level/i

  5. shows server error in dialog when API returns 400
     - Mock POST /api/v1/alerts/ returning 400 with { detail: 'Symbol not found' }
     - Open dialog, fill "INVALID", click submit
     - Assert error message visible in dialog

  6. cancel button closes dialog without API call
     - Open dialog, fill "AAPL"
     - Click "Cancel"
     - Assert dialog not visible
     - Assert no POST request made (verify via route handler call count)

test.describe('Create Alert Dialog - Moving Average')
  7. creates MA alert with selected periods
     - Mock POST returning mockCreatedMAResponse (2 alerts for MA50 + MA200)
     - Open dialog, fill "NVDA", select MA type toggle
     - Select MA50 and MA200 checkboxes
     - Click submit
     - Assert dialog closes

  8. prevents submission when zero MA periods selected
     - Open dialog, fill "NVDA", select MA type
     - Uncheck all MA period checkboxes
     - Click "Add Alert"
     - Assert error: /select at least one moving average/i

  9. MA direction selector defaults to "both"
     - Open dialog, select MA type
     - Assert direction select has value "both"

test.describe('Create Alert Dialog - Advanced Settings')
  10. advanced settings are collapsed by default
      - Open dialog
      - Assert tolerance input NOT visible
      - Assert "Advanced settings" toggle visible

  11. clicking advanced settings reveals tolerance input
      - Open dialog, click "Advanced settings"
      - Assert tolerance input visible with value "0.5"

  12. shows submitting state on button while creating
      - Mock POST with 1s delay
      - Open dialog, fill form, click submit
      - Assert button text changes to "Adding..."
```

### File 6: `frontend/tests/ui/alerts-detail.spec.ts`

**Mocked backend. 16 tests.**

```
test.describe('Alert Detail - Fibonacci')
  Setup: mock GET /api/v1/alerts/3 returning mockFibAtLevelAlert,
         mock GET /api/v1/alerts/3/events returning mockAlertEvents,
         mock GET /api/v1/alerts/3/price-data returning mockAlertPriceData

  1. renders page with symbol heading
     - Navigate to /alerts/3
     - Assert h1 contains "MSFT"

  2. renders breadcrumb navigation
     - Assert "Alerts" text visible (breadcrumb link)
     - Assert "MSFT" text visible (current breadcrumb)

  3. renders back button that navigates to dashboard
     - Click back button
     - Assert URL is /alerts

  4. renders chart container with canvas
     - Assert candlestick-chart testid visible
     - Assert canvas element attached (chart library rendered)

  5. renders Fibonacci info panel with swing range
     - Assert "Fibonacci Retracement" heading visible
     - Assert swing range text: "$370" and "$420" visible
     - Assert current price "$400.90" visible

  6. renders Fibonacci level table with status
     - Assert "38.2%" with price visible
     - Assert "50%" with price visible
     - Assert "61.8%" with price visible

  7. renders alert status badge
     - Assert "At Level" badge visible

  8. renders event history
     - Assert "Level Hit" event visible
     - Assert "Status Change" event visible
     - Assert events show prices and dates

  9. renders pause/resume button
     - Assert "Pause alert" button visible (since mockFibAtLevelAlert.is_paused is false)

  10. pause button sends PATCH and updates UI
      - Mock PATCH /api/v1/alerts/3 returning updated alert with is_paused: true
      - Mock GET (re-fetch) returning updated alert
      - Click "Pause alert"
      - Assert "Resume alert" button appears

  11. delete button opens confirmation dialog
      - Click "Delete alert"
      - Assert alertdialog visible with "Delete alert?" heading
      - Assert "Delete" and "Cancel" buttons visible

  12. confirming delete navigates back to dashboard
      - Mock DELETE /api/v1/alerts/3 returning { deleted: 3 }
      - Click delete, click confirm
      - Assert URL is /alerts

test.describe('Alert Detail - Moving Average')
  Setup: mock GET /api/v1/alerts/2 returning mockMAAlert,
         mock GET /api/v1/alerts/2/events returning [],
         mock GET /api/v1/alerts/2/price-data returning mock OHLCV data (with `timestamp` field)

  13. renders MA info panel with MA value and distance
      - Navigate to /alerts/2
      - Assert "MA200 Alert" heading visible
      - Assert "$125.50" (MA value) visible
      - Assert "2.0%" (distance) visible
      - Assert "Rising" (slope) visible

  14. renders empty event history message
      - Assert "No events recorded yet" visible

test.describe('Alert Detail - Error States')
  15. renders not found state for nonexistent alert
      - Mock GET /api/v1/alerts/999 returning 404
      - Navigate to /alerts/999
      - Assert "Alert not found" visible
      - Assert "Back to Alerts" button visible

  16. renders error state with retry on server error
      - Mock GET /api/v1/alerts/3 returning 500
      - Navigate to /alerts/3
      - Assert error alert component visible
      - Assert retry button visible
```

### File 7: `frontend/tests/e2e/alerts-crud.spec.ts`

**Real backend. 9 tests.**

All tests use the dedicated `E2ETST` symbol prefix for test isolation. `MockMarketDataProvider` accepts any symbol string. `test.beforeAll` verifies backend health. `test.beforeEach` cleans up: fetches all alerts, filters client-side for `item.symbol.startsWith('E2ET')`, DELETEs each match.

```
test.describe('Alerts E2E - CRUD Operations')
  beforeAll: verify backend is running (fetch BACKEND_URL/api/v1/health)
  beforeEach: clean up test alerts via API
    - GET /api/v1/alerts/
    - Filter items where symbol starts with "E2ET"
    - DELETE each matching alert

  1. can create a Fibonacci alert through the UI
     - Navigate to FRONTEND_URL/alerts
     - Click "Add Alert"
     - Fill symbol: "E2ETST1"
     - Select Fibonacci type
     - Leave default levels (38.2%, 50%, 61.8%)
     - Click submit
     - Assert dialog closes
     - Assert new alert row for E2ETST1 appears in table
     - Assert status badge visible (likely "No Structure")

  2. can create an MA alert through the UI
     - Navigate to /alerts
     - Click "Add Alert"
     - Fill symbol "E2ETST2"
     - Select MA type
     - Check MA50
     - Click submit
     - Assert dialog closes
     - Assert new MA50 alert row appears

  3. MA fan-out creates multiple rows for multiple periods
     - Navigate, open dialog
     - Fill symbol "E2ETST3", select MA type
     - Check MA50 and MA200
     - Submit
     - Assert TWO new alert rows appear (MA50 + MA200)

  4. can navigate from dashboard to alert detail view
     - Create alert via API: POST to BACKEND_URL/api/v1/alerts/ with symbol "E2ETST4"
     - Navigate to /alerts
     - Click the alert row
     - Assert URL contains /alerts/{id}
     - Assert symbol heading visible
     - Assert chart container visible
     - Assert "Fibonacci Retracement" label/heading visible (structural check)
     - NOTE: computed_state may be null for newly created alerts. Do NOT assert computed content (swing range, level prices). Assert structural elements only.

  5. can pause an alert from detail view
     - Create alert via API with symbol "E2ETST5"
     - Navigate to detail view
     - Click "Pause alert"
     - Assert "Resume alert" button appears
     - Verify via API: GET the alert, assert is_paused === true

  6. can resume a paused alert
     - Create alert via API with symbol "E2ETST6", then PATCH to pause it
     - Navigate to detail view
     - Assert "Resume alert" visible
     - Click "Resume alert"
     - Assert "Pause alert" appears
     - Verify via API: is_paused === false

  7. can delete an alert with confirmation
     - Create alert via API with symbol "E2ETST7"
     - Navigate to detail view
     - Click "Delete alert"
     - Assert confirmation dialog visible
     - Click "Delete" confirm button
     - Assert navigated back to /alerts
     - Assert deleted alert row NOT in table
     - Verify via API: GET returns 404 (immediate, no delay)

  8. alert detail shows chart container
     - Create Fibonacci alert via API with symbol "E2ETST8"
     - Navigate to detail view
     - Assert chart container visible
     - Assert canvas element attached (wait up to 10s)

  9. alert detail shows back navigation to dashboard
     - Create alert via API with symbol "E2ETST9"
     - Navigate to /alerts/{id}
     - Click back button
     - Assert URL is /alerts
     - Assert heading "Alerts" visible
```

### File 8: `frontend/tests/e2e/alerts-api-contracts.spec.ts`

**Real backend, direct API calls. 14 tests.**

All tests that create alerts use symbol prefix `E2ETST` and are cleaned up in `afterAll`.

```
test.describe('Alerts API Contracts')
  beforeAll: verify backend health
  afterAll: clean up all E2ETST alerts

  1. GET /api/v1/alerts/ returns 200 with correct structure
     - Fetch, assert status 200
     - Assert response has 'items' (array) and 'total' (number)

  2. POST /api/v1/alerts/ creates Fibonacci alert with 201
     - POST with { symbol: 'E2ETSTA', alert_type: 'fibonacci', config: { levels: [38.2, 50.0], tolerance_pct: 0.5, min_swing_pct: 10.0 } }
     - Assert status 201
     - Assert response is array with 1 item
     - Assert item has: id (number), symbol ('E2ETSTA'), alert_type ('fibonacci'), status (string), is_active (true), is_paused (false), config (object), computed_state, created_at, updated_at

  3. POST /api/v1/alerts/ with MA creates fan-out rows
     - POST with { symbol: 'E2ETSTB', alert_type: 'moving_average', config: { ma_periods: [50, 200], tolerance_pct: 0.5, direction: 'both' } }
     - Assert status 201
     - Assert response array has length 2
     - Assert items have ma_period 50 and 200 respectively in their config

  4. POST /api/v1/alerts/ returns 422 for invalid MA period
     - POST with symbol 'E2ETSTC', ma_periods: [100]
     - Assert status 422

  5. GET /api/v1/alerts/{id} returns single alert with computed_state
     - Create alert via POST with symbol 'E2ETSTD', get id from response
     - GET /api/v1/alerts/{id}
     - Assert status 200
     - Assert response has id, symbol, alert_type, status, computed_state

  6. GET /api/v1/alerts/99999 returns 404
     - Assert status 404, response has 'detail'

  7. PATCH /api/v1/alerts/{id} toggles is_paused
     - Create alert with symbol 'E2ETSTE', PATCH with { is_paused: true }
     - Assert status 200
     - Assert response.is_paused === true

  8. DELETE /api/v1/alerts/{id} soft-deletes
     - Create alert with symbol 'E2ETSTF', DELETE
     - Assert status 200
     - Assert response has 'deleted' field
     - GET same id returns 404

  9. GET /api/v1/alerts/{id}/events returns event history with correct schema
     - Create alert with symbol 'E2ETSTG', GET events
     - Assert status 200
     - Assert response is array
     - If data.length > 0: assert first item has id (number), alert_id (number),
       event_type (string), new_status (string), price_at_event (number), created_at (string)

  10. GET /api/v1/alerts/?status=no_structure filters by status
      - Create Fibonacci alert with symbol 'E2ETSTH' (will start as no_structure)
      - GET /api/v1/alerts/?status=no_structure
      - Assert response contains only items with status 'no_structure'

  11. GET /api/v1/alerts/?alert_type=fibonacci filters by type
      - GET /api/v1/alerts/?alert_type=fibonacci
      - Assert all returned items have alert_type 'fibonacci'

  12. GET /api/v1/alerts/?symbol=E2ETSTH filters by exact symbol
      - GET /api/v1/alerts/?symbol=E2ETSTH
      - Assert all returned items have symbol 'E2ETSTH'

  13. GET /api/v1/alerts/{id}/events returns 404 for soft-deleted alert
      - Create alert with symbol 'E2ETSTI', get id
      - DELETE the alert
      - GET /api/v1/alerts/{id}/events
      - Assert status 404

  14. GET /api/v1/alerts/{id}/price-data returns OHLCV data with timestamp field
      - Create alert with symbol 'E2ETSTJ', get id
      - GET /api/v1/alerts/{id}/price-data
      - Assert status 200
      - Assert response has 'data' array
      - If data.length > 0: assert first item has 'timestamp' (string), 'open' (number),
        'high' (number), 'low' (number), 'close' (number), 'volume' (number)
```

### File 9: `frontend/tests/ui/alerts-responsive.spec.ts`

**Mocked backend. 8 tests.**

```
test.describe('Alerts Responsive - Mobile (375x667)')
  test.use({ viewport: { width: 375, height: 667 } })

  Setup: mock GET /api/v1/alerts/ returning mockAlertList

  1. dashboard renders card layout on mobile, not table
     - Navigate to /alerts
     - Assert table element NOT visible
     - Assert mobile card elements visible (check for alert card content: symbol, status badge)

  2. alert cards display symbol, status, and alert type
     - Assert AAPL card shows "Retracing" badge
     - Assert NVDA card shows "Approaching" badge

  3. tapping a card navigates to detail view
     - Click AAPL card
     - Assert URL contains /alerts/1

  4. Add Alert button accessible on mobile
     - Assert "Add Alert" button visible and clickable
     - Click it, assert dialog opens

  5. no horizontal scroll on mobile
     - Evaluate document.body.scrollWidth <= window.innerWidth + 1

test.describe('Alerts Responsive - Desktop (1280x800)')
  test.use({ viewport: { width: 1280, height: 800 } })

  Setup: mock GET /api/v1/alerts/ returning mockAlertList

  6. dashboard renders table layout on desktop
     - Navigate to /alerts
     - Assert table element visible
     - Assert column headers: Symbol, Alert Type, Price, Status, Details, Last Alert

  7. Alerts link visible in desktop sidebar
     - Assert sidebar link "Alerts" visible

  8. filter comboboxes visible on desktop
     - Assert both type and status combobox elements visible
```

---

## Testing Strategy

### UI Tests (Mocked Backend)
- Use `page.route()` to intercept all `/api/v1/alerts*` requests.
- Mock data from `tests/fixtures/mockAlertData.ts`.
- Follow the `setupMocks` helper pattern from `tests/ui/arena-analytics.spec.ts`.
- Scope assertions to containers when text is ambiguous (e.g., badge text that appears in both table and info panel).
- Use `.first()` or exact match when needed to avoid strict mode violations.
- **Dashboard filtering is client-side**: The UI sends a single `GET /api/v1/alerts/` request at load time and filters the local data in-browser. Filter tests (17-21) mock the full list once and assert DOM visibility changes -- no additional API calls are made when filters change.

### E2E Tests (Real Backend)
- Backend must be running (`./scripts/dc.sh up -d`).
- Import `TEST_CONFIG` from `tests/e2e/config.ts`.
- **Dedicated test symbol**: All E2E tests use `E2ETST` prefix for symbol names (e.g., `E2ETST1`, `E2ETSTA`). `MockMarketDataProvider` accepts any symbol string and generates fake data.
- **Cleanup in beforeEach**: Fetch all alerts via `GET /api/v1/alerts/`, filter client-side for `item.symbol.startsWith('E2ET')`, DELETE each match. This mirrors the `stock-lists.spec.ts` prefix convention.
- Seed test data via direct `fetch()` to `BACKEND_URL`, not UI interactions.
- Use `test.beforeAll` for backend health check.
- Guard assertions on `computed_state` for newly created alerts (may be null). Assert structural elements, not computed values.

### Page Objects
- `AlertsPage` and `AlertDetailPage` encapsulate selectors and actions.
- Accessibility-first selectors: `getByRole`, `getByLabel`, `getByText`.
- `data-testid` only for canvas/chart elements.
- `goto()` methods use explicit element waits (`heading.waitFor`) instead of `waitForLoadState('networkidle')` to avoid flakiness from background polling.

### Fixture Data
- `mockAlertData.ts` provides every alert variant: all 7 Fibonacci statuses (no_structure, rallying, pullback_started, retracing, at_level, bouncing, invalidated), all 5 MA statuses (above_ma, approaching, at_ma, below_ma, insufficient_data), paused alert with `computed_state: null`, events, and price data.
- Price data uses `timestamp` field (not `date`) matching backend serialization.
- Fixtures match the exact `AlertResponse` schema from backend.

### Console Error Monitoring
- All UI test suites include a `page loads without console errors` test.
- Filter known React nesting warnings.

### Notification Banners
- UI tests mock `Notification.permission` via `page.addInitScript`.
- The granted-permission banner ("Alerts require this tab to remain open") and denied-permission banner are verified as DOM elements with `role="status"`.
- Actual `Notification` constructor calls are NOT tested in Playwright (covered by unit tests on `useNotifications`).

## Success Criteria

- [ ] All 83 tests pass (100% pass rate): 24 dashboard UI + 12 create dialog UI + 16 detail UI + 9 CRUD E2E + 14 API contract E2E + 8 responsive UI
- [ ] Tests run in under 3 minutes total (UI < 60s, E2E < 120s)
- [ ] No flaky tests: deterministic mock data, explicit element waits (no `waitForLoadState('networkidle')`, no arbitrary `waitForTimeout` except for chart canvas rendering)
- [ ] Every user-facing feature in the ticket has at least one test: dashboard, detail, create, filter, pause, delete, responsive, all 12 status badges, notification banners, `computed_state: null` graceful rendering
- [ ] Tests follow existing patterns: AAA, accessible queries, POM, fixture files, `setupMocks` helper
- [ ] E2E cleanup with `E2ETST` prefix prevents test data leakage between runs
- [ ] No console errors in any UI test (filtered for known framework warnings)
- [ ] API contract tests validate field names and types, including `timestamp` for OHLCV data and query parameter filtering

## Revision Log

| Change | Source | Category |
|--------|--------|----------|
| Fixed `mockAlertPriceData` field: `date` -> `timestamp` | B1 (backend-reviewer) | BLOCKING |
| Removed E2E CRUD test #4 (invalid symbol) -- MockProvider accepts any symbol | B2 (backend-reviewer) | BLOCKING |
| Added fixtures for all 7 Fib + 5 MA statuses; expanded badge assertion tests | B3 (all reviewers) | BLOCKING |
| Added `computed_state: null` rendering test for dashboard Details column | B4 (qa-engineer) | BLOCKING |
| Changed E2E symbols to `E2ETST` prefix; client-side filter cleanup | B5 (backend-reviewer) | BLOCKING |
| Guarded E2E detail test against `computed_state: null` for new alerts | S1 (frontend-reviewer) | SHOULD FIX |
| Added 3 API contract tests for query param filtering (status, type, symbol) | S2 (qa-engineer) | SHOULD FIX |
| Extended events API contract test with field-level schema validation | S3 (qa-engineer) | SHOULD FIX |
| Replaced `waitForLoadState('networkidle')` with explicit element waits in POM | S4 (frontend-reviewer) | SHOULD FIX |
| Added soft-deleted alert events 404 test | N1 (qa-engineer) | NICE TO HAVE |
| Use MA period `100` (not `999`) for invalid period test, matching backend tests | N2 (backend-reviewer) | NICE TO HAVE |
| Added Last Alert timestamp and Price column assertions | N3 (frontend-reviewer) | NICE TO HAVE |
| Added price-data OHLCV field validation test | Additional | NICE TO HAVE |
| Added notification banner tests (granted + denied) | Additional | Coverage gap |
| Added sorting test (actionable statuses first) | Additional | Coverage gap |
| Changed filter combobox selectors from positional to named (`aria-label`); added implementation prereq for aria-labels | C1 (qa-engineer, frontend-reviewer) | SIGN-OFF FIX |
| Added `navigation.spec.ts` regression fix to files-to-modify and implementation prereqs | C2 (qa-engineer, frontend-reviewer) | SIGN-OFF FIX |
| Scoped `confirmDelete()` to `alertdialog` role to avoid strict mode violations | F1 (frontend-reviewer) | NOTED GAP |
| Documented client-side filtering assumption in Testing Strategy | F2 (frontend-reviewer) | NOTED GAP |
