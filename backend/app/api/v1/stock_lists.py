"""API endpoints for Stock Lists management."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.deps import get_current_user_id
from app.models.stock_list import StockList
from app.repositories.stock_list_repository import StockListRepository
from app.schemas.stock_list import (
    StockListCreate,
    StockListResponse,
    StockListsResponse,
    StockListUpdate,
)

router = APIRouter()


def _to_response(stock_list: StockList) -> StockListResponse:
    """Convert model to response schema."""
    return StockListResponse(
        id=stock_list.id,
        name=stock_list.name,
        symbols=stock_list.symbols or [],
        symbol_count=len(stock_list.symbols or []),
    )


@router.get(
    "",
    response_model=StockListsResponse,
    summary="Get Stock Lists",
    description="Get all stock lists for the current user.",
    operation_id="get_stock_lists",
)
async def get_stock_lists(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db_session),
) -> StockListsResponse:
    """Get all stock lists for the current user."""
    repo = StockListRepository(db)
    lists, total = await repo.get_by_user(user_id, limit, offset)

    has_more = (offset + len(lists)) < total

    return StockListsResponse(
        items=[_to_response(lst) for lst in lists],
        total=total,
        has_more=has_more,
    )


@router.get(
    "/{list_id}",
    response_model=StockListResponse,
    summary="Get Stock List",
    description="Get a specific stock list by ID.",
    operation_id="get_stock_list",
)
async def get_stock_list(
    list_id: int,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db_session),
) -> StockListResponse:
    """Get a specific stock list."""
    repo = StockListRepository(db)
    stock_list = await repo.get_by_id_and_user(list_id, user_id)

    if not stock_list:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Stock list {list_id} not found",
        )

    return _to_response(stock_list)


@router.post(
    "",
    response_model=StockListResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Stock List",
    description="Create a new stock list.",
    operation_id="create_stock_list",
)
async def create_stock_list(
    request: StockListCreate,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db_session),
) -> StockListResponse:
    """Create a new stock list."""
    repo = StockListRepository(db)

    # Check for duplicate name
    if await repo.name_exists(user_id, request.name):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"A list named '{request.name}' already exists",
        )

    # Normalize symbols
    symbols = [s.upper().strip() for s in request.symbols if s.strip()]
    symbols = list(dict.fromkeys(symbols))  # Remove duplicates, preserve order

    stock_list = await repo.create(
        user_id=user_id,
        name=request.name.strip(),
        symbols=symbols,
    )

    return _to_response(stock_list)


@router.put(
    "/{list_id}",
    response_model=StockListResponse,
    summary="Update Stock List",
    description="Update an existing stock list.",
    operation_id="update_stock_list",
)
async def update_stock_list(
    list_id: int,
    request: StockListUpdate,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db_session),
) -> StockListResponse:
    """Update a stock list."""
    repo = StockListRepository(db)
    stock_list = await repo.get_by_id_and_user(list_id, user_id)

    if not stock_list:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Stock list {list_id} not found",
        )

    # Update name if provided
    if request.name is not None:
        name = request.name.strip()
        if await repo.name_exists(user_id, name, exclude_id=list_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"A list named '{name}' already exists",
            )
        stock_list.name = name

    # Update symbols if provided
    if request.symbols is not None:
        symbols = [s.upper().strip() for s in request.symbols if s.strip()]
        symbols = list(dict.fromkeys(symbols))  # Remove duplicates
        stock_list.symbols = symbols

    await db.flush()
    await db.refresh(stock_list)

    return _to_response(stock_list)


@router.delete(
    "/{list_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete Stock List",
    description="Delete a stock list.",
    operation_id="delete_stock_list",
)
async def delete_stock_list(
    list_id: int,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db_session),
) -> None:
    """Delete a stock list (soft delete)."""
    repo = StockListRepository(db)
    stock_list = await repo.get_by_id_and_user(list_id, user_id)

    if not stock_list:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Stock list {list_id} not found",
        )

    stock_list.soft_delete()
    await db.flush()
