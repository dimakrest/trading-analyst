"""Unit tests for Arena API endpoints.

Tests for:
- GET /api/v1/arena/agents - List available agents
- POST /api/v1/arena/simulations - Create simulation
- GET /api/v1/arena/simulations - List simulations
- GET /api/v1/arena/simulations/{id} - Get simulation details
- DELETE /api/v1/arena/simulations/{id} - Cancel/delete simulation
"""

from datetime import date, datetime
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.arena import (
    ArenaPosition,
    ArenaSimulation,
    ArenaSnapshot,
    PositionStatus,
    SimulationStatus,
)


class TestListAgents:
    """Tests for GET /api/v1/arena/agents endpoint."""

    @pytest.mark.asyncio
    async def test_list_agents_returns_available_agents(
        self,
        async_client: AsyncClient,
    ):
        """List agents returns all registered agents with info."""
        # Act
        response = await async_client.get("/api/v1/arena/agents")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1

        # Verify agent structure
        agent = data[0]
        assert "type" in agent
        assert "name" in agent
        assert "required_lookback_days" in agent

        # Verify live20 agent is registered
        agent_types = [a["type"] for a in data]
        assert "live20" in agent_types

    @pytest.mark.asyncio
    async def test_list_agents_live20_has_correct_properties(
        self,
        async_client: AsyncClient,
    ):
        """Live20 agent has expected lookback days."""
        # Act
        response = await async_client.get("/api/v1/arena/agents")

        # Assert
        assert response.status_code == 200
        data = response.json()

        live20 = next((a for a in data if a["type"] == "live20"), None)
        assert live20 is not None
        assert live20["required_lookback_days"] >= 20  # Live20 needs historical data


class TestCreateSimulation:
    """Tests for POST /api/v1/arena/simulations endpoint."""

    @pytest.mark.asyncio
    async def test_create_simulation_with_defaults(
        self,
        async_client: AsyncClient,
        db_session: AsyncSession,
    ):
        """Create simulation with minimal parameters uses defaults."""
        # Arrange
        request_data = {
            "symbols": ["AAPL", "GOOGL"],
            "start_date": "2024-01-01",
            "end_date": "2024-01-31",
        }

        # Act
        response = await async_client.post(
            "/api/v1/arena/simulations",
            json=request_data,
        )

        # Assert
        assert response.status_code == 202
        data = response.json()

        assert data["symbols"] == ["AAPL", "GOOGL"]
        assert data["start_date"] == "2024-01-01"
        assert data["end_date"] == "2024-01-31"
        assert Decimal(data["initial_capital"]) == Decimal("10000")
        assert Decimal(data["position_size"]) == Decimal("1000")
        assert data["agent_type"] == "live20"
        assert data["status"] == "pending"
        assert data["current_day"] == 0
        assert data["total_days"] == 0  # Worker initializes this
        assert "id" in data
        assert "created_at" in data

    @pytest.mark.asyncio
    async def test_create_simulation_with_all_parameters(
        self,
        async_client: AsyncClient,
        db_session: AsyncSession,
    ):
        """Create simulation with all custom parameters."""
        # Arrange
        request_data = {
            "name": "Test Simulation",
            "symbols": ["MSFT", "AMZN", "META"],
            "start_date": "2024-02-01",
            "end_date": "2024-03-31",
            "initial_capital": 50000,
            "position_size": 2500,
            "agent_type": "live20",
            "trailing_stop_pct": 7.5,
            "min_buy_score": 70,
        }

        # Act
        response = await async_client.post(
            "/api/v1/arena/simulations",
            json=request_data,
        )

        # Assert
        assert response.status_code == 202
        data = response.json()

        assert data["name"] == "Test Simulation"
        assert data["symbols"] == ["MSFT", "AMZN", "META"]
        assert Decimal(data["initial_capital"]) == Decimal("50000")
        assert Decimal(data["position_size"]) == Decimal("2500")
        assert data["trailing_stop_pct"] == "7.5"
        assert data["min_buy_score"] == 70

    @pytest.mark.asyncio
    async def test_create_simulation_normalizes_symbols(
        self,
        async_client: AsyncClient,
        db_session: AsyncSession,
    ):
        """Symbols are normalized to uppercase and trimmed."""
        # Arrange
        request_data = {
            "symbols": ["  aapl  ", "googl", "  MSFT"],
            "start_date": "2024-01-01",
            "end_date": "2024-01-31",
        }

        # Act
        response = await async_client.post(
            "/api/v1/arena/simulations",
            json=request_data,
        )

        # Assert
        assert response.status_code == 202
        data = response.json()
        assert data["symbols"] == ["AAPL", "GOOGL", "MSFT"]

    @pytest.mark.asyncio
    async def test_create_simulation_invalid_date_range(
        self,
        async_client: AsyncClient,
    ):
        """End date before start date returns validation error."""
        # Arrange
        request_data = {
            "symbols": ["AAPL"],
            "start_date": "2024-01-31",
            "end_date": "2024-01-01",
        }

        # Act
        response = await async_client.post(
            "/api/v1/arena/simulations",
            json=request_data,
        )

        # Assert
        assert response.status_code == 422
        data = response.json()
        assert "end_date must be after start_date" in str(data)

    @pytest.mark.asyncio
    async def test_create_simulation_same_start_end_date(
        self,
        async_client: AsyncClient,
    ):
        """Same start and end date returns validation error."""
        # Arrange
        request_data = {
            "symbols": ["AAPL"],
            "start_date": "2024-01-15",
            "end_date": "2024-01-15",
        }

        # Act
        response = await async_client.post(
            "/api/v1/arena/simulations",
            json=request_data,
        )

        # Assert
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_simulation_empty_symbols(
        self,
        async_client: AsyncClient,
    ):
        """Empty symbols list returns validation error."""
        # Arrange
        request_data = {
            "symbols": [],
            "start_date": "2024-01-01",
            "end_date": "2024-01-31",
        }

        # Act
        response = await async_client.post(
            "/api/v1/arena/simulations",
            json=request_data,
        )

        # Assert
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_simulation_too_many_symbols(
        self,
        async_client: AsyncClient,
    ):
        """More than 200 symbols returns validation error."""
        # Arrange
        symbols = [f"SYM{i}" for i in range(201)]
        request_data = {
            "symbols": symbols,
            "start_date": "2024-01-01",
            "end_date": "2024-01-31",
        }

        # Act
        response = await async_client.post(
            "/api/v1/arena/simulations",
            json=request_data,
        )

        # Assert
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_simulation_invalid_trailing_stop_zero(
        self,
        async_client: AsyncClient,
    ):
        """Trailing stop of 0 returns validation error."""
        # Arrange
        request_data = {
            "symbols": ["AAPL"],
            "start_date": "2024-01-01",
            "end_date": "2024-01-31",
            "trailing_stop_pct": 0,
        }

        # Act
        response = await async_client.post(
            "/api/v1/arena/simulations",
            json=request_data,
        )

        # Assert
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_simulation_invalid_trailing_stop_100(
        self,
        async_client: AsyncClient,
    ):
        """Trailing stop of 100 returns validation error."""
        # Arrange
        request_data = {
            "symbols": ["AAPL"],
            "start_date": "2024-01-01",
            "end_date": "2024-01-31",
            "trailing_stop_pct": 100,
        }

        # Act
        response = await async_client.post(
            "/api/v1/arena/simulations",
            json=request_data,
        )

        # Assert
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_simulation_negative_initial_capital(
        self,
        async_client: AsyncClient,
    ):
        """Negative initial capital returns validation error."""
        # Arrange
        request_data = {
            "symbols": ["AAPL"],
            "start_date": "2024-01-01",
            "end_date": "2024-01-31",
            "initial_capital": -1000,
        }

        # Act
        response = await async_client.post(
            "/api/v1/arena/simulations",
            json=request_data,
        )

        # Assert
        assert response.status_code == 422


