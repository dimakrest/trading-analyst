"""Integration tests for market-hours-aware cache freshness.

Tests verify the smart caching behavior:
- Market status detection (pre_market, market_open, after_hours, closed)
- Last complete trading day calculation
- Smart freshness checking based on market status and trading calendar
- Incremental fetching when data is incomplete
- Historical vs live data request handling
"""
from datetime import date, datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.repositories.stock_price import StockPriceRepository
from app.services import trading_calendar_service
from app.services.cache_service import CacheTTLConfig, MarketDataCache


# ============================================================================
# Test 1: Trading Calendar Service
# ============================================================================
class TestTradingCalendarService:
    """Test trading calendar service methods for market status detection."""

    def test_get_market_status_pre_market(self):
        """Test pre-market detection (before 9:30 AM ET)."""
        # Monday December 2, 2024 at 8:00 AM ET = 13:00 UTC
        timestamp = datetime(2024, 12, 2, 13, 0, tzinfo=timezone.utc)
        assert trading_calendar_service.get_market_status(timestamp) == "pre_market"

    def test_get_market_status_market_open(self):
        """Test market open detection (9:30 AM - 4:00 PM ET)."""
        # Monday 11:00 AM ET = 16:00 UTC
        timestamp = datetime(2024, 12, 2, 16, 0, tzinfo=timezone.utc)
        assert trading_calendar_service.get_market_status(timestamp) == "market_open"

    def test_get_market_status_after_hours(self):
        """Test after-hours detection (after 4:00 PM ET)."""
        # Monday 5:00 PM ET = 22:00 UTC
        timestamp = datetime(2024, 12, 2, 22, 0, tzinfo=timezone.utc)
        assert trading_calendar_service.get_market_status(timestamp) == "after_hours"

    def test_get_market_status_weekend(self):
        """Test weekend detection."""
        # Saturday December 7, 2024
        timestamp = datetime(2024, 12, 7, 16, 0, tzinfo=timezone.utc)
        assert trading_calendar_service.get_market_status(timestamp) == "closed"

    def test_get_market_status_default_none(self):
        """Test get_market_status with None defaults to current time."""
        # This should not raise an exception
        status = trading_calendar_service.get_market_status(None)
        assert status in ["pre_market", "market_open", "after_hours", "closed"]

    def test_get_last_complete_trading_day_after_hours(self):
        """After market close, today is the last complete day."""
        # Monday December 2, 2024 at 5:00 PM ET = 22:00 UTC
        timestamp = datetime(2024, 12, 2, 22, 0, tzinfo=timezone.utc)
        assert trading_calendar_service.get_last_complete_trading_day(timestamp) == date(2024, 12, 2)

    def test_get_last_complete_trading_day_pre_market(self):
        """Pre-market, previous trading day is complete."""
        # Tuesday December 3, 2024 at 8:00 AM ET = 13:00 UTC
        timestamp = datetime(2024, 12, 3, 13, 0, tzinfo=timezone.utc)
        # Monday Dec 2 should be the last complete day
        assert trading_calendar_service.get_last_complete_trading_day(timestamp) == date(2024, 12, 2)

    def test_get_last_complete_trading_day_during_market(self):
        """During market hours, previous trading day is complete."""
        # Tuesday December 3, 2024 at 11:00 AM ET = 16:00 UTC
        timestamp = datetime(2024, 12, 3, 16, 0, tzinfo=timezone.utc)
        # Monday Dec 2 should be the last complete day
        assert trading_calendar_service.get_last_complete_trading_day(timestamp) == date(2024, 12, 2)

    def test_get_last_complete_trading_day_weekend(self):
        """On weekend, Friday is the last complete day."""
        # Saturday December 7, 2024
        timestamp = datetime(2024, 12, 7, 16, 0, tzinfo=timezone.utc)
        # Friday Dec 6 should be the last complete day
        assert trading_calendar_service.get_last_complete_trading_day(timestamp) == date(2024, 12, 6)

    def test_get_last_complete_trading_day_monday_pre_market(self):
        """Monday pre-market should return previous Friday."""
        # Monday December 9, 2024 at 8:00 AM ET = 13:00 UTC
        timestamp = datetime(2024, 12, 9, 13, 0, tzinfo=timezone.utc)
        # Friday Dec 6 should be the last complete day
        assert trading_calendar_service.get_last_complete_trading_day(timestamp) == date(2024, 12, 6)

    def test_get_last_complete_trading_day_default_none(self):
        """Test get_last_complete_trading_day with None defaults to current time."""
        # This should not raise an exception
        last_day = trading_calendar_service.get_last_complete_trading_day(None)
        assert isinstance(last_day, date)

    def test_get_next_trading_day_weekday(self):
        """Get next trading day from a weekday."""
        # Monday December 2, 2024
        current = date(2024, 12, 2)
        # Next trading day should be Tuesday December 3
        assert trading_calendar_service.get_next_trading_day(current) == date(2024, 12, 3)

    def test_get_next_trading_day_friday(self):
        """Get next trading day from Friday should skip weekend."""
        # Friday December 6, 2024
        current = date(2024, 12, 6)
        # Next trading day should be Monday December 9
        assert trading_calendar_service.get_next_trading_day(current) == date(2024, 12, 9)


