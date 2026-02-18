"""Live 20 API endpoints.

Provides REST API for Live 20 mean reversion analysis, including:
- Batch symbol analysis (async queue-based processing)
- Historical results retrieval
- Run management (list, detail, delete)
"""

import logging
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.database import get_db_session, get_session_factory
from app.models.live20_run import Live20RunStatus
from app.models.recommendation import Recommendation, RecommendationSource
from app.repositories.agent_config_repository import AgentConfigRepository
from app.repositories.live20_run_repository import Live20RunRepository
from app.schemas.live20 import (
    Live20AnalyzeRequest,
    Live20AnalyzeResponse,
    Live20ResultResponse,
    Live20ResultsResponse,
    PortfolioRecommendRequest,
    PortfolioRecommendResponse,
    PortfolioRecommendItem,
)
from app.schemas.live20_run import (
    Live20RunDetailResponse,
    Live20RunListResponse,
    Live20RunSummary,
)

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post(
    "/analyze",
    response_model=Live20AnalyzeResponse,
    summary="Analyze Symbols with Live 20",
    description="Queue multiple stock symbols for Live 20 mean reversion analysis. "
    "Returns immediately with a run_id. Use GET /runs/{run_id} to check progress. "
    "Max 150 symbols per request.",
    operation_id="analyze_live20_symbols",
    responses={
        400: {"description": "Invalid request (bad symbols, too many symbols, etc.)"},
    },
)
async def analyze_symbols(
    request: Live20AnalyzeRequest,
    session_factory: async_sessionmaker[AsyncSession] = Depends(get_session_factory),
) -> Live20AnalyzeResponse:
    """Queue symbols for Live 20 mean reversion analysis.

    Creates a run with status='pending' and returns immediately.
    A background worker picks up pending runs and processes them.
    Use GET /runs/{run_id} to check progress and retrieve results.

    Args:
        request: List of symbols to analyze
        session_factory: Factory for creating database sessions

    Returns:
        Live20AnalyzeResponse with run_id and status='pending'
    """
    # Normalize symbols to uppercase and strip whitespace
    normalized_symbols = [s.upper().strip() for s in request.symbols if s.strip()]

    # Convert Pydantic models to dicts for JSON storage
    source_lists_dict = (
        [item.model_dump() for item in request.source_lists] if request.source_lists else None
    )

    # Create run with status='pending' for async processing
    async with session_factory() as session:
        # Look up agent config if provided
        agent_config = None
        if request.agent_config_id:
            config_repo = AgentConfigRepository(session)
            agent_config = await config_repo.get_by_id(request.agent_config_id)
            if not agent_config:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Agent config {request.agent_config_id} not found",
                )

        # Determine scoring algorithm: agent_config_id takes precedence
        scoring_algorithm = agent_config.scoring_algorithm if agent_config else request.scoring_algorithm

        repo = Live20RunRepository(session)
        run = await repo.create(
            input_symbols=normalized_symbols,
            symbol_count=len(normalized_symbols),
            status="pending",
            stock_list_id=request.stock_list_id,
            stock_list_name=request.stock_list_name,
            source_lists=source_lists_dict,
            scoring_algorithm=scoring_algorithm,
            agent_config_id=request.agent_config_id,
        )
        run_id = run.id
        await session.commit()

    logger.info(f"Created Live20Run {run_id} with {len(normalized_symbols)} symbols (pending)")

    # Return immediately - worker will pick up the job
    return Live20AnalyzeResponse(
        run_id=run_id,
        status="pending",
        total=len(normalized_symbols),
        message="Run queued for processing",
    )


