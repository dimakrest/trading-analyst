"""Unit tests for Arena comparison API endpoints.

Tests for:
- POST /api/v1/arena/comparisons - Create comparison group
- GET /api/v1/arena/comparisons/{group_id} - Fetch comparison group
- group_id field in SimulationResponse (list and detail endpoints)
- Shared validator functions (symbols, date range, agent_type)
"""

from datetime import date
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.arena import ArenaSimulation, SimulationStatus


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

BASE_COMPARISON_REQUEST = {
    "symbols": ["AAPL", "MSFT"],
    "start_date": "2024-01-01",
    "end_date": "2024-06-30",
    "portfolio_strategies": ["none", "score_sector_low_atr"],
}


class TestCreateComparison:
    """Tests for POST /api/v1/arena/comparisons endpoint."""

    @pytest.mark.asyncio
    async def test_create_comparison_returns_202(
        self,
        async_client: AsyncClient,
        db_session: AsyncSession,
    ):
        """POST /comparisons returns 202 with comparison group data."""
        # Act
        response = await async_client.post(
            "/api/v1/arena/comparisons",
            json=BASE_COMPARISON_REQUEST,
        )

        # Assert
        assert response.status_code == 202
        data = response.json()
        assert "group_id" in data
        assert "simulations" in data
        assert isinstance(data["group_id"], str)
        assert len(data["group_id"]) == 36  # UUID format

    @pytest.mark.asyncio
    async def test_create_comparison_creates_n_simulations(
        self,
        async_client: AsyncClient,
        db_session: AsyncSession,
    ):
        """POST /comparisons creates one simulation per strategy."""
        # Arrange
        strategies = ["none", "score_sector_low_atr", "score_sector_high_atr"]
        request = {
            **BASE_COMPARISON_REQUEST,
            "portfolio_strategies": strategies,
        }

        # Act
        response = await async_client.post("/api/v1/arena/comparisons", json=request)

        # Assert
        assert response.status_code == 202
        data = response.json()
        assert len(data["simulations"]) == 3

    @pytest.mark.asyncio
    async def test_create_comparison_simulations_share_group_id(
        self,
        async_client: AsyncClient,
        db_session: AsyncSession,
    ):
        """All simulations in a comparison have the same group_id."""
        # Act
        response = await async_client.post(
            "/api/v1/arena/comparisons",
            json=BASE_COMPARISON_REQUEST,
        )

        # Assert
        assert response.status_code == 202
        data = response.json()
        group_id = data["group_id"]
        for sim in data["simulations"]:
            assert sim["group_id"] == group_id

    @pytest.mark.asyncio
    async def test_create_comparison_each_sim_has_distinct_portfolio_strategy(
        self,
        async_client: AsyncClient,
        db_session: AsyncSession,
    ):
        """Each simulation in the comparison has a different portfolio_strategy."""
        # Arrange
        strategies = ["none", "score_sector_low_atr"]
        request = {**BASE_COMPARISON_REQUEST, "portfolio_strategies": strategies}

        # Act
        response = await async_client.post("/api/v1/arena/comparisons", json=request)

        # Assert
        assert response.status_code == 202
        data = response.json()
        returned_strategies = [s["portfolio_strategy"] for s in data["simulations"]]
        assert sorted(returned_strategies) == sorted(strategies)

    @pytest.mark.asyncio
    async def test_create_comparison_sim_names_include_strategy(
        self,
        async_client: AsyncClient,
        db_session: AsyncSession,
    ):
        """Simulation names append the strategy name in brackets."""
        # Arrange
        request = {
            **BASE_COMPARISON_REQUEST,
            "name": "My Comparison",
            "portfolio_strategies": ["none", "score_sector_low_atr"],
        }

        # Act
        response = await async_client.post("/api/v1/arena/comparisons", json=request)

        # Assert
        assert response.status_code == 202
        data = response.json()
        names = {s["name"] for s in data["simulations"]}
        assert "My Comparison [none]" in names
        assert "My Comparison [score_sector_low_atr]" in names

    @pytest.mark.asyncio
    async def test_create_comparison_default_name_is_comparison(
        self,
        async_client: AsyncClient,
        db_session: AsyncSession,
    ):
        """When no name is provided, 'Comparison' is used as default prefix."""
        # Act
        response = await async_client.post(
            "/api/v1/arena/comparisons",
            json=BASE_COMPARISON_REQUEST,
        )

        # Assert
        assert response.status_code == 202
        data = response.json()
        for sim in data["simulations"]:
            assert sim["name"].startswith("Comparison [")

    @pytest.mark.asyncio
    async def test_create_comparison_all_sims_start_pending(
        self,
        async_client: AsyncClient,
        db_session: AsyncSession,
    ):
        """All created simulations start with PENDING status."""
        # Act
        response = await async_client.post(
            "/api/v1/arena/comparisons",
            json=BASE_COMPARISON_REQUEST,
        )

        # Assert
        assert response.status_code == 202
        data = response.json()
        for sim in data["simulations"]:
            assert sim["status"] == "pending"
            assert sim["current_day"] == 0
            assert sim["total_days"] == 0

    @pytest.mark.asyncio
    async def test_create_comparison_shared_base_config(
        self,
        async_client: AsyncClient,
        db_session: AsyncSession,
    ):
        """All simulations share the same symbols, dates, capital, and trailing stop."""
        # Arrange
        request = {
            "symbols": ["TSLA", "NVDA"],
            "start_date": "2024-03-01",
            "end_date": "2024-09-30",
            "initial_capital": 25000,
            "position_size": 2500,
            "trailing_stop_pct": 7.5,
            "min_buy_score": 70,
            "portfolio_strategies": ["none", "score_sector_high_atr"],
        }

        # Act
        response = await async_client.post("/api/v1/arena/comparisons", json=request)

        # Assert
        assert response.status_code == 202
        data = response.json()
        for sim in data["simulations"]:
            assert sim["symbols"] == ["TSLA", "NVDA"]
            assert sim["start_date"] == "2024-03-01"
            assert sim["end_date"] == "2024-09-30"
            assert Decimal(sim["initial_capital"]) == Decimal("25000")
            assert Decimal(sim["position_size"]) == Decimal("2500")
            assert sim["trailing_stop_pct"] == "7.5"
            assert sim["min_buy_score"] == 70

    @pytest.mark.asyncio
    async def test_create_comparison_with_agent_config_id_uses_config_algorithm(
        self,
        async_client: AsyncClient,
        db_session: AsyncSession,
    ):
        """When agent_config_id is provided, scoring_algorithm comes from the config."""
        # Arrange: create an agent config with rsi2 algorithm via the API
        config_response = await async_client.post(
            "/api/v1/agent-configs",
            json={"name": "RSI2 Config for Comparison", "scoring_algorithm": "rsi2"},
        )
        assert config_response.status_code == 201
        config_id = config_response.json()["id"]

        request = {
            **BASE_COMPARISON_REQUEST,
            "agent_config_id": config_id,
            "scoring_algorithm": "cci",  # Should be overridden by config
        }

        # Act
        response = await async_client.post("/api/v1/arena/comparisons", json=request)

        # Assert
        assert response.status_code == 202
        data = response.json()
        # All simulations must use rsi2, not cci
        for sim in data["simulations"]:
            assert sim["scoring_algorithm"] == "rsi2"

    @pytest.mark.asyncio
    async def test_create_comparison_nonexistent_agent_config_id_returns_404(
        self,
        async_client: AsyncClient,
        db_session: AsyncSession,
    ):
        """When agent_config_id doesn't exist, returns 404."""
        # Arrange
        request = {
            **BASE_COMPARISON_REQUEST,
            "agent_config_id": 999999,
        }

        # Act
        response = await async_client.post("/api/v1/arena/comparisons", json=request)

        # Assert
        assert response.status_code == 404
        assert "999999" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_create_comparison_requires_minimum_two_strategies(
        self,
        async_client: AsyncClient,
    ):
        """portfolio_strategies with length 1 returns 422."""
        # Arrange
        request = {
            **BASE_COMPARISON_REQUEST,
            "portfolio_strategies": ["none"],  # Only 1 strategy — too few
        }

        # Act
        response = await async_client.post("/api/v1/arena/comparisons", json=request)

        # Assert
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_comparison_requires_at_most_four_strategies(
        self,
        async_client: AsyncClient,
    ):
        """portfolio_strategies with length > 4 returns 422."""
        # Arrange
        request = {
            **BASE_COMPARISON_REQUEST,
            "portfolio_strategies": [
                "none",
                "score_sector_low_atr",
                "score_sector_high_atr",
                "score_sector_moderate_atr",
                "none",  # 5 entries — too many (and duplicates)
            ],
        }

        # Act
        response = await async_client.post("/api/v1/arena/comparisons", json=request)

        # Assert
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_comparison_rejects_duplicate_strategies(
        self,
        async_client: AsyncClient,
    ):
        """Duplicate portfolio_strategies returns 422."""
        # Arrange
        request = {
            **BASE_COMPARISON_REQUEST,
            "portfolio_strategies": ["none", "none"],  # Duplicates
        }

        # Act
        response = await async_client.post("/api/v1/arena/comparisons", json=request)

        # Assert
        assert response.status_code == 422
        assert "duplicate" in response.json()["detail"][0]["msg"].lower()

    @pytest.mark.asyncio
    async def test_create_comparison_rejects_unknown_strategy(
        self,
        async_client: AsyncClient,
    ):
        """Unknown strategy name in portfolio_strategies returns 422."""
        # Arrange
        request = {
            **BASE_COMPARISON_REQUEST,
            "portfolio_strategies": ["none", "nonexistent_strategy"],
        }

        # Act
        response = await async_client.post("/api/v1/arena/comparisons", json=request)

        # Assert
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_comparison_rejects_invalid_date_range(
        self,
        async_client: AsyncClient,
    ):
        """end_date before start_date returns 422."""
        # Arrange
        request = {
            **BASE_COMPARISON_REQUEST,
            "start_date": "2024-06-30",
            "end_date": "2024-01-01",
        }

        # Act
        response = await async_client.post("/api/v1/arena/comparisons", json=request)

        # Assert
        assert response.status_code == 422
        assert "end_date must be after start_date" in str(response.json())

    @pytest.mark.asyncio
    async def test_create_comparison_normalizes_symbols(
        self,
        async_client: AsyncClient,
        db_session: AsyncSession,
    ):
        """Symbols are normalized to uppercase and stripped of whitespace."""
        # Arrange
        request = {
            **BASE_COMPARISON_REQUEST,
            "symbols": ["  aapl  ", "msft", "  GOOGL"],
        }

        # Act
        response = await async_client.post("/api/v1/arena/comparisons", json=request)

        # Assert
        assert response.status_code == 202
        data = response.json()
        for sim in data["simulations"]:
            assert sim["symbols"] == ["AAPL", "MSFT", "GOOGL"]

    @pytest.mark.asyncio
    async def test_create_comparison_rejects_empty_symbols(
        self,
        async_client: AsyncClient,
    ):
        """Empty symbols list returns 422."""
        # Arrange
        request = {**BASE_COMPARISON_REQUEST, "symbols": []}

        # Act
        response = await async_client.post("/api/v1/arena/comparisons", json=request)

        # Assert
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_comparison_rejects_invalid_agent_type(
        self,
        async_client: AsyncClient,
    ):
        """Unknown agent_type returns 422."""
        # Arrange
        request = {
            **BASE_COMPARISON_REQUEST,
            "agent_type": "nonexistent_agent",
        }

        # Act
        response = await async_client.post("/api/v1/arena/comparisons", json=request)

        # Assert
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_comparison_with_all_four_strategies(
        self,
        async_client: AsyncClient,
        db_session: AsyncSession,
    ):
        """POST /comparisons with all 4 available strategies creates 4 simulations."""
        # Arrange
        request = {
            **BASE_COMPARISON_REQUEST,
            "portfolio_strategies": [
                "none",
                "score_sector_low_atr",
                "score_sector_high_atr",
                "score_sector_moderate_atr",
            ],
        }

        # Act
        response = await async_client.post("/api/v1/arena/comparisons", json=request)

        # Assert
        assert response.status_code == 202
        data = response.json()
        assert len(data["simulations"]) == 4

    @pytest.mark.asyncio
    async def test_create_comparison_simulations_appear_in_list_endpoint(
        self,
        async_client: AsyncClient,
        db_session: AsyncSession,
    ):
        """Simulations created via comparison appear in GET /simulations list."""
        # Act
        response = await async_client.post(
            "/api/v1/arena/comparisons",
            json={
                **BASE_COMPARISON_REQUEST,
                "name": "List Visibility Test",
            },
        )
        assert response.status_code == 202
        group_id = response.json()["group_id"]

        # Verify they appear in the list endpoint with group_id populated
        list_response = await async_client.get("/api/v1/arena/simulations")
        assert list_response.status_code == 200
        items = list_response.json()["items"]
        grouped = [s for s in items if s["group_id"] == group_id]
        assert len(grouped) == 2


