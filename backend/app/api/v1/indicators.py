"""Stock indicator endpoints for technical indicator time-series data."""

import logging
from datetime import UTC, date, datetime, timedelta

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.config import get_settings
from app.core.deps import get_data_service, get_validated_symbol
from app.indicators.registry import (
    IndicatorType,
    PriceData,
    calculate_indicators,
)
from app.indicators.technical import commodity_channel_index, detect_cci_signals
from app.schemas.indicators import IndicatorAnalysisResponse, IndicatorData, IndicatorsResponse
from app.services.data_service import (
    APIError,
    DataService,
    DataValidationError,
    SymbolNotFoundError,
)
from app.utils.technical_indicators import calculate_sma
from app.utils.validation import is_valid_symbol, normalize_symbol

router = APIRouter()
logger = logging.getLogger(__name__)
settings = get_settings()


@router.get(
    "/{symbol}/indicators",
    response_model=IndicatorsResponse,
    summary="Get Technical Indicators",
    description="Retrieve technical indicator time-series data for a stock symbol. "
    "Returns 20-period Simple Moving Average (MA-20) and Commodity Channel Index (CCI) "
    "with momentum signals. For price data (OHLCV), use the /prices endpoint. "
    "Supports daily and intraday intervals (1d, 15m, etc.). "
    "Data is cached for performance with optional force refresh.",
    operation_id="get_stock_indicators",
    responses={
        400: {"description": "Invalid symbol or date range"},
        404: {"description": "Symbol not found"},
        500: {"description": "Internal Server Error"},
        503: {"description": "Yahoo Finance API unavailable"},
    }
)
async def get_stock_indicators(
    symbol: str,
    start_date: str | None = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: str | None = Query(None, description="End date (YYYY-MM-DD)"),
    period: str | None = Query(
        None, description="Period (e.g., 1mo, 3mo, 1y) - alternative to start_date/end_date"
    ),
    interval: str = Query("1d", description="Data interval (1d, 1wk, 1mo)"),
    force_refresh: bool = Query(False, description="Force refresh from data source (bypass cache)"),
    data_service: DataService = Depends(get_data_service),
) -> IndicatorsResponse:
    """Get technical indicators time-series data for a symbol.

    Returns MA-20 and CCI indicator values for each data point.

    Args:
        symbol: Stock symbol (e.g., AAPL, MSFT)
        start_date: Start date for data retrieval
        end_date: End date for data retrieval
        period: Period string (alternative to start_date/end_date)
        interval: Data interval
        force_refresh: Force refresh from data source (bypass cache)
        data_service: Data service dependency

    Returns:
        IndicatorsResponse: Technical indicators time-series data

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
                    detail=f"Invalid period '{period}'. Valid values: 1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max",
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
        logger.info(f"Fetching indicator data for {symbol} from {start_date} to {end_date}")

        price_records = await data_service.get_price_data(
            symbol=symbol,
            start_date=start_dt,
            end_date=end_dt,
            interval=interval,
            force_refresh=force_refresh,
        )

        # Calculate MA 20
        ma_20_values = []
        if price_records:
            # Create DataFrame from price records for MA calculation
            df_data = []
            for record in price_records:
                df_data.append({"date": record.timestamp, "Close": float(record.close_price)})

            df = pd.DataFrame(df_data)

            # Calculate MA 20
            ma_20_series = calculate_sma(df, column="Close", window=20)
            ma_20_values = ma_20_series.tolist()

        # Calculate CCI
        cci_values: list[float] = []
        cci_signals: list[str | None] = []
        if price_records:
            high_prices = [float(r.high_price) for r in price_records]
            low_prices = [float(r.low_price) for r in price_records]
            close_prices = [float(r.close_price) for r in price_records]

            cci_array = commodity_channel_index(high_prices, low_prices, close_prices, period=20)
            cci_values = cci_array.tolist()
            cci_signals = detect_cci_signals(cci_array)

        # Convert to response format
        indicator_data = []
        for i, record in enumerate(price_records):
            # Get MA 20 value for this record
            ma_20_value = ma_20_values[i] if i < len(ma_20_values) else None
            # Convert NaN to None
            if ma_20_value is not None and pd.isna(ma_20_value):
                ma_20_value = None

            # Get CCI value and signal for this record
            cci_value = cci_values[i] if i < len(cci_values) else None
            if cci_value is not None and pd.isna(cci_value):
                cci_value = None
            cci_signal = cci_signals[i] if i < len(cci_signals) else None

            # Format date based on interval type
            # For intraday intervals, include full timestamp to avoid duplicates
            # For daily/weekly/monthly intervals, use date-only format
            intraday_intervals = ['1m', '2m', '5m', '15m', '30m', '60m', '90m', '1h', '2h', '4h']
            if interval in intraday_intervals:
                date_str = record.timestamp.isoformat()
            else:
                date_str = record.timestamp.strftime("%Y-%m-%d")

            indicator_data.append(
                IndicatorData(
                    date=date_str,
                    ma_20=float(ma_20_value) if ma_20_value is not None else None,
                    cci=float(cci_value) if cci_value is not None else None,
                    cci_signal=cci_signal,
                )
            )

        response_data = IndicatorsResponse(
            symbol=symbol,
            data=indicator_data,
            total_records=len(indicator_data),
            start_date=start_date,
            end_date=end_date,
            interval=interval,
            indicators=["MA-20", "CCI"],
        )

        logger.info(f"Successfully computed indicators for {len(indicator_data)} records for {symbol}")
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
        logger.error(f"Unexpected error fetching indicator data for {symbol}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while fetching indicator data",
        )


# Constants for analysis endpoint
ANALYSIS_LOOKBACK_DAYS = 60
ANALYSIS_MIN_BARS = 25


@router.get(
    "/{symbol}/analysis",
    response_model=IndicatorAnalysisResponse,
    summary="Get indicator analysis for trading agents",
    description="Calculate requested indicators for a symbol. "
    "Each agent specifies which indicators it needs via the 'include' parameter. "
    "Returns single-moment analysis for agent decision-making.",
    operation_id="get_indicator_analysis",
    responses={
        400: {"description": "Invalid symbol, invalid indicator, or insufficient data"},
        404: {"description": "Symbol not found"},
        503: {"description": "Data service unavailable"},
    },
)
async def get_indicator_analysis(
    symbol: str = Depends(get_validated_symbol),
    include: list[IndicatorType] = Query(
        ...,
        description="Indicators to calculate (e.g., trend, cci, volume_signal)",
    ),
    analysis_date: date | None = Query(
        None,
        description="Historical date for point-in-time analysis (YYYY-MM-DD). Defaults to latest.",
    ),
    data_service: DataService = Depends(get_data_service),
) -> IndicatorAnalysisResponse:
    """Calculate requested indicators for agent decision-making.

    This unified endpoint serves all trading agents. Each agent requests
    only the indicators it needs, enabling:
    - Single HTTP call per stock evaluation
    - Single data fetch, multiple calculations
    - Early rejection (request fewer indicators initially)

    Available indicators:
    - trend: 10-day price trend direction and strength
    - ma20_distance: Price distance from 20-day moving average
    - candle_pattern: Candlestick pattern with trend context
    - volume_signal: Volume exhaustion/accumulation signals
    - cci: CCI momentum with alignment signals
    """
    try:
        # Validate at least one indicator requested
        if not include:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="At least one indicator must be specified via 'include' parameter",
            )

        # Fetch price data (uses injected data_service with caching)
        price_data = await _fetch_analysis_price_data(data_service, symbol, analysis_date)

        # Calculate requested indicators
        indicators = calculate_indicators(price_data, include)

        # Determine analysis date for response
        if analysis_date:
            response_date = analysis_date.isoformat()
        else:
            response_date = datetime.now(UTC).date().isoformat()

        return IndicatorAnalysisResponse(
            symbol=symbol,
            analysis_date=response_date,
            indicators=indicators,
        )

    except HTTPException:
        raise
    except SymbolNotFoundError:
        logger.warning(f"Symbol not found: {symbol}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Symbol '{symbol}' not found or has no data",
        )
    except APIError as e:
        logger.error(f"Data service error for {symbol}: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Data service temporarily unavailable",
        )
    except Exception as e:
        logger.error(f"Unexpected error in indicator analysis for {symbol}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred",
        )


async def _fetch_analysis_price_data(
    data_service: DataService,
    symbol: str,
    analysis_date: date | None = None,
) -> PriceData:
    """Fetch price data for indicator analysis.

    Args:
        data_service: Injected DataService with caching support
        symbol: Stock ticker symbol
        analysis_date: Optional historical date for point-in-time analysis

    Returns:
        PriceData container with OHLCV arrays

    Raises:
        HTTPException: If insufficient data is available
    """
    if analysis_date:
        end_dt = datetime.combine(analysis_date, datetime.max.time()).replace(tzinfo=UTC)
    else:
        end_dt = datetime.now(UTC)

    start_dt = end_dt - timedelta(days=ANALYSIS_LOOKBACK_DAYS)

    price_records = await data_service.get_price_data(
        symbol=symbol,
        start_date=start_dt,
        end_date=end_dt,
        interval="1d",
    )

    if not price_records or len(price_records) < ANALYSIS_MIN_BARS:
        record_count = len(price_records) if price_records else 0
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Insufficient data for {symbol}: {record_count} bars (need {ANALYSIS_MIN_BARS})",
        )

    return PriceData(
        opens=[float(r.open_price) for r in price_records],
        highs=[float(r.high_price) for r in price_records],
        lows=[float(r.low_price) for r in price_records],
        closes=[float(r.close_price) for r in price_records],
        volumes=[float(r.volume) for r in price_records],
    )
