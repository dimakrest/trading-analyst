"""Comprehensive tests for the Fibonacci retracement indicator.

Tests cover swing detection, level calculation, and the full status state machine
including boundary conditions and oscillation behavior.

All tests follow the AAA (Arrange / Act / Assert) pattern.
"""

import numpy as np
import pytest

from app.indicators.fibonacci import (
    FibonacciState,
    SwingPoint,
    SwingStructure,
    calculate_fib_levels,
    compute_fibonacci_status,
    detect_swing_high,
    detect_swing_low,
    find_latest_swing_structure,
)


# ---------------------------------------------------------------------------
# Test helpers / factories
# ---------------------------------------------------------------------------


def make_dates(n: int, start: int = 1) -> list[str]:
    """Generate synthetic date strings for n bars."""
    return [f"2026-01-{start + i:02d}" for i in range(n)]


def make_flat_prices(value: float, n: int) -> np.ndarray:
    """Create a flat price array."""
    return np.full(n, value, dtype=float)


def make_uptrend_data(
    base: float,
    peak: float,
    pullback_to: float,
    lookback: int = 10,
) -> tuple[np.ndarray, np.ndarray, list[str]]:
    """Build synthetic OHLC data for an uptrend followed by a pullback.

    Returns (highs, lows, dates) arrays suitable for swing detection.
    Layout (bar indices):
      0 .. lookback-1           : base plateau (swing low zone)
      lookback                  : swing low at `base` (confirmed by lookback bars each side)
      lookback+1 .. 2*lookback  : rising bars
      2*lookback+1              : swing high at `peak`
      2*lookback+2 .. 3*lookback+1 : falling bars (pullback toward pullback_to)
      Total bars: 3*lookback + 2  (extra bars at each end for confirmation)
    """
    n_bars = 4 * lookback + 4  # generous buffer on both sides
    highs = np.zeros(n_bars, dtype=float)
    lows = np.zeros(n_bars, dtype=float)

    # Default fill: mid-range
    mid = (base + peak) / 2
    highs[:] = mid + 1.0
    lows[:] = mid - 1.0

    # Carve out swing low region around index `lookback + 1`
    swing_low_idx = lookback + 1
    lows[swing_low_idx] = base
    highs[swing_low_idx] = base + 0.5

    # Gradually rising to swing high around index `2 * lookback + 2`
    swing_high_idx = 2 * lookback + 2
    highs[swing_high_idx] = peak
    lows[swing_high_idx] = peak - 0.5

    # After swing high: pull back toward pullback_to
    for i in range(swing_high_idx + 1, n_bars):
        factor = (i - swing_high_idx) / (n_bars - swing_high_idx)
        price = peak - (peak - pullback_to) * factor
        highs[i] = price + 0.5
        lows[i] = price - 0.5

    # Fill the rising section more carefully to avoid false peaks
    for i in range(swing_low_idx + 1, swing_high_idx):
        factor = (i - swing_low_idx) / (swing_high_idx - swing_low_idx)
        price = base + (peak - base) * factor
        highs[i] = price + 0.3
        lows[i] = price - 0.3

    dates = make_dates(n_bars)
    return highs, lows, dates


def make_downtrend_data(
    peak: float,
    base: float,
    bounce_to: float,
    lookback: int = 10,
) -> tuple[np.ndarray, np.ndarray, list[str]]:
    """Build synthetic data for a downtrend followed by a bounce.

    Returns (highs, lows, dates).
    """
    n_bars = 4 * lookback + 4
    highs = np.zeros(n_bars, dtype=float)
    lows = np.zeros(n_bars, dtype=float)

    mid = (base + peak) / 2
    highs[:] = mid + 1.0
    lows[:] = mid - 1.0

    # Swing high early
    swing_high_idx = lookback + 1
    highs[swing_high_idx] = peak
    lows[swing_high_idx] = peak - 0.5

    # Falling to swing low
    swing_low_idx = 2 * lookback + 2
    lows[swing_low_idx] = base
    highs[swing_low_idx] = base + 0.5

    # After swing low: bounce toward bounce_to
    for i in range(swing_low_idx + 1, n_bars):
        factor = (i - swing_low_idx) / (n_bars - swing_low_idx)
        price = base + (bounce_to - base) * factor
        highs[i] = price + 0.5
        lows[i] = price - 0.5

    # Fill falling section
    for i in range(swing_high_idx + 1, swing_low_idx):
        factor = (i - swing_high_idx) / (swing_low_idx - swing_high_idx)
        price = peak - (peak - base) * factor
        highs[i] = price + 0.3
        lows[i] = price - 0.3

    dates = make_dates(n_bars)
    return highs, lows, dates


