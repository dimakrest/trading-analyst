"""Live20 evaluation logic shared between service and arena agent.

This module contains the core scoring logic for the Live20 mean reversion strategy.
Trend is a non-scoring eligibility filter; 4 remaining criteria use configurable
weights that must sum to 100.

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
        score_for_long: Points awarded when criterion aligns (0-100 depending on weights)
    """

    name: str
    value: str
    aligned_for_long: bool
    score_for_long: int


class Live20Evaluator:
    """Core evaluation logic for Live20 mean reversion strategy.

    Evaluates stocks using:
    1. Trend filter (10-day) - eligibility only, contributes 0 score
    2. MA20 Distance - weighted score
    3. Candle Pattern - weighted score
    4. Volume - weighted score
    5. Momentum (CCI or RSI-2) - weighted score

    Mean Reversion Logic:
    - Trend must be bearish (eligibility filter)
    - LONG: Trend eligible + at least 2 of 4 non-trend criteria aligned
    - NO_SETUP: Trend ineligible or fewer than 2 non-trend criteria aligned

    Note:
        Requires minimum 25 price bars for accurate evaluation. The calling
        service/agent is responsible for validating data sufficiency before
        calling evaluate_criteria().
    """

    DEFAULT_SIGNAL_SCORES = {
        "volume": 25,
        "candle": 25,
        "momentum": 25,
        "ma20_distance": 25,
    }
    WEIGHT_PER_CRITERION = 25  # Backward-compatibility constant for callers/tests
    MA20_DISTANCE_THRESHOLD = 5.0  # 5% threshold for "far" from MA20
    MIN_CRITERIA_FOR_SETUP = 3  # Legacy threshold including trend
    MIN_NON_TREND_CRITERIA_FOR_SETUP = 2

    @classmethod
    def normalize_signal_scores(cls, signal_scores: dict[str, int] | None) -> dict[str, int]:
        """Normalize and validate signal score weights.

        Missing keys fall back to defaults, enabling backward compatibility with
        historical simulations/configs that predate configurable scores.

        Args:
            signal_scores: Optional score map for keys:
                volume, candle, momentum, ma20_distance

        Returns:
            Normalized score map containing all required keys.

        Raises:
            ValueError: If any score is invalid or total does not equal 100.
        """
        normalized: dict[str, int] = {}
        source = signal_scores or {}

        for key, default_value in cls.DEFAULT_SIGNAL_SCORES.items():
            raw_value = source.get(key, default_value)
            if not isinstance(raw_value, int):
                raise ValueError(f"Signal score '{key}' must be an integer (got {raw_value!r})")
            if raw_value < 0 or raw_value > 100:
                raise ValueError(
                    f"Signal score '{key}' must be in range 0-100 (got {raw_value})"
                )
            normalized[key] = raw_value

        total = sum(normalized.values())
        if total != 100:
            raise ValueError(
                "Signal scores must sum to 100 "
                f"(got {total}: volume={normalized['volume']}, "
                f"candle={normalized['candle']}, momentum={normalized['momentum']}, "
                f"ma20_distance={normalized['ma20_distance']})"
            )

        return normalized

    def evaluate_criteria(
        self,
        opens: list[float],
        highs: list[float],
        lows: list[float],
        closes: list[float],
        volumes: list[float],
        scoring_algorithm: ScoringAlgorithm = ScoringAlgorithm.CCI,
        signal_scores: dict[str, int] | None = None,
    ) -> tuple[list[CriterionResult], VolumeSignalAnalysis, MomentumAnalysis, str]:
        """Evaluate all 5 criteria for mean reversion strategy.

        Args:
            opens: Opening prices (oldest to newest)
            highs: High prices
            lows: Low prices
            closes: Closing prices
            volumes: Volume data
            scoring_algorithm: Scoring algorithm for momentum criterion (default CCI)
            signal_scores: Weight configuration for non-trend criteria

        Returns:
            Tuple of:
                - criteria: List of 5 CriterionResult objects
                - volume_signal: VolumeSignalAnalysis with RVOL and approach
                - momentum_analysis: CCIAnalysis or RSI2Analysis (depends on algorithm)
                - candle_explanation: Human-readable pattern explanation
        """
        criteria = []
        weights = self.normalize_signal_scores(signal_scores)

        # 1. Recent Trend (10-day) - eligibility filter only (non-scoring)
        trend = detect_trend(closes, period=10)
        criteria.append(
            CriterionResult(
                name="trend",
                value=trend.value,
                aligned_for_long=trend == TrendDirection.BEARISH,
                score_for_long=0,
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
                score_for_long=weights["ma20_distance"],
            )
        )

        # 3. Candle Pattern (multi-day priority: 3-day > 2-day > 1-day)
        multi_day_result = analyze_multi_day_patterns(opens, highs, lows, closes, trend)
        criteria.append(
            CriterionResult(
                name="candle",
                value=multi_day_result.pattern_name,
                aligned_for_long=multi_day_result.aligned_for_long,
                score_for_long=weights["candle"],
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
                score_for_long=weights["volume"],
            )
        )

        # 5. Momentum criterion - CCI or RSI-2
        # NOTE: Criterion name standardization - both use "momentum" for consistency
        # in name-based lookups. Alternative: keep algorithm-specific names ("cci"/"rsi2")
        # Current choice: "momentum" for both (generic, algorithm-agnostic)
        if scoring_algorithm == ScoringAlgorithm.RSI2:
            rsi2_analysis = analyze_rsi2(closes)
            weighted_momentum_score = int(
                round(weights["momentum"] * (rsi2_analysis.long_score / 20))
            )

            criteria.append(
                CriterionResult(
                    name="momentum",  # Standardized name (same as CCI below)
                    value=f"RSI-2: {rsi2_analysis.value:.0f}",
                    aligned_for_long=weighted_momentum_score > 0,
                    score_for_long=weighted_momentum_score,
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
                    score_for_long=weights["momentum"],
                )
            )
            momentum_analysis = cci_analysis

        return criteria, volume_signal, momentum_analysis, candle_explanation

    def determine_direction_and_score(self, criteria: list[CriterionResult]) -> tuple[str, int]:
        """Determine direction and calculate score based on LONG criteria alignment.

        Trend is an eligibility filter:
        - If trend is not bearish, direction is always NO_SETUP.
        - If trend is bearish, LONG requires at least 2 aligned non-trend criteria.

        Args:
            criteria: List of CriterionResult from evaluate_criteria()

        Returns:
            Tuple of (direction, score) where direction is LONG/NO_SETUP
        """
        trend_criterion = next((c for c in criteria if c.name == "trend"), None)
        if trend_criterion is None:
            raise ValueError("Trend criterion is required for direction determination")

        signal_criteria = [c for c in criteria if c.name != "trend"]
        non_trend_aligned = sum(1 for c in signal_criteria if c.aligned_for_long)
        score = sum(c.score_for_long for c in signal_criteria if c.aligned_for_long)

        if (
            trend_criterion.aligned_for_long
            and non_trend_aligned >= self.MIN_NON_TREND_CRITERIA_FOR_SETUP
        ):
            direction = Live20Direction.LONG
        else:
            direction = Live20Direction.NO_SETUP

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
