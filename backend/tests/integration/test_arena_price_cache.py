"""Integration tests for Arena price cache loading.

Tests the full DB → DataService → Cache → Engine pipeline,
verifying correct data transformation and concurrent loading behavior.
"""

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from sqlalchemy import text

from app.models.stock import StockPrice
from app.providers.mock import MockMarketDataProvider
from app.services.arena.simulation_engine import SimulationEngine
from app.services.arena.agent_protocol import PriceBar
from app.services.data_service import DataService


@pytest_asyncio.fixture(autouse=True)
async def clean_stock_prices(test_session_factory):
    """Clean stock_prices before each test to prevent data leakage."""
    async with test_session_factory() as session:
        await session.execute(text("DELETE FROM stock_prices"))
        await session.commit()
    yield


@pytest_asyncio.fixture
async def mock_provider():
    """Create mock provider that returns empty data (force DB usage only)."""
    provider = MockMarketDataProvider()
    # Mock fetch to return empty list (forces DataService to use only DB data)
    provider.fetch_price_data = AsyncMock(return_value=[])
    return provider


@pytest.mark.integration
async def test_load_price_cache_with_real_data(
    test_session_factory,
    mock_provider,
):
    """Test _load_price_cache loads real DB data and transforms correctly.

    Verifies:
    - Real StockPrice records → PriceBar transformation
    - Decimal precision preserved
    - Timezone handling (DB timestamp → date)
    - Volume type conversion (int)
    - Multiple symbols loaded correctly
    """
    # Arrange: Create real StockPrice records
    symbols = ["AAPL", "MSFT", "GOOGL"]
    start_date = date(2024, 1, 15)
    lookback_start = date(2024, 1, 1)

    # Seed 30 days of data for 3 symbols
    async with test_session_factory() as setup_session:
        for symbol in symbols:
            for i in range(30):
                current_date = lookback_start + timedelta(days=i)
                price_record = StockPrice(
                    symbol=symbol,
                    timestamp=datetime.combine(
                        current_date, datetime.min.time(), tzinfo=timezone.utc
                    ),
                    open_price=Decimal("100.50") + i,
                    high_price=Decimal("105.75") + i,
                    low_price=Decimal("98.25") + i,
                    close_price=Decimal("103.00") + i,
                    volume=1000000 + (i * 10000),
                    interval="1d",
                    data_source="manual",
                    last_fetched_at=datetime.now(timezone.utc),  # Mark as fresh
                )
                setup_session.add(price_record)
        await setup_session.commit()

    # Act: Load price cache using mocked provider
    async with test_session_factory() as engine_session:
        # Create DataService with mocked provider
        data_service = DataService(
            session_factory=test_session_factory,
            provider=mock_provider,
        )

        # Create engine with custom data_service
        engine = SimulationEngine(engine_session, session_factory=test_session_factory)
        engine.data_service = data_service
        simulation_id = 1

        await engine._load_price_cache(
            simulation_id=simulation_id,
            symbols=symbols,
            start_date=start_date,
            end_date=date(2024, 1, 31),
            lookback_days=14,
        )

        # Assert: Verify cache populated correctly
        assert simulation_id in engine._price_cache
        cache = engine._price_cache[simulation_id]

        # Verify all symbols present
        assert set(cache.keys()) == set(symbols)

        # Verify AAPL data transformation
        aapl_bars = cache["AAPL"]
        assert len(aapl_bars) == 30

        # Verify first bar's transformation accuracy
        first_bar = aapl_bars[0]
        assert isinstance(first_bar, PriceBar)
        assert first_bar.date == lookback_start
        assert first_bar.open == Decimal("100.50")
        assert first_bar.high == Decimal("105.75")
        assert first_bar.low == Decimal("98.25")
        assert first_bar.close == Decimal("103.00")
        assert first_bar.volume == 1000000
        assert isinstance(first_bar.volume, int)

        # Verify Decimal precision preserved (not float)
        assert isinstance(first_bar.open, Decimal)
        assert isinstance(first_bar.high, Decimal)


@pytest.mark.integration
async def test_load_price_cache_concurrent_loading(
    test_session_factory,
    mock_provider,
):
    """Test that concurrent symbol loading completes successfully.

    Verifies:
    - All symbols load in parallel
    - No data corruption from concurrent DB access
    """
    # Arrange: Seed data for 20 symbols
    symbols = [f"SYM{i:03d}" for i in range(20)]
    base_date = date(2024, 1, 1)

    async with test_session_factory() as setup_session:
        for symbol in symbols:
            for i in range(10):
                current_date = base_date + timedelta(days=i)
                price_record = StockPrice(
                    symbol=symbol,
                    timestamp=datetime.combine(
                        current_date, datetime.min.time(), tzinfo=timezone.utc
                    ),
                    open_price=Decimal("50.00"),
                    high_price=Decimal("52.00"),
                    low_price=Decimal("48.00"),
                    close_price=Decimal("51.00"),
                    volume=500000,
                    interval="1d",
                    data_source="manual",
                    last_fetched_at=datetime.now(timezone.utc),  # Mark as fresh
                )
                setup_session.add(price_record)
        await setup_session.commit()

    # Act: Load cache for all symbols using mocked provider
    async with test_session_factory() as engine_session:
        # Create DataService with mocked provider
        data_service = DataService(
            session_factory=test_session_factory,
            provider=mock_provider,
        )

        # Create engine with custom data_service
        engine = SimulationEngine(engine_session, session_factory=test_session_factory)
        engine.data_service = data_service
        simulation_id = 2

        await engine._load_price_cache(
            simulation_id=simulation_id,
            symbols=symbols,
            start_date=base_date,
            end_date=base_date + timedelta(days=9),
            lookback_days=0,
        )

        # Assert: All symbols loaded
        cache = engine._price_cache[simulation_id]
        assert len(cache) == 20

        for symbol in symbols:
            assert symbol in cache
            assert len(cache[symbol]) == 10


@pytest.mark.integration
async def test_load_price_cache_idempotent(
    test_session_factory,
    mock_provider,
):
    """Test that calling _load_price_cache twice doesn't reload data."""
    # Arrange: Seed minimal data
    symbol = "TEST"
    async with test_session_factory() as setup_session:
        price_record = StockPrice(
            symbol=symbol,
            timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc),
            open_price=Decimal("100.00"),
            high_price=Decimal("101.00"),
            low_price=Decimal("99.00"),
            close_price=Decimal("100.50"),
            volume=1000000,
            interval="1d",
            data_source="manual",
            last_fetched_at=datetime.now(timezone.utc),  # Mark as fresh
        )
        setup_session.add(price_record)
        await setup_session.commit()

    # Act: Load cache twice using mocked provider
    async with test_session_factory() as engine_session:
        # Create DataService with mocked provider
        data_service = DataService(
            session_factory=test_session_factory,
            provider=mock_provider,
        )

        # Create engine with custom data_service
        engine = SimulationEngine(engine_session, session_factory=test_session_factory)
        engine.data_service = data_service
        simulation_id = 3

        await engine._load_price_cache(
            simulation_id=simulation_id,
            symbols=[symbol],
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 1),
            lookback_days=0,
        )

        cache_after_first = engine._price_cache[simulation_id]

        await engine._load_price_cache(
            simulation_id=simulation_id,
            symbols=[symbol],
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 1),
            lookback_days=0,
        )

        cache_after_second = engine._price_cache[simulation_id]

        # Assert: Cache unchanged (same object reference)
        assert cache_after_first is cache_after_second
