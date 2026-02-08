"""Tests for DataService with provider abstraction and caching.

Tests cover:
- Symbol validation via provider
- Price data fetching with cache-first architecture
- Integration with providers (Yahoo, Mock)
- Cache orchestration with market-aware freshness checking
- Error handling for provider failures
- Integration with StockPriceRepository
- Concurrent operations and rate limiting
- Edge cases and error scenarios
"""
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest

from app.core.exceptions import (
    APIError,
    SymbolNotFoundError,
)
from app.providers.base import PriceDataPoint, SymbolInfo
from app.providers.mock import MockMarketDataProvider
from app.repositories.stock_price import StockPriceRepository
from app.services.cache_service import MarketDataCache
from app.services.data_service import DataService, DataServiceConfig


class TestDataServiceConfig:
    """Test DataService configuration."""

    def test_default_config(self):
        """Test default configuration values."""
        config = DataServiceConfig()

        assert config.max_retries == 3
        assert config.retry_delay == 1.0
        assert config.request_timeout == 30.0
        assert config.max_concurrent_requests == 5
        assert config.validate_data is True
        assert config.default_interval == "1d"
        assert config.max_history_years == 10

    def test_custom_config(self):
        """Test custom configuration values."""
        config = DataServiceConfig(
            max_retries=5,
            retry_delay=2.0,
            request_timeout=60.0,
            max_concurrent_requests=10,
            validate_data=False,
            default_interval="1h",
            max_history_years=5,
        )

        assert config.max_retries == 5
        assert config.retry_delay == 2.0
        assert config.request_timeout == 60.0
        assert config.max_concurrent_requests == 10
        assert config.validate_data is False
        assert config.default_interval == "1h"
        assert config.max_history_years == 5


