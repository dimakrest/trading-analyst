"""Tests for DataService with provider abstraction and caching.

Tests cover:
- Symbol validation via provider
- Price data fetching with cache-first architecture
- Integration with providers (Yahoo, Mock)
- Cache orchestration with market-aware freshness checking
- Error handling for provider failures
- Integration with StockPriceRepository
- Concurrent operations and rate limiting
- Edge cases and error scenarios
- batch_prefetch_sectors() for bulk sector pre-population
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions import (
    APIError,
    SymbolNotFoundError,
)
from app.providers.base import SymbolInfo
from app.providers.mock import MockMarketDataProvider
from app.services.data_service import DataService, DataServiceConfig


class _MockSessionContext:
    """Async context manager that yields a mock session."""

    def __init__(self, session):
        self.session = session

    async def __aenter__(self):
        return self.session

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return False


def _create_mock_session_factory(mock_session):
    """Create a mock session factory that returns mock session contexts.

    Args:
        mock_session: The mock session to yield from the context manager.

    Returns:
        A callable that returns async context managers yielding mock_session.
    """
    def factory():
        return _MockSessionContext(mock_session)
    return factory


class TestDataServiceConfig:
    """Test DataService configuration."""

    def test_default_config(self):
        """Test default configuration values."""
        config = DataServiceConfig()

        assert config.max_retries == 3
        assert config.retry_delay == 1.0
        assert config.request_timeout == 30.0
        assert config.validate_data is True
        assert config.default_interval == "1d"
        assert config.max_history_years == 10

    def test_custom_config(self):
        """Test custom configuration values."""
        config = DataServiceConfig(
            max_retries=5,
            retry_delay=2.0,
            request_timeout=60.0,
            validate_data=False,
            default_interval="1h",
            max_history_years=5,
        )

        assert config.max_retries == 5
        assert config.retry_delay == 2.0
        assert config.request_timeout == 60.0
        assert config.validate_data is False
        assert config.default_interval == "1h"
        assert config.max_history_years == 5


class TestDataService:
    """Test DataService operations with mock provider."""

    @pytest.fixture
    def mock_session(self):
        """Create mock database session."""
        return AsyncMock()

    @pytest.fixture
    def mock_provider(self):
        """Create mock provider."""
        provider = AsyncMock(spec=MockMarketDataProvider)
        provider.provider_name = "mock"
        provider.supported_intervals = ["1m", "5m", "1h", "1d"]
        return provider

    @pytest.fixture
    def mock_session_factory(self, mock_session):
        """Create mock session factory."""
        return _create_mock_session_factory(mock_session)

    @pytest.fixture
    def data_service(self, mock_session_factory, mock_provider):
        """Create DataService instance with mock dependencies."""
        config = DataServiceConfig(max_retries=1)  # Fast tests
        return DataService(
            session_factory=mock_session_factory,
            provider=mock_provider,
            config=config,
        )

    async def test_init(self, mock_session_factory, mock_provider):
        """Test DataService initialization."""
        config = DataServiceConfig()
        service = DataService(
            session_factory=mock_session_factory,
            provider=mock_provider,
            config=config,
        )

        assert service._session_factory == mock_session_factory
        assert service.config == config
        assert service.provider == mock_provider

    async def test_init_default_config(self, mock_session_factory):
        """Test DataService initialization with default config."""
        service = DataService(session_factory=mock_session_factory)

        assert service._session_factory == mock_session_factory
        assert isinstance(service.config, DataServiceConfig)
        assert service.config.max_retries == 3
        # Provider should default to Yahoo
        assert service.provider.provider_name == "yahoo_finance"

    async def test_get_symbol_info_success(self, data_service, mock_provider):
        """Test successful symbol info retrieval."""
        # Setup mock provider response
        mock_provider.get_symbol_info.return_value = SymbolInfo(
            symbol="AAPL",
            name="Apple Inc.",
            currency="USD",
            exchange="NASDAQ",
            market_cap=3000000000000.0,
            sector="Technology",
            industry="Consumer Electronics",
        )

        # Test symbol info retrieval
        result = await data_service.get_symbol_info("AAPL")

        # Verify result (converted to dict by DataService)
        assert result["symbol"] == "AAPL"
        assert result["name"] == "Apple Inc."
        assert result["currency"] == "USD"
        assert result["exchange"] == "NASDAQ"

        # Verify provider was called
        mock_provider.get_symbol_info.assert_called_once_with("AAPL")

    async def test_get_symbol_info_not_found(self, data_service, mock_provider):
        """Test symbol info retrieval with invalid symbol."""
        # Setup mock to raise SymbolNotFoundError
        mock_provider.get_symbol_info.side_effect = SymbolNotFoundError(
            "Symbol 'INVALID' not found"
        )

        # Test symbol info retrieval
        with pytest.raises(SymbolNotFoundError) as exc_info:
            await data_service.get_symbol_info("INVALID")

        assert "Symbol 'INVALID' not found" in str(exc_info.value)

    async def test_get_symbol_info_api_error(self, data_service, mock_provider):
        """Test symbol info retrieval with API error."""
        # Setup mock to raise APIError
        mock_provider.get_symbol_info.side_effect = APIError("API Error")

        # Test symbol info retrieval
        with pytest.raises(APIError) as exc_info:
            await data_service.get_symbol_info("AAPL")

        assert "API Error" in str(exc_info.value)

    # Note: Cache behavior tests have been moved to integration tests
    # (test_cache_integration.py) since they test implementation details
    # that are better validated with real database sessions

    async def test_service_constants(self, data_service):
        """Test DataService constants."""
        # Test valid intervals
        assert "1d" in data_service.VALID_INTERVALS
        assert "1h" in data_service.VALID_INTERVALS
        assert "5m" in data_service.VALID_INTERVALS
        assert "invalid" not in data_service.VALID_INTERVALS

        # Test intraday intervals
        assert "1m" in data_service.INTRADAY_INTERVALS
        assert "1h" in data_service.INTRADAY_INTERVALS
        assert "1d" not in data_service.INTRADAY_INTERVALS

    async def test_persistence_without_session_factory_fails(self):
        """Test that persistence operations fail gracefully without session factory."""
        # Create service without session factory
        config = DataServiceConfig(max_retries=1, validate_data=True)
        service = DataService(session_factory=None, config=config)

        # Try to use persistence operation - should fail with clear error
        with pytest.raises(RuntimeError, match="Session factory required"):
            await service.get_price_data("AAPL")

    async def test_api_operations_work_without_session_factory(self):
        """Test that API-only operations work without session factory."""
        # Create service without session factory (uses real Yahoo provider)
        config = DataServiceConfig(max_retries=1, validate_data=True)
        mock_provider = AsyncMock(spec=MockMarketDataProvider)
        mock_provider.get_symbol_info.return_value = SymbolInfo(
            symbol="AAPL",
            name="Apple Inc.",
            currency="USD",
            exchange="NASDAQ",
        )

        service = DataService(session_factory=None, provider=mock_provider, config=config)

        # API operations should work fine
        result = await service.get_symbol_info("AAPL")
        assert result["symbol"] == "AAPL"


class TestDataServiceErrorHandling:
    """Test error handling in DataService."""

    @pytest.fixture
    def mock_session(self):
        """Create mock database session."""
        return AsyncMock()

    @pytest.fixture
    def mock_provider(self):
        """Create mock provider."""
        provider = AsyncMock(spec=MockMarketDataProvider)
        provider.provider_name = "mock"
        return provider

    @pytest.fixture
    def mock_session_factory(self, mock_session):
        """Create mock session factory."""
        return _create_mock_session_factory(mock_session)

    @pytest.fixture
    def data_service(self, mock_session_factory, mock_provider):
        """Create DataService with minimal retries for testing."""
        config = DataServiceConfig(max_retries=2, retry_delay=0.1)
        return DataService(
            session_factory=mock_session_factory,
            provider=mock_provider,
            config=config,
        )


class TestDataServiceAdditionalCoverage:
    """Additional tests for coverage."""

    @pytest.fixture
    def mock_session(self):
        """Create mock database session."""
        return AsyncMock()

    @pytest.fixture
    def mock_provider(self):
        """Create mock provider."""
        provider = AsyncMock(spec=MockMarketDataProvider)
        provider.provider_name = "mock"
        return provider

    @pytest.fixture
    def mock_session_factory(self, mock_session):
        """Create mock session factory."""
        return _create_mock_session_factory(mock_session)

    @pytest.fixture
    def data_service(self, mock_session_factory, mock_provider):
        """Create DataService instance."""
        config = DataServiceConfig()
        return DataService(
            session_factory=mock_session_factory,
            provider=mock_provider,
            config=config,
        )


@pytest.mark.integration
class TestDataServiceIntegration:
    """Integration tests for DataService with real providers.

    These tests verify real provider integration.
    Tests are skipped by default to avoid external dependencies in CI/CD.

    To run: pytest -m integration
    """

    @pytest.fixture
    def real_data_service(self):
        """Create DataService for API testing.

        Note: No database session factory - testing API-only operations.
        """
        config = DataServiceConfig(max_retries=1, validate_data=True)
        return DataService(session_factory=None, config=config)

    @pytest.mark.skip(reason="Requires internet access and valid Yahoo Finance API")
    async def test_real_symbol_info_retrieval(self, real_data_service):
        """Test symbol info retrieval with real Yahoo Finance API."""
        # Test with well-known symbol
        result = await real_data_service.get_symbol_info("AAPL")

        assert result["symbol"] == "AAPL"
        assert result["name"] is not None
        assert result["currency"] == "USD"


# ---------------------------------------------------------------------------
# Helpers for batch_prefetch_sectors tests
# ---------------------------------------------------------------------------


def _make_db_row(symbol: str, sector: str | None):
    """Create a simple namespace object that mimics a SQLAlchemy Row with
    .symbol and .sector attributes, as returned by session.execute().all()."""
    row = MagicMock()
    row.symbol = symbol
    row.sector = sector
    return row


def _make_execute_result(rows):
    """Return a MagicMock whose .all() returns *rows* and .scalar_one_or_none() returns None.

    The .scalar_one_or_none() default of None models a DB cache miss inside
    get_sector_etf(), which uses scalar_one_or_none() to check stock_sectors.
    Tests that need a cache hit must override scalar_one_or_none() explicitly.
    """
    result = MagicMock()
    result.all.return_value = rows
    result.scalar_one_or_none.return_value = None
    return result


class _MockTaskSessionContext:
    """Async context manager returned by _session_factory() for task sessions.

    Wraps a dedicated AsyncMock so each factory call can return an independent
    session, allowing the test to assert on per-session calls.
    """

    def __init__(self, session):
        self._session = session

    async def __aenter__(self):
        return self._session

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return False


@pytest.mark.unit
class TestBatchPrefetchSectors:
    """Unit tests for DataService.batch_prefetch_sectors().

    All tests mock the DB session and the provider — no real I/O occurs.
    """

    # ------------------------------------------------------------------
    # Fixtures
    # ------------------------------------------------------------------

    @pytest.fixture
    def mock_provider(self):
        """Mock market-data provider (no real Yahoo calls)."""
        provider = AsyncMock(spec=MockMarketDataProvider)
        provider.provider_name = "mock"
        return provider

    @pytest.fixture
    def task_session(self):
        """Dedicated AsyncMock that simulates a per-task DB session.

        execute() returns a result where scalar_one_or_none() is None so that
        get_sector_etf() takes the cache-miss path and calls the provider.
        """
        session = AsyncMock()
        session.execute = AsyncMock(return_value=_make_execute_result([]))
        session.commit = AsyncMock()
        return session

    @pytest.fixture
    def mock_session_factory(self, task_session):
        """Session factory that always returns the same task_session context."""
        def factory():
            return _MockTaskSessionContext(task_session)
        return factory

    @pytest.fixture
    def data_service(self, mock_session_factory, mock_provider):
        """DataService wired with mock factory and provider."""
        return DataService(
            session_factory=mock_session_factory,
            provider=mock_provider,
            config=DataServiceConfig(max_retries=1),
        )

    # ------------------------------------------------------------------
    # Tests
    # ------------------------------------------------------------------

    async def test_batch_prefetch_sectors_empty_list(self, data_service):
        """Empty input returns {} without touching the DB or provider."""
        # Arrange
        caller_session = AsyncMock()

        # Act
        result = await data_service.batch_prefetch_sectors([], caller_session)

        # Assert
        assert result == {}
        caller_session.execute.assert_not_called()

    async def test_batch_prefetch_sectors_all_cached(self, data_service, mock_provider):
        """All symbols already in DB — provider is never called."""
        # Arrange
        symbols = ["AAPL", "MSFT"]
        caller_session = AsyncMock()
        caller_session.execute = AsyncMock(return_value=_make_execute_result([
            _make_db_row("AAPL", "Technology"),
            _make_db_row("MSFT", "Technology"),
        ]))

        # Act
        result = await data_service.batch_prefetch_sectors(symbols, caller_session)

        # Assert — provider never touched
        mock_provider.get_symbol_info.assert_not_called()
        # Only the initial read, no second bulk read
        assert caller_session.execute.call_count == 1
        assert result == {"AAPL": "Technology", "MSFT": "Technology"}

    async def test_batch_prefetch_sectors_all_missing(
        self, data_service, mock_provider, task_session
    ):
        """No symbols in DB — get_sector_etf called for all via own sessions."""
        # Arrange
        symbols = ["AAPL", "MSFT"]
        caller_session = AsyncMock()
        # First execute call (initial read): nothing cached
        # Second execute call (bulk re-read): returns freshly inserted data
        caller_session.execute = AsyncMock(side_effect=[
            _make_execute_result([]),  # initial read — nothing cached
            _make_execute_result([    # bulk re-read after fetch
                _make_db_row("AAPL", "Technology"),
                _make_db_row("MSFT", "Technology"),
            ]),
        ])

        mock_provider.get_symbol_info.return_value = SymbolInfo(
            symbol="AAPL",
            name="Apple Inc.",
            currency="USD",
            exchange="NASDAQ",
            sector="Technology",
            industry="Consumer Electronics",
        )

        # Act
        result = await data_service.batch_prefetch_sectors(symbols, caller_session)

        # Assert — provider called once per symbol (both were missing)
        assert mock_provider.get_symbol_info.call_count == 2
        assert result == {"AAPL": "Technology", "MSFT": "Technology"}
        # Caller session used for initial + bulk re-read
        assert caller_session.execute.call_count == 2

    async def test_batch_prefetch_sectors_mixed(
        self, data_service, mock_provider, task_session
    ):
        """Some symbols cached, some missing — Yahoo called only for missing."""
        # Arrange
        symbols = ["AAPL", "MSFT", "GOOGL"]
        caller_session = AsyncMock()
        caller_session.execute = AsyncMock(side_effect=[
            _make_execute_result([
                _make_db_row("AAPL", "Technology"),  # already cached
            ]),
            _make_execute_result([                   # bulk re-read
                _make_db_row("AAPL", "Technology"),
                _make_db_row("MSFT", "Technology"),
                _make_db_row("GOOGL", "Communication Services"),
            ]),
        ])

        mock_provider.get_symbol_info.side_effect = [
            SymbolInfo(
                symbol="MSFT",
                name="Microsoft Corporation",
                currency="USD",
                exchange="NASDAQ",
                sector="Technology",
                industry="Software",
            ),
            SymbolInfo(
                symbol="GOOGL",
                name="Alphabet Inc.",
                currency="USD",
                exchange="NASDAQ",
                sector="Communication Services",
                industry="Internet Content & Information",
            ),
        ]

        # Act
        result = await data_service.batch_prefetch_sectors(symbols, caller_session)

        # Assert — provider called only for the two missing symbols
        assert mock_provider.get_symbol_info.call_count == 2
        assert result["AAPL"] == "Technology"
        assert result["MSFT"] == "Technology"
        assert result["GOOGL"] == "Communication Services"

    async def test_batch_prefetch_sectors_partial_failure(
        self, data_service, mock_provider, task_session
    ):
        """One Yahoo call raises — others succeed; no exception propagated."""
        # Arrange
        symbols = ["AAPL", "BADFOO"]
        caller_session = AsyncMock()
        caller_session.execute = AsyncMock(side_effect=[
            _make_execute_result([]),  # initial read — nothing cached
            _make_execute_result([    # bulk re-read — only AAPL succeeded
                _make_db_row("AAPL", "Technology"),
            ]),
        ])

        mock_provider.get_symbol_info.side_effect = [
            SymbolInfo(
                symbol="AAPL",
                name="Apple Inc.",
                currency="USD",
                exchange="NASDAQ",
                sector="Technology",
                industry="Consumer Electronics",
            ),
            Exception("Yahoo API timeout"),
        ]

        # Act — must not raise
        result = await data_service.batch_prefetch_sectors(symbols, caller_session)

        # Assert
        assert result["AAPL"] == "Technology"
        assert result["BADFOO"] is None

    async def test_batch_prefetch_sectors_uses_independent_sessions(
        self, mock_provider
    ):
        """Each concurrent fetch opens its own session via _session_factory.

        The caller's session must not be used for the per-symbol fetches.
        """
        # Arrange
        symbols = ["AAPL", "MSFT"]
        caller_session = AsyncMock()
        caller_session.execute = AsyncMock(side_effect=[
            _make_execute_result([]),  # initial read — nothing cached
            _make_execute_result([    # bulk re-read
                _make_db_row("AAPL", "Technology"),
                _make_db_row("MSFT", "Technology"),
            ]),
        ])

        # Track every session created by the factory
        created_sessions = []

        def session_factory():
            task_sess = AsyncMock()
            task_sess.execute = AsyncMock(return_value=_make_execute_result([]))
            task_sess.commit = AsyncMock()
            created_sessions.append(task_sess)
            return _MockTaskSessionContext(task_sess)

        mock_provider.get_symbol_info.return_value = SymbolInfo(
            symbol="AAPL",
            name="Apple Inc.",
            currency="USD",
            exchange="NASDAQ",
            sector="Technology",
            industry="Consumer Electronics",
        )

        service = DataService(
            session_factory=session_factory,
            provider=mock_provider,
            config=DataServiceConfig(max_retries=1),
        )

        # Act
        await service.batch_prefetch_sectors(symbols, caller_session)

        # Assert — factory called once per missing symbol (2 independent sessions)
        assert len(created_sessions) == 2
        # Each task session was committed independently
        for sess in created_sessions:
            sess.commit.assert_called_once()
        # Caller's session was never committed (it's the caller's responsibility)
        caller_session.commit.assert_not_called()
