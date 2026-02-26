"""Stock price and market data models.

Models for storing stock market data with proper financial data types
and time-series optimization for technical analysis.
"""
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import BigInteger
from sqlalchemy import Boolean
from sqlalchemy import CheckConstraint
from sqlalchemy import DateTime
from sqlalchemy import Index
from sqlalchemy import Numeric
from sqlalchemy import String
from sqlalchemy import desc
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship

from app.models.base import Base


class StockPrice(Base):
    """Stock price data model optimized for time-series analysis.

    Stores OHLCV (Open, High, Low, Close, Volume) data with proper
    financial precision and indexing for efficient queries.

    Financial Data Best Practices:
    - Use Decimal for price data to avoid floating point precision issues
    - Store timestamps in UTC with timezone awareness
    - Use BigInteger for volume to handle high-volume stocks
    - Include data quality indicators
    - Optimize for time-series queries with composite indexes
    """

    __tablename__ = "stock_prices"

    # Stock identifier
    symbol: Mapped[str] = mapped_column(
        String(10), nullable=False, index=True, doc="Stock symbol (e.g., 'AAPL', 'GOOGL')"
    )

    # Time dimension
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True, doc="Price data timestamp in UTC"
    )

    # OHLC price data - using Numeric for precision
    open_price: Mapped[Decimal] = mapped_column(
        Numeric(precision=12, scale=4), nullable=False, doc="Opening price with 4 decimal precision"
    )

    high_price: Mapped[Decimal] = mapped_column(
        Numeric(precision=12, scale=4), nullable=False, doc="Highest price during the period"
    )

    low_price: Mapped[Decimal] = mapped_column(
        Numeric(precision=12, scale=4), nullable=False, doc="Lowest price during the period"
    )

    close_price: Mapped[Decimal] = mapped_column(
        Numeric(precision=12, scale=4), nullable=False, doc="Closing price with 4 decimal precision"
    )

    # Volume data
    volume: Mapped[int] = mapped_column(
        BigInteger, nullable=False, doc="Trading volume (number of shares)"
    )

    # Adjusted close for stock splits and dividends
    adjusted_close: Mapped[Decimal | None] = mapped_column(
        Numeric(precision=12, scale=4), nullable=True, doc="Split and dividend adjusted close price"
    )

    # Time period identifier
    interval: Mapped[str] = mapped_column(
        String(10), nullable=False, default="1d", doc="Data interval (e.g., '1d', '1h', '5m')"
    )

    # Data quality indicators
    is_validated: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, doc="Whether price data has been validated"
    )

    data_source: Mapped[str] = mapped_column(
        String(50), nullable=False, default="yahoo_finance", doc="Source of the price data"
    )

    # Cache freshness tracking
    last_fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        doc="When this data was last fetched from the provider"
    )

    # Optional market indicators
    market_cap: Mapped[Decimal | None] = mapped_column(
        Numeric(precision=20, scale=2),
        nullable=True,
        doc="Market capitalization at this point in time",
    )

    # Technical analysis helpers
    price_change: Mapped[Decimal | None] = mapped_column(
        Numeric(precision=12, scale=4), nullable=True, doc="Price change from previous period"
    )

    price_change_percent: Mapped[Decimal | None] = mapped_column(
        Numeric(precision=8, scale=4),
        nullable=True,
        doc="Percentage price change from previous period",
    )

    # Database constraints
    __table_args__ = (
        # Unique constraint to prevent duplicate entries
        Index(
            "ix_stock_prices_symbol_timestamp_interval",
            "symbol",
            "timestamp",
            "interval",
            unique=True,
        ),
        # Time-series query optimization
        Index("ix_stock_prices_timestamp_symbol", "timestamp", "symbol"),
        # Symbol-based queries optimization
        Index("ix_stock_prices_symbol_timestamp_desc", "symbol", desc("timestamp")),
        # Cache freshness optimization
        Index("ix_stock_prices_freshness", "symbol", "interval", desc("last_fetched_at")),
        # Data quality constraints
        CheckConstraint("open_price > 0", name="ck_stock_prices_open_positive"),
        CheckConstraint("high_price > 0", name="ck_stock_prices_high_positive"),
        CheckConstraint("low_price > 0", name="ck_stock_prices_low_positive"),
        CheckConstraint("close_price > 0", name="ck_stock_prices_close_positive"),
        CheckConstraint("volume >= 0", name="ck_stock_prices_volume_non_negative"),
        CheckConstraint("high_price >= low_price", name="ck_stock_prices_high_gte_low"),
        CheckConstraint("high_price >= open_price", name="ck_stock_prices_high_gte_open"),
        CheckConstraint("high_price >= close_price", name="ck_stock_prices_high_gte_close"),
        CheckConstraint("low_price <= open_price", name="ck_stock_prices_low_lte_open"),
        CheckConstraint("low_price <= close_price", name="ck_stock_prices_low_lte_close"),
        CheckConstraint(
            "adjusted_close IS NULL OR adjusted_close > 0",
            name="ck_stock_prices_adjusted_close_positive",
        ),
        CheckConstraint(
            "price_change_percent IS NULL OR price_change_percent >= -100.0",
            name="ck_stock_prices_change_percent_valid",
        ),
        CheckConstraint(
            "market_cap IS NULL OR market_cap > 0", name="ck_stock_prices_market_cap_positive"
        ),
        CheckConstraint(
            "interval IN ('1m', '2m', '5m', '15m', '30m', '60m', '90m', '1h', '1d', '5d', '1wk', '1mo', '3mo')",
            name="ck_stock_prices_valid_interval",
        ),
        CheckConstraint(
            "data_source IN ('yahoo_finance', 'manual', 'mock', 'ib')",
            name="ck_stock_prices_valid_data_source",
        ),
    )

    def __repr__(self) -> str:
        """String representation showing key identification fields."""
        return (
            f"<StockPrice(symbol='{self.symbol}', "
            f"timestamp='{self.timestamp}', "
            f"close={self.close_price}, "
            f"volume={self.volume})>"
        )

    @property
    def price_range(self) -> Decimal:
        """Calculate the price range (high - low) for this period."""
        return self.high_price - self.low_price

    @property
    def typical_price(self) -> Decimal:
        """Calculate typical price: (high + low + close) / 3."""
        return (self.high_price + self.low_price + self.close_price) / 3

    @property
    def is_up_day(self) -> bool:
        """Check if close price is higher than open price."""
        return self.close_price > self.open_price

    @property
    def body_size(self) -> Decimal:
        """Calculate candle body size (absolute difference between open and close)."""
        return abs(self.close_price - self.open_price)

    @property
    def upper_shadow(self) -> Decimal:
        """Calculate upper shadow (wick) size."""
        return self.high_price - max(self.open_price, self.close_price)

    @property
    def lower_shadow(self) -> Decimal:
        """Calculate lower shadow (wick) size."""
        return min(self.open_price, self.close_price) - self.low_price

    def to_ohlcv_dict(self) -> dict:
        """Convert to OHLCV dictionary format for technical analysis.

        Returns:
            dict: OHLCV data with float values for compatibility
        """
        return {
            "open": float(self.open_price),
            "high": float(self.high_price),
            "low": float(self.low_price),
            "close": float(self.close_price),
            "volume": self.volume,
            "timestamp": self.timestamp,
            "symbol": self.symbol,
        }