class TestSimulationParameterExposure:
    """Tests for exposing simulation parameters in API responses."""

    @pytest.mark.asyncio
    async def test_create_simulation_exposes_trailing_stop_pct(
        self,
        async_client: AsyncClient,
        db_session: AsyncSession,
    ):
        """Created simulation exposes trailing_stop_pct from agent_config."""
        # Arrange
        request_data = {
            "symbols": ["AAPL"],
            "start_date": "2024-01-01",
            "end_date": "2024-01-31",
            "trailing_stop_pct": 7.5,
        }

        # Act
        response = await async_client.post(
            "/api/v1/arena/simulations",
            json=request_data,
        )

        # Assert
        assert response.status_code == 202
        data = response.json()
        assert data["trailing_stop_pct"] == "7.5"

    @pytest.mark.asyncio
    async def test_create_simulation_exposes_min_buy_score(
        self,
        async_client: AsyncClient,
        db_session: AsyncSession,
    ):
        """Created simulation exposes min_buy_score from agent_config."""
        # Arrange
        request_data = {
            "symbols": ["AAPL"],
            "start_date": "2024-01-01",
            "end_date": "2024-01-31",
            "min_buy_score": 75,
        }

        # Act
        response = await async_client.post(
            "/api/v1/arena/simulations",
            json=request_data,
        )

        # Assert
        assert response.status_code == 202
        data = response.json()
        assert data["min_buy_score"] == 75

    @pytest.mark.asyncio
    async def test_create_simulation_default_values_exposed(
        self,
        async_client: AsyncClient,
        db_session: AsyncSession,
    ):
        """Created simulation with defaults exposes default parameter values."""
        # Arrange
        request_data = {
            "symbols": ["AAPL"],
            "start_date": "2024-01-01",
            "end_date": "2024-01-31",
        }

        # Act
        response = await async_client.post(
            "/api/v1/arena/simulations",
            json=request_data,
        )

        # Assert
        assert response.status_code == 202
        data = response.json()
        # Default trailing_stop_pct is 5.0
        assert data["trailing_stop_pct"] == "5.0"
        # Default min_buy_score is 60
        assert data["min_buy_score"] == 60

    @pytest.mark.asyncio
    async def test_get_simulation_exposes_parameters(
        self,
        async_client: AsyncClient,
        db_session: AsyncSession,
    ):
        """Get simulation detail exposes agent config parameters."""
        # Arrange
        sim = ArenaSimulation(
            name="Parameter Test Sim",
            symbols=["AAPL"],
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 31),
            initial_capital=Decimal("10000"),
            position_size=Decimal("1000"),
            agent_type="live20",
            agent_config={
                "trailing_stop_pct": 8.5,
                "min_buy_score": 80,
                "spy_trend_filter": False,
            },
            status=SimulationStatus.RUNNING.value,
        )
        db_session.add(sim)
        await db_session.commit()
        await db_session.refresh(sim)

        # Act
        response = await async_client.get(f"/api/v1/arena/simulations/{sim.id}")

        # Assert
        assert response.status_code == 200
        data = response.json()
        sim_data = data["simulation"]
        assert sim_data["trailing_stop_pct"] == "8.5"
        assert sim_data["min_buy_score"] == 80

    @pytest.mark.asyncio
    async def test_list_simulations_exposes_parameters(
        self,
        async_client: AsyncClient,
        db_session: AsyncSession,
    ):
        """List simulations exposes agent config parameters."""
        # Arrange
        sim = ArenaSimulation(
            name="List Parameter Test",
            symbols=["GOOGL"],
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 31),
            initial_capital=Decimal("10000"),
            position_size=Decimal("1000"),
            agent_type="live20",
            agent_config={
                "trailing_stop_pct": 6.0,
                "min_buy_score": 65,
            },
            status=SimulationStatus.PENDING.value,
        )
        db_session.add(sim)
        await db_session.commit()

        # Act
        response = await async_client.get("/api/v1/arena/simulations")

        # Assert
        assert response.status_code == 200
        data = response.json()
        sim_data = next(
            (s for s in data["items"] if s["name"] == "List Parameter Test"),
            None,
        )
        assert sim_data is not None
        assert sim_data["trailing_stop_pct"] == "6.0"
        assert sim_data["min_buy_score"] == 65

    @pytest.mark.asyncio
    async def test_old_simulation_missing_agent_config_returns_none(
        self,
        async_client: AsyncClient,
        db_session: AsyncSession,
    ):
        """Old simulation without agent_config returns None for parameters gracefully."""
        # Arrange - Create a simulation with empty agent_config (like old data)
        sim = ArenaSimulation(
            name="Old Sim",
            symbols=["AAPL"],
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 31),
            initial_capital=Decimal("10000"),
            position_size=Decimal("1000"),
            agent_type="live20",
            agent_config={},  # Empty config like old simulations
            status=SimulationStatus.COMPLETED.value,
        )
        db_session.add(sim)
        await db_session.commit()
        await db_session.refresh(sim)

        # Act
        response = await async_client.get(f"/api/v1/arena/simulations/{sim.id}")

        # Assert
        assert response.status_code == 200
        data = response.json()
        sim_data = data["simulation"]
        assert sim_data["trailing_stop_pct"] is None
        assert sim_data["min_buy_score"] is None

    @pytest.mark.asyncio
    async def test_old_simulation_partial_agent_config_returns_none_for_missing(
        self,
        async_client: AsyncClient,
        db_session: AsyncSession,
    ):
        """Simulation with partial agent_config returns None for missing fields."""
        # Arrange - Create simulation with only trailing_stop_pct
        sim = ArenaSimulation(
            name="Partial Config Sim",
            symbols=["MSFT"],
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 31),
            initial_capital=Decimal("10000"),
            position_size=Decimal("1000"),
            agent_type="live20",
            agent_config={"trailing_stop_pct": 5.0},  # Only one field
            status=SimulationStatus.COMPLETED.value,
        )
        db_session.add(sim)
        await db_session.commit()
        await db_session.refresh(sim)

        # Act
        response = await async_client.get(f"/api/v1/arena/simulations/{sim.id}")

        # Assert
        assert response.status_code == 200
        data = response.json()
        sim_data = data["simulation"]
        assert sim_data["trailing_stop_pct"] == "5.0"
        assert sim_data["min_buy_score"] is None  # Missing field returns None


