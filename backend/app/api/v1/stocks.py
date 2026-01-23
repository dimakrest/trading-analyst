"""Stock data endpoints for price information and market data.
"""
import logging
from datetime import UTC
from datetime import datetime
from datetime import timedelta

from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from fastapi import Query
from fastapi import status
from pydantic import Field

from app.core.config import get_settings
from app.core.deps import get_data_service
from app.schemas.base import StrictBaseModel
from app.services.data_service import APIError
from app.services.data_service import DataService
from app.services.data_service import DataValidationError
from app.services.data_service import SymbolNotFoundError
from app.utils.validation import is_valid_symbol, normalize_symbol

router = APIRouter()
logger = logging.getLogger(__name__)
settings = get_settings()


# Response Models
class PriceData(StrictBaseModel):
    """Price data model."""

    date: str = Field(..., description="Date in YYYY-MM-DD format for daily data, ISO datetime for intraday data")
    open: float = Field(..., description="Opening price")
    high: float = Field(..., description="High price")
    low: float = Field(..., description="Low price")
    close: float = Field(..., description="Closing price")
    volume: int = Field(..., description="Trading volume")

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "examples": [
                {
                    "date": "2025-12-06",
                    "open": 178.25,
                    "high": 180.15,
                    "low": 177.90,
                    "close": 179.85,
                    "volume": 45823100
                }
            ]
        }
    }


class StockDataResponse(StrictBaseModel):
    """Stock data response model."""

    symbol: str = Field(..., description="Stock symbol")
    data: list[PriceData] = Field(..., description="Price data points")
    total_records: int = Field(..., description="Total number of records")
    start_date: str = Field(..., description="Start date of data")
    end_date: str = Field(..., description="End date of data")
    interval: str = Field(default="1d", description="Data interval")
    source: str = Field(default="yahoo", description="Data source")
    last_updated: str = Field(..., description="Last update timestamp")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "symbol": "AAPL",
                    "data": [
                        {
                            "date": "2025-12-04",
                            "open": 177.50,
                            "high": 179.20,
                            "low": 176.85,
                            "close": 178.45,
                            "volume": 42156800
                        },
                        {
                            "date": "2025-12-05",
                            "open": 178.80,
                            "high": 180.45,
                            "low": 178.10,
                            "close": 179.20,
                            "volume": 38945600
                        },
                        {
                            "date": "2025-12-06",
                            "open": 178.25,
                            "high": 180.15,
                            "low": 177.90,
                            "close": 179.85,
                            "volume": 45823100
                        }
                    ],
                    "total_records": 3,
                    "start_date": "2025-12-04",
                    "end_date": "2025-12-06",
                    "interval": "1d",
                    "source": "yahoo",
                    "last_updated": "2025-12-06T15:45:30.123456"
                }
            ]
        }
    }


# Mock function removed - using real Yahoo Finance data


