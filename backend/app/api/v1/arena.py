"""Arena simulation API endpoints.

This module provides REST API endpoints for managing arena simulations,
including creation, listing, retrieval, and cancellation/deletion.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.models.arena import ArenaSimulation, SimulationStatus
from app.repositories.agent_config_repository import AgentConfigRepository
from app.schemas.arena import (
    AgentInfo,
    CreateSimulationRequest,
    PortfolioStrategyInfo,
    PositionResponse,
    SimulationDetailResponse,
    SimulationListResponse,
    SimulationResponse,
    SnapshotResponse,
)
from app.services.arena.agent_registry import list_agents

router = APIRouter()
logger = logging.getLogger(__name__)


def _build_simulation_response(simulation: ArenaSimulation) -> SimulationResponse:
    """Convert database model to response schema.

    Args:
        simulation: ArenaSimulation database model

    Returns:
        SimulationResponse ready for API response
    """
    # Extract agent config parameters (handles None and missing keys gracefully)
    agent_config = simulation.agent_config or {}
    trailing_stop_pct = agent_config.get("trailing_stop_pct")
    min_buy_score = agent_config.get("min_buy_score")
    scoring_algorithm = agent_config.get("scoring_algorithm", "cci")
    portfolio_strategy = agent_config.get("portfolio_strategy")
    max_per_sector = agent_config.get("max_per_sector")
    max_open_positions = agent_config.get("max_open_positions")

    return SimulationResponse(
        id=simulation.id,
        name=simulation.name,
        stock_list_id=simulation.stock_list_id,
        stock_list_name=simulation.stock_list_name,
        symbols=simulation.symbols,
        start_date=simulation.start_date,
        end_date=simulation.end_date,
        initial_capital=simulation.initial_capital,
        position_size=simulation.position_size,
        agent_type=simulation.agent_type,
        trailing_stop_pct=trailing_stop_pct,
        min_buy_score=min_buy_score,
        scoring_algorithm=scoring_algorithm,
        portfolio_strategy=portfolio_strategy,
        max_per_sector=max_per_sector,
        max_open_positions=max_open_positions,
        status=simulation.status,
        current_day=simulation.current_day,
        total_days=simulation.total_days,
        final_equity=simulation.final_equity,
        total_return_pct=simulation.total_return_pct,
        total_trades=simulation.total_trades,
        winning_trades=simulation.winning_trades,
        max_drawdown_pct=simulation.max_drawdown_pct,
        created_at=simulation.created_at,
    )


@router.get(
    "/agents",
    response_model=list[AgentInfo],
    status_code=status.HTTP_200_OK,
    summary="List Available Arena Agents",
    description="Get a list of all available trading agents for arena simulations.",
    operation_id="list_arena_agents",
)
async def get_agents() -> list[AgentInfo]:
    """List all available arena agents.

    Returns:
        List of agent info including type, name, and required lookback days.
    """
    agents = list_agents()
    return [
        AgentInfo(
            type=agent["type"],
            name=str(agent["name"]),
            required_lookback_days=int(agent["required_lookback_days"]),
        )
        for agent in agents
    ]


@router.get(
    "/portfolio-strategies",
    response_model=list[PortfolioStrategyInfo],
    status_code=status.HTTP_200_OK,
    summary="List Portfolio Selection Strategies",
    description="Get a list of all available portfolio selection strategies for arena simulations.",
    operation_id="list_portfolio_strategies",
)
async def list_portfolio_strategies() -> list[PortfolioStrategyInfo]:
    """List all available portfolio selection strategies.

    Returns:
        List of strategy info including name and description.
    """
    from app.services.portfolio_selector import list_selectors

    return [PortfolioStrategyInfo(**s) for s in list_selectors()]


@router.post(
    "/simulations",
    response_model=SimulationResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Create Arena Simulation",
    description="Create a new arena simulation. Returns 202 Accepted with simulation details. "
    "The simulation is created with status=PENDING and will be processed by a background worker.",
    operation_id="create_arena_simulation",
    responses={
        400: {"description": "Invalid request (validation failed)"},
    },
)
async def create_simulation(
    request: CreateSimulationRequest,
    session: AsyncSession = Depends(get_db_session),
) -> SimulationResponse:
    """Create a new arena simulation.

    The simulation is created with PENDING status. A background worker
    will pick it up, initialize the total_days, and process it.

    Args:
        request: Simulation configuration
        session: Database session

    Returns:
        SimulationResponse with simulation details

    Raises:
        HTTPException: If validation fails
    """
    # Look up agent config if provided
    if request.agent_config_id:
        config_repo = AgentConfigRepository(session)
        agent_config_obj = await config_repo.get_by_id(request.agent_config_id)
        if not agent_config_obj:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Agent config {request.agent_config_id} not found",
            )
        scoring_algorithm = agent_config_obj.scoring_algorithm
    else:
        scoring_algorithm = request.scoring_algorithm

    # Build agent_config dictionary from request parameters
    agent_config = {
        "trailing_stop_pct": request.trailing_stop_pct,
        "min_buy_score": request.min_buy_score,
        "scoring_algorithm": scoring_algorithm,
        "portfolio_strategy": request.portfolio_strategy,
        "max_per_sector": request.max_per_sector,
        "max_open_positions": request.max_open_positions,
    }
    if request.agent_config_id is not None:
        agent_config["agent_config_id"] = request.agent_config_id

    # Create simulation record
    simulation = ArenaSimulation(
        name=request.name,
        stock_list_id=request.stock_list_id,
        stock_list_name=request.stock_list_name,
        symbols=request.symbols,
        start_date=request.start_date,
        end_date=request.end_date,
        initial_capital=request.initial_capital,
        position_size=request.position_size,
        agent_type=request.agent_type,
        agent_config=agent_config,
        status=SimulationStatus.PENDING.value,
        current_day=0,
        total_days=0,  # Worker will initialize this
    )

    session.add(simulation)
    await session.commit()
    await session.refresh(simulation)

    logger.info(
        "Created arena simulation",
        extra={
            "simulation_id": simulation.id,
            "agent_type": simulation.agent_type,
            "symbols_count": len(simulation.symbols),
        },
    )

    return _build_simulation_response(simulation)


@router.get(
    "/simulations",
    response_model=SimulationListResponse,
    status_code=status.HTTP_200_OK,
    summary="List Arena Simulations",
    description="Get a list of simulations, ordered by most recent first.",
    operation_id="list_arena_simulations",
)
async def list_simulations(
    limit: int = Query(default=20, ge=1, le=100, description="Maximum results"),
    offset: int = Query(default=0, ge=0, description="Results offset"),
    session: AsyncSession = Depends(get_db_session),
) -> SimulationListResponse:
    """List arena simulations.

    Args:
        limit: Maximum number of results to return
        offset: Number of results to skip
        session: Database session

    Returns:
        Paginated list of simulation summaries, most recent first
    """
    # Count total simulations
    count_stmt = select(func.count()).select_from(ArenaSimulation)
    count_result = await session.execute(count_stmt)
    total = count_result.scalar() or 0

    stmt = (
        select(ArenaSimulation)
        .order_by(ArenaSimulation.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await session.execute(stmt)
    simulations = result.scalars().all()

    items = [_build_simulation_response(sim) for sim in simulations]
    return SimulationListResponse(
        items=items,
        total=total,
        has_more=(offset + len(items)) < total,
    )


@router.get(
    "/simulations/{simulation_id}",
    response_model=SimulationDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Arena Simulation Details",
    description="Get detailed simulation info including positions and daily snapshots.",
    operation_id="get_arena_simulation",
    responses={
        404: {"description": "Simulation not found"},
    },
)
async def get_simulation(
    simulation_id: int,
    session: AsyncSession = Depends(get_db_session),
) -> SimulationDetailResponse:
    """Get detailed simulation info.

    Args:
        simulation_id: Simulation primary key
        session: Database session

    Returns:
        SimulationDetailResponse with simulation, positions, and snapshots

    Raises:
        HTTPException: If simulation not found
    """
    stmt = select(ArenaSimulation).where(ArenaSimulation.id == simulation_id)
    result = await session.execute(stmt)
    simulation = result.scalar_one_or_none()

    if not simulation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Simulation {simulation_id} not found",
        )

    # Positions and snapshots are loaded via selectin relationship
    positions = [
        PositionResponse(
            id=pos.id,
            symbol=pos.symbol,
            status=pos.status,
            signal_date=pos.signal_date,
            entry_date=pos.entry_date,
            entry_price=pos.entry_price,
            shares=pos.shares,
            highest_price=pos.highest_price,
            current_stop=pos.current_stop,
            exit_date=pos.exit_date,
            exit_price=pos.exit_price,
            exit_reason=pos.exit_reason,
            realized_pnl=pos.realized_pnl,
            return_pct=pos.return_pct,
            agent_reasoning=pos.agent_reasoning,
            agent_score=pos.agent_score,
        )
        for pos in simulation.positions
    ]

    snapshots = [
        SnapshotResponse(
            id=snap.id,
            snapshot_date=snap.snapshot_date,
            day_number=snap.day_number,
            cash=snap.cash,
            positions_value=snap.positions_value,
            total_equity=snap.total_equity,
            daily_pnl=snap.daily_pnl,
            daily_return_pct=snap.daily_return_pct,
            cumulative_return_pct=snap.cumulative_return_pct,
            open_position_count=snap.open_position_count,
            decisions=snap.decisions,
        )
        for snap in simulation.snapshots
    ]

    return SimulationDetailResponse(
        simulation=_build_simulation_response(simulation),
        positions=positions,
        snapshots=snapshots,
    )


@router.post(
    "/simulations/{simulation_id}/cancel",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Cancel Arena Simulation",
    description="Cancel a pending, running, or paused simulation. "
    "Sets status to 'cancelled' and stops worker processing.",
    operation_id="cancel_arena_simulation",
    responses={
        404: {"description": "Simulation not found"},
        400: {"description": "Simulation cannot be cancelled (already completed/failed/cancelled)"},
    },
)
async def cancel_simulation(
    simulation_id: int,
    session: AsyncSession = Depends(get_db_session),
) -> None:
    """Cancel an Arena simulation (pending/running/paused only)."""
    stmt = select(ArenaSimulation).where(ArenaSimulation.id == simulation_id)
    result = await session.execute(stmt)
    simulation = result.scalar_one_or_none()

    if not simulation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Simulation not found",
        )

    cancellable_statuses = (
        SimulationStatus.PENDING.value,
        SimulationStatus.RUNNING.value,
        SimulationStatus.PAUSED.value,
    )
    if simulation.status not in cancellable_statuses:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot cancel {simulation.status} simulation. Only pending/running/paused simulations can be cancelled.",
        )

    simulation.status = SimulationStatus.CANCELLED.value
    await session.commit()
    logger.info(
        "Cancelled arena simulation",
        extra={"simulation_id": simulation_id},
    )


@router.delete(
    "/simulations/{simulation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete Arena Simulation",
    description="Permanently delete a completed, failed, or cancelled simulation. "
    "For active simulations, use POST /simulations/{id}/cancel instead.",
    operation_id="delete_arena_simulation",
    responses={
        404: {"description": "Simulation not found"},
        400: {"description": "Cannot delete active simulation - use cancel endpoint instead"},
    },
)
async def delete_simulation(
    simulation_id: int,
    session: AsyncSession = Depends(get_db_session),
) -> None:
    """Delete an Arena simulation (completed/failed/cancelled only).

    Args:
        simulation_id: Simulation primary key
        session: Database session

    Raises:
        HTTPException: 404 if simulation not found
        HTTPException: 400 if simulation is pending, running, or paused
    """
    stmt = select(ArenaSimulation).where(ArenaSimulation.id == simulation_id)
    result = await session.execute(stmt)
    simulation = result.scalar_one_or_none()

    if not simulation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Simulation not found",
        )

    # Only allow deletion of terminal states
    active_statuses = (SimulationStatus.PENDING.value, SimulationStatus.RUNNING.value, SimulationStatus.PAUSED.value)
    if simulation.status in active_statuses:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot delete {simulation.status} simulation. Use POST /simulations/{simulation_id}/cancel to stop it first.",
        )

    # Delete completed/cancelled/failed simulation
    await session.delete(simulation)
    await session.commit()
    logger.info(
        "Deleted arena simulation",
        extra={"simulation_id": simulation_id},
    )
