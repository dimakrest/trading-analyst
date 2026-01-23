"""Cache service for market data with two-level caching.

Implements L1 (in-memory) and L2 (database) caching to minimize API calls.
"""
import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from enum import Enum
from typing import Optional
from zoneinfo import ZoneInfo

from cachetools import TTLCache

from app.services import trading_calendar_service
from app.providers.base import PriceDataPoint
from app.repositories.stock_price import StockPriceRepository

logger = logging.getLogger(__name__)


class CacheHitType(str, Enum):
    """Type of cache hit (for metrics and logging)."""
    L1_HIT = "l1_hit"  # In-memory cache hit
    L2_HIT = "l2_hit"  # Database cache hit
    MISS = "miss"      # Cache miss, need to fetch


@dataclass
class CacheTTLConfig:
    """TTL configuration for different data intervals."""
    daily: int = 86400           # 24 hours
    hourly: int = 3600           # 1 hour
    intraday: int = 300          # 5 minutes
    market_hours_ttl: int = 300  # 5 minutes during market hours
    l1_ttl: int = 30             # 30 seconds for L1 cache
    l1_size: int = 200           # Max symbols in L1 cache


@dataclass
class FreshnessResult:
    """Result of freshness check with market-aware logic."""
    is_fresh: bool
    reason: str
    market_status: str  # "pre_market", "market_open", "after_hours", "closed"
    recommended_ttl: int  # Seconds before next check
    last_data_date: date | None  # Last date in cached data
    last_complete_trading_day: date  # Last day with complete data available
    needs_fetch: bool  # Whether to fetch new data
    fetch_start_date: date | None  # Start date for incremental fetch (if needed)


