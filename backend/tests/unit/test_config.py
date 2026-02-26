"""Unit tests for application configuration.

Tests the Settings class in app.core.config, ensuring new config fields
have correct default values.
"""
from app.core.config import Settings, get_settings


class TestSettingsDefaults:
    """Tests for Settings default values."""

    def test_job_queue_timing_defaults(self) -> None:
        """Test job queue timing config fields have correct defaults."""
        settings = Settings()
        assert settings.job_heartbeat_interval == 30
        assert settings.job_stale_threshold == 300

    def test_yahoo_retry_config_defaults(self) -> None:
        """Test Yahoo Finance retry config fields have correct defaults."""
        settings = Settings()
        assert settings.yahoo_max_retries == 3
        assert settings.yahoo_retry_delay == 1.0

    def test_data_service_defaults(self) -> None:
        """Test data service config fields have correct defaults."""
        settings = Settings()
        assert settings.default_history_days == 365

    def test_ib_broker_timeout_defaults(self) -> None:
        """Test IB broker timeout config fields have correct defaults."""
        settings = Settings()
        assert settings.ib_fill_poll_interval == 0.1
        assert settings.ib_cancel_wait_time == 2

    def test_worker_config_defaults(self) -> None:
        """Test worker config fields have correct defaults."""
        settings = Settings()
        assert settings.worker_shutdown_iterations == 30
        assert settings.worker_shutdown_sleep == 1
        assert settings.worker_sweeper_interval == 60


class TestGetSettings:
    """Tests for get_settings() function."""

    def test_get_settings_returns_settings_instance(self) -> None:
        """Test that get_settings() returns a Settings instance."""
        get_settings.cache_clear()
        settings = get_settings()
        assert isinstance(settings, Settings)

    def test_get_settings_is_cached(self) -> None:
        """Test that get_settings() returns the same cached instance."""
        get_settings.cache_clear()
        settings1 = get_settings()
        settings2 = get_settings()
        assert settings1 is settings2
