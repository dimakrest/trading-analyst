"""Stock sector cache model.

Caches the stock→sector ETF mapping from Yahoo Finance.
Sector info rarely changes, so this avoids repeated Yahoo API calls.
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

    __table_args__ = (
        Index("ix_stock_sectors_sector_etf", "sector_etf"),
    )