class MarketDataCache:
    """
    Two-level cache for market data:
    - L1: In-memory (fast, recent, per-instance)
    - L2: Database (persistent, shared, TTL-validated)

    Cache-first flow:
    1. Check L1 (in-memory) → ~1ms
    2. Check L2 (database) with TTL → ~20ms
    3. On miss: caller fetches and stores → ~500ms
    """

    def __init__(
        self,
        repository: StockPriceRepository,
        ttl_config: CacheTTLConfig,
    ):
        self.repository = repository
        self.ttl_config = ttl_config

        # L1: In-memory cache with TTL
        self.l1_cache: TTLCache = TTLCache(
            maxsize=ttl_config.l1_size,
            ttl=ttl_config.l1_ttl
        )

        logger.info(
            f"MarketDataCache initialized: "
            f"L1 size={ttl_config.l1_size}, TTL={ttl_config.l1_ttl}s"
        )

    def _get_l1_key(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime,
        interval: str,
    ) -> str:
        """Generate cache key for L1."""
        return f"{symbol}:{interval}:{start_date.date()}:{end_date.date()}"

    def _get_ttl_for_interval(self, interval: str) -> int:
        """Get appropriate TTL for interval type."""
        intraday_intervals = ["1m", "2m", "5m", "15m", "30m", "60m", "90m", "1h"]
        hourly_intervals = ["1h", "4h"]

        if interval in intraday_intervals:
            return self.ttl_config.intraday
        elif interval in hourly_intervals:
            return self.ttl_config.hourly
        else:
            return self.ttl_config.daily

    async def get(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime,
        interval: str,
    ) -> tuple[list[PriceDataPoint] | None, CacheHitType]:
        """
        Attempt to get data from cache (L1 → L2).

        Returns:
            (data, hit_type) where:
            - data: List of PriceDataPoint or None if cache miss
            - hit_type: CacheHitType indicating where data came from
        """
        cache_key = self._get_l1_key(symbol, start_date, end_date, interval)

        # Check L1 (in-memory)
        if cache_key in self.l1_cache:
            data = self.l1_cache[cache_key]
            logger.debug(f"L1 cache hit: {cache_key}")
            return (data, CacheHitType.L1_HIT)

        # Check L2 (database) with TTL validation
        ttl_seconds = self._get_ttl_for_interval(interval)
        price_records, is_fresh = await self.repository.get_cached_price_data(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            interval=interval,
            ttl_seconds=ttl_seconds,
        )

        if price_records and is_fresh:
            # Convert to PriceDataPoint
            data = [self._record_to_point(record) for record in price_records]

            # Store in L1 for next time
            self.l1_cache[cache_key] = data

            logger.debug(f"L2 cache hit: {cache_key}")
            return (data, CacheHitType.L2_HIT)

        # Cache miss
        logger.debug(f"Cache miss: {cache_key}")
        return (None, CacheHitType.MISS)

    async def set(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime,
        interval: str,
        data: list[PriceDataPoint],
    ) -> None:
        """
        Store data in both cache levels.

        Note: L2 storage is done by caller via repository.
        This method only updates L1 and metadata.
        """
        cache_key = self._get_l1_key(symbol, start_date, end_date, interval)

        # Store in L1
        self.l1_cache[cache_key] = data

        # Update L2 freshness timestamp
        await self.repository.update_last_fetched_at(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            interval=interval,
        )

        logger.debug(f"Cached {len(data)} points: {cache_key}")

    def invalidate(
        self,
        symbol: str,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        interval: str | None = None,
    ) -> None:
        """
        Invalidate cache entries matching criteria.

        If only symbol provided, clears all L1 entries for that symbol.
        L2 invalidation requires database update (handled by caller).
        """
        keys_to_remove = []

        for key in list(self.l1_cache.keys()):
            if key.startswith(f"{symbol}:"):
                keys_to_remove.append(key)

        for key in keys_to_remove:
            del self.l1_cache[key]

        logger.debug(f"Invalidated {len(keys_to_remove)} cache entries for {symbol}")

    async def check_freshness_smart(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime,
        interval: str,
    ) -> FreshnessResult:
        """
        Check cache freshness using market-hours-aware logic.

        Logic:
        1. Determine if this is a historical or live request
        2. For historical (end_date < today): use end_date as reference
        3. For live (end_date >= today): use current time as reference
        4. Check if cached data covers the relevant range

        During market hours (market_open): Use 5-minute TTL, check if today's data exists
        Pre-market/after-hours/closed: Check if data covers up to last_complete_trading_day

        Args:
            symbol: Stock symbol
            start_date: Start date for requested data range
            end_date: End date for requested data range
            interval: Data interval (e.g., "1d", "1h")

        Returns:
            FreshnessResult with freshness status and fetch recommendations
        """
        now = datetime.now(timezone.utc)
        eastern = ZoneInfo("US/Eastern")
        today = now.astimezone(eastern).date()

        # Get market status and last complete trading day based on current time
        market_status = trading_calendar_service.get_market_status(now)
        last_complete_day_now = trading_calendar_service.get_last_complete_trading_day(now)

        # Determine if this is a historical request
        # A request is historical if end_date is before today
        # This ensures "yesterday" requests during market hours are treated as historical
        # Convert end_date to Eastern time to handle UTC midnight edge cases
        # Example: "2025-11-01 01:00 UTC" = "2025-10-31 21:00 EST" (still Oct 31)
        end_date_utc = end_date if end_date.tzinfo else end_date.replace(tzinfo=timezone.utc)
        end_date_eastern = end_date_utc.astimezone(eastern)
        requested_end = end_date_eastern.date()
        is_historical_request = requested_end < today

        if is_historical_request:
            # Historical request: use requested end_date as reference
            # The "last complete trading day" is the last trading day <= requested end_date
            last_complete_day = requested_end
            for _ in range(10):  # Max 10 days back (covers any holiday streak)
                if trading_calendar_service.is_trading_day(last_complete_day):
                    break
                last_complete_day = last_complete_day - timedelta(days=1)
            market_status = "closed"  # Historical data is always "closed"
        else:
            # Live request: use current time as reference (existing behavior)
            last_complete_day = last_complete_day_now

        # Get cached data to check coverage
        price_records = await self.repository.get_price_data_by_date_range(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            interval=interval,
        )

        if not price_records:
            return FreshnessResult(
                is_fresh=False,
                reason="No cached data",
                market_status=market_status,
                recommended_ttl=0,
                last_data_date=None,
                last_complete_trading_day=last_complete_day,
                needs_fetch=True,
                fetch_start_date=start_date.date(),
            )

        # Find the first and last dates in cached data
        last_data_date = max(record.timestamp.date() for record in price_records)
        first_data_date = min(record.timestamp.date() for record in price_records)

        # Check if cache covers the START of the requested range
        # Normalize to first trading day for requests starting on holidays/weekends
        requested_start = start_date.date()
        normalized_start = trading_calendar_service.get_first_trading_day_on_or_after(
            requested_start
        )

        if first_data_date > normalized_start:
            return FreshnessResult(
                is_fresh=False,
                reason=f"Cache missing data before {first_data_date} (requested: {requested_start}, first trading day: {normalized_start})",
                market_status=market_status,
                recommended_ttl=0,
                last_data_date=last_data_date,
                last_complete_trading_day=last_complete_day,
                needs_fetch=True,
                fetch_start_date=requested_start,
            )

        # For historical requests, check if cache covers the requested range
        if is_historical_request:
            if last_data_date >= last_complete_day:
                return FreshnessResult(
                    is_fresh=True,
                    reason=f"Historical data covers requested range (up to {last_data_date})",
                    market_status=market_status,
                    recommended_ttl=86400,  # 24 hours
                    last_data_date=last_data_date,
                    last_complete_trading_day=last_complete_day,
                    needs_fetch=False,
                    fetch_start_date=None,
                )
            else:
                # Missing data within the historical range
                next_needed_day = trading_calendar_service.get_next_trading_day(last_data_date)
                return FreshnessResult(
                    is_fresh=False,
                    reason=f"Historical data missing from {next_needed_day} to {last_complete_day}",
                    market_status=market_status,
                    recommended_ttl=0,
                    last_data_date=last_data_date,
                    last_complete_trading_day=last_complete_day,
                    needs_fetch=True,
                    fetch_start_date=last_data_date,
                )

        # Live request logic: Determine freshness based on market status
        if market_status == "market_open":
            # During market hours: use short TTL for live data
            # Check if we have data for today
            if last_data_date < today:
                # Missing today's data entirely
                return FreshnessResult(
                    is_fresh=False,
                    reason="Missing today's intraday data",
                    market_status=market_status,
                    recommended_ttl=self.ttl_config.market_hours_ttl,
                    last_data_date=last_data_date,
                    last_complete_trading_day=last_complete_day,
                    needs_fetch=True,
                    fetch_start_date=last_data_date,
                )

            # Have today's data, but check TTL for live updates
            latest_fetch = max(record.last_fetched_at for record in price_records)
            ttl_threshold = now - timedelta(seconds=self.ttl_config.market_hours_ttl)

            if latest_fetch >= ttl_threshold:
                return FreshnessResult(
                    is_fresh=True,
                    reason="Data fresh within 5-minute TTL",
                    market_status=market_status,
                    recommended_ttl=self.ttl_config.market_hours_ttl,
                    last_data_date=last_data_date,
                    last_complete_trading_day=last_complete_day,
                    needs_fetch=False,
                    fetch_start_date=None,
                )
            else:
                return FreshnessResult(
                    is_fresh=False,
                    reason="TTL expired during market hours",
                    market_status=market_status,
                    recommended_ttl=self.ttl_config.market_hours_ttl,
                    last_data_date=last_data_date,
                    last_complete_trading_day=last_complete_day,
                    needs_fetch=True,
                    fetch_start_date=last_data_date,
                )

        else:
            # Pre-market, after-hours, or closed
            # Check if data covers up to last complete trading day
            if last_data_date >= last_complete_day:
                return FreshnessResult(
                    is_fresh=True,
                    reason=f"Data covers up to last complete trading day ({last_complete_day})",
                    market_status=market_status,
                    recommended_ttl=86400,  # 24 hours
                    last_data_date=last_data_date,
                    last_complete_trading_day=last_complete_day,
                    needs_fetch=False,
                    fetch_start_date=None,
                )
            else:
                # Missing data for completed trading days
                next_needed_day = trading_calendar_service.get_next_trading_day(last_data_date)
                return FreshnessResult(
                    is_fresh=False,
                    reason=f"Missing data from {next_needed_day} to {last_complete_day}",
                    market_status=market_status,
                    recommended_ttl=0,
                    last_data_date=last_data_date,
                    last_complete_trading_day=last_complete_day,
                    needs_fetch=True,
                    fetch_start_date=last_data_date,  # Small overlap is OK
                )

    def _record_to_point(self, record) -> PriceDataPoint:
        """Convert StockPrice model to PriceDataPoint."""
        return PriceDataPoint(
            symbol=record.symbol,
            timestamp=record.timestamp,
            open_price=record.open_price,
            high_price=record.high_price,
            low_price=record.low_price,
            close_price=record.close_price,
            volume=record.volume,
        )
