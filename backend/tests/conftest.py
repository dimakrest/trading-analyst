"""Shared pytest fixtures for testing infrastructure.

CRITICAL: Environment variables MUST be set before ANY imports.
"""
import os

# ===============================================================================
# CRITICAL: Set test environment variables FIRST, before ANY other imports!
# This ensures Settings classes pick up the test database configuration.
# ===============================================================================
if os.getenv("DOCKER_ENV") == "true":
    # Dev containers use postgres-dev service name
    TEST_DATABASE_URL = "postgresql+asyncpg://trader:localpass@postgres-dev:5432/trading_analyst_test"
else:
    # Port 5438 maps to dev container postgres port (5437 is for test)
    TEST_DATABASE_URL = "postgresql+asyncpg://trader:localpass@localhost:5438/trading_analyst_test"

# Override environment variables BEFORE importing any app code
os.environ["ENVIRONMENT"] = "test"
os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ["DATABASE_ECHO"] = "false"
os.environ["LOG_LEVEL"] = "WARNING"

# Now import everything else AFTER environment is configured
import asyncio
from collections.abc import AsyncGenerator
from collections.abc import Generator
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from app.core.config import Settings
from app.core.config import get_settings
from app.core.database import Base
from app.core.database import get_db_session
from app.core.database import get_session_factory
from app.utils.structured_logging import configure_structured_logging


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create an event loop for the test session.

    This fixture ensures that async tests run in the same event loop.
    """
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def test_settings() -> Settings:
    """Create test settings with test database configuration.

    Returns:
        Settings: Test configuration
    """
    # Override environment for tests
    os.environ["ENVIRONMENT"] = "test"
    os.environ["DATABASE_URL"] = TEST_DATABASE_URL
    os.environ["DATABASE_ECHO"] = "false"
    os.environ["LOG_LEVEL"] = "WARNING"

    settings = Settings(
        environment="test",
        database_url=TEST_DATABASE_URL,
        database_echo=False,
        log_level="WARNING",
        debug=True,
    )
    return settings


@pytest.fixture(scope="session", autouse=True)
def configure_logging(test_settings: Settings):
    """Configure structured logging for tests.

    Args:
        test_settings: Test configuration
    """
    # Configure structlog for test environment
    configure_structured_logging(log_level=test_settings.log_level)


@pytest.fixture(scope="session")
async def test_engine(test_settings: Settings):
    """Create test database engine.

    Args:
        test_settings: Test configuration

    Returns:
        AsyncEngine: Test database engine
    """
    engine = create_async_engine(
        test_settings.database_url,
        echo=test_settings.database_echo,
        pool_size=5,
        max_overflow=10,
        pool_timeout=10,  # Prevent indefinite wait for pool connections
        connect_args={
            "server_settings": {
                "application_name": f"{test_settings.app_name}_test",
            }
        },
    )

    # Drop and recreate all tables to pick up schema changes
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    # One-time cleanup at session start (safe - no concurrent tests yet)
    async with engine.begin() as conn:
        await conn.execute(text(
            "TRUNCATE TABLE arena_positions, arena_snapshots, arena_simulations, "
            "live20_runs, stock_prices, ib_orders, recommendations, stock_lists "
            "RESTART IDENTITY CASCADE"
        ))

    yield engine
    await engine.dispose()


@pytest.fixture(scope="session")
def test_session_factory(test_engine):
    """Create test session factory.

    Args:
        test_engine: Test database engine

    Returns:
        async_sessionmaker: Test session factory
    """
    return async_sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
        autocommit=False,
    )


@pytest_asyncio.fixture
async def db_connection(test_engine):
    """Per-test connection with outer transaction for rollback isolation.

    The outer transaction is rolled back after each test, undoing all changes.
    Pulled in automatically by db_session and override_get_session_factory.
    Tests using test_session_factory directly (with their own TRUNCATE fixtures)
    should NOT request this fixture to avoid AccessExclusiveLock conflicts.
    """
    async with test_engine.connect() as connection:
        transaction = await connection.begin()
        try:
            yield connection
        finally:
            await transaction.rollback()


@pytest_asyncio.fixture
async def db_session(db_connection) -> AsyncGenerator[AsyncSession, None]:
    """Per-test session bound to the rollback connection.

    join_transaction_mode="create_savepoint" means:
    - session.commit() -> RELEASE SAVEPOINT (not actual COMMIT)
    - session.rollback() -> ROLLBACK TO SAVEPOINT
    The outer transaction in db_connection rolls back everything after the test.
    """
    session = AsyncSession(
        bind=db_connection,
        expire_on_commit=False,
        autoflush=False,
        join_transaction_mode="create_savepoint",
    )
    try:
        yield session
    finally:
        await session.close()


@pytest.fixture
def rollback_session_factory(db_connection):
    """Session factory creating sessions on the rollback connection.

    Replacement for test_session_factory in tests that don't need separate DB
    connections. Sessions use join_transaction_mode="create_savepoint", so
    commits become savepoint releases (rolled back with the outer transaction).
    """
    def factory():
        return AsyncSession(
            bind=db_connection,
            expire_on_commit=False,
            autoflush=False,
            join_transaction_mode="create_savepoint",
        )
    return factory


@pytest.fixture
def override_get_settings(test_settings: Settings):
    """Override the get_settings dependency for tests.

    Args:
        test_settings: Test configuration

    Returns:
        Settings: Test settings
    """
    return test_settings


@pytest.fixture
def override_get_db_session(db_session: AsyncSession):
    """Override the get_db_session dependency for tests.

    Args:
        db_session: Test database session

    Returns:
        AsyncSession: Test database session
    """

    async def _get_test_db_session():
        yield db_session

    return _get_test_db_session


@pytest.fixture
def override_get_session_factory(db_connection):
    """Override get_session_factory to create sessions bound to rollback connection.

    This ensures that endpoint code using `async with session_factory() as session:`
    also participates in transaction rollback isolation.
    """
    def bound_session_factory():
        """Creates a session bound to the test's rollback connection."""
        return AsyncSession(
            bind=db_connection,
            expire_on_commit=False,
            autoflush=False,
            join_transaction_mode="create_savepoint",
        )

    # Double-lambda matches FastAPI DI pattern: get_session_factory() returns
    # a factory function, which is then called to create sessions.
    return lambda: bound_session_factory


