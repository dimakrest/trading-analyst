"""Fibonacci retracement indicator for Trading Analyst.

Provides swing detection, Fibonacci level calculation, and status state machine
for tracking price retracements against detected swing structures.

All monetary calculations use Python Decimal arithmetic to avoid floating-point
drift on real money computations.

Status state machine transitions:
    no_structure -> rallying (valid swing detected, price at/above swing high)
    rallying -> pullback_started (price retreated from swing extreme)
    pullback_started -> retracing (price crossed 23.6% level)
    retracing -> at_level (price within tolerance of a configured level)
    at_level -> bouncing (price moved back toward trend direction)
    any -> invalidated (price broke through swing origin)
"""

import datetime
from dataclasses import dataclass
from dataclasses import field
from decimal import ROUND_HALF_UP
from decimal import Decimal

import numpy as np
from numpy.typing import NDArray


# Standard Fibonacci retracement levels as percentages
FIBONACCI_LEVELS: list[float] = [23.6, 38.2, 50.0, 61.8, 78.6]


@dataclass
class SwingPoint:
    """A detected swing high or low in price data."""

    index: int
    price: float
    date: str


@dataclass
class SwingStructure:
    """A valid high/low swing pair with directional context."""

    high: SwingPoint
    low: SwingPoint
    direction: str  # "uptrend" or "downtrend"


@dataclass
class FibonacciState:
    """Computed Fibonacci retracement state for a given price bar.

    Attributes:
        status: Current lifecycle status (no_structure, rallying, pullback_started,
            retracing, at_level, bouncing, invalidated).
        swing_structure: The most recent valid swing high/low pair, or None.
        fib_levels: Mapping of level percentage to level detail dict.
            Keys are float percentages (e.g., 38.2). Values contain:
            {price: float, status: str ("pending"|"active"|"triggered"),
             triggered_at: str | None}.
        retracement_pct: How far price has retraced from the swing extreme (0-100),
            or None when no structure exists.
        next_level: The next untriggered level deeper than current retracement,
            as {"pct": float, "price": float}, or None.
        current_price: The price used for this computation.
        events: List of event dicts generated during this computation.
            Each event has: event_type, previous_status, new_status,
            price_at_event, details.
    """

    status: str
    swing_structure: SwingStructure | None
    fib_levels: dict[float, dict]
    retracement_pct: float | None
    next_level: dict | None
    current_price: float
    events: list[dict] = field(default_factory=list)


def detect_swing_high(
    highs: NDArray[np.float64],
    dates: list[str],
    lookback: int = 10,
) -> list[SwingPoint]:
    """Detect local swing highs in a price series.

    A swing high is a bar where the high price is strictly greater than all
    bars within `lookback` bars on both sides. Bars within `lookback` of the
    array boundaries are excluded (insufficient context on one side).

    Args:
        highs: Array of high prices.
        dates: Corresponding date strings for each bar (same length as highs).
        lookback: Number of bars on each side required to confirm a swing high.
            Default is 10.

    Returns:
        List of SwingPoint instances sorted by ascending index.

    Raises:
        ValueError: If highs and dates have different lengths.
    """
    highs_array = np.array(highs, dtype=float)

    if len(highs_array) != len(dates):
        raise ValueError(
            f"highs and dates must have same length: "
            f"got {len(highs_array)} and {len(dates)}"
        )

    swing_points: list[SwingPoint] = []
    n = len(highs_array)

    for i in range(lookback, n - lookback):
        candidate = highs_array[i]
        left_window = highs_array[i - lookback : i]
        right_window = highs_array[i + 1 : i + lookback + 1]

        if candidate > np.max(left_window) and candidate > np.max(right_window):
            swing_points.append(SwingPoint(index=i, price=float(candidate), date=dates[i]))

    return swing_points


def detect_swing_low(
    lows: NDArray[np.float64],
    dates: list[str],
    lookback: int = 10,
) -> list[SwingPoint]:
    """Detect local swing lows in a price series.

    A swing low is a bar where the low price is strictly less than all bars
    within `lookback` bars on both sides. Bars within `lookback` of the array
    boundaries are excluded (insufficient context on one side).

    Args:
        lows: Array of low prices.
        dates: Corresponding date strings for each bar (same length as lows).
        lookback: Number of bars on each side required to confirm a swing low.
            Default is 10.

    Returns:
        List of SwingPoint instances sorted by ascending index.

    Raises:
        ValueError: If lows and dates have different lengths.
    """
    lows_array = np.array(lows, dtype=float)

    if len(lows_array) != len(dates):
        raise ValueError(
            f"lows and dates must have same length: "
            f"got {len(lows_array)} and {len(dates)}"
        )

    swing_points: list[SwingPoint] = []
    n = len(lows_array)

    for i in range(lookback, n - lookback):
        candidate = lows_array[i]
        left_window = lows_array[i - lookback : i]
        right_window = lows_array[i + 1 : i + lookback + 1]

        if candidate < np.min(left_window) and candidate < np.min(right_window):
            swing_points.append(SwingPoint(index=i, price=float(candidate), date=dates[i]))

    return swing_points


