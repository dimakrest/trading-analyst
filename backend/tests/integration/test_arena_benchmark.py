"""Integration tests for the Arena benchmark endpoint.

Tests verify:
1. 404 is returned for a non-existent simulation
2. Correct normalized cumulative return data for a valid simulation
3. Empty list returned (not error) when data_service returns no bars
4. 422 returned for a disallowed symbol (anything other than SPY or QQQ)
"""

from datetime import date, datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.arena import ArenaSimulation, SimulationStatus
from app.providers.base import PriceDataPoint

# Mark all tests in this module as integration tests
pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_price_bar(symbol: str, date_val: date, close: str) -> PriceDataPoint:
    """Build a PriceDataPoint with a UTC midnight timestamp for the given date."""
    return PriceDataPoint(
        symbol=symbol,
        timestamp=datetime.combine(date_val, datetime.min.time(), tzinfo=timezone.utc),
        open_price=Decimal(close),
        high_price=Decimal(close),
        low_price=Decimal(close),
        close_price=Decimal(close),
        volume=1_000_000,
    )


def _make_mock_data_service(bars: list[PriceDataPoint]) -> MagicMock:
    """Return a mock DataService whose get_price_data returns the provided bars."""
    mock_ds = MagicMock()
    mock_ds.get_price_data = AsyncMock(return_value=bars)
    return mock_ds


async def _seed_simulation(db_session: AsyncSession) -> ArenaSimulation:
    """Insert a minimal completed simulation and return it."""
    simulation = ArenaSimulation(
        name="Benchmark Test Simulation",
        symbols=["AAPL"],
        start_date=date(2024, 1, 2),
        end_date=date(2024, 1, 31),
        initial_capital=Decimal("10000"),
        position_size=Decimal("1000"),
        agent_type="live20",
        agent_config={"trailing_stop_pct": 5.0, "min_buy_score": 60},
        status=SimulationStatus.COMPLETED.value,
        current_day=20,
        total_days=20,
        total_trades=0,
        winning_trades=0,
    )
    db_session.add(simulation)
    await db_session.commit()
    return simulation


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_benchmark_data_returns_404_for_nonexistent_simulation(
    app,
    async_client: AsyncClient,
) -> None:
    """GET /simulations/{id}/benchmark returns 404 when simulation does not exist.

    Uses a deliberately large simulation_id (999999) that will not be present
    in the test database.
    """
    # Arrange — inject a mock data_service to avoid real API calls
    from app.core.deps import get_data_service

    mock_ds = _make_mock_data_service([])
    app.dependency_overrides[get_data_service] = lambda: mock_ds

    try:
        # Act
        response = await async_client.get("/api/v1/arena/simulations/999999/benchmark")

        # Assert
        assert response.status_code == 404
        assert response.json()["detail"] == "Simulation not found"
    finally:
        app.dependency_overrides.pop(get_data_service, None)