@router.get(
    "/{symbol}/prices",
    response_model=StockDataResponse,
    summary="Get Stock Prices",
    description="Retrieve historical OHLCV price data for a stock symbol. "
    "Returns pure price data only (Open, High, Low, Close, Volume). "
    "For technical indicators (MA-20, CCI), use the /indicators endpoint. "
    "Supports daily and intraday intervals (1d, 15m, etc.). "
    "Data is cached for performance with optional force refresh.",
    operation_id="get_stock_prices",
    responses={
        400: {"description": "Invalid symbol or date range"},
        404: {"description": "Symbol not found"},
        500: {"description": "Internal Server Error"},
        503: {"description": "Yahoo Finance API unavailable"},
    }
)
async def get_stock_prices(
    symbol: str,
    start_date: str | None = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: str | None = Query(None, description="End date (YYYY-MM-DD)"),
    period: str | None = Query(None, description="Period (e.g., 1mo, 3mo, 1y) - alternative to start_date/end_date"),
    interval: str = Query("1d", description="Data interval (1d, 1wk, 1mo)"),
    force_refresh: bool = Query(False, description="Force refresh from data source (bypass cache)"),
    data_service: DataService = Depends(get_data_service),
) -> StockDataResponse:
    """Get stock price data for a symbol using Yahoo Finance.

    Args:
        symbol: Stock symbol (e.g., AAPL, MSFT)
        start_date: Start date for data retrieval
        end_date: End date for data retrieval
        interval: Data interval
        force_refresh: Whether to bypass cache and fetch fresh data
        data_service: Yahoo Finance data service

    Returns:
        StockDataResponse: Stock price data

    Raises:
        HTTPException: If symbol is invalid or data retrieval fails
    """
    try:
        # Validate and clean symbol
        symbol = normalize_symbol(symbol)
        if not is_valid_symbol(symbol):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid symbol format: {symbol}"
            )

        # Handle period parameter (convert to start_date/end_date)
        if period and not start_date and not end_date:
            # Parse period string (e.g., "1mo", "3mo", "1y", "5d")
            period_map = {
                "1d": 1,
                "5d": 5,
                "1mo": 30,
                "3mo": 90,
                "6mo": 180,
                "1y": 365,
                "2y": 730,
                "5y": 1825,
                "10y": 3650,
                "ytd": None,  # Year to date
                "max": 3650 * 3,  # 30 years
            }

            if period in period_map:
                end_date = datetime.now(UTC).strftime("%Y-%m-%d")
                if period == "ytd":
                    # Year to date
                    start_date = datetime(datetime.now(UTC).year, 1, 1).strftime("%Y-%m-%d")
                else:
                    days = period_map[period]
                    start_date = (datetime.now(UTC) - timedelta(days=days)).strftime("%Y-%m-%d")
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid period '{period}'. Valid values: 1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max"
                )

        # Set default date range (1 year) if neither period nor dates provided
        if not start_date:
            start_date = (datetime.now(UTC) - timedelta(days=settings.default_history_days)).strftime("%Y-%m-%d")
        if not end_date:
            end_date = datetime.now(UTC).strftime("%Y-%m-%d")

        # Parse and validate dates
        try:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d").replace(tzinfo=UTC)
            end_dt = datetime.strptime(end_date, "%Y-%m-%d").replace(tzinfo=UTC)

            if start_dt > end_dt:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Start date must be before end date",
                )

            if (end_dt - start_dt).days > 1095:  # ~3 years
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Date range cannot exceed 3 years",
                )

        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid date format. Use YYYY-MM-DD",
            )

        # Fetch with cache-first approach using unified get_price_data()
        logger.info(f"Fetching price data for {symbol} from {start_date} to {end_date}")

        price_records = await data_service.get_price_data(
            symbol=symbol,
            start_date=start_dt,
            end_date=end_dt,
            interval=interval,
            force_refresh=force_refresh,
        )

        # Convert to response format
        price_data = []
        for record in price_records:
            # Format date based on interval type
            # For intraday intervals, include full timestamp to avoid duplicates
            # For daily/weekly/monthly intervals, use date-only format
            intraday_intervals = ['1m', '2m', '5m', '15m', '30m', '60m', '90m', '1h', '2h', '4h']
            if interval in intraday_intervals:
                date_str = record.timestamp.isoformat()
            else:
                date_str = record.timestamp.strftime("%Y-%m-%d")

            price_data.append(
                PriceData(
                    date=date_str,
                    open=float(record.open_price),
                    high=float(record.high_price),
                    low=float(record.low_price),
                    close=float(record.close_price),
                    volume=record.volume,
                )
            )

        response_data = StockDataResponse(
            symbol=symbol,
            data=price_data,
            total_records=len(price_data),
            start_date=start_date,
            end_date=end_date,
            interval=interval,
            source=data_service.provider.provider_name,
            last_updated=datetime.now(UTC).isoformat(),
        )

        logger.info(f"Successfully fetched {len(price_data)} records for {symbol}")
        return response_data

    except HTTPException:
        # Re-raise HTTPException as-is (from validation errors above)
        raise
    except SymbolNotFoundError:
        logger.warning(f"Symbol not found: {symbol}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Symbol '{symbol}' not found or has no data",
        )
    except DataValidationError as e:
        logger.warning(f"Data validation error for {symbol}: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except APIError as e:
        logger.error(f"Yahoo Finance API error for {symbol}: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"External data service temporarily unavailable: {str(e)}",
        )
    except Exception as e:
        logger.error(f"Unexpected error fetching data for {symbol}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while fetching stock data",
        )