class TestDataService:
    """Test DataService operations with mock provider."""

    @pytest.fixture
    def mock_session(self):
        """Create mock database session."""
        return AsyncMock()

    @pytest.fixture
    def mock_provider(self):
        """Create mock provider."""
        provider = AsyncMock(spec=MockMarketDataProvider)
        provider.provider_name = "mock"
        provider.supported_intervals = ["1m", "5m", "1h", "1d"]
        return provider

    @pytest.fixture
    def mock_cache(self):
        """Create mock cache."""
        from datetime import date, timedelta
        from app.services.cache_service import FreshnessResult

        cache = AsyncMock(spec=MarketDataCache)

        # Default: freshness check indicates need to fetch
        default_freshness = FreshnessResult(
            is_fresh=False,
            reason="No cached data",
            market_status="pre_market",
            recommended_ttl=0,
            last_data_date=None,
            last_complete_trading_day=date.today() - timedelta(days=1),
            needs_fetch=True,
            fetch_start_date=date.today() - timedelta(days=365),
        )
        cache.check_freshness_smart.return_value = default_freshness

        return cache

    @pytest.fixture
    def mock_repository(self):
        """Create mock repository."""
        return AsyncMock(spec=StockPriceRepository)

    @pytest.fixture
    def data_service(self, mock_session, mock_provider, mock_cache, mock_repository):
        """Create DataService instance with mock dependencies."""
        config = DataServiceConfig(max_retries=1)  # Fast tests
        return DataService(
            session=mock_session,
            provider=mock_provider,
            cache=mock_cache,
            repository=mock_repository,
            config=config,
        )

    async def test_init(self, mock_session, mock_provider, mock_cache, mock_repository):
        """Test DataService initialization."""
        config = DataServiceConfig()
        service = DataService(
            session=mock_session,
            provider=mock_provider,
            cache=mock_cache,
            repository=mock_repository,
            config=config,
        )

        assert service.session == mock_session
        assert service.config == config
        assert service.provider == mock_provider
        assert service.cache == mock_cache
        assert service.repository == mock_repository
        assert service._semaphore._value == config.max_concurrent_requests

    async def test_init_default_config(self, mock_session):
        """Test DataService initialization with default config."""
        service = DataService(session=mock_session)

        assert service.session == mock_session
        assert isinstance(service.config, DataServiceConfig)
        assert service.config.max_retries == 3
        # Provider should default to Yahoo
        assert service.provider.provider_name == "yahoo_finance"

    async def test_validate_symbol_success(self, data_service, mock_provider):
        """Test successful symbol validation."""
        # Setup mock provider response
        mock_provider.validate_symbol.return_value = SymbolInfo(
            symbol="AAPL",
            name="Apple Inc.",
            currency="USD",
            exchange="NASDAQ",
            market_cap=3000000000000.0,
            sector="Technology",
            industry="Consumer Electronics",
        )

        # Test validation
        result = await data_service.validate_symbol("AAPL")

        # Verify result (converted to dict by DataService)
        assert result["symbol"] == "AAPL"
        assert result["name"] == "Apple Inc."
        assert result["currency"] == "USD"
        assert result["exchange"] == "NASDAQ"

        # Verify provider was called
        mock_provider.validate_symbol.assert_called_once_with("AAPL")

    async def test_validate_symbol_not_found(self, data_service, mock_provider):
        """Test symbol validation with invalid symbol."""
        # Setup mock to raise SymbolNotFoundError
        mock_provider.validate_symbol.side_effect = SymbolNotFoundError(
            "Symbol 'INVALID' not found"
        )

        # Test validation
        with pytest.raises(SymbolNotFoundError) as exc_info:
            await data_service.validate_symbol("INVALID")

        assert "Symbol 'INVALID' not found" in str(exc_info.value)

    async def test_validate_symbol_api_error(self, data_service, mock_provider):
        """Test symbol validation with API error."""
        # Setup mock to raise APIError
        mock_provider.validate_symbol.side_effect = APIError("API Error")

        # Test validation
        with pytest.raises(APIError) as exc_info:
            await data_service.validate_symbol("AAPL")

        assert "API Error" in str(exc_info.value)

    async def test_get_price_data_cache_hit(
        self, data_service, mock_provider, mock_cache, mock_repository
    ):
        """Test get_price_data with cache hit."""
        from datetime import date, timedelta
        from decimal import Decimal as D
        from unittest.mock import MagicMock
        from app.models.stock import StockPrice
        from app.services.cache_service import FreshnessResult

        # Create mock StockPrice records
        mock_record = MagicMock(spec=StockPrice)
        mock_record.symbol = "AAPL"
        mock_record.timestamp = datetime.now(UTC)
        mock_record.open_price = D("100.0")
        mock_record.high_price = D("102.0")
        mock_record.low_price = D("99.0")
        mock_record.close_price = D("101.0")
        mock_record.volume = 1000000

        # Setup smart freshness check to indicate data is fresh with cached_records
        freshness = FreshnessResult(
            is_fresh=True,
            reason="Data covers up to last complete trading day",
            market_status="pre_market",
            recommended_ttl=86400,
            last_data_date=date.today() - timedelta(days=1),
            last_complete_trading_day=date.today() - timedelta(days=1),
            needs_fetch=False,
            fetch_start_date=None,
            cached_records=[mock_record],
        )
        mock_cache.check_freshness_smart.return_value = freshness

        # Test get price data
        result = await data_service.get_price_data("AAPL")

        # Verify result contains data
        assert len(result) > 0
        assert all(isinstance(r, PriceDataPoint) for r in result)
        assert result[0].symbol == "AAPL"

        # Provider should NOT be called (cache hit)
        mock_provider.fetch_price_data.assert_not_called()
        mock_repository.sync_price_data.assert_not_called()

    async def test_get_price_data_cache_miss(
        self, data_service, mock_provider, mock_cache, mock_repository
    ):
        """Test get_price_data with cache miss."""
        from unittest.mock import MagicMock
        from decimal import Decimal as D
        from app.models.stock import StockPrice

        # Setup provider response
        mock_points = [
            PriceDataPoint(
                symbol="AAPL",
                timestamp=datetime.now(UTC),
                open_price=Decimal("100.0"),
                high_price=Decimal("102.0"),
                low_price=Decimal("99.0"),
                close_price=Decimal("101.0"),
                volume=1000000,
            )
        ]
        mock_provider.fetch_price_data.return_value = mock_points

        # Setup repository response for sync
        mock_repository.sync_price_data.return_value = {
            "inserted": 1,
            "updated": 0,
            "skipped": 0,
        }

        # Setup repository to return records after fetch
        mock_record = MagicMock(spec=StockPrice)
        mock_record.symbol = "AAPL"
        mock_record.timestamp = datetime.now(UTC)
        mock_record.open_price = D("100.0")
        mock_record.high_price = D("102.0")
        mock_record.low_price = D("99.0")
        mock_record.close_price = D("101.0")
        mock_record.volume = 1000000
        mock_repository.get_price_data_by_date_range.return_value = [mock_record]

        # Test get price data
        result = await data_service.get_price_data("AAPL")

        # Verify result contains data
        assert len(result) > 0
        assert all(isinstance(r, PriceDataPoint) for r in result)

        # Provider should be called
        mock_provider.fetch_price_data.assert_called_once()
        mock_repository.sync_price_data.assert_called_once()

    async def test_get_price_data_force_refresh(
        self, data_service, mock_provider, mock_cache, mock_repository
    ):
        """Test get_price_data with force_refresh."""
        from unittest.mock import MagicMock
        from decimal import Decimal as D
        from app.models.stock import StockPrice

        # Setup provider response
        mock_points = [
            PriceDataPoint(
                symbol="AAPL",
                timestamp=datetime.now(UTC),
                open_price=Decimal("100.0"),
                high_price=Decimal("102.0"),
                low_price=Decimal("99.0"),
                close_price=Decimal("101.0"),
                volume=1000000,
            )
        ]
        mock_provider.fetch_price_data.return_value = mock_points

        # Setup repository response
        mock_repository.sync_price_data.return_value = {
            "inserted": 1,
            "updated": 0,
            "skipped": 0,
        }

        # Setup repository to return records after fetch
        mock_record = MagicMock(spec=StockPrice)
        mock_record.symbol = "AAPL"
        mock_record.timestamp = datetime.now(UTC)
        mock_record.open_price = D("100.0")
        mock_record.high_price = D("102.0")
        mock_record.low_price = D("99.0")
        mock_record.close_price = D("101.0")
        mock_record.volume = 1000000
        mock_repository.get_price_data_by_date_range.return_value = [mock_record]

        # Test with force_refresh=True
        result = await data_service.get_price_data("AAPL", force_refresh=True)

        # Smart freshness check should NOT be called (force refresh bypasses it)
        mock_cache.check_freshness_smart.assert_not_called()

        # Provider should be called
        mock_provider.fetch_price_data.assert_called_once()
        mock_repository.sync_price_data.assert_called_once()

    async def test_service_constants(self, data_service):
        """Test DataService constants."""
        # Test valid intervals
        assert "1d" in data_service.VALID_INTERVALS
        assert "1h" in data_service.VALID_INTERVALS
        assert "5m" in data_service.VALID_INTERVALS
        assert "invalid" not in data_service.VALID_INTERVALS

        # Test intraday intervals
        assert "1m" in data_service.INTRADAY_INTERVALS
        assert "1h" in data_service.INTRADAY_INTERVALS
        assert "1d" not in data_service.INTRADAY_INTERVALS

    async def test_persistence_without_session_fails(self):
        """Test that persistence operations fail gracefully without session."""
        # Create service without session
        config = DataServiceConfig(max_retries=1, validate_data=True)
        service = DataService(session=None, config=config)

        # Try to use persistence operation - should fail with clear error
        with pytest.raises(RuntimeError, match="Database session required"):
            await service.get_price_data("AAPL")

    async def test_api_operations_work_without_session(self):
        """Test that API-only operations work without session."""
        # Create service without session (uses real Yahoo provider)
        config = DataServiceConfig(max_retries=1, validate_data=True)
        mock_provider = AsyncMock(spec=MockMarketDataProvider)
        mock_provider.validate_symbol.return_value = SymbolInfo(
            symbol="AAPL",
            name="Apple Inc.",
            currency="USD",
            exchange="NASDAQ",
        )

        service = DataService(session=None, provider=mock_provider, config=config)

        # API operations should work fine
        result = await service.validate_symbol("AAPL")
        assert result["symbol"] == "AAPL"