def make_swing_structure_uptrend(
    swing_low_price: float = 110.0,
    swing_high_price: float = 140.0,
) -> SwingStructure:
    """Create a simple uptrend SwingStructure for testing."""
    return SwingStructure(
        high=SwingPoint(index=20, price=swing_high_price, date="2026-01-20"),
        low=SwingPoint(index=10, price=swing_low_price, date="2026-01-10"),
        direction="uptrend",
    )


def make_swing_structure_downtrend(
    swing_high_price: float = 140.0,
    swing_low_price: float = 110.0,
) -> SwingStructure:
    """Create a simple downtrend SwingStructure for testing."""
    return SwingStructure(
        high=SwingPoint(index=10, price=swing_high_price, date="2026-01-10"),
        low=SwingPoint(index=20, price=swing_low_price, date="2026-01-20"),
        direction="downtrend",
    )


def make_config(
    levels: list[float] | None = None,
    tolerance_pct: float = 0.5,
    min_swing_pct: float = 10.0,
) -> dict:
    """Create a standard Fibonacci alert config dict."""
    return {
        "levels": levels if levels is not None else [38.2, 50.0, 61.8],
        "tolerance_pct": tolerance_pct,
        "min_swing_pct": min_swing_pct,
    }


def make_previous_state(
    status: str,
    swing_structure: SwingStructure | None = None,
    fib_levels: dict[float, dict] | None = None,
    current_price: float = 130.0,
    retracement_pct: float | None = None,
) -> FibonacciState:
    """Build a FibonacciState for use as previous_state in tests."""
    return FibonacciState(
        status=status,
        swing_structure=swing_structure,
        fib_levels=fib_levels or {},
        retracement_pct=retracement_pct,
        next_level=None,
        current_price=current_price,
        events=[],
    )


# ---------------------------------------------------------------------------
# 1. test_detect_swing_high_basic
# ---------------------------------------------------------------------------


class TestDetectSwingHighBasic:
    """Detects obvious peaks in synthetic price data."""

    def test_detect_swing_high_basic(self):
        # Arrange: simple spike at index 10
        n = 30
        highs = np.full(n, 100.0)
        highs[10] = 115.0
        dates = make_dates(n)

        # Act
        result = detect_swing_high(highs, dates, lookback=5)

        # Assert
        assert len(result) == 1
        assert result[0].index == 10
        assert result[0].price == pytest.approx(115.0)
        assert result[0].date == dates[10]


# ---------------------------------------------------------------------------
# 2. test_detect_swing_low_basic
# ---------------------------------------------------------------------------


class TestDetectSwingLowBasic:
    """Detects obvious troughs in synthetic price data."""

    def test_detect_swing_low_basic(self):
        # Arrange: simple dip at index 12
        n = 30
        lows = np.full(n, 100.0)
        lows[12] = 85.0
        dates = make_dates(n)

        # Act
        result = detect_swing_low(lows, dates, lookback=5)

        # Assert
        assert len(result) == 1
        assert result[0].index == 12
        assert result[0].price == pytest.approx(85.0)
        assert result[0].date == dates[12]


# ---------------------------------------------------------------------------
# 3. test_no_swing_detected_flat_data
# ---------------------------------------------------------------------------


class TestNoSwingDetectedFlatData:
    """Returns empty list when price data is completely flat."""

    def test_no_swing_detected_flat_data(self):
        # Arrange: perfectly flat data — no bar is strictly higher or lower than neighbors
        n = 40
        flat_prices = make_flat_prices(100.0, n)
        dates = make_dates(n)

        # Act
        highs_result = detect_swing_high(flat_prices, dates, lookback=5)
        lows_result = detect_swing_low(flat_prices, dates, lookback=5)

        # Assert
        assert highs_result == []
        assert lows_result == []


# ---------------------------------------------------------------------------
# 4. test_swing_structure_uptrend
# ---------------------------------------------------------------------------


