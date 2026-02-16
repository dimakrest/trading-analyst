"""Unit tests for agent config API endpoints."""

import pytest
from fastapi import status
from httpx import AsyncClient


@pytest.mark.asyncio
class TestAgentConfigsAPI:
    """Tests for agent configuration CRUD endpoints."""

    async def test_list_agent_configs_initially_empty(self, async_client: AsyncClient):
        """Test listing agent configs (initially empty in test environment)."""
        response = await async_client.get("/api/v1/agent-configs")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "items" in data
        assert "total" in data
        # In test environment, starts empty (no seeded data)
        assert isinstance(data["items"], list)
        assert isinstance(data["total"], int)

    async def test_create_agent_config(self, async_client: AsyncClient):
        """Test creating a new agent configuration."""
        payload = {
            "name": "RSI-2 Strategy",
            "agent_type": "live20",
            "scoring_algorithm": "rsi2"
        }

        response = await async_client.post("/api/v1/agent-configs", json=payload)

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["name"] == "RSI-2 Strategy"
        assert data["agent_type"] == "live20"
        assert data["scoring_algorithm"] == "rsi2"
        assert "id" in data

    async def test_create_agent_config_duplicate_name(self, async_client: AsyncClient):
        """Test that creating a config with duplicate name fails."""
        payload = {
            "name": "Test Config",
            "scoring_algorithm": "cci"
        }

        # Create first config
        response1 = await async_client.post("/api/v1/agent-configs", json=payload)
        assert response1.status_code == status.HTTP_201_CREATED

        # Try to create duplicate
        response2 = await async_client.post("/api/v1/agent-configs", json=payload)
        assert response2.status_code == status.HTTP_400_BAD_REQUEST
        assert "already exists" in response2.json()["detail"]

    async def test_create_agent_config_invalid_algorithm(self, async_client: AsyncClient):
        """Test that invalid scoring_algorithm is rejected."""
        payload = {
            "name": "Invalid Config",
            "scoring_algorithm": "invalid"
        }

        response = await async_client.post("/api/v1/agent-configs", json=payload)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    async def test_get_agent_config_by_id(self, async_client: AsyncClient):
        """Test retrieving a specific agent config by ID."""
        # Create a config
        payload = {
            "name": "Get Test Config",
            "scoring_algorithm": "rsi2"
        }
        create_response = await async_client.post("/api/v1/agent-configs", json=payload)
        assert create_response.status_code == status.HTTP_201_CREATED
        config_id = create_response.json()["id"]

        # Get by ID
        response = await async_client.get(f"/api/v1/agent-configs/{config_id}")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["id"] == config_id
        assert data["name"] == "Get Test Config"
        assert data["scoring_algorithm"] == "rsi2"

    async def test_get_agent_config_not_found(self, async_client: AsyncClient):
        """Test that getting non-existent config returns 404."""
        response = await async_client.get("/api/v1/agent-configs/99999")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    async def test_update_agent_config_name(self, async_client: AsyncClient):
        """Test updating an agent config name."""
        # Create a config
        payload = {
            "name": "Original Name",
            "scoring_algorithm": "cci"
        }
        create_response = await async_client.post("/api/v1/agent-configs", json=payload)
        config_id = create_response.json()["id"]

        # Update name
        update_payload = {"name": "Updated Name"}
        response = await async_client.put(
            f"/api/v1/agent-configs/{config_id}",
            json=update_payload
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["name"] == "Updated Name"
        assert data["scoring_algorithm"] == "cci"  # Unchanged

    async def test_update_agent_config_algorithm(self, async_client: AsyncClient):
        """Test updating an agent config scoring algorithm."""
        # Create a config
        payload = {
            "name": "Update Algo Test",
            "scoring_algorithm": "cci"
        }
        create_response = await async_client.post("/api/v1/agent-configs", json=payload)
        config_id = create_response.json()["id"]

        # Update algorithm
        update_payload = {"scoring_algorithm": "rsi2"}
        response = await async_client.put(
            f"/api/v1/agent-configs/{config_id}",
            json=update_payload
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["name"] == "Update Algo Test"  # Unchanged
        assert data["scoring_algorithm"] == "rsi2"

    async def test_update_agent_config_duplicate_name(self, async_client: AsyncClient):
        """Test that updating to a duplicate name fails."""
        # Create two configs
        config1 = await async_client.post("/api/v1/agent-configs", json={
            "name": "Config 1",
            "scoring_algorithm": "cci"
        })
        config1_id = config1.json()["id"]

        await async_client.post("/api/v1/agent-configs", json={
            "name": "Config 2",
            "scoring_algorithm": "rsi2"
        })

        # Try to rename Config 1 to "Config 2"
        response = await async_client.put(
            f"/api/v1/agent-configs/{config1_id}",
            json={"name": "Config 2"}
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "already exists" in response.json()["detail"]

    async def test_delete_agent_config(self, async_client: AsyncClient):
        """Test soft-deleting an agent config."""
        # Create two configs so we don't delete the last one
        payload1 = {
            "name": "Delete Test Config 1",
            "scoring_algorithm": "cci"
        }
        create_response1 = await async_client.post("/api/v1/agent-configs", json=payload1)
        config_id = create_response1.json()["id"]

        payload2 = {
            "name": "Delete Test Config 2",
            "scoring_algorithm": "rsi2"
        }
        await async_client.post("/api/v1/agent-configs", json=payload2)

        # Delete the first one
        response = await async_client.delete(f"/api/v1/agent-configs/{config_id}")

        assert response.status_code == status.HTTP_204_NO_CONTENT

        # Verify it's no longer in the list
        list_response = await async_client.get("/api/v1/agent-configs")
        items = list_response.json()["items"]
        assert not any(item["id"] == config_id for item in items)

    async def test_cannot_delete_last_config(self, async_client: AsyncClient):
        """Test that deleting the last remaining config is prevented."""
        # Create one config
        payload = {
            "name": "Last Config",
            "scoring_algorithm": "cci"
        }
        create_response = await async_client.post("/api/v1/agent-configs", json=payload)
        config_id = create_response.json()["id"]

        # Try to delete it (it's the only one)
        response = await async_client.delete(f"/api/v1/agent-configs/{config_id}")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "last remaining" in response.json()["detail"]
