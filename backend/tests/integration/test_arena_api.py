"""Integration tests for Arena API endpoints.

Tests verify:
1. Creating simulations with portfolio params stored correctly in agent_config
2. GET /portfolio-strategies returns all 4 strategies
3. Backward compatibility — creation without portfolio params defaults to "none"
4. Invalid portfolio_strategy returns 422 validation error
"""

import pytest
from httpx import AsyncClient

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
