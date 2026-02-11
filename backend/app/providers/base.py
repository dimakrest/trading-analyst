"""Base provider interface and data models for market data providers.

This module defines the contract that all market data providers must implement,
following the same pattern as BrokerInterface for consistency.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any


@dataclass
class PriceDataRequest:
    """Request for historical price data."""

    symbol: str
    start_date: datetime
    end_date: datetime
    interval: str = "1d"
    include_pre_post: bool = False


@dataclass
class PriceDataPoint:
    """Single OHLCV price data point."""

    symbol: str
    timestamp: datetime
    open_price: Decimal
    high_price: Decimal
    low_price: Decimal
    close_price: Decimal
    volume: int

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for database storage."""
        return {
            "symbol": self.symbol,
            "timestamp": self.timestamp,
            "open_price": self.open_price,
            "high_price": self.high_price,
            "low_price": self.low_price,
            "close_price": self.close_price,
            "volume": self.volume,
            "interval": "1d",  # Will be set by caller
            "data_source": "provider",  # Will be overridden
            "is_validated": False,
        }


@dataclass
class SymbolInfo:
    """Basic information about a stock symbol."""

    symbol: str
    name: str
    currency: str
    exchange: str
    market_cap: float | None = None
    sector: str | None = None
    industry: str | None = None


class MarketDataProviderInterface(ABC):
    """
    Abstract interface for market data providers.

    This interface defines the contract that all market data providers
    (Yahoo Finance, Interactive Brokers, Mock) must implement. Following the same
    pattern as BrokerInterface for consistency.
    """

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the name of this provider (e.g., 'yahoo_finance')."""
        pass

    @property
    @abstractmethod
    def supported_intervals(self) -> list[str]:
        """Return list of supported interval values."""
        pass

    def _validate_price_point(self, point: PriceDataPoint) -> None:
        """Validate OHLCV price constraints.

        Raises:
            DataValidationError: If price data violates constraints

        Args:
            point: PriceDataPoint to validate
        """
        from app.core.exceptions import DataValidationError

        if point.high_price < point.low_price:
            raise DataValidationError(
                f"High price ({point.high_price}) < Low price ({point.low_price})"
            )

        if point.open_price < Decimal("0"):
            raise DataValidationError("Open price cannot be negative")

        if point.close_price < Decimal("0"):
            raise DataValidationError("Close price cannot be negative")

        if point.volume < 0:
            raise DataValidationError("Volume cannot be negative")

    @abstractmethod
    async def get_symbol_info(self, symbol: str) -> SymbolInfo:
        """
        Get comprehensive information about a stock symbol.

        Fetches symbol metadata including name, sector, industry, and exchange.
        Raises SymbolNotFoundError for invalid symbols (validation is a side effect).

        Args:
            symbol: Stock symbol to query (e.g., 'AAPL')

        Returns:
            SymbolInfo with stock metadata

        Raises:
            SymbolNotFoundError: If symbol doesn't exist
            APIError: If provider API fails
        """
        pass

    @abstractmethod
    async def fetch_price_data(self, request: PriceDataRequest) -> list[PriceDataPoint]:
        """
        Fetch historical OHLCV price data.

        Args:
            request: PriceDataRequest with symbol, dates, interval

        Returns:
            List of PriceDataPoint objects sorted by timestamp

        Raises:
            SymbolNotFoundError: If symbol doesn't exist
            DataValidationError: If returned data is invalid
            APIError: If provider API fails after retries
        """
        pass

    @abstractmethod
    async def get_latest_quote(self, symbol: str) -> dict[str, Any]:
        """
        Get the latest real-time quote for a symbol.

        Args:
            symbol: Stock symbol (e.g., 'AAPL')

        Returns:
            Dictionary with quote data (current_price, volume, etc.)

        Raises:
            SymbolNotFoundError: If symbol doesn't exist
            APIError: If provider API fails
        """
        pass
