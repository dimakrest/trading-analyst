"""Schemas for Stock List API."""

from pydantic import Field

from app.schemas.base import StrictBaseModel


class StockListCreate(StrictBaseModel):
    """Request to create a new stock list."""

    name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Name for the list"
    )
    symbols: list[str] = Field(
        default_factory=list,
        max_length=150,
        description="Initial list of stock symbols"
    )


class StockListUpdate(StrictBaseModel):
    """Request to update a stock list."""

    name: str | None = Field(
        None,
        min_length=1,
        max_length=100,
        description="New name for the list"
    )
    symbols: list[str] | None = Field(
        None,
        max_length=150,
        description="New list of stock symbols"
    )


class StockListResponse(StrictBaseModel):
    """Response containing a stock list."""

    id: int
    name: str
    symbols: list[str]
    symbol_count: int = Field(description="Number of symbols in list")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "id": 1,
                    "name": "Tech Stocks",
                    "symbols": ["AAPL", "MSFT", "GOOGL", "AMZN", "META"],
                    "symbol_count": 5
                }
            ]
        }
    }


class StockListsResponse(StrictBaseModel):
    """Paginated response containing stock lists."""

    items: list[StockListResponse]
    total: int
    has_more: bool

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "items": [
                        {
                            "id": 1,
                            "name": "Tech Stocks",
                            "symbols": ["AAPL", "MSFT", "GOOGL", "AMZN", "META"],
                            "symbol_count": 5
                        },
                        {
                            "id": 2,
                            "name": "Energy Sector",
                            "symbols": ["XOM", "CVX", "COP"],
                            "symbol_count": 3
                        }
                    ],
                    "total": 2,
                    "has_more": False
                }
            ]
        }
    }
