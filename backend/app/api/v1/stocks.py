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
from typing import Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import get_settings
from app.core.database import get_session_factory
from app.core.deps import get_data_service
from app.models.stock_sector import StockSector
from app.constants.sectors import VALID_SECTOR_ETFS
from app.schemas.base import StrictBaseModel
from app.services.data_service import APIError
from app.services.data_service import DataService
from app.services.data_service import DataValidationError
from app.services.data_service import SymbolNotFoundError
from app.utils.validation import is_valid_symbol, normalize_symbol
from app.indicators.ma_analysis import analyze_ma_distance, PricePosition
from app.indicators.trend import detect_trend, TrendDirection

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


class StockInfoResponse(StrictBaseModel):
    """Stock info response with sector data."""

    symbol: str = Field(..., description="Stock symbol")
    name: str = Field(..., description="Company name")
    sector: str | None = Field(None, description="Yahoo Finance sector name (e.g., 'Technology')")
    sector_etf: str | None = Field(None, description="Mapped SPDR ETF symbol (e.g., 'XLK')")
    industry: str | None = Field(None, description="Industry classification")
    exchange: str | None = Field(None, description="Stock exchange")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "symbol": "AAPL",
                    "name": "Apple Inc.",
                    "sector": "Technology",
                    "sector_etf": "XLK",
                    "industry": "Consumer Electronics",
                    "exchange": "NASDAQ"
                }
            ]
        }
    }


@router.get(
    "/{symbol}/info",
    response_model=StockInfoResponse,
    summary="Get Stock Metadata",
    description="Returns stock metadata including sector ETF mapping. Uses DB cache for sector info.",
    operation_id="get_stock_info",
    responses={
        400: {"description": "Invalid symbol format"},
        404: {"description": "Symbol not found"},
        503: {"description": "Data provider unavailable"},
    },
)
async def get_stock_info(
    symbol: str,
    data_service: DataService = Depends(get_data_service),
    session_factory: async_sessionmaker[AsyncSession] = Depends(get_session_factory),
) -> StockInfoResponse:
    """Get stock metadata including sector information.

    Reads from stock_sectors cache when available.
    Falls back to Yahoo Finance on cache miss and caches the result.

    Args:
        symbol: Stock symbol (e.g., AAPL, MSFT)
        data_service: Data service for fetching stock info
        session_factory: Database session factory

    Returns:
        StockInfoResponse: Stock metadata with sector information

    Raises:
        HTTPException: If symbol is invalid or data retrieval fails
    """
    try:
        # Validate and clean symbol
        symbol = normalize_symbol(symbol)
        if not is_valid_symbol(symbol):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid symbol format: {symbol}"
            )

        # Try cache first for complete stock info (name + exchange + sector)
        try:
            async with session_factory() as session:
                result = await session.execute(
                    select(StockSector).where(StockSector.symbol == symbol)
                )
                cached = result.scalar_one_or_none()

                if cached and cached.name is not None:
                    # Full cache hit - no provider call needed
                    return StockInfoResponse(
                        symbol=symbol,
                        name=cached.name,
                        sector=cached.sector,
                        sector_etf=cached.sector_etf,
                        industry=cached.industry,
                        exchange=cached.exchange,
                    )

                # Cache miss or partial hit - delegate to service which handles:
                # 1. Checking cache for sector info
                # 2. Calling provider if needed (get_symbol_info)
                # 3. Storing complete data (name, exchange, sector, industry, sector_etf)
                # 4. Handling race conditions with ON CONFLICT DO UPDATE
                await data_service.get_sector_etf(symbol, session)
                await session.commit()

                # After get_sector_etf(), the complete data is in cache - refresh and re-query
                session.expire_all()  # Clear identity map to fetch fresh data
                result = await session.execute(
                    select(StockSector).where(StockSector.symbol == symbol)
                )
                cached = result.scalar_one_or_none()

                if not cached:
                    # Should never happen, but handle gracefully
                    raise RuntimeError(f"Cache write failed for {symbol}")

                return StockInfoResponse(
                    symbol=symbol,
                    name=cached.name or symbol,
                    sector=cached.sector,
                    sector_etf=cached.sector_etf,
                    industry=cached.industry,
                    exchange=cached.exchange,
                )
        except SymbolNotFoundError:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Symbol '{symbol}' not found"
            )
        except APIError:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Data provider unavailable"
            )
    except HTTPException:
        # Re-raise HTTPException as-is
        raise
    except Exception as e:
        logger.error(f"Unexpected error fetching stock info for {symbol}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while fetching stock info",
        )


class SectorTrendResponse(StrictBaseModel):
    """Sector trend analysis response."""

    sector_etf: str = Field(..., description="Sector ETF symbol (e.g., 'XLK', 'XLE')")
    trend_direction: Literal["up", "down", "sideways"] = Field(
        ..., description="Trend direction over 20-day period"
    )
    ma20_position: Literal["above", "below"] = Field(
        ..., description="Current price position relative to MA20"
    )
    ma20_distance_pct: float = Field(
        ..., description="Percentage distance from MA20 (positive = above, negative = below)"
    )
    ma50_position: Literal["above", "below"] = Field(
        ..., description="Current price position relative to MA50"
    )
    ma50_distance_pct: float = Field(
        ..., description="Percentage distance from MA50 (positive = above, negative = below)"
    )
    price_change_5d_pct: float = Field(..., description="5-day price change percentage")
    price_change_20d_pct: float = Field(..., description="20-day price change percentage")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "sector_etf": "XLK",
                    "trend_direction": "up",
                    "ma20_position": "above",
                    "ma20_distance_pct": 2.5,
                    "ma50_position": "above",
                    "ma50_distance_pct": 5.2,
                    "price_change_5d_pct": 1.8,
                    "price_change_20d_pct": 4.3,
                }
            ]
        }
    }