class TestGetComparison:
    """Tests for GET /api/v1/arena/comparisons/{group_id} endpoint."""

    @pytest.mark.asyncio
    async def test_get_comparison_returns_all_simulations(
        self,
        async_client: AsyncClient,
        db_session: AsyncSession,
    ):
        """GET /comparisons/{group_id} returns all simulations in the group."""
        # Arrange: create a comparison group first
        create_response = await async_client.post(
            "/api/v1/arena/comparisons",
            json={
                **BASE_COMPARISON_REQUEST,
                "portfolio_strategies": ["none", "score_sector_low_atr", "score_sector_high_atr"],
            },
        )
        assert create_response.status_code == 202
        group_id = create_response.json()["group_id"]

        # Act
        response = await async_client.get(f"/api/v1/arena/comparisons/{group_id}")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["group_id"] == group_id
        assert len(data["simulations"]) == 3

    @pytest.mark.asyncio
    async def test_get_comparison_simulations_ordered_by_id(
        self,
        async_client: AsyncClient,
        db_session: AsyncSession,
    ):
        """GET /comparisons/{group_id} returns simulations in ascending id order."""
        # Arrange
        create_response = await async_client.post(
            "/api/v1/arena/comparisons",
            json=BASE_COMPARISON_REQUEST,
        )
        assert create_response.status_code == 202
        group_id = create_response.json()["group_id"]

        # Act
        response = await async_client.get(f"/api/v1/arena/comparisons/{group_id}")

        # Assert
        assert response.status_code == 200
        sims = response.json()["simulations"]
        ids = [s["id"] for s in sims]
        assert ids == sorted(ids), "Simulations must be ordered by ascending id"

    @pytest.mark.asyncio
    async def test_get_comparison_returns_404_for_unknown_group(
        self,
        async_client: AsyncClient,
        db_session: AsyncSession,
    ):
        """GET /comparisons/{group_id} returns 404 for unknown group_id."""
        # Act
        response = await async_client.get(
            "/api/v1/arena/comparisons/00000000-0000-0000-0000-000000000000"
        )

        # Assert
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_get_comparison_reflects_simulation_updates(
        self,
        async_client: AsyncClient,
        db_session: AsyncSession,
    ):
        """GET /comparisons/{group_id} returns current simulation state."""
        # Arrange: create comparison
        create_response = await async_client.post(
            "/api/v1/arena/comparisons",
            json=BASE_COMPARISON_REQUEST,
        )
        assert create_response.status_code == 202
        data = create_response.json()
        group_id = data["group_id"]
        sim_id = data["simulations"][0]["id"]

        # Simulate the worker updating a simulation's status
        stmt_result = await db_session.get(ArenaSimulation, sim_id)
        stmt_result.status = SimulationStatus.RUNNING.value
        stmt_result.current_day = 5
        stmt_result.total_days = 20
        await db_session.commit()

        # Act
        response = await async_client.get(f"/api/v1/arena/comparisons/{group_id}")

        # Assert
        assert response.status_code == 200
        sims = response.json()["simulations"]
        updated_sim = next(s for s in sims if s["id"] == sim_id)
        assert updated_sim["status"] == "running"
        assert updated_sim["current_day"] == 5
        assert updated_sim["total_days"] == 20


