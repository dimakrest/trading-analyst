"""Tests for health check endpoints.
"""
from datetime import datetime
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from fastapi import status
from fastapi.testclient import TestClient
from httpx import AsyncClient

from app.api.v1.health import health_check
from app.api.v1.health import liveness_check
from app.api.v1.health import readiness_check


class TestHealthEndpoints:
    """Test health check endpoints functionality."""

    @pytest.mark.unit
    def test_health_endpoint_success(self, client: TestClient):
        """Test successful health check."""
        response = client.get("/api/v1/health")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Check response structure
        assert "status" in data
        assert "timestamp" in data
        assert "version" in data
        assert "environment" in data
        assert "checks" in data

        # Check response values
        assert data["status"] == "healthy"
        assert data["version"] == "1.0.0"
        assert isinstance(data["checks"], dict)

        # Validate timestamp format
        timestamp = datetime.fromisoformat(data["timestamp"])
        assert isinstance(timestamp, datetime)

    @pytest.mark.asyncio
    async def test_health_endpoint_async(self, async_client: AsyncClient):
        """Test health check with async client."""
        response = await async_client.get("/api/v1/health")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "healthy"

    @pytest.mark.unit
    def test_health_check_application_component(self, client: TestClient):
        """Test that application component is checked."""
        response = client.get("/api/v1/health")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert "application" in data["checks"]
        app_check = data["checks"]["application"]
        assert "status" in app_check
        assert "message" in app_check
        assert app_check["status"] == "healthy"

    def test_readiness_endpoint(self, client: TestClient):
        """Test readiness check endpoint."""
        response = client.get("/api/v1/health/ready")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert "status" in data
        assert "timestamp" in data
        assert data["status"] == "ready"

        # Validate timestamp format
        timestamp = datetime.fromisoformat(data["timestamp"])
        assert isinstance(timestamp, datetime)

    @pytest.mark.asyncio
    async def test_readiness_endpoint_async(self, async_client: AsyncClient):
        """Test readiness check with async client."""
        response = await async_client.get("/api/v1/health/ready")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "ready"

    def test_liveness_endpoint(self, client: TestClient):
        """Test liveness check endpoint."""
        response = client.get("/api/v1/health/live")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert "status" in data
        assert "timestamp" in data
        assert data["status"] == "alive"

        # Validate timestamp format
        timestamp = datetime.fromisoformat(data["timestamp"])
        assert isinstance(timestamp, datetime)

    @pytest.mark.asyncio
    async def test_liveness_endpoint_async(self, async_client: AsyncClient):
        """Test liveness check with async client."""
        response = await async_client.get("/api/v1/health/live")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "alive"


class TestHealthCheckLogic:
    """Test the health check logic in detail."""

    @pytest.mark.asyncio
    async def test_health_check_function_directly(self):
        """Test the health_check function directly."""
        result = await health_check()

        assert isinstance(result, dict)
        assert "status" in result
        assert "timestamp" in result
        assert "version" in result
        assert "environment" in result
        assert "checks" in result

        assert result["status"] == "healthy"
        assert result["version"] == "1.0.0"
        assert isinstance(result["checks"], dict)

    @pytest.mark.asyncio
    async def test_readiness_check_function_directly(self):
        """Test the readiness_check function directly."""
        result = await readiness_check()

        assert isinstance(result, dict)
        assert "status" in result
        assert "timestamp" in result
        assert result["status"] == "ready"

    @pytest.mark.asyncio
    async def test_liveness_check_function_directly(self):
        """Test the liveness_check function directly."""
        result = await liveness_check()

        assert isinstance(result, dict)
        assert "status" in result
        assert "timestamp" in result
        assert result["status"] == "alive"

    @pytest.mark.asyncio
    async def test_health_check_includes_environment(self):
        """Test that health check includes environment information."""
        result = await health_check()

        assert "environment" in result
        # Should have environment from test settings
        assert result["environment"] in ["test", "development"]

    @pytest.mark.asyncio
    async def test_health_check_application_component_success(self):
        """Test application component check succeeds."""
        result = await health_check()

        assert "checks" in result
        assert "application" in result["checks"]

        app_check = result["checks"]["application"]
        assert app_check["status"] == "healthy"
        assert "message" in app_check
        assert "ready" in app_check["message"].lower()