def find_latest_swing_structure(
    highs: NDArray[np.float64],
    lows: NDArray[np.float64],
    dates: list[str],
    lookback: int = 10,
    min_swing_pct: float = 10.0,
) -> SwingStructure | None:
    """Find the most recent valid swing high and swing low pair.

    Searches from the most recent bars backward to find the latest pair of swing
    high and swing low that satisfies the minimum percentage move requirement.
    The direction is determined by which swing point came later in time:
    - If the swing low has a higher index than the swing high, trend is uptrend
      (price rose from the low to the high — we are looking for pullback entries).
    - If the swing high has a higher index than the swing low, trend is downtrend
      (price fell from the high to the low — we are looking for bounce entries).

    Args:
        highs: Array of high prices.
        lows: Array of low prices.
        dates: Corresponding date strings for each bar.
        lookback: Lookback period for swing point detection. Default is 10.
        min_swing_pct: Minimum percentage move between swing high and swing low
            to qualify as a valid structure. Default is 10.0%.

    Returns:
        SwingStructure with the most recent valid pair, or None if no pair
        meets the minimum move requirement or no swing points are detected.
    """
    swing_highs = detect_swing_high(highs, dates, lookback)
    swing_lows = detect_swing_low(lows, dates, lookback)

    if not swing_highs or not swing_lows:
        return None

    # Try the most recent combinations first (work backward from latest points)
    # We want the pair where both points are as recent as possible.
    # Check pairings starting from the most recently detected points.
    best_structure: SwingStructure | None = None
    best_latest_index = -1

    for sh in reversed(swing_highs):
        for sl in reversed(swing_lows):
            if sh.index == sl.index:
                continue

            # Calculate percentage move
            move_pct = abs(sh.price - sl.price) / sl.price * 100

            if move_pct < min_swing_pct:
                continue

            # Latest index of the two points
            latest_index = max(sh.index, sl.index)

            if latest_index > best_latest_index:
                # Direction: if swing low came before swing high (sl.index < sh.index),
                # price rallied from the low to the high -> uptrend (expect pullback).
                # If swing high came before swing low (sh.index < sl.index),
                # price fell from the high to the low -> downtrend (expect bounce).
                if sl.index < sh.index:
                    direction = "uptrend"
                else:
                    direction = "downtrend"

                best_structure = SwingStructure(high=sh, low=sl, direction=direction)
                best_latest_index = latest_index

    return best_structure


def calculate_fib_levels(
    swing_high: float,
    swing_low: float,
    direction: str,
) -> dict[float, float]:
    """Calculate Fibonacci retracement level prices.

    Uses Python Decimal arithmetic for precision on real money computations.

    For uptrend (price pulled back from swing_high toward swing_low):
        level_price = swing_high - (swing_high - swing_low) * level_pct / 100

    For downtrend (price bounced from swing_low toward swing_high):
        level_price = swing_low + (swing_high - swing_low) * level_pct / 100

    Example (uptrend $110 -> $140):
        23.6% -> $132.92
        38.2% -> $128.54
        50.0% -> $125.00
        61.8% -> $121.46
        78.6% -> $116.42

    Args:
        swing_high: The swing high price.
        swing_low: The swing low price.
        direction: "uptrend" or "downtrend".

    Returns:
        Dict mapping level percentage (float) to level price (float).
        Example: {23.6: 132.92, 38.2: 128.54, ...}

    Raises:
        ValueError: If direction is not "uptrend" or "downtrend".
    """
    if direction not in ("uptrend", "downtrend"):
        raise ValueError(f"direction must be 'uptrend' or 'downtrend', got {direction!r}")

    d_high = Decimal(str(swing_high))
    d_low = Decimal(str(swing_low))
    d_range = d_high - d_low

    result: dict[float, float] = {}

    for level_pct in FIBONACCI_LEVELS:
        d_level = Decimal(str(level_pct))
        d_ratio = d_level / Decimal("100")

        if direction == "uptrend":
            d_price = d_high - d_range * d_ratio
        else:
            d_price = d_low + d_range * d_ratio

        # Round to 2 decimal places (cents precision for stocks)
        d_price = d_price.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        result[level_pct] = float(d_price)

    return result