class TestListSimulations:
    """Tests for GET /api/v1/arena/simulations endpoint."""

    @pytest.mark.asyncio
    async def test_list_simulations_empty(
        self,
        async_client: AsyncClient,
        db_session: AsyncSession,
    ):
        """List simulations returns empty list when none exist."""
        # Act
        response = await async_client.get("/api/v1/arena/simulations")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0
        assert data["has_more"] is False

    @pytest.mark.asyncio
    async def test_list_simulations_returns_recent_first(
        self,
        async_client: AsyncClient,
        db_session: AsyncSession,
    ):
        """List simulations returns most recent first."""
        # Arrange - Create multiple simulations with explicit time ordering
        # Use explicit created_at to ensure deterministic ordering
        older_time = datetime(2024, 1, 1, 10, 0, 0)
        newer_time = datetime(2024, 1, 2, 10, 0, 0)

        sim1 = ArenaSimulation(
            name="First Sim",
            symbols=["AAPL"],
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 31),
            initial_capital=Decimal("10000"),
            position_size=Decimal("1000"),
            agent_type="live20",
            agent_config={},
            status=SimulationStatus.COMPLETED.value,
        )
        # Set created_at manually for deterministic test
        sim1.created_at = older_time

        sim2 = ArenaSimulation(
            name="Second Sim",
            symbols=["GOOGL"],
            start_date=date(2024, 2, 1),
            end_date=date(2024, 2, 28),
            initial_capital=Decimal("20000"),
            position_size=Decimal("2000"),
            agent_type="live20",
            agent_config={},
            status=SimulationStatus.PENDING.value,
        )
        sim2.created_at = newer_time

        db_session.add(sim1)
        db_session.add(sim2)
        await db_session.commit()

        # Act
        response = await async_client.get("/api/v1/arena/simulations")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 2
        assert data["total"] == 2
        assert data["has_more"] is False
        # Most recent (sim2) should be first
        assert data["items"][0]["name"] == "Second Sim"
        assert data["items"][1]["name"] == "First Sim"

    @pytest.mark.asyncio
    async def test_list_simulations_with_limit(
        self,
        async_client: AsyncClient,
        db_session: AsyncSession,
    ):
        """List simulations respects limit parameter."""
        # Arrange - Create 3 simulations
        for i in range(3):
            sim = ArenaSimulation(
                name=f"Sim {i}",
                symbols=["AAPL"],
                start_date=date(2024, 1, 1),
                end_date=date(2024, 1, 31),
                initial_capital=Decimal("10000"),
                position_size=Decimal("1000"),
                agent_type="live20",
                agent_config={},
                status=SimulationStatus.PENDING.value,
            )
            db_session.add(sim)
        await db_session.commit()

        # Act
        response = await async_client.get("/api/v1/arena/simulations?limit=2")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 2
        assert data["total"] == 3  # 3 total simulations created
        assert data["has_more"] is True  # More exist beyond limit

    @pytest.mark.asyncio
    async def test_list_simulations_with_offset(
        self,
        async_client: AsyncClient,
        db_session: AsyncSession,
    ):
        """List simulations respects offset parameter."""
        # Arrange - Create 3 simulations
        for i in range(3):
            sim = ArenaSimulation(
                name=f"Sim {i}",
                symbols=["AAPL"],
                start_date=date(2024, 1, 1),
                end_date=date(2024, 1, 31),
                initial_capital=Decimal("10000"),
                position_size=Decimal("1000"),
                agent_type="live20",
                agent_config={},
                status=SimulationStatus.PENDING.value,
            )
            db_session.add(sim)
        await db_session.commit()

        # Act
        response = await async_client.get("/api/v1/arena/simulations?offset=1")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 2  # Skipped first one
        assert data["total"] == 3  # Total still 3
        assert data["has_more"] is False  # No more beyond offset+items

    @pytest.mark.asyncio
    async def test_list_simulations_exact_last_page(
        self,
        async_client: AsyncClient,
        db_session: AsyncSession,
    ):
        """has_more is False when exactly at last page (offset + limit == total)."""
        # Arrange - Create 4 simulations
        for i in range(4):
            sim = ArenaSimulation(
                name=f"Sim {i}",
                symbols=["AAPL"],
                start_date=date(2024, 1, 1),
                end_date=date(2024, 1, 31),
                initial_capital=Decimal("10000"),
                position_size=Decimal("1000"),
                agent_type="live20",
                agent_config={},
                status=SimulationStatus.PENDING.value,
            )
            db_session.add(sim)
        await db_session.commit()

        # Act - Request last page exactly: offset=2, limit=2 → returns items 3,4 of 4
        response = await async_client.get("/api/v1/arena/simulations?limit=2&offset=2")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 2
        assert data["total"] == 4
        assert data["has_more"] is False  # (2 + 2) < 4 is False

    @pytest.mark.asyncio
    async def test_list_simulations_invalid_limit(
        self,
        async_client: AsyncClient,
    ):
        """Invalid limit parameter returns validation error."""
        # Act
        response = await async_client.get("/api/v1/arena/simulations?limit=0")

        # Assert
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_list_simulations_limit_max_100(
        self,
        async_client: AsyncClient,
    ):
        """Limit over 100 returns validation error."""
        # Act
        response = await async_client.get("/api/v1/arena/simulations?limit=101")

        # Assert
        assert response.status_code == 422


