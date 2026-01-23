"""Async database configuration and session management.
"""
import logging
from collections.abc import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Create async engine with proper connection pooling
engine = create_async_engine(
    settings.database_url,
    echo=settings.database_echo,
    pool_size=settings.database_pool_size,
    max_overflow=settings.database_max_overflow,
    pool_pre_ping=settings.database_pool_pre_ping,
    pool_recycle=settings.database_pool_recycle,
    # Remove poolclass for async engines - asyncpg uses its own pool management
    connect_args={
        "server_settings": {
            "application_name": settings.app_name,
        },
        "command_timeout": settings.database_command_timeout,
    },
)

# Create async session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)

# Import Base class and all models to register them with metadata
from app.models import Base


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency to get async database session with proper error handling.

    Yields:
        AsyncSession: Database session

    Example:
        ```python
        @router.get("/")
        async def get_data(session: AsyncSession = Depends(get_db_session)):
            result = await session.execute(select(Model))
            return result.scalars().all()
        ```
    """
    session = AsyncSessionLocal()
    try:
        yield session
        await session.commit()
    except SQLAlchemyError as e:
        await session.rollback()
        logger.error(f"Database error: {e}")
        raise
    except Exception as e:
        await session.rollback()
        logger.error(f"Unexpected error: {e}")
        raise
    finally:
        await session.close()


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Dependency to get the async session factory.

    Use this when you need to create multiple sessions (e.g., for concurrent tasks).
    Each task should create its own session using:
        async with session_factory() as session:
            ...

    Returns:
        async_sessionmaker: Factory for creating AsyncSession instances

    Example:
        ```python
        @router.post("/batch")
        async def batch_operation(
            session_factory: async_sessionmaker = Depends(get_session_factory)
        ):
            async def process_item(item):
                async with session_factory() as session:
                    # Each task gets its own session
                    ...
            await asyncio.gather(*[process_item(i) for i in items])
        ```
    """
    return AsyncSessionLocal


async def check_db_health() -> dict[str, str]:
    """Check database connection health.

    Returns:
        dict: Health check result with status and details

    Raises:
        SQLAlchemyError: If database connection fails
    """
    try:
        async with AsyncSessionLocal() as session:
            # Simple query to test connection
            result = await session.execute(text("SELECT 1 as health_check"))
            health_value = result.scalar()

            if health_value == 1:
                return {
                    "status": "healthy",
                    "message": "Database connection successful",
                    "database_url": settings.database_url.split("@")[-1],  # Hide credentials
                }
            else:
                return {
                    "status": "unhealthy",
                    "message": "Database query returned unexpected result",
                }
    except SQLAlchemyError as e:
        logger.error(f"Database health check failed: {e}")
        return {"status": "unhealthy", "message": f"Database connection failed: {str(e)}"}
    except Exception as e:
        logger.error(f"Unexpected error during health check: {e}")
        return {"status": "unhealthy", "message": f"Unexpected error: {str(e)}"}


async def close_db() -> None:
    """Close database connections gracefully.

    Call this during application shutdown.
    """
    try:
        await engine.dispose()
        logger.info("Database connections closed successfully")
    except Exception as e:
        logger.error(f"Error closing database connections: {e}")
        raise
