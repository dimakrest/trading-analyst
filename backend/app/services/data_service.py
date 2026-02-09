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
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

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

logger = logging.getLogger(__name__)


@dataclass
class DataServiceConfig:
    """Configuration for DataService operations."""

    max_retries: int = 3
    retry_delay: float = 1.0
    request_timeout: float = 30.0
    max_concurrent_requests: int = 5
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
    - Maintains backward-compatible API

    Two operational modes:
    1. Full mode (session provided): Uses cache and persistence
    2. API-only mode (session=None): Direct provider access only
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
        session: AsyncSession | None = None,
        provider: MarketDataProviderInterface | None = None,
        cache: MarketDataCache | None = None,
        repository: StockPriceRepository | None = None,
        config: DataServiceConfig | None = None,
    ):
        """
        Initialize DataService with dependencies.

        Args:
            session: Database session (optional for API-only mode)
            provider: Market data provider (defaults to Yahoo if None)
            cache: Cache service (created if session provided)
            repository: Repository (created if session provided)
            config: Service configuration (uses defaults if None)
        """
        self.session = session
        self.provider = provider or YahooFinanceProvider()
        self.config = config or DataServiceConfig()
        self.logger = logger

        # Set up repository and cache if session provided
        if session:
            self.repository = repository or StockPriceRepository(session)
            self.cache = cache or self._create_default_cache()
        else:
            self.repository = None
            self.cache = None

        # Semaphore to limit concurrent requests
        self._semaphore = asyncio.Semaphore(self.config.max_concurrent_requests)

    def _create_default_cache(self) -> MarketDataCache:
        """Create cache with default configuration."""
        return MarketDataCache(self.repository, CacheTTLConfig())

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

    def _require_repository(self) -> StockPriceRepository:
        """Ensure repository is available for database operations.

        Raises:
            RuntimeError: If session was not provided during initialization

        Returns:
            StockPriceRepository instance
        """
        if self.repository is None:
            raise RuntimeError(
                "Database session required for this operation. "
                "Initialize DataService with a session to use persistence features."
            )
        return self.repository

    async def validate_symbol(self, symbol: str) -> dict[str, Any]:
        """
        Validate stock symbol via provider.

        This is a pass-through to the provider, maintaining backward
        compatibility with existing code.
        """
        symbol_info = await self.provider.validate_symbol(symbol)

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
            RuntimeError: If session not provided during initialization
            SymbolNotFoundError: If symbol not found
            DataValidationError: If data validation fails
        """
        self._require_repository()

        # Normalize inputs
        symbol = symbol.upper().strip()
        if end_date is None:
            end_date = datetime.now(timezone.utc)
        if start_date is None:
            start_date = end_date - timedelta(days=get_settings().default_history_days)

        cache_key = f"{symbol}:{interval}:{start_date.date()}:{end_date.date()}"

        # Smart cache check (no lock needed)
        fetch_start = start_date
        if not force_refresh and self.cache:
            freshness = await self.cache.check_freshness_smart(
                symbol=symbol,
                start_date=start_date,
                end_date=end_date,
                interval=interval,
            )

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

        # Cache miss — acquire lock for this cache key
        fetch_lock = await self._get_fetch_lock(cache_key)
        async with fetch_lock:
            # Double-check after lock (race condition protection)
            if not force_refresh and self.cache:
                freshness = await self.cache.check_freshness_smart(
                    symbol=symbol,
                    start_date=start_date,
                    end_date=end_date,
                    interval=interval,
                )

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

            # Fetch from provider
            request = PriceDataRequest(
                symbol=symbol,
                start_date=fetch_start,
                end_date=end_date,
                interval=interval,
            )
            price_points = await self.provider.fetch_price_data(request)

            # Store in database (sync_price_data already sets last_fetched_at)
            price_dicts = [self._point_to_dict(point, interval) for point in price_points]
            await self.repository.sync_price_data(
                symbol=symbol,
                new_data=price_dicts,
                interval=interval,
            )

            self.logger.info(f"Fetched and stored {len(price_points)} points for {symbol}")

        # Read full merged range from DB (includes both old + new data)
        price_records = await self.repository.get_price_data_by_date_range(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            interval=interval,
        )
        return [self._record_to_point(r) for r in price_records]

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
