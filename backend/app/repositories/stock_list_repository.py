"""Repository for StockList CRUD operations."""

from collections.abc import Sequence

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.stock_list import StockList
from app.repositories.base import BaseRepository


class StockListRepository(BaseRepository[StockList]):
    """Repository for StockList database operations."""

    def __init__(self, session: AsyncSession):
        super().__init__(StockList, session)

    async def get_by_user(
        self,
        user_id: int,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[Sequence[StockList], int]:
        """Get all lists for a user with pagination."""
        base_query = (
            select(StockList)
            .where(StockList.user_id == user_id)
            .where(StockList.deleted_at.is_(None))
        )

        # Count
        count_query = select(func.count()).select_from(base_query.subquery())
        count_result = await self.session.execute(count_query)
        total = count_result.scalar() or 0

        # Results
        query = base_query.order_by(StockList.name).limit(limit).offset(offset)
        result = await self.session.execute(query)
        lists = result.scalars().all()

        return lists, total

    async def get_by_id_and_user(
        self,
        list_id: int,
        user_id: int,
    ) -> StockList | None:
        """Get a specific list by ID, ensuring user ownership."""
        result = await self.session.execute(
            select(StockList)
            .where(StockList.id == list_id)
            .where(StockList.user_id == user_id)
            .where(StockList.deleted_at.is_(None))
        )
        return result.scalar_one_or_none()

    async def name_exists(
        self,
        user_id: int,
        name: str,
        exclude_id: int | None = None,
    ) -> bool:
        """Check if a list name already exists for this user."""
        query = (
            select(func.count())
            .select_from(StockList)
            .where(StockList.user_id == user_id)
            .where(StockList.name == name)
            .where(StockList.deleted_at.is_(None))
        )
        if exclude_id:
            query = query.where(StockList.id != exclude_id)

        result = await self.session.execute(query)
        count = result.scalar() or 0
        return count > 0
