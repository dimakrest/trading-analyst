"""Live 20 service for mean reversion stock analysis."""

import logging
import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.indicators.cci_analysis import CCIAnalysis
from app.indicators.rsi2_analysis import RSI2Analysis
from app.models.recommendation import Recommendation, RecommendationSource, ScoringAlgorithm
from app.services.data_service import DataService
from app.services.live20_evaluator import (
    Live20Direction,
    Live20Evaluator,
)
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

    See Live20Evaluator for details on the 5 criteria and scoring logic.
    """

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        scoring_algorithm: str = "cci"
    ) -> None:
        """Initialize Live20Service with database session factory.

        Args:
            session_factory: Factory for creating async database sessions.
            scoring_algorithm: Scoring algorithm to use ('cci' or 'rsi2', default 'cci')
        """
        self.session_factory = session_factory
        self._evaluator = Live20Evaluator()
        self._scoring_algorithm = ScoringAlgorithm(scoring_algorithm)

    async def _analyze_symbol(self, symbol: str) -> Live20Result:
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
                momentum_analysis,
                candle_explanation,
            ) = self._evaluator.evaluate_criteria(
                opens, highs, lows, closes, volumes,
                scoring_algorithm=self._scoring_algorithm,
            )

            # Determine direction based on aligned criteria
            direction, score = self._evaluator.determine_direction_and_score(criteria)

            # Lookup sector ETF (cheap DB cache hit, non-blocking)
            sector_etf = None
            try:
                async with self.session_factory() as session:
                    sector_etf = await data_service.get_sector_etf(symbol, session)
            except Exception as e:
                # Non-critical - don't fail analysis if sector lookup fails
                logger.warning(f"Failed to fetch sector ETF for {symbol}: {e}")

            # Create recommendation with common fields
            recommendation = Recommendation(
                stock=symbol,
                source=RecommendationSource.LIVE_20.value,
                recommendation=direction,  # Maps to recommendation field
                confidence_score=score,
                reasoning="Live 20 mean reversion analysis",
                # Common Live 20 specific fields
                live20_scoring_algorithm=self._scoring_algorithm.value,
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
                live20_criteria_aligned=sum(
                    1
                    for c in criteria
                    if (direction == Live20Direction.LONG and c.aligned_for_long)
                    or (direction == Live20Direction.SHORT and c.aligned_for_short)
                ),
                live20_direction=direction,
                live20_sector_etf=sector_etf,
            )

            # Algorithm-specific fields (mutually exclusive — never cross-populate)
            if isinstance(momentum_analysis, CCIAnalysis):
                recommendation.live20_cci_direction = momentum_analysis.direction.value
                recommendation.live20_cci_value = Decimal(str(momentum_analysis.value))
                recommendation.live20_cci_zone = momentum_analysis.zone.value
                # Find the momentum criterion using name-based lookup (not hardcoded index)
                momentum_criterion = next(
                    (c for c in criteria if c.name in ("cci", "momentum")),
                    None
                )
                if momentum_criterion is None:
                    raise ValueError("Momentum criterion not found in criteria list")
                recommendation.live20_cci_aligned = (
                    (direction == Live20Direction.LONG and momentum_criterion.aligned_for_long)
                    or (direction == Live20Direction.SHORT and momentum_criterion.aligned_for_short)
                )
                # RSI-2 fields stay NULL
            elif isinstance(momentum_analysis, RSI2Analysis):
                recommendation.live20_rsi2_value = Decimal(str(momentum_analysis.value))
                # Store direction-appropriate score (mirrors CCI's direction-aware aligned field)
                if direction == Live20Direction.LONG:
                    recommendation.live20_rsi2_score = momentum_analysis.long_score
                elif direction == Live20Direction.SHORT:
                    recommendation.live20_rsi2_score = momentum_analysis.short_score
                else:
                    # NO_SETUP: store the higher score (matches determine_direction_and_score logic)
                    recommendation.live20_rsi2_score = max(
                        momentum_analysis.long_score, momentum_analysis.short_score
                    )
                # CCI fields stay NULL (no phantom alignment data)

            # NOTE: Storing only a single rsi2_score loses directional information.
            # For RSI-2 with graduated scoring, we could store both live20_rsi2_long_score
            # and live20_rsi2_short_score to preserve full context, similar to CCI's
            # separate direction/zone/aligned fields. Current design stores only the
            # direction-appropriate score. This is a known limitation - see ticket for details.

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
