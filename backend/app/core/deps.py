"""Dependency injection for FastAPI endpoints.

This module provides dependency functions for common resources like database sessions,
configuration settings, and other shared components.
"""
import asyncio
import logging
from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends
from fastapi import HTTPException
from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.brokers.base import BrokerInterface
from app.brokers.ib import IBBroker
from app.brokers.mock import MockBroker
from app.core.config import Settings, get_settings
from app.core.database import get_db_session, get_session_factory
from app.providers.base import MarketDataProviderInterface
from app.providers.ib_data import IBDataProvider
from app.providers.mock import MockMarketDataProvider
from app.providers.yahoo import YahooFinanceProvider
from app.services.data_service import DataService
from app.utils.validation import is_valid_symbol, normalize_symbol

logger = logging.getLogger(__name__)

# Type aliases for cleaner dependency injection
DatabaseSession = Annotated[AsyncSession, Depends(get_db_session)]
AppSettings = Annotated[Settings, Depends(get_settings)]


async def get_database_session() -> AsyncGenerator[AsyncSession, None]:
    """Get database session dependency for FastAPI endpoints.

    This is an alias for the main database session dependency.
    Use this in your FastAPI route handlers.

    Yields:
        AsyncSession: Database session

    Example:
        ```python
        @router.get("/items/")
        async def get_items(db: DatabaseSession):
            # Use db session here
            pass
        ```
    """
    async for session in get_db_session():
        yield session


async def get_app_settings() -> Settings:
    """Get application settings dependency.

    Returns:
        Settings: Application configuration settings

    Example:
        ```python
        @router.get("/info/")
        async def get_app_info(settings: AppSettings):
            return {"app_name": settings.app_name}
        ```
    """
    return get_settings()


async def get_current_user_id() -> int:
    """Get current user ID dependency.

    Returns a default user ID since authentication is intentionally omitted
    for this local-first deployment model.

    Returns:
        int: User ID (always returns 1)

    Design Decision:
        Authentication is intentionally simplified for local-first deployment.
        This system runs on private networks for a small team (2-3 users) in a
        trusted environment. All users share a single user context.

        For future deployments requiring user authentication (if moving beyond
        the trusted local environment), implement OAuth2/JWT token validation
        here.
    """
    return 1


async def get_validated_symbol(symbol: str) -> str:
    """Validate and normalize stock symbol.

    FastAPI dependency that validates symbol format and normalizes it.
    Use this in route handlers to eliminate duplicate validation code.

    Args:
        symbol: Raw symbol from URL path

    Returns:
        Normalized symbol (uppercase, trimmed)

    Raises:
        HTTPException: 400 if symbol format is invalid

    Example:
        ```python
        @router.get("/{symbol}/analysis")
        async def get_analysis(
            symbol: str = Depends(get_validated_symbol),
        ):
            # symbol is already validated and normalized
            pass
        ```
    """
    symbol = normalize_symbol(symbol)
    if not is_valid_symbol(symbol):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid symbol format: {symbol}",
        )
    return symbol


async def get_market_data_provider() -> MarketDataProviderInterface:
    """Get market data provider based on configuration (async dependency).

    This async function returns the appropriate provider implementation based on
    the MARKET_DATA_PROVIDER setting:
    - "yahoo": Returns YahooFinanceProvider (free, real data)
    - "ib": Returns IBDataProvider singleton (real-time data from Interactive Brokers)
    - "mock": Returns MockMarketDataProvider (testing, fake data)

    For IB provider, returns a singleton instance to avoid "client ID already in use"
    errors, as IB Gateway only allows one connection per client_id.

    Returns:
        MarketDataProviderInterface: Configured provider instance

    Raises:
        NotImplementedError: If provider type is not yet implemented
        ValueError: If provider type is unknown

    Example:
        ```python
        @router.get("/stocks/{symbol}/info")
        async def get_symbol_info(
            symbol: str,
            provider: MarketDataProviderInterface = Depends(get_market_data_provider)
        ):
            symbol_info = await provider.get_symbol_info(symbol)
            return symbol_info
        ```
    """
    settings = get_settings()

    if settings.market_data_provider == "yahoo":
        logger.info("Using YahooFinanceProvider for market data")
        return YahooFinanceProvider()

    elif settings.market_data_provider == "ib":
        logger.info("Using IBDataProvider singleton for market data")
        return await get_ib_data_provider()

    elif settings.market_data_provider == "mock":
        logger.info("Using MockMarketDataProvider for market data")
        return MockMarketDataProvider()

    else:
        raise ValueError(
            f"Unknown market data provider: {settings.market_data_provider}. "
            "Valid options: 'yahoo', 'ib', 'mock'"
        )


async def get_data_service(
    session_factory: async_sessionmaker[AsyncSession] = Depends(get_session_factory),
    provider: MarketDataProviderInterface = Depends(get_market_data_provider),
) -> DataService:
    """Get DataService with injected dependencies.

    Dependencies:
    - session_factory: Factory for creating short-lived database sessions
    - provider: Market data provider (Yahoo, Mock, etc.)

    Sessions are created internally by DataService for each DB operation,
    ensuring connections are not held during external API calls.
    """
    return DataService(
        session_factory=session_factory,
        provider=provider,
    )


