"""Main FastAPI application with async support and middleware.
"""
import asyncio
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

from app.api.v1 import account
from app.api.v1 import agent_configs
from app.api.v1 import arena
from app.api.v1 import health
from app.api.v1 import indicators
from app.api.v1 import live20
from app.api.v1 import stock_lists
from app.api.v1 import stocks
from app.core.config import get_settings
from app.core.database import close_db
from app.core.deps import cleanup_ib_broker, cleanup_ib_data_provider
from app.core.docs import API_CONTACT
from app.core.docs import API_DESCRIPTION
from app.core.docs import API_TITLE
from app.core.docs import API_VERSION
from app.core.docs import OPENAPI_TAGS
from app.core.docs import custom_openapi_schema
from app.core.docs import get_swagger_ui_html_config
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

        # Validate IB configuration
        if settings.broker_type == "ib":
            # First, ensure IB_ACCOUNT is configured (mandatory for IB broker)
            if not settings.ib_account or settings.ib_account.strip() == "":
                error_msg = (
                    "IB_ACCOUNT is not configured. When using broker_type='ib', "
                    "you must set IB_ACCOUNT in your .env file with your Interactive Brokers account ID "
                    "(e.g., IB_ACCOUNT=DU1234567 for paper trading or IB_ACCOUNT=U1234567 for live trading)."
                )
                logger.error(error_msg)
                raise ValueError(error_msg)

            # Validate port matches account type
            is_paper_account = settings.ib_account.startswith("DU")
            is_paper_port = settings.ib_port == 4001
            is_live_port = settings.ib_port == 4002

            if is_paper_account and not is_paper_port:
                error_msg = (
                    f"Configuration mismatch: Paper account '{settings.ib_account}' "
                    f"should use port 4001, but port {settings.ib_port} is configured. "
                    "Update IB_PORT=4001 in your .env file."
                )
                logger.error(error_msg)
                raise ValueError(error_msg)

            if not is_paper_account and not is_live_port:
                error_msg = (
                    f"Configuration mismatch: Live account '{settings.ib_account}' "
                    f"should use port 4002, but port {settings.ib_port} is configured. "
                    "Update IB_PORT=4002 in your .env file."
                )
                logger.error(error_msg)
                raise ValueError(error_msg)

            logger.info(
                "IB configuration validated",
                account=settings.ib_account,
                port=settings.ib_port,
                account_type="paper" if is_paper_account else "live",
            )

        # Connect IBBroker and IBDataProvider if configured
        if settings.broker_type == "ib":
            from app.core.deps import get_ib_broker_singleton, get_ib_data_provider

            # Connect IBBroker
            try:
                broker = await get_ib_broker_singleton()
                if broker:
                    await broker.connect()
                    logger.info("IBBroker connected successfully on startup")
            except Exception as e:
                logger.error(f"Failed to connect IBBroker on startup: {e}")
                # Don't fail startup - let it try to connect later

            # Connect IBDataProvider
            try:
                data_provider = await get_ib_data_provider()
                if data_provider and not data_provider._connected:
                    await data_provider.connect()
                    logger.info("IBDataProvider connected successfully on startup")
            except Exception as e:
                logger.error(f"Failed to connect IBDataProvider on startup: {e}")
                # Don't fail startup - let it try to connect later

        # Initialize job queue workers
        # Workers poll for pending jobs and process them with heartbeat monitoring
        from app.core.database import get_session_factory
        from app.models.arena import ArenaSimulation
        from app.models.live20_run import Live20Run
        from app.services.arena import ArenaWorker
        from app.services.job_queue_service import JobQueueService
        from app.services.live20_worker import Live20Worker

        session_factory = get_session_factory()

        # Create queue service for Live20 jobs
        # Use worker_type for more descriptive worker IDs in logs (e.g., 'live20-a1b2c3d4')
        live20_queue = JobQueueService(
            session_factory, Live20Run, worker_type="live20"
        )

        # Create queue service for Arena simulation jobs
        arena_queue = JobQueueService(
            session_factory, ArenaSimulation, worker_type="arena"
        )

        # STARTUP RECOVERY: Reset any stranded 'running' jobs to 'pending'
        # Since this is a local-first single-instance app, any 'running' jobs
        # at startup are definitely orphaned from the previous process.
        # This provides immediate recovery (0-5 seconds) vs. waiting for
        # the sweeper (5 minutes).
        try:
            live20_reset = await live20_queue.reset_stranded_jobs()
            if live20_reset:
                logger.info(
                    f"Startup recovery: reset {live20_reset} Live20 runs for immediate resume"
                )
            arena_reset = await arena_queue.reset_stranded_jobs()
            if arena_reset:
                logger.info(
                    f"Startup recovery: reset {arena_reset} Arena simulations for immediate resume"
                )
        except Exception as e:
            logger.error(f"Startup recovery failed: {e}")
            # Don't fail startup - sweeper will catch these eventually

        # Create and start workers
        # All workers use default poll_interval of 5.0 seconds
        live20_worker = Live20Worker(session_factory, live20_queue)
        arena_worker = ArenaWorker(session_factory, arena_queue)

        # Start worker loops as background tasks
        live20_worker_task = asyncio.create_task(live20_worker.start())
        arena_worker_task = asyncio.create_task(arena_worker.start())

        logger.info("Application initialized successfully, workers started")

        yield

        # Shutdown workers gracefully
        logger.info("Stopping job queue workers...")
        await live20_worker.stop()
        await arena_worker.stop()

        # Cancel worker tasks
        live20_worker_task.cancel()
        arena_worker_task.cancel()
        try:
            await live20_worker_task
        except asyncio.CancelledError:
            pass
        try:
            await arena_worker_task
        except asyncio.CancelledError:
            pass
        logger.info("Job queue workers stopped")

    finally:
        # Shutdown
        logger.info("Shutting down Trading Analyst API")
        await cleanup_ib_broker()
        await cleanup_ib_data_provider()
        await close_db()
        logger.info("Application shutdown complete")


