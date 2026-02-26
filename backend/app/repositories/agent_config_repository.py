"""Repository for AgentConfig CRUD operations."""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent_config import AgentConfig
from app.repositories.base import BaseRepository


class AgentConfigRepository(BaseRepository[AgentConfig]):
    """Repository for AgentConfig database operations."""

    def __init__(self, session: AsyncSession):
        super().__init__(AgentConfig, session)

    async def get_all_active(self) -> list[AgentConfig]:
        """Get all non-deleted configs, ordered by name."""
        return await self.list(
            order_by="name",
            filters={"deleted_at": None},
        )

    async def name_exists(
        self,
        name: str,
        exclude_id: int | None = None,
    ) -> bool:
        """Check if a config name already exists."""
        query = (
            select(func.count())
            .select_from(AgentConfig)
            .where(AgentConfig.name == name)
            .where(AgentConfig.deleted_at.is_(None))
        )
        if exclude_id is not None:
            query = query.where(AgentConfig.id != exclude_id)

        result = await self.session.execute(query)
        count = result.scalar() or 0
        return count > 0

    async def count_active(self) -> int:
        """Count non-deleted agent configs."""
        query = (
            select(func.count())
            .select_from(AgentConfig)
            .where(AgentConfig.deleted_at.is_(None))
        )
        result = await self.session.execute(query)
        return result.scalar() or 0