@pytest.mark.asyncio
async def test_get_benchmark_data_returns_normalized_cumulative_return(
    app,
    async_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """GET /simulations/{id}/benchmark returns correct normalized cumulative return data.

    Given three bars with closing prices 100, 110, and 90:
    - Day 1: (100 - 100) / 100 * 100 = 0.00%
    - Day 2: (110 - 100) / 100 * 100 = 10.00%
    - Day 3: (90 - 100) / 100 * 100 = -10.00%
    """
    # Arrange
    simulation = await _seed_simulation(db_session)

    bars = [
        _make_price_bar("SPY", date(2024, 1, 2), "100.00"),
        _make_price_bar("SPY", date(2024, 1, 3), "110.00"),
        _make_price_bar("SPY", date(2024, 1, 4), "90.00"),
    ]
    from app.core.deps import get_data_service

    mock_ds = _make_mock_data_service(bars)
    app.dependency_overrides[get_data_service] = lambda: mock_ds

    try:
        # Act
        response = await async_client.get(
            f"/api/v1/arena/simulations/{simulation.id}/benchmark",
            params={"symbol": "SPY"},
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3

        assert data[0]["date"] == "2024-01-02"
        assert Decimal(data[0]["close"]) == Decimal("100.00")
        assert Decimal(data[0]["cumulative_return_pct"]) == Decimal("0.00")

        assert data[1]["date"] == "2024-01-03"
        assert Decimal(data[1]["close"]) == Decimal("110.00")
        assert Decimal(data[1]["cumulative_return_pct"]) == Decimal("10.00")

        assert data[2]["date"] == "2024-01-04"
        assert Decimal(data[2]["close"]) == Decimal("90.00")
        assert Decimal(data[2]["cumulative_return_pct"]) == Decimal("-10.00")
    finally:
        app.dependency_overrides.pop(get_data_service, None)


@pytest.mark.asyncio
async def test_get_benchmark_data_returns_empty_list_when_no_price_data(
    app,
    async_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """GET /simulations/{id}/benchmark returns [] when data_service has no bars.

    This covers the case where benchmark data is unavailable for the requested
    symbol in the simulation's date range (e.g. data not yet cached).
    """
    # Arrange
    simulation = await _seed_simulation(db_session)

    from app.core.deps import get_data_service

    mock_ds = _make_mock_data_service([])
    app.dependency_overrides[get_data_service] = lambda: mock_ds

    try:
        # Act
        response = await async_client.get(
            f"/api/v1/arena/simulations/{simulation.id}/benchmark",
            params={"symbol": "QQQ"},
        )

        # Assert
        assert response.status_code == 200
        assert response.json() == []
    finally:
        app.dependency_overrides.pop(get_data_service, None)


@pytest.mark.asyncio
async def test_get_benchmark_data_returns_422_for_disallowed_symbol(
    async_client: AsyncClient,
) -> None:
    """GET /simulations/{id}/benchmark returns 422 for symbols other than SPY or QQQ.

    FastAPI/Pydantic validates the Literal["SPY", "QQQ"] constraint and rejects
    any other value with a 422 Unprocessable Entity response before hitting the
    endpoint handler.
    """
    # Act — use any simulation_id; validation fires before DB lookup
    response = await async_client.get(
        "/api/v1/arena/simulations/1/benchmark",
        params={"symbol": "IWM"},
    )

    # Assert
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_get_benchmark_data_supports_qqq_symbol(
    app,
    async_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """GET /simulations/{id}/benchmark accepts QQQ as a valid benchmark symbol.

    Verifies both allowed values (SPY tested above, QQQ tested here) pass
    the Literal constraint and return a 200 response with correct data.
    """
    # Arrange
    simulation = await _seed_simulation(db_session)

    bars = [
        _make_price_bar("QQQ", date(2024, 1, 2), "400.00"),
        _make_price_bar("QQQ", date(2024, 1, 3), "420.00"),
    ]
    from app.core.deps import get_data_service

    mock_ds = _make_mock_data_service(bars)
    app.dependency_overrides[get_data_service] = lambda: mock_ds

    try:
        # Act
        response = await async_client.get(
            f"/api/v1/arena/simulations/{simulation.id}/benchmark",
            params={"symbol": "QQQ"},
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["date"] == "2024-01-02"
        assert Decimal(data[0]["cumulative_return_pct"]) == Decimal("0.00")
        assert data[1]["date"] == "2024-01-03"
        # (420 - 400) / 400 * 100 = 5.00%
        assert Decimal(data[1]["cumulative_return_pct"]) == Decimal("5.00")
    finally:
        app.dependency_overrides.pop(get_data_service, None)


@pytest.mark.asyncio
async def test_get_benchmark_data_default_symbol_is_spy(
    app,
    async_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """GET /simulations/{id}/benchmark defaults to SPY when no symbol param given.

    Verifies the default value and that data_service is called with 'SPY'.
    """
    # Arrange
    simulation = await _seed_simulation(db_session)

    bars = [_make_price_bar("SPY", date(2024, 1, 2), "475.00")]
    from app.core.deps import get_data_service

    mock_ds = _make_mock_data_service(bars)
    app.dependency_overrides[get_data_service] = lambda: mock_ds

    try:
        # Act — omit symbol param to trigger default
        response = await async_client.get(
            f"/api/v1/arena/simulations/{simulation.id}/benchmark"
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1

        # Verify data_service was called with SPY
        call_kwargs = mock_ds.get_price_data.call_args.kwargs
        assert call_kwargs["symbol"] == "SPY"
    finally:
        app.dependency_overrides.pop(get_data_service, None)
