"""Historical bounce rate indicator for mean-reversion analysis.

Measures how reliably a stock mean-reverts after pulling back to MA20
in a bearish trend. A "bounce" is defined as recovering ≥2.5% from
the pullback-day low within 15 trading days.
"""

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from app.indicators.technical import simple_moving_average
from app.indicators.trend import detect_trend, TrendDirection


@dataclass
class BounceRateAnalysis:
    """Result of bounce rate analysis."""
    bounce_rate: float | None  # 0.0-1.0, or None if insufficient data
    total_events: int          # Number of pullback events found
    successful_bounces: int    # Number that recovered ≥2.5% within 15 days


# Minimum pullback events required for a valid bounce rate
MIN_BOUNCE_EVENTS = 3

# Recovery threshold (matches trailing stop %)
RECOVERY_PCT = 2.5

# Max days to recover (matches max hold period)
RECOVERY_WINDOW_DAYS = 15

# MA20 distance threshold (matches Live20 alignment criterion)
MA20_DISTANCE_THRESHOLD = -5.0

# Trend detection period (matches Live20 trend criterion)
TREND_PERIOD = 10

# MA period — hardcoded to 20 (all other constants are MA20-specific)
MA_PERIOD = 20


def calculate_bounce_rate(
    closes: list[float] | NDArray[np.float64],
    lows: list[float] | NDArray[np.float64],
) -> BounceRateAnalysis:
    """Calculate historical bounce rate from pullbacks to MA20.

    Scans the price history for pullback events (price ≥5% below MA20
    in a bearish 10-day trend) and checks whether each recovered ≥2.5%
    from the pullback-day low within 15 trading days.

    Args:
        closes: Closing prices, oldest to newest.
        lows: Low prices, oldest to newest.

    Returns:
        BounceRateAnalysis with bounce_rate (0.0-1.0 or None),
        total_events, and successful_bounces.
    """
    closes_arr = np.array(closes, dtype=float)
    lows_arr = np.array(lows, dtype=float)
    n = len(closes_arr)

    # Need enough data for MA20 + trend detection + at least some recovery window
    min_required = MA_PERIOD + TREND_PERIOD + RECOVERY_WINDOW_DAYS
    if n < min_required:
        return BounceRateAnalysis(bounce_rate=None, total_events=0, successful_bounces=0)

    # Precompute MA20 for all bars
    ma = simple_moving_average(closes_arr, MA_PERIOD)

    total_events = 0
    successful_bounces = 0

    # Start scanning from the first bar where MA20 and trend are both computable.
    # After a pullback event, skip forward RECOVERY_WINDOW_DAYS to avoid
    # overlapping events from the same pullback.
    start_idx = max(MA_PERIOD, TREND_PERIOD)
    # Stop early enough to allow recovery window to be evaluated
    # (last event must have room for 15-day forward check)
    end_idx = n - RECOVERY_WINDOW_DAYS

    i = start_idx
    while i < end_idx:
        # Check MA20 distance at this bar
        current_ma = ma[i]
        if np.isnan(current_ma) or current_ma <= 0:
            i += 1
            continue

        distance_pct = ((closes_arr[i] - current_ma) / current_ma) * 100

        if distance_pct > MA20_DISTANCE_THRESHOLD:
            # Not far enough below MA20
            i += 1
            continue

        # Check 10-day trend ending at this bar
        trend_slice = closes_arr[max(0, i - TREND_PERIOD + 1):i + 1]
        if len(trend_slice) < TREND_PERIOD:
            i += 1
            continue

        trend = detect_trend(trend_slice, period=TREND_PERIOD)
        if trend != TrendDirection.BEARISH:
            i += 1
            continue

        # This is a pullback event.
        total_events += 1
        pullback_low = lows_arr[i]

        # Check if price recovers ≥2.5% from pullback-day low within 15 days
        recovery_target = pullback_low * (1 + RECOVERY_PCT / 100)
        recovery_end = min(i + RECOVERY_WINDOW_DAYS + 1, n)

        recovered = False
        for j in range(i + 1, recovery_end):
            if closes_arr[j] >= recovery_target:
                recovered = True
                break

        if recovered:
            successful_bounces += 1

        # Skip forward to avoid overlapping events from the same pullback
        i += RECOVERY_WINDOW_DAYS

    if total_events < MIN_BOUNCE_EVENTS:
        return BounceRateAnalysis(
            bounce_rate=None,
            total_events=total_events,
            successful_bounces=successful_bounces,
        )

    return BounceRateAnalysis(
        bounce_rate=successful_bounces / total_events,
        total_events=total_events,
        successful_bounces=successful_bounces,
    )