@pytest.fixture
def app(override_get_settings, override_get_db_session, override_get_session_factory):
    """Create FastAPI test application with dependency overrides.

    Args:
        override_get_settings: Test settings override
        override_get_db_session: Test database session override
        override_get_session_factory: Test session factory override

    Returns:
        FastAPI: Test application instance
    """
    from app.main import app as main_app

    # Override dependencies
    main_app.dependency_overrides[get_settings] = lambda: override_get_settings
    main_app.dependency_overrides[get_db_session] = override_get_db_session
    main_app.dependency_overrides[get_session_factory] = override_get_session_factory

    yield main_app

    # Clean up overrides
    main_app.dependency_overrides.clear()


@pytest.fixture
def client(app) -> TestClient:
    """Create synchronous test client.

    Args:
        app: Test application instance

    Returns:
        TestClient: Synchronous test client
    """
    return TestClient(app)


@pytest_asyncio.fixture
async def async_client(app) -> AsyncGenerator[AsyncClient, None]:
    """Create async test client.

    Args:
        app: Test application instance

    Yields:
        AsyncClient: Async test client
    """
    async with AsyncClient(app=app, base_url="http://testserver") as client:
        yield client


# Common test data fixtures
@pytest.fixture
def sample_stock_data():
    """Sample stock data for testing.

    Returns:
        dict: Sample stock data
    """
    return {
        "symbol": "AAPL",
        "name": "Apple Inc.",
        "price": 150.0,
        "volume": 1000000,
        "market_cap": 2500000000000,
    }


# Mock fixtures for external services
@pytest.fixture
def mock_yahoo_finance():
    """Mock Yahoo Finance service for testing.

    Returns:
        AsyncMock: Mocked Yahoo Finance service
    """
    mock = AsyncMock()
    mock.get_stock_data.return_value = {
        "symbol": "AAPL",
        "price": 150.0,
        "volume": 1000000,
        "timestamp": "2024-01-01T10:00:00Z",
    }
    return mock


# Note: Test isolation uses transaction rollback (not TRUNCATE).
# Each test runs inside an outer transaction that is rolled back after the test,
# avoiding AccessExclusiveLock deadlocks from TRUNCATE operations.


# Pytest configuration
def pytest_configure(config):
    """Configure pytest with custom markers and settings.

    Args:
        config: Pytest configuration
    """
    # ENFORCE: Backend tests must run in Docker containers
    if not os.getenv("DOCKER_ENV"):
        raise RuntimeError(
            "\n\n"
            "=" * 70 + "\n"
            "ERROR: Backend tests MUST run in Docker containers\n"
            "=" * 70 + "\n"
            "Backend tests require Docker to ensure:\n"
            "  - Consistent PostgreSQL database environment\n"
            "  - Proper test isolation\n"
            "  - Reproducible test results across all developers\n"
            "\n"
            "To run tests:\n"
            "  docker-compose exec backend pytest\n"
            "\n"
            "Or start backend service and run tests:\n"
            "  docker-compose up -d backend\n"
            "  docker-compose exec backend pytest --cov=app\n"
            "\n"
            "Documentation: docs/guides/testing.md\n"
            "=" * 70 + "\n"
        )

    config.addinivalue_line("markers", "unit: mark test as a unit test")
    config.addinivalue_line("markers", "integration: mark test as an integration test")
    config.addinivalue_line("markers", "slow: mark test as slow running")
    config.addinivalue_line("markers", "database: mark test as requiring database")
    config.addinivalue_line("markers", "external: mark test as making external calls")


# Custom test utilities
class TestUtils:
    """Utility functions for tests."""

    @staticmethod
    async def create_test_stock(session: AsyncSession, **kwargs) -> dict:
        """Create a test stock record.

        Args:
            session: Database session
            **kwargs: Stock attributes

        Returns:
            dict: Created stock data
        """
        # This will be implemented when stock models are available
        pass


@pytest.fixture
def test_utils():
    """Provide test utility functions.

    Returns:
        TestUtils: Test utility class
    """
    return TestUtils