class TestGetSimulation:
    """Tests for GET /api/v1/arena/simulations/{id} endpoint."""

    @pytest.mark.asyncio
    async def test_get_simulation_not_found(
        self,
        async_client: AsyncClient,
        db_session: AsyncSession,
    ):
        """Get non-existent simulation returns 404."""
        # Act
        response = await async_client.get("/api/v1/arena/simulations/99999")

        # Assert
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_get_simulation_returns_details(
        self,
        async_client: AsyncClient,
        db_session: AsyncSession,
    ):
        """Get simulation returns full details."""
        # Arrange
        sim = ArenaSimulation(
            name="Detail Test Sim",
            symbols=["AAPL", "GOOGL"],
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 31),
            initial_capital=Decimal("15000"),
            position_size=Decimal("1500"),
            agent_type="live20",
            agent_config={"trailing_stop_pct": 5.0},
            status=SimulationStatus.RUNNING.value,
            current_day=5,
            total_days=20,
            total_trades=3,
            winning_trades=2,
        )
        db_session.add(sim)
        await db_session.commit()
        await db_session.refresh(sim)

        # Act
        response = await async_client.get(f"/api/v1/arena/simulations/{sim.id}")

        # Assert
        assert response.status_code == 200
        data = response.json()

        assert "simulation" in data
        assert "positions" in data
        assert "snapshots" in data

        sim_data = data["simulation"]
        assert sim_data["id"] == sim.id
        assert sim_data["name"] == "Detail Test Sim"
        assert sim_data["symbols"] == ["AAPL", "GOOGL"]
        assert Decimal(sim_data["initial_capital"]) == Decimal("15000")
        assert sim_data["status"] == "running"
        assert sim_data["current_day"] == 5
        assert sim_data["total_days"] == 20
        assert sim_data["total_trades"] == 3
        assert sim_data["winning_trades"] == 2

    @pytest.mark.asyncio
    async def test_get_simulation_includes_positions(
        self,
        async_client: AsyncClient,
        db_session: AsyncSession,
    ):
        """Get simulation includes position data."""
        # Arrange
        sim = ArenaSimulation(
            name="Position Test Sim",
            symbols=["AAPL"],
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 31),
            initial_capital=Decimal("10000"),
            position_size=Decimal("1000"),
            agent_type="live20",
            agent_config={},
            status=SimulationStatus.RUNNING.value,
        )
        db_session.add(sim)
        await db_session.flush()

        position = ArenaPosition(
            simulation_id=sim.id,
            symbol="AAPL",
            status=PositionStatus.OPEN.value,
            signal_date=date(2024, 1, 5),
            entry_date=date(2024, 1, 6),
            entry_price=Decimal("150.00"),
            shares=6,
            trailing_stop_pct=Decimal("5.0"),
            highest_price=Decimal("155.00"),
            current_stop=Decimal("147.25"),
            agent_reasoning="Strong technical setup",
            agent_score=85,
        )
        db_session.add(position)
        await db_session.commit()
        await db_session.refresh(sim)

        # Act
        response = await async_client.get(f"/api/v1/arena/simulations/{sim.id}")

        # Assert
        assert response.status_code == 200
        data = response.json()

        assert len(data["positions"]) == 1
        pos = data["positions"][0]
        assert pos["symbol"] == "AAPL"
        assert pos["status"] == "open"
        assert Decimal(pos["entry_price"]) == Decimal("150.00")
        assert pos["shares"] == 6
        assert pos["agent_score"] == 85

    @pytest.mark.asyncio
    async def test_get_simulation_includes_snapshots(
        self,
        async_client: AsyncClient,
        db_session: AsyncSession,
    ):
        """Get simulation includes snapshot data."""
        # Arrange
        sim = ArenaSimulation(
            name="Snapshot Test Sim",
            symbols=["AAPL"],
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 31),
            initial_capital=Decimal("10000"),
            position_size=Decimal("1000"),
            agent_type="live20",
            agent_config={},
            status=SimulationStatus.RUNNING.value,
        )
        db_session.add(sim)
        await db_session.flush()

        snapshot = ArenaSnapshot(
            simulation_id=sim.id,
            snapshot_date=date(2024, 1, 5),
            day_number=5,
            cash=Decimal("9000"),
            positions_value=Decimal("1100"),
            total_equity=Decimal("10100"),
            daily_pnl=Decimal("50"),
            daily_return_pct=Decimal("0.50"),
            cumulative_return_pct=Decimal("1.00"),
            open_position_count=1,
            decisions={"AAPL": {"action": "hold", "score": 75}},
        )
        db_session.add(snapshot)
        await db_session.commit()
        await db_session.refresh(sim)

        # Act
        response = await async_client.get(f"/api/v1/arena/simulations/{sim.id}")

        # Assert
        assert response.status_code == 200
        data = response.json()

        assert len(data["snapshots"]) == 1
        snap = data["snapshots"][0]
        assert snap["snapshot_date"] == "2024-01-05"
        assert snap["day_number"] == 5
        assert Decimal(snap["cash"]) == Decimal("9000")
        assert Decimal(snap["total_equity"]) == Decimal("10100")
        assert Decimal(snap["cumulative_return_pct"]) == Decimal("1.00")
        assert snap["decisions"]["AAPL"]["action"] == "hold"


