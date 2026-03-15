"""Stock price alert API endpoints.

Provides RESTful endpoints for creating, reading, updating, and soft-deleting
StockAlert records, plus event history and price data for chart rendering.

Endpoints:
  POST   /                       Create alert(s). MA fan-out creates one per period.
  GET    /                       List all non-deleted alerts with optional filters.
  GET    /{alert_id}             Get a single alert by ID.
  PATCH  /{alert_id}             Update alert config or pause state.
  DELETE /{alert_id}             Soft-delete an alert.
  GET    /{alert_id}/events      Get event history for an alert.
  GET    /{alert_id}/price-data  Get OHLCV data for chart rendering.
"""
import logging
from datetime import datetime
from datetime import timedelta
from datetime import timezone

from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from fastapi import Query
from fastapi import status
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.database import get_session_factory
from app.core.deps import get_market_data_provider
from app.core.exceptions import SymbolNotFoundError
from app.providers.base import MarketDataProviderInterface
from app.schemas.alert import AlertEventResponse
from app.schemas.alert import AlertListResponse
from app.schemas.alert import AlertPriceDataResponse
from app.schemas.alert import AlertResponse
from app.schemas.alert import CreateAlertRequest
from app.schemas.alert import UpdateAlertRequest
from app.services.alert_service import AlertService
from app.services.data_service import DataService

router = APIRouter()
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Dependency helpers
# ---------------------------------------------------------------------------


def _build_service(
    session_factory: async_sessionmaker,
    provider: MarketDataProviderInterface,
) -> AlertService:
    """Construct an AlertService from injected dependencies."""
    return AlertService(session_factory=session_factory, provider=provider)


# ---------------------------------------------------------------------------
# POST / — Create alert(s)
# ---------------------------------------------------------------------------


@router.post("/", response_model=list[AlertResponse], status_code=status.HTTP_201_CREATED)
async def create_alert(
    request: CreateAlertRequest,
    session_factory: async_sessionmaker = Depends(get_session_factory),
    provider: MarketDataProviderInterface = Depends(get_market_data_provider),
) -> list[AlertResponse]:
    """Create one or more stock price alerts.

    For moving_average alerts with multiple ma_periods, one StockAlert row is
    created per period. All other alert types create exactly one record.

    Symbol existence is validated by fetching price data from the market data
    provider. A 400 is returned for unknown symbols.

    Args:
        request: Validated alert creation payload.
        session_factory: Async session factory for DB access.
        provider: Market data provider for symbol validation.

    Returns:
        List of created AlertResponse objects (length >= 1).

    Raises:
        HTTPException 400: If the symbol does not exist.
    """
    service = _build_service(session_factory, provider)
    config = request.config.model_dump()

    try:
        alerts = await service.create_alert(
            symbol=request.symbol.upper(),
            alert_type=request.alert_type,
            config=config,
        )
    except SymbolNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Symbol not found: {request.symbol.upper()}",
        )

    return [AlertResponse.model_validate(a) for a in alerts]


# ---------------------------------------------------------------------------
# GET / — List alerts
# ---------------------------------------------------------------------------


@router.get("/", response_model=AlertListResponse)
async def list_alerts(
    status_filter: str | None = Query(default=None, alias="status"),
    alert_type: str | None = Query(default=None),
    symbol: str | None = Query(default=None),
    session_factory: async_sessionmaker = Depends(get_session_factory),
    provider: MarketDataProviderInterface = Depends(get_market_data_provider),
) -> AlertListResponse:
    """List all non-deleted alerts with optional filters.

    Supports filtering by status, alert_type, and symbol via query parameters.
    Soft-deleted alerts are excluded from results.

    Args:
        status_filter: Filter by alert status (e.g. "at_level", "at_ma").
        alert_type: Filter by type ("fibonacci" or "moving_average").
        symbol: Filter by ticker symbol (case-insensitive, normalised to uppercase).
        session_factory: Async session factory for DB access.
        provider: Market data provider (required by AlertService constructor).

    Returns:
        AlertListResponse with items and total count.
    """
    service = _build_service(session_factory, provider)

    filters: dict = {}
    if status_filter:
        filters["status"] = status_filter
    if alert_type:
        filters["alert_type"] = alert_type
    if symbol:
        filters["symbol"] = symbol.upper()

    alerts, total = await service.list_alerts(filters if filters else None)
    return AlertListResponse(
        items=[AlertResponse.model_validate(a) for a in alerts],
        total=total,
    )


# ---------------------------------------------------------------------------
# GET /{alert_id} — Get single alert
# ---------------------------------------------------------------------------


@router.get("/{alert_id}", response_model=AlertResponse)
async def get_alert(
    alert_id: int,
    session_factory: async_sessionmaker = Depends(get_session_factory),
    provider: MarketDataProviderInterface = Depends(get_market_data_provider),
) -> AlertResponse:
    """Get a single alert by ID.

    Soft-deleted alerts return 404.

    Args:
        alert_id: Primary key of the StockAlert.
        session_factory: Async session factory for DB access.
        provider: Market data provider (required by AlertService constructor).

    Returns:
        AlertResponse for the requested alert.

    Raises:
        HTTPException 404: If alert not found or has been soft-deleted.
    """
    service = _build_service(session_factory, provider)
    alert = await service.get_alert(alert_id)
    if alert is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Alert {alert_id} not found",
        )
    return AlertResponse.model_validate(alert)


# ---------------------------------------------------------------------------
# PATCH /{alert_id} — Update alert
# ---------------------------------------------------------------------------


