"""Type definitions for pricing strategies."""

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum


class EntryStrategy(str, Enum):
    """Entry price calculation strategies."""

    CURRENT_PRICE = "current_price"  # Latest closing price (default)
    BREAKOUT_CONFIRMATION = "breakout_confirmation"  # Entry at % offset for confirmation


class ExitStrategy(str, Enum):
    """Exit price calculation strategies."""

    ATR_BASED = "atr_based"  # Stop loss based on ATR multiple


@dataclass
class PricingConfig:
    """Configuration for pricing calculations.

    Attributes:
        entry_strategy: How to calculate entry price
        exit_strategy: How to calculate stop loss
        breakout_offset_pct: Percentage offset for BREAKOUT_CONFIRMATION (default 2.0)
        atr_multiplier: ATR multiplier for stop loss (default 0.5)
    """

    entry_strategy: EntryStrategy = EntryStrategy.CURRENT_PRICE
    exit_strategy: ExitStrategy = ExitStrategy.ATR_BASED
    breakout_offset_pct: float = 2.0
    atr_multiplier: float = 0.5

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON storage."""
        return {
            "entry_strategy": self.entry_strategy.value,
            "exit_strategy": self.exit_strategy.value,
            "breakout_offset_pct": self.breakout_offset_pct,
            "atr_multiplier": self.atr_multiplier,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "PricingConfig":
        """Create from dictionary."""
        return cls(
            entry_strategy=EntryStrategy(data.get("entry_strategy", "current_price")),
            exit_strategy=ExitStrategy(data.get("exit_strategy", "atr_based")),
            breakout_offset_pct=data.get("breakout_offset_pct", 2.0),
            atr_multiplier=data.get("atr_multiplier", 0.5),
        )


@dataclass
class PricingResult:
    """Result of pricing calculations.

    Attributes:
        entry_price: Calculated entry price
        stop_loss: Calculated stop loss price (None if ATR unavailable)
        atr: Average True Range value used for stop loss calculation (None if unavailable)
        entry_strategy: Strategy used for entry
        exit_strategy: Strategy used for exit
    """

    entry_price: Decimal
    stop_loss: Decimal | None  # None if ATR calculation fails
    atr: Decimal | None  # None if ATR calculation fails
    entry_strategy: EntryStrategy
    exit_strategy: ExitStrategy
