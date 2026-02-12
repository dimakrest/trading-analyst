"""Interactive Brokers market data provider implementation.

Provides real-time intraday data via IB Gateway/TWS connection.
"""
import asyncio
import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from ib_async import IB, Stock

from app.core.config import get_settings
from app.core.exceptions import APIError, DataValidationError, SymbolNotFoundError
from app.providers.base import (
    MarketDataProviderInterface,
    PriceDataPoint,
    PriceDataRequest,
    SymbolInfo,
)

logger = logging.getLogger(__name__)


class IBDataProvider(MarketDataProviderInterface):
    """Interactive Brokers market data provider for real-time intraday data.

    Uses ib_async library to fetch historical bars from IB Gateway/TWS.
    Optimized for 15-minute intraday data for "hot trade" evaluation.

    Note:
        Currently supports US equities only (SMART routing, USD currency).
        International markets may be added in a future version if needed.
    """

    # Supported intervals for IB historical data
    VALID_INTERVALS = ["1m", "2m", "5m", "15m", "30m", "1h", "1d"]

    # IB bar size mapping (our interval -> IB barSizeSetting)
    BAR_SIZE_MAP = {
        "1m": "1 min",
        "2m": "2 mins",
        "5m": "5 mins",
        "15m": "15 mins",
        "30m": "30 mins",
        "1h": "1 hour",
        "1d": "1 day",
    }

    # Connection settings
    CONNECTION_TIMEOUT = 30

    # Market configuration (US equities only for now)
    DEFAULT_EXCHANGE = "SMART"  # IB Smart Order Routing - best execution across US exchanges
    DEFAULT_CURRENCY = "USD"    # US Dollar denominated stocks

    def __init__(self):
        """Initialize IB data provider."""
        self._settings = get_settings()
        if self._settings.ib_data_client_id is None:
            raise ValueError(
                "IB_DATA_CLIENT_ID environment variable is required when using IB data provider"
            )
        self.ib = IB()
        self._connected = False
        self._host = self._settings.ib_host
        self._port = self._settings.ib_port
        self._client_id = self._settings.ib_data_client_id

    @property
    def provider_name(self) -> str:
        return "ib"

    @property
    def supported_intervals(self) -> list[str]:
        return self.VALID_INTERVALS.copy()

    async def connect(self) -> None:
        """Connect to IB Gateway/TWS."""
        if self._connected and self.ib.isConnected():
            return

        try:
            logger.info(f"Connecting to IB Gateway at {self._host}:{self._port}")
            await asyncio.wait_for(
                self.ib.connectAsync(
                    host=self._host,
                    port=self._port,
                    clientId=self._client_id,
                    readonly=True,  # Data only, no orders
                ),
                timeout=self.CONNECTION_TIMEOUT,
            )
            self._connected = True
            logger.info("Successfully connected to IB Gateway for market data")
        except asyncio.TimeoutError:
            raise APIError(f"Timeout connecting to IB Gateway at {self._host}:{self._port}")
        except OSError as e:
            logger.error(f"Failed to connect to IB Gateway: {e}")
            raise APIError(f"Failed to connect to IB Gateway: {e}")

    async def disconnect(self) -> None:
        """Disconnect from IB Gateway."""
        if self.ib.isConnected():
            self.ib.disconnect()
            self._connected = False
            logger.info("Disconnected from IB Gateway")

    async def _ensure_connected(self) -> None:
        """Ensure connection is active, reconnect if needed."""
        if not self._connected or not self.ib.isConnected():
            await self.connect()

    def _normalize_datetime(self, bar_date: Any) -> datetime:
        """Normalize bar date to datetime with UTC timezone.

        Args:
            bar_date: Date from IB bar (datetime or string)

        Returns:
            datetime: Normalized datetime with UTC timezone
        """
        if isinstance(bar_date, datetime):
            dt = bar_date
        else:
            dt = datetime.fromisoformat(str(bar_date))

        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)

        return dt

    async def get_symbol_info(self, symbol: str) -> SymbolInfo:
        """Get symbol information from Interactive Brokers.

        Note: IB API provides limited symbol metadata (symbol and currency only).
        For full info (sector, industry), use Yahoo Finance provider.
        """
        await self._ensure_connected()

        symbol = symbol.upper().strip()

        try:
            contract = Stock(symbol, self.DEFAULT_EXCHANGE, self.DEFAULT_CURRENCY)
            qualified = await self.ib.qualifyContractsAsync(contract)

            if not qualified:
                raise SymbolNotFoundError(f"Symbol '{symbol}' not found in IB")

            return SymbolInfo(
                symbol=symbol,
                name=symbol,  # IB API doesn't provide company name in contract qualification
                currency=self.DEFAULT_CURRENCY,
                exchange=self.DEFAULT_EXCHANGE,
                market_cap=None,
                sector=None,
                industry=None,
            )
        except SymbolNotFoundError:
            raise
        except Exception as e:
            logger.error(f"Error fetching symbol info for {symbol}: {e}")
            raise APIError(f"Failed to fetch symbol info for {symbol}: {e}")

    async def fetch_price_data(self, request: PriceDataRequest) -> list[PriceDataPoint]:
        """Fetch historical price data from IB."""
        await self._ensure_connected()

        # Validate interval
        if request.interval not in self.VALID_INTERVALS:
            raise DataValidationError(
                f"Invalid interval '{request.interval}'. "
                f"Valid values: {', '.join(self.VALID_INTERVALS)}"
            )

        symbol = request.symbol.upper().strip()
        bar_size = self.BAR_SIZE_MAP[request.interval]

        try:
            # Create and qualify contract
            contract = Stock(symbol, self.DEFAULT_EXCHANGE, self.DEFAULT_CURRENCY)
            qualified = await self.ib.qualifyContractsAsync(contract)

            if not qualified:
                raise SymbolNotFoundError(f"Symbol '{symbol}' not found in IB")

            # Calculate duration string based on date range
            # IB rejects requests >365 days unless specified in years
            days = (request.end_date - request.start_date).days + 1
            if days > 365:
                # For >365 days, use years instead of days
                years = days / 365.25  # Account for leap years
                duration = f"{int(years)} Y" if years >= 1 else "1 Y"
            else:
                duration = f"{days} D"

            # Fetch historical bars
            logger.info(f"Fetching {bar_size} bars for {symbol}, duration: {duration}")

            bars = await self.ib.reqHistoricalDataAsync(
                contract,
                endDateTime="",  # Empty = now
                durationStr=duration,
                barSizeSetting=bar_size,
                whatToShow="TRADES",
                useRTH=True,  # Regular trading hours only
                formatDate=1,
            )

            if not bars:
                logger.warning(f"No data returned for {symbol}")
                return []

            # Transform to PriceDataPoint list
            price_points = []
            for bar in bars:
                point = PriceDataPoint(
                    symbol=symbol,
                    timestamp=self._normalize_datetime(bar.date),
                    open_price=Decimal(str(bar.open)),
                    high_price=Decimal(str(bar.high)),
                    low_price=Decimal(str(bar.low)),
                    close_price=Decimal(str(bar.close)),
                    volume=int(bar.volume) if bar.volume >= 0 else 0,
                )

                # Validate OHLC constraints
                self._validate_price_point(point)
                price_points.append(point)

            logger.info(f"Fetched {len(price_points)} bars for {symbol}")
            return price_points

        except (SymbolNotFoundError, DataValidationError):
            raise
        except Exception as e:
            logger.error(f"Error fetching data for {symbol}: {e}")
            raise APIError(f"Failed to fetch data from IB: {e}")

    async def get_latest_quote(self, symbol: str) -> dict[str, Any]:
        """Get latest quote from IB (not implemented - use fetch_price_data)."""
        raise NotImplementedError("Use fetch_price_data for IB data")
