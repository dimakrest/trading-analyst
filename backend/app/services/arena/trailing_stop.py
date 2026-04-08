"""Trailing stop management for arena positions.

This module provides trailing stop implementations for position management
in arena simulations. Trailing stops move upward with price to lock in profits.

Available implementations:
- FixedPercentTrailingStop: Fixed percentage below the running high.
- AtrTrailingStop: ATR-adaptive percentage, computed once at entry and then
  behaves identically to FixedPercentTrailingStop for subsequent updates.
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import ClassVar


@dataclass
class TrailingStopUpdate:
    """Result of updating a trailing stop.

    Attributes:
        highest_price: Updated highest price since entry
        stop_price: Updated stop price
        stop_triggered: Whether the stop was triggered this update
        trigger_price: Price that triggered the stop (if triggered)
    """

    highest_price: Decimal
    stop_price: Decimal
    stop_triggered: bool
    trigger_price: Decimal | None = None


class FixedPercentTrailingStop:
    """Fixed percentage trailing stop.

    Tracks highest price since entry and triggers when price drops
    by the configured percentage from that high.

    Example: 5% trailing stop with entry at $100:
    - Initial stop: $95 (100 * 0.95)
    - Price rises to $110: Stop moves to $104.50 (110 * 0.95)
    - Price drops to $104: Stop triggers at $104.50

    The stop only moves up, never down, progressively locking in gains.
    """

    def __init__(self, trail_pct: Decimal) -> None:
        """Initialize trailing stop.

        Args:
            trail_pct: Percentage to trail (e.g., Decimal("5.0") for 5%)

        Raises:
            ValueError: If trail_pct is not between 0 and 100 (exclusive).
        """
        if trail_pct <= 0 or trail_pct >= 100:
            msg = f"trail_pct must be between 0 and 100, got {trail_pct}"
            raise ValueError(msg)
        self.trail_pct = trail_pct
        self._trail_multiplier = Decimal("1") - (trail_pct / Decimal("100"))

    def calculate_initial_stop(
        self, entry_price: Decimal
    ) -> tuple[Decimal, Decimal]:
        """Calculate initial stop price on position open.

        Args:
            entry_price: Position entry price

        Returns:
            Tuple of (highest_price, stop_price)
        """
        highest = entry_price
        stop = (highest * self._trail_multiplier).quantize(Decimal("0.0001"))
        return highest, stop

    def update(
        self,
        current_high: Decimal,
        current_low: Decimal,
        previous_highest: Decimal,
        previous_stop: Decimal,
    ) -> TrailingStopUpdate:
        """Update trailing stop based on new price bar.

        Checks if the stop was triggered (current_low <= previous_stop) first.
        If not triggered, updates the highest price and stop if price made new high.
        The stop can only move up, never down.

        Args:
            current_high: Today's high price
            current_low: Today's low price
            previous_highest: Previous highest price since entry
            previous_stop: Previous stop price

        Returns:
            TrailingStopUpdate with new values and trigger status
        """
        # Check if stop was triggered (price went below or touched stop)
        if current_low <= previous_stop:
            return TrailingStopUpdate(
                highest_price=previous_highest,
                stop_price=previous_stop,
                stop_triggered=True,
                trigger_price=previous_stop,  # Exit at stop price
            )

        # Update highest if new high
        new_highest = max(current_high, previous_highest)
        new_stop = (new_highest * self._trail_multiplier).quantize(Decimal("0.0001"))

        # Stop can only move up, never down
        new_stop = max(new_stop, previous_stop)

        return TrailingStopUpdate(
            highest_price=new_highest,
            stop_price=new_stop,
            stop_triggered=False,
        )


def _make_trail_multiplier(trail_pct: Decimal) -> Decimal:
    """Compute the price multiplier for a given trail percentage.

    Args:
        trail_pct: Trailing percentage (e.g., Decimal("5.0") for 5%).

    Returns:
        Multiplier such that stop = highest * multiplier.
    """
    return Decimal("1") - (trail_pct / Decimal("100"))


class AtrTrailingStop:
    """ATR-adaptive trailing stop.

    Sets an initial stop distance proportional to the symbol's ATR%.
    Volatile stocks receive wider stops; calm stocks receive tighter stops.
    After the initial stop is set the update mechanics are identical to
    FixedPercentTrailingStop — the stop only moves up, never down.

    The trail percentage is clamped to [min_pct, max_pct] to prevent
    pathologically tight or wide stops.

    Example: atr_multiplier=2.0, atr_pct=3.5 → trail_pct=7.0%
        - Entry at $100: stop = $93.00
        - Price rises to $110: stop moves to $102.30 (110 * 0.93)
        - Price drops to $101: stop triggers at $102.30 (gap-down handled by caller)

    Attributes:
        atr_multiplier: Multiplier applied to the symbol's ATR%.
        min_pct: Floor for the computed trail percentage.
        max_pct: Ceiling for the computed trail percentage.
    """

    def __init__(
        self,
        atr_multiplier: float = 2.0,
        min_pct: float = 2.0,
        max_pct: float = 10.0,
    ) -> None:
        """Initialize ATR trailing stop parameters.

        Args:
            atr_multiplier: Multiplier applied to ATR% to determine trail distance.
            min_pct: Minimum trail percentage (floor, inclusive).
            max_pct: Maximum trail percentage (ceiling, inclusive).

        Raises:
            ValueError: If atr_multiplier <= 0, min_pct <= 0, max_pct >= 100,
                or min_pct > max_pct.
        """
        if atr_multiplier <= 0:
            msg = f"atr_multiplier must be positive, got {atr_multiplier}"
            raise ValueError(msg)
        if min_pct <= 0:
            msg = f"min_pct must be positive, got {min_pct}"
            raise ValueError(msg)
        if max_pct >= 100:
            msg = f"max_pct must be less than 100, got {max_pct}"
            raise ValueError(msg)
        if min_pct > max_pct:
            msg = f"min_pct ({min_pct}) must not exceed max_pct ({max_pct})"
            raise ValueError(msg)
        self.atr_multiplier = atr_multiplier
        self.min_pct = min_pct
        self.max_pct = max_pct

    def compute_clamped_pct(self, atr_pct: float) -> float:
        """Compute the trail percentage clamped to [min_pct, max_pct].

        This is the single source of truth for the ATR → trail_pct
        conversion. Both ``calculate_initial_stop`` (for actual stop
        placement) and risk-based position sizing call this so the
        sizing math and the stop placement can never diverge.

        Args:
            atr_pct: ATR as a percentage of price (e.g., 3.5 for 3.5%).

        Returns:
            Clamped trail percentage (e.g., 7.0 for 7%).

        Raises:
            ValueError: If atr_pct is not positive.
        """
        if atr_pct <= 0:
            msg = f"atr_pct must be positive, got {atr_pct}"
            raise ValueError(msg)
        raw_pct = self.atr_multiplier * atr_pct
        return max(self.min_pct, min(self.max_pct, raw_pct))

    def calculate_initial_stop(
        self, entry_price: Decimal, atr_pct: float
    ) -> tuple[Decimal, Decimal, Decimal]:
        """Calculate initial stop on position open using the symbol's ATR%.

        Computes trail_pct = atr_multiplier * atr_pct, clamped to
        [min_pct, max_pct], then derives the stop price from that distance.

        Args:
            entry_price: Position entry price.
            atr_pct: ATR as a percentage of price (e.g., 3.5 for 3.5%).

        Returns:
            Tuple of (highest_price, stop_price, trail_pct_decimal) where
            trail_pct_decimal is the clamped percentage stored on the position
            (as a Decimal, e.g., Decimal("7.00") for 7%).

        Raises:
            ValueError: If atr_pct is not positive.
        """
        clamped_pct = self.compute_clamped_pct(atr_pct)
        trail_pct_decimal = Decimal(str(round(clamped_pct, 4)))

        multiplier = _make_trail_multiplier(trail_pct_decimal)
        highest = entry_price
        stop = (highest * multiplier).quantize(Decimal("0.0001"))
        return highest, stop, trail_pct_decimal

    def update(
        self,
        current_high: Decimal,
        current_low: Decimal,
        previous_highest: Decimal,
        previous_stop: Decimal,
        trail_pct: Decimal,
    ) -> TrailingStopUpdate:
        """Update trailing stop based on a new price bar.

        Identical logic to FixedPercentTrailingStop.update() but accepts
        the per-position trail_pct computed at entry rather than using a
        class-level fixed percentage.

        Args:
            current_high: Today's high price.
            current_low: Today's low price.
            previous_highest: Previous highest price since entry.
            previous_stop: Previous stop price.
            trail_pct: Trail percentage stored on the position (Decimal, e.g., 7.0).

        Returns:
            TrailingStopUpdate with new values and trigger status.
        """
        if current_low <= previous_stop:
            return TrailingStopUpdate(
                highest_price=previous_highest,
                stop_price=previous_stop,
                stop_triggered=True,
                trigger_price=previous_stop,
            )

        multiplier = _make_trail_multiplier(trail_pct)
        new_highest = max(current_high, previous_highest)
        new_stop = (new_highest * multiplier).quantize(Decimal("0.0001"))
        new_stop = max(new_stop, previous_stop)

        return TrailingStopUpdate(
            highest_price=new_highest,
            stop_price=new_stop,
            stop_triggered=False,
        )
