"""Unit tests for Live20Service.

Tests service-layer concerns:
- Database operations
- Error handling
- Pricing integration
- Symbol validation

Note: Concurrency control is tested in worker tests, not service tests.
For evaluation logic tests, see test_live20_evaluator.py.
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.recommendation import RecommendationSource
from app.providers.base import PriceDataPoint
from app.services.live20_service import (
    Live20Result,
    Live20Service,
)
from app.services.pricing_strategies import PricingConfig


# Common fixtures for all test classes


@pytest.fixture
def mock_session_factory():
    """Create mock session factory."""
    session = AsyncMock()
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()

    factory = MagicMock()
    factory.return_value.__aenter__ = AsyncMock(return_value=session)
    factory.return_value.__aexit__ = AsyncMock()
    return factory


@pytest.fixture
def service(mock_session_factory):
    """Create Live20Service instance."""
    return Live20Service(mock_session_factory)


class TestLive20Service:
    """Test suite for Live20Service.

    Tests service-layer concerns only. Evaluation logic is tested
    in test_live20_evaluator.py.
    """

    @pytest.fixture
    def sample_price_data(self):
        """Create sample price data for testing."""
        base_date = datetime.now(timezone.utc) - timedelta(days=30)
        return [
            PriceDataPoint(
                symbol="AAPL",
                timestamp=base_date + timedelta(days=i),
                open_price=Decimal("100.0") + i,
                high_price=Decimal("102.0") + i,
                low_price=Decimal("99.0") + i,
                close_price=Decimal("101.0") + i,
                volume=Decimal("1000000"),
            )
            for i in range(30)
        ]

    @pytest.mark.asyncio
    async def test_analyze_symbol_success(self, service, mock_session_factory, sample_price_data):
        """Test successful symbol analysis."""
        with patch(
            "app.services.live20_service.DataService.get_price_data",
            new_callable=AsyncMock,
        ) as mock_get_data:
            mock_get_data.return_value = sample_price_data

            result = await service._analyze_symbol("AAPL", PricingConfig())

            assert result.status == "success"
            assert result.symbol == "AAPL"
            assert result.recommendation is not None
            assert result.recommendation.source == RecommendationSource.LIVE_20.value
            assert result.recommendation.stock == "AAPL"

    @pytest.mark.asyncio
    async def test_analyze_symbol_invalid_symbol(self, service):
        """Test analysis with invalid symbol."""
        result = await service._analyze_symbol("", PricingConfig())

        assert result.status == "error"
        assert "Invalid symbol" in result.error_message

    @pytest.mark.asyncio
    async def test_analyze_symbol_insufficient_data(self, service, mock_session_factory):
        """Test analysis with insufficient data."""
        with patch(
            "app.services.live20_service.DataService.get_price_data",
            new_callable=AsyncMock,
        ) as mock_get_data:
            mock_get_data.return_value = []  # No data

            result = await service._analyze_symbol("AAPL", PricingConfig())

            assert result.status == "error"
            assert "Insufficient data" in result.error_message
