"""Live 20 service for mean reversion stock analysis."""

import logging
import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.recommendation import Recommendation, RecommendationSource
from app.services.data_service import DataService
from app.services.live20_evaluator import (
    Live20Direction,
    Live20Evaluator,
)
from app.services.pricing_strategies import PricingCalculator, PricingConfig
from app.utils.technical_indicators import calculate_atr_percentage

logger = logging.getLogger(__name__)


@dataclass
class Live20Result:
    """Result of Live 20 analysis for a single symbol.

    Attributes:
        symbol: Stock symbol analyzed
        status: Analysis status ("success" or "error")
        error_message: Error details if status is "error"
        recommendation: Created Recommendation object if status is "success"
    """

    symbol: str
    status: str
    error_message: str | None = None
    recommendation: Recommendation | None = None


class Live20Service:
    """Service for Live 20 mean reversion analysis.

    Delegates evaluation logic to Live20Evaluator and handles:
    - Database operations (fetching price data, saving recommendations)
    - Pricing calculations

    See Live20Evaluator for details on the 5 criteria and scoring logic.
    """

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        """Initialize Live20Service with database session factory.

        Args:
            session_factory: Factory for creating async database sessions.
        """
        self.session_factory = session_factory
        self._evaluator = Live20Evaluator()

    async def _analyze_symbol(self, symbol: str, pricing_config: PricingConfig) -> Live20Result:
        """Analyze a single symbol and save result."""
        try:
            # Validate symbol
            if not symbol or len(symbol) > 10:
                return Live20Result(
                    symbol=symbol,
                    status="error",
                    error_message=f"Invalid symbol: {symbol}",
                )

            # Create DataService with session_factory
            data_service = DataService(session_factory=self.session_factory)

            # Fetch price data (60 days for MA20 + buffer)
            end_date = datetime.now(timezone.utc)
            start_date = end_date - timedelta(days=60)

            price_records = await data_service.get_price_data(
                symbol=symbol,
                start_date=start_date,
                end_date=end_date,
                interval="1d",
            )

            if not price_records or len(price_records) < 25:
                return Live20Result(
                    symbol=symbol,
                    status="error",
                    error_message=f"Insufficient data ({len(price_records) if price_records else 0} records)",
                )

            # Extract arrays
            opens = [float(r.open_price) for r in price_records]
            highs = [float(r.high_price) for r in price_records]
            lows = [float(r.low_price) for r in price_records]
            closes = [float(r.close_price) for r in price_records]
            volumes = [float(r.volume) for r in price_records]

            # Calculate ATR independently (for ALL stocks, regardless of direction)
            atr_percentage = calculate_atr_percentage(highs, lows, closes)

            # Evaluate all criteria
            (
                criteria,
                volume_signal,
                cci_analysis,
                candle_explanation,
            ) = self._evaluator.evaluate_criteria(opens, highs, lows, closes, volumes)

            # Determine direction based on aligned criteria
            direction, score = self._evaluator.determine_direction_and_score(criteria)

            # Calculate pricing using strategy config
            calculator = PricingCalculator(pricing_config)
            pricing_result = calculator.calculate(direction, closes, highs, lows)

            # Lookup sector ETF (cheap DB cache hit, non-blocking)
            sector_etf = None
            try:
                async with self.session_factory() as session:
                    sector_etf = await data_service.get_sector_etf(symbol, session)
            except Exception as e:
                # Non-critical - don't fail analysis if sector lookup fails
                logger.warning(f"Failed to fetch sector ETF for {symbol}: {e}")

            # Create recommendation with pricing
            recommendation = Recommendation(
                stock=symbol,
                source=RecommendationSource.LIVE_20.value,
                recommendation=direction,  # Maps to recommendation field
                confidence_score=score,
                # Use calculated prices or None for NO_SETUP
                entry_price=pricing_result.entry_price if pricing_result else None,
                stop_loss=pricing_result.stop_loss if pricing_result else None,
                reasoning="Live 20 mean reversion analysis",
                # Strategy fields
                live20_entry_strategy=(
                    pricing_result.entry_strategy.value if pricing_result else None
                ),
                live20_exit_strategy=(
                    pricing_result.exit_strategy.value if pricing_result else None
                ),
                # Live 20 specific fields
                live20_trend_direction=criteria[0].value,
                live20_trend_aligned=(
                    (direction == Live20Direction.LONG and criteria[0].aligned_for_long)
                    or (direction == Live20Direction.SHORT and criteria[0].aligned_for_short)
                ),
                live20_ma20_distance_pct=Decimal(str(self._evaluator.get_ma20_distance(closes))),
                live20_ma20_aligned=(
                    (direction == Live20Direction.LONG and criteria[1].aligned_for_long)
                    or (direction == Live20Direction.SHORT and criteria[1].aligned_for_short)
                ),
                live20_candle_pattern=criteria[2].value,
                live20_candle_bullish=closes[-1] > opens[-1],  # Green candle if close > open
                live20_candle_aligned=(
                    (direction == Live20Direction.LONG and criteria[2].aligned_for_long)
                    or (direction == Live20Direction.SHORT and criteria[2].aligned_for_short)
                ),
                live20_candle_explanation=candle_explanation,
                live20_volume_aligned=(
                    (direction == Live20Direction.LONG and criteria[3].aligned_for_long)
                    or (direction == Live20Direction.SHORT and criteria[3].aligned_for_short)
                ),
                live20_volume_approach=volume_signal.approach.value,
                live20_atr=Decimal(str(round(atr_percentage, 4))) if atr_percentage is not None else None,
                live20_rvol=Decimal(str(volume_signal.rvol)) if math.isfinite(volume_signal.rvol) else None,
                live20_cci_direction=cci_analysis.direction.value,
                live20_cci_value=Decimal(str(cci_analysis.value)),
                live20_cci_zone=cci_analysis.zone.value,
                live20_cci_aligned=(
                    (direction == Live20Direction.LONG and criteria[4].aligned_for_long)
                    or (direction == Live20Direction.SHORT and criteria[4].aligned_for_short)
                ),
                live20_criteria_aligned=sum(
                    1
                    for c in criteria
                    if (direction == Live20Direction.LONG and c.aligned_for_long)
                    or (direction == Live20Direction.SHORT and c.aligned_for_short)
                ),
                live20_direction=direction,
                live20_sector_etf=sector_etf,
            )

            # Save to database using separate short-lived session
            async with self.session_factory() as session:
                session.add(recommendation)
                await session.commit()
                await session.refresh(recommendation)

            return Live20Result(
                symbol=symbol,
                status="success",
                recommendation=recommendation,
            )

        except Exception as e:
            logger.error(f"Error analyzing {symbol}: {e}", exc_info=True)
            return Live20Result(
                symbol=symbol,
                status="error",
                error_message=str(e),
            )
