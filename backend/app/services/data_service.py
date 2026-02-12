"""Data service for market data integration with cache-first architecture.

This service provides a comprehensive interface for fetching, validating,
and persisting financial market data. It handles:
- Provider abstraction (Yahoo Finance, Mock, etc.)
- Market-aware caching (database with smart freshness logic)
- Cache-first orchestration to minimize API calls
- Data validation and transformation
- Error handling for external API dependencies
- Integration with StockPriceRepository for persistence
- Timezone handling and data quality assurance
"""
import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, AsyncContextManager

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import (
    APIError,
    DataValidationError,
    SymbolNotFoundError,
)
from app.providers.base import MarketDataProviderInterface, PriceDataPoint, PriceDataRequest
from app.providers.yahoo import YahooFinanceProvider
from app.repositories.stock_price import StockPriceRepository
from app.services.cache_service import MarketDataCache, CacheTTLConfig
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.models.stock_sector import StockSector
from app.constants.sectors import get_sector_etf as map_sector_to_etf

logger = logging.getLogger(__name__)


@dataclass
class DataServiceConfig:
    """Configuration for DataService operations."""

    max_retries: int = 3
    retry_delay: float = 1.0
    request_timeout: float = 30.0
    validate_data: bool = True
    default_interval: str = "1d"
    default_history_days: int = field(default_factory=lambda: get_settings().default_history_days)
    max_history_years: int = 10


