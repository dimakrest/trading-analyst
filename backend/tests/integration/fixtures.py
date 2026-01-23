"""Shared fixtures for integration tests.

This module provides common fixtures for API integration testing including
async clients, database setup/teardown, and test data generators.
"""
import asyncio
from collections.abc import AsyncGenerator
from datetime import datetime
from datetime import timedelta
from decimal import Decimal
from typing import Any

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.models.stock_price import StockPrice


@pytest_asyncio.fixture
async def integration_client() -> AsyncGenerator[AsyncClient, None]:
    """Create async HTTP client for integration testing.

    Yields:
        AsyncClient: Configured async HTTP client for API testing
    """
    async with AsyncClient(app=app, base_url="http://testserver") as client:
        yield client


@pytest_asyncio.fixture
async def seed_price_data(db_session: AsyncSession) -> Any:
    """Helper fixture to seed test price data into database.

    Args:
        db_session: Database session fixture

    Returns:
        Async function that seeds price data for a symbol
    """

    async def _seed(
        symbol: str,
        days: int = 120,
        base_price: float = 100.0,
        volatility: float = 0.02,
        start_date: datetime | None = None,
    ) -> list[StockPrice]:
        """Seed price data for a symbol.

        Args:
            symbol: Stock symbol
            days: Number of days of data
            base_price: Starting price
            volatility: Price volatility factor
            start_date: Starting date (default: 120 days ago)

        Returns:
            List of created StockPrice records
        """
        if start_date is None:
            start_date = datetime.utcnow() - timedelta(days=days)

        prices = []
        current_price = base_price

        for i in range(days):
            date = start_date + timedelta(days=i)

            # Simple random walk for price movement
            import random

            price_change = current_price * volatility * random.uniform(-1, 1)
            current_price = max(1.0, current_price + price_change)

            # Generate OHLC data
            high = current_price * (1 + abs(volatility * random.uniform(0, 1)))
            low = current_price * (1 - abs(volatility * random.uniform(0, 1)))
            open_price = current_price * (1 + volatility * random.uniform(-0.5, 0.5))
            close_price = current_price

            volume = int(1000000 * random.uniform(0.5, 2.0))

            stock_price = StockPrice(
                symbol=symbol,
                timestamp=date,
                open_price=Decimal(str(round(open_price, 2))),
                high_price=Decimal(str(round(high, 2))),
                low_price=Decimal(str(round(low, 2))),
                close_price=Decimal(str(round(close_price, 2))),
                volume=volume,
                interval="1d",
                data_source="manual",
                is_validated=True,
            )

            prices.append(stock_price)
            db_session.add(stock_price)

        await db_session.commit()
        await db_session.refresh(prices[0])

        return prices

    return _seed


@pytest_asyncio.fixture
async def seed_pattern_data(symbol: str, db_session: AsyncSession) -> Any:
    """Helper to seed pattern detection data.

    Args:
        symbol: Stock symbol
        db_session: Database session

    Returns:
        Function to seed patterns with specific characteristics
    """

    async def _seed_patterns(
        count: int = 5, pattern_type: str = "ma_crossover", min_confidence: float = 0.7
    ) -> list[dict[str, Any]]:
        """Seed pattern data.

        Args:
            count: Number of patterns to create
            pattern_type: Type of pattern
            min_confidence: Minimum confidence score

        Returns:
            List of created pattern dictionaries
        """
        # This would integrate with the Pattern model once available
        # For now, return empty list as placeholder
        return []

    return _seed_patterns


@pytest.fixture
def sample_ma_crossover_data() -> dict[str, Any]:
    """Generate sample data that contains MA crossover pattern.

    Returns:
        Dictionary with prices, dates, and volumes showing crossover
    """
    import random
    from datetime import UTC

    base_date = datetime.now(UTC) - timedelta(days=120)
    dates = [base_date + timedelta(days=i) for i in range(120)]

    # Create price data with clear MA crossover
    prices = []
    base_price = 100.0

    for i in range(120):
        if i < 50:
            # Downtrend
            price = base_price * (1 - (i / 100) * 0.02)
        elif i < 70:
            # Crossover region
            price = base_price * (0.98 + (i - 50) / 20 * 0.04)
        else:
            # Uptrend after crossover
            price = base_price * (1.02 + (i - 70) / 50 * 0.05)

        # Add some noise
        price *= 1 + random.uniform(-0.01, 0.01)
        prices.append(round(price, 2))

    volumes = [int(1000000 * random.uniform(0.8, 1.2)) for _ in range(120)]

    return {"symbol": "AAPL", "prices": prices, "dates": dates, "volumes": volumes}


@pytest.fixture
def sample_support_resistance_data() -> dict[str, Any]:
    """Generate sample data with support/resistance levels.

    Returns:
        Dictionary with prices showing clear support/resistance
    """
    import random
    from datetime import UTC

    base_date = datetime.now(UTC) - timedelta(days=100)
    dates = [base_date + timedelta(days=i) for i in range(100)]

    # Create price data bouncing off support at 100 and resistance at 110
    prices = []
    support_level = 100.0
    resistance_level = 110.0

    for i in range(100):
        # Oscillate between support and resistance
        cycle_position = (i % 20) / 20.0
        price = support_level + (resistance_level - support_level) * cycle_position

        # Touch levels more precisely every 10 days
        if i % 10 == 0:
            if i % 20 == 0:
                price = support_level + random.uniform(0, 0.5)
            else:
                price = resistance_level - random.uniform(0, 0.5)

        # Add small noise
        price *= 1 + random.uniform(-0.005, 0.005)
        prices.append(round(price, 2))

    volumes = [int(1000000 * random.uniform(0.8, 1.2)) for _ in range(100)]

    return {"symbol": "GOOGL", "prices": prices, "dates": dates, "volumes": volumes}


@pytest_asyncio.fixture
async def cleanup_test_data(db_session: AsyncSession) -> AsyncGenerator[None, None]:
    """Cleanup test data after each integration test.

    Args:
        db_session: Database session

    Yields:
        None
    """
    yield

    # Cleanup after test
    try:
        # Clean up stock prices
        await db_session.execute("TRUNCATE TABLE stock_prices CASCADE")
        # Clean up patterns if table exists
        try:
            await db_session.execute("TRUNCATE TABLE patterns CASCADE")
        except Exception:
            pass  # Table might not exist yet
        await db_session.commit()
    except Exception as e:
        await db_session.rollback()
        # Log but don't fail test
        import logging

        logging.warning(f"Cleanup failed: {e}")