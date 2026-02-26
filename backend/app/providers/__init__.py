"""Market data provider abstractions and implementations.

This package provides a provider-agnostic interface for fetching market data,
following the same pattern as BrokerInterface for consistency.

Available providers:
- YahooFinanceProvider: Free market data via Yahoo Finance
- IBDataProvider: Real-time data via Interactive Brokers
- MockMarketDataProvider: Fake data for testing
"""

from app.providers.base import (
    MarketDataProviderInterface,
    PriceDataPoint,
    PriceDataRequest,
    SymbolInfo,
)
from app.providers.ib_data import IBDataProvider
from app.providers.mock import MockMarketDataProvider
from app.providers.yahoo import YahooFinanceProvider

__all__ = [
    "MarketDataProviderInterface",
    "PriceDataPoint",
    "PriceDataRequest",
    "SymbolInfo",
    "YahooFinanceProvider",
    "IBDataProvider",
    "MockMarketDataProvider",
]
