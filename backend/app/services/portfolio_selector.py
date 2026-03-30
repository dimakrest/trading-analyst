"""Portfolio selector module for Arena position selection strategies.

This module provides pure-logic portfolio selection with no DB or I/O dependencies.
It ranks qualifying signals using configurable strategies and applies shared
constraint filtering (sector cap, max open positions).

Key classes:
- QualifyingSignal: Data container for a signal eligible for selection
- PortfolioSelector: Abstract base defining the rank/select interface
- FifoSelector: Preserves original symbol list order (original Arena behavior)
- ScoreSectorSelector: Score-ranked with ATR as a tiebreaker
- EnrichedScoreSelector: Multi-factor tiebreaker cascade using signal metadata

Key functions:
- get_selector: Retrieve a selector by strategy name, with FIFO fallback
- list_selectors: Return all available strategies with names and descriptions
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from statistics import median

logger = logging.getLogger(__name__)


@dataclass
class QualifyingSignal:
    """A trading signal that qualifies for portfolio selection.

    Attributes:
        symbol: Stock ticker symbol.
        score: Numeric score from signal evaluation (0-100).
        sector: GICS sector for diversification constraints.
            None = unknown sector, treated as a unique key (never blocked).
        atr_pct: Average True Range as percentage of price.
            None = unknown, sorted to end in ATR-aware selectors.
        metadata: Optional enriched signal data from the agent.
            Keys: cci_value, cci_direction, ma_distance_pct, rvol,
                  candle_duration, candle_pattern.
            Used by EnrichedScoreSelector. None-safe: all selectors
            must handle absent metadata gracefully.
    """

    symbol: str
    score: int
    sector: str | None  # None = unknown, treated as unique sector
    atr_pct: float | None  # None = unknown, sorted to end
    metadata: dict | None = None  # None = no enriched data (backward compat)


class PortfolioSelector(ABC):
    """Base class for portfolio selection strategies.

    Subclasses implement rank() for strategy-specific ordering.
    Constraint filtering (sector cap, position limit) is shared.
    """

    @property
    @abstractmethod
    def name(self) -> str: ...

    @property
    @abstractmethod
    def description(self) -> str: ...

    @abstractmethod
    def rank(self, signals: list[QualifyingSignal]) -> list[QualifyingSignal]:
        """Strategy-specific ranking. Override this."""
        ...

    def select(
        self,
        signals: list[QualifyingSignal],
        existing_sector_counts: dict[str, int],
        current_open_count: int,
        max_per_sector: int | None = None,
        max_open_positions: int | None = None,
    ) -> list[QualifyingSignal]:
        """Rank signals then apply constraints. Returns ordered selection."""
        ranked = self.rank(signals)
        return self._apply_constraints(
            ranked, existing_sector_counts, current_open_count,
            max_per_sector, max_open_positions,
        )

    def _apply_constraints(
        self,
        ranked: list[QualifyingSignal],
        existing_sector_counts: dict[str, int],
        current_open_count: int,
        max_per_sector: int | None,
        max_open_positions: int | None,
    ) -> list[QualifyingSignal]:
        """Universal constraint filtering. Shared by all strategies."""
        selected = []
        sector_counts = dict(existing_sector_counts)
        count = current_open_count

        for signal in ranked:
            if max_open_positions is not None and count >= max_open_positions:
                break

            # Unknown sector = unique key per symbol, never blocked by cap
            sector_key = signal.sector or f"__unknown_{signal.symbol}"
            if max_per_sector is not None and sector_counts.get(sector_key, 0) >= max_per_sector:
                continue

            selected.append(signal)
            sector_counts[sector_key] = sector_counts.get(sector_key, 0) + 1
            count += 1

        return selected


class FifoSelector(PortfolioSelector):
    """No ranking — preserves original symbol list order."""

    @property
    def name(self) -> str:
        return "none"

    @property
    def description(self) -> str:
        return "No ranking — opens positions in symbol list order (original behavior)"

    def rank(self, signals: list[QualifyingSignal]) -> list[QualifyingSignal]:
        return list(signals)


class ScoreSectorSelector(PortfolioSelector):
    """Score-ranked with sector diversification and ATR tiebreaker."""

    def __init__(self, atr_preference: str) -> None:  # "low", "high", "moderate"
        self._atr_preference = atr_preference

    @property
    def name(self) -> str:
        return f"score_sector_{self._atr_preference}_atr"

    @property
    def description(self) -> str:
        descriptions = {
            "low": "Rank by score, prefer lowest ATR% (tighter stops, calmer stocks)",
            "high": "Rank by score, prefer highest ATR% (wider swings, more upside potential)",
            "moderate": "Rank by score, prefer ATR% closest to median (avoid extremes)",
        }
        return descriptions[self._atr_preference]

    def rank(self, signals: list[QualifyingSignal]) -> list[QualifyingSignal]:
        if self._atr_preference == "low":
            return sorted(
                signals,
                key=lambda s: (-s.score, s.atr_pct if s.atr_pct is not None else float("inf")),
            )
        elif self._atr_preference == "high":
            return sorted(
                signals,
                key=lambda s: (-s.score, -(s.atr_pct if s.atr_pct is not None else 0)),
            )
        else:  # moderate
            known_atrs = [s.atr_pct for s in signals if s.atr_pct is not None]
            median_atr = median(known_atrs) if known_atrs else 0.0
            return sorted(
                signals,
                key=lambda s: (
                    -s.score,
                    abs(s.atr_pct - median_atr) if s.atr_pct is not None else float("inf"),
                ),
            )


class EnrichedScoreSelector(PortfolioSelector):
    """Multi-factor tiebreaker cascade using enriched signal metadata.

    When signals tie on score, this selector applies a deterministic cascade
    optimized for mean-reversion bounce quality:

    1. Score (primary — higher is better)
    2. CCI direction — RISING from oversold beats FLAT (momentum turning up)
    3. Candle quality — 3-day patterns > 2-day > 1-day (more reliable)
    4. RVOL — higher relative volume = more conviction behind the reversal
    5. MA20 distance — moderate distance preferred over extreme (sweet spot)
    6. ATR — lower ATR as final tiebreaker (calmer stock, tighter stops)

    Key design choice: extreme oversold depth is penalized, not rewarded.
    CCI at -200 often means a stock is crashing, not bouncing. A stock
    with CCI RISING from -120 is a better mean-reversion candidate than
    one still FALLING at -200. Similarly, moderate MA distance (-5% to -12%)
    is preferred over extreme (-20%+) which signals structural breakdown.

    Signals without metadata (metadata=None) degrade gracefully: all metadata
    keys fall back to neutral defaults so the cascade still produces a stable
    ordering without errors.
    """

    _CANDLE_QUALITY: dict[str, int] = {"3-day": 3, "2-day": 2, "1-day": 1}
    _CCI_DIRECTION_SCORE: dict[str, int] = {"rising": 3, "flat": 2, "falling": 1}
    # MA distance sweet spot: 5-12% below MA20 is ideal for mean reversion.
    # Closer than 5% = weak setup, further than 12% = possible structural breakdown.
    _MA_SWEET_SPOT_CENTER: float = 8.5  # midpoint of [5, 12]

    def __init__(self, atr_preference: str = "low", ma_sweet_spot_center: float = 8.5) -> None:
        """Initialize with optional ATR preference and MA sweet spot center.

        Args:
            atr_preference: "low" (default) or "high" — controls ATR sort
                direction as the last tiebreaker in the cascade.
            ma_sweet_spot_center: MA20 distance sweet-spot center (%). Signals
                whose absolute MA20 distance is closest to this value are
                preferred. Default: 8.5 (midpoint of the 5-12% range).
        """
        self._atr_preference = atr_preference
        self._ma_sweet_spot_center = ma_sweet_spot_center

    @property
    def name(self) -> str:
        if self._atr_preference == "high":
            return "enriched_score_high_atr"
        return "enriched_score"

    @property
    def description(self) -> str:
        atr_label = "highest" if self._atr_preference == "high" else "lowest"
        return (
            f"Rank by score then metadata cascade: CCI direction, candle quality, "
            f"RVOL, MA20 sweet spot, then {atr_label} ATR as final tiebreaker"
        )

    def rank(self, signals: list[QualifyingSignal]) -> list[QualifyingSignal]:
        """Rank signals using the multi-factor tiebreaker cascade."""
        return sorted(signals, key=self._rank_key)

    def _rank_key(self, s: QualifyingSignal) -> tuple:
        """Build a sortable tuple for the tiebreaker cascade.

        All values are negated where "higher is better" so that Python's
        ascending sort produces the correct descending result.
        """
        m = s.metadata or {}

        # CCI direction: rising > flat > falling (momentum turning is key)
        cci_dir = m.get("cci_direction", "")
        cci_dir_score = self._CCI_DIRECTION_SCORE.get(cci_dir, 0)

        candle_quality = self._CANDLE_QUALITY.get(m.get("candle_duration", "1-day"), 0)

        rvol = m.get("rvol", 1.0) or 1.0

        # MA distance: prefer sweet spot (5-12% below MA). Penalize extremes.
        # Distance from sweet spot center: lower = better.
        ma_distance_pct = m.get("ma_distance_pct")
        if ma_distance_pct is not None:
            ma_deviation = abs(abs(ma_distance_pct) - self._ma_sweet_spot_center)
        else:
            ma_deviation = float("inf")  # unknown = worst

        if self._atr_preference == "high":
            atr_key = -(s.atr_pct if s.atr_pct is not None else 0.0)
        else:
            atr_key = s.atr_pct if s.atr_pct is not None else float("inf")

        return (
            -s.score,          # 1. Higher score first
            -cci_dir_score,    # 2. RISING > FLAT > FALLING (momentum turning)
            -candle_quality,   # 3. 3-day > 2-day > 1-day patterns
            -rvol,             # 4. Higher volume conviction first
            ma_deviation,      # 5. Closer to sweet spot = lower = better
            atr_key,           # 6. ATR preference (low=ascending, high=descending)
        )


# --- Registry ---

SELECTOR_REGISTRY: dict[str, PortfolioSelector] = {
    "none": FifoSelector(),
    "score_sector_low_atr": ScoreSectorSelector("low"),
    "score_sector_high_atr": ScoreSectorSelector("high"),
    "score_sector_moderate_atr": ScoreSectorSelector("moderate"),
    "enriched_score": EnrichedScoreSelector("low"),
    "enriched_score_high_atr": EnrichedScoreSelector("high"),
}


def get_selector(strategy_name: str) -> PortfolioSelector:
    """Get a portfolio selector by name. Falls back to FIFO on unknown name.

    Args:
        strategy_name: The registered strategy name (e.g. "none", "score_sector_low_atr").

    Returns:
        PortfolioSelector: The matching selector, or FifoSelector on unknown name.
    """
    selector = SELECTOR_REGISTRY.get(strategy_name)
    if selector is None:
        logger.warning("Unknown portfolio strategy '%s', falling back to 'none'", strategy_name)
        return SELECTOR_REGISTRY["none"]
    return selector


def list_selectors() -> list[dict[str, str]]:
    """List all available selectors with name and description.

    Returns:
        list[dict[str, str]]: Each entry has "name" and "description" keys.
    """
    return [{"name": s.name, "description": s.description} for s in SELECTOR_REGISTRY.values()]