class TestCancelSimulation:
    """Tests for POST /api/v1/arena/simulations/{id}/cancel endpoint."""

    @pytest.mark.asyncio
    async def test_cancel_running_simulation_returns_204(
        self,
        async_client: AsyncClient,
        db_session: AsyncSession,
    ):
        """Cancel running simulation returns 204 and sets status to cancelled."""
        # Arrange
        sim = ArenaSimulation(
            name="Running Sim",
            symbols=["AAPL"],
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 31),
            initial_capital=Decimal("10000"),
            position_size=Decimal("1000"),
            agent_type="live20",
            agent_config={},
            status=SimulationStatus.RUNNING.value,
            current_day=5,
            total_days=20,
        )
        db_session.add(sim)
        await db_session.commit()
        await db_session.refresh(sim)
        sim_id = sim.id

        # Act
        response = await async_client.post(f"/api/v1/arena/simulations/{sim_id}/cancel")

        # Assert
        assert response.status_code == 204

        # Verify status changed to cancelled
        await db_session.refresh(sim)
        assert sim.status == SimulationStatus.CANCELLED.value

    @pytest.mark.asyncio
    async def test_cancel_pending_simulation_returns_204(
        self,
        async_client: AsyncClient,
        db_session: AsyncSession,
    ):
        """Cancel pending simulation returns 204 and sets status to cancelled."""
        # Arrange
        sim = ArenaSimulation(
            name="Pending Sim",
            symbols=["GOOGL"],
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 31),
            initial_capital=Decimal("10000"),
            position_size=Decimal("1000"),
            agent_type="live20",
            agent_config={},
            status=SimulationStatus.PENDING.value,
        )
        db_session.add(sim)
        await db_session.commit()
        await db_session.refresh(sim)
        sim_id = sim.id

        # Act
        response = await async_client.post(f"/api/v1/arena/simulations/{sim_id}/cancel")

        # Assert
        assert response.status_code == 204

        # Verify status changed to cancelled
        await db_session.refresh(sim)
        assert sim.status == SimulationStatus.CANCELLED.value

    @pytest.mark.asyncio
    async def test_cancel_paused_simulation_returns_204(
        self,
        async_client: AsyncClient,
        db_session: AsyncSession,
    ):
        """Cancel paused simulation returns 204 and sets status to cancelled."""
        # Arrange
        sim = ArenaSimulation(
            name="Paused Sim",
            symbols=["MSFT"],
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 31),
            initial_capital=Decimal("10000"),
            position_size=Decimal("1000"),
            agent_type="live20",
            agent_config={},
            status=SimulationStatus.PAUSED.value,
            current_day=10,
            total_days=20,
        )
        db_session.add(sim)
        await db_session.commit()
        await db_session.refresh(sim)
        sim_id = sim.id

        # Act
        response = await async_client.post(f"/api/v1/arena/simulations/{sim_id}/cancel")

        # Assert
        assert response.status_code == 204

        # Verify status changed to cancelled
        await db_session.refresh(sim)
        assert sim.status == SimulationStatus.CANCELLED.value

    @pytest.mark.asyncio
    async def test_cancel_completed_simulation_returns_400(
        self,
        async_client: AsyncClient,
        db_session: AsyncSession,
    ):
        """Cancel completed simulation returns 400."""
        # Arrange
        sim = ArenaSimulation(
            name="Completed Sim",
            symbols=["AAPL"],
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 31),
            initial_capital=Decimal("10000"),
            position_size=Decimal("1000"),
            agent_type="live20",
            agent_config={},
            status=SimulationStatus.COMPLETED.value,
            final_equity=Decimal("11000"),
        )
        db_session.add(sim)
        await db_session.commit()
        await db_session.refresh(sim)
        sim_id = sim.id

        # Act
        response = await async_client.post(f"/api/v1/arena/simulations/{sim_id}/cancel")

        # Assert
        assert response.status_code == 400
        assert "Cannot cancel completed simulation" in response.json()["detail"]

        # Verify status unchanged
        await db_session.refresh(sim)
        assert sim.status == SimulationStatus.COMPLETED.value

    @pytest.mark.asyncio
    async def test_cancel_cancelled_simulation_returns_400(
        self,
        async_client: AsyncClient,
        db_session: AsyncSession,
    ):
        """Cancel already cancelled simulation returns 400."""
        # Arrange
        sim = ArenaSimulation(
            name="Already Cancelled Sim",
            symbols=["AAPL"],
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 31),
            initial_capital=Decimal("10000"),
            position_size=Decimal("1000"),
            agent_type="live20",
            agent_config={},
            status=SimulationStatus.CANCELLED.value,
        )
        db_session.add(sim)
        await db_session.commit()
        await db_session.refresh(sim)
        sim_id = sim.id

        # Act
        response = await async_client.post(f"/api/v1/arena/simulations/{sim_id}/cancel")

        # Assert
        assert response.status_code == 400
        assert "Cannot cancel cancelled simulation" in response.json()["detail"]

        # Verify status unchanged
        await db_session.refresh(sim)
        assert sim.status == SimulationStatus.CANCELLED.value

    @pytest.mark.asyncio
    async def test_cancel_failed_simulation_returns_400(
        self,
        async_client: AsyncClient,
        db_session: AsyncSession,
    ):
        """Cancel failed simulation returns 400."""
        # Arrange
        sim = ArenaSimulation(
            name="Failed Sim",
            symbols=["AAPL"],
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 31),
            initial_capital=Decimal("10000"),
            position_size=Decimal("1000"),
            agent_type="live20",
            agent_config={},
            status=SimulationStatus.FAILED.value,
            error_message="Data fetch failed",
        )
        db_session.add(sim)
        await db_session.commit()
        await db_session.refresh(sim)
        sim_id = sim.id

        # Act
        response = await async_client.post(f"/api/v1/arena/simulations/{sim_id}/cancel")

        # Assert
        assert response.status_code == 400
        assert "Cannot cancel failed simulation" in response.json()["detail"]

        # Verify status unchanged
        await db_session.refresh(sim)
        assert sim.status == SimulationStatus.FAILED.value

    @pytest.mark.asyncio
    async def test_cancel_non_existent_simulation_returns_404(
        self,
        async_client: AsyncClient,
        db_session: AsyncSession,
    ):
        """Cancel non-existent simulation returns 404."""
        # Act
        response = await async_client.post("/api/v1/arena/simulations/99999/cancel")

        # Assert
        assert response.status_code == 404
        assert "Simulation not found" in response.json()["detail"]