def create_app() -> FastAPI:
    """Create and configure FastAPI application.

    Returns:
        FastAPI: Configured application instance
    """
    settings = get_settings()

    app = FastAPI(
        title=API_TITLE,
        description=API_DESCRIPTION,
        version=API_VERSION,
        contact=API_CONTACT,
        openapi_tags=OPENAPI_TAGS,
        docs_url="/docs" if settings.is_development else None,
        redoc_url="/redoc" if settings.is_development else None,
        openapi_url="/openapi.json" if settings.is_development else None,
        debug=settings.debug,
        lifespan=lifespan,
        swagger_ui_parameters=get_swagger_ui_html_config()["swagger_ui_parameters"]
        if settings.is_development
        else None,
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

    app.include_router(account.router, prefix=settings.api_v1_prefix, tags=["account"])

    app.include_router(stocks.router, prefix=f"{settings.api_v1_prefix}/stocks", tags=["stocks"])

    app.include_router(
        indicators.router, prefix=f"{settings.api_v1_prefix}/stocks", tags=["indicators"]
    )


    app.include_router(
        live20.router, prefix=f"{settings.api_v1_prefix}/live-20", tags=["live-20"]
    )

    app.include_router(
        stock_lists.router,
        prefix=f"{settings.api_v1_prefix}/stock-lists",
        tags=["stock-lists"],
    )

    app.include_router(
        agent_configs.router,
        prefix=f"{settings.api_v1_prefix}/agent-configs",
        tags=["agent-configs"],
    )

    app.include_router(
        arena.router,
        prefix=f"{settings.api_v1_prefix}/arena",
        tags=["arena"],
    )

    # Set custom OpenAPI schema with enhanced documentation
    if settings.is_development:
        app.openapi = lambda: custom_openapi_schema(app)

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
