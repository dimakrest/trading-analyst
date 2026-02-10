"""Trading recommendation model for Live20 evaluator results."""
from datetime import date
from decimal import Decimal
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import Boolean
from sqlalchemy import CheckConstraint
from sqlalchemy import Date
from sqlalchemy import ForeignKey
from sqlalchemy import Index
from sqlalchemy import Integer
from sqlalchemy import Numeric
from sqlalchemy import String
from sqlalchemy import Text
from sqlalchemy import desc
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.live20_run import Live20Run


class RecommendationDecision(str, Enum):
    """Valid recommendation decisions for Live20.

    Direction-based system:
    - LONG: Bullish setup detected
    - SHORT: Bearish setup detected
    - NO_SETUP: No actionable setup
    """

    LONG = "LONG"
    SHORT = "SHORT"
    NO_SETUP = "NO_SETUP"


class RecommendationSource(str, Enum):
    """Source/type of recommendation."""

    LIVE_20 = "live_20"


class Recommendation(Base):
    """Trading recommendation from Live20 deterministic evaluator."""

    __tablename__ = "recommendations"

    # Input
    stock: Mapped[str] = mapped_column(
        String(10), nullable=False, index=True, doc="Stock symbol (e.g., 'AAPL')"
    )

    analysis_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
        index=True,
        doc="Historical analysis date for Arena simulations. Null for live recommendations.",
    )

    # Evaluator Response Fields
    recommendation: Mapped[str] = mapped_column(
        String(20), nullable=False, doc="LONG, SHORT, or NO_SETUP (Live20 directions)"
    )

    entry_price: Mapped[Decimal | None] = mapped_column(
        Numeric(precision=12, scale=4), nullable=True, doc="Recommended entry price"
    )

    stop_loss: Mapped[Decimal | None] = mapped_column(
        Numeric(precision=12, scale=4), nullable=True, doc="Recommended stop loss price"
    )

    take_profit: Mapped[Decimal | None] = mapped_column(
        Numeric(precision=12, scale=4), nullable=True, doc="Recommended take profit price"
    )

    reasoning: Mapped[str] = mapped_column(
        Text, nullable=False, doc="Evaluator's reasoning for the recommendation"
    )

    confidence_score: Mapped[int] = mapped_column(
        Integer, nullable=False, doc="Confidence score 0-100"
    )

    # Recommendation source/type
    source: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        index=True,
        doc="Source of recommendation: 'live_20', etc.",
    )

    # Live 20 specific fields (nullable, only populated for live_20 source)
    live20_trend_direction: Mapped[str | None] = mapped_column(
        String(10), nullable=True, doc="10-day trend direction: 'up', 'down', 'sideways'"
    )
    live20_trend_aligned: Mapped[bool | None] = mapped_column(
        Boolean, nullable=True, doc="Whether trend aligns with direction for mean reversion"
    )
    live20_ma20_distance_pct: Mapped[Decimal | None] = mapped_column(
        Numeric(8, 2), nullable=True, doc="Distance from MA20 as percentage (negative = below)"
    )
    live20_ma20_aligned: Mapped[bool | None] = mapped_column(
        Boolean, nullable=True, doc="Whether MA20 distance aligns with direction (>5% threshold)"
    )
    live20_candle_pattern: Mapped[str | None] = mapped_column(
        String(30),
        nullable=True,
        doc="Detected candle pattern: 'hammer', 'shooting_star', 'doji', etc.",
    )
    live20_candle_bullish: Mapped[bool | None] = mapped_column(
        Boolean, nullable=True, doc="Whether candle closed higher than open (green candle)"
    )
    live20_candle_aligned: Mapped[bool | None] = mapped_column(
        Boolean, nullable=True, doc="Whether candle pattern aligns with direction"
    )
    live20_candle_explanation: Mapped[str | None] = mapped_column(
        String(255), nullable=True, doc="Explanation of candle pattern in context (for tooltip)"
    )
    live20_volume_aligned: Mapped[bool | None] = mapped_column(
        Boolean, nullable=True, doc="Whether volume pattern aligns with direction"
    )
    live20_volume_approach: Mapped[str | None] = mapped_column(
        String(15),
        nullable=True,
        doc="Volume approach: 'exhaustion', 'accumulation', 'distribution', or null",
    )
    live20_atr: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 4), nullable=True, doc="Average True Range (14-period) for volatility context"
    )
    live20_rvol: Mapped[Decimal | None] = mapped_column(
        Numeric(8, 2), nullable=True, doc="Relative volume ratio (today/yesterday) for conviction assessment"
    )
    live20_cci_direction: Mapped[str | None] = mapped_column(
        String(10), nullable=True, doc="CCI direction: 'rising', 'falling', 'flat'"
    )
    live20_cci_value: Mapped[Decimal | None] = mapped_column(
        Numeric(8, 2), nullable=True, doc="CCI indicator value"
    )
    live20_cci_zone: Mapped[str | None] = mapped_column(
        String(15), nullable=True, doc="CCI zone: 'overbought', 'oversold', 'neutral'"
    )
    live20_cci_aligned: Mapped[bool | None] = mapped_column(
        Boolean, nullable=True, doc="Whether CCI aligns with direction"
    )
    live20_criteria_aligned: Mapped[int | None] = mapped_column(
        Integer, nullable=True, doc="Number of criteria aligned (0-5)"
    )
    live20_direction: Mapped[str | None] = mapped_column(
        String(10), nullable=True, index=True, doc="Live 20 direction: 'LONG', 'SHORT', 'NO_SETUP'"
    )
    live20_entry_strategy: Mapped[str | None] = mapped_column(
        String(20), nullable=True, doc="Entry strategy used: 'current_price', 'breakout_confirmation'"
    )
    live20_exit_strategy: Mapped[str | None] = mapped_column(
        String(20), nullable=True, doc="Exit strategy used: 'atr_based'"
    )

    live20_run_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("live20_runs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        doc="ID of the Live 20 run this recommendation belongs to",
    )

    live20_run: Mapped["Live20Run | None"] = relationship(
        "Live20Run",
        back_populates="recommendations",
        foreign_keys=[live20_run_id],
    )

    # Constraints
    __table_args__ = (
        CheckConstraint(
            "confidence_score >= 0 AND confidence_score <= 100",
            name="ck_recommendations_confidence_range",
        ),
        CheckConstraint(
            # Live20 directions; legacy values (Buy, Watchlist, Not Buy) kept for existing data
            "recommendation IN ('Buy', 'Watchlist', 'Not Buy', 'LONG', 'SHORT', 'NO_SETUP')",
            name="ck_recommendations_valid_decision",
        ),
        Index("ix_recommendations_stock_created", "stock", desc("created_at")),
    )

    def __repr__(self) -> str:
        """String representation of Recommendation."""
        return (
            f"<Recommendation(id={self.id}, stock='{self.stock}', "
            f"recommendation='{self.recommendation}')>"
        )