# ============================================================================
# Test 2: Smart Freshness Checker
# ============================================================================
class TestSmartFreshnessChecker:
    """Test smart freshness checking logic with market-aware behavior."""

    @pytest.fixture
    def mock_repository(self):
        """Create a mock repository."""
        repo = AsyncMock(spec=StockPriceRepository)
        repo.get_price_data_by_date_range = AsyncMock(return_value=[])
        return repo

    @pytest.fixture
    def cache_with_mock_repo(self, mock_repository):
        """Create cache with mock repository."""
        ttl_config = CacheTTLConfig()
        return MarketDataCache(mock_repository, ttl_config)

    @pytest.mark.asyncio
    async def test_no_cached_data_returns_stale(self, cache_with_mock_repo, mock_repository):
        """When there's no cached data, should return stale result."""
        # Empty cache
        mock_repository.get_price_data_by_date_range.return_value = []

        freshness = await cache_with_mock_repo.check_freshness_smart(
            symbol="AAPL",
            start_date=datetime(2024, 11, 1, tzinfo=timezone.utc),
            end_date=datetime(2024, 12, 3, tzinfo=timezone.utc),
            interval="1d",
        )

        assert not freshness.is_fresh
        assert freshness.reason == "No cached data"
        assert freshness.needs_fetch is True
        assert freshness.last_data_date is None

    @pytest.mark.asyncio
    async def test_fresh_data_pre_market_complete(self, cache_with_mock_repo, mock_repository):
        """Pre-market with all data from previous trading day should be fresh."""
        # Create mock price records covering the requested range (Nov 1 to Dec 2)
        mock_record_start = MagicMock()
        mock_record_start.timestamp = datetime(2024, 11, 1, 21, 0, tzinfo=timezone.utc)
        mock_record_start.last_fetched_at = datetime(2024, 11, 1, 22, 0, tzinfo=timezone.utc)
        mock_record_end = MagicMock()
        mock_record_end.timestamp = datetime(2024, 12, 2, 21, 0, tzinfo=timezone.utc)
        mock_record_end.last_fetched_at = datetime(2024, 12, 2, 22, 0, tzinfo=timezone.utc)
        mock_repository.get_price_data_by_date_range.return_value = [mock_record_start, mock_record_end]

        # Check freshness on Dec 3 pre-market (8 AM ET = 13:00 UTC)
        with patch('app.services.cache_service.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2024, 12, 3, 13, 0, tzinfo=timezone.utc)  # 8 AM ET
            mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)
            mock_datetime.combine = datetime.combine
            mock_datetime.min = datetime.min

            with patch("app.services.cache_service.trading_calendar_service.get_market_status", return_value='pre_market'):
                with patch("app.services.cache_service.trading_calendar_service.get_last_complete_trading_day", return_value=date(2024, 12, 2)):
                    freshness = await cache_with_mock_repo.check_freshness_smart(
                        symbol="AAPL",
                        start_date=datetime(2024, 11, 1, tzinfo=timezone.utc),
                        end_date=datetime(2024, 12, 3, 16, 0, tzinfo=timezone.utc),  # Dec 3 11 AM ET
                        interval="1d",
                    )

                    assert freshness.is_fresh
                    assert freshness.needs_fetch is False
                    assert freshness.market_status == "pre_market"
                    assert freshness.last_data_date == date(2024, 12, 2)
                    assert freshness.last_complete_trading_day == date(2024, 12, 2)
                    assert "covers up to last complete trading day" in freshness.reason

    @pytest.mark.asyncio
    async def test_stale_data_pre_market_missing_day(self, cache_with_mock_repo, mock_repository):
        """Pre-market missing previous trading day should be stale."""
        # Have data from Nov 1 through Dec 1 (missing Dec 2)
        mock_record_start = MagicMock()
        mock_record_start.timestamp = datetime(2024, 11, 1, 21, 0, tzinfo=timezone.utc)
        mock_record_start.last_fetched_at = datetime(2024, 11, 1, 22, 0, tzinfo=timezone.utc)
        mock_record_end = MagicMock()
        mock_record_end.timestamp = datetime(2024, 12, 1, 21, 0, tzinfo=timezone.utc)
        mock_record_end.last_fetched_at = datetime(2024, 12, 1, 22, 0, tzinfo=timezone.utc)
        mock_repository.get_price_data_by_date_range.return_value = [mock_record_start, mock_record_end]

        # Check on Dec 3 pre-market - should need Dec 2
        # Mock datetime.now() to make Dec 3 appear as "today"
        with patch('app.services.cache_service.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2024, 12, 3, 13, 0, tzinfo=timezone.utc)  # 8 AM ET
            mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)
            mock_datetime.combine = datetime.combine
            mock_datetime.min = datetime.min

            with patch("app.services.cache_service.trading_calendar_service.get_market_status", return_value='pre_market'):
                with patch("app.services.cache_service.trading_calendar_service.get_last_complete_trading_day", return_value=date(2024, 12, 2)):
                    with patch("app.services.cache_service.trading_calendar_service.get_next_trading_day", return_value=date(2024, 12, 2)):
                        freshness = await cache_with_mock_repo.check_freshness_smart(
                            symbol="AAPL",
                            start_date=datetime(2024, 11, 1, tzinfo=timezone.utc),
                            end_date=datetime(2024, 12, 3, 16, 0, tzinfo=timezone.utc),  # Dec 3 during trading hours
                            interval="1d",
                        )

                        assert not freshness.is_fresh
                        assert freshness.needs_fetch is True
                        assert freshness.market_status == "pre_market"
                        assert freshness.last_data_date == date(2024, 12, 1)
                        assert freshness.last_complete_trading_day == date(2024, 12, 2)
                        assert freshness.fetch_start_date == date(2024, 12, 1)
                        assert "Missing data from" in freshness.reason

    @pytest.mark.asyncio
    async def test_stale_data_market_open_ttl_expired(self, cache_with_mock_repo, mock_repository):
        """During market hours with expired TTL should be stale."""
        # Have data from Nov 1 through today but fetched > 5 minutes ago
        now = datetime(2024, 12, 3, 16, 0, tzinfo=timezone.utc)  # 11 AM ET
        mock_record_start = MagicMock()
        mock_record_start.timestamp = datetime(2024, 11, 1, 15, 0, tzinfo=timezone.utc)
        mock_record_start.last_fetched_at = now - timedelta(minutes=10)
        mock_record_end = MagicMock()
        mock_record_end.timestamp = datetime(2024, 12, 3, 15, 0, tzinfo=timezone.utc)
        mock_record_end.last_fetched_at = now - timedelta(minutes=10)  # 10 minutes old
        mock_repository.get_price_data_by_date_range.return_value = [mock_record_start, mock_record_end]

        with patch("app.services.cache_service.trading_calendar_service.get_market_status", return_value='market_open'):
            with patch("app.services.cache_service.trading_calendar_service.get_last_complete_trading_day", return_value=date(2024, 12, 2)):
                with patch('app.services.cache_service.datetime') as mock_datetime:
                    mock_datetime.now.return_value = now
                    mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)
                    mock_datetime.combine = datetime.combine
                    mock_datetime.min = datetime.min

                    freshness = await cache_with_mock_repo.check_freshness_smart(
                        symbol="AAPL",
                        start_date=datetime(2024, 11, 1, tzinfo=timezone.utc),
                        end_date=datetime(2024, 12, 3, 16, 0, tzinfo=timezone.utc),  # Dec 3 during trading hours
                        interval="1d",
                    )

                    assert not freshness.is_fresh
                    assert freshness.needs_fetch is True
                    assert freshness.market_status == "market_open"
                    assert freshness.recommended_ttl == 300  # 5 minutes
                    assert "TTL expired during market hours" in freshness.reason

    @pytest.mark.asyncio
    async def test_fresh_data_market_open_recent_fetch(self, cache_with_mock_repo, mock_repository):
        """During market hours with recent fetch should be fresh."""
        # Have data from Nov 1 through today fetched < 5 minutes ago
        now = datetime(2024, 12, 3, 16, 0, tzinfo=timezone.utc)  # 11 AM ET
        mock_record_start = MagicMock()
        mock_record_start.timestamp = datetime(2024, 11, 1, 15, 0, tzinfo=timezone.utc)
        mock_record_start.last_fetched_at = now - timedelta(minutes=2)
        mock_record_end = MagicMock()
        mock_record_end.timestamp = datetime(2024, 12, 3, 15, 0, tzinfo=timezone.utc)
        mock_record_end.last_fetched_at = now - timedelta(minutes=2)  # 2 minutes old
        mock_repository.get_price_data_by_date_range.return_value = [mock_record_start, mock_record_end]

        with patch("app.services.cache_service.trading_calendar_service.get_market_status", return_value='market_open'):
            with patch("app.services.cache_service.trading_calendar_service.get_last_complete_trading_day", return_value=date(2024, 12, 2)):
                with patch('app.services.cache_service.datetime') as mock_datetime:
                    mock_datetime.now.return_value = now
                    mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)
                    mock_datetime.combine = datetime.combine
                    mock_datetime.min = datetime.min

                    freshness = await cache_with_mock_repo.check_freshness_smart(
                        symbol="AAPL",
                        start_date=datetime(2024, 11, 1, tzinfo=timezone.utc),
                        end_date=datetime(2024, 12, 3, 16, 0, tzinfo=timezone.utc),  # Dec 3 during trading hours
                        interval="1d",
                    )

                    assert freshness.is_fresh
                    assert freshness.needs_fetch is False
                    assert freshness.market_status == "market_open"
                    assert freshness.recommended_ttl == 300  # 5 minutes
                    assert "5-minute TTL" in freshness.reason

    @pytest.mark.asyncio
    async def test_stale_data_market_open_missing_today(self, cache_with_mock_repo, mock_repository):
        """During market hours missing today's data should be stale."""
        # Have data from Nov 1 through yesterday (missing today Dec 3)
        mock_record_start = MagicMock()
        mock_record_start.timestamp = datetime(2024, 11, 1, 21, 0, tzinfo=timezone.utc)
        mock_record_start.last_fetched_at = datetime(2024, 11, 1, 22, 0, tzinfo=timezone.utc)
        mock_record_end = MagicMock()
        mock_record_end.timestamp = datetime(2024, 12, 2, 21, 0, tzinfo=timezone.utc)
        mock_record_end.last_fetched_at = datetime(2024, 12, 2, 22, 0, tzinfo=timezone.utc)
        mock_repository.get_price_data_by_date_range.return_value = [mock_record_start, mock_record_end]

        # Mock datetime.now() to make Dec 3 appear as "today"
        with patch('app.services.cache_service.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2024, 12, 3, 16, 0, tzinfo=timezone.utc)  # 11 AM ET
            mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)
            mock_datetime.combine = datetime.combine
            mock_datetime.min = datetime.min

            with patch("app.services.cache_service.trading_calendar_service.get_market_status", return_value='market_open'):
                with patch("app.services.cache_service.trading_calendar_service.get_last_complete_trading_day", return_value=date(2024, 12, 2)):
                    freshness = await cache_with_mock_repo.check_freshness_smart(
                        symbol="AAPL",
                        start_date=datetime(2024, 11, 1, tzinfo=timezone.utc),
                        end_date=datetime(2024, 12, 3, 16, 0, tzinfo=timezone.utc),  # Dec 3 during trading hours
                        interval="1d",
                    )

                    assert not freshness.is_fresh
                    assert freshness.needs_fetch is True
                    assert freshness.market_status == "market_open"
                    assert freshness.last_data_date == date(2024, 12, 2)
                    assert "Missing today's intraday data" in freshness.reason

    @pytest.mark.asyncio
    async def test_fresh_data_after_hours_complete(self, cache_with_mock_repo, mock_repository):
        """After hours with today's data should be fresh."""
        # Have data from Nov 1 through today
        mock_record_start = MagicMock()
        mock_record_start.timestamp = datetime(2024, 11, 1, 21, 0, tzinfo=timezone.utc)
        mock_record_start.last_fetched_at = datetime(2024, 11, 1, 22, 0, tzinfo=timezone.utc)
        mock_record_end = MagicMock()
        mock_record_end.timestamp = datetime(2024, 12, 3, 21, 0, tzinfo=timezone.utc)
        mock_record_end.last_fetched_at = datetime(2024, 12, 3, 22, 0, tzinfo=timezone.utc)
        mock_repository.get_price_data_by_date_range.return_value = [mock_record_start, mock_record_end]

        # Mock datetime.now() to make Dec 3 appear as "today"
        with patch('app.services.cache_service.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2024, 12, 3, 22, 0, tzinfo=timezone.utc)  # 5 PM ET
            mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)
            mock_datetime.combine = datetime.combine
            mock_datetime.min = datetime.min

            with patch("app.services.cache_service.trading_calendar_service.get_market_status", return_value='after_hours'):
                with patch("app.services.cache_service.trading_calendar_service.get_last_complete_trading_day", return_value=date(2024, 12, 3)):
                    freshness = await cache_with_mock_repo.check_freshness_smart(
                        symbol="AAPL",
                        start_date=datetime(2024, 11, 1, tzinfo=timezone.utc),
                        end_date=datetime(2024, 12, 3, 21, 0, tzinfo=timezone.utc),  # Dec 3 after hours
                        interval="1d",
                    )

                    assert freshness.is_fresh
                    assert freshness.needs_fetch is False
                    assert freshness.market_status == "after_hours"
                    assert freshness.recommended_ttl == 86400  # 24 hours
                    assert "covers up to last complete trading day" in freshness.reason

    @pytest.mark.asyncio
    async def test_stale_data_after_hours_missing_today(self, cache_with_mock_repo, mock_repository):
        """After hours missing today's data should be stale."""
        # Have data from Nov 1 through yesterday (missing today Dec 3)
        mock_record_start = MagicMock()
        mock_record_start.timestamp = datetime(2024, 11, 1, 21, 0, tzinfo=timezone.utc)
        mock_record_start.last_fetched_at = datetime(2024, 11, 1, 22, 0, tzinfo=timezone.utc)
        mock_record_end = MagicMock()
        mock_record_end.timestamp = datetime(2024, 12, 2, 21, 0, tzinfo=timezone.utc)
        mock_record_end.last_fetched_at = datetime(2024, 12, 2, 22, 0, tzinfo=timezone.utc)
        mock_repository.get_price_data_by_date_range.return_value = [mock_record_start, mock_record_end]

        # Mock datetime.now() to make Dec 3 appear as "today"
        with patch('app.services.cache_service.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2024, 12, 3, 22, 0, tzinfo=timezone.utc)  # 5 PM ET
            mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)
            mock_datetime.combine = datetime.combine
            mock_datetime.min = datetime.min

            with patch("app.services.cache_service.trading_calendar_service.get_market_status", return_value='after_hours'):
                with patch("app.services.cache_service.trading_calendar_service.get_last_complete_trading_day", return_value=date(2024, 12, 3)):
                    with patch("app.services.cache_service.trading_calendar_service.get_next_trading_day", return_value=date(2024, 12, 3)):
                        freshness = await cache_with_mock_repo.check_freshness_smart(
                            symbol="AAPL",
                            start_date=datetime(2024, 11, 1, tzinfo=timezone.utc),
                            end_date=datetime(2024, 12, 3, 21, 0, tzinfo=timezone.utc),  # Dec 3 after hours
                            interval="1d",
                        )

                        assert not freshness.is_fresh
                        assert freshness.needs_fetch is True
                        assert freshness.market_status == "after_hours"
                        assert freshness.fetch_start_date == date(2024, 12, 2)
                        assert "Missing data from" in freshness.reason

    @pytest.mark.asyncio
    async def test_fresh_data_weekend_complete(self, cache_with_mock_repo, mock_repository):
        """Weekend with Friday's data should be fresh."""
        # Have data from Nov 1 through Friday
        mock_record_start = MagicMock()
        mock_record_start.timestamp = datetime(2024, 11, 1, 21, 0, tzinfo=timezone.utc)
        mock_record_start.last_fetched_at = datetime(2024, 11, 1, 22, 0, tzinfo=timezone.utc)
        mock_record_end = MagicMock()
        mock_record_end.timestamp = datetime(2024, 12, 6, 21, 0, tzinfo=timezone.utc)
        mock_record_end.last_fetched_at = datetime(2024, 12, 6, 22, 0, tzinfo=timezone.utc)
        mock_repository.get_price_data_by_date_range.return_value = [mock_record_start, mock_record_end]

        with patch("app.services.cache_service.trading_calendar_service.get_market_status", return_value='closed'):
            with patch("app.services.cache_service.trading_calendar_service.get_last_complete_trading_day", return_value=date(2024, 12, 6)):
                freshness = await cache_with_mock_repo.check_freshness_smart(
                    symbol="AAPL",
                    start_date=datetime(2024, 11, 1, tzinfo=timezone.utc),
                    end_date=datetime(2024, 12, 8, tzinfo=timezone.utc),
                    interval="1d",
                )

                assert freshness.is_fresh
                assert freshness.needs_fetch is False
                assert freshness.market_status == "closed"
                assert freshness.recommended_ttl == 86400  # 24 hours

    @pytest.mark.asyncio
    async def test_historical_range_respects_end_date(self, cache_with_mock_repo, mock_repository):
        """Test that historical data requests use the requested end date for freshness.

        When requesting historical data (end_date < today), the system should
        validate cache freshness against the requested end date, not the current date.

        Scenario: Today is 2026-01-04, requesting Sept-Oct 2025 data.
        Cache has complete data through 2025-10-31. Should be FRESH.
        """
        # Cache has data from Sept 1 through Oct 31, 2025
        mock_record_start = MagicMock()
        mock_record_start.timestamp = datetime(2025, 9, 1, 16, 0, tzinfo=timezone.utc)
        mock_record_start.last_fetched_at = datetime(2025, 10, 31, 21, 0, tzinfo=timezone.utc)
        mock_record_end = MagicMock()
        mock_record_end.timestamp = datetime(2025, 10, 31, 16, 0, tzinfo=timezone.utc)
        mock_record_end.last_fetched_at = datetime(2025, 10, 31, 21, 0, tzinfo=timezone.utc)
        mock_repository.get_price_data_by_date_range.return_value = [mock_record_start, mock_record_end]

        # Setup: It's January 4, 2026 (today)
        with patch("app.services.cache_service.trading_calendar_service.get_market_status", return_value='closed'):
            with patch("app.services.cache_service.trading_calendar_service.get_last_complete_trading_day", return_value=date(2026, 1, 3)):
                freshness = await cache_with_mock_repo.check_freshness_smart(
                    symbol="AAPL",
                    start_date=datetime(2025, 9, 1, tzinfo=timezone.utc),
                    end_date=datetime(2025, 10, 31, tzinfo=timezone.utc),
                    interval="1d",
                )

                # Should be FRESH because cache covers the requested historical range
                assert freshness.is_fresh is True, f"Expected fresh but got stale: {freshness.reason}"
                assert freshness.needs_fetch is False
                assert "Historical data covers requested range" in freshness.reason


