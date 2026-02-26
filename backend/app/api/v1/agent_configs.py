"""API endpoints for Agent Configuration management."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.models.agent_config import AgentConfig
from app.repositories.agent_config_repository import AgentConfigRepository
from app.schemas.agent_config import (
    AgentConfigCreate,
    AgentConfigListResponse,
    AgentConfigResponse,
    AgentConfigUpdate,
)

router = APIRouter()


def _to_response(config: AgentConfig) -> AgentConfigResponse:
    """Convert model to response schema."""
    return AgentConfigResponse(
        id=config.id,
        name=config.name,
        agent_type=config.agent_type,
        scoring_algorithm=config.scoring_algorithm,
        volume_score=config.volume_score,
        candle_pattern_score=config.candle_pattern_score,
        cci_score=config.cci_score,
        ma20_distance_score=config.ma20_distance_score,
    )


@router.get(
    "",
    response_model=AgentConfigListResponse,
    summary="Get Agent Configurations",
    description="Get all agent configurations.",
    operation_id="get_agent_configs",
)
async def get_agent_configs(
    db: AsyncSession = Depends(get_db_session),
) -> AgentConfigListResponse:
    """Get all agent configurations."""
    repo = AgentConfigRepository(db)
    configs = await repo.get_all_active()

    return AgentConfigListResponse(
        items=[_to_response(config) for config in configs],
        total=len(configs),
    )


@router.get(
    "/{config_id}",
    response_model=AgentConfigResponse,
    summary="Get Agent Configuration",
    description="Get a specific agent configuration by ID.",
    operation_id="get_agent_config",
)
async def get_agent_config(
    config_id: int,
    db: AsyncSession = Depends(get_db_session),
) -> AgentConfigResponse:
    """Get a specific agent configuration."""
    repo = AgentConfigRepository(db)
    config = await repo.get_by_id(config_id)

    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent configuration {config_id} not found",
        )

    return _to_response(config)


@router.post(
    "",
    response_model=AgentConfigResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Agent Configuration",
    description="Create a new agent configuration.",
    operation_id="create_agent_config",
)
async def create_agent_config(
    request: AgentConfigCreate,
    db: AsyncSession = Depends(get_db_session),
) -> AgentConfigResponse:
    """Create a new agent configuration."""
    repo = AgentConfigRepository(db)

    # Check for duplicate name
    if await repo.name_exists(request.name):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"An agent configuration named '{request.name}' already exists",
        )

    config = await repo.create(
        name=request.name.strip(),
        agent_type=request.agent_type,
        scoring_algorithm=request.scoring_algorithm,
        volume_score=request.volume_score,
        candle_pattern_score=request.candle_pattern_score,
        cci_score=request.cci_score,
        ma20_distance_score=request.ma20_distance_score,
    )

    return _to_response(config)


@router.put(
    "/{config_id}",
    response_model=AgentConfigResponse,
    summary="Update Agent Configuration",
    description="Update an existing agent configuration.",
    operation_id="update_agent_config",
)
async def update_agent_config(
    config_id: int,
    request: AgentConfigUpdate,
    db: AsyncSession = Depends(get_db_session),
) -> AgentConfigResponse:
    """Update an agent configuration."""
    repo = AgentConfigRepository(db)
    config = await repo.get_by_id(config_id)

    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent configuration {config_id} not found",
        )

    # Update name if provided
    if request.name is not None:
        name = request.name.strip()
        if await repo.name_exists(name, exclude_id=config_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"An agent configuration named '{name}' already exists",
            )
        config.name = name

    # Update scoring_algorithm if provided
    if request.scoring_algorithm is not None:
        config.scoring_algorithm = request.scoring_algorithm

    # Validate and update signal score weights (must sum to 100)
    new_volume_score = (
        request.volume_score if request.volume_score is not None else config.volume_score
    )
    new_candle_pattern_score = (
        request.candle_pattern_score
        if request.candle_pattern_score is not None
        else config.candle_pattern_score
    )
    new_cci_score = request.cci_score if request.cci_score is not None else config.cci_score
    new_ma20_distance_score = (
        request.ma20_distance_score
        if request.ma20_distance_score is not None
        else config.ma20_distance_score
    )
    score_total = (
        new_volume_score
        + new_candle_pattern_score
        + new_cci_score
        + new_ma20_distance_score
    )
    if score_total != 100:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Signal scores must sum to 100 "
                f"(got {score_total}: volume={new_volume_score}, "
                f"candle={new_candle_pattern_score}, cci={new_cci_score}, "
                f"ma20={new_ma20_distance_score})"
            ),
        )

    config.volume_score = new_volume_score
    config.candle_pattern_score = new_candle_pattern_score
    config.cci_score = new_cci_score
    config.ma20_distance_score = new_ma20_distance_score

    await db.commit()
    await db.refresh(config)

    return _to_response(config)


@router.delete(
    "/{config_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete Agent Configuration",
    description="Delete an agent configuration (soft delete). Cannot delete the last remaining config.",
    operation_id="delete_agent_config",
)
async def delete_agent_config(
    config_id: int,
    db: AsyncSession = Depends(get_db_session),
) -> None:
    """Delete an agent configuration (soft delete)."""
    repo = AgentConfigRepository(db)
    config = await repo.get_by_id(config_id)

    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent configuration {config_id} not found",
        )

    # Prevent deleting the last remaining config
    active_count = await repo.count_active()
    if active_count <= 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete the last remaining agent configuration",
        )

    config.soft_delete()
    await db.commit()
