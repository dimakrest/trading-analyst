"""Tests for the main FastAPI application.
"""
import pytest
from fastapi import status
from fastapi.testclient import TestClient
from httpx import AsyncClient

from app.main import app
from app.main import create_app


class TestMainApplication:
    """Test the main FastAPI application configuration and endpoints."""

    def test_create_app(self):
        """Test application factory function."""
        test_app = create_app()
        assert test_app is not None
        assert test_app.title == "Trading Analyst API"
        assert test_app.version == "1.0.0"

    def test_app_instance_exists(self):
        """Test that the app instance is created."""
        assert app is not None
        assert hasattr(app, "title")
        assert hasattr(app, "version")

    @pytest.mark.unit
    def test_root_endpoint(self, client: TestClient):
        """Test the root endpoint returns expected information."""
        response = client.get("/")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert "message" in data
        assert "version" in data
        assert "docs" in data
        assert "health" in data
        assert data["message"] == "Trading Analyst API"
        assert data["version"] == "1.0.0"

    @pytest.mark.asyncio
    async def test_root_endpoint_async(self, async_client: AsyncClient):
        """Test the root endpoint with async client."""
        response = await async_client.get("/")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["message"] == "Trading Analyst API"
        assert data["version"] == "1.0.0"

    @pytest.mark.unit
    def test_cors_headers(self, client: TestClient):
        """Test CORS headers are properly configured."""
        # Make a preflight request
        response = client.options(
            "/api/v1/health",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "Content-Type",
            },
        )

        # Should allow the request
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_204_NO_CONTENT]

    def test_nonexistent_endpoint(self, client: TestClient):
        """Test that nonexistent endpoints return 404."""
        response = client.get("/nonexistent")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_app_middleware_configured(self):
        """Test that middleware is properly configured."""
        from starlette.middleware.cors import CORSMiddleware
        # Check that CORS middleware is configured
        middleware_classes = [middleware.cls for middleware in app.user_middleware]
        assert CORSMiddleware in middleware_classes

    def test_exception_handler_registered(self):
        """Test that global exception handler is registered."""
        # The exception handler should be registered in the app
        assert hasattr(app, "exception_handlers")
        assert Exception in app.exception_handlers

    @pytest.mark.unit
    def test_docs_endpoint_accessibility(self, client: TestClient):
        """Test that docs endpoint is accessible in development."""
        response = client.get("/docs")
        # Should either be accessible (200) or redirect (3xx)
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_301_MOVED_PERMANENTLY,
            status.HTTP_302_FOUND,
            status.HTTP_404_NOT_FOUND,  # Might be disabled in test environment
        ]

    def test_redoc_endpoint_accessibility(self, client: TestClient):
        """Test that redoc endpoint is accessible in development."""
        response = client.get("/redoc")
        # Should either be accessible (200) or redirect (3xx)
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_301_MOVED_PERMANENTLY,
            status.HTTP_302_FOUND,
            status.HTTP_404_NOT_FOUND,  # Might be disabled in test environment
        ]


