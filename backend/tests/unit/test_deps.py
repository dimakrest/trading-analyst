"""Unit tests for dependency injection functions.

Tests the dependency injection functions in app.core.deps,
particularly the singleton behavior of get_market_data_provider().
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.core.deps import get_market_data_provider
from app.providers.ib_data import IBDataProvider
from app.providers.mock import MockMarketDataProvider
from app.providers.yahoo import YahooFinanceProvider


class TestGetMarketDataProvider:
    """Tests for get_market_data_provider dependency function."""

    @pytest.mark.asyncio
    async def test_returns_yahoo_provider_when_configured(self) -> None:
        """Test that YahooFinanceProvider is returned when MARKET_DATA_PROVIDER=yahoo."""
        with patch("app.core.deps.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(market_data_provider="yahoo")
            provider = await get_market_data_provider()
            assert isinstance(provider, YahooFinanceProvider)

    @pytest.mark.asyncio
    async def test_returns_mock_provider_when_configured(self) -> None:
        """Test that MockMarketDataProvider is returned when MARKET_DATA_PROVIDER=mock."""
        with patch("app.core.deps.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(market_data_provider="mock")
            provider = await get_market_data_provider()
            assert isinstance(provider, MockMarketDataProvider)

    @pytest.mark.asyncio
    async def test_returns_ib_singleton_when_configured(self) -> None:
        """Test that IBDataProvider singleton is returned when MARKET_DATA_PROVIDER=ib.

        Verifies singleton behavior to avoid "client ID already in use" errors,
        as IB Gateway only allows one connection per client_id.
        """
        with patch("app.core.deps.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(market_data_provider="ib")

            mock_ib_provider = MagicMock(spec=IBDataProvider)
            mock_ib_provider.provider_name = "interactive_brokers"

            with patch("app.core.deps.get_ib_data_provider") as mock_get_ib:
                mock_get_ib.return_value = mock_ib_provider

                provider1 = await get_market_data_provider()
                provider2 = await get_market_data_provider()

                assert provider1 is provider2
                assert provider1.provider_name == "interactive_brokers"
                assert mock_get_ib.call_count == 2

    @pytest.mark.asyncio
    async def test_raises_value_error_for_unknown_provider(self) -> None:
        """Test that ValueError is raised for unknown provider configuration."""
        with patch("app.core.deps.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(market_data_provider="unknown")

            with pytest.raises(ValueError, match="Unknown market data provider"):
                await get_market_data_provider()
