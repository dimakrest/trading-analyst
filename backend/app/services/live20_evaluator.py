"""Live20 evaluation logic shared between service and arena agent.

This module contains the core scoring logic for the Live20 mean reversion strategy.
It evaluates 5 criteria (20 points each, 100 total) and determines LONG/NO_SETUP
direction based on criteria alignment.

Usage:
    evaluator = Live20Evaluator()
    criteria, volume_signal, momentum_analysis, candle_explanation = evaluator.evaluate_criteria(
        opens, highs, lows, closes, volumes
    )
    direction, score = evaluator.determine_direction_and_score(criteria)
"""

from dataclasses import dataclass
from enum import Enum

from app.indicators.cci_analysis import CCIAnalysis, CCIDirection, CCIZone, analyze_cci
from app.indicators.ma_analysis import analyze_ma_distance
from app.indicators.multi_day_patterns import analyze_multi_day_patterns
from app.indicators.rsi2_analysis import RSI2Analysis, analyze_rsi2
from app.indicators.trend import TrendDirection, detect_trend
from app.indicators.volume import VolumeSignalAnalysis, detect_volume_signal
from app.models.recommendation import ScoringAlgorithm

# Union type for momentum analysis (CCI or RSI-2)
# Note: Union type is intentional for 2 algorithms. If a third algorithm is
# ever added, refactor to a Protocol with common interface. See ticket 011.
MomentumAnalysis = CCIAnalysis | RSI2Analysis


class Live20Direction(str, Enum):
    """Live20 direction constants (LONG-only system)."""

    LONG = "LONG"
    NO_SETUP = "NO_SETUP"


@dataclass
class CriterionResult:
    """Result of evaluating a single Live20 criterion.

    Attributes:
        name: Criterion identifier (trend, ma20_distance, candle, volume, momentum)
        value: Display value for UI (e.g., "bearish", "-7.2%", "hammer", "1.5x")
        aligned_for_long: Whether criterion supports LONG setup
        score_for_long: Points awarded when direction is LONG (0-20)
    """

    name: str
    value: str
    aligned_for_long: bool
    score_for_long: int


