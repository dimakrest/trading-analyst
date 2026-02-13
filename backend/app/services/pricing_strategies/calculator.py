"""Pricing calculator for Live 20 analysis."""

import logging
from decimal import Decimal

from app.utils.technical_indicators import calculate_atr_percentage

from .types import EntryStrategy, PricingConfig, PricingResult

logger = logging.getLogger(__name__)


class PricingCalculator:
    """Calculator for entry and exit prices.

    Implements pricing strategies for Live 20 mean reversion analysis:
    - CURRENT_PRICE: Entry at latest closing price
    - BREAKOUT_CONFIRMATION: Entry at % above/below current (confirmation entry)
    - ATR_BASED: Stop loss at entry +/- (multiplier x ATR)
    """

    def __init__(self, config: PricingConfig | None = None):
        """Initialize calculator with configuration.

        Args:
            config: Pricing configuration. Uses defaults if not provided.
        """
        self.config = config or PricingConfig()

    def calculate(
        self,
        direction: str,
        closes: list[float],
        highs: list[float],
        lows: list[float],
    ) -> PricingResult | None:
        """Calculate entry and stop loss prices.

        Args:
            direction: Trade direction ("LONG", "SHORT", or "NO_SETUP")
            closes: List of closing prices (oldest to newest)
            highs: List of high prices
            lows: List of low prices

        Returns:
            PricingResult with calculated prices, or None for NO_SETUP
        """
        # No prices for NO_SETUP
        if direction == "NO_SETUP":
            return None

        current_price = closes[-1]

        # Calculate entry price
        entry_price = self._calculate_entry(direction, current_price)

        # Calculate ATR as percentage using shared utility
        atr_percentage = self._get_latest_atr(highs, lows, closes, entry_price)
        if atr_percentage is None or atr_percentage <= 0:
            # Don't guess - let human define risk if ATR unavailable
            logger.warning("ATR calculation failed - returning None for stop_loss and atr")
            return PricingResult(
                entry_price=Decimal(str(round(entry_price, 4))),
                stop_loss=None,
                atr=None,
                entry_strategy=self.config.entry_strategy,
                exit_strategy=self.config.exit_strategy,
            )

        # Calculate stop loss using ATR percentage
        stop_loss = self._calculate_stop_loss(direction, entry_price, atr_percentage)

        return PricingResult(
            entry_price=Decimal(str(round(entry_price, 4))),
            stop_loss=Decimal(str(round(stop_loss, 4))),
            atr=Decimal(str(round(atr_percentage, 4))),
            entry_strategy=self.config.entry_strategy,
            exit_strategy=self.config.exit_strategy,
        )

    def _calculate_entry(self, direction: str, current_price: float) -> float:
        """Calculate entry price based on strategy.

        Args:
            direction: Trade direction ("LONG" or "SHORT")
            current_price: Current/latest closing price

        Returns:
            Calculated entry price
        """
        if self.config.entry_strategy == EntryStrategy.CURRENT_PRICE:
            return current_price

        # BREAKOUT_CONFIRMATION strategy
        offset_multiplier = self.config.breakout_offset_pct / 100.0

        if direction == "LONG":
            # Buy confirmation above current level
            return current_price * (1 + offset_multiplier)
        else:  # SHORT
            # Sell confirmation below current level
            return current_price * (1 - offset_multiplier)

    def _calculate_stop_loss(
        self, direction: str, entry_price: float, atr_percentage: float
    ) -> float:
        """Calculate stop loss based on ATR percentage.

        Args:
            direction: Trade direction ("LONG" or "SHORT")
            entry_price: Calculated entry price
            atr_percentage: Average True Range as percentage (e.g., 4.25 for 4.25%)

        Returns:
            Calculated stop loss price
        """
        # Convert ATR percentage back to dollars for stop distance calculation
        atr_dollars = (atr_percentage / 100.0) * entry_price
        stop_distance = atr_dollars * self.config.atr_multiplier

        if direction == "LONG":
            # Stop below entry for long positions
            return entry_price - stop_distance
        else:  # SHORT
            # Stop above entry for short positions
            return entry_price + stop_distance

    def _get_latest_atr(
        self,
        highs: list[float],
        lows: list[float],
        closes: list[float],
        current_price: float,
        period: int = 14,
    ) -> float | None:
        """Get latest ATR value as percentage of current price.

        Thin wrapper around calculate_atr_percentage() with error handling.

        Args:
            highs: List of high prices
            lows: List of low prices
            closes: List of closing prices
            current_price: Current/entry price for percentage calculation
            period: ATR period (default 14)

        Returns:
            Latest ATR as percentage, or None if calculation fails
        """
        try:
            return calculate_atr_percentage(
                highs, lows, closes, period, price_override=current_price
            )
        except Exception as e:
            logger.error(f"ATR calculation error: {e}")
            return None
