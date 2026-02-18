"""Portfolio selector module for Arena position selection strategies.

This module provides pure-logic portfolio selection with no DB or I/O dependencies.
It ranks qualifying signals using configurable strategies and applies shared
constraint filtering (sector cap, max open positions).

Key classes:
- QualifyingSignal: Data container for a signal eligible for selection
- PortfolioSelector: Abstract base defining the rank/select interface
- FifoSelector: Preserves original symbol list order (original Arena behavior)
- ScoreSectorSelector: Score-ranked with ATR as a tiebreaker

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
    """A trading signal that qualifies for portfolio selection."""

    symbol: str
    score: int
    sector: str | None  # None = unknown, treated as unique sector
    atr_pct: float | None  # None = unknown, sorted to end


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


# --- Registry ---

SELECTOR_REGISTRY: dict[str, PortfolioSelector] = {
    "none": FifoSelector(),
    "score_sector_low_atr": ScoreSectorSelector("low"),
    "score_sector_high_atr": ScoreSectorSelector("high"),
    "score_sector_moderate_atr": ScoreSectorSelector("moderate"),
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
