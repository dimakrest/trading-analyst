"""Repository for Live20Run database operations.

Provides data access layer for Live20Run model, including operations
to create runs, list with filtering, and soft-delete functionality.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Sequence

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.live20_run import Live20Run
from app.models.recommendation import Recommendation

logger = logging.getLogger(__name__)


class Live20RunRepository:
    """Repository for Live20Run CRUD operations.

    Handles database access for Live 20 analysis runs, providing
    efficient querying with filtering and pagination support.
    """

    def __init__(self, session: AsyncSession):
        """Initialize repository with database session.

        Args:
            session: Async database session for database operations
        """
        self.session = session
        self.logger = logger

    async def create(
        self,
        input_symbols: list[str],
        symbol_count: int,
        long_count: int = 0,
        short_count: int = 0,
        no_setup_count: int = 0,
        status: str = "pending",
        stock_list_id: int | None = None,
        stock_list_name: str | None = None,
        source_lists: list[dict] | None = None,
    ) -> Live20Run:
        """Create a new Live20Run.

        Args:
            input_symbols: List of symbols analyzed in this run
            symbol_count: Total number of symbols
            long_count: Number of LONG signals (default 0 for pending runs)
            short_count: Number of SHORT signals (default 0 for pending runs)
            no_setup_count: Number of NO_SETUP signals (default 0 for pending runs)
            status: Run status (default 'pending' for queue-based processing)
            stock_list_id: ID of stock list used as source, if any
            stock_list_name: Name of stock list at time of analysis, if any
            source_lists: Array of source lists when multiple lists combined, if any

        Returns:
            Created Live20Run instance
        """
        run = Live20Run(
            input_symbols=input_symbols,
            symbol_count=symbol_count,
            long_count=long_count,
            short_count=short_count,
            no_setup_count=no_setup_count,
            status=status,
            stock_list_id=stock_list_id,
            stock_list_name=stock_list_name,
            source_lists=source_lists,
        )
        self.session.add(run)
        await self.session.flush()
        await self.session.refresh(run)

        self.logger.info(
            f"Created Live20Run {run.id}: {symbol_count} symbols "
            f"(LONG={long_count}, SHORT={short_count}, NO_SETUP={no_setup_count})"
        )
        return run

    async def get_by_id(self, run_id: int) -> Live20Run | None:
        """Get a run by ID, excluding soft-deleted.

        Args:
            run_id: Primary key of the run

        Returns:
            Live20Run instance or None if not found or soft-deleted
        """
        query = select(Live20Run).where(
            Live20Run.id == run_id,
            Live20Run.deleted_at.is_(None),
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def list_runs(
        self,
        limit: int = 20,
        offset: int = 0,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        has_direction: str | None = None,
        symbol_search: str | None = None,
    ) -> tuple[Sequence[Live20Run], int]:
        """List runs with filters, returns (runs, total_count).

        Args:
            limit: Maximum number of runs to return
            offset: Number of runs to skip for pagination
            date_from: Filter runs created on or after this date
            date_to: Filter runs created on or before this date
            has_direction: Filter runs with at least one result of this direction (LONG/SHORT/NO_SETUP)
            symbol_search: Filter runs that analyzed this symbol

        Returns:
            Tuple of (list of runs, total count matching filters)
        """
        base_query = select(Live20Run).where(Live20Run.deleted_at.is_(None))

        # Apply filters
        if date_from:
            base_query = base_query.where(Live20Run.created_at >= date_from)
        if date_to:
            base_query = base_query.where(Live20Run.created_at <= date_to)
        if has_direction == "LONG":
            base_query = base_query.where(Live20Run.long_count > 0)
        elif has_direction == "SHORT":
            base_query = base_query.where(Live20Run.short_count > 0)
        elif has_direction == "NO_SETUP":
            base_query = base_query.where(Live20Run.no_setup_count > 0)

        # Symbol search using PostgreSQL JSONB containment operator
        if symbol_search:
            # Use @> operator to check if input_symbols array contains the search symbol
            search_json = json.dumps([symbol_search.upper()])
            base_query = base_query.where(
                text("CAST(input_symbols AS JSONB) @> CAST(:search_json AS JSONB)").bindparams(
                    search_json=search_json
                )
            )

        # Get total count
        count_query = select(func.count()).select_from(base_query.subquery())
        total = await self.session.execute(count_query)
        total_count = total.scalar() or 0

        # Get paginated results
        query = base_query.order_by(Live20Run.created_at.desc()).limit(limit).offset(offset)
        result = await self.session.execute(query)
        runs = result.scalars().all()

        return runs, total_count

    async def soft_delete(self, run_id: int) -> bool:
        """Soft-delete a run by setting deleted_at timestamp.

        Args:
            run_id: Primary key of the run to delete

        Returns:
            True if run was found and deleted, False if not found
        """
        run = await self.get_by_id(run_id)
        if not run:
            return False

        run.deleted_at = datetime.now(timezone.utc)
        self.logger.info(f"Soft-deleted Live20Run {run_id}")
        return True

    async def get_run_recommendations(self, run_id: int) -> Sequence[Recommendation]:
        """Get all recommendations for a run, ordered by confidence score.

        Args:
            run_id: Primary key of the run

        Returns:
            List of recommendations ordered by confidence_score descending
        """
        query = (
            select(Recommendation)
            .where(
                Recommendation.live20_run_id == run_id,
                Recommendation.deleted_at.is_(None),
            )
            .order_by(Recommendation.confidence_score.desc())
        )
        result = await self.session.execute(query)
        return result.scalars().all()