# ============================================================================
# Test 3: Incremental Fetching Behavior
# ============================================================================
class TestIncrementalFetching:
    """Test incremental data fetching behavior with smart freshness."""

    @pytest.fixture
    def mock_repository(self):
        """Create a mock repository."""
        repo = AsyncMock(spec=StockPriceRepository)
        repo.get_price_data_by_date_range = AsyncMock(return_value=[])
        return repo

    @pytest.fixture
    def cache_with_mock_repo(self, mock_repository):
        """Create cache with mock repository."""
        ttl_config = CacheTTLConfig()
        return MarketDataCache(mock_repository, ttl_config)

    @pytest.mark.asyncio
    async def test_incremental_fetch_start_date_calculation(self, cache_with_mock_repo, mock_repository):
        """Should calculate correct fetch_start_date for incremental fetch."""
        # Have data from Nov 1 through Dec 2, missing Dec 3-4
        mock_record_start = MagicMock()
        mock_record_start.timestamp = datetime(2024, 11, 1, 21, 0, tzinfo=timezone.utc)
        mock_record_start.last_fetched_at = datetime(2024, 11, 1, 22, 0, tzinfo=timezone.utc)
        mock_record_end = MagicMock()
        mock_record_end.timestamp = datetime(2024, 12, 2, 21, 0, tzinfo=timezone.utc)
        mock_record_end.last_fetched_at = datetime(2024, 12, 2, 22, 0, tzinfo=timezone.utc)
        mock_repository.get_price_data_by_date_range.return_value = [mock_record_start, mock_record_end]

        # Mock datetime.now() to make Dec 4 appear as "today"
        with patch('app.services.cache_service.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2024, 12, 4, 22, 0, tzinfo=timezone.utc)  # 5 PM ET
            mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)
            mock_datetime.combine = datetime.combine
            mock_datetime.min = datetime.min

            with patch("app.services.cache_service.trading_calendar_service.get_market_status", return_value='after_hours'):
                with patch("app.services.cache_service.trading_calendar_service.get_last_complete_trading_day", return_value=date(2024, 12, 4)):
                    with patch("app.services.cache_service.trading_calendar_service.get_next_trading_day", return_value=date(2024, 12, 3)):
                        freshness = await cache_with_mock_repo.check_freshness_smart(
                            symbol="AAPL",
                            start_date=datetime(2024, 11, 1, tzinfo=timezone.utc),
                            end_date=datetime(2024, 12, 4, 21, 0, tzinfo=timezone.utc),  # Dec 4 after hours
                            interval="1d",
                        )

                        # Should fetch from Dec 2 (small overlap is OK)
                        assert freshness.fetch_start_date == date(2024, 12, 2)
                        assert freshness.last_data_date == date(2024, 12, 2)
                        assert freshness.last_complete_trading_day == date(2024, 12, 4)

    @pytest.mark.asyncio
    async def test_incremental_fetch_with_multiple_records(self, cache_with_mock_repo, mock_repository):
        """Should find the latest date among multiple records."""
        # Have multiple records from Nov 1 through Dec 3, latest is Dec 3
        mock_record_start = MagicMock()
        mock_record_start.timestamp = datetime(2024, 11, 1, 21, 0, tzinfo=timezone.utc)
        mock_record_start.last_fetched_at = datetime(2024, 11, 1, 22, 0, tzinfo=timezone.utc)

        mock_record1 = MagicMock()
        mock_record1.timestamp = datetime(2024, 12, 1, 21, 0, tzinfo=timezone.utc)
        mock_record1.last_fetched_at = datetime(2024, 12, 1, 22, 0, tzinfo=timezone.utc)

        mock_record2 = MagicMock()
        mock_record2.timestamp = datetime(2024, 12, 2, 21, 0, tzinfo=timezone.utc)
        mock_record2.last_fetched_at = datetime(2024, 12, 2, 22, 0, tzinfo=timezone.utc)

        mock_record3 = MagicMock()
        mock_record3.timestamp = datetime(2024, 12, 3, 21, 0, tzinfo=timezone.utc)
        mock_record3.last_fetched_at = datetime(2024, 12, 3, 22, 0, tzinfo=timezone.utc)

        mock_repository.get_price_data_by_date_range.return_value = [
            mock_record_start,
            mock_record1,
            mock_record2,
            mock_record3,
        ]

        with patch("app.services.cache_service.trading_calendar_service.get_market_status", return_value='after_hours'):
            with patch("app.services.cache_service.trading_calendar_service.get_last_complete_trading_day", return_value=date(2024, 12, 5)):
                freshness = await cache_with_mock_repo.check_freshness_smart(
                    symbol="AAPL",
                    start_date=datetime(2024, 11, 1, tzinfo=timezone.utc),
                    end_date=datetime(2024, 12, 5, tzinfo=timezone.utc),
                    interval="1d",
                )

                # Should detect last_data_date as Dec 3
                assert freshness.last_data_date == date(2024, 12, 3)
                assert freshness.fetch_start_date == date(2024, 12, 3)
                assert not freshness.is_fresh