@router.patch("/{alert_id}", response_model=AlertResponse)
async def update_alert(
    alert_id: int,
    request: UpdateAlertRequest,
    session_factory: async_sessionmaker = Depends(get_session_factory),
    provider: MarketDataProviderInterface = Depends(get_market_data_provider),
) -> AlertResponse:
    """Update an alert's configuration or pause state.

    Only fields included in the request body are applied. Soft-deleted alerts
    return 404.

    Args:
        alert_id: Primary key of the StockAlert.
        request: Partial update payload (config and/or is_paused).
        session_factory: Async session factory for DB access.
        provider: Market data provider (required by AlertService constructor).

    Returns:
        Updated AlertResponse.

    Raises:
        HTTPException 404: If alert not found or has been soft-deleted.
    """
    service = _build_service(session_factory, provider)

    updates: dict = {}
    if request.config is not None:
        updates["config"] = request.config.model_dump()
    if request.is_paused is not None:
        updates["is_paused"] = request.is_paused

    alert = await service.update_alert(alert_id, updates)
    if alert is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Alert {alert_id} not found",
        )
    return AlertResponse.model_validate(alert)


# ---------------------------------------------------------------------------
# DELETE /{alert_id} — Soft delete
# ---------------------------------------------------------------------------


@router.delete("/{alert_id}", status_code=status.HTTP_200_OK)
async def delete_alert(
    alert_id: int,
    session_factory: async_sessionmaker = Depends(get_session_factory),
    provider: MarketDataProviderInterface = Depends(get_market_data_provider),
) -> dict:
    """Soft-delete an alert.

    Sets deleted_at and deactivates the alert without removing the record.
    Returns 404 if the alert does not exist or is already deleted.

    Args:
        alert_id: Primary key of the StockAlert.
        session_factory: Async session factory for DB access.
        provider: Market data provider (required by AlertService constructor).

    Returns:
        Confirmation dict with deleted alert ID.

    Raises:
        HTTPException 404: If alert not found or already soft-deleted.
    """
    service = _build_service(session_factory, provider)
    deleted = await service.delete_alert(alert_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Alert {alert_id} not found",
        )
    return {"deleted": alert_id}


# ---------------------------------------------------------------------------
# GET /{alert_id}/events — Event history
# ---------------------------------------------------------------------------


@router.get("/{alert_id}/events", response_model=list[AlertEventResponse])
async def get_alert_events(
    alert_id: int,
    session_factory: async_sessionmaker = Depends(get_session_factory),
    provider: MarketDataProviderInterface = Depends(get_market_data_provider),
) -> list[AlertEventResponse]:
    """Get the event history for an alert, newest first.

    Returns an empty list if the alert exists but has no events.
    Returns 404 if the alert does not exist or has been soft-deleted.

    Args:
        alert_id: Primary key of the StockAlert.
        session_factory: Async session factory for DB access.
        provider: Market data provider (required by AlertService constructor).

    Returns:
        List of AlertEventResponse objects ordered by created_at descending.

    Raises:
        HTTPException 404: If alert not found or has been soft-deleted.
    """
    service = _build_service(session_factory, provider)

    # Verify alert exists and is not soft-deleted before fetching events
    alert = await service.get_alert(alert_id)
    if alert is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Alert {alert_id} not found",
        )

    events = await service.get_alert_events(alert_id)
    return [
        AlertEventResponse(
            id=e.id,
            alert_id=e.alert_id,
            event_type=e.event_type,
            previous_status=e.previous_status,
            new_status=e.new_status,
            price_at_event=float(e.price_at_event),
            details=e.details,
            created_at=e.created_at,
        )
        for e in events
    ]


# ---------------------------------------------------------------------------
# GET /{alert_id}/price-data — OHLCV data for chart rendering
# ---------------------------------------------------------------------------


@router.get("/{alert_id}/price-data", response_model=AlertPriceDataResponse)
async def get_alert_price_data(
    alert_id: int,
    days: int = Query(default=365, ge=1, le=3650),
    session_factory: async_sessionmaker = Depends(get_session_factory),
    provider: MarketDataProviderInterface = Depends(get_market_data_provider),
) -> AlertPriceDataResponse:
    """Get OHLCV price data for the symbol associated with an alert.

    Fetches daily candles going back `days` calendar days from today. The data
    is returned as a list of dicts for direct consumption by the frontend chart
    component without transformation.

    Args:
        alert_id: Primary key of the StockAlert.
        days: Number of calendar days of history to return (default 365, max 3650).
        session_factory: Async session factory for DB access.
        provider: Market data provider for fetching price data.

    Returns:
        AlertPriceDataResponse with OHLCV dicts, symbol, alert_id, and days.

    Raises:
        HTTPException 404: If alert not found or has been soft-deleted.
    """
    service = _build_service(session_factory, provider)

    alert = await service.get_alert(alert_id)
    if alert is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Alert {alert_id} not found",
        )

    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=days)

    data_service = DataService(session_factory=session_factory, provider=provider)
    price_data = await data_service.get_price_data(
        symbol=alert.symbol,
        start_date=start_date,
        end_date=end_date,
        interval="1d",
    )

    ohlcv_dicts = [
        {
            "timestamp": p.timestamp.isoformat(),
            "open": float(p.open_price),
            "high": float(p.high_price),
            "low": float(p.low_price),
            "close": float(p.close_price),
            "volume": p.volume,
        }
        for p in price_data
    ]

    return AlertPriceDataResponse(
        symbol=alert.symbol,
        alert_id=alert_id,
        data=ohlcv_dicts,
        days=days,
    )
