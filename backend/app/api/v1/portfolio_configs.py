"""API endpoints for Portfolio Configuration management."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.models.portfolio_config import PortfolioConfig
from app.repositories.base import DuplicateError
from app.repositories.portfolio_config_repository import PortfolioConfigRepository
from app.schemas.portfolio_config import (
    PortfolioConfigCreate,
    PortfolioConfigListResponse,
    PortfolioConfigResponse,
    PortfolioConfigUpdate,
)

router = APIRouter()


def _to_response(config: PortfolioConfig) -> PortfolioConfigResponse:
    """Convert model to response schema."""
    return PortfolioConfigResponse(
        id=config.id,
        name=config.name,
        portfolio_strategy=config.portfolio_strategy,
        position_size=config.position_size,
        min_buy_score=config.min_buy_score,
        trailing_stop_pct=config.trailing_stop_pct,
        max_per_sector=config.max_per_sector,
        max_open_positions=config.max_open_positions,
    )


@router.get(
    "",
    response_model=PortfolioConfigListResponse,
    summary="Get Portfolio Configurations",
    description="Get all portfolio configurations.",
    operation_id="get_portfolio_configs",
)
async def get_portfolio_configs(
    db: AsyncSession = Depends(get_db_session),
) -> PortfolioConfigListResponse:
    """Get all portfolio configurations."""
    repo = PortfolioConfigRepository(db)
    configs = await repo.get_all_active()

    return PortfolioConfigListResponse(
        items=[_to_response(config) for config in configs],
        total=len(configs),
    )


@router.get(
    "/{config_id}",
    response_model=PortfolioConfigResponse,
    summary="Get Portfolio Configuration",
    description="Get a specific portfolio configuration by ID.",
    operation_id="get_portfolio_config",
)
async def get_portfolio_config(
    config_id: int,
    db: AsyncSession = Depends(get_db_session),
) -> PortfolioConfigResponse:
    """Get a specific portfolio configuration."""
    repo = PortfolioConfigRepository(db)
    config = await repo.get_by_id(config_id)

    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Portfolio configuration {config_id} not found",
        )

    return _to_response(config)


@router.post(
    "",
    response_model=PortfolioConfigResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Portfolio Configuration",
    description="Create a new portfolio configuration.",
    operation_id="create_portfolio_config",
)
async def create_portfolio_config(
    request: PortfolioConfigCreate,
    db: AsyncSession = Depends(get_db_session),
) -> PortfolioConfigResponse:
    """Create a new portfolio configuration."""
    repo = PortfolioConfigRepository(db)
    name = request.name.strip()
    if not name:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Setup name cannot be empty",
        )

    if await repo.name_exists(name):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"A portfolio configuration named '{name}' already exists",
        )

    try:
        config = await repo.create(
            name=name,
            portfolio_strategy=request.portfolio_strategy,
            position_size=request.position_size,
            min_buy_score=request.min_buy_score,
            trailing_stop_pct=request.trailing_stop_pct,
            max_per_sector=(
                None if request.portfolio_strategy == "none" else request.max_per_sector
            ),
            max_open_positions=(
                None if request.portfolio_strategy == "none" else request.max_open_positions
            ),
        )
    except DuplicateError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"A portfolio configuration named '{name}' already exists",
        ) from None
    try:
        await db.commit()
        await db.refresh(config)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"A portfolio configuration named '{name}' already exists",
        ) from None

    return _to_response(config)


@router.put(
    "/{config_id}",
    response_model=PortfolioConfigResponse,
    summary="Update Portfolio Configuration",
    description="Update an existing portfolio configuration.",
    operation_id="update_portfolio_config",
)
async def update_portfolio_config(
    config_id: int,
    request: PortfolioConfigUpdate,
    db: AsyncSession = Depends(get_db_session),
) -> PortfolioConfigResponse:
    """Update a portfolio configuration."""
    repo = PortfolioConfigRepository(db)
    config = await repo.get_by_id(config_id)

    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Portfolio configuration {config_id} not found",
        )

    if request.name is not None:
        name = request.name.strip()
        if not name:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Setup name cannot be empty",
            )
        if await repo.name_exists(name, exclude_id=config_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"A portfolio configuration named '{name}' already exists",
            )
        config.name = name

    if request.portfolio_strategy is not None:
        config.portfolio_strategy = request.portfolio_strategy

    if request.position_size is not None:
        config.position_size = request.position_size

    if request.min_buy_score is not None:
        config.min_buy_score = request.min_buy_score

    if request.trailing_stop_pct is not None:
        config.trailing_stop_pct = request.trailing_stop_pct

    if "max_per_sector" in request.model_fields_set:
        config.max_per_sector = request.max_per_sector

    if "max_open_positions" in request.model_fields_set:
        config.max_open_positions = request.max_open_positions

    # For "none", caps are semantically irrelevant and should be cleared.
    if config.portfolio_strategy == "none":
        config.max_per_sector = None
        config.max_open_positions = None

    try:
        await db.commit()
        await db.refresh(config)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"A portfolio configuration named '{config.name}' already exists",
        ) from None

    return _to_response(config)


@router.delete(
    "/{config_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete Portfolio Configuration",
    description="Delete a portfolio configuration (soft delete).",
    operation_id="delete_portfolio_config",
)
async def delete_portfolio_config(
    config_id: int,
    db: AsyncSession = Depends(get_db_session),
) -> None:
    """Delete a portfolio configuration (soft delete)."""
    repo = PortfolioConfigRepository(db)
    config = await repo.get_by_id(config_id)

    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Portfolio configuration {config_id} not found",
        )

    config.soft_delete()
    await db.commit()
