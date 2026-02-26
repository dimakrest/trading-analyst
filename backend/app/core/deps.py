"""Dependency injection for FastAPI endpoints.

This module provides dependency functions for common resources like database sessions,
configuration settings, and other shared components.
"""
from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends
from fastapi import HTTPException
from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.config import get_settings
from app.core.database import get_db_session
from app.utils.validation import is_valid_symbol
from app.utils.validation import normalize_symbol

# Type aliases for cleaner dependency injection
DatabaseSession = Annotated[AsyncSession, Depends(get_db_session)]
AppSettings = Annotated[Settings, Depends(get_settings)]


async def get_database_session() -> AsyncGenerator[AsyncSession, None]:
    """Get database session dependency for FastAPI endpoints.

    This is an alias for the main database session dependency.
    Use this in your FastAPI route handlers.

    Yields:
        AsyncSession: Database session

    Example:
        ```python
        @router.get("/items/")
        async def get_items(db: DatabaseSession):
            # Use db session here
            pass
        ```
    """
    async for session in get_db_session():
        yield session


async def get_app_settings() -> Settings:
    """Get application settings dependency.

    Returns:
        Settings: Application configuration settings

    Example:
        ```python
        @router.get("/info/")
        async def get_app_info(settings: AppSettings):
            return {"app_name": settings.app_name}
        ```
    """
    return get_settings()


async def get_validated_symbol(symbol: str) -> str:
    """Validate and normalize stock symbol.

    FastAPI dependency that validates symbol format and normalizes it.
    Use this in route handlers to eliminate duplicate validation code.

    Args:
        symbol: Raw symbol from URL path

    Returns:
        Normalized symbol (uppercase, trimmed)

    Raises:
        HTTPException: 400 if symbol format is invalid

    Example:
        ```python
        @router.get("/{symbol}/analysis")
        async def get_analysis(
            symbol: str = Depends(get_validated_symbol),
        ):
            # symbol is already validated and normalized
            pass
        ```
    """
    symbol = normalize_symbol(symbol)
    if not is_valid_symbol(symbol):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid symbol format: {symbol}",
        )
    return symbol
