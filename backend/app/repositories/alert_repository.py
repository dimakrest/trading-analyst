"""Repository for StockAlert and AlertEvent database operations."""
import logging
from datetime import datetime
from datetime import timezone

from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.alert import AlertEvent
from app.models.alert import StockAlert
from app.repositories.base import BaseRepository

logger = logging.getLogger(__name__)


class AlertRepository(BaseRepository[StockAlert]):
    """Repository for StockAlert CRUD operations.

    Extends BaseRepository with alert-specific query methods for active alert
    monitoring and event persistence.
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialize with AsyncSession."""
        super().__init__(StockAlert, session)

    async def list_active_unpaused(self) -> list[StockAlert]:
        """Get all active, non-paused, non-deleted alerts.

        Returns:
            List of StockAlert instances that are active, not paused, and not
            soft-deleted.
        """
        query = (
            select(StockAlert)
            .where(
                StockAlert.is_active.is_(True),
                StockAlert.is_paused.is_(False),
                StockAlert.deleted_at.is_(None),
            )
            .order_by(StockAlert.id)
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def update_state(self, alert_id: int, new_state: dict) -> StockAlert | None:
        """Update status and computed_state on an alert.

        Args:
            alert_id: Primary key of the alert.
            new_state: Dict containing at minimum "status" and "computed_state" keys.

        Returns:
            Updated StockAlert, or None if not found.
        """
        entity = await self.get_by_id(alert_id)
        if entity is None:
            logger.warning(f"StockAlert id={alert_id} not found for state update")
            return None

        entity.status = new_state["status"]
        entity.computed_state = new_state.get("computed_state")
        if hasattr(entity, "updated_at"):
            entity.updated_at = datetime.now(timezone.utc)

        await self.session.flush()
        await self.session.refresh(entity)
        return entity

    async def update_last_triggered(self, alert_id: int) -> None:
        """Update last_triggered_at to now.

        Args:
            alert_id: Primary key of the alert.
        """
        entity = await self.get_by_id(alert_id)
        if entity is None:
            logger.warning(f"StockAlert id={alert_id} not found for last_triggered update")
            return

        entity.last_triggered_at = datetime.now(timezone.utc)
        if hasattr(entity, "updated_at"):
            entity.updated_at = datetime.now(timezone.utc)
        await self.session.flush()

    async def create_event(self, alert_id: int, event_data: dict) -> AlertEvent:
        """Create an AlertEvent record.

        Args:
            alert_id: ID of the parent StockAlert.
            event_data: Dict with keys: event_type, previous_status, new_status,
                price_at_event, details.

        Returns:
            Created AlertEvent instance.
        """
        event = AlertEvent(
            alert_id=alert_id,
            event_type=event_data["event_type"],
            previous_status=event_data.get("previous_status"),
            new_status=event_data["new_status"],
            price_at_event=event_data["price_at_event"],
            details=event_data.get("details"),
        )
        self.session.add(event)
        await self.session.flush()
        await self.session.refresh(event)
        return event

    async def get_events_for_alert(self, alert_id: int) -> list[AlertEvent]:
        """Get events for an alert ordered by created_at descending.

        Args:
            alert_id: Primary key of the alert.

        Returns:
            List of AlertEvent instances for this alert, newest first.
        """
        query = (
            select(AlertEvent)
            .where(AlertEvent.alert_id == alert_id)
            .order_by(AlertEvent.created_at.desc())
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def list_alerts(self, filters: dict | None = None) -> list[StockAlert]:
        """List alerts with optional filters, excluding soft-deleted.

        Supported filter keys: status, alert_type, symbol.

        Args:
            filters: Optional dict of field name -> value to filter by.

        Returns:
            List of matching StockAlert instances.
        """
        query = select(StockAlert).where(StockAlert.deleted_at.is_(None))

        if filters:
            if "status" in filters:
                query = query.where(StockAlert.status == filters["status"])
            if "alert_type" in filters:
                query = query.where(StockAlert.alert_type == filters["alert_type"])
            if "symbol" in filters:
                query = query.where(StockAlert.symbol == filters["symbol"])

        query = query.order_by(StockAlert.id)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def count_alerts(self, filters: dict | None = None) -> int:
        """Count alerts matching filters, excluding soft-deleted.

        Args:
            filters: Optional dict of field name -> value to filter by.

        Returns:
            Integer count of matching alerts.
        """
        query = (
            select(func.count())
            .select_from(StockAlert)
            .where(StockAlert.deleted_at.is_(None))
        )

        if filters:
            if "status" in filters:
                query = query.where(StockAlert.status == filters["status"])
            if "alert_type" in filters:
                query = query.where(StockAlert.alert_type == filters["alert_type"])
            if "symbol" in filters:
                query = query.where(StockAlert.symbol == filters["symbol"])

        result = await self.session.execute(query)
        return result.scalar_one()