class TestDeleteSimulation:
    """Tests for DELETE /api/v1/arena/simulations/{id} endpoint."""

    @pytest.mark.asyncio
    async def test_delete_simulation_not_found(
        self,
        async_client: AsyncClient,
        db_session: AsyncSession,
    ):
        """Delete non-existent simulation returns 404."""
        # Act
        response = await async_client.delete("/api/v1/arena/simulations/99999")

        # Assert
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_pending_simulation_returns_400(
        self,
        async_client: AsyncClient,
        db_session: AsyncSession,
    ):
        """Delete pending simulation returns 400 - use cancel endpoint instead."""
        # Arrange
        sim = ArenaSimulation(
            name="Pending Sim",
            symbols=["AAPL"],
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 31),
            initial_capital=Decimal("10000"),
            position_size=Decimal("1000"),
            agent_type="live20",
            agent_config={},
            status=SimulationStatus.PENDING.value,
        )
        db_session.add(sim)
        await db_session.commit()
        await db_session.refresh(sim)
        sim_id = sim.id

        # Act
        response = await async_client.delete(f"/api/v1/arena/simulations/{sim_id}")

        # Assert
        assert response.status_code == 400
        assert "Cannot delete pending simulation" in response.json()["detail"]
        assert "cancel" in response.json()["detail"].lower()

        # Verify status unchanged
        await db_session.refresh(sim)
        assert sim.status == SimulationStatus.PENDING.value

    @pytest.mark.asyncio
    async def test_delete_running_simulation_returns_400(
        self,
        async_client: AsyncClient,
        db_session: AsyncSession,
    ):
        """Delete running simulation returns 400 - use cancel endpoint instead."""
        # Arrange
        sim = ArenaSimulation(
            name="Running Sim",
            symbols=["AAPL"],
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 31),
            initial_capital=Decimal("10000"),
            position_size=Decimal("1000"),
            agent_type="live20",
            agent_config={},
            status=SimulationStatus.RUNNING.value,
            current_day=5,
            total_days=20,
        )
        db_session.add(sim)
        await db_session.commit()
        await db_session.refresh(sim)
        sim_id = sim.id

        # Act
        response = await async_client.delete(f"/api/v1/arena/simulations/{sim_id}")

        # Assert
        assert response.status_code == 400
        assert "Cannot delete running simulation" in response.json()["detail"]
        assert "cancel" in response.json()["detail"].lower()

        # Verify status unchanged
        await db_session.refresh(sim)
        assert sim.status == SimulationStatus.RUNNING.value

    @pytest.mark.asyncio
    async def test_delete_paused_simulation_returns_400(
        self,
        async_client: AsyncClient,
        db_session: AsyncSession,
    ):
        """Delete paused simulation returns 400 - use cancel endpoint instead."""
        # Arrange
        sim = ArenaSimulation(
            name="Paused Sim",
            symbols=["AAPL"],
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 31),
            initial_capital=Decimal("10000"),
            position_size=Decimal("1000"),
            agent_type="live20",
            agent_config={},
            status=SimulationStatus.PAUSED.value,
            current_day=5,
            total_days=20,
        )
        db_session.add(sim)
        await db_session.commit()
        await db_session.refresh(sim)
        sim_id = sim.id

        # Act
        response = await async_client.delete(f"/api/v1/arena/simulations/{sim_id}")

        # Assert
        assert response.status_code == 400
        assert "Cannot delete paused simulation" in response.json()["detail"]
        assert "cancel" in response.json()["detail"].lower()

        # Verify status unchanged
        await db_session.refresh(sim)
        assert sim.status == SimulationStatus.PAUSED.value

    @pytest.mark.asyncio
    async def test_delete_completed_simulation_deletes(
        self,
        async_client: AsyncClient,
        db_session: AsyncSession,
    ):
        """Delete completed simulation removes it from database."""
        # Arrange
        sim = ArenaSimulation(
            name="Completed Sim",
            symbols=["AAPL"],
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 31),
            initial_capital=Decimal("10000"),
            position_size=Decimal("1000"),
            agent_type="live20",
            agent_config={},
            status=SimulationStatus.COMPLETED.value,
            final_equity=Decimal("11000"),
            total_return_pct=Decimal("10.0"),
        )
        db_session.add(sim)
        await db_session.commit()
        await db_session.refresh(sim)
        sim_id = sim.id

        # Act
        response = await async_client.delete(f"/api/v1/arena/simulations/{sim_id}")

        # Assert
        assert response.status_code == 204

        # Verify actually deleted
        get_response = await async_client.get(f"/api/v1/arena/simulations/{sim_id}")
        assert get_response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_failed_simulation_deletes(
        self,
        async_client: AsyncClient,
        db_session: AsyncSession,
    ):
        """Delete failed simulation removes it from database."""
        # Arrange
        sim = ArenaSimulation(
            name="Failed Sim",
            symbols=["AAPL"],
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 31),
            initial_capital=Decimal("10000"),
            position_size=Decimal("1000"),
            agent_type="live20",
            agent_config={},
            status=SimulationStatus.FAILED.value,
            error_message="Data fetch failed",
        )
        db_session.add(sim)
        await db_session.commit()
        await db_session.refresh(sim)
        sim_id = sim.id

        # Act
        response = await async_client.delete(f"/api/v1/arena/simulations/{sim_id}")

        # Assert
        assert response.status_code == 204

        # Verify actually deleted
        get_response = await async_client.get(f"/api/v1/arena/simulations/{sim_id}")
        assert get_response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_cancelled_simulation_deletes(
        self,
        async_client: AsyncClient,
        db_session: AsyncSession,
    ):
        """Delete cancelled simulation removes it from database."""
        # Arrange
        sim = ArenaSimulation(
            name="Cancelled Sim",
            symbols=["AAPL"],
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 31),
            initial_capital=Decimal("10000"),
            position_size=Decimal("1000"),
            agent_type="live20",
            agent_config={},
            status=SimulationStatus.CANCELLED.value,
        )
        db_session.add(sim)
        await db_session.commit()
        await db_session.refresh(sim)
        sim_id = sim.id

        # Act
        response = await async_client.delete(f"/api/v1/arena/simulations/{sim_id}")

        # Assert
        assert response.status_code == 204

        # Verify actually deleted
        get_response = await async_client.get(f"/api/v1/arena/simulations/{sim_id}")
        assert get_response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_simulation_cascades_positions_and_snapshots(
        self,
        async_client: AsyncClient,
        db_session: AsyncSession,
    ):
        """Deleting simulation also removes related positions and snapshots."""
        # Arrange
        sim = ArenaSimulation(
            name="Cascade Test Sim",
            symbols=["AAPL"],
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 31),
            initial_capital=Decimal("10000"),
            position_size=Decimal("1000"),
            agent_type="live20",
            agent_config={},
            status=SimulationStatus.COMPLETED.value,
        )
        db_session.add(sim)
        await db_session.flush()

        position = ArenaPosition(
            simulation_id=sim.id,
            symbol="AAPL",
            status=PositionStatus.CLOSED.value,
            signal_date=date(2024, 1, 5),
            trailing_stop_pct=Decimal("5.0"),
        )
        snapshot = ArenaSnapshot(
            simulation_id=sim.id,
            snapshot_date=date(2024, 1, 5),
            day_number=5,
            cash=Decimal("9000"),
            positions_value=Decimal("1000"),
            total_equity=Decimal("10000"),
            decisions={},
        )
        db_session.add_all([position, snapshot])
        await db_session.commit()
        await db_session.refresh(sim)
        sim_id = sim.id

        # Act
        response = await async_client.delete(f"/api/v1/arena/simulations/{sim_id}")

        # Assert
        assert response.status_code == 204

        # Simulation should be deleted (cascade deletes positions and snapshots)
        get_response = await async_client.get(f"/api/v1/arena/simulations/{sim_id}")
        assert get_response.status_code == 404


