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
        default=[
            "http://localhost:3000",
            "http://localhost:5173",
            "http://localhost:5174",
            "http://localhost:5177",
            "http://localhost:5232",
            "http://localhost:8000",
            "http://localhost:8093",
        ],
        description="Allowed CORS origins",
    )

    # Logging
    log_level: str = Field(default="INFO", description="Log level")

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