class TestSwingStructureUptrend:
    """Low-then-high pattern is detected as uptrend."""

    def test_swing_structure_uptrend(self):
        # Arrange: swing low at 110, swing high at 140, then pullback to 130
        highs, lows, dates = make_uptrend_data(
            base=110.0, peak=140.0, pullback_to=130.0, lookback=5
        )

        # Act
        structure = find_latest_swing_structure(
            highs, lows, dates, lookback=5, min_swing_pct=10.0
        )

        # Assert
        assert structure is not None
        assert structure.direction == "uptrend"
        assert structure.high.price == pytest.approx(140.0)
        assert structure.low.price == pytest.approx(110.0)
        # Swing low index must be less than swing high index for uptrend
        assert structure.low.index < structure.high.index


# ---------------------------------------------------------------------------
# 5. test_swing_structure_downtrend
# ---------------------------------------------------------------------------


class TestSwingStructureDowntrend:
    """High-then-low pattern is detected as downtrend."""

    def test_swing_structure_downtrend(self):
        # Arrange: swing high at 140, swing low at 110, then bounce to 120
        highs, lows, dates = make_downtrend_data(
            peak=140.0, base=110.0, bounce_to=120.0, lookback=5
        )

        # Act
        structure = find_latest_swing_structure(
            highs, lows, dates, lookback=5, min_swing_pct=10.0
        )

        # Assert
        assert structure is not None
        assert structure.direction == "downtrend"
        assert structure.high.price == pytest.approx(140.0)
        assert structure.low.price == pytest.approx(110.0)
        # Swing high index must be less than swing low index for downtrend
        assert structure.high.index < structure.low.index


# ---------------------------------------------------------------------------
# 6. test_swing_structure_minimum_move
# ---------------------------------------------------------------------------


class TestSwingStructureMinimumMove:
    """Rejects swing structures where the move is below min_swing_pct."""

    def test_swing_structure_minimum_move(self):
        # Arrange: swing from 100 to 104 = 4% move (below 10% threshold)
        highs, lows, dates = make_uptrend_data(
            base=100.0, peak=104.0, pullback_to=102.0, lookback=5
        )

        # Act: require 10% minimum
        structure = find_latest_swing_structure(
            highs, lows, dates, lookback=5, min_swing_pct=10.0
        )

        # Assert: should be None because 4% < 10%
        assert structure is None

    def test_swing_structure_exactly_at_minimum_move(self):
        # Arrange: swing from 100 to 110 = 10% move (exactly at threshold)
        highs, lows, dates = make_uptrend_data(
            base=100.0, peak=110.0, pullback_to=105.0, lookback=5
        )

        # Act: require exactly 10%
        structure = find_latest_swing_structure(
            highs, lows, dates, lookback=5, min_swing_pct=10.0
        )

        # Assert: should be found (move >= min_swing_pct)
        assert structure is not None


# ---------------------------------------------------------------------------
# 7. test_fib_levels_uptrend
# ---------------------------------------------------------------------------


class TestFibLevelsUptrend:
    """Correct Fibonacci level prices for $110 -> $140 uptrend."""

    def test_fib_levels_uptrend(self):
        # Arrange
        swing_high = 140.0
        swing_low = 110.0

        # Act
        levels = calculate_fib_levels(swing_high, swing_low, direction="uptrend")

        # Assert: levels calculated downward from swing_high
        # range = 30.0
        # 23.6%: 140 - 30 * 0.236 = 140 - 7.08 = 132.92
        # 38.2%: 140 - 30 * 0.382 = 140 - 11.46 = 128.54
        # 50.0%: 140 - 30 * 0.500 = 140 - 15.00 = 125.00
        # 61.8%: 140 - 30 * 0.618 = 140 - 18.54 = 121.46
        # 78.6%: 140 - 30 * 0.786 = 140 - 23.58 = 116.42
        assert levels[23.6] == pytest.approx(132.92, abs=0.01)
        assert levels[38.2] == pytest.approx(128.54, abs=0.01)
        assert levels[50.0] == pytest.approx(125.00, abs=0.01)
        assert levels[61.8] == pytest.approx(121.46, abs=0.01)
        assert levels[78.6] == pytest.approx(116.42, abs=0.01)