class Live20Evaluator:
    """Core evaluation logic for Live20 mean reversion strategy.

    Evaluates stocks using 5 criteria (20 points each, 100 total):
    1. Recent Trend (10-day) - Looking for counter-trend setup
    2. MA20 Distance - Price stretched from moving average (>5%)
    3. Candle Pattern - Reversal patterns (multi-day: Morning Star, Piercing Line, etc.)
    4. Volume (Dual Approach) - Exhaustion OR Accumulation/Distribution
    5. Momentum (CCI or RSI-2) - Momentum confirmation

    Mean Reversion Logic:
    - LONG: Downtrend + far below MA20 (expecting bounce)
    - NO_SETUP: Less than 3 criteria aligned

    Note:
        Requires minimum 25 price bars for accurate evaluation. The calling
        service/agent is responsible for validating data sufficiency before
        calling evaluate_criteria().
    """

    WEIGHT_PER_CRITERION = 20
    MA20_DISTANCE_THRESHOLD = 5.0  # 5% threshold for "far" from MA20
    MIN_CRITERIA_FOR_SETUP = 3

    def evaluate_criteria(
        self,
        opens: list[float],
        highs: list[float],
        lows: list[float],
        closes: list[float],
        volumes: list[float],
        scoring_algorithm: ScoringAlgorithm = ScoringAlgorithm.CCI,
    ) -> tuple[list[CriterionResult], VolumeSignalAnalysis, MomentumAnalysis, str]:
        """Evaluate all 5 criteria for mean reversion strategy.

        Args:
            opens: Opening prices (oldest to newest)
            highs: High prices
            lows: Low prices
            closes: Closing prices
            volumes: Volume data
            scoring_algorithm: Scoring algorithm for momentum criterion (default CCI)

        Returns:
            Tuple of:
                - criteria: List of 5 CriterionResult objects
                - volume_signal: VolumeSignalAnalysis with RVOL and approach
                - momentum_analysis: CCIAnalysis or RSI2Analysis (depends on algorithm)
                - candle_explanation: Human-readable pattern explanation
        """
        criteria = []

        # 1. Recent Trend (10-day) - MEAN REVERSION: opposite trend is good
        trend = detect_trend(closes, period=10)
        criteria.append(
            CriterionResult(
                name="trend",
                value=trend.value,
                aligned_for_long=trend == TrendDirection.BEARISH,
                score_for_long=self.WEIGHT_PER_CRITERION,
            )
        )

        # 2. MA20 Distance - Price stretched from MA
        ma_analysis = analyze_ma_distance(closes, period=20)
        distance_pct = ma_analysis.distance_pct
        is_far_below = distance_pct < -self.MA20_DISTANCE_THRESHOLD
        criteria.append(
            CriterionResult(
                name="ma20_distance",
                value=f"{distance_pct:+.1f}%",
                aligned_for_long=is_far_below,
                score_for_long=self.WEIGHT_PER_CRITERION,
            )
        )

        # 3. Candle Pattern (multi-day priority: 3-day > 2-day > 1-day)
        multi_day_result = analyze_multi_day_patterns(opens, highs, lows, closes, trend)
        criteria.append(
            CriterionResult(
                name="candle",
                value=multi_day_result.pattern_name,
                aligned_for_long=multi_day_result.aligned_for_long,
                score_for_long=self.WEIGHT_PER_CRITERION,
            )
        )
        candle_explanation = multi_day_result.explanation

        # 4. Volume - Dual approach (Exhaustion OR Accumulation/Distribution)
        volume_signal = detect_volume_signal(opens, closes, volumes)
        criteria.append(
            CriterionResult(
                name="volume",
                value=f"{volume_signal.rvol}x",
                aligned_for_long=volume_signal.aligned_for_long,
                score_for_long=self.WEIGHT_PER_CRITERION,
            )
        )

        # 5. Momentum criterion - CCI or RSI-2
        # NOTE: Criterion name standardization - both use "momentum" for consistency
        # in name-based lookups. Alternative: keep algorithm-specific names ("cci"/"rsi2")
        # Current choice: "momentum" for both (generic, algorithm-agnostic)
        if scoring_algorithm == ScoringAlgorithm.RSI2:
            rsi2_analysis = analyze_rsi2(closes)

            criteria.append(
                CriterionResult(
                    name="momentum",  # Standardized name (same as CCI below)
                    value=f"RSI-2: {rsi2_analysis.value:.0f}",
                    aligned_for_long=rsi2_analysis.long_score > 0,
                    score_for_long=rsi2_analysis.long_score,
                )
            )
            momentum_analysis: MomentumAnalysis = rsi2_analysis
        else:
            # Existing CCI logic (unchanged)
            cci_analysis = analyze_cci(highs, lows, closes, period=14)

            # LONG alignment logic
            aligned_for_long = (
                cci_analysis.zone == CCIZone.OVERSOLD
                and cci_analysis.direction in (CCIDirection.RISING, CCIDirection.FLAT)
            ) or (
                cci_analysis.zone == CCIZone.NEUTRAL and cci_analysis.direction == CCIDirection.RISING
            )

            criteria.append(
                CriterionResult(
                    name="momentum",  # Changed from "cci" to "momentum" for consistency
                    value=cci_analysis.zone.value,
                    aligned_for_long=aligned_for_long,
                    score_for_long=self.WEIGHT_PER_CRITERION,
                )
            )
            momentum_analysis = cci_analysis

        return criteria, volume_signal, momentum_analysis, candle_explanation

    def determine_direction_and_score(self, criteria: list[CriterionResult]) -> tuple[str, int]:
        """Determine direction and calculate score based on LONG criteria alignment.

        LONG-only: returns LONG when >= 3 criteria aligned, NO_SETUP otherwise.

        Args:
            criteria: List of CriterionResult from evaluate_criteria()

        Returns:
            Tuple of (direction, score) where direction is LONG/NO_SETUP
        """
        long_aligned = sum(1 for c in criteria if c.aligned_for_long)

        if long_aligned >= self.MIN_CRITERIA_FOR_SETUP:
            direction = Live20Direction.LONG
            score = sum(c.score_for_long for c in criteria if c.aligned_for_long)
        else:
            direction = Live20Direction.NO_SETUP
            score = sum(c.score_for_long for c in criteria if c.aligned_for_long)

        return direction, score

    def get_ma20_distance(self, closes: list[float]) -> float:
        """Get MA20 distance percentage.

        Args:
            closes: Closing prices

        Returns:
            Distance percentage (positive = above MA, negative = below MA)
        """
        ma_analysis = analyze_ma_distance(closes, period=20)
        return ma_analysis.distance_pct
