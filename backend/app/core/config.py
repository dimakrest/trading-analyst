"""Configuration management using Pydantic v2 settings.
"""
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings
from pydantic_settings import SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with environment variable support."""

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=False, extra="ignore"
    )

    # Application
    app_name: str = Field(default="Trading Analyst API", description="Application name")
    debug: bool = Field(default=False, description="Debug mode")
    environment: str = Field(
        default="development", description="Environment (development, production)"
    )

    # Database
    database_url: str = Field(
        default="postgresql+asyncpg://trader:localpass@localhost:5433/trading_analyst",
        description="Async database URL",
    )
    database_echo: bool = Field(default=False, description="Echo SQL statements")
    database_pool_size: int = Field(default=5, description="Database connection pool size")
    database_max_overflow: int = Field(
        default=10, description="Database connection pool max overflow"
    )
    database_pool_pre_ping: bool = Field(default=True, description="Enable pool pre-ping")
    database_pool_recycle: int = Field(default=3600, description="Pool recycle time in seconds")
    database_connect_timeout: int = Field(default=30, description="Database connection timeout")
    database_command_timeout: int = Field(default=60, description="Database command timeout")

    # Test Database (for testing environment)
    test_database_url: str | None = Field(
        default=None, description="Test database URL (if different from main database)"
    )

    # API
    api_v1_prefix: str = Field(default="/api/v1", description="API v1 prefix")
    cors_origins: list[str] = Field(
        default=["http://localhost:3000", "http://localhost:5173", "http://localhost:5174", "http://localhost:5177", "http://localhost:5232", "http://localhost:8000", "http://localhost:8093"],
        description="Allowed CORS origins",
    )

    # Logging
    log_level: str = Field(default="INFO", description="Log level")

    # Broker Configuration
    broker_type: str = Field(
        default="mock",
        description="Broker type: 'mock' for testing, 'ib' for Interactive Brokers"
    )
    ib_host: str = Field(default="127.0.0.1", description="Interactive Brokers TWS/Gateway host")
    ib_port: int = Field(default=7497, description="Interactive Brokers TWS/Gateway port (7497 for TWS, 4002 for Gateway)")
    ib_client_id: int = Field(default=1, description="Interactive Brokers client ID for broker/trading")
    ib_data_client_id: int | None = Field(default=None, description="Interactive Brokers client ID for data provider (required when using IB data provider)")
    ib_account: str | None = Field(default=None, description="Interactive Brokers account ID")
    ib_connection_timeout: int = Field(
        default=30,
        description="Timeout in seconds for IB connection attempts"
    )
    ib_order_timeout: int = Field(
        default=60,
        description="Timeout in seconds waiting for order fills"
    )

    # Execution Guardrails
    max_order_value: float = Field(
        default=1000.0,
        description="Maximum order value in dollars per trade"
    )
    account_balance: float = Field(
        default=2000.0,
        description="Simulated account balance for position size validation"
    )
    max_daily_trades: int = Field(
        default=3,
        description="Maximum number of trades allowed per day (PDT protection)"
    )

    live20_batch_size: int = Field(
        default=10, description="Number of symbols to process concurrently in Live20 analysis"
    )

    # Market Data Provider Configuration
    market_data_provider: str = Field(
        default="yahoo",
        description="Market data provider: 'yahoo', 'ib', 'mock'"
    )

    # Job Queue Timing
    job_heartbeat_interval: int = Field(
        default=30,
        description="Job heartbeat update interval in seconds"
    )
    job_stale_threshold: int = Field(
        default=300,
        description="Job considered stale after this many seconds without heartbeat"
    )

    # Yahoo Finance Retry Configuration
    yahoo_max_retries: int = Field(
        default=3,
        description="Maximum retry attempts for Yahoo Finance API calls"
    )
    yahoo_retry_delay: float = Field(
        default=1.0,
        description="Initial delay between retries in seconds (uses exponential backoff)"
    )

    # Data Service Defaults
    default_history_days: int = Field(
        default=365,
        description="Default number of days of historical data to fetch"
    )

    # IB Broker Timeouts
    ib_fill_poll_interval: float = Field(
        default=0.1,
        description="Polling interval when waiting for IB order fills in seconds"
    )
    ib_cancel_wait_time: int = Field(
        default=2,
        description="Time to wait after cancelling IB orders in seconds"
    )

    # Worker Configuration
    worker_shutdown_iterations: int = Field(
        default=30,
        description="Maximum iterations to wait for graceful worker shutdown"
    )
    worker_shutdown_sleep: int = Field(
        default=1,
        description="Sleep duration between shutdown check iterations in seconds"
    )
    worker_sweeper_interval: int = Field(
        default=60,
        description="Interval for sweeper to check for stale jobs in seconds"
    )

    @property
    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.environment.lower() == "development"

    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.environment.lower() == "production"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance.

    Returns:
        Settings: Application settings
    """
    return Settings()
