"""Live20 agent adapted for arena simulations.

This agent uses Live20Evaluator for scoring and filters to LONG-only setups.
It evaluates historical price data and returns trading decisions for arena simulations.
"""

import logging
from datetime import date
from typing import ClassVar

from app.models.recommendation import ScoringAlgorithm
from app.services.arena.agent_protocol import AgentDecision, BaseAgent, PriceBar
from app.services.live20_evaluator import Live20Evaluator

logger = logging.getLogger(__name__)


class Live20ArenaAgent(BaseAgent):
    """Live20 mean reversion agent for arena simulations.

    Uses Live20Evaluator for the 5-criterion scoring and filters to LONG-only:
    1. Recent Trend (10-day) - Counter-trend setup
    2. MA20 Distance - Price stretched from moving average (>5%)
    3. Candle Pattern - Reversal patterns (multi-day: Morning Star, Piercing Line, etc.)
    4. Volume - Exhaustion or Accumulation/Distribution
    5. CCI - Momentum confirmation

    Returns BUY signal when score >= min_buy_score (configurable, default 60).
    """

    DEFAULT_MIN_BUY_SCORE: ClassVar[int] = 60

    def __init__(self, config: dict | None = None) -> None:
        """Initialize agent with Live20Evaluator and optional configuration.

        Args:
            config: Optional configuration dict. Supported keys:
                - min_buy_score: Minimum score threshold for BUY signal (default: 60)
                - scoring_algorithm: Scoring algorithm ('cci' or 'rsi2', default: 'cci')
        """
        super().__init__(config)
        self._evaluator = Live20Evaluator()
        self._min_buy_score = self._config.get("min_buy_score", self.DEFAULT_MIN_BUY_SCORE)

        # Validate and convert scoring_algorithm with error handling
        scoring_algorithm_str = self._config.get("scoring_algorithm", "cci")
        try:
            self._scoring_algorithm = ScoringAlgorithm(scoring_algorithm_str)
        except ValueError:
            # Invalid algorithm in config - log error and fall back to CCI
            # This prevents arena simulations from crashing on bad config
            logger.error(
                f"Invalid scoring_algorithm in agent config: {scoring_algorithm_str}. "
                f"Falling back to CCI."
            )
            self._scoring_algorithm = ScoringAlgorithm.CCI

    # Expose constants for backward compatibility (used in tests)
    @property
    def WEIGHT_PER_CRITERION(self) -> int:
        """Weight per criterion (20 points each)."""
        return self._evaluator.WEIGHT_PER_CRITERION

    @property
    def MA20_DISTANCE_THRESHOLD(self) -> float:
        """MA20 distance threshold (5%)."""
        return self._evaluator.MA20_DISTANCE_THRESHOLD

    @property
    def MIN_CRITERIA_FOR_SETUP(self) -> int:
        """Minimum criteria for valid setup (3)."""
        return self._evaluator.MIN_CRITERIA_FOR_SETUP

    @property
    def MIN_SCORE_FOR_SIGNAL(self) -> int:
        """Minimum score for BUY signal (backward compatibility property)."""
        return self._min_buy_score

    @property
    def min_buy_score(self) -> int:
        """Minimum score threshold for BUY signal."""
        return self._min_buy_score

    @property
    def name(self) -> str:
        """Human-readable agent name for display in UI."""
        return "Live20"

    @property
    def required_lookback_days(self) -> int:
        """Number of historical days needed before first decision.

        Live20 requires 60 days of data for MA20 + buffer.
        """
        return 60

    async def evaluate(
        self,
        symbol: str,
        price_history: list[PriceBar],
        current_date: date,
        has_open_position: bool,
    ) -> AgentDecision:
        """Evaluate symbol for LONG setup using Live20 criteria.

        Args:
            symbol: Stock symbol to evaluate
            price_history: Historical price data (oldest to newest)
            current_date: Current simulation date
            has_open_position: Whether we already hold this symbol

        Returns:
            AgentDecision with action, score, and reasoning
        """
        # No signal if already holding position (no pyramiding)
        if has_open_position:
            return AgentDecision(
                symbol=symbol,
                action="HOLD",
                score=None,
                reasoning="Already holding position",
            )

        # Need minimum data
        if len(price_history) < 25:
            return AgentDecision(
                symbol=symbol,
                action="NO_SIGNAL",
                score=None,
                reasoning=f"Insufficient data ({len(price_history)} bars)",
            )

        # Extract price arrays
        opens = [float(bar.open) for bar in price_history]
        highs = [float(bar.high) for bar in price_history]
        lows = [float(bar.low) for bar in price_history]
        closes = [float(bar.close) for bar in price_history]
        volumes = [float(bar.volume) for bar in price_history]

        # Evaluate criteria using shared evaluator
        criteria, _, _, _ = self._evaluator.evaluate_criteria(
            opens, highs, lows, closes, volumes,
            scoring_algorithm=self._scoring_algorithm,
        )

        # Sum-based scoring to support graduated algorithms (equivalent to count*20 for CCI)
        # NOTE: Arena agent is LONG-only by design (no SHORT signal support)
        aligned_count = sum(1 for c in criteria if c.aligned_for_long)
        score = sum(c.score_for_long for c in criteria if c.aligned_for_long)

        # Build reasoning
        aligned_criteria = [c.name for c in criteria if c.aligned_for_long]
        not_aligned = [c.name for c in criteria if not c.aligned_for_long]

        reasoning_parts = [
            f"Score: {score}/100 ({aligned_count}/5 criteria aligned)",
            f"Aligned: {', '.join(aligned_criteria) if aligned_criteria else 'none'}",
            f"Not aligned: {', '.join(not_aligned) if not_aligned else 'none'}",
        ]

        # Determine action (LONG-only)
        if score >= self._min_buy_score:
            action = "BUY"
        else:
            action = "NO_SIGNAL"

        return AgentDecision(
            symbol=symbol,
            action=action,
            score=score,
            reasoning="; ".join(reasoning_parts),
        )