# ---------------------------------------------------------------------------
# 8. test_fib_levels_downtrend
# ---------------------------------------------------------------------------


class TestFibLevelsDowntrend:
    """Correct Fibonacci level prices for downtrend."""

    def test_fib_levels_downtrend(self):
        # Arrange: swing_high=140, swing_low=110, direction=downtrend
        # Levels calculated upward from swing_low
        # range = 30.0
        # 23.6%: 110 + 30 * 0.236 = 110 + 7.08 = 117.08
        # 38.2%: 110 + 30 * 0.382 = 110 + 11.46 = 121.46
        # 50.0%: 110 + 30 * 0.500 = 110 + 15.00 = 125.00
        # 61.8%: 110 + 30 * 0.618 = 110 + 18.54 = 128.54
        # 78.6%: 110 + 30 * 0.786 = 110 + 23.58 = 133.58
        swing_high = 140.0
        swing_low = 110.0

        # Act
        levels = calculate_fib_levels(swing_high, swing_low, direction="downtrend")

        # Assert
        assert levels[23.6] == pytest.approx(117.08, abs=0.01)
        assert levels[38.2] == pytest.approx(121.46, abs=0.01)
        assert levels[50.0] == pytest.approx(125.00, abs=0.01)
        assert levels[61.8] == pytest.approx(128.54, abs=0.01)
        assert levels[78.6] == pytest.approx(133.58, abs=0.01)


# ---------------------------------------------------------------------------
# 9. test_status_no_structure
# ---------------------------------------------------------------------------


class TestStatusNoStructure:
    """Returns no_structure status when no valid swing found."""

    def test_status_no_structure(self):
        # Arrange
        config = make_config()

        # Act
        state = compute_fibonacci_status(
            current_price=130.0,
            swing_structure=None,
            fib_levels={},
            config=config,
            previous_state=None,
        )

        # Assert
        assert state.status == "no_structure"
        assert state.swing_structure is None
        assert state.retracement_pct is None
        assert state.next_level is None
        assert state.events == []


# ---------------------------------------------------------------------------
# 10. test_status_retracing
# ---------------------------------------------------------------------------


class TestStatusRetracing:
    """Price between 23.6% and 78.6% returns retracing."""

    def test_status_retracing(self):
        # Arrange: uptrend 110->140, price at 127.0
        # retracement = (140 - 127) / 30 * 100 = 43.3% -> between 23.6 and 78.6
        structure = make_swing_structure_uptrend(110.0, 140.0)
        fib_levels = calculate_fib_levels(140.0, 110.0, "uptrend")
        config = make_config()

        # Act: price at 127.0 is below 38.2% level (128.54) — should be retracing
        state = compute_fibonacci_status(
            current_price=127.0,
            swing_structure=structure,
            fib_levels=fib_levels,
            config=config,
            previous_state=None,
        )

        # Assert
        assert state.status == "retracing"
        assert state.retracement_pct is not None
        assert 23.6 < state.retracement_pct < 78.6


# ---------------------------------------------------------------------------
# 11. test_status_at_level
# ---------------------------------------------------------------------------


class TestStatusAtLevel:
    """Price within tolerance of fib level returns at_level and generates event."""

    def test_status_at_level(self):
        # Arrange: uptrend 110->140
        # 38.2% level = 128.54, price exactly at 128.54
        structure = make_swing_structure_uptrend(110.0, 140.0)
        fib_levels = calculate_fib_levels(140.0, 110.0, "uptrend")
        config = make_config(levels=[38.2, 50.0, 61.8], tolerance_pct=0.5)

        # Act
        state = compute_fibonacci_status(
            current_price=128.54,
            swing_structure=structure,
            fib_levels=fib_levels,
            config=config,
            previous_state=None,
        )

        # Assert
        assert state.status == "at_level"
        assert len(state.events) == 1
        event = state.events[0]
        assert event["event_type"] == "level_hit"
        assert event["new_status"] == "at_level"
        assert event["details"]["level_pct"] == pytest.approx(38.2, abs=0.01)


# ---------------------------------------------------------------------------
# 12. test_status_at_level_fires_once
# ---------------------------------------------------------------------------