class TestGroupIdInSimulationResponse:
    """Tests that group_id is exposed in SimulationResponse for list and detail endpoints."""

    @pytest.mark.asyncio
    async def test_group_id_present_in_list_endpoint(
        self,
        async_client: AsyncClient,
        db_session: AsyncSession,
    ):
        """GET /simulations returns group_id for simulations that are part of a group."""
        # Arrange: create a comparison to get simulations with group_id
        create_response = await async_client.post(
            "/api/v1/arena/comparisons",
            json=BASE_COMPARISON_REQUEST,
        )
        assert create_response.status_code == 202
        group_id = create_response.json()["group_id"]

        # Act
        list_response = await async_client.get("/api/v1/arena/simulations")

        # Assert
        assert list_response.status_code == 200
        items = list_response.json()["items"]
        grouped = [s for s in items if s.get("group_id") == group_id]
        assert len(grouped) >= 2
        for sim in grouped:
            assert sim["group_id"] == group_id

    @pytest.mark.asyncio
    async def test_group_id_is_none_for_standalone_simulation(
        self,
        async_client: AsyncClient,
        db_session: AsyncSession,
    ):
        """Standalone simulations (created via POST /simulations) have group_id=None."""
        # Act
        response = await async_client.post(
            "/api/v1/arena/simulations",
            json={
                "symbols": ["AAPL"],
                "start_date": "2024-01-01",
                "end_date": "2024-01-31",
            },
        )

        # Assert
        assert response.status_code == 202
        assert response.json()["group_id"] is None

    @pytest.mark.asyncio
    async def test_group_id_present_in_detail_endpoint(
        self,
        async_client: AsyncClient,
        db_session: AsyncSession,
    ):
        """GET /simulations/{id} returns group_id for grouped simulations."""
        # Arrange: create a simulation with group_id directly in DB
        sim = ArenaSimulation(
            name="Grouped Sim Detail Test",
            symbols=["AAPL"],
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 31),
            initial_capital=Decimal("10000"),
            position_size=Decimal("1000"),
            agent_type="live20",
            agent_config={"trailing_stop_pct": 5.0},
            group_id="test-group-uuid-1234",
            status=SimulationStatus.PENDING.value,
        )
        db_session.add(sim)
        await db_session.commit()
        await db_session.refresh(sim)

        # Act
        response = await async_client.get(f"/api/v1/arena/simulations/{sim.id}")

        # Assert
        assert response.status_code == 200
        sim_data = response.json()["simulation"]
        assert sim_data["group_id"] == "test-group-uuid-1234"

    @pytest.mark.asyncio
    async def test_group_id_none_in_detail_endpoint_for_standalone(
        self,
        async_client: AsyncClient,
        db_session: AsyncSession,
    ):
        """GET /simulations/{id} returns group_id=None for standalone simulations."""
        # Arrange
        sim = ArenaSimulation(
            name="Standalone Detail Test",
            symbols=["MSFT"],
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 31),
            initial_capital=Decimal("10000"),
            position_size=Decimal("1000"),
            agent_type="live20",
            agent_config={},
            group_id=None,
            status=SimulationStatus.PENDING.value,
        )
        db_session.add(sim)
        await db_session.commit()
        await db_session.refresh(sim)

        # Act
        response = await async_client.get(f"/api/v1/arena/simulations/{sim.id}")

        # Assert
        assert response.status_code == 200
        sim_data = response.json()["simulation"]
        assert sim_data["group_id"] is None


