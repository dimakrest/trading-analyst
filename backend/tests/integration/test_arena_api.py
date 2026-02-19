"""Integration tests for Arena API endpoints.

Tests verify:
1. Creating simulations with portfolio params stored correctly in agent_config
2. GET /portfolio-strategies returns all 4 strategies
3. Backward compatibility — creation without portfolio params defaults to "none"
4. Invalid portfolio_strategy returns 422 validation error
5. GET /simulations/{id} returns sector field on each position
"""

from datetime import date
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.arena import ArenaPosition, ArenaSimulation, SimulationStatus
from app.models.stock_sector import StockSector

# Mark all tests in this module as integration tests
pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

VALID_SIMULATION_PAYLOAD = {
    "symbols": ["AAPL", "MSFT"],
    "start_date": "2024-01-02",
    "end_date": "2024-01-31",
    "initial_capital": "10000",
    "position_size": "1000",
    "agent_type": "live20",
    "trailing_stop_pct": 5.0,
    "min_buy_score": 60,
}


# ---------------------------------------------------------------------------
# Portfolio Strategies Endpoint
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_portfolio_strategies_returns_all_four(async_client: AsyncClient) -> None:
    """GET /portfolio-strategies returns all 4 registered strategies."""
    response = await async_client.get("/api/v1/arena/portfolio-strategies")

    assert response.status_code == 200
    strategies = response.json()

    assert isinstance(strategies, list)
    assert len(strategies) == 4

    names = {s["name"] for s in strategies}
    assert names == {
        "none",
        "score_sector_low_atr",
        "score_sector_high_atr",
        "score_sector_moderate_atr",
    }

    # Each strategy must have a non-empty description
    for strategy in strategies:
        assert "name" in strategy
        assert "description" in strategy
        assert strategy["description"], f"Strategy '{strategy['name']}' has empty description"


# ---------------------------------------------------------------------------
# Create Simulation — Portfolio Params
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_simulation_with_portfolio_strategy_stores_in_agent_config(
    async_client: AsyncClient,
) -> None:
    """POST /simulations with portfolio params stores them correctly in the response."""
    payload = {
        **VALID_SIMULATION_PAYLOAD,
        "portfolio_strategy": "score_sector_low_atr",
        "max_per_sector": 2,
        "max_open_positions": 10,
    }
    response = await async_client.post("/api/v1/arena/simulations", json=payload)

    assert response.status_code == 202
    data = response.json()

    assert data["portfolio_strategy"] == "score_sector_low_atr"
    assert data["max_per_sector"] == 2
    assert data["max_open_positions"] == 10


@pytest.mark.asyncio
async def test_create_simulation_without_portfolio_params_defaults_to_none(
    async_client: AsyncClient,
) -> None:
    """POST /simulations without portfolio params defaults to 'none' strategy (backward compat)."""
    response = await async_client.post("/api/v1/arena/simulations", json=VALID_SIMULATION_PAYLOAD)

    assert response.status_code == 202
    data = response.json()

    assert data["portfolio_strategy"] == "none"
    assert data["max_per_sector"] is None
    assert data["max_open_positions"] is None


@pytest.mark.asyncio
async def test_create_simulation_with_high_atr_strategy(async_client: AsyncClient) -> None:
    """POST /simulations with score_sector_high_atr strategy stores correctly."""
    payload = {
        **VALID_SIMULATION_PAYLOAD,
        "portfolio_strategy": "score_sector_high_atr",
        "max_per_sector": 3,
    }
    response = await async_client.post("/api/v1/arena/simulations", json=payload)

    assert response.status_code == 202
    data = response.json()

    assert data["portfolio_strategy"] == "score_sector_high_atr"
    assert data["max_per_sector"] == 3
    assert data["max_open_positions"] is None


@pytest.mark.asyncio
async def test_create_simulation_with_moderate_atr_strategy(async_client: AsyncClient) -> None:
    """POST /simulations with score_sector_moderate_atr strategy stores correctly."""
    payload = {
        **VALID_SIMULATION_PAYLOAD,
        "portfolio_strategy": "score_sector_moderate_atr",
        "max_open_positions": 5,
    }
    response = await async_client.post("/api/v1/arena/simulations", json=payload)

    assert response.status_code == 202
    data = response.json()

    assert data["portfolio_strategy"] == "score_sector_moderate_atr"
    assert data["max_per_sector"] is None
    assert data["max_open_positions"] == 5


@pytest.mark.asyncio
async def test_create_simulation_with_invalid_portfolio_strategy_returns_422(
    async_client: AsyncClient,
) -> None:
    """POST /simulations with invalid portfolio_strategy returns 422 validation error."""
    payload = {
        **VALID_SIMULATION_PAYLOAD,
        "portfolio_strategy": "nonexistent_strategy",
    }
    response = await async_client.post("/api/v1/arena/simulations", json=payload)

    assert response.status_code == 422
    error_data = response.json()
    # Verify the error message mentions the unknown strategy
    error_str = str(error_data)
    assert "nonexistent_strategy" in error_str or "portfolio_strategy" in error_str