class TestDataServiceErrorHandling:
    """Test error handling in DataService."""

    @pytest.fixture
    def mock_session(self):
        """Create mock database session."""
        return AsyncMock()

    @pytest.fixture
    def mock_provider(self):
        """Create mock provider."""
        provider = AsyncMock(spec=MockMarketDataProvider)
        provider.provider_name = "mock"
        return provider

    @pytest.fixture
    def mock_cache(self):
        """Create mock cache."""
        from datetime import date, timedelta
        from app.services.cache_service import FreshnessResult

        cache = AsyncMock(spec=MarketDataCache)

        # Default: freshness check indicates need to fetch
        default_freshness = FreshnessResult(
            is_fresh=False,
            reason="No cached data",
            market_status="pre_market",
            recommended_ttl=0,
            last_data_date=None,
            last_complete_trading_day=date.today() - timedelta(days=1),
            needs_fetch=True,
            fetch_start_date=date.today() - timedelta(days=365),
        )
        cache.check_freshness_smart.return_value = default_freshness

        return cache

    @pytest.fixture
    def mock_repository(self):
        """Create mock repository."""
        return AsyncMock(spec=StockPriceRepository)

    @pytest.fixture
    def data_service(self, mock_session, mock_provider, mock_cache, mock_repository):
        """Create DataService with minimal retries for testing."""
        config = DataServiceConfig(max_retries=2, retry_delay=0.1)
        return DataService(
            session=mock_session,
            provider=mock_provider,
            cache=mock_cache,
            repository=mock_repository,
            config=config,
        )

    async def test_provider_api_error(
        self, data_service, mock_provider, mock_cache
    ):
        """Test handling of provider API errors."""
        from datetime import date, timedelta
        from app.services.cache_service import FreshnessResult

        # Setup smart freshness check to indicate need to fetch
        mock_cache.check_freshness_smart.return_value = FreshnessResult(
            is_fresh=False,
            reason="No cached data",
            market_status="closed",
            recommended_ttl=0,
            last_data_date=None,
            last_complete_trading_day=date.today() - timedelta(days=1),
            needs_fetch=True,
            fetch_start_date=date.today() - timedelta(days=365),
        )

        # Setup mock to raise APIError
        mock_provider.fetch_price_data.side_effect = APIError("API Error")

        # Test fetch - should propagate error
        with pytest.raises(APIError) as exc_info:
            await data_service.get_price_data("AAPL")

        assert "API Error" in str(exc_info.value)

    async def test_repository_error_handling(
        self, data_service, mock_provider, mock_cache, mock_repository
    ):
        """Test handling of repository errors."""
        # Setup mocks
        mock_provider.fetch_price_data.return_value = [
            PriceDataPoint(
                symbol="AAPL",
                timestamp=datetime.now(UTC),
                open_price=Decimal("100.0"),
                high_price=Decimal("102.0"),
                low_price=Decimal("99.0"),
                close_price=Decimal("101.0"),
                volume=1000000,
            )
        ]

        # Setup repository to raise error
        mock_repository.sync_price_data.side_effect = Exception("DB Error")

        # Test - should propagate error
        with pytest.raises(Exception) as exc_info:
            await data_service.get_price_data("AAPL")

        assert "DB Error" in str(exc_info.value)

    async def test_concurrent_request_limiting(self, mock_session):
        """Test concurrent request limiting."""
        config = DataServiceConfig(max_concurrent_requests=2)
        service = DataService(session=mock_session, config=config)

        # Check semaphore limit
        assert service._semaphore._value == 2

        # Test semaphore acquisition
        await service._semaphore.acquire()
        await service._semaphore.acquire()

        # Should not be able to acquire more
        assert service._semaphore.locked()