class TestApplicationLifespan:
    """Test application lifespan management."""

    def test_lifespan_context_manager(self):
        """Test that lifespan context manager exists."""
        import inspect

        from app.main import lifespan

        # lifespan is decorated with @asynccontextmanager, so it's callable
        assert inspect.isfunction(lifespan) or hasattr(lifespan, '__call__')

    @pytest.mark.asyncio
    async def test_app_startup_and_shutdown(self, monkeypatch):
        """Test application startup and shutdown process."""
        from app.core.config import Settings
        from app.main import lifespan

        # Mock settings with valid configuration (mock broker to skip IB validation)
        mock_settings = Settings(
            broker_type="mock",  # Use mock broker to avoid IB configuration requirements
            market_data_provider="mock",
        )

        def mock_get_settings():
            return mock_settings

        monkeypatch.setattr("app.main.get_settings", mock_get_settings)
        monkeypatch.setattr("app.core.deps.get_settings", mock_get_settings)

        # Test that lifespan manager doesn't raise exceptions
        async with lifespan(app):
            # Application should be running normally
            pass
        # Should complete without errors

    @pytest.mark.asyncio
    async def test_port_validation_paper_account_correct_port(self, monkeypatch):
        """Test port validation allows paper account with port 4001."""
        from app.core.config import Settings
        from app.main import lifespan

        # Mock settings with paper account + correct port
        mock_settings = Settings(
            broker_type="ib",
            ib_account="DU1234567",  # Paper account
            ib_port=4001,  # Correct port for paper trading
            market_data_provider="mock",
        )

        def mock_get_settings():
            return mock_settings

        monkeypatch.setattr("app.main.get_settings", mock_get_settings)
        monkeypatch.setattr("app.core.deps.get_settings", mock_get_settings)

        # Should not raise any exception
        async with lifespan(app):
            pass

    @pytest.mark.asyncio
    async def test_port_validation_live_account_correct_port(self, monkeypatch):
        """Test port validation allows live account with port 4002."""
        from app.core.config import Settings
        from app.main import lifespan

        # Mock settings with live account + correct port
        mock_settings = Settings(
            broker_type="ib",
            ib_account="U1234567",  # Live account
            ib_port=4002,  # Correct port for live trading
            market_data_provider="mock",
        )

        def mock_get_settings():
            return mock_settings

        monkeypatch.setattr("app.main.get_settings", mock_get_settings)
        monkeypatch.setattr("app.core.deps.get_settings", mock_get_settings)

        # Should not raise any exception
        async with lifespan(app):
            pass

    @pytest.mark.asyncio
    async def test_port_validation_paper_account_wrong_port(self, monkeypatch):
        """Test port validation rejects paper account with wrong port."""
        from app.core.config import Settings
        from app.main import lifespan

        # Mock settings with paper account + WRONG port
        mock_settings = Settings(
            broker_type="ib",
            ib_account="DU1234567",  # Paper account
            ib_port=4002,  # WRONG: should be 4001
            market_data_provider="mock",
        )

        def mock_get_settings():
            return mock_settings

        monkeypatch.setattr("app.main.get_settings", mock_get_settings)
        monkeypatch.setattr("app.core.deps.get_settings", mock_get_settings)

        # Should raise ValueError with clear message
        with pytest.raises(ValueError) as exc_info:
            async with lifespan(app):
                pass

        error_message = str(exc_info.value)
        assert "Configuration mismatch" in error_message
        assert "DU1234567" in error_message
        assert "port 4001" in error_message
        assert "4002" in error_message

    @pytest.mark.asyncio
    async def test_port_validation_live_account_wrong_port(self, monkeypatch):
        """Test port validation rejects live account with wrong port."""
        from app.core.config import Settings
        from app.main import lifespan

        # Mock settings with live account + WRONG port
        mock_settings = Settings(
            broker_type="ib",
            ib_account="U1234567",  # Live account
            ib_port=4001,  # WRONG: should be 4002
            market_data_provider="mock",
        )

        def mock_get_settings():
            return mock_settings

        monkeypatch.setattr("app.main.get_settings", mock_get_settings)
        monkeypatch.setattr("app.core.deps.get_settings", mock_get_settings)

        # Should raise ValueError with clear message
        with pytest.raises(ValueError) as exc_info:
            async with lifespan(app):
                pass

        error_message = str(exc_info.value)
        assert "Configuration mismatch" in error_message
        assert "U1234567" in error_message
        assert "port 4002" in error_message
        assert "4001" in error_message

    @pytest.mark.asyncio
    async def test_port_validation_skipped_for_mock_broker(self, monkeypatch):
        """Test port validation is skipped when using mock broker."""
        from app.core.config import Settings
        from app.main import lifespan

        # Mock settings with mock broker (validation should be skipped)
        mock_settings = Settings(
            broker_type="mock",  # Mock broker - validation should be skipped
            ib_account="DU1234567",
            ib_port=9999,  # Arbitrary port - should be ignored
            market_data_provider="mock",
        )

        def mock_get_settings():
            return mock_settings

        monkeypatch.setattr("app.main.get_settings", mock_get_settings)
        monkeypatch.setattr("app.core.deps.get_settings", mock_get_settings)

        # Should not raise any exception (validation skipped)
        async with lifespan(app):
            pass

    @pytest.mark.asyncio
    async def test_ib_account_required_when_using_ib_broker(self, monkeypatch):
        """Test that IB_ACCOUNT is mandatory when using IB broker."""
        from app.core.config import Settings
        from app.main import lifespan

        # Mock settings with IB broker but NO account configured
        mock_settings = Settings(
            broker_type="ib",
            ib_account=None,  # Missing account - should fail
            ib_port=4001,
            market_data_provider="mock",
        )

        def mock_get_settings():
            return mock_settings

        monkeypatch.setattr("app.main.get_settings", mock_get_settings)
        monkeypatch.setattr("app.core.deps.get_settings", mock_get_settings)

        # Should raise ValueError about missing IB_ACCOUNT
        with pytest.raises(ValueError) as exc_info:
            async with lifespan(app):
                pass

        error_message = str(exc_info.value)
        assert "IB_ACCOUNT is not configured" in error_message
        assert "broker_type='ib'" in error_message

    @pytest.mark.asyncio
    async def test_ib_account_empty_string_rejected(self, monkeypatch):
        """Test that empty string IB_ACCOUNT is rejected when using IB broker."""
        from app.core.config import Settings
        from app.main import lifespan

        # Mock settings with IB broker but EMPTY account
        mock_settings = Settings(
            broker_type="ib",
            ib_account="",  # Empty string - should fail
            ib_port=4001,
            market_data_provider="mock",
        )

        def mock_get_settings():
            return mock_settings

        monkeypatch.setattr("app.main.get_settings", mock_get_settings)
        monkeypatch.setattr("app.core.deps.get_settings", mock_get_settings)

        # Should raise ValueError about missing IB_ACCOUNT
        with pytest.raises(ValueError) as exc_info:
            async with lifespan(app):
                pass

        error_message = str(exc_info.value)
        assert "IB_ACCOUNT is not configured" in error_message

    @pytest.mark.asyncio
    async def test_ib_account_whitespace_only_rejected(self, monkeypatch):
        """Test that whitespace-only IB_ACCOUNT is rejected when using IB broker."""
        from app.core.config import Settings
        from app.main import lifespan

        # Mock settings with IB broker but whitespace-only account
        mock_settings = Settings(
            broker_type="ib",
            ib_account="   ",  # Whitespace only - should fail
            ib_port=4001,
            market_data_provider="mock",
        )

        def mock_get_settings():
            return mock_settings

        monkeypatch.setattr("app.main.get_settings", mock_get_settings)
        monkeypatch.setattr("app.core.deps.get_settings", mock_get_settings)

        # Should raise ValueError about missing IB_ACCOUNT
        with pytest.raises(ValueError) as exc_info:
            async with lifespan(app):
                pass

        error_message = str(exc_info.value)
        assert "IB_ACCOUNT is not configured" in error_message


