"""Unit tests for market-aware cache freshness checking."""
from datetime import date, datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest

from app.repositories.stock_price import StockPriceRepository
from app.services.cache_service import CacheTTLConfig, MarketDataCache


class MockStockPrice:
    """Mock StockPrice model for testing."""

    def __init__(self, symbol: str, timestamp: datetime, last_fetched_at: datetime):
        self.symbol = symbol
        self.timestamp = timestamp
        self.last_fetched_at = last_fetched_at


@pytest.fixture
def mock_repository():
    """Create a mock repository."""
    repo = AsyncMock(spec=StockPriceRepository)
    return repo


@pytest.fixture
def cache_service(mock_repository):
    """Create cache service with mock repository."""
    ttl_config = CacheTTLConfig()
    return MarketDataCache(repository=mock_repository, ttl_config=ttl_config)


class TestSmartFreshnessChecking:
    """Test smart freshness checking with market-aware logic."""

    @pytest.mark.asyncio
    async def test_no_cached_data_returns_stale(
        self, cache_service, mock_repository
    ):
        """No cached data should return stale with needs_fetch=True."""
        # Setup: No data in cache
        mock_repository.get_price_data_by_date_range.return_value = []

        # Execute
        start_date = datetime(2024, 12, 1, tzinfo=timezone.utc)
        end_date = datetime(2024, 12, 3, tzinfo=timezone.utc)

        result = await cache_service.check_freshness_smart(
            symbol="AAPL",
            start_date=start_date,
            end_date=end_date,
            interval="1d",
        )

        # Verify
        assert result.is_fresh is False
        assert result.needs_fetch is True
        assert result.last_data_date is None
        assert result.fetch_start_date == date(2024, 12, 1)
        assert result.reason == "No cached data"

    @pytest.mark.asyncio
    @patch("app.services.cache_service.trading_calendar_service.get_market_status")
    @patch("app.services.cache_service.trading_calendar_service.get_last_complete_trading_day")
    async def test_pre_market_with_complete_data_is_fresh(
        self, mock_last_complete, mock_market_status, cache_service, mock_repository
    ):
        """Pre-market with data covering previous trading day should be fresh."""
        # Setup: Tuesday Dec 3, 8:00 AM ET (pre-market)
        now = datetime(2024, 12, 3, 13, 0, tzinfo=timezone.utc)  # 8:00 AM ET
        mock_market_status.return_value = "pre_market"
        # Last complete trading day is Monday Dec 2
        mock_last_complete.return_value = date(2024, 12, 2)

        # Have data from Dec 1 through Dec 2 (covering requested range start)
        mock_records = [
            MockStockPrice(
                symbol="AAPL",
                timestamp=datetime(2024, 12, 1, 16, 0, tzinfo=timezone.utc),
                last_fetched_at=datetime(2024, 12, 1, 21, 0, tzinfo=timezone.utc),
            ),
            MockStockPrice(
                symbol="AAPL",
                timestamp=datetime(2024, 12, 2, 16, 0, tzinfo=timezone.utc),
                last_fetched_at=datetime(2024, 12, 2, 21, 0, tzinfo=timezone.utc),
            ),
        ]
        mock_repository.get_price_data_by_date_range.return_value = mock_records

        # Execute (with mocked time)
        with patch("app.services.cache_service.datetime") as mock_datetime:
            mock_datetime.now.return_value = now
            mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)
            mock_datetime.combine = datetime.combine
            mock_datetime.min = datetime.min

            result = await cache_service.check_freshness_smart(
                symbol="AAPL",
                start_date=datetime(2024, 12, 1, tzinfo=timezone.utc),
                end_date=datetime(2024, 12, 3, 16, 0, tzinfo=timezone.utc),  # Dec 3 4PM UTC = Dec 3 11AM EST
                interval="1d",
            )

        # Verify
        assert result.is_fresh is True
        assert result.needs_fetch is False
        assert result.last_data_date == date(2024, 12, 2)
        assert result.last_complete_trading_day == date(2024, 12, 2)
        assert "complete trading day" in result.reason
        assert result.recommended_ttl == 86400  # 24 hours

    @pytest.mark.asyncio
    @patch("app.services.cache_service.trading_calendar_service.get_next_trading_day")
    @patch("app.services.cache_service.trading_calendar_service.get_market_status")
    @patch("app.services.cache_service.trading_calendar_service.get_last_complete_trading_day")
    async def test_pre_market_missing_previous_day_is_stale(
        self, mock_last_complete, mock_market_status, mock_next_trading, cache_service, mock_repository
    ):
        """Pre-market missing previous trading day should be stale."""
        # Setup: Wednesday Dec 4, 8:00 AM ET (pre-market)
        mock_market_status.return_value = "pre_market"
        # Last complete trading day is Tuesday Dec 3
        mock_last_complete.return_value = date(2024, 12, 3)
        mock_next_trading.return_value = date(2024, 12, 2)

        # Only have data through Dec 1 (missing Dec 2 and Dec 3)
        mock_records = [
            MockStockPrice(
                symbol="AAPL",
                timestamp=datetime(2024, 12, 1, 16, 0, tzinfo=timezone.utc),
                last_fetched_at=datetime(2024, 12, 1, 21, 0, tzinfo=timezone.utc),
            ),
        ]
        mock_repository.get_price_data_by_date_range.return_value = mock_records

        # Execute
        result = await cache_service.check_freshness_smart(
            symbol="AAPL",
            start_date=datetime(2024, 11, 30, tzinfo=timezone.utc),
            end_date=datetime(2024, 12, 4, tzinfo=timezone.utc),
            interval="1d",
        )

        # Verify
        assert result.is_fresh is False
        assert result.needs_fetch is True
        assert result.last_data_date == date(2024, 12, 1)
        assert result.last_complete_trading_day == date(2024, 12, 3)
        # Reason can be either "missing data before" (start not covered) or "Missing data from" (end not covered)
        assert "missing" in result.reason.lower()
        # fetch_start_date is last_data_date for incremental fetch (start is covered after normalization)
        assert result.fetch_start_date == date(2024, 12, 1)

    @pytest.mark.asyncio
    @patch("app.services.cache_service.trading_calendar_service.get_market_status")
    @patch("app.services.cache_service.trading_calendar_service.get_last_complete_trading_day")
    async def test_market_open_with_recent_fetch_is_fresh(
        self, mock_last_complete, mock_market_status, cache_service, mock_repository
    ):
        """During market hours with recent fetch (within 5 min) should be fresh."""
        # Setup: Monday Dec 2, 11:00 AM ET (market open)
        now = datetime(2024, 12, 2, 16, 0, tzinfo=timezone.utc)  # 11:00 AM ET
        mock_market_status.return_value = "market_open"
        mock_last_complete.return_value = date(2024, 12, 1)

        # Have data from Dec 1 (covering request start) through today, fetched 2 minutes ago
        mock_records = [
            MockStockPrice(
                symbol="AAPL",
                timestamp=datetime(2024, 12, 1, 16, 0, tzinfo=timezone.utc),
                last_fetched_at=now - timedelta(minutes=2),
            ),
            MockStockPrice(
                symbol="AAPL",
                timestamp=datetime(2024, 12, 2, 15, 0, tzinfo=timezone.utc),
                last_fetched_at=now - timedelta(minutes=2),  # 2 min ago
            ),
        ]
        mock_repository.get_price_data_by_date_range.return_value = mock_records

        # Execute (with mocked time)
        with patch("app.services.cache_service.datetime") as mock_datetime:
            mock_datetime.now.return_value = now
            mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)

            result = await cache_service.check_freshness_smart(
                symbol="AAPL",
                start_date=datetime(2024, 12, 1, tzinfo=timezone.utc),
                end_date=datetime(2024, 12, 2, 16, 0, tzinfo=timezone.utc),  # Dec 2 4PM UTC = Dec 2 11AM EST
                interval="1d",
            )

        # Verify
        assert result.is_fresh is True
        assert result.needs_fetch is False
        assert result.market_status == "market_open"
        assert "5-minute TTL" in result.reason
        assert result.recommended_ttl == 300  # 5 minutes

    @pytest.mark.asyncio
    @patch("app.services.cache_service.trading_calendar_service.get_market_status")
    @patch("app.services.cache_service.trading_calendar_service.get_last_complete_trading_day")
    async def test_market_open_with_stale_fetch_is_stale(
        self, mock_last_complete, mock_market_status, cache_service, mock_repository
    ):
        """During market hours with stale fetch (>5 min) should be stale."""
        # Setup: Monday Dec 2, 11:00 AM ET (market open)
        now = datetime(2024, 12, 2, 16, 0, tzinfo=timezone.utc)  # 11:00 AM ET
        mock_market_status.return_value = "market_open"
        mock_last_complete.return_value = date(2024, 12, 1)

        # Have data from Dec 1 through today, but fetched 10 minutes ago (stale)
        mock_records = [
            MockStockPrice(
                symbol="AAPL",
                timestamp=datetime(2024, 12, 1, 16, 0, tzinfo=timezone.utc),
                last_fetched_at=now - timedelta(minutes=10),
            ),
            MockStockPrice(
                symbol="AAPL",
                timestamp=datetime(2024, 12, 2, 15, 0, tzinfo=timezone.utc),
                last_fetched_at=now - timedelta(minutes=10),  # 10 min ago (stale)
            ),
        ]
        mock_repository.get_price_data_by_date_range.return_value = mock_records

        # Execute (with mocked time)
        with patch("app.services.cache_service.datetime") as mock_datetime:
            mock_datetime.now.return_value = now
            mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)

            result = await cache_service.check_freshness_smart(
                symbol="AAPL",
                start_date=datetime(2024, 12, 1, tzinfo=timezone.utc),
                end_date=datetime(2024, 12, 2, 16, 0, tzinfo=timezone.utc),  # Dec 2 4PM UTC = Dec 2 11AM EST
                interval="1d",
            )

        # Verify
        assert result.is_fresh is False
        assert result.needs_fetch is True
        assert result.market_status == "market_open"
        assert "TTL expired" in result.reason
        assert result.fetch_start_date == date(2024, 12, 2)

    @pytest.mark.asyncio
    @patch("app.services.cache_service.trading_calendar_service.get_market_status")
    @patch("app.services.cache_service.trading_calendar_service.get_last_complete_trading_day")
    async def test_market_open_missing_today_data_is_stale(
        self, mock_last_complete, mock_market_status, cache_service, mock_repository
    ):
        """During market hours without today's data should be stale."""
        # Setup: Monday Dec 2, 11:00 AM ET (market open)
        now = datetime(2024, 12, 2, 16, 0, tzinfo=timezone.utc)  # 11:00 AM ET
        mock_market_status.return_value = "market_open"
        mock_last_complete.return_value = date(2024, 12, 1)

        # Only have data through Dec 1 (missing today Dec 2)
        mock_records = [
            MockStockPrice(
                symbol="AAPL",
                timestamp=datetime(2024, 12, 1, 16, 0, tzinfo=timezone.utc),
                last_fetched_at=datetime(2024, 12, 1, 21, 0, tzinfo=timezone.utc),
            ),
        ]
        mock_repository.get_price_data_by_date_range.return_value = mock_records

        # Execute (with mocked time)
        with patch("app.services.cache_service.datetime") as mock_datetime:
            mock_datetime.now.return_value = now
            mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)

            result = await cache_service.check_freshness_smart(
                symbol="AAPL",
                start_date=datetime(2024, 12, 1, tzinfo=timezone.utc),
                end_date=datetime(2024, 12, 2, 16, 0, tzinfo=timezone.utc),  # Dec 2 4PM UTC = Dec 2 11AM EST
                interval="1d",
            )

        # Verify
        assert result.is_fresh is False
        assert result.needs_fetch is True
        assert result.market_status == "market_open"
        assert "Missing today's intraday data" in result.reason
        assert result.last_data_date == date(2024, 12, 1)

    @pytest.mark.asyncio
    @patch("app.services.cache_service.trading_calendar_service.get_market_status")
    @patch("app.services.cache_service.trading_calendar_service.get_last_complete_trading_day")
    async def test_after_hours_with_today_data_is_fresh(
        self, mock_last_complete, mock_market_status, cache_service, mock_repository
    ):
        """After hours with today's data should be fresh."""
        # Setup: Monday Dec 2, 5:00 PM ET (after hours)
        now = datetime(2024, 12, 2, 22, 0, tzinfo=timezone.utc)  # 5:00 PM ET
        mock_market_status.return_value = "after_hours"
        # Today is now complete
        mock_last_complete.return_value = date(2024, 12, 2)

        # Have data from Dec 1 through today Dec 2
        mock_records = [
            MockStockPrice(
                symbol="AAPL",
                timestamp=datetime(2024, 12, 1, 20, 0, tzinfo=timezone.utc),
                last_fetched_at=datetime(2024, 12, 1, 21, 0, tzinfo=timezone.utc),
            ),
            MockStockPrice(
                symbol="AAPL",
                timestamp=datetime(2024, 12, 2, 20, 0, tzinfo=timezone.utc),  # 4PM ET
                last_fetched_at=datetime(2024, 12, 2, 21, 0, tzinfo=timezone.utc),
            ),
        ]
        mock_repository.get_price_data_by_date_range.return_value = mock_records

        # Execute (with mocked time)
        with patch("app.services.cache_service.datetime") as mock_datetime:
            mock_datetime.now.return_value = now
            mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)
            mock_datetime.combine = datetime.combine
            mock_datetime.min = datetime.min

            result = await cache_service.check_freshness_smart(
                symbol="AAPL",
                start_date=datetime(2024, 12, 1, tzinfo=timezone.utc),
                end_date=datetime(2024, 12, 2, 22, 0, tzinfo=timezone.utc),  # Dec 2 10PM UTC = Dec 2 5PM EST
                interval="1d",
            )

        # Verify
        assert result.is_fresh is True
        assert result.needs_fetch is False
        assert result.market_status == "after_hours"
        assert result.last_data_date == date(2024, 12, 2)
        assert result.last_complete_trading_day == date(2024, 12, 2)
        assert "complete trading day" in result.reason

    @pytest.mark.asyncio
    @patch("app.services.cache_service.trading_calendar_service.get_next_trading_day")
    @patch("app.services.cache_service.trading_calendar_service.get_market_status")
    @patch("app.services.cache_service.trading_calendar_service.get_last_complete_trading_day")
    async def test_after_hours_without_today_data_is_stale(
        self, mock_last_complete, mock_market_status, mock_next_trading, cache_service, mock_repository
    ):
        """After hours without today's data should be stale."""
        # Setup: Monday Dec 2, 5:00 PM ET (after hours)
        now = datetime(2024, 12, 2, 22, 0, tzinfo=timezone.utc)  # 5:00 PM ET
        mock_market_status.return_value = "after_hours"
        # Today is now complete
        mock_last_complete.return_value = date(2024, 12, 2)
        mock_next_trading.return_value = date(2024, 12, 2)

        # Only have data through Dec 1 (missing today Dec 2)
        mock_records = [
            MockStockPrice(
                symbol="AAPL",
                timestamp=datetime(2024, 12, 1, 16, 0, tzinfo=timezone.utc),
                last_fetched_at=datetime(2024, 12, 1, 21, 0, tzinfo=timezone.utc),
            ),
        ]
        mock_repository.get_price_data_by_date_range.return_value = mock_records

        # Execute (with mocked time)
        with patch("app.services.cache_service.datetime") as mock_datetime:
            mock_datetime.now.return_value = now
            mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)
            mock_datetime.combine = datetime.combine
            mock_datetime.min = datetime.min

            result = await cache_service.check_freshness_smart(
                symbol="AAPL",
                start_date=datetime(2024, 11, 30, tzinfo=timezone.utc),
                end_date=datetime(2024, 12, 2, 22, 0, tzinfo=timezone.utc),  # Dec 2 10PM UTC = Dec 2 5PM EST
                interval="1d",
            )

        # Verify
        assert result.is_fresh is False
        assert result.needs_fetch is True
        assert result.market_status == "after_hours"
        # Reason can be "missing data before" (start not covered) or "Missing data from" (end not covered)
        assert "missing" in result.reason.lower()
        assert result.last_data_date == date(2024, 12, 1)
        # fetch_start_date is last_data_date for incremental fetch (start is covered after normalization)
        assert result.fetch_start_date == date(2024, 12, 1)

    @pytest.mark.asyncio
    @patch("app.services.cache_service.trading_calendar_service.get_market_status")
    @patch("app.services.cache_service.trading_calendar_service.get_last_complete_trading_day")
    async def test_weekend_with_complete_week_is_fresh(
        self, mock_last_complete, mock_market_status, cache_service, mock_repository
    ):
        """Weekend with data through Friday should be fresh."""
        # Setup: Saturday Dec 7
        now = datetime(2024, 12, 7, 16, 0, tzinfo=timezone.utc)  # 11:00 AM ET
        mock_market_status.return_value = "closed"
        # Last complete trading day is Friday Dec 6
        mock_last_complete.return_value = date(2024, 12, 6)

        # Have data from Dec 1 through Friday Dec 6
        mock_records = [
            MockStockPrice(
                symbol="AAPL",
                timestamp=datetime(2024, 12, 1, 20, 0, tzinfo=timezone.utc),
                last_fetched_at=datetime(2024, 12, 1, 21, 0, tzinfo=timezone.utc),
            ),
            MockStockPrice(
                symbol="AAPL",
                timestamp=datetime(2024, 12, 6, 20, 0, tzinfo=timezone.utc),
                last_fetched_at=datetime(2024, 12, 6, 21, 0, tzinfo=timezone.utc),
            ),
        ]
        mock_repository.get_price_data_by_date_range.return_value = mock_records

        # Execute (with mocked time)
        with patch("app.services.cache_service.datetime") as mock_datetime:
            mock_datetime.now.return_value = now
            mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)
            mock_datetime.combine = datetime.combine
            mock_datetime.min = datetime.min

            result = await cache_service.check_freshness_smart(
                symbol="AAPL",
                start_date=datetime(2024, 12, 1, tzinfo=timezone.utc),
                end_date=datetime(2024, 12, 7, 16, 0, tzinfo=timezone.utc),  # Dec 7 4PM UTC = Dec 7 11AM EST
                interval="1d",
            )

        # Verify
        assert result.is_fresh is True
        assert result.needs_fetch is False
        assert result.market_status == "closed"
        assert result.last_data_date == date(2024, 12, 6)
        assert result.last_complete_trading_day == date(2024, 12, 6)
        assert "complete trading day" in result.reason

    @pytest.mark.asyncio
    @patch("app.services.cache_service.trading_calendar_service.get_next_trading_day")
    @patch("app.services.cache_service.trading_calendar_service.get_market_status")
    @patch("app.services.cache_service.trading_calendar_service.get_last_complete_trading_day")
    async def test_weekend_missing_friday_is_stale(
        self, mock_last_complete, mock_market_status, mock_next_trading, cache_service, mock_repository
    ):
        """Weekend without Friday's data should be stale."""
        # Setup: Saturday Dec 7
        mock_market_status.return_value = "closed"
        # Last complete trading day is Friday Dec 6
        mock_last_complete.return_value = date(2024, 12, 6)
        mock_next_trading.return_value = date(2024, 12, 6)

        # Only have data through Thursday Dec 5 (missing Friday Dec 6)
        mock_records = [
            MockStockPrice(
                symbol="AAPL",
                timestamp=datetime(2024, 12, 5, 20, 0, tzinfo=timezone.utc),
                last_fetched_at=datetime(2024, 12, 5, 21, 0, tzinfo=timezone.utc),
            ),
        ]
        mock_repository.get_price_data_by_date_range.return_value = mock_records

        # Execute
        result = await cache_service.check_freshness_smart(
            symbol="AAPL",
            start_date=datetime(2024, 12, 1, tzinfo=timezone.utc),
            end_date=datetime(2024, 12, 7, tzinfo=timezone.utc),
            interval="1d",
        )

        # Verify
        assert result.is_fresh is False
        assert result.needs_fetch is True
        assert result.market_status == "closed"
        # Reason can be "missing data before" (start not covered) or "Missing data from" (end not covered)
        assert "missing" in result.reason.lower()
        assert result.last_data_date == date(2024, 12, 5)
        # fetch_start_date is last_data_date for incremental fetch (missing end data)
        assert result.fetch_start_date == date(2024, 12, 5)

    @pytest.mark.asyncio
    @patch("app.services.cache_service.trading_calendar_service.get_market_status")
    @patch("app.services.cache_service.trading_calendar_service.get_last_complete_trading_day")
    async def test_partial_cache_coverage_missing_start_range_is_stale(
        self, mock_last_complete, mock_market_status, cache_service, mock_repository
    ):
        """
        Regression test: Cache has Jan 1-15, request is Dec 1 - Jan 15.

        The cache should detect that the START of the requested range
        is not covered and return stale, even if the END is covered.
        """
        # Setup: It's Jan 16, after hours
        mock_market_status.return_value = "after_hours"
        mock_last_complete.return_value = date(2025, 1, 15)

        # Cache only has data from Jan 1 to Jan 15 (missing Dec 1-31)
        mock_records = [
            MockStockPrice(
                symbol="AAPL",
                timestamp=datetime(2025, 1, 1, 16, 0, tzinfo=timezone.utc),
                last_fetched_at=datetime(2025, 1, 1, 21, 0, tzinfo=timezone.utc),
            ),
            MockStockPrice(
                symbol="AAPL",
                timestamp=datetime(2025, 1, 15, 16, 0, tzinfo=timezone.utc),
                last_fetched_at=datetime(2025, 1, 15, 21, 0, tzinfo=timezone.utc),
            ),
        ]
        mock_repository.get_price_data_by_date_range.return_value = mock_records

        # Request data from Dec 1, 2024 to Jan 15, 2025
        result = await cache_service.check_freshness_smart(
            symbol="AAPL",
            start_date=datetime(2024, 12, 1, tzinfo=timezone.utc),
            end_date=datetime(2025, 1, 15, tzinfo=timezone.utc),
            interval="1d",
        )

        # Verify: Should be STALE because Dec 1-31 is missing
        assert result.is_fresh is False
        assert result.needs_fetch is True
        assert result.fetch_start_date == date(2024, 12, 1)  # Fetch from requested start
        assert "missing" in result.reason.lower() or "before" in result.reason.lower()
        assert result.last_data_date == date(2025, 1, 15)

    @pytest.mark.asyncio
    @patch("app.services.cache_service.trading_calendar_service.get_market_status")
    @patch("app.services.cache_service.trading_calendar_service.get_last_complete_trading_day")
    async def test_cache_covers_full_range_is_fresh(
        self, mock_last_complete, mock_market_status, cache_service, mock_repository
    ):
        """Cache covering full requested range should be fresh."""
        # Setup: It's Jan 16, after hours
        mock_market_status.return_value = "after_hours"
        mock_last_complete.return_value = date(2025, 1, 15)

        # Cache has data from Dec 1 to Jan 15 (full coverage)
        mock_records = [
            MockStockPrice(
                symbol="AAPL",
                timestamp=datetime(2024, 12, 1, 16, 0, tzinfo=timezone.utc),
                last_fetched_at=datetime(2024, 12, 1, 21, 0, tzinfo=timezone.utc),
            ),
            MockStockPrice(
                symbol="AAPL",
                timestamp=datetime(2025, 1, 15, 16, 0, tzinfo=timezone.utc),
                last_fetched_at=datetime(2025, 1, 15, 21, 0, tzinfo=timezone.utc),
            ),
        ]
        mock_repository.get_price_data_by_date_range.return_value = mock_records

        # Request data from Dec 1, 2024 to Jan 15, 2025
        result = await cache_service.check_freshness_smart(
            symbol="AAPL",
            start_date=datetime(2024, 12, 1, tzinfo=timezone.utc),
            end_date=datetime(2025, 1, 15, tzinfo=timezone.utc),
            interval="1d",
        )

        # Verify: Should be FRESH because full range is covered
        assert result.is_fresh is True
        assert result.needs_fetch is False
        assert result.last_data_date == date(2025, 1, 15)

    @pytest.mark.asyncio
    @patch("app.services.cache_service.trading_calendar_service.get_market_status")
    @patch("app.services.cache_service.trading_calendar_service.get_last_complete_trading_day")
    async def test_historical_range_with_complete_data_is_fresh(
        self, mock_last_complete, mock_market_status, cache_service, mock_repository
    ):
        """
        REGRESSION TEST: Historical data requests should use end_date for freshness check.

        Bug: Cache compared against current date instead of requested end_date.
        Fix: Use requested end_date as the reference when end_date < today.

        Scenario: It's 2026-01-04 (today), simulation requests Sept-Oct 2025 data.
        Cache has data through 2025-10-31. Should be FRESH, not stale.
        """
        # Setup: It's January 4, 2026 (today)
        mock_market_status.return_value = "closed"
        mock_last_complete.return_value = date(2026, 1, 3)  # Yesterday (today = Jan 4)

        # Cache has data from Sept 1 through Oct 31, 2025
        mock_records = [
            MockStockPrice(
                symbol="AAPL",
                timestamp=datetime(2025, 9, 1, 16, 0, tzinfo=timezone.utc),
                last_fetched_at=datetime(2025, 10, 31, 21, 0, tzinfo=timezone.utc),
            ),
            MockStockPrice(
                symbol="AAPL",
                timestamp=datetime(2025, 10, 31, 16, 0, tzinfo=timezone.utc),
                last_fetched_at=datetime(2025, 10, 31, 21, 0, tzinfo=timezone.utc),
            ),
        ]
        mock_repository.get_price_data_by_date_range.return_value = mock_records

        # Request historical data: Sept 1 to Oct 31, 2025
        result = await cache_service.check_freshness_smart(
            symbol="AAPL",
            start_date=datetime(2025, 9, 1, tzinfo=timezone.utc),
            end_date=datetime(2025, 10, 31, tzinfo=timezone.utc),
            interval="1d",
        )

        # Verify: Should be FRESH because cache covers the requested historical range
        assert result.is_fresh is True, f"Expected fresh but got stale: {result.reason}"
        assert result.needs_fetch is False

    @pytest.mark.asyncio
    @patch("app.services.cache_service.trading_calendar_service.get_market_status")
    @patch("app.services.cache_service.trading_calendar_service.get_last_complete_trading_day")
    async def test_historical_range_missing_end_data_is_stale(
        self, mock_last_complete, mock_market_status, cache_service, mock_repository
    ):
        """
        Historical data request missing data at the END of requested range should be stale.

        Scenario: Request Sept-Oct 2025, but cache only has Sept 1-15.
        Should be STALE because Oct data is missing.
        """
        # Setup: It's January 4, 2026 (today)
        mock_market_status.return_value = "closed"
        mock_last_complete.return_value = date(2026, 1, 3)

        # Cache only has data through Sept 15 (missing Sept 16 - Oct 31)
        mock_records = [
            MockStockPrice(
                symbol="AAPL",
                timestamp=datetime(2025, 9, 1, 16, 0, tzinfo=timezone.utc),
                last_fetched_at=datetime(2025, 9, 15, 21, 0, tzinfo=timezone.utc),
            ),
            MockStockPrice(
                symbol="AAPL",
                timestamp=datetime(2025, 9, 15, 16, 0, tzinfo=timezone.utc),
                last_fetched_at=datetime(2025, 9, 15, 21, 0, tzinfo=timezone.utc),
            ),
        ]
        mock_repository.get_price_data_by_date_range.return_value = mock_records

        # Request historical data: Sept 1 to Oct 31, 2025
        result = await cache_service.check_freshness_smart(
            symbol="AAPL",
            start_date=datetime(2025, 9, 1, tzinfo=timezone.utc),
            end_date=datetime(2025, 10, 31, tzinfo=timezone.utc),
            interval="1d",
        )

        # Verify: Should be STALE because end of requested range is not covered
        assert result.is_fresh is False
        assert result.needs_fetch is True

    @pytest.mark.asyncio
    @patch("app.services.cache_service.trading_calendar_service.get_market_status")
    @patch("app.services.cache_service.trading_calendar_service.get_last_complete_trading_day")
    async def test_live_range_still_uses_current_time(
        self, mock_last_complete, mock_market_status, cache_service, mock_repository
    ):
        """
        Live data requests (end_date = today) should retain current behavior.

        Ensures the fix for historical data doesn't break live data freshness.
        """
        # Setup: It's January 4, 2026 (today), after hours
        mock_market_status.return_value = "after_hours"
        mock_last_complete.return_value = date(2026, 1, 3)  # Yesterday is last complete day

        # Cache has data from Jan 1 through Jan 3 (covers last complete day)
        mock_records = [
            MockStockPrice(
                symbol="AAPL",
                timestamp=datetime(2026, 1, 1, 16, 0, tzinfo=timezone.utc),
                last_fetched_at=datetime(2026, 1, 3, 21, 0, tzinfo=timezone.utc),
            ),
            MockStockPrice(
                symbol="AAPL",
                timestamp=datetime(2026, 1, 3, 16, 0, tzinfo=timezone.utc),
                last_fetched_at=datetime(2026, 1, 3, 21, 0, tzinfo=timezone.utc),
            ),
        ]
        mock_repository.get_price_data_by_date_range.return_value = mock_records

        # Request data up to TODAY (live request)
        # Note: We mock datetime.now in the service
        with patch("app.services.cache_service.datetime") as mock_datetime:
            mock_datetime.now.return_value = datetime(2026, 1, 4, 22, 0, tzinfo=timezone.utc)
            mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)

            result = await cache_service.check_freshness_smart(
                symbol="AAPL",
                start_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
                end_date=datetime(2026, 1, 4, 22, 0, tzinfo=timezone.utc),  # Today 10PM UTC = 5PM EST
                interval="1d",
            )

        # Verify: Should be FRESH because it's after hours and data covers last complete day
        assert result.is_fresh is True
        assert result.needs_fetch is False

    @pytest.mark.asyncio
    @patch("app.services.cache_service.trading_calendar_service.get_market_status")
    @patch("app.services.cache_service.trading_calendar_service.get_last_complete_trading_day")
    async def test_yesterday_request_during_market_open_is_historical(
        self, mock_last_complete, mock_market_status, cache_service, mock_repository
    ):
        """
        Requesting yesterday's data during market hours should be treated as historical.

        Scenario: It's Wednesday 10am (market open), user requests data ending Tuesday.
        Cache has data through Tuesday. Should be FRESH (historical), not trigger live fetch.
        """
        # Setup: It's Wednesday Jan 8, 2026, market is open
        mock_market_status.return_value = "market_open"
        mock_last_complete.return_value = date(2026, 1, 7)  # Tuesday (last complete day)

        # Cache has data through Tuesday (yesterday)
        mock_records = [
            MockStockPrice(
                symbol="AAPL",
                timestamp=datetime(2026, 1, 6, 16, 0, tzinfo=timezone.utc),
                last_fetched_at=datetime(2026, 1, 7, 21, 0, tzinfo=timezone.utc),
            ),
            MockStockPrice(
                symbol="AAPL",
                timestamp=datetime(2026, 1, 7, 16, 0, tzinfo=timezone.utc),
                last_fetched_at=datetime(2026, 1, 7, 21, 0, tzinfo=timezone.utc),
            ),
        ]
        mock_repository.get_price_data_by_date_range.return_value = mock_records

        # Mock datetime.now to return Wednesday 10am EST (15:00 UTC)
        with patch("app.services.cache_service.datetime") as mock_datetime:
            mock_datetime.now.return_value = datetime(2026, 1, 8, 15, 0, tzinfo=timezone.utc)
            mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)
            mock_datetime.combine = datetime.combine
            mock_datetime.min = datetime.min

            # Request data ending Tuesday (yesterday)
            result = await cache_service.check_freshness_smart(
                symbol="AAPL",
                start_date=datetime(2026, 1, 6, tzinfo=timezone.utc),
                end_date=datetime(2026, 1, 7, tzinfo=timezone.utc),  # Tuesday (yesterday)
                interval="1d",
            )

        # Should be FRESH - treated as historical, not live
        assert result.is_fresh is True, f"Expected fresh but got stale: {result.reason}"
        assert result.needs_fetch is False
        assert "Historical" in result.reason or "covers" in result.reason.lower()

    @pytest.mark.asyncio
    @patch("app.services.cache_service.trading_calendar_service.get_market_status")
    @patch("app.services.cache_service.trading_calendar_service.get_last_complete_trading_day")
    async def test_utc_midnight_boundary_handled_correctly(
        self, mock_last_complete, mock_market_status, cache_service, mock_repository
    ):
        """
        UTC timestamp near midnight should be converted to Eastern time correctly.

        Scenario: end_date = Nov 1 01:00 UTC = Oct 31 21:00 EST
        Should be treated as Oct 31, not Nov 1.
        """
        # Setup: It's November 3, 2025 (Monday), market closed
        mock_market_status.return_value = "closed"
        mock_last_complete.return_value = date(2025, 10, 31)  # Friday Oct 31

        # Cache has data from Oct 1 through Oct 31
        mock_records = [
            MockStockPrice(
                symbol="AAPL",
                timestamp=datetime(2025, 10, 1, 16, 0, tzinfo=timezone.utc),
                last_fetched_at=datetime(2025, 10, 31, 21, 0, tzinfo=timezone.utc),
            ),
            MockStockPrice(
                symbol="AAPL",
                timestamp=datetime(2025, 10, 31, 16, 0, tzinfo=timezone.utc),
                last_fetched_at=datetime(2025, 10, 31, 21, 0, tzinfo=timezone.utc),
            ),
        ]
        mock_repository.get_price_data_by_date_range.return_value = mock_records

        with patch("app.services.cache_service.datetime") as mock_datetime:
            mock_datetime.now.return_value = datetime(2025, 11, 3, 15, 0, tzinfo=timezone.utc)
            mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)
            mock_datetime.combine = datetime.combine
            mock_datetime.min = datetime.min

            # Request with end_date in UTC that crosses midnight
            # Nov 1 01:00 UTC = Oct 31 21:00 EST (still Oct 31 in Eastern!)
            result = await cache_service.check_freshness_smart(
                symbol="AAPL",
                start_date=datetime(2025, 10, 1, tzinfo=timezone.utc),
                end_date=datetime(2025, 11, 1, 1, 0, tzinfo=timezone.utc),  # Nov 1 01:00 UTC
                interval="1d",
            )

        # Should be FRESH - end_date is Oct 31 in Eastern time
        assert result.is_fresh is True, f"Expected fresh but got stale: {result.reason}"
        assert result.needs_fetch is False

    @pytest.mark.asyncio
    @patch("app.services.cache_service.trading_calendar_service.get_first_trading_day_on_or_after")
    @patch("app.services.cache_service.trading_calendar_service.get_market_status")
    @patch("app.services.cache_service.trading_calendar_service.get_last_complete_trading_day")
    async def test_request_starting_on_holiday_is_fresh_when_cache_has_next_trading_day(
        self, mock_last_complete, mock_market_status, mock_first_trading_day, cache_service, mock_repository
    ):
        """Regression test: requests starting on holidays should match cached data.

        Scenario: Request starts Jan 1 (holiday), cache has data from Jan 2.
        The system normalizes the start date to the first trading day (Jan 2),
        so Jan 2 >= Jan 2 means the cache covers the requested range.
        """
        # Setup: It's Jan 5, 2026 (Monday), after hours
        now = datetime(2026, 1, 5, 22, 0, tzinfo=timezone.utc)  # 5:00 PM ET
        mock_market_status.return_value = "after_hours"
        mock_last_complete.return_value = date(2026, 1, 5)
        mock_first_trading_day.return_value = date(2026, 1, 2)  # Jan 1 -> Jan 2

        # Cache has data from Jan 2 (first trading day after New Year's) through Jan 5
        mock_records = [
            MockStockPrice(
                symbol="AAPL",
                timestamp=datetime(2026, 1, 2, 21, 0, tzinfo=timezone.utc),  # Jan 2
                last_fetched_at=datetime(2026, 1, 5, 22, 0, tzinfo=timezone.utc),
            ),
            MockStockPrice(
                symbol="AAPL",
                timestamp=datetime(2026, 1, 5, 21, 0, tzinfo=timezone.utc),  # Jan 5
                last_fetched_at=datetime(2026, 1, 5, 22, 0, tzinfo=timezone.utc),
            ),
        ]
        mock_repository.get_price_data_by_date_range.return_value = mock_records

        # Request data starting Jan 1 (holiday) through Jan 5
        with patch("app.services.cache_service.datetime") as mock_datetime:
            mock_datetime.now.return_value = now
            mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)
            mock_datetime.combine = datetime.combine
            mock_datetime.min = datetime.min

            result = await cache_service.check_freshness_smart(
                symbol="AAPL",
                start_date=datetime(2026, 1, 1, tzinfo=timezone.utc),  # New Year's Day!
                end_date=datetime(2026, 1, 5, 22, 0, tzinfo=timezone.utc),
                interval="1d",
            )

        # Should be FRESH - cache covers from first trading day (Jan 2) through Jan 5
        assert result.is_fresh is True, f"Expected fresh but got stale: {result.reason}"
        assert result.needs_fetch is False
