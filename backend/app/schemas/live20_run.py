"""Pydantic schemas for Live20Run API.

Defines request and response schemas for Live 20 run management endpoints,
including list views, detail views, and delete operations.
"""

from datetime import datetime

from pydantic import Field

from app.schemas.base import StrictBaseModel
from app.schemas.live20 import Live20ResultResponse, SourceListItem


class Live20RunSummary(StrictBaseModel):
    """Summary of a Live 20 run for list view.

    Provides high-level statistics about a single Live 20 analysis run
    without including the full recommendation details.
    """

    id: int
    created_at: datetime
    status: str
    symbol_count: int
    processed_count: int
    long_count: int
    short_count: int
    no_setup_count: int
    stock_list_id: int | None = None
    stock_list_name: str | None = None
    source_lists: list[SourceListItem] | None = Field(
        None,
        description="Array of source lists when multiple lists combined",
    )
    agent_config_id: int | None = None
    scoring_algorithm: str | None = None
    failed_count: int = Field(
        default=0, description="Number of symbols that failed analysis"
    )

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "examples": [
                {
                    "id": 1,
                    "created_at": "2025-01-22T10:30:00",
                    "status": "completed",
                    "symbol_count": 50,
                    "processed_count": 48,
                    "long_count": 12,
                    "short_count": 8,
                    "no_setup_count": 28,
                    "stock_list_id": 1,
                    "stock_list_name": "S&P 500 Top 50",
                    "source_lists": None,
                    "failed_count": 2
                }
            ]
        }
    }

    @classmethod
    def model_validate(
        cls,
        obj: "Live20RunSummary | object",
        *,
        strict: bool | None = None,
        from_attributes: bool | None = None,
        context: dict | None = None,
    ) -> "Live20RunSummary":
        """Override to calculate failed_count from failed_symbols dict.

        Args:
            obj: ORM object or dict to validate
            strict: Enable strict validation mode
            from_attributes: Allow validation from object attributes
            context: Additional context for validation

        Returns:
            Validated Live20RunSummary instance with calculated failed_count
        """
        # Calculate failed_count from failed_symbols dict
        failed_count = 0
        if hasattr(obj, "failed_symbols") and obj.failed_symbols:
            failed_count = len(obj.failed_symbols)

        # Create instance with all fields
        return cls(
            id=obj.id,
            created_at=obj.created_at,
            status=obj.status,
            symbol_count=obj.symbol_count,
            processed_count=obj.processed_count,
            long_count=obj.long_count,
            short_count=obj.short_count,
            no_setup_count=obj.no_setup_count,
            stock_list_id=getattr(obj, "stock_list_id", None),
            stock_list_name=getattr(obj, "stock_list_name", None),
            source_lists=getattr(obj, "source_lists", None),
            agent_config_id=getattr(obj, "agent_config_id", None),
            scoring_algorithm=getattr(obj, "scoring_algorithm", None),
            failed_count=failed_count,
        )


class Live20RunListResponse(StrictBaseModel):
    """Response for listing Live 20 runs with pagination.

    Includes pagination metadata to support efficient loading of large
    run histories.
    """

    items: list[Live20RunSummary]
    total: int = Field(..., description="Total number of runs matching filters")
    has_more: bool = Field(..., description="Whether there are more runs to fetch")
    limit: int = Field(..., description="Maximum runs returned in this response")
    offset: int = Field(..., description="Number of runs skipped")


class Live20RunDetailResponse(StrictBaseModel):
    """Full details of a Live 20 run including all recommendations.

    Provides complete information about a run, including the input symbols
    and all individual recommendation results.
    """

    id: int
    created_at: datetime
    status: str
    symbol_count: int
    processed_count: int
    long_count: int
    short_count: int
    no_setup_count: int
    input_symbols: list[str]
    stock_list_id: int | None = None
    stock_list_name: str | None = None
    source_lists: list[SourceListItem] | None = Field(
        None,
        description="Array of source lists when multiple lists combined",
    )
    agent_config_id: int | None = None
    scoring_algorithm: str | None = None
    results: list[Live20ResultResponse]
    failed_symbols: dict[str, str] = Field(
        default_factory=dict,
        description="Dict of failed symbols with error messages: {symbol: error_message}",
    )

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "examples": [
                {
                    "id": 1,
                    "created_at": "2025-01-22T10:30:00",
                    "status": "completed",
                    "symbol_count": 5,
                    "processed_count": 4,
                    "long_count": 2,
                    "short_count": 1,
                    "no_setup_count": 1,
                    "input_symbols": ["AAPL", "MSFT", "GOOGL", "AMZN", "META"],
                    "stock_list_id": 1,
                    "stock_list_name": "Tech Stocks",
                    "source_lists": None,
                    "results": [
                        {
                            "id": 1,
                            "stock": "AAPL",
                            "created_at": "2025-01-22T10:30:00",
                            "recommendation": "LONG",
                            "confidence_score": 80,
                            "trend_aligned": True,
                            "ma20_aligned": True,
                            "candle_aligned": True,
                            "volume_aligned": True,
                            "cci_aligned": True,
                            "criteria_aligned": 4,
                            "direction": "LONG"
                        }
                    ],
                    "failed_symbols": {
                        "META": "Insufficient data available"
                    }
                }
            ]
        }
    }


class Live20RunDeleteResponse(StrictBaseModel):
    """Response after soft-deleting a run."""

    success: bool
    message: str

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "success": True,
                    "message": "Run 1 deleted successfully"
                }
            ]
        }
    }
