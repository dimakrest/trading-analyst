"""Main FastAPI application with async support and middleware.
"""
import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi import Request
from fastapi import status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.api.v1 import health
from app.core.config import get_settings
from app.core.database import close_db
from app.utils.structured_logging import configure_structured_logging
from app.utils.structured_logging import get_logger

# Configure structured logging using centralized configuration
configure_structured_logging(log_level="INFO")  # Will be overridden by Settings in production
logger = get_logger(__name__)

# Initialize rate limiter
# Disable rate limiting in test environment to avoid test failures
ENVIRONMENT = os.getenv("ENVIRONMENT")
if ENVIRONMENT == "test":
    # In test environment, disable rate limiting entirely
    limiter = Limiter(key_func=get_remote_address, enabled=False)
else:
    limiter = Limiter(key_func=get_remote_address)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan management.

    Handles startup and shutdown events for the FastAPI application.
    """
    settings = get_settings()

    # Startup
    logger.info("Starting Trading Analyst API", environment=settings.environment)

    try:
        # NOTE: Database schema is managed by Alembic migrations.
        # Run migrations with: alembic upgrade head

        logger.info("Application initialized successfully")

        yield

    finally:
        # Shutdown
        logger.info("Shutting down Trading Analyst API")
        await close_db()
        logger.info("Application shutdown complete")


def create_app() -> FastAPI:
    """Create and configure FastAPI application.

    Returns:
        FastAPI: Configured application instance
    """
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        description="Trading Analyst API",
        version="1.0.0",
        docs_url="/docs" if settings.is_development else None,
        redoc_url="/redoc" if settings.is_development else None,
        openapi_url="/openapi.json" if settings.is_development else None,
        debug=settings.debug,
        lifespan=lifespan,
    )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["*"],
    )

    # Add rate limiter
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    # Global exception handler
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        """Global exception handler for unhandled exceptions.

        Args:
            request: The incoming request
            exc: The exception that occurred

        Returns:
            JSONResponse: Error response
        """
        logger.error(
            "Unhandled exception occurred",
            exc_info=exc,
            path=str(request.url),
            method=request.method,
        )

        if settings.is_development:
            # In development, include more error details
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={
                    "error": "Internal Server Error",
                    "detail": str(exc),
                    "type": type(exc).__name__,
                },
            )
        else:
            # In production, return generic error message
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={
                    "error": "Internal Server Error",
                    "detail": "An unexpected error occurred",
                },
            )

    # Include routers
    app.include_router(health.router, prefix=settings.api_v1_prefix, tags=["health"])

    return app


# Create application instance
app = create_app()


@app.get("/", include_in_schema=False)
async def root() -> dict[str, str]:
    """Root endpoint redirect.

    Returns:
        dict: Welcome message with links
    """
    settings = get_settings()
    return {
        "message": "Trading Analyst API",
        "version": "1.0.0",
        "docs": f"{settings.api_v1_prefix}/docs" if settings.is_development else "disabled",
        "health": f"{settings.api_v1_prefix}/health",
    }


if __name__ == "__main__":
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.is_development,
        log_level=settings.log_level.lower(),
    )
