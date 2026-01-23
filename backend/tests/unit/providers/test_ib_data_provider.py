"""Unit tests for IB Data Provider.

Tests the IBDataProvider class for connecting to Interactive Brokers Gateway,
fetching historical price data, and validating data integrity.
"""
from datetime import datetime
from datetime import timedelta
from datetime import timezone
from decimal import Decimal
from unittest.mock import AsyncMock
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest

from app.core.exceptions import APIError
from app.core.exceptions import DataValidationError
from app.core.exceptions import SymbolNotFoundError
from app.providers.base import PriceDataPoint
from app.providers.base import PriceDataRequest
from app.providers.ib_data import IBDataProvider


class TestIBDataProvider:
    """Tests for IBDataProvider class."""

    @pytest.fixture
    def provider(self) -> IBDataProvider:
        """Create IBDataProvider instance.

        Returns:
            IBDataProvider: Configured provider instance for testing.
        """
        with patch("app.providers.ib_data.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                ib_data_client_id=99,
                ib_host="127.0.0.1",
                ib_port=7497,
            )
            return IBDataProvider()

    def test_provider_name(self, provider: IBDataProvider) -> None:
        """Test provider_name property.

        Args:
            provider: IBDataProvider instance fixture.
        """
        assert provider.provider_name == "ib"

    def test_supported_intervals(self, provider: IBDataProvider) -> None:
        """Test supported_intervals property.

        Args:
            provider: IBDataProvider instance fixture.
        """
        intervals = provider.supported_intervals
        assert "15m" in intervals
        assert "1d" in intervals
        assert "1m" in intervals

    def test_bar_size_mapping(self, provider: IBDataProvider) -> None:
        """Test interval to IB bar size mapping.

        Args:
            provider: IBDataProvider instance fixture.
        """
        assert provider.BAR_SIZE_MAP["15m"] == "15 mins"
        assert provider.BAR_SIZE_MAP["1d"] == "1 day"
        assert provider.BAR_SIZE_MAP["1h"] == "1 hour"

    @pytest.mark.asyncio
    async def test_connect_success(self, provider: IBDataProvider) -> None:
        """Test successful connection to IB Gateway.

        Args:
            provider: IBDataProvider instance fixture.
        """
        with patch.object(provider.ib, "connectAsync", new_callable=AsyncMock) as mock_connect:
            with patch.object(provider.ib, "isConnected", return_value=True):
                await provider.connect()
                mock_connect.assert_called_once()
                assert provider._connected is True

    @pytest.mark.asyncio
    async def test_connect_timeout(self, provider: IBDataProvider) -> None:
        """Test connection timeout raises APIError.

        Args:
            provider: IBDataProvider instance fixture.
        """
        with patch.object(provider.ib, "connectAsync", new_callable=AsyncMock) as mock_connect:
            mock_connect.side_effect = TimeoutError()

            with pytest.raises(APIError, match="Timeout connecting"):
                await provider.connect()

    @pytest.mark.asyncio
    async def test_fetch_price_data_invalid_interval(
        self, provider: IBDataProvider
    ) -> None:
        """Test fetch_price_data rejects invalid interval.

        Args:
            provider: IBDataProvider instance fixture.
        """
        provider._connected = True
        with patch.object(provider.ib, "isConnected", return_value=True):
            request = PriceDataRequest(
                symbol="AAPL",
                start_date=datetime.now(timezone.utc) - timedelta(days=1),
                end_date=datetime.now(timezone.utc),
                interval="invalid",
            )

            with pytest.raises(DataValidationError, match="Invalid interval"):
                await provider.fetch_price_data(request)

    @pytest.mark.asyncio
    async def test_fetch_price_data_success(self, provider: IBDataProvider) -> None:
        """Test successful data fetch.

        Args:
            provider: IBDataProvider instance fixture.
        """
        provider._connected = True

        # Mock IB bar response
        mock_bar = MagicMock()
        mock_bar.date = datetime(2025, 11, 26, 9, 30, tzinfo=timezone.utc)
        mock_bar.open = 276.96
        mock_bar.high = 279.05
        mock_bar.low = 276.96
        mock_bar.close = 277.28
        mock_bar.volume = 1922415

        with patch.object(provider.ib, "isConnected", return_value=True):
            with patch.object(
                provider.ib, "qualifyContractsAsync", new_callable=AsyncMock
            ) as mock_qualify:
                mock_qualify.return_value = [MagicMock()]

                with patch.object(
                    provider.ib, "reqHistoricalDataAsync", new_callable=AsyncMock
                ) as mock_hist:
                    mock_hist.return_value = [mock_bar]

                    request = PriceDataRequest(
                        symbol="AAPL",
                        start_date=datetime.now(timezone.utc) - timedelta(days=1),
                        end_date=datetime.now(timezone.utc),
                        interval="15m",
                    )

                    result = await provider.fetch_price_data(request)

                    assert len(result) == 1
                    assert result[0].symbol == "AAPL"
                    assert result[0].open_price == Decimal("276.96")
                    assert result[0].close_price == Decimal("277.28")
                    assert result[0].volume == 1922415

    @pytest.mark.asyncio
    async def test_fetch_price_data_symbol_not_found(
        self, provider: IBDataProvider
    ) -> None:
        """Test fetch_price_data raises SymbolNotFoundError for invalid symbol.

        Args:
            provider: IBDataProvider instance fixture.
        """
        provider._connected = True

        with patch.object(provider.ib, "isConnected", return_value=True):
            with patch.object(
                provider.ib, "qualifyContractsAsync", new_callable=AsyncMock
            ) as mock_qualify:
                mock_qualify.return_value = []

                request = PriceDataRequest(
                    symbol="INVALID",
                    start_date=datetime.now(timezone.utc) - timedelta(days=1),
                    end_date=datetime.now(timezone.utc),
                    interval="15m",
                )

                with pytest.raises(SymbolNotFoundError):
                    await provider.fetch_price_data(request)

    def test_validate_price_point_valid(self, provider: IBDataProvider) -> None:
        """Test _validate_price_point with valid data.

        Args:
            provider: IBDataProvider instance fixture.
        """
        point = PriceDataPoint(
            symbol="AAPL",
            timestamp=datetime.now(timezone.utc),
            open_price=Decimal("100.00"),
            high_price=Decimal("105.00"),
            low_price=Decimal("99.00"),
            close_price=Decimal("102.00"),
            volume=1000,
        )
        provider._validate_price_point(point)

    def test_validate_price_point_high_less_than_low(
        self, provider: IBDataProvider
    ) -> None:
        """Test _validate_price_point rejects high < low.

        Args:
            provider: IBDataProvider instance fixture.
        """
        point = PriceDataPoint(
            symbol="AAPL",
            timestamp=datetime.now(timezone.utc),
            open_price=Decimal("100.00"),
            high_price=Decimal("95.00"),
            low_price=Decimal("99.00"),
            close_price=Decimal("102.00"),
            volume=1000,
        )

        with pytest.raises(DataValidationError, match="High price .* < Low price"):
            provider._validate_price_point(point)
