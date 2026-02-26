"""Cache service for market data freshness checking.

Provides smart caching logic that understands market hours and trading days.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

from app.services import trading_calendar_service
from app.repositories.stock_price import StockPriceRepository

if TYPE_CHECKING:
    from app.models.stock import StockPrice

logger = logging.getLogger(__name__)


@dataclass
class CacheTTLConfig:
    """TTL configuration for market data freshness checks."""
    market_hours_ttl: int = 300  # 5 minutes during market hours


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
    cached_records: list[StockPrice] | None = None  # Records from freshness check DB query


class MarketDataCache:
    """
    Market-aware freshness checker for market data.

    Provides smart caching logic that understands market hours and trading days:
    - During market hours: 5-minute TTL for live data
    - Pre/after/closed: Check data covers last complete trading day
    - Historical requests: Check data covers requested range
    - Incremental fetch: Only fetch missing dates when possible
    """

    def __init__(self, repository: StockPriceRepository, ttl_config: CacheTTLConfig):
        self.repository = repository
        self.ttl_config = ttl_config

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
                    cached_records=price_records,
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
                    cached_records=price_records,
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
                    cached_records=price_records,
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