@router.get(
    "/{symbol}/sector-trend",
    response_model=SectorTrendResponse,
    summary="Get Sector Trend Analysis",
    description=(
        "Returns trend analysis for a sector ETF including MA positions and price changes. "
        "Fetches 60 days of price data which is cached in stock_prices table. "
        "Multiple stocks in the same sector share one cached price fetch."
    ),
    operation_id="get_sector_trend",
    responses={
        400: {"description": "Invalid sector ETF symbol"},
        404: {"description": "Symbol not found"},
        503: {"description": "Data provider unavailable"},
    },
)
async def get_sector_trend(
    symbol: str,
    data_service: DataService = Depends(get_data_service),
) -> SectorTrendResponse:
    """Get sector trend analysis for a sector ETF.

    Fetches 60 days of price data via DataService (which caches in stock_prices).
    If multiple stocks share the same sector, the ETF prices are fetched once
    and served from cache on subsequent requests.

    Uses existing indicator modules for consistency:
    - analyze_ma_distance() for MA20/MA50 position and distance
    - detect_trend() for trend direction

    Args:
        symbol: Sector ETF symbol (must be in SECTOR_TO_ETF values)
        data_service: Data service for fetching price data

    Returns:
        SectorTrendResponse: Sector trend analysis data

    Raises:
        HTTPException: If symbol is invalid or data retrieval fails
    """
    try:
        # Validate and clean symbol
        symbol = normalize_symbol(symbol)
        if not is_valid_symbol(symbol):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid symbol format: {symbol}"
            )

        # Validate it's a known sector ETF
        if symbol not in VALID_SECTOR_ETFS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Symbol '{symbol}' is not a valid sector ETF. "
                       f"Valid sector ETFs: {', '.join(sorted(VALID_SECTOR_ETFS))}"
            )

        # Fetch 60 days of price data (auto-cached in stock_prices)
        end_date = datetime.now(UTC)
        start_date = end_date - timedelta(days=60)

        logger.info(f"Fetching sector trend data for {symbol}")
        price_records = await data_service.get_price_data(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            interval="1d",
            force_refresh=False,  # Use cache for efficiency
        )

        if len(price_records) < 25:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Insufficient price data for {symbol}. Need at least 25 days, got {len(price_records)}"
            )

        # Extract closing prices
        closes = [float(record.close_price) for record in price_records]

        # Calculate MA20 analysis
        ma20_analysis = analyze_ma_distance(closes, period=20)

        # Calculate MA50 analysis
        ma50_analysis = analyze_ma_distance(closes, period=50)

        # Detect 20-day trend
        trend = detect_trend(closes, period=20, threshold_pct=1.0)

        # Calculate price changes
        if len(closes) >= 6:
            price_5d_ago = closes[-6]  # -6 because -1 is current, -6 is 5 days ago
            price_change_5d_pct = ((closes[-1] - price_5d_ago) / price_5d_ago) * 100
        else:
            price_change_5d_pct = 0.0

        if len(closes) >= 21:
            price_20d_ago = closes[-21]  # -21 because -1 is current, -21 is 20 days ago
            price_change_20d_pct = ((closes[-1] - price_20d_ago) / price_20d_ago) * 100
        else:
            price_change_20d_pct = 0.0

        # Map indicator results to Literal types
        # TrendDirection -> "up"/"down"/"sideways"
        if trend == TrendDirection.BULLISH:
            trend_direction = "up"
        elif trend == TrendDirection.BEARISH:
            trend_direction = "down"
        else:
            trend_direction = "sideways"

        # PricePosition -> "above"/"below" (AT is treated as "above" for simplicity)
        ma20_position = "above" if ma20_analysis.price_position in (PricePosition.ABOVE, PricePosition.AT) else "below"
        ma50_position = "above" if ma50_analysis.price_position in (PricePosition.ABOVE, PricePosition.AT) else "below"

        return SectorTrendResponse(
            sector_etf=symbol,
            trend_direction=trend_direction,
            ma20_position=ma20_position,
            ma20_distance_pct=round(ma20_analysis.distance_pct, 2),
            ma50_position=ma50_position,
            ma50_distance_pct=round(ma50_analysis.distance_pct, 2),
            price_change_5d_pct=round(price_change_5d_pct, 2),
            price_change_20d_pct=round(price_change_20d_pct, 2),
        )

    except HTTPException:
        # Re-raise HTTPException as-is
        raise
    except SymbolNotFoundError:
        logger.warning(f"Sector ETF not found: {symbol}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sector ETF '{symbol}' not found"
        )
    except DataValidationError as e:
        logger.warning(f"Data validation error for {symbol}: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except APIError as e:
        logger.error(f"Data provider error for {symbol}: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Data provider unavailable"
        )
    except Exception as e:
        logger.error(f"Unexpected error fetching sector trend for {symbol}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while fetching sector trend",
        )