class TestSharedValidatorFunctions:
    """Tests that shared validator functions produce identical behavior in both schemas."""

    @pytest.mark.asyncio
    async def test_comparison_normalizes_symbols_same_as_simulation(
        self,
        async_client: AsyncClient,
        db_session: AsyncSession,
    ):
        """Symbol normalization in CreateComparisonRequest matches CreateSimulationRequest."""
        # Arrange: lowercase symbols with whitespace
        symbols_input = ["  aapl  ", "googl", "MSFT  "]
        expected = ["AAPL", "GOOGL", "MSFT"]

        # Test on CreateSimulationRequest
        sim_response = await async_client.post(
            "/api/v1/arena/simulations",
            json={
                "symbols": symbols_input,
                "start_date": "2024-01-01",
                "end_date": "2024-01-31",
            },
        )
        assert sim_response.status_code == 202
        assert sim_response.json()["symbols"] == expected

        # Test on CreateComparisonRequest
        cmp_response = await async_client.post(
            "/api/v1/arena/comparisons",
            json={
                "symbols": symbols_input,
                "start_date": "2024-01-01",
                "end_date": "2024-06-30",
                "portfolio_strategies": ["none", "score_sector_low_atr"],
            },
        )
        assert cmp_response.status_code == 202
        for sim in cmp_response.json()["simulations"]:
            assert sim["symbols"] == expected

    @pytest.mark.asyncio
    async def test_comparison_rejects_invalid_date_range_same_as_simulation(
        self,
        async_client: AsyncClient,
    ):
        """Date range validation in CreateComparisonRequest matches CreateSimulationRequest."""
        # CreateSimulationRequest rejects end < start
        sim_response = await async_client.post(
            "/api/v1/arena/simulations",
            json={
                "symbols": ["AAPL"],
                "start_date": "2024-06-30",
                "end_date": "2024-01-01",
            },
        )
        assert sim_response.status_code == 422
        assert "end_date must be after start_date" in str(sim_response.json())

        # CreateComparisonRequest must also reject end < start
        cmp_response = await async_client.post(
            "/api/v1/arena/comparisons",
            json={
                "symbols": ["AAPL"],
                "start_date": "2024-06-30",
                "end_date": "2024-01-01",
                "portfolio_strategies": ["none", "score_sector_low_atr"],
            },
        )
        assert cmp_response.status_code == 422
        assert "end_date must be after start_date" in str(cmp_response.json())

    @pytest.mark.asyncio
    async def test_comparison_rejects_unknown_agent_type_same_as_simulation(
        self,
        async_client: AsyncClient,
    ):
        """agent_type validation in CreateComparisonRequest matches CreateSimulationRequest."""
        invalid_agent = "nonexistent_agent_xyz"

        # CreateSimulationRequest rejects unknown agent_type
        sim_response = await async_client.post(
            "/api/v1/arena/simulations",
            json={
                "symbols": ["AAPL"],
                "start_date": "2024-01-01",
                "end_date": "2024-01-31",
                "agent_type": invalid_agent,
            },
        )
        assert sim_response.status_code == 422

        # CreateComparisonRequest must also reject it
        cmp_response = await async_client.post(
            "/api/v1/arena/comparisons",
            json={
                "symbols": ["AAPL"],
                "start_date": "2024-01-01",
                "end_date": "2024-06-30",
                "agent_type": invalid_agent,
                "portfolio_strategies": ["none", "score_sector_low_atr"],
            },
        )
        assert cmp_response.status_code == 422

    @pytest.mark.asyncio
    async def test_comparison_rejects_too_many_symbols_same_as_simulation(
        self,
        async_client: AsyncClient,
    ):
        """Symbol count limit in CreateComparisonRequest matches CreateSimulationRequest."""
        # The configured limit is 600, so 601 should fail in both schemas
        symbols = [f"SYM{i}" for i in range(601)]

        sim_response = await async_client.post(
            "/api/v1/arena/simulations",
            json={
                "symbols": symbols,
                "start_date": "2024-01-01",
                "end_date": "2024-01-31",
            },
        )
        assert sim_response.status_code == 422

        cmp_response = await async_client.post(
            "/api/v1/arena/comparisons",
            json={
                "symbols": symbols,
                "start_date": "2024-01-01",
                "end_date": "2024-06-30",
                "portfolio_strategies": ["none", "score_sector_low_atr"],
            },
        )
        assert cmp_response.status_code == 422
