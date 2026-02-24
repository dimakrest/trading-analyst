"""Unit tests for Live20Service.

Tests service-layer concerns:
- Database operations
- Error handling
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
from app.services.live20_service import Live20Service


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
                volume=1000000,
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

            result = await service._analyze_symbol("AAPL")

            assert result.status == "success"
            assert result.symbol == "AAPL"
            assert result.recommendation is not None
            assert result.recommendation.source == RecommendationSource.LIVE_20.value
            assert result.recommendation.stock == "AAPL"

    @pytest.mark.asyncio
    async def test_analyze_symbol_persists_atr_and_rvol(self, service, mock_session_factory, sample_price_data):
        """Test that ATR and rvol are persisted in the recommendation."""
        with patch(
            "app.services.live20_service.DataService.get_price_data",
            new_callable=AsyncMock,
        ) as mock_get_data:
            mock_get_data.return_value = sample_price_data

            result = await service._analyze_symbol("AAPL")

            assert result.status == "success"
            rec = result.recommendation

            # Verify ATR is persisted
            assert rec.live20_atr is not None
            assert isinstance(rec.live20_atr, Decimal)
            assert rec.live20_atr > Decimal("0")

            # Verify rvol is persisted
            assert rec.live20_rvol is not None
            assert isinstance(rec.live20_rvol, Decimal)
            # rvol should be a ratio (typically 0.x to 3.x)
            assert rec.live20_rvol >= Decimal("0")
            assert rec.live20_rvol < Decimal("100")

    @pytest.mark.asyncio
    async def test_analyze_symbol_invalid_symbol(self, service):
        """Test analysis with invalid symbol."""
        result = await service._analyze_symbol("")

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

            result = await service._analyze_symbol("AAPL")

            assert result.status == "error"
            assert "Insufficient data" in result.error_message

    @pytest.mark.asyncio
    async def test_analyze_symbol_persists_support_resistance(self, service, mock_session_factory, sample_price_data):
        """Test that cluster-based S/R levels (support_1, resistance_1) and touch counts are persisted."""
        from app.indicators.technical import SRLevel

        mock_support = SRLevel(price=125.0, touches=3, strength=0.75, last_touch_idx=20)
        mock_resistance = SRLevel(price=135.0, touches=4, strength=0.85, last_touch_idx=25)

        with patch(
            "app.services.live20_service.DataService.get_price_data",
            new_callable=AsyncMock,
        ) as mock_get_data, patch(
            "app.services.live20_service.cluster_support_resistance",
        ) as mock_cluster_sr:
            mock_get_data.return_value = sample_price_data
            # Return support below price (125.0) and resistance above price (135.0)
            # The service iterates levels sorted by strength desc; put resistance first
            # so both branches are exercised. The service picks by price vs current_price.
            mock_cluster_sr.return_value = [mock_resistance, mock_support]

            result = await service._analyze_symbol("AAPL")

            assert result.status == "success"
            rec = result.recommendation

            # Pivot is None in cluster-based S/R
            assert rec.live20_pivot is None

            # Support below current price
            assert rec.live20_support_1 == Decimal("125.0")
            assert rec.live20_support_1_touches == 3

            # Resistance above current price
            assert rec.live20_resistance_1 == Decimal("135.0")
            assert rec.live20_resistance_1_touches == 4