def compute_fibonacci_status(
    current_price: float,
    swing_structure: SwingStructure | None,
    fib_levels: dict[float, float],
    config: dict,
    previous_state: "FibonacciState | None",
) -> FibonacciState:
    """Compute the current Fibonacci retracement status.

    Implements a state machine that tracks price position relative to the
    detected swing structure and Fibonacci levels. Events are generated when
    the price first hits a configured level or when the structure is invalidated.

    State machine transitions:
        no_structure: When no valid swing structure is detected.
        rallying: Valid swing found, price at or above swing high (uptrend) or
            at or below swing low (downtrend).
        pullback_started: Price has retreated from the swing extreme but has not
            yet reached the 23.6% retracement level.
        retracing: Price is between the 23.6% and 78.6% retracement levels.
        at_level: Price is within tolerance_pct of a configured level (fires once
            per level per swing structure).
        bouncing: Price has moved back toward the trend direction after being
            at_level.
        invalidated: Price broke through the swing origin (below swing_low for
            uptrend, above swing_high for downtrend). Strict less-than boundary.

    Each configured level fires exactly one level_hit event per swing structure.
    Once a level is marked "triggered" in previous_state, it will not fire again
    unless a new swing structure is detected (re-anchoring).

    Args:
        current_price: The current market price.
        swing_structure: The most recently detected swing structure, or None.
        fib_levels: Mapping of level_pct -> level_price from calculate_fib_levels().
        config: Alert configuration dict with keys:
            - levels: list[float] — configured Fibonacci levels to watch
              (e.g., [38.2, 50.0, 61.8])
            - tolerance_pct: float — percentage tolerance for at_level detection
              (e.g., 0.5 means ±0.5%)
            - min_swing_pct: float — minimum swing percentage (used upstream)
        previous_state: The FibonacciState from the previous computation, or None
            for the first computation.

    Returns:
        A new FibonacciState reflecting the current price and structure.
    """
    events: list[dict] = []
    previous_status = previous_state.status if previous_state else None

    # --- No structure case ---
    if swing_structure is None:
        level_state = _build_level_state(fib_levels, previous_state, same_structure=False)
        return FibonacciState(
            status="no_structure",
            swing_structure=None,
            fib_levels=level_state,
            retracement_pct=None,
            next_level=None,
            current_price=current_price,
            events=events,
        )

    tolerance_pct = config.get("tolerance_pct", 0.5)
    configured_levels: list[float] = config.get("levels", [38.2, 50.0, 61.8])

    swing_high = swing_structure.high.price
    swing_low = swing_structure.low.price
    direction = swing_structure.direction

    # Detect whether we have a new swing structure vs the previous one.
    # Re-anchor if swing points have changed.
    same_structure = _is_same_structure(swing_structure, previous_state)

    # Build level tracking state, carrying over triggered flags if same structure
    level_state = _build_level_state(fib_levels, previous_state, same_structure=same_structure)

    # --- Invalidation check (strict less-than for uptrend, strict greater-than for downtrend) ---
    if direction == "uptrend":
        is_invalidated = current_price < swing_low
    else:
        is_invalidated = current_price > swing_high

    if is_invalidated:
        new_status = "invalidated"
        if previous_status != "invalidated":
            events.append({
                "event_type": "invalidated",
                "previous_status": previous_status,
                "new_status": new_status,
                "price_at_event": current_price,
                "details": {
                    "swing_high": swing_high,
                    "swing_low": swing_low,
                    "direction": direction,
                },
            })
        retracement_pct = _compute_retracement_pct(current_price, swing_high, swing_low, direction)
        return FibonacciState(
            status=new_status,
            swing_structure=swing_structure,
            fib_levels=level_state,
            retracement_pct=retracement_pct,
            next_level=None,
            current_price=current_price,
            events=events,
        )

    # --- Compute retracement percentage ---
    retracement_pct = _compute_retracement_pct(current_price, swing_high, swing_low, direction)

    # --- Check if price is at any configured level ---
    at_level_result = _check_at_level(
        current_price=current_price,
        fib_levels=fib_levels,
        configured_levels=configured_levels,
        level_state=level_state,
        tolerance_pct=tolerance_pct,
        previous_status=previous_status,
        events=events,
    )

    if at_level_result is not None:
        # Check if bouncing: was previously at_level and price has moved toward trend
        is_bouncing = _is_bouncing(current_price, direction, previous_state)

        if is_bouncing:
            new_status = "bouncing"
        else:
            new_status = "at_level"

        next_level = _find_next_level(retracement_pct, configured_levels, level_state, fib_levels)
        return FibonacciState(
            status=new_status,
            swing_structure=swing_structure,
            fib_levels=level_state,
            retracement_pct=retracement_pct,
            next_level=next_level,
            current_price=current_price,
            events=events,
        )

    # --- Determine general status based on retracement depth ---
    new_status = _determine_status_by_retracement(
        current_price=current_price,
        retracement_pct=retracement_pct,
        direction=direction,
        swing_high=swing_high,
        swing_low=swing_low,
        previous_status=previous_status,
        previous_state=previous_state,
    )

    next_level = _find_next_level(retracement_pct, configured_levels, level_state, fib_levels)

    return FibonacciState(
        status=new_status,
        swing_structure=swing_structure,
        fib_levels=level_state,
        retracement_pct=retracement_pct,
        next_level=next_level,
        current_price=current_price,
        events=events,
    )


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _compute_retracement_pct(
    current_price: float,
    swing_high: float,
    swing_low: float,
    direction: str,
) -> float:
    """Compute how far price has retraced from the swing extreme.

    For uptrend: measures how far price has fallen from swing_high toward swing_low.
    For downtrend: measures how far price has risen from swing_low toward swing_high.

    Args:
        current_price: Current market price.
        swing_high: Swing high price.
        swing_low: Swing low price.
        direction: "uptrend" or "downtrend".

    Returns:
        Retracement percentage (0-100+). Values above 100 indicate the price
        has gone past the swing origin (invalidation territory).
    """
    price_range = swing_high - swing_low
    if price_range == 0:
        return 0.0

    if direction == "uptrend":
        return (swing_high - current_price) / price_range * 100
    else:
        return (current_price - swing_low) / price_range * 100


