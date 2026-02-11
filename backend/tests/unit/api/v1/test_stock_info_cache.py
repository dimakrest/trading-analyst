"""Unit tests for stock info endpoint caching behavior.

Verifies:
- Finding 1 fix: cache-hit should NOT call the provider when
  name and exchange are stored in stock_sectors.
- Finding 3 fix: concurrent inserts for the same symbol don't crash
  (ON CONFLICT DO NOTHING).
"""
import pytest
from unittest.mock import AsyncMock
from httpx import AsyncClient
from sqlalchemy import text

from app.models.stock_sector import StockSector
from app.providers.base import SymbolInfo
from app.services.data_service import DataService


@pytest.fixture(autouse=True)
async def clean_stock_sectors(db_session):
    """Clean stock_sectors table before each test."""
    await db_session.execute(text("DELETE FROM stock_sectors"))
    await db_session.commit()


@pytest.mark.asyncio
class TestStockInfoCache:
    """Tests for GET /api/v1/stocks/{symbol}/info caching."""

    def _make_mock_data_service(self, info_return=None, info_side_effect=None):
        """Create a DataService with mocked provider."""
        # Create mock provider that returns SymbolInfo
        mock_provider = AsyncMock()

        if info_side_effect:
            mock_provider.get_symbol_info.side_effect = info_side_effect
        elif info_return:
            # Convert dict to SymbolInfo for provider mock
            mock_provider.get_symbol_info.return_value = SymbolInfo(
                symbol=info_return.get("symbol", "TEST"),
                name=info_return.get("name", "Test Company"),
                currency=info_return.get("currency", "USD"),
                exchange=info_return.get("exchange", "NYSE"),
                market_cap=info_return.get("market_cap"),
                sector=info_return.get("sector"),
                industry=info_return.get("industry"),
            )

        data_service = DataService(session_factory=None, provider=mock_provider)

        # Also mock get_symbol_info method to return dict (for backward compatibility)
        mock = AsyncMock()
        if info_side_effect:
            mock.side_effect = info_side_effect
        elif info_return:
            mock.return_value = info_return
        data_service.get_symbol_info = mock

        return data_service

    async def test_full_cache_hit_no_provider_call(self, app, db_session):
        """Full cache hit (name + exchange present) returns from DB only."""
        # Seed complete cache row
        db_session.add(StockSector(
            symbol="AAPL",
            sector="Technology",
            sector_etf="XLK",
            industry="Consumer Electronics",
            name="Apple Inc.",
            exchange="NASDAQ",
        ))
        await db_session.commit()

        # Mock provider — should NOT be called
        mock_ds = self._make_mock_data_service(
            info_side_effect=AssertionError("Provider should not be called on full cache hit"),
        )

        from app.core.deps import get_data_service
        app.dependency_overrides[get_data_service] = lambda: mock_ds

        async with AsyncClient(app=app, base_url="http://testserver") as client:
            response = await client.get("/api/v1/stocks/AAPL/info")

        assert response.status_code == 200
        data = response.json()
        assert data["symbol"] == "AAPL"
        assert data["name"] == "Apple Inc."
        assert data["exchange"] == "NASDAQ"
        assert data["sector"] == "Technology"
        assert data["sector_etf"] == "XLK"
        assert data["industry"] == "Consumer Electronics"

        # Verify provider was never called
        mock_ds.get_symbol_info.assert_not_called()

        app.dependency_overrides.pop(get_data_service, None)

    async def test_partial_cache_hit_calls_provider(self, app, db_session):
        """Partial cache hit (NULL name) falls back to provider for name/exchange."""
        # Seed old row without name/exchange
        db_session.add(StockSector(
            symbol="MSFT",
            sector="Technology",
            sector_etf="XLK",
            industry="Software",
            name=None,
            exchange=None,
        ))
        await db_session.commit()

        mock_ds = self._make_mock_data_service(info_return={
            "symbol": "MSFT",
            "name": "Microsoft Corporation",
            "currency": "USD",
            "exchange": "NASDAQ",
            "market_cap": 3_000_000_000_000,
            "sector": "Technology",
            "industry": "Software",
        })

        from app.core.deps import get_data_service
        app.dependency_overrides[get_data_service] = lambda: mock_ds

        async with AsyncClient(app=app, base_url="http://testserver") as client:
            response = await client.get("/api/v1/stocks/MSFT/info")

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Microsoft Corporation"
        assert data["exchange"] == "NASDAQ"
        # Sector info from cache
        assert data["sector_etf"] == "XLK"

        # After refactor: endpoint calls get_sector_etf() which internally calls provider
        # The provider's get_symbol_info was called (not the endpoint's method)
        assert mock_ds.provider.get_symbol_info.called

        app.dependency_overrides.pop(get_data_service, None)

    async def test_cache_miss_stores_name_and_exchange(self, app, db_session):
        """Cache miss stores complete data including name and exchange."""
        mock_ds = self._make_mock_data_service(info_return={
            "symbol": "TSLA",
            "name": "Tesla, Inc.",
            "currency": "USD",
            "exchange": "NASDAQ",
            "market_cap": 800_000_000_000,
            "sector": "Consumer Cyclical",
            "industry": "Auto Manufacturers",
        })

        from app.core.deps import get_data_service
        app.dependency_overrides[get_data_service] = lambda: mock_ds

        async with AsyncClient(app=app, base_url="http://testserver") as client:
            response = await client.get("/api/v1/stocks/TSLA/info")

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Tesla, Inc."
        assert data["exchange"] == "NASDAQ"

        # Verify DB row has name and exchange
        from sqlalchemy import select
        result = await db_session.execute(
            select(StockSector).where(StockSector.symbol == "TSLA")
        )
        cached = result.scalar_one_or_none()
        assert cached is not None
        assert cached.name == "Tesla, Inc."
        assert cached.exchange == "NASDAQ"
        assert cached.sector == "Consumer Cyclical"
        assert cached.sector_etf == "XLY"

        app.dependency_overrides.pop(get_data_service, None)

    async def test_concurrent_cache_miss_no_integrity_error(self, app, db_session):
        """Two concurrent cache-miss requests for same symbol don't crash.

        Verifies Finding 3 fix: ON CONFLICT DO NOTHING makes the insert
        idempotent, so the second request succeeds instead of raising
        IntegrityError.
        """
        import asyncio

        mock_ds = self._make_mock_data_service(info_return={
            "symbol": "GOOG",
            "name": "Alphabet Inc.",
            "currency": "USD",
            "exchange": "NASDAQ",
            "market_cap": 2_000_000_000_000,
            "sector": "Communication Services",
            "industry": "Internet Content & Information",
        })

        from app.core.deps import get_data_service
        app.dependency_overrides[get_data_service] = lambda: mock_ds

        async def make_request():
            async with AsyncClient(app=app, base_url="http://testserver") as client:
                return await client.get("/api/v1/stocks/GOOG/info")

        # Fire two concurrent requests — both will miss cache
        r1, r2 = await asyncio.gather(make_request(), make_request())

        assert r1.status_code == 200
        assert r2.status_code == 200
        assert r1.json()["name"] == "Alphabet Inc."
        assert r2.json()["name"] == "Alphabet Inc."

        # Only one row in DB
        from sqlalchemy import select, func
        result = await db_session.execute(
            select(func.count()).select_from(StockSector).where(
                StockSector.symbol == "GOOG"
            )
        )
        assert result.scalar() == 1

        app.dependency_overrides.pop(get_data_service, None)

    async def test_data_service_get_sector_etf_stores_name_exchange(self, db_session, test_session_factory):
        """DataService.get_sector_etf() stores name and exchange on cache miss."""
        mock_provider = AsyncMock()
        mock_provider.get_symbol_info.return_value = SymbolInfo(
            symbol="NVDA",
            name="NVIDIA Corporation",
            currency="USD",
            exchange="NASDAQ",
            market_cap=2_000_000_000_000,
            sector="Technology",
            industry="Semiconductors",
        )

        data_service = DataService(
            session_factory=test_session_factory,
            provider=mock_provider,
        )

        async with test_session_factory() as session:
            sector_etf = await data_service.get_sector_etf("NVDA", session)
            await session.commit()

        assert sector_etf == "XLK"

        # Verify DB row has name and exchange
        from sqlalchemy import select
        async with test_session_factory() as session:
            result = await session.execute(
                select(StockSector).where(StockSector.symbol == "NVDA")
            )
            cached = result.scalar_one_or_none()

        assert cached is not None
        assert cached.name == "NVIDIA Corporation"
        assert cached.exchange == "NASDAQ"
        assert cached.sector == "Technology"
        assert cached.sector_etf == "XLK"

    async def test_data_service_concurrent_get_sector_etf_no_integrity_error(self, db_session, test_session_factory):
        """Two concurrent get_sector_etf calls for same symbol don't crash.

        Verifies Finding 3 fix at the data_service layer.
        """
        import asyncio

        mock_provider = AsyncMock()
        mock_provider.get_symbol_info.return_value = SymbolInfo(
            symbol="AMD",
            name="Advanced Micro Devices",
            currency="USD",
            exchange="NASDAQ",
            market_cap=200_000_000_000,
            sector="Technology",
            industry="Semiconductors",
        )

        data_service = DataService(
            session_factory=test_session_factory,
            provider=mock_provider,
        )

        async def call_get_sector_etf():
            async with test_session_factory() as session:
                result = await data_service.get_sector_etf("AMD", session)
                await session.commit()
                return result

        r1, r2 = await asyncio.gather(
            call_get_sector_etf(), call_get_sector_etf()
        )

        assert r1 == "XLK"
        assert r2 == "XLK"

        # Only one row in DB
        from sqlalchemy import select, func
        async with test_session_factory() as session:
            result = await session.execute(
                select(func.count()).select_from(StockSector).where(
                    StockSector.symbol == "AMD"
                )
            )
            assert result.scalar() == 1