async def get_broker(
    db: AsyncSession = Depends(get_database_session),
) -> BrokerInterface:
    """Get broker dependency for order execution.

    This function returns the appropriate broker implementation based on
    the BROKER_TYPE configuration setting:
    - "mock": Returns MockBroker (simulates order execution)
    - "ib": Returns IBBroker (Interactive Brokers)

    Args:
        db: Database session for order persistence (used by IBBroker)

    Returns:
        BrokerInterface: Configured broker instance

    Raises:
        ValueError: If broker type is unknown

    Example:
        ```python
        @router.post("/execution/run-cycle")
        async def run_execution_cycle(
            broker: BrokerInterface = Depends(get_broker)
        ):
            # Use broker for order execution
            pass
        ```
    """
    settings = get_settings()

    if settings.broker_type == "mock":
        logger.info("Using MockBroker for order execution")
        return MockBroker()  # MockBroker doesn't need DB
    elif settings.broker_type == "ib":
        logger.info("Using IBBroker for order execution")
        return IBBroker(db=db)  # Pass DB session for order persistence
    else:
        raise ValueError(
            f"Unknown broker type: {settings.broker_type}. "
            "Valid options: 'mock', 'ib'"
        )


# IB Data Provider singleton with thread-safe initialization
_ib_data_provider: IBDataProvider | None = None
_ib_data_provider_lock = asyncio.Lock()


async def get_ib_data_provider() -> IBDataProvider:
    """Get IB data provider instance (singleton with thread-safe initialization).

    Returns a singleton instance of IBDataProvider for fetching real-time
    intraday data from Interactive Brokers.

    This is separate from get_market_data_provider() to allow explicit
    IB provider usage when needed (e.g., for "hot trade" evaluation).

    The singleton is initialized lazily with an asyncio lock to prevent
    race conditions in concurrent access.

    Returns:
        IBDataProvider: Singleton IB data provider instance

    Example:
        ```python
        @router.get("/stocks/{symbol}/intraday")
        async def get_intraday_data(
            symbol: str,
            provider: IBDataProvider = Depends(get_ib_data_provider)
        ):
            # Fetch real-time 15-minute data from IB
            data = await provider.fetch_price_data(...)
            return data
        ```
    """
    global _ib_data_provider
    if _ib_data_provider is None:
        async with _ib_data_provider_lock:
            # Check again after acquiring lock (double-check locking pattern)
            if _ib_data_provider is None:
                _ib_data_provider = IBDataProvider()
    return _ib_data_provider


async def cleanup_ib_data_provider() -> None:
    """Cleanup IB data provider on application shutdown.

    Disconnects from IB Gateway if a connection was established.
    Called by the FastAPI lifespan manager during shutdown.
    """
    global _ib_data_provider
    if _ib_data_provider is not None:
        try:
            await _ib_data_provider.disconnect()
        except Exception as e:
            logger.warning(f"Error disconnecting IB data provider: {e}")
        finally:
            _ib_data_provider = None


# IBBroker singleton with thread-safe initialization
_ib_broker: IBBroker | None = None
_ib_broker_lock = asyncio.Lock()


async def get_ib_broker_singleton() -> IBBroker | None:
    """Get IBBroker singleton instance (thread-safe initialization).

    Returns a singleton instance of IBBroker for trading and status queries.
    This reuses the same connection for both order execution AND status queries,
    following the same pattern as get_ib_data_provider().

    Note: The broker is initialized without a database session for status queries.
    For order execution, use get_broker() which provides a database session.

    Returns:
        IBBroker: Singleton broker instance, or None if broker type is not IB

    Example:
        ```python
        @router.get("/account/status")
        async def get_status(
            broker: IBBroker | None = Depends(get_ib_broker_singleton)
        ):
            if broker and broker.ib.isConnected():
                return {"status": "connected"}
        ```
    """
    settings = get_settings()

    # Return None for non-IB broker types
    if settings.broker_type != "ib":
        return None

    global _ib_broker
    if _ib_broker is None:
        async with _ib_broker_lock:
            # Double-check locking pattern
            if _ib_broker is None:
                # Initialize without DB session for status queries
                # Order execution should use get_broker() with DB session
                # db=None is intentional: status queries are read-only IB API calls
                # that don't persist data (unlike order execution which requires DB)
                _ib_broker = IBBroker(db=None)
    return _ib_broker


async def cleanup_ib_broker() -> None:
    """Cleanup IBBroker on application shutdown.

    Disconnects from IB Gateway if a connection was established.
    Called by the FastAPI lifespan manager during shutdown.
    """
    global _ib_broker
    if _ib_broker is not None:
        try:
            await _ib_broker.disconnect()
        except Exception as e:
            logger.warning(f"Error disconnecting IB broker: {e}")
        finally:
            _ib_broker = None


async def get_account_service(broker: IBBroker | None = Depends(get_ib_broker_singleton)) -> "AccountService":
    """Get AccountService with injected singleton connections.

    Args:
        broker: IBBroker singleton instance (or None if not configured)

    Returns:
        AccountService: Service with broker and data provider singletons
    """
    from app.services.account_service import AccountService

    # Try to get IB data provider, but it's optional (might not be configured)
    data_provider = None
    try:
        data_provider = await get_ib_data_provider()
    except (ValueError, Exception):
        # IB data provider not configured or failed to initialize
        # This is fine - we can still provide broker status
        pass

    return AccountService(broker=broker, data_provider=data_provider)