@router.get(
    "/results",
    response_model=Live20ResultsResponse,
    summary="Get Live 20 Results",
    description="Get Live 20 analysis results with optional filtering by direction and minimum score.",
    operation_id="get_live20_results",
    responses={
        400: {"description": "Invalid direction or score parameter"},
        500: {"description": "Internal Server Error"},
    },
)
async def get_results(
    direction: Literal["LONG", "SHORT", "NO_SETUP"] | None = Query(
        None,
        description="Filter by direction: LONG, SHORT, or NO_SETUP",
    ),
    min_score: int = Query(0, ge=0, le=100, description="Minimum score filter (0-100)"),
    limit: int = Query(100, ge=1, le=500, description="Maximum results to return"),
    db: AsyncSession = Depends(get_db_session),
) -> Live20ResultsResponse:
    """Get Live 20 results with filtering.

    Returns most recent Live 20 analysis results ordered by created_at descending.
    Optionally filter by direction (LONG/SHORT/NO_SETUP) and minimum score.

    Args:
        direction: Optional filter by direction
        min_score: Minimum score filter (0-100)
        limit: Maximum results to return (1-500)
        db: Database session

    Returns:
        Live20ResultsResponse with results, total count, and direction counts
    """
    # Base query for Live 20 recommendations
    base_query = (
        select(Recommendation)
        .where(Recommendation.source == RecommendationSource.LIVE_20.value)
        .where(Recommendation.deleted_at.is_(None))
    )

    # Apply filters
    if direction:
        base_query = base_query.where(Recommendation.live20_direction == direction)
    if min_score > 0:
        base_query = base_query.where(Recommendation.confidence_score >= min_score)

    # Get most recent results ordered by created_at
    query = base_query.order_by(Recommendation.created_at.desc()).limit(limit)

    result = await db.execute(query)
    recommendations = list(result.scalars().all())

    # Get counts for all directions (unfiltered, excluding deleted)
    count_query = (
        select(
            Recommendation.live20_direction,
            func.count(Recommendation.id).label("count"),
        )
        .where(Recommendation.source == RecommendationSource.LIVE_20.value)
        .where(Recommendation.deleted_at.is_(None))
        .group_by(Recommendation.live20_direction)
    )
    count_result = await db.execute(count_query)
    counts_raw = {row.live20_direction: row.count for row in count_result}

    return Live20ResultsResponse(
        results=[Live20ResultResponse.from_recommendation(r) for r in recommendations],
        total=len(recommendations),
        counts={
            "long": counts_raw.get("LONG", 0),
            "short": counts_raw.get("SHORT", 0),
            "no_setup": counts_raw.get("NO_SETUP", 0),
        },
    )


