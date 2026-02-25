"""Unit tests for the historical bounce rate indicator.

Tests validate that calculate_bounce_rate() correctly identifies pullback events
(price ≥5% below MA20 in a bearish 10-day trend) and measures recovery rates.

Key constants from the implementation:
    MIN_BOUNCE_EVENTS = 3
    RECOVERY_PCT = 2.5
    RECOVERY_WINDOW_DAYS = 15
    MA20_DISTANCE_THRESHOLD = -5.0  (price must be >5% below MA20)
    TREND_PERIOD = 10
    MA_PERIOD = 20
    min_required = MA_PERIOD + TREND_PERIOD + RECOVERY_WINDOW_DAYS = 45 bars

Data construction patterns used in these tests
-----------------------------------------------
A pullback event is triggered when:
  (close[i] - ma20[i]) / ma20[i] * 100 <= -5.0
  AND
  detect_trend(closes[i-9:i+1], period=10) == BEARISH

The simplest reliable event is a single-bar drop from a stable price:
  - 30 bars at 100.0 → MA20 stabilizes at 100.0
  - 1 bar at 89.0   → MA20 ≈ 99.45, dist ≈ -10.5%, trend BEARISH (-11%)
  - 15 recovery bars → checked for closes ≥ 89.0 * 1.025 = 91.225

After an event, the scanner skips 15 bars (RECOVERY_WINDOW_DAYS).
Each event segment is therefore 30 + 1 + 15 = 46 bars (plus 30 pre-event stable).
"""

import pytest

from app.indicators.bounce_rate import (
    BounceRateAnalysis,
    MIN_BOUNCE_EVENTS,
    calculate_bounce_rate,
)


# ---------------------------------------------------------------------------
# Data-construction helpers
# ---------------------------------------------------------------------------

def _stable(price: float, n: int) -> list[float]:
    """Return a flat price series of length n."""
    return [price] * n


def _declining(start: float, end: float, n: int) -> list[float]:
    """Return a linearly declining price series from start to end (inclusive)."""
    if n == 1:
        return [start]
    step = (end - start) / (n - 1)
    return [start + step * i for i in range(n)]


def _build_event_series(
    bounce_flags: list[bool],
    stable_price: float = 100.0,
    pullback_price: float = 89.0,
) -> tuple[list[float], list[float]]:
    """Build a price series that produces exactly len(bounce_flags) pullback events.

    Each event uses a single-bar drop pattern:
      - 30 bars at stable_price (re-establishes MA20 ≈ stable_price)
      - 1  bar at pullback_price (triggers the event: dist ≈ -10.5%, trend BEARISH)
      - 15 bars at recovery_price (if bounce=True) or pullback_price (if bounce=False)

    The structure is prepended with 20 additional stable bars so that MA20 is
    valid from the very first scan index.

    Recovery price is set to pullback_price * 1.03 (3% above pullback low),
    which exceeds the 2.5% RECOVERY_PCT threshold.

    Args:
        bounce_flags: One bool per desired event; True = recovery succeeds.
        stable_price: Price during stable (non-event) periods.
        pullback_price: Price during the pullback event bar.

    Returns:
        (closes, lows) both as plain lists, lows == closes throughout.
    """
    recovery_price = pullback_price * 1.03   # 89 * 1.03 = 91.67 > 91.225 target

    # Extra stable history ensures MA20 is well-established before the first event
    closes: list[float] = _stable(stable_price, 20)

    for bounce in bounce_flags:
        # Re-establish MA20 at stable_price before the event bar
        closes += _stable(stable_price, 30)
        # Single-bar drop → event fires here
        closes.append(pullback_price)
        # Recovery window: 15 bars with or without recovery
        if bounce:
            closes += _stable(recovery_price, 15)
        else:
            closes += _stable(pullback_price, 15)

    # lows mirror closes throughout (simplest synthetic data)
    lows = list(closes)
    return closes, lows


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_insufficient_data_returns_none():
    """Fewer bars than min_required (45) must return bounce_rate=None, total_events=0."""
    # 44 bars — one short of the 45-bar minimum
    closes = _stable(100.0, 44)
    lows = _stable(100.0, 44)

    result = calculate_bounce_rate(closes, lows)

    assert isinstance(result, BounceRateAnalysis)
    assert result.bounce_rate is None
    assert result.total_events == 0
    assert result.successful_bounces == 0


def test_no_pullback_events_returns_none():
    """Price always at MA20 (distance = 0%) — no pullback events should be found.

    60 bars at a stable price of 100.0: MA20 always equals the close, so distance
    is 0%, which does not satisfy the ≤ -5.0% threshold.
    """
    closes = _stable(100.0, 60)
    lows = _stable(100.0, 60)

    result = calculate_bounce_rate(closes, lows)

    assert result.bounce_rate is None
    assert result.total_events == 0


def test_all_bounces_returns_1():
    """Every pullback recovers — bounce_rate must equal 1.0.

    Three events each followed by a close ≥ 2.5% above the pullback low.
    """
    closes, lows = _build_event_series(bounce_flags=[True, True, True])

    result = calculate_bounce_rate(closes, lows)

    assert result.total_events == 3
    assert result.successful_bounces == 3
    assert result.bounce_rate == 1.0