class TestSchemaValidation:
    """Tests for schema validation edge cases."""

    @pytest.mark.asyncio
    async def test_extra_fields_rejected(
        self,
        async_client: AsyncClient,
    ):
        """Extra fields in request are rejected (strict schema)."""
        # Arrange
        request_data = {
            "symbols": ["AAPL"],
            "start_date": "2024-01-01",
            "end_date": "2024-01-31",
            "unknown_field": "should fail",
        }

        # Act
        response = await async_client.post(
            "/api/v1/arena/simulations",
            json=request_data,
        )

        # Assert
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_created_at_serialized_as_iso_string(
        self,
        async_client: AsyncClient,
        db_session: AsyncSession,
    ):
        """created_at is serialized as ISO format string."""
        # Arrange
        request_data = {
            "symbols": ["AAPL"],
            "start_date": "2024-01-01",
            "end_date": "2024-01-31",
        }

        # Act
        response = await async_client.post(
            "/api/v1/arena/simulations",
            json=request_data,
        )

        # Assert
        assert response.status_code == 202
        data = response.json()

        # Verify created_at is a valid ISO format string
        created_at = data["created_at"]
        assert isinstance(created_at, str)
        # Should be parseable as ISO datetime
        datetime.fromisoformat(created_at.replace("Z", "+00:00"))

    @pytest.mark.asyncio
    async def test_decimal_fields_serialized_as_strings(
        self,
        async_client: AsyncClient,
        db_session: AsyncSession,
    ):
        """Decimal fields are serialized as strings to preserve precision."""
        # Arrange
        request_data = {
            "symbols": ["AAPL"],
            "start_date": "2024-01-01",
            "end_date": "2024-01-31",
            "initial_capital": 10000.50,
            "position_size": 1000.25,
        }

        # Act
        response = await async_client.post(
            "/api/v1/arena/simulations",
            json=request_data,
        )

        # Assert
        assert response.status_code == 202
        data = response.json()

        # Decimal fields should be strings
        assert isinstance(data["initial_capital"], str)
        assert isinstance(data["position_size"], str)


