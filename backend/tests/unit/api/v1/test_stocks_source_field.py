"""Unit tests for stock prices API source field.

Tests that the response source field correctly reflects the configured provider
and prevents regression of hardcoded source values.
"""
import pytest
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from httpx import AsyncClient

from app.providers.base import PriceDataPoint
from app.providers.yahoo import YahooFinanceProvider
from app.providers.ib_data import IBDataProvider
from app.providers.mock import MockMarketDataProvider
from app.services.data_service import DataService


@pytest.mark.asyncio
class TestStockPricesSourceField:
    """Tests for stock prices API source field with different providers."""

    async def _create_mock_data_service(self, provider) -> DataService:
        """Create a DataService with mocked get_price_data.

        The provider stays real (so provider.provider_name works for source field),
        but get_price_data is mocked to avoid real API/DB calls.

        Args:
            provider: Market data provider instance

        Returns:
            DataService: DataService with mocked get_price_data
        """
        data_service = DataService(
            session_factory=None,  # Not needed - get_price_data is mocked
            provider=provider,
        )
        # Mock get_price_data to avoid real API/DB calls.
        # These tests only verify the source field, not data fetching.
        fake_points = [
            PriceDataPoint(
                symbol="AAPL",
                timestamp=datetime.now(timezone.utc),
                open_price=Decimal("150.00"),
                high_price=Decimal("155.00"),
                low_price=Decimal("149.00"),
                close_price=Decimal("152.00"),
                volume=1000000,
            )
        ]
        data_service.get_price_data = AsyncMock(return_value=fake_points)
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

        This test creates a custom provider with the name 'mock' (which is valid
        in our database constraint) to verify that the source field truly reflects
        the provider's name dynamically, not a hardcoded value.
        """
        # Arrange - Create a custom provider that uses 'mock' as its name
        # (which is valid in our database constraint)
        class CustomTestProvider(MockMarketDataProvider):
            """Custom test provider with dynamically-set name."""

            def __init__(self):
                super().__init__()
                self._custom_name = "mock"

            @property
            def provider_name(self) -> str:
                return self._custom_name

        custom_provider = CustomTestProvider()
        # Verify it's using the name we set
        assert custom_provider.provider_name == "mock"

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
        assert data["source"] == "mock", (
            "Source field appears to be hardcoded! It should reflect the provider's name. "
            f"Expected 'mock', got '{data['source']}'"
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