class TestDataServiceAdditionalCoverage:
    """Additional tests for coverage."""

    @pytest.fixture
    def mock_session(self):
        """Create mock database session."""
        return AsyncMock()

    @pytest.fixture
    def mock_provider(self):
        """Create mock provider."""
        provider = AsyncMock(spec=MockMarketDataProvider)
        provider.provider_name = "mock"
        return provider

    @pytest.fixture
    def mock_cache(self):
        """Create mock cache."""
        from datetime import date, timedelta
        from app.services.cache_service import FreshnessResult

        cache = AsyncMock(spec=MarketDataCache)

        # Default: freshness check indicates need to fetch
        default_freshness = FreshnessResult(
            is_fresh=False,
            reason="No cached data",
            market_status="pre_market",
            recommended_ttl=0,
            last_data_date=None,
            last_complete_trading_day=date.today() - timedelta(days=1),
            needs_fetch=True,
            fetch_start_date=date.today() - timedelta(days=365),
        )
        cache.check_freshness_smart.return_value = default_freshness

        return cache

    @pytest.fixture
    def mock_repository(self):
        """Create mock repository."""
        return AsyncMock(spec=StockPriceRepository)

    @pytest.fixture
    def data_service(self, mock_session, mock_provider, mock_cache, mock_repository):
        """Create DataService instance."""
        config = DataServiceConfig()
        return DataService(
            session=mock_session,
            provider=mock_provider,
            cache=mock_cache,
            repository=mock_repository,
            config=config,
        )


@pytest.mark.integration
class TestDataServiceIntegration:
    """Integration tests for DataService with real providers.

    These tests verify real provider integration.
    Tests are skipped by default to avoid external dependencies in CI/CD.

    To run: pytest -m integration
    """

    @pytest.fixture
    def real_data_service(self):
        """Create DataService for API testing.

        Note: No database session - testing API-only operations.
        """
        config = DataServiceConfig(max_retries=1, validate_data=True)
        return DataService(session=None, config=config)

    @pytest.mark.skip(reason="Requires internet access and valid Yahoo Finance API")
    async def test_real_symbol_validation(self, real_data_service):
        """Test symbol validation with real Yahoo Finance API."""
        # Test with well-known symbol
        result = await real_data_service.validate_symbol("AAPL")

        assert result["symbol"] == "AAPL"
        assert result["name"] is not None
        assert result["currency"] == "USD"