class TestStockListIntegration:
    """Tests for stock list tracking in arena simulations."""

    @pytest.mark.asyncio
    async def test_create_simulation_with_stock_list(
        self,
        async_client: AsyncClient,
        db_session: AsyncSession,
    ):
        """Test creating a simulation with stock list reference."""
        # Arrange
        request_data = {
            "symbols": ["AAPL", "MSFT"],
            "start_date": "2024-01-01",
            "end_date": "2024-06-01",
            "stock_list_id": 123,
            "stock_list_name": "Tech Stocks",
        }

        # Act
        response = await async_client.post(
            "/api/v1/arena/simulations",
            json=request_data,
        )

        # Assert
        assert response.status_code == 202
        data = response.json()
        assert data["stock_list_id"] == 123
        assert data["stock_list_name"] == "Tech Stocks"

    @pytest.mark.asyncio
    async def test_create_simulation_without_stock_list(
        self,
        async_client: AsyncClient,
        db_session: AsyncSession,
    ):
        """Test creating a simulation without stock list reference."""
        # Arrange
        request_data = {
            "symbols": ["AAPL", "MSFT"],
            "start_date": "2024-01-01",
            "end_date": "2024-06-01",
        }

        # Act
        response = await async_client.post(
            "/api/v1/arena/simulations",
            json=request_data,
        )

        # Assert
        assert response.status_code == 202
        data = response.json()
        assert data["stock_list_id"] is None
        assert data["stock_list_name"] is None

    @pytest.mark.asyncio
    async def test_get_simulation_includes_stock_list_fields(
        self,
        async_client: AsyncClient,
        db_session: AsyncSession,
    ):
        """Test that get simulation detail returns stock list fields."""
        # Arrange
        sim = ArenaSimulation(
            name="Stock List Test Sim",
            stock_list_id=456,
            stock_list_name="Value Stocks",
            symbols=["JNJ", "PG"],
            start_date=date(2024, 1, 1),
            end_date=date(2024, 6, 1),
            initial_capital=Decimal("10000"),
            position_size=Decimal("1000"),
            agent_type="live20",
            agent_config={},
            status=SimulationStatus.PENDING.value,
        )
        db_session.add(sim)
        await db_session.commit()
        await db_session.refresh(sim)

        # Act
        response = await async_client.get(f"/api/v1/arena/simulations/{sim.id}")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["simulation"]["stock_list_id"] == 456
        assert data["simulation"]["stock_list_name"] == "Value Stocks"

    @pytest.mark.asyncio
    async def test_list_simulations_includes_stock_list_fields(
        self,
        async_client: AsyncClient,
        db_session: AsyncSession,
    ):
        """Test that list simulations returns stock list fields."""
        # Arrange
        sim = ArenaSimulation(
            name="Listed Sim",
            stock_list_id=789,
            stock_list_name="Growth Stocks",
            symbols=["GOOGL", "AMZN"],
            start_date=date(2024, 1, 1),
            end_date=date(2024, 6, 1),
            initial_capital=Decimal("10000"),
            position_size=Decimal("1000"),
            agent_type="live20",
            agent_config={},
            status=SimulationStatus.PENDING.value,
        )
        db_session.add(sim)
        await db_session.commit()

        # Act
        response = await async_client.get("/api/v1/arena/simulations")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) >= 1
        assert data["total"] >= 1
        # Find our simulation in the list
        sim_data = next((s for s in data["items"] if s["name"] == "Listed Sim"), None)
        assert sim_data is not None
        assert sim_data["stock_list_id"] == 789
        assert sim_data["stock_list_name"] == "Growth Stocks"

    @pytest.mark.asyncio
    async def test_create_simulation_with_only_stock_list_id(
        self,
        async_client: AsyncClient,
        db_session: AsyncSession,
    ):
        """Test creating simulation with only stock_list_id (no name)."""
        # Arrange
        request_data = {
            "symbols": ["AAPL"],
            "start_date": "2024-01-01",
            "end_date": "2024-06-01",
            "stock_list_id": 100,
        }

        # Act
        response = await async_client.post(
            "/api/v1/arena/simulations",
            json=request_data,
        )

        # Assert
        assert response.status_code == 202
        data = response.json()
        assert data["stock_list_id"] == 100
        assert data["stock_list_name"] is None

    @pytest.mark.asyncio
    async def test_create_simulation_with_only_stock_list_name(
        self,
        async_client: AsyncClient,
        db_session: AsyncSession,
    ):
        """Test creating simulation with only stock_list_name (no id)."""
        # Arrange
        request_data = {
            "symbols": ["AAPL"],
            "start_date": "2024-01-01",
            "end_date": "2024-06-01",
            "stock_list_name": "Manual List",
        }

        # Act
        response = await async_client.post(
            "/api/v1/arena/simulations",
            json=request_data,
        )

        # Assert
        assert response.status_code == 202
        data = response.json()
        assert data["stock_list_id"] is None
        assert data["stock_list_name"] == "Manual List"
