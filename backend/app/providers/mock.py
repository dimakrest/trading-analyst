"""Mock market data provider for testing.

Generates fake but realistic-looking data without hitting external APIs.
Useful for unit tests, integration tests, and development environments.
"""
import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

from app.providers.base import (
    MarketDataProviderInterface,
    PriceDataPoint,
    PriceDataRequest,
    SymbolInfo,
)

logger = logging.getLogger(__name__)


class MockMarketDataProvider(MarketDataProviderInterface):
    """
    Mock market data provider for testing.

    Generates fake but realistic-looking data without hitting external APIs.
    Useful for:
    - Unit tests that need predictable data
    - Integration tests that don't want external dependencies
    - Development environments without API access
    """

    @property
    def provider_name(self) -> str:
        return "mock"

    @property
    def supported_intervals(self) -> list[str]:
        return ["1m", "5m", "15m", "1h", "1d", "1wk"]

    async def get_symbol_info(self, symbol: str) -> SymbolInfo:
        """Get mock symbol information for testing."""
        return SymbolInfo(
            symbol=symbol.upper(),
            name=f"{symbol.upper()} Corporation",
            currency="USD",
            exchange="MOCK",
            market_cap=1000000000.0,
            sector="Technology",
            industry="Software",
        )

    async def fetch_price_data(self, request: PriceDataRequest) -> list[PriceDataPoint]:
        """Generate fake historical data."""
        price_points = []
        current_date = request.start_date
        base_price = Decimal("100.00")

        while current_date <= request.end_date:
            # Generate fake OHLCV data
            open_price = base_price
            high_price = open_price * Decimal("1.02")
            low_price = open_price * Decimal("0.98")
            close_price = open_price * Decimal("1.01")
            volume = 1000000

            point = PriceDataPoint(
                symbol=request.symbol,
                timestamp=current_date,
                open_price=open_price,
                high_price=high_price,
                low_price=low_price,
                close_price=close_price,
                volume=volume,
            )

            price_points.append(point)

            # Increment date based on interval
            if request.interval == "1d":
                current_date += timedelta(days=1)
            elif request.interval == "1h":
                current_date += timedelta(hours=1)
            else:
                current_date += timedelta(minutes=5)

            # Vary price for next iteration
            base_price = close_price

        logger.info(f"Generated {len(price_points)} mock data points for {request.symbol}")
        return price_points

    async def get_latest_quote(self, symbol: str) -> dict[str, Any]:
        """Return mock quote."""
        return {
            "symbol": symbol.upper(),
            "current_price": 150.25,
            "previous_close": 149.50,
            "open": 150.00,
            "day_high": 151.00,
            "day_low": 149.00,
            "volume": 1000000,
            "timestamp": datetime.now(),
        }