def test_no_bounces_returns_0():
    """Every pullback keeps falling — bounce_rate must equal 0.0.

    Three events where the price stays at the pullback low throughout the
    15-bar recovery window, never reaching the 2.5% recovery target.
    """
    closes, lows = _build_event_series(bounce_flags=[False, False, False])

    result = calculate_bounce_rate(closes, lows)

    assert result.total_events == 3
    assert result.successful_bounces == 0
    assert result.bounce_rate == 0.0


def test_mixed_bounces():
    """2 bounces out of 3 events — bounce_rate must be exactly 2/3."""
    closes, lows = _build_event_series(bounce_flags=[True, True, False])

    result = calculate_bounce_rate(closes, lows)

    assert result.total_events == 3
    assert result.successful_bounces == 2
    assert abs(result.bounce_rate - 2 / 3) < 1e-9


def test_below_min_events_returns_none():
    """Only 2 pullback events (below MIN_BOUNCE_EVENTS=3) — bounce_rate must be None.

    The function must return None for the rate when fewer than 3 events are found,
    even when total_events and successful_bounces are non-zero.
    """
    closes, lows = _build_event_series(bounce_flags=[True, True])

    result = calculate_bounce_rate(closes, lows)

    assert result.bounce_rate is None
    assert result.total_events == 2
    assert result.successful_bounces == 2


def test_events_do_not_overlap():
    """The scanner must count each pullback region as exactly one event.

    Three well-separated pullback events (each in its own 30+1+15 block)
    should produce exactly 3 total_events — confirming that the 15-bar skip
    prevents a single pullback region from being counted multiple times.
    """
    closes, lows = _build_event_series(bounce_flags=[True, True, True])

    result = calculate_bounce_rate(closes, lows)

    assert result.total_events == 3, (
        f"Expected exactly 3 non-overlapping events, got {result.total_events}"
    )


def test_bearish_trend_required():
    """A pullback below MA20 without a bearish 10-day trend must NOT be counted.

    We construct a series where the price drop happens BEFORE the scan window opens,
    so that when the scanner starts (bar 20) the 10-bar trend window contains only
    flat (equal) prices — producing a NEUTRAL trend that disqualifies the event.

    Structure:
      bars 0..9  : 100.0  (10 bars — provides the elevated MA20)
      bars 10..59: 88.0   (50 bars — price already below MA20 before scan starts)

    At the first scan bar (i=20):
      - MA20 = (10 × 100 + 10 × 88) / 20 = 94.0  →  dist ≈ -6.4%  (qualifies)
      - trend_slice = closes[11..20] = [88] × 10  →  pct_change = 0%  →  NEUTRAL
      So no event is counted.

    By bar 22 the MA20 has normalized enough that dist < -5%, so no further events.
    """
    closes = _stable(100.0, 10) + _stable(88.0, 50)
    lows = list(closes)

    result = calculate_bounce_rate(closes, lows)

    assert result.total_events == 0
    assert result.bounce_rate is None


def test_ma20_distance_threshold():
    """Price only ~2.3% below MA20 (not the required 5%) must NOT trigger an event.

    Structure:
      bars 0..29 : 100.0           (stable — MA20 = 100)
      bars 30..39: declining from 100 to 97  (3% total drop)
      bars 40..54: 97.0            (15 flat bars fill recovery window)

    At bar 39 (deepest point):
      MA20 ≈ 99.25  →  dist ≈ -2.3%  which is above the -5.0% threshold.
    No bars ever satisfy the distance criterion, so total_events must be 0.
    """
    declining_segment = _declining(100.0, 97.0, 10)
    closes = _stable(100.0, 30) + declining_segment + _stable(97.0, 15)
    lows = list(closes)

    result = calculate_bounce_rate(closes, lows)

    assert result.total_events == 0
    assert result.bounce_rate is None


def test_result_is_bounce_rate_analysis_dataclass():
    """calculate_bounce_rate must always return a BounceRateAnalysis instance."""
    closes = _stable(100.0, 10)
    lows = _stable(100.0, 10)

    result = calculate_bounce_rate(closes, lows)

    assert isinstance(result, BounceRateAnalysis)
    assert hasattr(result, "bounce_rate")
    assert hasattr(result, "total_events")
    assert hasattr(result, "successful_bounces")


def test_accepts_numpy_arrays():
    """calculate_bounce_rate must accept numpy arrays as input without error."""
    import numpy as np

    closes = np.array(_stable(100.0, 50), dtype=float)
    lows = np.array(_stable(100.0, 50), dtype=float)

    result = calculate_bounce_rate(closes, lows)

    assert isinstance(result, BounceRateAnalysis)


def test_bounce_rate_within_valid_range():
    """When bounce_rate is not None it must be in [0.0, 1.0]."""
    closes, lows = _build_event_series(bounce_flags=[True, False, True])

    result = calculate_bounce_rate(closes, lows)

    if result.bounce_rate is not None:
        assert 0.0 <= result.bounce_rate <= 1.0


def test_successful_bounces_leq_total_events():
    """successful_bounces must never exceed total_events."""
    closes, lows = _build_event_series(bounce_flags=[True, True, False])

    result = calculate_bounce_rate(closes, lows)

    assert result.successful_bounces <= result.total_events