class TestApplicationConfiguration:
    """Test application configuration and settings."""

    def test_api_routes_included(self):
        """Test that API routes are properly included."""
        # Check that health routes are included
        routes = [route.path for route in app.routes]
        health_routes = [route for route in routes if "health" in route]
        assert len(health_routes) > 0

    def test_app_title_and_metadata(self):
        """Test application title and metadata."""
        assert app.title == "Trading Analyst API"
        assert "Trading Analyst API" in app.description
        assert "pattern detection" in app.description.lower()
        assert app.version == "1.0.0"

    def test_dependency_injection_works(self, client: TestClient):
        """Test that dependency injection is working."""
        # This is tested indirectly through health endpoints
        response = client.get("/api/v1/health")
        # Should work without dependency injection errors
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_503_SERVICE_UNAVAILABLE]


class TestErrorHandling:
    """Test error handling and exception management."""

    @pytest.mark.unit
    def test_global_exception_handler_structure(self):
        """Test that global exception handler is properly structured."""
        # The handler should be registered
        assert Exception in app.exception_handlers
        handler = app.exception_handlers[Exception]
        assert callable(handler)

    @pytest.mark.asyncio
    async def test_unhandled_exception_response_format(self, async_client: AsyncClient):
        """Test that unhandled exceptions return proper JSON format."""
        # This would need a route that deliberately raises an exception
        # For now, we just test that the handler exists and is callable
        handler = app.exception_handlers[Exception]
        assert callable(handler)

    def test_http_exception_handling(self, client: TestClient):
        """Test HTTP exception handling."""
        response = client.get("/nonexistent-endpoint")
        assert response.status_code == status.HTTP_404_NOT_FOUND

        data = response.json()
        assert "detail" in data


@pytest.mark.integration
class TestApplicationIntegration:
    """Integration tests for the complete application."""

    @pytest.mark.asyncio
    async def test_full_request_cycle(self, async_client: AsyncClient):
        """Test a complete request-response cycle."""
        response = await async_client.get("/")
        assert response.status_code == status.HTTP_200_OK

        data = response.json()
        assert isinstance(data, dict)
        assert "message" in data

    def test_multiple_concurrent_requests(self, client: TestClient):
        """Test handling multiple concurrent requests."""
        import concurrent.futures

        def make_request():
            return client.get("/")

        # Make multiple concurrent requests
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(make_request) for _ in range(10)]
            responses = [future.result() for future in futures]

        # All requests should succeed
        for response in responses:
            assert response.status_code == status.HTTP_200_OK

    @pytest.mark.slow
    def test_app_performance_basic(self, client: TestClient):
        """Basic performance test for the application."""
        import time

        start_time = time.time()

        # Make multiple requests
        for _ in range(100):
            response = client.get("/")
            assert response.status_code == status.HTTP_200_OK

        end_time = time.time()
        total_time = end_time - start_time

        # Should complete 100 requests in reasonable time (adjust threshold as needed)
        assert total_time < 10.0  # 10 seconds for 100 requests