class DataService:
    """
    Market data service with cache-first architecture.

    Architecture:
    - Uses injected MarketDataProviderInterface (not hardcoded Yahoo)
    - Uses MarketDataCache for market-aware freshness checking
    - Orchestrates: cache check → provider fetch → repository store
    - Short-lived sessions: DB connections released during external API calls

    Two operational modes:
    1. Full mode (session_factory provided): Uses cache and persistence
    2. API-only mode (session_factory=None): Direct provider access only
    """

    # Valid intervals (inherited from providers, kept for backward compatibility)
    VALID_INTERVALS = {
        "1m",
        "2m",
        "5m",
        "15m",
        "30m",
        "60m",
        "90m",
        "1h",
        "1d",
        "5d",
        "1wk",
        "1mo",
        "3mo",
    }

    # Intervals that require intraday handling
    INTRADAY_INTERVALS = {"1m", "2m", "5m", "15m", "30m", "60m", "90m", "1h"}

    # Class-level locks for fetch coordination (prevents duplicate API calls)
    _fetch_locks: dict[str, asyncio.Lock] = {}
    _lock_manager_lock = asyncio.Lock()

    def __init__(
        self,
        session_factory: Callable[[], AsyncContextManager[AsyncSession]] | None = None,
        provider: MarketDataProviderInterface | None = None,
        config: DataServiceConfig | None = None,
    ):
        """
        Initialize DataService with dependencies.

        Args:
            session_factory: Callable that returns an async context manager yielding
                a database session. Use async_sessionmaker or a custom factory.
                None for API-only mode (no caching/persistence).
            provider: Market data provider (defaults to Yahoo if None)
            config: Service configuration (uses defaults if None)
        """
        self._session_factory = session_factory
        self.provider = provider or YahooFinanceProvider()
        self.config = config or DataServiceConfig()
        self.logger = logger
        self._ttl_config = CacheTTLConfig()

    @staticmethod
    async def _get_fetch_lock(cache_key: str) -> asyncio.Lock:
        """Get or create lock for a cache key.

        This prevents multiple concurrent requests for the same data
        from fetching from provider simultaneously (race condition).

        Args:
            cache_key: Unique cache key for the data request

        Returns:
            asyncio.Lock for this specific cache key
        """
        async with DataService._lock_manager_lock:
            if cache_key not in DataService._fetch_locks:
                DataService._fetch_locks[cache_key] = asyncio.Lock()
            return DataService._fetch_locks[cache_key]

    def _require_session_factory(self) -> None:
        """Ensure session_factory is available for database operations.

        Raises:
            RuntimeError: If session_factory was not provided during initialization
        """
        if self._session_factory is None:
            raise RuntimeError(
                "Session factory required for this operation. "
                "Initialize DataService with a session_factory to use persistence features."
            )

    async def get_symbol_info(self, symbol: str) -> dict[str, Any]:
        """
        Get comprehensive information about a stock symbol.

        Fetches symbol metadata including name, sector, industry, and exchange
        from the configured provider.

        Args:
            symbol: Stock symbol to query (e.g., 'AAPL')

        Returns:
            Dictionary with symbol information:
                - symbol: Normalized stock symbol
                - name: Company name
                - currency: Trading currency
                - exchange: Stock exchange
                - market_cap: Market capitalization (optional)
                - sector: Business sector (optional)
                - industry: Industry classification (optional)

        Raises:
            SymbolNotFoundError: If symbol doesn't exist
            APIError: If provider API fails
        """
        symbol_info = await self.provider.get_symbol_info(symbol)

        # Convert to dict for backward compatibility
        return {
            "symbol": symbol_info.symbol,
            "name": symbol_info.name,
            "currency": symbol_info.currency,
            "exchange": symbol_info.exchange,
            "market_cap": symbol_info.market_cap,
            "sector": symbol_info.sector,
            "industry": symbol_info.industry,
        }

    async def get_sector_etf(self, symbol: str, session: AsyncSession) -> str | None:
        """Get sector ETF for a symbol, using DB cache.

        Checks stock_sectors table first. On cache miss, fetches from Yahoo
        via get_symbol_info(), stores in cache, and returns.

        This is a non-critical operation - returns None on any failure
        to avoid blocking the main flow.

        Args:
            symbol: Stock symbol (e.g., 'AAPL')
            session: Active database session

        Returns:
            SPDR ETF symbol (e.g., 'XLK') or None if not mapped
        """
        symbol = symbol.upper().strip()

        # Check cache
        result = await session.execute(
            select(StockSector).where(StockSector.symbol == symbol)
        )
        cached = result.scalar_one_or_none()
        if cached and cached.name is not None:
            # Full cache hit - all data present
            return cached.sector_etf

        # Cache miss OR partial hit (cached exists but name is NULL) - fetch from provider
        try:
            info = await self.provider.get_symbol_info(symbol)
            sector_etf = map_sector_to_etf(info.sector)

            # Store in cache (idempotent — upsert for both new and partial cache hits)
            stmt = pg_insert(StockSector).values(
                symbol=symbol,
                sector=info.sector,
                sector_etf=sector_etf,
                industry=info.industry,
                name=info.name,
                exchange=info.exchange,
            ).on_conflict_do_update(
                index_elements=["symbol"],
                set_=dict(
                    sector=info.sector,
                    sector_etf=sector_etf,
                    industry=info.industry,
                    name=info.name,
                    exchange=info.exchange,
                )
            )
            await session.execute(stmt)
            await session.flush()

            return sector_etf
        except Exception as e:
            self.logger.warning(f"Failed to fetch sector info for {symbol}: {e}")
            return None

    async def get_price_data(
        self,
        symbol: str,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        interval: str = "1d",
        force_refresh: bool = False,
    ) -> list[PriceDataPoint]:
        """
        Get price data with cache-first logic.

        Sessions are opened only for DB operations and closed before external API calls.

        Flow:
        1. Check freshness (market-aware) — returns cached data if fresh
        2. If stale: acquire lock, double-check, fetch from provider, store in DB
        3. Read full merged range from DB after store

        Race condition protection:
        - Per-cache-key locks prevent duplicate provider fetches
        - Double-check after lock acquisition catches concurrent populates

        Args:
            symbol: Stock symbol (e.g., 'AAPL')
            start_date: Start date (defaults to 1 year ago)
            end_date: End date (defaults to now)
            interval: Data interval (default "1d")
            force_refresh: Skip cache and fetch fresh data

        Returns:
            List of PriceDataPoint objects sorted by timestamp

        Raises:
            RuntimeError: If session_factory not provided during initialization
            SymbolNotFoundError: If symbol not found
            DataValidationError: If data validation fails
        """
        self._require_session_factory()
        # Type assertion: After _require_session_factory(), we know it's not None
        assert self._session_factory is not None

        # Normalize inputs
        symbol = symbol.upper().strip()
        if end_date is None:
            end_date = datetime.now(timezone.utc)
        if start_date is None:
            start_date = end_date - timedelta(days=get_settings().default_history_days)

        cache_key = f"{symbol}:{interval}:{start_date.date()}:{end_date.date()}"

        # --- Phase 1: Cache check (short-lived session) ---
        fetch_start = start_date
        if not force_refresh:
            async with self._session_factory() as session:
                repo = StockPriceRepository(session)
                cache = MarketDataCache(repo, self._ttl_config)
                freshness = await cache.check_freshness_smart(
                    symbol=symbol,
                    start_date=start_date,
                    end_date=end_date,
                    interval=interval,
                )
            # Session closed here — objects detached but scalar attrs accessible

            if freshness.is_fresh and freshness.cached_records is not None:
                self.logger.debug(
                    f"Cache hit for {symbol}: {freshness.reason} "
                    f"(market: {freshness.market_status})"
                )
                return [self._record_to_point(r) for r in freshness.cached_records]

            # Use incremental start date if available
            if freshness.fetch_start_date and freshness.fetch_start_date > start_date.date():
                fetch_start = datetime.combine(
                    freshness.fetch_start_date,
                    datetime.min.time(),
                    tzinfo=timezone.utc,
                )
                self.logger.debug(
                    f"Incremental fetch for {symbol}: {freshness.fetch_start_date} to {end_date.date()}"
                )

        # --- Phase 2: Lock + double-check + fetch + store ---
        fetch_lock = await self._get_fetch_lock(cache_key)
        async with fetch_lock:
            # Double-check after lock (short-lived session)
            if not force_refresh:
                async with self._session_factory() as session:
                    repo = StockPriceRepository(session)
                    cache = MarketDataCache(repo, self._ttl_config)
                    freshness = await cache.check_freshness_smart(
                        symbol=symbol,
                        start_date=start_date,
                        end_date=end_date,
                        interval=interval,
                    )
                # Session closed here

                if freshness.is_fresh and freshness.cached_records is not None:
                    self.logger.debug(
                        f"Cache hit after lock for {symbol}: {freshness.reason} "
                        f"(market: {freshness.market_status})"
                    )
                    return [self._record_to_point(r) for r in freshness.cached_records]

                # Update fetch_start in case it changed
                if freshness.fetch_start_date and freshness.fetch_start_date > start_date.date():
                    fetch_start = datetime.combine(
                        freshness.fetch_start_date,
                        datetime.min.time(),
                        tzinfo=timezone.utc,
                    )

            # --- Yahoo fetch (NO session open!) ---
            request = PriceDataRequest(
                symbol=symbol,
                start_date=fetch_start,
                end_date=end_date,
                interval=interval,
            )
            price_points = await self.provider.fetch_price_data(request)

            # --- Phase 3: Store + read (short-lived session) ---
            price_dicts = [self._point_to_dict(point, interval) for point in price_points]
            async with self._session_factory() as session:
                repo = StockPriceRepository(session)
                await repo.sync_price_data(
                    symbol=symbol,
                    new_data=price_dicts,
                    interval=interval,
                )
                await session.commit()

                self.logger.info(f"Fetched and stored {len(price_points)} points for {symbol}")

                # Read full merged range from DB (includes both old + new data)
                price_records = await repo.get_price_data_by_date_range(
                    symbol=symbol,
                    start_date=start_date,
                    end_date=end_date,
                    interval=interval,
                )
                result = [self._record_to_point(r) for r in price_records]
            # Session closed here

        return result

    @staticmethod
    def _record_to_point(record) -> PriceDataPoint:
        """Convert StockPrice DB record to PriceDataPoint."""
        return PriceDataPoint(
            symbol=record.symbol,
            timestamp=record.timestamp,
            open_price=record.open_price,
            high_price=record.high_price,
            low_price=record.low_price,
            close_price=record.close_price,
            volume=record.volume,
        )

    def _point_to_dict(
        self,
        point: PriceDataPoint,
        interval: str
    ) -> dict[str, Any]:
        """Convert PriceDataPoint to dict for backward compatibility."""
        data = point.to_dict()
        data["interval"] = interval
        data["data_source"] = self.provider.provider_name
        return data