@router.get(
    "/runs",
    response_model=Live20RunListResponse,
    summary="List Live 20 Runs",
    description="List Live 20 analysis runs with optional filtering by date, direction, or symbol. "
    "Results are paginated and ordered by created_at descending.",
    operation_id="list_live20_runs",
    responses={
        400: {"description": "Invalid filter parameters"},
    },
)
async def list_runs(
    limit: int = Query(20, ge=1, le=100, description="Max runs to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    date_from: datetime | None = Query(None, description="Filter runs created on or after this date"),
    date_to: datetime | None = Query(None, description="Filter runs created on or before this date"),
    has_direction: Literal["LONG", "SHORT", "NO_SETUP"] | None = Query(
        None, description="Filter runs that have at least one result of this direction"
    ),
    symbol: str | None = Query(None, description="Filter runs that analyzed this symbol"),
    db: AsyncSession = Depends(get_db_session),
) -> Live20RunListResponse:
    """List Live 20 analysis runs with optional filtering.

    Returns runs in reverse chronological order (newest first) with
    pagination support. Filters can be combined.

    Args:
        limit: Maximum number of runs to return (1-100)
        offset: Number of runs to skip for pagination
        date_from: Only include runs created on or after this date
        date_to: Only include runs created on or before this date
        has_direction: Only include runs with at least one result of this direction
        symbol: Only include runs that analyzed this symbol
        db: Database session

    Returns:
        Live20RunListResponse with filtered and paginated runs
    """
    repo = Live20RunRepository(db)
    runs, total = await repo.list_runs(
        limit=limit,
        offset=offset,
        date_from=date_from,
        date_to=date_to,
        has_direction=has_direction,
        symbol_search=symbol,
    )

    items = [Live20RunSummary.model_validate(r) for r in runs]
    return Live20RunListResponse(
        items=items,
        total=total,
        has_more=(offset + len(items)) < total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/runs/{run_id}",
    response_model=Live20RunDetailResponse,
    summary="Get Live 20 Run Details",
    description="Get full details of a Live 20 run including all individual analysis results. "
    "Results are ordered by confidence score descending.",
    operation_id="get_live20_run",
    responses={404: {"description": "Run not found or has been deleted"}},
)
async def get_run(
    run_id: int,
    db: AsyncSession = Depends(get_db_session),
) -> Live20RunDetailResponse:
    """Get full details of a Live 20 run including all results.

    Args:
        run_id: Primary key of the run to retrieve
        db: Database session

    Returns:
        Live20RunDetailResponse with complete run details and all results

    Raises:
        HTTPException: 404 if run not found or has been soft-deleted
    """
    repo = Live20RunRepository(db)
    run = await repo.get_by_id(run_id)

    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    recommendations = await repo.get_run_recommendations(run_id)

    return Live20RunDetailResponse(
        id=run.id,
        created_at=run.created_at,
        status=run.status,
        symbol_count=run.symbol_count,
        processed_count=run.processed_count,
        long_count=run.long_count,
        short_count=run.short_count,
        no_setup_count=run.no_setup_count,
        input_symbols=run.input_symbols,
        stock_list_id=run.stock_list_id,
        stock_list_name=run.stock_list_name,
        source_lists=run.source_lists,
        agent_config_id=run.agent_config_id,
        scoring_algorithm=run.scoring_algorithm,
        results=[Live20ResultResponse.from_recommendation(r) for r in recommendations],
        failed_symbols=run.failed_symbols or {},
    )


@router.post(
    "/runs/{run_id}/cancel",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Cancel Live 20 Run",
    description="Cancel a pending or running Live 20 run. "
    "Sets status to 'cancelled' and stops worker processing. "
    "The worker checks cancellation status between symbols and stops gracefully.",
    operation_id="cancel_live20_run",
    responses={
        404: {"description": "Run not found or already deleted"},
        400: {"description": "Run cannot be cancelled (already completed/failed/cancelled)"},
    },
)
async def cancel_run(
    run_id: int,
    db: AsyncSession = Depends(get_db_session),
) -> None:
    """Cancel a Live20 run (pending/running only).

    Sets the run status to 'cancelled' so the background worker stops processing.
    The worker checks cancellation status between symbols and stops gracefully.

    Args:
        run_id: Primary key of the run to cancel
        db: Database session

    Raises:
        HTTPException: 404 if run not found or already deleted
        HTTPException: 400 if run cannot be cancelled (already completed/failed/cancelled)
    """
    repo = Live20RunRepository(db)
    run = await repo.get_by_id(run_id)

    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    if run.status not in (Live20RunStatus.PENDING, Live20RunStatus.RUNNING):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot cancel {run.status} run. Only pending/running runs can be cancelled.",
        )

    run.status = Live20RunStatus.CANCELLED
    await db.commit()
    logger.info(f"Cancelled Live20Run {run_id}")


@router.delete(
    "/runs/{run_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete Live 20 Run",
    description="Permanently delete a completed, failed, or cancelled Live 20 run. "
    "For active runs, use POST /runs/{id}/cancel instead.",
    operation_id="delete_live20_run",
    responses={
        404: {"description": "Run not found"},
        400: {"description": "Cannot delete active run - use cancel endpoint instead"},
    },
)
async def delete_run(
    run_id: int,
    db: AsyncSession = Depends(get_db_session),
) -> None:
    """Delete a Live20 run (completed/failed/cancelled only).

    Args:
        run_id: Primary key of the run
        db: Database session

    Raises:
        HTTPException: 404 if run not found or already deleted
        HTTPException: 400 if run is pending or running
    """
    repo = Live20RunRepository(db)
    run = await repo.get_by_id(run_id)

    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    # Only allow deletion of terminal states
    if run.status in (Live20RunStatus.PENDING, Live20RunStatus.RUNNING):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot delete {run.status} run. Use POST /runs/{run_id}/cancel to stop it first.",
        )

    # Soft-delete for completed/failed/cancelled runs
    success = await repo.soft_delete(run_id)
    if not success:
        raise HTTPException(status_code=404, detail="Run not found")
    await db.commit()
    logger.info(f"Soft deleted Live20Run {run_id}")


