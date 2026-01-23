"""Trailing stop management for arena positions.

This module provides trailing stop implementations for position management
in arena simulations. Trailing stops move upward with price to lock in profits.
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
