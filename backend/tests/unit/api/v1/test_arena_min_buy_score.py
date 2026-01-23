"""Unit tests for min_buy_score field in Arena API.

Tests for Phase 1 of arena-configurable-buy-threshold ticket:
- min_buy_score field validation (20-100 range)
- min_buy_score default value (60)
- min_buy_score included in agent_config
"""
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.arena import ArenaSimulation


class TestMinBuyScoreField:
    """Tests for min_buy_score field validation and defaults."""

    @pytest.mark.asyncio
    async def test_min_buy_score_uses_default_when_not_provided(
        self,
        async_client: AsyncClient,
        db_session: AsyncSession,
    ):
        """When min_buy_score is not provided, default 60 is used."""
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
        simulation_id = data["id"]

        # Verify agent_config in database contains min_buy_score: 60
        stmt = select(ArenaSimulation).where(ArenaSimulation.id == simulation_id)
        result = await db_session.execute(stmt)
        simulation = result.scalar_one()
        assert simulation.agent_config["min_buy_score"] == 60

    @pytest.mark.asyncio
    async def test_min_buy_score_accepts_custom_value(
        self,
        async_client: AsyncClient,
        db_session: AsyncSession,
    ):
        """Custom min_buy_score value is stored in agent_config."""
        # Arrange
        request_data = {
            "symbols": ["AAPL"],
            "start_date": "2024-01-01",
            "end_date": "2024-01-31",
            "min_buy_score": 80,
        }

        # Act
        response = await async_client.post(
            "/api/v1/arena/simulations",
            json=request_data,
        )

        # Assert
        assert response.status_code == 202
        data = response.json()
        simulation_id = data["id"]

        # Verify agent_config in database contains min_buy_score: 80
        stmt = select(ArenaSimulation).where(ArenaSimulation.id == simulation_id)
        result = await db_session.execute(stmt)
        simulation = result.scalar_one()
        assert simulation.agent_config["min_buy_score"] == 80

    @pytest.mark.asyncio
    async def test_min_buy_score_accepts_minimum_value_20(
        self,
        async_client: AsyncClient,
        db_session: AsyncSession,
    ):
        """min_buy_score accepts minimum value of 20."""
        # Arrange
        request_data = {
            "symbols": ["AAPL"],
            "start_date": "2024-01-01",
            "end_date": "2024-01-31",
            "min_buy_score": 20,
        }

        # Act
        response = await async_client.post(
            "/api/v1/arena/simulations",
            json=request_data,
        )

        # Assert
        assert response.status_code == 202
        data = response.json()
        simulation_id = data["id"]

        stmt = select(ArenaSimulation).where(ArenaSimulation.id == simulation_id)
        result = await db_session.execute(stmt)
        simulation = result.scalar_one()
        assert simulation.agent_config["min_buy_score"] == 20

    @pytest.mark.asyncio
    async def test_min_buy_score_accepts_maximum_value_100(
        self,
        async_client: AsyncClient,
        db_session: AsyncSession,
    ):
        """min_buy_score accepts maximum value of 100."""
        # Arrange
        request_data = {
            "symbols": ["AAPL"],
            "start_date": "2024-01-01",
            "end_date": "2024-01-31",
            "min_buy_score": 100,
        }

        # Act
        response = await async_client.post(
            "/api/v1/arena/simulations",
            json=request_data,
        )

        # Assert
        assert response.status_code == 202
        data = response.json()
        simulation_id = data["id"]

        stmt = select(ArenaSimulation).where(ArenaSimulation.id == simulation_id)
        result = await db_session.execute(stmt)
        simulation = result.scalar_one()
        assert simulation.agent_config["min_buy_score"] == 100

    @pytest.mark.asyncio
    async def test_min_buy_score_rejects_below_minimum(
        self,
        async_client: AsyncClient,
    ):
        """min_buy_score below 20 returns validation error."""
        # Arrange
        request_data = {
            "symbols": ["AAPL"],
            "start_date": "2024-01-01",
            "end_date": "2024-01-31",
            "min_buy_score": 19,
        }

        # Act
        response = await async_client.post(
            "/api/v1/arena/simulations",
            json=request_data,
        )

        # Assert
        assert response.status_code == 422
        error_detail = response.json()
        assert "detail" in error_detail
        assert any("min_buy_score" in str(error).lower() for error in error_detail["detail"])

    @pytest.mark.asyncio
    async def test_min_buy_score_rejects_above_maximum(
        self,
        async_client: AsyncClient,
    ):
        """min_buy_score above 100 returns validation error."""
        # Arrange
        request_data = {
            "symbols": ["AAPL"],
            "start_date": "2024-01-01",
            "end_date": "2024-01-31",
            "min_buy_score": 101,
        }

        # Act
        response = await async_client.post(
            "/api/v1/arena/simulations",
            json=request_data,
        )

        # Assert
        assert response.status_code == 422
        error_detail = response.json()
        assert "detail" in error_detail
        assert any("min_buy_score" in str(error).lower() for error in error_detail["detail"])

    @pytest.mark.asyncio
    async def test_min_buy_score_combined_with_trailing_stop(
        self,
        async_client: AsyncClient,
        db_session: AsyncSession,
    ):
        """Both min_buy_score and trailing_stop_pct are included in agent_config."""
        # Arrange
        request_data = {
            "symbols": ["AAPL"],
            "start_date": "2024-01-01",
            "end_date": "2024-01-31",
            "trailing_stop_pct": 7.5,
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
        simulation_id = data["id"]

        # Verify both fields in agent_config
        stmt = select(ArenaSimulation).where(ArenaSimulation.id == simulation_id)
        result = await db_session.execute(stmt)
        simulation = result.scalar_one()
        assert simulation.agent_config["trailing_stop_pct"] == 7.5
        assert simulation.agent_config["min_buy_score"] == 75
