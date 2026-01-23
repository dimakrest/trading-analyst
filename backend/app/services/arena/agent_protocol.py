"""Agent protocol for arena simulations.

Defines the base interface that all trading agents must implement,
along with core data types for agent communication.
"""
from abc import ABC
from abc import abstractmethod
from dataclasses import dataclass
from datetime import date
from decimal import Decimal


@dataclass
class AgentDecision:
    """Decision made by an agent for a symbol on a given day.

    Represents the output of an agent's evaluation of a trading opportunity.
    """

    symbol: str
    action: str  # "BUY", "HOLD", or "NO_SIGNAL"
    score: int | None = None
    reasoning: str | None = None

    def __post_init__(self) -> None:
        """Validate action field after initialization."""
        valid_actions = {"BUY", "HOLD", "NO_SIGNAL"}
        if self.action not in valid_actions:
            raise ValueError(
                f"Invalid action '{self.action}'. Must be one of: {valid_actions}"
            )


@dataclass
class PriceBar:
    """Single day's OHLCV data.

    Represents one trading day's price and volume information.
    """

    date: date
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int

    def __post_init__(self) -> None:
        """Validate price relationships after initialization."""
        if self.high < self.low:
            raise ValueError(
                f"High price ({self.high}) cannot be less than low price ({self.low})"
            )
        if self.high < self.open or self.high < self.close:
            raise ValueError(f"High price ({self.high}) must be >= open and close")
        if self.low > self.open or self.low > self.close:
            raise ValueError(f"Low price ({self.low}) must be <= open and close")
        if self.volume < 0:
            raise ValueError(f"Volume ({self.volume}) cannot be negative")


class BaseAgent(ABC):
    """Base class for arena trading agents.

    Agents analyze price data and produce trading decisions.
    Currently only Live20 implements this interface.
    """

    def __init__(self, config: dict | None = None) -> None:
        """Initialize agent with optional configuration.

        Args:
            config: Agent-specific configuration dict.
        """
        self._config = config or {}

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable agent name for display in UI."""
        pass

    @property
    @abstractmethod
    def required_lookback_days(self) -> int:
        """Number of historical days needed before first decision.

        This determines how much price history must be loaded
        before the simulation start date.
        """
        pass

    @abstractmethod
    async def evaluate(
        self,
        symbol: str,
        price_history: list[PriceBar],
        current_date: date,
        has_open_position: bool,
    ) -> AgentDecision:
        """Evaluate a symbol and return a trading decision.

        Args:
            symbol: Stock symbol to evaluate
            price_history: Historical price data (oldest to newest)
            current_date: Current simulation date
            has_open_position: Whether we already hold this symbol

        Returns:
            AgentDecision with action, score, and reasoning
        """
        pass