class TestStatusAtLevelFiresOnce:
    """Same level does not fire a second event per swing structure."""

    def test_status_at_level_fires_once(self):
        # Arrange: uptrend 110->140, price at 38.2% level (128.54)
        structure = make_swing_structure_uptrend(110.0, 140.0)
        fib_levels = calculate_fib_levels(140.0, 110.0, "uptrend")
        config = make_config(levels=[38.2, 50.0, 61.8], tolerance_pct=0.5)

        # First hit — fires event
        first_state = compute_fibonacci_status(
            current_price=128.54,
            swing_structure=structure,
            fib_levels=fib_levels,
            config=config,
            previous_state=None,
        )
        assert len(first_state.events) == 1

        # Act: same price again (same swing structure) — should NOT fire again
        second_state = compute_fibonacci_status(
            current_price=128.54,
            swing_structure=structure,
            fib_levels=fib_levels,
            config=config,
            previous_state=first_state,
        )

        # Assert: no new events generated
        assert second_state.status == "at_level"
        assert second_state.events == []


# ---------------------------------------------------------------------------
# 13. test_status_invalidated_uptrend
# ---------------------------------------------------------------------------


class TestStatusInvalidatedUptrend:
    """Price strictly below swing low invalidates uptrend structure."""

    def test_status_invalidated_uptrend(self):
        # Arrange: uptrend 110->140, price at 109.99 (below swing low of 110)
        structure = make_swing_structure_uptrend(110.0, 140.0)
        fib_levels = calculate_fib_levels(140.0, 110.0, "uptrend")
        config = make_config()

        # Act
        state = compute_fibonacci_status(
            current_price=109.99,
            swing_structure=structure,
            fib_levels=fib_levels,
            config=config,
            previous_state=None,
        )

        # Assert
        assert state.status == "invalidated"
        assert len(state.events) == 1
        assert state.events[0]["event_type"] == "invalidated"


# ---------------------------------------------------------------------------
# 14. test_status_invalidated_downtrend
# ---------------------------------------------------------------------------


class TestStatusInvalidatedDowntrend:
    """Price strictly above swing high invalidates downtrend structure."""

    def test_status_invalidated_downtrend(self):
        # Arrange: downtrend 140->110, price at 140.01 (above swing high of 140)
        structure = make_swing_structure_downtrend(swing_high_price=140.0, swing_low_price=110.0)
        fib_levels = calculate_fib_levels(140.0, 110.0, "downtrend")
        config = make_config()

        # Act
        state = compute_fibonacci_status(
            current_price=140.01,
            swing_structure=structure,
            fib_levels=fib_levels,
            config=config,
            previous_state=None,
        )

        # Assert
        assert state.status == "invalidated"
        assert len(state.events) == 1
        assert state.events[0]["event_type"] == "invalidated"


# ---------------------------------------------------------------------------
# 15. test_status_bouncing
# ---------------------------------------------------------------------------


class TestStatusBouncing:
    """Price moves back toward trend from at_level returns bouncing."""

    def test_status_bouncing(self):
        # Arrange: uptrend 110->140
        # First: price at 38.2% level (128.54) -> at_level
        structure = make_swing_structure_uptrend(110.0, 140.0)
        fib_levels = calculate_fib_levels(140.0, 110.0, "uptrend")
        config = make_config(levels=[38.2, 50.0, 61.8], tolerance_pct=0.5)

        at_level_state = compute_fibonacci_status(
            current_price=128.54,
            swing_structure=structure,
            fib_levels=fib_levels,
            config=config,
            previous_state=None,
        )
        assert at_level_state.status == "at_level"

        # Act: price moves up to 129.50 (higher than 128.54, bouncing upward from level)
        # 38.2% level = 128.54, tolerance is 0.5% -> 128.54 * 1.005 = 129.18
        # 129.50 is outside tolerance AND higher than previous price -> bouncing
        bounce_state = compute_fibonacci_status(
            current_price=129.50,
            swing_structure=structure,
            fib_levels=fib_levels,
            config=config,
            previous_state=at_level_state,
        )

        # Assert
        assert bounce_state.status == "bouncing"


# ---------------------------------------------------------------------------
# 16. test_re_anchor_new_swing_high
# ---------------------------------------------------------------------------


