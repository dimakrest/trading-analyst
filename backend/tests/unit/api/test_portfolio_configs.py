"""Unit tests for portfolio config API endpoints."""

import pytest
from fastapi import status
from httpx import AsyncClient


@pytest.mark.asyncio
class TestPortfolioConfigsAPI:
    """Tests for portfolio configuration CRUD endpoints."""

    async def test_list_portfolio_configs_initially_empty(self, async_client: AsyncClient):
        """Test listing portfolio configs (initially empty in test environment)."""
        response = await async_client.get("/api/v1/portfolio-configs")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert isinstance(data["items"], list)
        assert isinstance(data["total"], int)

    async def test_create_portfolio_config(self, async_client: AsyncClient):
        """Test creating a new portfolio configuration."""
        payload = {
            "name": "Balanced Setup",
            "portfolio_strategy": "score_sector_moderate_atr",
            "position_size": 1500,
            "min_buy_score": 70,
            "trailing_stop_pct": 6.5,
            "max_per_sector": 2,
            "max_open_positions": 10,
        }

        response = await async_client.post("/api/v1/portfolio-configs", json=payload)

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["name"] == "Balanced Setup"
        assert data["portfolio_strategy"] == "score_sector_moderate_atr"
        assert data["position_size"] == 1500
        assert data["min_buy_score"] == 70
        assert data["trailing_stop_pct"] == 6.5
        assert data["max_per_sector"] == 2
        assert data["max_open_positions"] == 10
        assert "id" in data

    async def test_create_portfolio_config_duplicate_name(self, async_client: AsyncClient):
        """Test that creating a config with duplicate name fails."""
        payload = {
            "name": "Duplicate Setup",
            "portfolio_strategy": "score_sector_low_atr",
        }

        first = await async_client.post("/api/v1/portfolio-configs", json=payload)
        assert first.status_code == status.HTTP_201_CREATED

        second = await async_client.post("/api/v1/portfolio-configs", json=payload)
        assert second.status_code == status.HTTP_400_BAD_REQUEST
        assert "already exists" in second.json()["detail"]

    async def test_create_portfolio_config_invalid_strategy(self, async_client: AsyncClient):
        """Test that invalid portfolio strategy is rejected."""
        payload = {
            "name": "Invalid Setup",
            "portfolio_strategy": "does_not_exist",
        }

        response = await async_client.post("/api/v1/portfolio-configs", json=payload)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    async def test_get_portfolio_config_by_id(self, async_client: AsyncClient):
        """Test retrieving a specific portfolio config by ID."""
        create_response = await async_client.post(
            "/api/v1/portfolio-configs",
            json={
                "name": "Get Setup",
                "portfolio_strategy": "score_sector_high_atr",
            },
        )
        config_id = create_response.json()["id"]

        response = await async_client.get(f"/api/v1/portfolio-configs/{config_id}")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["id"] == config_id
        assert data["name"] == "Get Setup"
        assert data["portfolio_strategy"] == "score_sector_high_atr"
        assert data["position_size"] == 1000
        assert data["min_buy_score"] == 60
        assert data["trailing_stop_pct"] == 5.0

    async def test_get_portfolio_config_not_found(self, async_client: AsyncClient):
        """Test that getting non-existent config returns 404."""
        response = await async_client.get("/api/v1/portfolio-configs/99999")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    async def test_update_portfolio_config(self, async_client: AsyncClient):
        """Test updating a portfolio configuration."""
        create_response = await async_client.post(
            "/api/v1/portfolio-configs",
            json={
                "name": "Original Setup",
                "portfolio_strategy": "score_sector_low_atr",
                "position_size": 1200,
                "min_buy_score": 55,
                "trailing_stop_pct": 7.0,
                "max_per_sector": 2,
            },
        )
        config_id = create_response.json()["id"]

        response = await async_client.put(
            f"/api/v1/portfolio-configs/{config_id}",
            json={
                "name": "Updated Setup",
                "portfolio_strategy": "score_sector_high_atr",
                "position_size": 2000,
                "min_buy_score": 75,
                "trailing_stop_pct": 4.5,
                "max_per_sector": 3,
                "max_open_positions": 7,
            },
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["name"] == "Updated Setup"
        assert data["portfolio_strategy"] == "score_sector_high_atr"
        assert data["position_size"] == 2000
        assert data["min_buy_score"] == 75
        assert data["trailing_stop_pct"] == 4.5
        assert data["max_per_sector"] == 3
        assert data["max_open_positions"] == 7

    async def test_update_portfolio_config_duplicate_name(self, async_client: AsyncClient):
        """Test that updating to a duplicate name fails."""
        first = await async_client.post(
            "/api/v1/portfolio-configs",
            json={"name": "Config A", "portfolio_strategy": "none"},
        )
        first_id = first.json()["id"]

        await async_client.post(
            "/api/v1/portfolio-configs",
            json={"name": "Config B", "portfolio_strategy": "none"},
        )

        response = await async_client.put(
            f"/api/v1/portfolio-configs/{first_id}",
            json={"name": "Config B"},
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "already exists" in response.json()["detail"]

    async def test_delete_portfolio_config(self, async_client: AsyncClient):
        """Test soft-deleting a portfolio config."""
        create_response = await async_client.post(
            "/api/v1/portfolio-configs",
            json={
                "name": "Delete Setup",
                "portfolio_strategy": "score_sector_low_atr",
            },
        )
        config_id = create_response.json()["id"]

        delete_response = await async_client.delete(f"/api/v1/portfolio-configs/{config_id}")
        assert delete_response.status_code == status.HTTP_204_NO_CONTENT

        list_response = await async_client.get("/api/v1/portfolio-configs")
        items = list_response.json()["items"]
        assert not any(item["id"] == config_id for item in items)

    async def test_update_portfolio_config_strategy_none_clears_caps(
        self,
        async_client: AsyncClient,
    ):
        """Switching strategy to none should clear max caps."""
        create_response = await async_client.post(
            "/api/v1/portfolio-configs",
            json={
                "name": "Clear Caps Setup",
                "portfolio_strategy": "score_sector_low_atr",
                "position_size": 1000,
                "min_buy_score": 60,
                "trailing_stop_pct": 5.5,
                "max_per_sector": 2,
                "max_open_positions": 6,
            },
        )
        config_id = create_response.json()["id"]

        update_response = await async_client.put(
            f"/api/v1/portfolio-configs/{config_id}",
            json={
                "portfolio_strategy": "none",
            },
        )

        assert update_response.status_code == status.HTTP_200_OK
        data = update_response.json()
        assert data["portfolio_strategy"] == "none"
        assert data["position_size"] == 1000
        assert data["min_buy_score"] == 60
        assert data["trailing_stop_pct"] == 5.5
        assert data["max_per_sector"] is None
        assert data["max_open_positions"] is None
