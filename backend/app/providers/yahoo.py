"""Yahoo Finance market data provider implementation.

This provider wraps the yfinance library, handling async execution,
data transformation, error handling, and retries.
"""
import asyncio
import logging
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

import pandas as pd
import yfinance as yf

from app.core.config import get_settings
from app.core.exceptions import (
    APIError,
    DataValidationError,
    SymbolNotFoundError,
)
from app.providers.base import (
    MarketDataProviderInterface,
    PriceDataPoint,
    PriceDataRequest,
    SymbolInfo,
)

logger = logging.getLogger(__name__)
settings = get_settings()


class YahooFinanceProvider(MarketDataProviderInterface):
    """
    Yahoo Finance market data provider implementation.

    Wraps the yfinance library, handling:
    - Async execution of blocking yfinance calls
    - Data transformation to common format
    - Error handling and retries
    - Validation of intervals and data quality
    """

    # Yahoo Finance-specific interval values
    VALID_INTERVALS = [
        "1m",
        "2m",
        "5m",
        "15m",
        "30m",
        "60m",
        "90m",  # Intraday
        "1h",
        "1d",
        "5d",
        "1wk",
        "1mo",
        "3mo",  # Daily+
    ]

    INTRADAY_INTERVALS = ["1m", "2m", "5m", "15m", "30m", "60m", "90m", "1h"]

    @property
    def provider_name(self) -> str:
        return "yahoo_finance"

    @property
    def supported_intervals(self) -> list[str]:
        return self.VALID_INTERVALS.copy()

    async def get_symbol_info(self, symbol: str) -> SymbolInfo:
        """Get comprehensive information about a stock symbol from Yahoo Finance."""
        symbol = symbol.upper().strip()

        try:
            loop = asyncio.get_event_loop()

            # Fetch ticker info (blocking call, run in executor)
            ticker = await loop.run_in_executor(None, lambda: yf.Ticker(symbol))
            info = await loop.run_in_executor(None, lambda: ticker.info)

            # Check if symbol exists
            if not info or "symbol" not in info:
                raise SymbolNotFoundError(f"Symbol '{symbol}' not found")

            # Extract relevant fields
            return SymbolInfo(
                symbol=symbol,
                name=info.get("longName", info.get("shortName", symbol)),
                currency=info.get("currency", "USD"),
                exchange=info.get("exchange", "Unknown"),
                market_cap=info.get("marketCap"),
                sector=info.get("sector"),
                industry=info.get("industry"),
            )

        except SymbolNotFoundError:
            raise
        except Exception as e:
            logger.error(f"Error fetching symbol info for {symbol}: {e}")
            raise APIError(f"Failed to fetch symbol info for {symbol}: {e}")

    async def fetch_price_data(self, request: PriceDataRequest) -> list[PriceDataPoint]:
        """Fetch historical price data from Yahoo Finance."""
        # Validate interval
        if request.interval not in self.VALID_INTERVALS:
            raise DataValidationError(
                f"Invalid interval '{request.interval}'. "
                f"Valid values: {', '.join(self.VALID_INTERVALS)}"
            )

        # Validate date range
        self._validate_date_range(request)

        # Fetch with retries
        data = await self._fetch_with_retry(request)

        # Transform to common format
        price_points = await self._transform_data(data, request)

        logger.info(
            f"Fetched {len(price_points)} data points for {request.symbol} "
            f"from {request.start_date} to {request.end_date}"
        )

        return price_points

    async def get_latest_quote(self, symbol: str) -> dict[str, Any]:
        """Get latest quote from Yahoo Finance."""
        symbol = symbol.upper().strip()

        try:
            loop = asyncio.get_event_loop()

            ticker = await loop.run_in_executor(None, lambda: yf.Ticker(symbol))
            info = await loop.run_in_executor(None, lambda: ticker.info)
            fast_info = await loop.run_in_executor(None, lambda: ticker.fast_info)

            quote = {
                "symbol": symbol,
                "current_price": fast_info.get("lastPrice", info.get("regularMarketPrice")),
                "previous_close": info.get("previousClose"),
                "open": info.get("regularMarketOpen"),
                "day_high": info.get("dayHigh"),
                "day_low": info.get("dayLow"),
                "volume": info.get("volume"),
                "average_volume": info.get("averageVolume"),
                "market_cap": info.get("marketCap"),
                "fifty_two_week_high": info.get("fiftyTwoWeekHigh"),
                "fifty_two_week_low": info.get("fiftyTwoWeekLow"),
                "timestamp": datetime.now(timezone.utc),
            }

            return quote

        except Exception as e:
            logger.error(f"Error fetching quote for {symbol}: {e}")
            raise APIError(f"Failed to fetch quote for {symbol}: {e}")

    def _validate_date_range(self, request: PriceDataRequest) -> None:
        """Validate date range constraints."""
        if request.start_date >= request.end_date:
            raise DataValidationError("start_date must be before end_date")

        # Intraday data limited to 60 days
        if request.interval in self.INTRADAY_INTERVALS:
            max_days = 60
            if (request.end_date - request.start_date).days > max_days:
                raise DataValidationError(f"Intraday data limited to {max_days} days")

    async def _fetch_with_retry(self, request: PriceDataRequest) -> pd.DataFrame:
        """Fetch data with retry logic and exponential backoff."""
        loop = asyncio.get_event_loop()
        last_error = None

        for attempt in range(settings.yahoo_max_retries):
            try:
                # Execute blocking yfinance call in thread pool
                ticker = await loop.run_in_executor(None, lambda: yf.Ticker(request.symbol))

                data = await loop.run_in_executor(
                    None,
                    lambda: ticker.history(
                        start=request.start_date.date(),
                        end=request.end_date.date() + timedelta(days=1),  # yfinance end is exclusive
                        interval=request.interval,
                        prepost=request.include_pre_post,
                        auto_adjust=True,
                        back_adjust=False,
                    ),
                )

                if data.empty:
                    raise DataValidationError(f"No data returned for {request.symbol}")

                return data

            except Exception as e:
                last_error = e
                if attempt < settings.yahoo_max_retries - 1:
                    wait_time = settings.yahoo_retry_delay * (2**attempt)
                    logger.warning(
                        f"Attempt {attempt + 1} failed for {request.symbol}, "
                        f"retrying in {wait_time}s: {e}"
                    )
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(
                        f"All {settings.yahoo_max_retries} attempts failed for " f"{request.symbol}: {e}"
                    )

        raise APIError(
            f"Failed to fetch data after {settings.yahoo_max_retries} attempts: {last_error}"
        )

    async def _transform_data(
        self, data: pd.DataFrame, request: PriceDataRequest
    ) -> list[PriceDataPoint]:
        """Transform Yahoo Finance DataFrame to PriceDataPoint list."""
        price_points = []

        for timestamp, row in data.iterrows():
            # Convert timestamp to datetime
            if hasattr(timestamp, "to_pydatetime"):
                timestamp_dt = timestamp.to_pydatetime()
            else:
                timestamp_dt = timestamp

            # Normalize to UTC (like IB provider does)
            if timestamp_dt.tzinfo is not None:
                timestamp_dt = timestamp_dt.astimezone(timezone.utc)
            else:
                timestamp_dt = timestamp_dt.replace(tzinfo=timezone.utc)

            # Create price point
            point = PriceDataPoint(
                symbol=request.symbol,
                timestamp=timestamp_dt,
                open_price=Decimal(str(row["Open"])),
                high_price=Decimal(str(row["High"])),
                low_price=Decimal(str(row["Low"])),
                close_price=Decimal(str(row["Close"])),
                volume=int(row["Volume"]) if not pd.isna(row["Volume"]) else 0,
            )

            # Validate OHLC constraints
            self._validate_price_point(point)

            price_points.append(point)

        return price_points

    async def get_next_earnings_date(self, symbol: str) -> int | None:
        """Get days until next earnings date for a symbol.

        Args:
            symbol: Stock ticker symbol (e.g., 'AAPL')

        Returns:
            Days until earnings (negative if past), or None if unavailable
            (ETF, missing data, error)
        """
        symbol = symbol.upper().strip()

        try:
            loop = asyncio.get_event_loop()

            # Fetch calendar
            calendar = await loop.run_in_executor(
                None, lambda: yf.Ticker(symbol).calendar
            )

            # Check if calendar exists and has earnings date
            if not calendar or not isinstance(calendar, dict):
                logger.debug(f"No calendar data for {symbol} (likely ETF)")
                return None

            if "Earnings Date" not in calendar:
                logger.debug(f"No earnings date in calendar for {symbol}")
                return None

            earnings_dates = calendar["Earnings Date"]
            if not earnings_dates:
                return None

            # Parse first date (next earnings)
            if isinstance(earnings_dates, list) and len(earnings_dates) > 0:
                raw_date = earnings_dates[0]

                # Handle different date formats from yfinance
                if isinstance(raw_date, date):
                    earnings_date = raw_date
                elif isinstance(raw_date, str):
                    try:
                        earnings_date = datetime.strptime(raw_date, "%Y-%m-%d").date()
                    except ValueError as e:
                        logger.debug(
                            f"Date parsing failed for {symbol}: raw value='{raw_date}', error={e}"
                        )
                        return None
                else:
                    logger.debug(
                        f"Unexpected date type for {symbol}: {type(raw_date).__name__}"
                    )
                    return None

                today = date.today()
                days_until = (earnings_date - today).days

                logger.info(f"Fetched earnings date for {symbol}: {days_until} days")
                return days_until

            return None

        except Exception as e:
            logger.warning(f"Error fetching earnings date for {symbol}: {e}")
            return None