def _is_same_structure(
    swing_structure: SwingStructure,
    previous_state: "FibonacciState | None",
) -> bool:
    """Determine whether the swing structure matches the previous state's structure.

    Compares swing high and low indices and direction. If the structure has
    changed (re-anchored), triggered level history should be reset.

    Args:
        swing_structure: Current swing structure.
        previous_state: Previous FibonacciState, or None.

    Returns:
        True if the swing structure is the same as the previous state's structure.
    """
    if previous_state is None or previous_state.swing_structure is None:
        return False

    prev = previous_state.swing_structure
    return (
        prev.high.index == swing_structure.high.index
        and prev.low.index == swing_structure.low.index
        and prev.direction == swing_structure.direction
    )


def _build_level_state(
    fib_levels: dict[float, float],
    previous_state: "FibonacciState | None",
    same_structure: bool,
) -> dict[float, dict]:
    """Build the fib_levels state dict, carrying over triggered flags when appropriate.

    Args:
        fib_levels: Mapping of level_pct -> level_price.
        previous_state: Previous FibonacciState, or None.
        same_structure: If True, carry over triggered status from previous_state.

    Returns:
        Dict mapping level_pct -> {price, status, triggered_at}.
    """
    result: dict[float, dict] = {}

    for level_pct, level_price in fib_levels.items():
        # Start with pending status
        level_detail: dict = {
            "price": level_price,
            "status": "pending",
            "triggered_at": None,
        }

        # Carry over triggered status if same structure
        if (
            same_structure
            and previous_state is not None
            and level_pct in previous_state.fib_levels
        ):
            prev_level = previous_state.fib_levels[level_pct]
            if prev_level.get("status") == "triggered":
                level_detail["status"] = "triggered"
                level_detail["triggered_at"] = prev_level.get("triggered_at")

        result[level_pct] = level_detail

    return result