class TestReAnchorNewSwingHigh:
    """New swing structure triggers a fresh computation without carried-over triggers."""

    def test_re_anchor_new_swing_high(self):
        # Arrange: original structure 110->140
        old_structure = make_swing_structure_uptrend(110.0, 140.0)
        old_fib_levels = calculate_fib_levels(140.0, 110.0, "uptrend")
        config = make_config(levels=[38.2, 50.0, 61.8], tolerance_pct=0.5)

        # Simulate that 38.2% was already triggered on the old structure
        old_state = compute_fibonacci_status(
            current_price=128.54,
            swing_structure=old_structure,
            fib_levels=old_fib_levels,
            config=config,
            previous_state=None,
        )
        assert old_state.fib_levels[38.2]["status"] == "triggered"

        # New structure: price made new swing high at 155 with same low
        new_structure = SwingStructure(
            high=SwingPoint(index=30, price=155.0, date="2026-02-01"),
            low=SwingPoint(index=10, price=110.0, date="2026-01-10"),
            direction="uptrend",
        )
        new_fib_levels = calculate_fib_levels(155.0, 110.0, "uptrend")

        # Act: compute with new structure, using old state as previous
        new_state = compute_fibonacci_status(
            current_price=140.0,
            swing_structure=new_structure,
            fib_levels=new_fib_levels,
            config=config,
            previous_state=old_state,
        )

        # Assert: 38.2% level should be reset to pending (new structure)
        assert new_state.fib_levels[38.2]["status"] == "pending"


# ---------------------------------------------------------------------------
# 17. test_full_lifecycle
# ---------------------------------------------------------------------------


class TestFullLifecycle:
    """Simulate a realistic price sequence through all states."""

    def test_full_lifecycle(self):
        # Arrange: uptrend 110->140, then pull back through all states
        structure = make_swing_structure_uptrend(110.0, 140.0)
        fib_levels = calculate_fib_levels(140.0, 110.0, "uptrend")
        config = make_config(levels=[38.2, 50.0, 61.8], tolerance_pct=0.5)

        # Step 1: Price at swing high -> rallying
        s1 = compute_fibonacci_status(
            current_price=140.0,
            swing_structure=structure,
            fib_levels=fib_levels,
            config=config,
            previous_state=None,
        )
        assert s1.status == "rallying"

        # Step 2: Price slightly above 23.6% (133.50) -> pullback_started
        s2 = compute_fibonacci_status(
            current_price=133.50,
            swing_structure=structure,
            fib_levels=fib_levels,
            config=config,
            previous_state=s1,
        )
        assert s2.status == "pullback_started"

        # Step 3: Price below 23.6% level (132.92), around 131.0 -> retracing
        s3 = compute_fibonacci_status(
            current_price=131.0,
            swing_structure=structure,
            fib_levels=fib_levels,
            config=config,
            previous_state=s2,
        )
        assert s3.status == "retracing"

        # Step 4: Price at 38.2% level (128.54) -> at_level, event fired
        s4 = compute_fibonacci_status(
            current_price=128.54,
            swing_structure=structure,
            fib_levels=fib_levels,
            config=config,
            previous_state=s3,
        )
        assert s4.status == "at_level"
        assert any(e["event_type"] == "level_hit" for e in s4.events)

        # Step 5: Price bounces up to 130.0 -> bouncing
        s5 = compute_fibonacci_status(
            current_price=130.0,
            swing_structure=structure,
            fib_levels=fib_levels,
            config=config,
            previous_state=s4,
        )
        assert s5.status == "bouncing"

        # Step 6: Price collapses below swing low (110.0) -> invalidated
        s6 = compute_fibonacci_status(
            current_price=108.0,
            swing_structure=structure,
            fib_levels=fib_levels,
            config=config,
            previous_state=s5,
        )
        assert s6.status == "invalidated"
        assert any(e["event_type"] == "invalidated" for e in s6.events)


# ---------------------------------------------------------------------------
# 18. test_status_at_level_boundary_outside
# ---------------------------------------------------------------------------


