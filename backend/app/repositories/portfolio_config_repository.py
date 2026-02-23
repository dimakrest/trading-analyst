"""Repository for PortfolioConfig CRUD operations."""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.portfolio_config import PortfolioConfig
from app.repositories.base import BaseRepository


class PortfolioConfigRepository(BaseRepository[PortfolioConfig]):
    """Repository for PortfolioConfig database operations."""

    def __init__(self, session: AsyncSession):
        super().__init__(PortfolioConfig, session)

    async def get_all_active(self) -> list[PortfolioConfig]:
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
            .select_from(PortfolioConfig)
            .where(PortfolioConfig.name == name)
            .where(PortfolioConfig.deleted_at.is_(None))
        )
        if exclude_id is not None:
            query = query.where(PortfolioConfig.id != exclude_id)

        result = await self.session.execute(query)
        count = result.scalar() or 0
        return count > 0