def _check_at_level(
    current_price: float,
    fib_levels: dict[float, float],
    configured_levels: list[float],
    level_state: dict[float, dict],
    tolerance_pct: float,
    previous_status: str | None,
    events: list[dict],
) -> tuple[float, float] | None:
    """Check if current price is within tolerance of any configured, untriggered level.

    When a level is first hit, marks it as triggered in level_state and appends
    a level_hit event to events. Each level fires only once per swing structure.

    Args:
        current_price: Current market price.
        fib_levels: Mapping of level_pct -> level_price.
        configured_levels: The levels configured in the alert (subset of fib_levels).
        level_state: Mutable dict of level tracking state (modified in place for triggers).
        tolerance_pct: Tolerance percentage for at_level detection.
        previous_status: Status from the previous computation.
        events: Mutable event list (appended to when a level is hit).

    Returns:
        Tuple of (level_pct, level_price) for the first matching level, or None.
    """
    for level_pct in sorted(configured_levels):
        if level_pct not in fib_levels:
            continue

        level_price = fib_levels[level_pct]
        level_detail = level_state.get(level_pct)

        if level_detail is None:
            continue

        # Check if within tolerance
        is_at_level = abs(current_price - level_price) / level_price <= tolerance_pct / 100

        if not is_at_level:
            continue

        # If already triggered for this swing structure, still return at_level
        # but do not fire a new event
        if level_detail.get("status") == "triggered":
            # We are still near this level — report at_level but no new event
            return (level_pct, level_price)

        # First time hitting this level — fire event and mark triggered
        triggered_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
        level_detail["status"] = "triggered"
        level_detail["triggered_at"] = triggered_at

        events.append({
            "event_type": "level_hit",
            "previous_status": previous_status,
            "new_status": "at_level",
            "price_at_event": current_price,
            "details": {
                "level_pct": level_pct,
                "level_price": level_price,
            },
        })
        return (level_pct, level_price)

    return None


def _is_bouncing(
    current_price: float,
    direction: str,
    previous_state: "FibonacciState | None",
) -> bool:
    """Determine if price is bouncing back toward the trend direction.

    A bounce occurs when the previous status was at_level or bouncing, and the
    price is now moving back toward the trend direction.

    For uptrend: price is rising away from the retracement level toward swing_high.
    For downtrend: price is falling away from the retracement level toward swing_low.

    Args:
        current_price: Current market price.
        direction: "uptrend" or "downtrend".
        previous_state: Previous FibonacciState, or None.

    Returns:
        True if the price is bouncing.
    """
    if previous_state is None:
        return False

    if previous_state.status not in ("at_level", "bouncing"):
        return False

    prev_price = previous_state.current_price

    if direction == "uptrend":
        # Bouncing means price is moving up (toward swing_high)
        return current_price > prev_price
    else:
        # Bouncing means price is moving down (toward swing_low)
        return current_price < prev_price


def _determine_status_by_retracement(
    current_price: float,
    retracement_pct: float,
    direction: str,
    swing_high: float,
    swing_low: float,
    previous_status: str | None,
    previous_state: "FibonacciState | None",
) -> str:
    """Determine the non-level status based on retracement depth.

    Called only when price is not at any configured level.

    Args:
        current_price: Current market price.
        retracement_pct: How far price has retraced (0-100+).
        direction: "uptrend" or "downtrend".
        swing_high: Swing high price.
        swing_low: Swing low price.
        previous_status: Previous status string, or None.
        previous_state: Previous FibonacciState, or None.

    Returns:
        Status string: "rallying", "pullback_started", "retracing", or "bouncing".
    """
    # Price still at or beyond the swing extreme (not yet pulled back)
    if direction == "uptrend":
        at_extreme = current_price >= swing_high
    else:
        at_extreme = current_price <= swing_low

    if at_extreme:
        return "rallying"

    # Price has retraced past 78.6% but not invalidated yet
    # (between 78.6% and 100% — deep retracement but not yet below swing_low)
    if retracement_pct >= 78.6:
        # Still technically retracing very deeply, classify as retracing
        return "retracing"

    # Between 23.6% and 78.6% — in retracement zone
    if retracement_pct >= 23.6:
        # Check if bouncing from a previously at_level state
        if previous_status in ("at_level", "bouncing") and previous_state is not None:
            prev_price = previous_state.current_price
            if direction == "uptrend" and current_price > prev_price:
                return "bouncing"
            if direction == "downtrend" and current_price < prev_price:
                return "bouncing"
        return "retracing"

    # Between 0% and 23.6% — just started pulling back
    return "pullback_started"


def _find_next_level(
    retracement_pct: float,
    configured_levels: list[float],
    level_state: dict[float, dict],
    fib_levels: dict[float, float],
) -> dict | None:
    """Find the next untriggered configured level deeper than current retracement.

    Args:
        retracement_pct: Current retracement percentage.
        configured_levels: Configured levels to watch.
        level_state: Current level tracking state.
        fib_levels: Mapping of level_pct -> level_price.

    Returns:
        Dict with {"pct": float, "price": float} for the next level, or None.
    """
    for level_pct in sorted(configured_levels):
        if level_pct <= retracement_pct:
            continue

        level_detail = level_state.get(level_pct)
        if level_detail is None:
            continue

        if level_detail.get("status") == "triggered":
            continue

        level_price = fib_levels.get(level_pct)
        if level_price is None:
            continue

        return {"pct": level_pct, "price": level_price}

    return None