class TestHealthCheckErrorHandling:
    """Test error handling in health checks."""

    @pytest.mark.asyncio
    @patch("asyncio.sleep")
    async def test_health_check_with_asyncio_error(self, mock_sleep):
        """Test health check when asyncio operations fail."""
        # Make asyncio.sleep raise an exception
        mock_sleep.side_effect = Exception("Async operation failed")

        # The function should raise HTTPException with 503 when unhealthy
        with pytest.raises(HTTPException) as exc_info:
            await health_check()

        assert exc_info.value.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        # The detail contains the health data
        health_data = exc_info.value.detail
        assert health_data["status"] == "unhealthy"
        assert "checks" in health_data
        assert "application" in health_data["checks"]
        assert health_data["checks"]["application"]["status"] == "unhealthy"

    @pytest.mark.unit
    def test_health_endpoint_exception_returns_503(self, client: TestClient):
        """Test that health endpoint returns 503 when unhealthy."""
        import asyncio as orig_asyncio

        # Create a selective mock that only fails for our specific call
        original_sleep = orig_asyncio.sleep

        async def selective_sleep(delay, *args, **kwargs):
            # Only fail for the health check's sleep (0.001 seconds)
            if delay == 0.001:
                raise Exception("Test failure")
            # Let other sleeps through (for test infrastructure)
            return await original_sleep(delay, *args, **kwargs)

        with patch("app.api.v1.health.asyncio.sleep", side_effect=selective_sleep):
            response = client.get("/api/v1/health")
            assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE

            # Verify response contains health data
            response_data = response.json()
            assert "detail" in response_data
            assert response_data["detail"]["status"] == "unhealthy"


class TestHealthCheckResponseFormat:
    """Test the format and structure of health check responses."""

    def test_health_response_content_type(self, client: TestClient):
        """Test that health endpoint returns JSON content type."""
        response = client.get("/api/v1/health")
        assert "application/json" in response.headers["content-type"]

    def test_readiness_response_content_type(self, client: TestClient):
        """Test that readiness endpoint returns JSON content type."""
        response = client.get("/api/v1/health/ready")
        assert "application/json" in response.headers["content-type"]

    def test_liveness_response_content_type(self, client: TestClient):
        """Test that liveness endpoint returns JSON content type."""
        response = client.get("/api/v1/health/live")
        assert "application/json" in response.headers["content-type"]

    @pytest.mark.unit
    def test_health_response_has_required_fields(self, client: TestClient):
        """Test that health response has all required fields."""
        response = client.get("/api/v1/health")
        data = response.json()

        required_fields = ["status", "timestamp", "version", "environment", "checks"]
        for field in required_fields:
            assert field in data, f"Missing required field: {field}"

    def test_timestamp_format_is_iso(self, client: TestClient):
        """Test that timestamps are in ISO format."""
        endpoints = ["/api/v1/health", "/api/v1/health/ready", "/api/v1/health/live"]

        for endpoint in endpoints:
            response = client.get(endpoint)
            data = response.json()
            timestamp_str = data["timestamp"]

            # Should be able to parse as ISO format
            timestamp = datetime.fromisoformat(timestamp_str)
            assert isinstance(timestamp, datetime)

    def test_status_values_are_valid(self, client: TestClient):
        """Test that status values are from valid set."""
        response = client.get("/api/v1/health")
        data = response.json()

        valid_statuses = ["healthy", "unhealthy"]
        assert data["status"] in valid_statuses

        response_ready = client.get("/api/v1/health/ready")
        data_ready = response_ready.json()
        assert data_ready["status"] == "ready"

        response_live = client.get("/api/v1/health/live")
        data_live = response_live.json()
        assert data_live["status"] == "alive"


@pytest.mark.integration
class TestHealthCheckIntegration:
    """Integration tests for health check endpoints."""

    def test_all_health_endpoints_accessible(self, client: TestClient):
        """Test that all health endpoints are accessible."""
        endpoints = ["/api/v1/health", "/api/v1/health/ready", "/api/v1/health/live"]

        for endpoint in endpoints:
            response = client.get(endpoint)
            assert response.status_code == status.HTTP_200_OK

    @pytest.mark.asyncio
    async def test_concurrent_health_checks(self, async_client: AsyncClient):
        """Test concurrent health check requests."""
        import asyncio

        async def make_health_request():
            return await async_client.get("/api/v1/health")

        # Make multiple concurrent requests
        tasks = [make_health_request() for _ in range(10)]
        responses = await asyncio.gather(*tasks)

        # All should succeed
        for response in responses:
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["status"] == "healthy"

    @pytest.mark.slow
    def test_health_check_performance(self, client: TestClient):
        """Test health check performance."""
        import time

        start_time = time.time()

        # Make multiple requests
        for _ in range(50):
            response = client.get("/api/v1/health")
            assert response.status_code == status.HTTP_200_OK

        end_time = time.time()
        total_time = end_time - start_time

        # Health checks should be fast (adjust threshold as needed)
        assert total_time < 5.0  # 50 requests in 5 seconds

    def test_health_check_with_different_methods(self, client: TestClient):
        """Test health endpoints with different HTTP methods."""
        # GET should work
        response = client.get("/api/v1/health")
        assert response.status_code == status.HTTP_200_OK

        # POST should not be allowed (should return 405 Method Not Allowed)
        response = client.post("/api/v1/health")
        assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

        # PUT should not be allowed
        response = client.put("/api/v1/health")
        assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

        # DELETE should not be allowed
        response = client.delete("/api/v1/health")
        assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED
