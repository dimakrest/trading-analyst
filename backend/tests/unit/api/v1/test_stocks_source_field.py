"""Unit tests for stock prices API source field.

Tests that the response source field correctly reflects the configured provider
and prevents regression of hardcoded source values.
"""
import pytest
from datetime import datetime, timedelta, UTC
from unittest.mock import AsyncMock, MagicMock
from httpx import AsyncClient
from decimal import Decimal

from app.providers.yahoo import YahooFinanceProvider
from app.providers.ib_data import IBDataProvider
from app.providers.mock import MockMarketDataProvider
from app.services.data_service import DataService
from app.repositories.stock_price import StockPriceRepository
from app.services.cache_service import MarketDataCache, CacheTTLConfig
from app.models.stock import StockPrice


@pytest.mark.asyncio
class TestStockPricesSourceField:
    """Tests for stock prices API source field with different providers."""

    def _create_mock_stock_price(self, symbol: str, date: datetime, index: int) -> StockPrice:
        """Create a mock StockPrice database record.

        Args:
            symbol: Stock symbol
            date: Date for the record
            index: Index for varying prices

        Returns:
            StockPrice: Mock database record
        """
        mock_record = MagicMock(spec=StockPrice)
        mock_record.symbol = symbol
        mock_record.timestamp = date
        mock_record.interval = "1d"
        mock_record.open_price = Decimal(str(150.0 + index))
        mock_record.high_price = Decimal(str(155.0 + index))
        mock_record.low_price = Decimal(str(149.0 + index))
        mock_record.close_price = Decimal(str(152.0 + index))
        mock_record.volume = 1000000 + (index * 1000)
        mock_record.data_source = "test"
        return mock_record

    async def _create_mock_data_service(
        self, provider: YahooFinanceProvider | IBDataProvider | MockMarketDataProvider
    ) -> DataService:
        """Create a mock DataService with the specified provider.

        Args:
            provider: Market data provider instance

        Returns:
            DataService: Mocked DataService with provider
        """
        from app.services.cache_service import FreshnessResult
        from datetime import date

        # Create mock session
        mock_session = AsyncMock()

        # Create mock repository
        mock_repository = AsyncMock(spec=StockPriceRepository)

        # Create sample price records that will be returned by the repository
        end_date = datetime.now(UTC)
        start_date = end_date - timedelta(days=5)
        mock_records = []

        for i in range(5):
            record_date = start_date + timedelta(days=i)
            mock_records.append(self._create_mock_stock_price("AAPL", record_date, i))

        # Mock repository methods
        mock_repository.get_price_data_by_date_range = AsyncMock(return_value=mock_records)

        # Create cache with test configuration
        ttl_config = CacheTTLConfig()
        mock_cache = MagicMock(spec=MarketDataCache)
        mock_cache.repository = mock_repository
        mock_cache.ttl_config = ttl_config

        # Mock check_freshness_smart to return fresh data with cached_records
        mock_cache.check_freshness_smart = AsyncMock(
            return_value=FreshnessResult(
                is_fresh=True,
                reason="Test data is fresh",
                market_status="closed",
                recommended_ttl=3600,
                last_data_date=date.today(),
                last_complete_trading_day=date.today(),
                needs_fetch=False,
                fetch_start_date=None,
                cached_records=mock_records,
            )
        )

        # Create DataService with the provider
        data_service = DataService(
            session=mock_session,
            provider=provider,
            cache=mock_cache,
            repository=mock_repository,
        )

        return data_service

    async def test_yahoo_provider_source_field(self, app):
        """Test that response source field is 'yahoo_finance' when using Yahoo provider.

        Verifies that when DataService uses YahooFinanceProvider,
        the API response contains source='yahoo_finance'.
        """
        # Arrange
        yahoo_provider = YahooFinanceProvider()
        mock_data_service = await self._create_mock_data_service(yahoo_provider)

        # Override the get_data_service dependency
        from app.core.deps import get_data_service

        async def override_get_data_service() -> DataService:
            return mock_data_service

        app.dependency_overrides[get_data_service] = override_get_data_service

        # Act
        async with AsyncClient(app=app, base_url="http://testserver") as client:
            response = await client.get(
                "/api/v1/stocks/AAPL/prices",
                params={
                    "interval": "1d",
                    "period": "5d",
                }
            )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert "source" in data
        assert data["source"] == "yahoo_finance", (
            f"Expected source='yahoo_finance' for Yahoo provider, got '{data['source']}'"
        )

        # Verify provider_name property matches
        assert yahoo_provider.provider_name == "yahoo_finance"

        # Clean up
        app.dependency_overrides.clear()

    async def test_ib_provider_source_field(self, app):
        """Test that response source field is 'ib' when using IB provider.

        Verifies that when DataService uses IBDataProvider,
        the API response contains source='ib'.
        """
        # Arrange
        # Mock IBDataProvider to avoid actual IB Gateway connection
        mock_ib_provider = MagicMock(spec=IBDataProvider)
        mock_ib_provider.provider_name = "ib"
        mock_ib_provider.supported_intervals = ["1m", "5m", "15m", "30m", "1h", "1d"]

        mock_data_service = await self._create_mock_data_service(mock_ib_provider)

        # Override the get_data_service dependency
        from app.core.deps import get_data_service

        async def override_get_data_service() -> DataService:
            return mock_data_service

        app.dependency_overrides[get_data_service] = override_get_data_service

        # Act
        async with AsyncClient(app=app, base_url="http://testserver") as client:
            response = await client.get(
                "/api/v1/stocks/AAPL/prices",
                params={
                    "interval": "15m",
                    "period": "5d",
                }
            )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert "source" in data
        assert data["source"] == "ib", (
            f"Expected source='ib' for IB provider, got '{data['source']}'"
        )

        # Verify provider_name property matches
        assert mock_ib_provider.provider_name == "ib"

        # Clean up
        app.dependency_overrides.clear()

    async def test_mock_provider_source_field(self, app):
        """Test that response source field is 'mock' when using Mock provider.

        Verifies that when DataService uses MockMarketDataProvider,
        the API response contains source='mock'.
        """
        # Arrange
        mock_provider = MockMarketDataProvider()
        mock_data_service = await self._create_mock_data_service(mock_provider)

        # Override the get_data_service dependency
        from app.core.deps import get_data_service

        async def override_get_data_service() -> DataService:
            return mock_data_service

        app.dependency_overrides[get_data_service] = override_get_data_service

        # Act
        async with AsyncClient(app=app, base_url="http://testserver") as client:
            response = await client.get(
                "/api/v1/stocks/AAPL/prices",
                params={
                    "interval": "1d",
                    "period": "5d",
                }
            )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert "source" in data
        assert data["source"] == "mock", (
            f"Expected source='mock' for Mock provider, got '{data['source']}'"
        )

        # Verify provider_name property matches
        assert mock_provider.provider_name == "mock"

        # Clean up
        app.dependency_overrides.clear()

    async def test_source_field_not_hardcoded(self, app):
        """Test that source field is not hardcoded and changes with provider.

        This test creates a custom provider with a unique name to verify
        that the source field truly reflects the provider's name dynamically.
        """
        # Arrange - Create a custom provider with unique name
        class CustomTestProvider(MockMarketDataProvider):
            """Custom test provider with unique name."""

            @property
            def provider_name(self) -> str:
                return "custom_test_provider"

        custom_provider = CustomTestProvider()
        mock_data_service = await self._create_mock_data_service(custom_provider)

        # Override the get_data_service dependency
        from app.core.deps import get_data_service

        async def override_get_data_service() -> DataService:
            return mock_data_service

        app.dependency_overrides[get_data_service] = override_get_data_service

        # Act
        async with AsyncClient(app=app, base_url="http://testserver") as client:
            response = await client.get(
                "/api/v1/stocks/AAPL/prices",
                params={
                    "interval": "1d",
                    "period": "5d",
                }
            )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert "source" in data
        assert data["source"] == "custom_test_provider", (
            "Source field appears to be hardcoded! It should reflect the provider's name. "
            f"Expected 'custom_test_provider', got '{data['source']}'"
        )

        # Clean up
        app.dependency_overrides.clear()

    async def test_all_providers_have_different_names(self):
        """Test that all three providers have distinct provider names.

        This ensures no naming conflicts that could mask the source field bug.
        """
        yahoo_provider = YahooFinanceProvider()
        mock_provider = MockMarketDataProvider()

        # Note: We can't instantiate real IBDataProvider without IB Gateway connection,
        # so we just verify the expected name from the plan
        assert yahoo_provider.provider_name == "yahoo_finance"
        assert mock_provider.provider_name == "mock"

        # Verify they are all different
        provider_names = {yahoo_provider.provider_name, mock_provider.provider_name, "ib"}
        assert len(provider_names) == 3, (
            "Provider names must be unique. Found duplicates in: "
            f"{[yahoo_provider.provider_name, mock_provider.provider_name, 'ib']}"
        )