class TestStatusAtLevelBoundaryOutside:
    """Price at level_price * 1.0051 (just outside 0.5%) must NOT trigger at_level."""

    def test_status_at_level_boundary_outside(self):
        # Arrange
        structure = make_swing_structure_uptrend(110.0, 140.0)
        fib_levels = calculate_fib_levels(140.0, 110.0, "uptrend")
        config = make_config(levels=[38.2], tolerance_pct=0.5)
        level_price = fib_levels[38.2]  # 128.54

        # Price just outside tolerance: level * 1.0051 (0.51% above)
        price_outside = level_price * 1.0051

        # Act
        state = compute_fibonacci_status(
            current_price=price_outside,
            swing_structure=structure,
            fib_levels=fib_levels,
            config=config,
            previous_state=None,
        )

        # Assert: NOT at_level
        assert state.status != "at_level"
        assert state.events == []


# ---------------------------------------------------------------------------
# 19. test_status_at_level_boundary_inside
# ---------------------------------------------------------------------------


class TestStatusAtLevelBoundaryInside:
    """Price at level_price * 1.0049 (just inside 0.5%) MUST trigger at_level."""

    def test_status_at_level_boundary_inside(self):
        # Arrange
        structure = make_swing_structure_uptrend(110.0, 140.0)
        fib_levels = calculate_fib_levels(140.0, 110.0, "uptrend")
        config = make_config(levels=[38.2], tolerance_pct=0.5)
        level_price = fib_levels[38.2]  # 128.54

        # Price just inside tolerance: level * 1.0049 (0.49% above)
        price_inside = level_price * 1.0049

        # Act
        state = compute_fibonacci_status(
            current_price=price_inside,
            swing_structure=structure,
            fib_levels=fib_levels,
            config=config,
            previous_state=None,
        )

        # Assert: MUST be at_level
        assert state.status == "at_level"
        assert len(state.events) == 1


# ---------------------------------------------------------------------------
# 20. test_transition_no_structure_to_rallying_exact_lookback_boundary
# ---------------------------------------------------------------------------


class TestTransitionNoStructureToRallyingLookbackBoundary:
    """Swing confirmed only after N+lookback bars are available on both sides."""

    def test_transition_no_structure_to_rallying_exact_lookback_boundary(self):
        # Arrange: build data with lookback=5, then slice to just barely have
        # enough bars for swing confirmation
        highs, lows, dates = make_uptrend_data(
            base=110.0, peak=140.0, pullback_to=135.0, lookback=5
        )
        config = make_config(min_swing_pct=10.0)

        # With full data, structure should be found
        structure_full = find_latest_swing_structure(
            highs, lows, dates, lookback=5, min_swing_pct=10.0
        )
        assert structure_full is not None, "Expected structure in full data"

        # Truncate to just the swing low + lookback bars (swing high not yet visible)
        # This simulates not enough data yet
        swing_low_idx = lows.argmin()
        truncated_end = swing_low_idx + 5  # too few bars after the low
        if truncated_end < len(highs):
            h_trunc = highs[:truncated_end]
            l_trunc = lows[:truncated_end]
            d_trunc = dates[:truncated_end]

            structure_trunc = find_latest_swing_structure(
                h_trunc, l_trunc, d_trunc, lookback=5, min_swing_pct=10.0
            )
            # May or may not find structure, but the point is it shouldn't find
            # a confirmed swing high that requires lookback bars after it
            # If found, confirm its index is within valid range
            if structure_trunc is not None:
                n_trunc = len(h_trunc)
                assert structure_trunc.high.index <= n_trunc - 5 - 1


# ---------------------------------------------------------------------------
# 21. test_transition_at_level_tolerance_boundary_inclusive
# ---------------------------------------------------------------------------


class TestTransitionAtLevelToleranceBoundaryInclusive:
    """Price at level * 1.00499 triggers; price at level * 1.00501 does not."""

    def test_tolerance_boundary_inclusive(self):
        # Arrange
        structure = make_swing_structure_uptrend(110.0, 140.0)
        fib_levels = calculate_fib_levels(140.0, 110.0, "uptrend")
        config = make_config(levels=[38.2], tolerance_pct=0.5)
        level_price = fib_levels[38.2]

        # Price exactly at boundary inclusion (0.499% above level -> inside)
        price_inside = level_price * 1.00499

        state_inside = compute_fibonacci_status(
            current_price=price_inside,
            swing_structure=structure,
            fib_levels=fib_levels,
            config=config,
            previous_state=None,
        )

        # Price exactly at boundary exclusion (0.501% above level -> outside)
        price_outside = level_price * 1.00501

        state_outside = compute_fibonacci_status(
            current_price=price_outside,
            swing_structure=structure,
            fib_levels=fib_levels,
            config=config,
            previous_state=None,
        )

        # Assert
        assert state_inside.status == "at_level"
        assert state_outside.status != "at_level"


