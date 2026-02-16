"""Integration tests for agent config pipeline with Live20 and Arena."""

import pytest
from httpx import AsyncClient
from fastapi import status


@pytest.mark.asyncio
class TestAgentConfigPipeline:
    """Tests for agent config integration with Live20 and Arena."""

    async def test_live20_with_agent_config(
        self,
        async_client: AsyncClient,
    ):
        """Test Live20 analyze accepts agent_config_id and stores algorithm correctly."""
        # Create an RSI-2 agent config
        config_response = await async_client.post("/api/v1/agent-configs", json={
            "name": "Test RSI-2",
            "scoring_algorithm": "rsi2"
        })
        assert config_response.status_code == status.HTTP_201_CREATED
        agent_config_id = config_response.json()["id"]

        # Analyze with agent_config_id
        analyze_response = await async_client.post(
            "/api/v1/live-20/analyze",
            json={
                "symbols": ["AAPL"],
                "agent_config_id": agent_config_id
            }
        )
        assert analyze_response.status_code == status.HTTP_200_OK
        run_id = analyze_response.json()["run_id"]

        # Get run details
        run_response = await async_client.get(f"/api/v1/live-20/runs/{run_id}")
        assert run_response.status_code == status.HTTP_200_OK

        run_data = run_response.json()
        # Verify agent_config_id is stored correctly
        assert run_data["agent_config_id"] == agent_config_id
        # Verify scoring_algorithm from agent config is used
        assert run_data["scoring_algorithm"] == "rsi2"

    async def test_live20_without_agent_config_defaults_to_cci(
        self,
        async_client: AsyncClient,
    ):
        """Test Live20 defaults to CCI when no agent_config_id provided."""
        # Analyze without agent_config_id
        analyze_response = await async_client.post(
            "/api/v1/live-20/analyze",
            json={
                "symbols": ["MSFT"]
            }
        )
        assert analyze_response.status_code == status.HTTP_200_OK
        run_id = analyze_response.json()["run_id"]

        # Get run details
        run_response = await async_client.get(f"/api/v1/live-20/runs/{run_id}")
        run_data = run_response.json()

        # Should default to CCI
        assert run_data["scoring_algorithm"] == "cci"
        assert run_data["agent_config_id"] is None

    async def test_arena_with_agent_config(
        self,
        async_client: AsyncClient,
    ):
        """Test Arena simulation uses correct algorithm from agent config."""
        # Create an RSI-2 agent config
        config_response = await async_client.post("/api/v1/agent-configs", json={
            "name": "Arena RSI-2",
            "scoring_algorithm": "rsi2"
        })
        agent_config_id = config_response.json()["id"]

        # Create simulation with agent_config_id
        sim_response = await async_client.post(
            "/api/v1/arena/simulations",
            json={
                "symbols": ["AAPL", "MSFT"],
                "start_date": "2025-01-01",
                "end_date": "2025-01-31",
                "initial_capital": 10000,
                "position_size": 1000,
                "agent_config_id": agent_config_id
            }
        )

        assert sim_response.status_code == status.HTTP_202_ACCEPTED
        sim_data = sim_response.json()

        # Verify scoring_algorithm from agent config was used
        assert sim_data["scoring_algorithm"] == "rsi2"

    async def test_arena_without_agent_config_uses_request_algorithm(
        self,
        async_client: AsyncClient,
    ):
        """Test Arena uses scoring_algorithm from request when no agent_config_id."""
        sim_response = await async_client.post(
            "/api/v1/arena/simulations",
            json={
                "symbols": ["AAPL", "MSFT"],
                "start_date": "2025-01-01",
                "end_date": "2025-01-31",
                "initial_capital": 10000,
                "position_size": 1000,
                "scoring_algorithm": "rsi2"
            }
        )

        assert sim_response.status_code == status.HTTP_202_ACCEPTED
        sim_data = sim_response.json()
        assert sim_data["scoring_algorithm"] == "rsi2"

    async def test_live20_agent_config_id_takes_precedence(
        self,
        async_client: AsyncClient,
    ):
        """Test that agent_config_id overrides direct scoring_algorithm parameter."""
        # Create CCI agent config
        config_response = await async_client.post("/api/v1/agent-configs", json={
            "name": "Precedence Test",
            "scoring_algorithm": "cci"
        })
        agent_config_id = config_response.json()["id"]

        # Analyze with both agent_config_id (cci) and scoring_algorithm (rsi2)
        # agent_config_id should take precedence
        analyze_response = await async_client.post(
            "/api/v1/live-20/analyze",
            json={
                "symbols": ["GOOGL"],
                "agent_config_id": agent_config_id,
                "scoring_algorithm": "rsi2"  # Should be ignored
            }
        )
        run_id = analyze_response.json()["run_id"]

        run_response = await async_client.get(f"/api/v1/live-20/runs/{run_id}")
        run_data = run_response.json()

        # Should use CCI from agent_config_id, not RSI-2 from direct param
        assert run_data["scoring_algorithm"] == "cci"
        assert run_data["agent_config_id"] == agent_config_id

    async def test_live20_invalid_agent_config_id(
        self,
        async_client: AsyncClient,
    ):
        """Test that invalid agent_config_id returns 404."""
        analyze_response = await async_client.post(
            "/api/v1/live-20/analyze",
            json={
                "symbols": ["AAPL"],
                "agent_config_id": 99999
            }
        )

        assert analyze_response.status_code == status.HTTP_404_NOT_FOUND
        assert "Agent config" in analyze_response.json()["detail"]

    async def test_arena_invalid_agent_config_id(
        self,
        async_client: AsyncClient,
    ):
        """Test that invalid agent_config_id returns 404."""
        sim_response = await async_client.post(
            "/api/v1/arena/simulations",
            json={
                "symbols": ["AAPL"],
                "start_date": "2025-01-01",
                "end_date": "2025-01-31",
                "agent_config_id": 99999
            }
        )

        assert sim_response.status_code == status.HTTP_404_NOT_FOUND
        assert "Agent config" in sim_response.json()["detail"]
