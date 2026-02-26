"""
Alembic migration environment with async SQLAlchemy support.
"""
import asyncio
import os
import sys
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.ext.asyncio import create_async_engine
from alembic import context

# Add the parent directory to the path so we can import our app modules
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.core.config import get_settings
from app.models.base import Base

# Import all models here to ensure they are registered with Base metadata
# This is required for autogenerate to detect all tables
try:
    # Import all model classes to register them with Base metadata
    from app.models import (
        StockPrice,
        IBOrder,
        Recommendation,
        Live20Run,
        StockList,
        ArenaSimulation,
        ArenaPosition,
        ArenaSnapshot,
    )
except ImportError:
    # Models may not exist yet during initial setup
    pass

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Get application settings
settings = get_settings()

# Set the database URL dynamically from application settings
if not config.get_main_option("sqlalchemy.url"):
    config.set_main_option("sqlalchemy.url", settings.database_url)

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Add your model's MetaData object here for 'autogenerate' support
target_metadata = Base.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    """Run migrations with the given connection."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    This uses async SQLAlchemy engine for compatibility
    with the application's async database operations.
    """
    connectable = create_async_engine(
        config.get_main_option("sqlalchemy.url"),
        poolclass=pool.NullPool,
        # Use the same connection settings as the main app
        connect_args={
            "server_settings": {
                "application_name": f"{settings.app_name}_migration",
            },
            "command_timeout": settings.database_command_timeout,
        }
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_async_migrations():
    """Wrapper to run async migrations."""
    asyncio.run(run_migrations_online())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_async_migrations()