# ---------------------------------------------------------------------------
# 22. test_transition_at_level_fires_exactly_once_on_oscillation
# ---------------------------------------------------------------------------


class TestTransitionAtLevelFiresExactlyOnceOnOscillation:
    """Price crosses the level band 5 times; level_hit event fires exactly once."""

    def test_at_level_fires_exactly_once_on_oscillation(self):
        # Arrange: uptrend 110->140, watch 38.2% level at 128.54
        structure = make_swing_structure_uptrend(110.0, 140.0)
        fib_levels = calculate_fib_levels(140.0, 110.0, "uptrend")
        config = make_config(levels=[38.2], tolerance_pct=0.5)
        level_price = fib_levels[38.2]

        # Prices that oscillate in and out of tolerance band
        # Inside tolerance:  level * 1.001 (0.1% above)
        # Outside tolerance: level * 1.006 (0.6% above, out of 0.5% band)
        inside_price = level_price * 1.001
        outside_price = level_price * 1.006

        prices_sequence = [
            outside_price,  # miss
            inside_price,   # HIT (1st time) -> event fires
            outside_price,  # exit band
            inside_price,   # re-enter (already triggered) -> no new event
            outside_price,  # exit band
        ]

        total_level_hit_events = 0
        state = None

        # Act: run through the sequence
        for price in prices_sequence:
            state = compute_fibonacci_status(
                current_price=price,
                swing_structure=structure,
                fib_levels=fib_levels,
                config=config,
                previous_state=state,
            )
            total_level_hit_events += sum(
                1 for e in state.events if e["event_type"] == "level_hit"
            )

        # Assert: exactly one level_hit event total
        assert total_level_hit_events == 1


# ---------------------------------------------------------------------------
# 23. test_invalidation_strict_less_than_swing_low
# ---------------------------------------------------------------------------


class TestInvalidationStrictLessThanSwingLow:
    """current_price < swing_low triggers invalidation; == does not."""

    def test_invalidation_strict_less_than_swing_low(self):
        # Arrange
        swing_low = 110.0
        structure = make_swing_structure_uptrend(swing_low_price=swing_low, swing_high_price=140.0)
        fib_levels = calculate_fib_levels(140.0, swing_low, "uptrend")
        config = make_config()

        # Price strictly below swing_low -> invalidated
        state_below = compute_fibonacci_status(
            current_price=swing_low - 0.01,
            swing_structure=structure,
            fib_levels=fib_levels,
            config=config,
            previous_state=None,
        )

        # Price exactly at swing_low -> NOT invalidated
        state_at = compute_fibonacci_status(
            current_price=swing_low,
            swing_structure=structure,
            fib_levels=fib_levels,
            config=config,
            previous_state=None,
        )

        # Assert
        assert state_below.status == "invalidated"
        assert state_at.status != "invalidated"


# ---------------------------------------------------------------------------
# 24. test_invalidation_price_exactly_at_swing_low_no_trigger
# ---------------------------------------------------------------------------


class TestInvalidationPriceExactlyAtSwingLowNoTrigger:
    """Explicit test: price exactly at swing_low is NOT invalidated."""

    def test_invalidation_price_exactly_at_swing_low_no_trigger(self):
        # Arrange: uptrend 110->140, test boundary at exactly 110.0
        swing_low = 110.0
        swing_high = 140.0
        structure = make_swing_structure_uptrend(
            swing_low_price=swing_low, swing_high_price=swing_high
        )
        fib_levels = calculate_fib_levels(swing_high, swing_low, "uptrend")
        config = make_config()

        # Act: price exactly at swing low
        state = compute_fibonacci_status(
            current_price=swing_low,
            swing_structure=structure,
            fib_levels=fib_levels,
            config=config,
            previous_state=None,
        )

        # Assert: strictly NOT invalidated — price at swing_low is still valid
        assert state.status != "invalidated"
        assert not any(e["event_type"] == "invalidated" for e in state.events)