@router.post(
    "/runs/{run_id}/recommend",
    response_model=PortfolioRecommendResponse,
    status_code=status.HTTP_200_OK,
    summary="Recommend Portfolio from Live20 Run",
    description="Generate a portfolio recommendation from a live20 run's results. "
    "Filters qualifying signals by minimum confidence score, then applies the chosen "
    "portfolio selection strategy to produce an ordered list of recommended stocks.",
    operation_id="recommend_live20_portfolio",
    responses={
        404: {"description": "Run not found"},
        400: {"description": "Invalid strategy name"},
    },
)
async def recommend_portfolio(
    run_id: int,
    request: PortfolioRecommendRequest,
    db: AsyncSession = Depends(get_db_session),
) -> PortfolioRecommendResponse:
    """Generate a portfolio recommendation from a live20 run.

    Fetches all recommendations for the run that meet the minimum score
    threshold and have a non-NO_SETUP direction, then applies the chosen
    portfolio selection strategy to rank and filter them.

    Args:
        run_id: Primary key of the live20 run
        request: Strategy parameters including min_score, strategy, and constraints
        db: Database session

    Returns:
        PortfolioRecommendResponse with ordered list of recommended stocks

    Raises:
        HTTPException: 404 if run not found or soft-deleted
        HTTPException: 400 if strategy name is not recognized
    """
    from app.services.portfolio_selector import QualifyingSignal, get_selector

    # Verify run exists (repo.get_by_id returns None for soft-deleted runs)
    repo = Live20RunRepository(db)
    run = await repo.get_by_id(run_id)
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")

    # Validate strategy name
    selector = get_selector(request.strategy)
    # get_selector falls back to 'none' on unknown names; detect explicit mismatch
    if selector.name != request.strategy:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown portfolio strategy: {request.strategy}",
        )

    # Query recommendations for this run that qualify (score >= min_score, direction != NO_SETUP)
    stmt = (
        select(Recommendation)
        .where(Recommendation.live20_run_id == run_id)
        .where(Recommendation.confidence_score >= request.min_score)
        .where(Recommendation.live20_direction != "NO_SETUP")
        .where(Recommendation.live20_direction.is_not(None))
        .order_by(Recommendation.confidence_score.desc())
    )
    if request.directions:
        stmt = stmt.where(Recommendation.live20_direction.in_(request.directions))
    result = await db.execute(stmt)
    qualifying_recs = list(result.scalars().all())

    # Build QualifyingSignal list from recommendation fields
    # Keep direction alongside each signal so we can include it in the response
    qualifying_signals: list[QualifyingSignal] = []
    direction_by_symbol: dict[str, str | None] = {}
    for rec in qualifying_recs:
        atr_pct = float(rec.live20_atr) if rec.live20_atr is not None else None
        qualifying_signals.append(
            QualifyingSignal(
                symbol=rec.stock,
                score=rec.confidence_score,
                sector=rec.live20_sector_etf,
                atr_pct=atr_pct,
            )
        )
        direction_by_symbol[rec.stock] = rec.live20_direction

    # Apply portfolio selection strategy
    # For live20 recommendations, no existing positions to account for
    selected = selector.select(
        signals=qualifying_signals,
        existing_sector_counts={},
        current_open_count=0,
        max_per_sector=request.max_per_sector,
        max_open_positions=request.max_positions,
    )

    items = [
        PortfolioRecommendItem(
            symbol=signal.symbol,
            score=signal.score,
            direction=direction_by_symbol.get(signal.symbol),
            sector=signal.sector,
            atr_pct=signal.atr_pct,
        )
        for signal in selected
    ]

    return PortfolioRecommendResponse(
        strategy=selector.name,
        strategy_description=selector.description,
        items=items,
        total_qualifying=len(qualifying_signals),
        total_selected=len(selected),
    )
