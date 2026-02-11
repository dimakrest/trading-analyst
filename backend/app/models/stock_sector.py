"""Stock metadata cache model.

Caches stock metadata (sector, name, exchange) from Yahoo Finance.
This info rarely changes, so caching avoids repeated Yahoo API calls.
"""
from sqlalchemy import String, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class StockSector(Base):
    """Cached stock-to-sector mapping."""

    __tablename__ = "stock_sectors"

    symbol: Mapped[str] = mapped_column(
        String(10), nullable=False, unique=True, index=True,
        doc="Stock symbol (e.g., 'AAPL')"
    )
    sector: Mapped[str | None] = mapped_column(
        String(50), nullable=True,
        doc="Yahoo Finance sector name (e.g., 'Technology')"
    )
    sector_etf: Mapped[str | None] = mapped_column(
        String(10), nullable=True,
        doc="Mapped SPDR ETF symbol (e.g., 'XLK')"
    )
    industry: Mapped[str | None] = mapped_column(
        String(100), nullable=True,
        doc="Yahoo Finance industry (e.g., 'Consumer Electronics')"
    )
    name: Mapped[str | None] = mapped_column(
        String(200), nullable=True,
        doc="Company name (e.g., 'Apple Inc.')"
    )
    exchange: Mapped[str | None] = mapped_column(
        String(50), nullable=True,
        doc="Stock exchange (e.g., 'NASDAQ', 'NYSE')"
    )

    __table_args__ = (
        Index("ix_stock_sectors_sector_etf", "sector_etf"),
    )
