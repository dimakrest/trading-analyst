"""Live20 evaluation logic shared between service and arena agent.

This module contains the core scoring logic for the Live20 mean reversion strategy.
It evaluates 5 criteria (20 points each, 100 total) and determines LONG/SHORT/NO_SETUP
direction based on criteria alignment.

Usage:
    evaluator = Live20Evaluator()
    criteria, volume_signal, cci_analysis, candle_explanation = evaluator.evaluate_criteria(
        opens, highs, lows, closes, volumes
    )
    direction, score = evaluator.determine_direction_and_score(criteria)
"""

from dataclasses import dataclass
from enum import Enum

from app.indicators.cci_analysis import CCIAnalysis, CCIDirection, CCIZone, analyze_cci
from app.indicators.ma_analysis import analyze_ma_distance
from app.indicators.multi_day_patterns import analyze_multi_day_patterns
from app.indicators.trend import TrendDirection, detect_trend
from app.indicators.volume import VolumeSignalAnalysis, detect_volume_signal


class Live20Direction(str, Enum):
    """Live20 direction constants."""

    LONG = "LONG"
    SHORT = "SHORT"
    NO_SETUP = "NO_SETUP"


@dataclass
class CriterionResult:
    """Result of evaluating a single Live20 criterion.

    Attributes:
        name: Criterion identifier (trend, ma20_distance, candle, volume, cci)
        value: Display value for UI (e.g., "bearish", "-7.2%", "hammer", "1.5x")
        aligned_for_long: Whether criterion supports LONG setup
        aligned_for_short: Whether criterion supports SHORT setup
        score: Point value (always 20 in current implementation)
    """

    name: str
    value: str
    aligned_for_long: bool
    aligned_for_short: bool
    score: int


class Live20Evaluator:
    """Core evaluation logic for Live20 mean reversion strategy.

    Evaluates stocks using 5 criteria (20 points each, 100 total):
    1. Recent Trend (10-day) - Looking for counter-trend setup
    2. MA20 Distance - Price stretched from moving average (>5%)
    3. Candle Pattern - Reversal patterns (multi-day: Morning Star, Piercing Line, etc.)
    4. Volume (Dual Approach) - Exhaustion OR Accumulation/Distribution
    5. CCI - Momentum confirmation (zone + direction)

    Mean Reversion Logic:
    - LONG: Downtrend + far below MA20 (expecting bounce)
    - SHORT: Uptrend + far above MA20 (expecting pullback)
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
    ) -> tuple[list[CriterionResult], VolumeSignalAnalysis, CCIAnalysis, str]:
        """Evaluate all 5 criteria for mean reversion strategy.

        Args:
            opens: Opening prices (oldest to newest)
            highs: High prices
            lows: Low prices
            closes: Closing prices
            volumes: Volume data

        Returns:
            Tuple of:
                - criteria: List of 5 CriterionResult objects
                - volume_signal: VolumeSignalAnalysis with RVOL and approach
                - cci_analysis: CCIAnalysis with value, zone, and direction
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
                aligned_for_short=trend == TrendDirection.BULLISH,
                score=self.WEIGHT_PER_CRITERION,
            )
        )

        # 2. MA20 Distance - Price stretched from MA
        ma_analysis = analyze_ma_distance(closes, period=20)
        distance_pct = ma_analysis.distance_pct
        is_far_below = distance_pct < -self.MA20_DISTANCE_THRESHOLD
        is_far_above = distance_pct > self.MA20_DISTANCE_THRESHOLD
        criteria.append(
            CriterionResult(
                name="ma20_distance",
                value=f"{distance_pct:+.1f}%",
                aligned_for_long=is_far_below,
                aligned_for_short=is_far_above,
                score=self.WEIGHT_PER_CRITERION,
            )
        )

        # 3. Candle Pattern (multi-day priority: 3-day > 2-day > 1-day)
        multi_day_result = analyze_multi_day_patterns(opens, highs, lows, closes, trend)
        criteria.append(
            CriterionResult(
                name="candle",
                value=multi_day_result.pattern_name,
                aligned_for_long=multi_day_result.aligned_for_long,
                aligned_for_short=multi_day_result.aligned_for_short,
                score=self.WEIGHT_PER_CRITERION,
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
                aligned_for_short=volume_signal.aligned_for_short,
                score=self.WEIGHT_PER_CRITERION,
            )
        )

        # 5. CCI - Momentum confirmation (zone + direction awareness)
        cci_analysis = analyze_cci(highs, lows, closes, period=14)

        # LONG: oversold (rising/flat direction) or neutral (rising direction)
        aligned_for_long = (
            cci_analysis.zone == CCIZone.OVERSOLD
            and cci_analysis.direction in (CCIDirection.RISING, CCIDirection.FLAT)
        ) or (
            cci_analysis.zone == CCIZone.NEUTRAL and cci_analysis.direction == CCIDirection.RISING
        )

        # SHORT: overbought (falling/flat direction) or neutral (falling direction)
        aligned_for_short = (
            cci_analysis.zone == CCIZone.OVERBOUGHT
            and cci_analysis.direction in (CCIDirection.FALLING, CCIDirection.FLAT)
        ) or (
            cci_analysis.zone == CCIZone.NEUTRAL and cci_analysis.direction == CCIDirection.FALLING
        )

        criteria.append(
            CriterionResult(
                name="cci",
                value=cci_analysis.zone.value,
                aligned_for_long=aligned_for_long,
                aligned_for_short=aligned_for_short,
                score=self.WEIGHT_PER_CRITERION,
            )
        )

        return criteria, volume_signal, cci_analysis, candle_explanation

    def determine_direction_and_score(self, criteria: list[CriterionResult]) -> tuple[str, int]:
        """Determine direction and calculate score based on criteria alignment.

        Args:
            criteria: List of CriterionResult from evaluate_criteria()

        Returns:
            Tuple of (direction, score) where direction is LONG/SHORT/NO_SETUP
        """
        long_aligned = sum(1 for c in criteria if c.aligned_for_long)
        short_aligned = sum(1 for c in criteria if c.aligned_for_short)

        # Determine direction
        if long_aligned >= self.MIN_CRITERIA_FOR_SETUP and long_aligned > short_aligned:
            direction = Live20Direction.LONG
            aligned_count = long_aligned
        elif short_aligned >= self.MIN_CRITERIA_FOR_SETUP and short_aligned > long_aligned:
            direction = Live20Direction.SHORT
            aligned_count = short_aligned
        else:
            direction = Live20Direction.NO_SETUP
            aligned_count = max(long_aligned, short_aligned)

        score = aligned_count * self.WEIGHT_PER_CRITERION
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
