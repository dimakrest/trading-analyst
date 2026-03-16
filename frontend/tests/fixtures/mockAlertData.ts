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
  computed_state: null,
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
