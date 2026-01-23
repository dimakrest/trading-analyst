"""Setup isolated test database with schema.

This script creates a fresh test database and initializes it with the required schema.
It should be run before executing tests to ensure a clean testing environment.
"""
import asyncio
import sys
from pathlib import Path

from sqlalchemy.ext.asyncio import create_async_engine

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.database import Base


async def setup_test_db() -> None:
    """Create and initialize test database."""
    print("Setting up test database...")

    # Connect to postgres database to create test database
    admin_engine = create_async_engine(
        "postgresql+asyncpg://trader:localpass@postgres:5432/postgres",
        isolation_level="AUTOCOMMIT",
        echo=False,
    )

    try:
        async with admin_engine.connect() as conn:
            # Drop existing test database if it exists
            print("Dropping existing test database (if exists)...")
            from sqlalchemy import text
            await conn.execute(
                text(
                    "SELECT pg_terminate_backend(pid) "
                    "FROM pg_stat_activity "
                    "WHERE datname = 'trading_analyst_test' AND pid <> pg_backend_pid()"
                )
            )
            await conn.execute(text("DROP DATABASE IF EXISTS trading_analyst_test"))

            # Create fresh test database
            print("Creating test database...")
            await conn.execute(text("CREATE DATABASE trading_analyst_test"))

        print("Test database created successfully")
    finally:
        await admin_engine.dispose()

    # Connect to test database and create schema
    test_engine = create_async_engine(
        "postgresql+asyncpg://trader:localpass@postgres:5432/trading_analyst_test",
        echo=False,
    )

    try:
        async with test_engine.begin() as conn:
            print("Creating database schema...")
            await conn.run_sync(Base.metadata.create_all)
        print("Database schema created successfully")
    finally:
        await test_engine.dispose()

    print("Test database setup complete!")


if __name__ == "__main__":
    try:
        asyncio.run(setup_test_db())
        sys.exit(0)
    except Exception as e:
        print(f"Error setting up test database: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)