@pytest.mark.asyncio
async def test_create_simulation_max_per_sector_below_minimum_returns_422(
    async_client: AsyncClient,
) -> None:
    """max_per_sector must be >= 1; value of 0 returns 422."""
    payload = {
        **VALID_SIMULATION_PAYLOAD,
        "portfolio_strategy": "score_sector_low_atr",
        "max_per_sector": 0,
    }
    response = await async_client.post("/api/v1/arena/simulations", json=payload)

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_simulation_max_open_positions_below_minimum_returns_422(
    async_client: AsyncClient,
) -> None:
    """max_open_positions must be >= 1; value of 0 returns 422."""
    payload = {
        **VALID_SIMULATION_PAYLOAD,
        "portfolio_strategy": "score_sector_low_atr",
        "max_open_positions": 0,
    }
    response = await async_client.post("/api/v1/arena/simulations", json=payload)

    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Sector Enrichment on Position Responses
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_simulation_positions_include_sector_when_stock_sector_exists(
    async_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """GET /simulations/{id} returns sector field populated from stock_sectors table.

    Creates a simulation with one position for AAPL and a matching StockSector
    record. Verifies that the sector field in the position response reflects
    the value stored in stock_sectors.
    """
    # Seed sector data for AAPL
    stock_sector = StockSector(
        symbol="AAPL",
        sector="Technology",
        industry="Consumer Electronics",
        name="Apple Inc.",
    )
    db_session.add(stock_sector)

    # Create a completed simulation
    simulation = ArenaSimulation(
        name="Sector Enrichment Test",
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
        total_trades=1,
        winning_trades=1,
    )
    db_session.add(simulation)
    await db_session.flush()

    # Create one closed position for AAPL
    position = ArenaPosition(
        simulation_id=simulation.id,
        symbol="AAPL",
        status="closed",
        signal_date=date(2024, 1, 3),
        entry_date=date(2024, 1, 4),
        entry_price=Decimal("150.00"),
        shares=6,
        trailing_stop_pct=Decimal("5.00"),
        exit_date=date(2024, 1, 10),
        exit_price=Decimal("160.00"),
        exit_reason="stop_hit",
        realized_pnl=Decimal("60.00"),
        return_pct=Decimal("6.6667"),
    )
    db_session.add(position)
    await db_session.commit()

    response = await async_client.get(f"/api/v1/arena/simulations/{simulation.id}")

    assert response.status_code == 200
    data = response.json()

    assert len(data["positions"]) == 1
    position_data = data["positions"][0]
    assert "sector" in position_data
    assert position_data["sector"] == "Technology"


@pytest.mark.asyncio
async def test_get_simulation_positions_sector_is_none_when_no_stock_sector_record(
    async_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """GET /simulations/{id} returns sector=None when symbol is absent from stock_sectors.

    Verifies graceful handling when a position symbol has no entry in the
    stock_sectors table (new or obscure ticker).
    """
    # Create a completed simulation for a symbol with no sector record
    simulation = ArenaSimulation(
        name="No Sector Record Test",
        symbols=["UNKN"],
        start_date=date(2024, 1, 2),
        end_date=date(2024, 1, 31),
        initial_capital=Decimal("10000"),
        position_size=Decimal("1000"),
        agent_type="live20",
        agent_config={"trailing_stop_pct": 5.0, "min_buy_score": 60},
        status=SimulationStatus.COMPLETED.value,
        current_day=20,
        total_days=20,
        total_trades=1,
        winning_trades=0,
    )
    db_session.add(simulation)
    await db_session.flush()

    position = ArenaPosition(
        simulation_id=simulation.id,
        symbol="UNKN",
        status="closed",
        signal_date=date(2024, 1, 3),
        entry_date=date(2024, 1, 4),
        entry_price=Decimal("50.00"),
        shares=20,
        trailing_stop_pct=Decimal("5.00"),
        exit_date=date(2024, 1, 8),
        exit_price=Decimal("48.00"),
        exit_reason="stop_hit",
        realized_pnl=Decimal("-40.00"),
        return_pct=Decimal("-4.0000"),
    )
    db_session.add(position)
    await db_session.commit()

    response = await async_client.get(f"/api/v1/arena/simulations/{simulation.id}")

    assert response.status_code == 200
    data = response.json()

    assert len(data["positions"]) == 1
    position_data = data["positions"][0]
    assert "sector" in position_data
    assert position_data["sector"] is None
