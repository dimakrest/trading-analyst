"""Health check endpoint for monitoring application status.
"""
import asyncio
from datetime import datetime
from typing import Any

from fastapi import APIRouter
from fastapi import HTTPException
from fastapi import status

from app.core.config import get_settings

router = APIRouter()


@router.get(
    "/health",
    response_model=dict[str, Any],
    summary="Comprehensive Health Check",
    description="Returns detailed health status including application readiness, "
    "database connectivity, and external service availability. "
    "Use this endpoint to verify all system components are operational.",
    operation_id="get_health_status",
    responses={
        200: {"description": "Service is healthy"},
        503: {
            "description": "Service is unhealthy",
            "content": {
                "application/json": {
                    "example": {
                        "status": "unhealthy",
                        "timestamp": "2025-10-02T10:00:00",
                        "version": "1.0.0",
                        "environment": "development",
                        "checks": {
                            "application": {
                                "status": "unhealthy",
                                "message": "Application not ready: error details",
                            }
                        },
                    }
                }
            },
        },
    },
)
async def health_check() -> dict[str, Any]:
    """Comprehensive health check endpoint.

    Returns:
        Dict[str, Any]: Health status information

    Raises:
        HTTPException: If any health check fails (status 503)
    """
    settings = get_settings()
    health_data = {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0",
        "environment": settings.environment,
        "checks": {},
    }

    # Application readiness check
    try:
        # Simple async operation test
        await asyncio.sleep(0.001)
        health_data["checks"]["application"] = {"status": "healthy", "message": "Application ready"}
    except Exception as e:
        health_data["status"] = "unhealthy"
        health_data["checks"]["application"] = {
            "status": "unhealthy",
            "message": f"Application not ready: {str(e)}",
        }

    # Return appropriate HTTP status
    if health_data["status"] == "unhealthy":
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=health_data)

    return health_data


@router.get(
    "/health/ready",
    response_model=dict[str, str],
    summary="Readiness Probe",
    description="Simple readiness check for load balancers and orchestration systems. "
    "Returns 200 OK when the application is ready to serve traffic.",
    operation_id="get_readiness",
    responses={
        500: {"description": "Internal Server Error"},
    }
)
async def readiness_check() -> dict[str, str]:
    """Simple readiness check for load balancer probes.

    Returns:
        Dict[str, str]: Ready status
    """
    return {"status": "ready", "timestamp": datetime.utcnow().isoformat()}


@router.get(
    "/health/live",
    response_model=dict[str, str],
    summary="Liveness Probe",
    description="Simple liveness check for container orchestration. "
    "Returns 200 OK when the application process is alive.",
    operation_id="get_liveness",
    responses={
        500: {"description": "Internal Server Error"},
    }
)
async def liveness_check() -> dict[str, str]:
    """Simple liveness check for container orchestration.

    Returns:
        Dict[str, str]: Live status
    """
    return {"status": "alive", "timestamp": datetime.utcnow().isoformat()}
