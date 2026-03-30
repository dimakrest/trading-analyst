"""Unit tests for the portfolio_selector module.

Tests cover:
- FifoSelector: order preservation and constraint enforcement
- ScoreSectorSelector: all three ATR preference modes
- _apply_constraints: sector cap, position cap, existing counts
- Edge cases: empty input, single signal, all-same sector, None sector, None ATR
- Registry helpers: get_selector, list_selectors
"""
import pytest

from app.services.portfolio_selector import (
    EnrichedScoreSelector,
    FifoSelector,
    QualifyingSignal,
    ScoreSectorSelector,
    get_selector,
    list_selectors,
    SELECTOR_REGISTRY,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sig(
    symbol: str,
    score: int = 60,
    sector: str | None = "Technology",
    atr_pct: float | None = 2.0,
) -> QualifyingSignal:
    """Factory shortcut for QualifyingSignal."""
    return QualifyingSignal(symbol=symbol, score=score, sector=sector, atr_pct=atr_pct)


# ---------------------------------------------------------------------------
# FifoSelector
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestFifoSelector:
    """Tests for FifoSelector."""

    @pytest.fixture
    def selector(self) -> FifoSelector:
        return FifoSelector()

    # --- identity / metadata ---

    def test_name(self, selector: FifoSelector) -> None:
        assert selector.name == "none"

    def test_description_mentions_order(self, selector: FifoSelector) -> None:
        assert "order" in selector.description.lower() or "original" in selector.description.lower()

    # --- rank ---

    def test_rank_preserves_input_order(self, selector: FifoSelector) -> None:
        signals = [_sig("C"), _sig("A"), _sig("B")]
        ranked = selector.rank(signals)
        assert [s.symbol for s in ranked] == ["C", "A", "B"]

    def test_rank_returns_new_list(self, selector: FifoSelector) -> None:
        signals = [_sig("A"), _sig("B")]
        ranked = selector.rank(signals)
        assert ranked is not signals

    def test_rank_empty_list(self, selector: FifoSelector) -> None:
        assert selector.rank([]) == []

    def test_rank_single_signal(self, selector: FifoSelector) -> None:
        signals = [_sig("X")]
        assert selector.rank(signals) == signals

    # --- select with max_per_sector ---

    def test_select_respects_max_per_sector(self, selector: FifoSelector) -> None:
        signals = [
            _sig("A", sector="Tech"),
            _sig("B", sector="Tech"),
            _sig("C", sector="Finance"),
        ]
        result = selector.select(
            signals,
            existing_sector_counts={},
            current_open_count=0,
            max_per_sector=1,
        )
        symbols = [s.symbol for s in result]
        assert "A" in symbols
        assert "B" not in symbols  # blocked by sector cap
        assert "C" in symbols

    def test_select_respects_existing_sector_counts(self, selector: FifoSelector) -> None:
        """Existing open positions already count toward the sector cap."""
        signals = [_sig("A", sector="Tech"), _sig("B", sector="Tech")]
        result = selector.select(
            signals,
            existing_sector_counts={"Tech": 1},
            current_open_count=1,
            max_per_sector=1,
        )
        assert result == []  # both blocked; "Tech" cap already full

    # --- select with max_open_positions ---

    def test_select_respects_max_open_positions(self, selector: FifoSelector) -> None:
        signals = [_sig("A"), _sig("B"), _sig("C")]
        result = selector.select(
            signals,
            existing_sector_counts={},
            current_open_count=0,
            max_open_positions=2,
        )
        assert len(result) == 2
        assert [s.symbol for s in result] == ["A", "B"]

    def test_select_respects_existing_open_count(self, selector: FifoSelector) -> None:
        """current_open_count already consumes from max_open_positions."""
        signals = [_sig("A"), _sig("B"), _sig("C")]
        result = selector.select(
            signals,
            existing_sector_counts={},
            current_open_count=2,
            max_open_positions=3,
        )
        assert len(result) == 1
        assert result[0].symbol == "A"

    def test_select_no_constraints(self, selector: FifoSelector) -> None:
        signals = [_sig("A"), _sig("B"), _sig("C")]
        result = selector.select(
            signals,
            existing_sector_counts={},
            current_open_count=0,
        )
        assert [s.symbol for s in result] == ["A", "B", "C"]

    def test_select_already_at_max_positions(self, selector: FifoSelector) -> None:
        """When current_open_count == max_open_positions, nothing is selected."""
        signals = [_sig("A"), _sig("B")]
        result = selector.select(
            signals,
            existing_sector_counts={},
            current_open_count=5,
            max_open_positions=5,
        )
        assert result == []


# ---------------------------------------------------------------------------
# ScoreSectorSelector — low ATR
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestScoreSectorSelectorLowAtr:
    """Tests for ScoreSectorSelector with atr_preference='low'."""

    @pytest.fixture
    def selector(self) -> ScoreSectorSelector:
        return ScoreSectorSelector("low")

    def test_name(self, selector: ScoreSectorSelector) -> None:
        assert selector.name == "score_sector_low_atr"

    def test_description_mentions_low(self, selector: ScoreSectorSelector) -> None:
        assert "low" in selector.description.lower() or "lowest" in selector.description.lower()

    def test_rank_by_score_descending(self, selector: ScoreSectorSelector) -> None:
        signals = [
            _sig("A", score=40, atr_pct=1.0),
            _sig("B", score=80, atr_pct=2.0),
            _sig("C", score=60, atr_pct=1.5),
        ]
        ranked = selector.rank(signals)
        assert [s.symbol for s in ranked] == ["B", "C", "A"]

    def test_rank_same_score_lower_atr_first(self, selector: ScoreSectorSelector) -> None:
        signals = [
            _sig("A", score=60, atr_pct=3.0),
            _sig("B", score=60, atr_pct=1.0),
            _sig("C", score=60, atr_pct=2.0),
        ]
        ranked = selector.rank(signals)
        assert [s.symbol for s in ranked] == ["B", "C", "A"]

    def test_none_atr_sorted_to_end(self, selector: ScoreSectorSelector) -> None:
        signals = [
            _sig("A", score=60, atr_pct=None),
            _sig("B", score=60, atr_pct=1.0),
            _sig("C", score=60, atr_pct=2.0),
        ]
        ranked = selector.rank(signals)
        assert ranked[-1].symbol == "A"

    def test_none_atr_after_known_same_score(self, selector: ScoreSectorSelector) -> None:
        signals = [_sig("A", score=80, atr_pct=None), _sig("B", score=80, atr_pct=2.0)]
        ranked = selector.rank(signals)
        assert ranked[0].symbol == "B"
        assert ranked[1].symbol == "A"

    def test_rank_empty(self, selector: ScoreSectorSelector) -> None:
        assert selector.rank([]) == []

    def test_rank_single(self, selector: ScoreSectorSelector) -> None:
        s = _sig("X", score=70, atr_pct=1.5)
        assert selector.rank([s]) == [s]

    def test_all_none_atr_ranks_by_score_only(self, selector: ScoreSectorSelector) -> None:
        signals = [_sig("A", score=50, atr_pct=None), _sig("B", score=70, atr_pct=None)]
        ranked = selector.rank(signals)
        assert ranked[0].symbol == "B"


# ---------------------------------------------------------------------------
# ScoreSectorSelector — high ATR
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestScoreSectorSelectorHighAtr:
    """Tests for ScoreSectorSelector with atr_preference='high'."""

    @pytest.fixture
    def selector(self) -> ScoreSectorSelector:
        return ScoreSectorSelector("high")

    def test_name(self, selector: ScoreSectorSelector) -> None:
        assert selector.name == "score_sector_high_atr"

    def test_description_mentions_high(self, selector: ScoreSectorSelector) -> None:
        assert "high" in selector.description.lower() or "highest" in selector.description.lower()

    def test_rank_by_score_descending(self, selector: ScoreSectorSelector) -> None:
        signals = [
            _sig("A", score=40, atr_pct=5.0),
            _sig("B", score=80, atr_pct=1.0),
            _sig("C", score=60, atr_pct=3.0),
        ]
        ranked = selector.rank(signals)
        assert [s.symbol for s in ranked] == ["B", "C", "A"]

    def test_rank_same_score_higher_atr_first(self, selector: ScoreSectorSelector) -> None:
        signals = [
            _sig("A", score=60, atr_pct=1.0),
            _sig("B", score=60, atr_pct=4.0),
            _sig("C", score=60, atr_pct=2.5),
        ]
        ranked = selector.rank(signals)
        assert [s.symbol for s in ranked] == ["B", "C", "A"]

    def test_none_atr_treated_as_zero_for_high_preference(self, selector: ScoreSectorSelector) -> None:
        """None ATR uses 0 as a substitute, so it ranks below any positive ATR."""
        signals = [
            _sig("A", score=60, atr_pct=None),
            _sig("B", score=60, atr_pct=0.5),
        ]
        ranked = selector.rank(signals)
        # B has ATR 0.5, A effectively has ATR 0 — B should rank higher
        assert ranked[0].symbol == "B"
        assert ranked[1].symbol == "A"

    def test_rank_empty(self, selector: ScoreSectorSelector) -> None:
        assert selector.rank([]) == []


# ---------------------------------------------------------------------------
# ScoreSectorSelector — moderate ATR
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestScoreSectorSelectorModerateAtr:
    """Tests for ScoreSectorSelector with atr_preference='moderate'."""

    @pytest.fixture
    def selector(self) -> ScoreSectorSelector:
        return ScoreSectorSelector("moderate")

    def test_name(self, selector: ScoreSectorSelector) -> None:
        assert selector.name == "score_sector_moderate_atr"

    def test_description_mentions_median(self, selector: ScoreSectorSelector) -> None:
        assert "median" in selector.description.lower() or "moderate" in selector.description.lower()

    def test_rank_by_score_descending(self, selector: ScoreSectorSelector) -> None:
        signals = [
            _sig("A", score=40, atr_pct=2.0),
            _sig("B", score=80, atr_pct=2.0),
        ]
        ranked = selector.rank(signals)
        assert ranked[0].symbol == "B"

    def test_rank_same_score_closest_to_median_first(self, selector: ScoreSectorSelector) -> None:
        """Median of [1.0, 2.0, 5.0] = 2.0; B (2.0) is closest."""
        signals = [
            _sig("A", score=60, atr_pct=1.0),  # distance 1.0 from median 2.0
            _sig("B", score=60, atr_pct=2.0),  # distance 0.0
            _sig("C", score=60, atr_pct=5.0),  # distance 3.0
        ]
        ranked = selector.rank(signals)
        assert ranked[0].symbol == "B"
        assert ranked[-1].symbol == "C"

    def test_none_atr_sorted_to_end_moderate(self, selector: ScoreSectorSelector) -> None:
        signals = [
            _sig("A", score=60, atr_pct=None),
            _sig("B", score=60, atr_pct=2.0),
        ]
        ranked = selector.rank(signals)
        assert ranked[-1].symbol == "A"

    def test_all_none_atr_falls_back_to_zero_median(self, selector: ScoreSectorSelector) -> None:
        """When no known ATRs exist, median defaults to 0.0; None ATR goes to end."""
        signals = [
            _sig("A", score=80, atr_pct=None),
            _sig("B", score=60, atr_pct=None),
        ]
        ranked = selector.rank(signals)
        # Score ordering still works; None ATRs all share inf distance
        assert ranked[0].symbol == "A"

    def test_rank_empty(self, selector: ScoreSectorSelector) -> None:
        assert selector.rank([]) == []

    def test_rank_single(self, selector: ScoreSectorSelector) -> None:
        s = _sig("X")
        assert selector.rank([s]) == [s]


# ---------------------------------------------------------------------------
# Constraint filtering — shared behaviour across strategies
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestApplyConstraints:
    """Tests for _apply_constraints (exercised via FifoSelector.select for clarity)."""

    @pytest.fixture
    def selector(self) -> FifoSelector:
        return FifoSelector()

    def test_sector_cap_allows_up_to_limit(self, selector: FifoSelector) -> None:
        signals = [
            _sig("A", sector="Tech"),
            _sig("B", sector="Tech"),
            _sig("C", sector="Tech"),
        ]
        result = selector.select(
            signals,
            existing_sector_counts={},
            current_open_count=0,
            max_per_sector=2,
        )
        assert len(result) == 2
        assert result[0].symbol == "A"
        assert result[1].symbol == "B"

    def test_different_sectors_not_blocked_by_each_other(self, selector: FifoSelector) -> None:
        signals = [
            _sig("A", sector="Tech"),
            _sig("B", sector="Energy"),
            _sig("C", sector="Tech"),
        ]
        result = selector.select(
            signals,
            existing_sector_counts={},
            current_open_count=0,
            max_per_sector=1,
        )
        symbols = [s.symbol for s in result]
        assert "A" in symbols
        assert "B" in symbols
        assert "C" not in symbols

    def test_position_cap_stops_at_limit(self, selector: FifoSelector) -> None:
        signals = [_sig(f"S{i}", sector=f"Sector{i}") for i in range(10)]
        result = selector.select(
            signals,
            existing_sector_counts={},
            current_open_count=0,
            max_open_positions=4,
        )
        assert len(result) == 4

    def test_combined_sector_and_position_cap(self, selector: FifoSelector) -> None:
        signals = [
            _sig("A", sector="Tech"),
            _sig("B", sector="Tech"),  # would be blocked by sector cap
            _sig("C", sector="Energy"),
            _sig("D", sector="Finance"),
        ]
        result = selector.select(
            signals,
            existing_sector_counts={},
            current_open_count=0,
            max_per_sector=1,
            max_open_positions=3,
        )
        symbols = [s.symbol for s in result]
        assert "A" in symbols
        assert "B" not in symbols
        assert "C" in symbols
        assert "D" in symbols

    def test_no_caps_selects_all(self, selector: FifoSelector) -> None:
        signals = [_sig("A"), _sig("B"), _sig("C")]
        result = selector.select(
            signals,
            existing_sector_counts={},
            current_open_count=0,
        )
        assert len(result) == 3

    def test_existing_sector_counts_reduce_available_slots(self, selector: FifoSelector) -> None:
        signals = [_sig("A", sector="Tech"), _sig("B", sector="Tech")]
        result = selector.select(
            signals,
            existing_sector_counts={"Tech": 1},
            current_open_count=1,
            max_per_sector=2,
        )
        # One Tech slot remains; only A fits, B would exceed cap
        assert len(result) == 1
        assert result[0].symbol == "A"


# ---------------------------------------------------------------------------
# None sector handling
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestNoneSectorHandling:
    """Symbols with None sector are never blocked by sector cap."""

    @pytest.fixture
    def selector(self) -> FifoSelector:
        return FifoSelector()

    def test_none_sector_not_blocked_by_cap(self, selector: FifoSelector) -> None:
        signals = [
            _sig("A", sector=None),
            _sig("B", sector=None),
            _sig("C", sector=None),
        ]
        result = selector.select(
            signals,
            existing_sector_counts={},
            current_open_count=0,
            max_per_sector=1,
        )
        # Each None-sector symbol gets its own unique key, so all three pass
        assert len(result) == 3
        assert {s.symbol for s in result} == {"A", "B", "C"}

    def test_none_sector_mixes_with_known_sector(self, selector: FifoSelector) -> None:
        signals = [
            _sig("A", sector="Tech"),
            _sig("B", sector=None),
            _sig("C", sector="Tech"),
        ]
        result = selector.select(
            signals,
            existing_sector_counts={},
            current_open_count=0,
            max_per_sector=1,
        )
        symbols = [s.symbol for s in result]
        assert "A" in symbols
        assert "B" in symbols
        assert "C" not in symbols  # blocked — Tech cap full after A

    def test_none_sector_each_gets_unique_key(self, selector: FifoSelector) -> None:
        """Two None-sector symbols do not share a sector key."""
        signals = [_sig("X", sector=None), _sig("Y", sector=None)]
        result = selector.select(
            signals,
            existing_sector_counts={},
            current_open_count=0,
            max_per_sector=1,
        )
        assert len(result) == 2


# ---------------------------------------------------------------------------
# None ATR handling
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestNoneAtrHandling:
    """None ATR values should not raise errors and rank to end in sorting."""

    def test_low_atr_with_all_none_no_error(self) -> None:
        selector = ScoreSectorSelector("low")
        signals = [_sig("A", atr_pct=None), _sig("B", atr_pct=None)]
        ranked = selector.rank(signals)
        assert len(ranked) == 2

    def test_high_atr_with_all_none_no_error(self) -> None:
        selector = ScoreSectorSelector("high")
        signals = [_sig("A", atr_pct=None), _sig("B", atr_pct=None)]
        ranked = selector.rank(signals)
        assert len(ranked) == 2

    def test_moderate_atr_with_all_none_no_error(self) -> None:
        selector = ScoreSectorSelector("moderate")
        signals = [_sig("A", atr_pct=None), _sig("B", atr_pct=None)]
        ranked = selector.rank(signals)
        assert len(ranked) == 2

    def test_moderate_atr_none_does_not_break_median(self) -> None:
        """None ATR excluded from median; known ATRs still determine median."""
        selector = ScoreSectorSelector("moderate")
        signals = [
            _sig("A", score=60, atr_pct=None),
            _sig("B", score=60, atr_pct=2.0),
            _sig("C", score=60, atr_pct=4.0),
        ]
        # Median of [2.0, 4.0] = 3.0; C is closest (distance 1.0), B is 1.0 away too
        ranked = selector.rank(signals)
        assert ranked[-1].symbol == "A"  # None always last

    def test_low_atr_none_goes_after_known(self) -> None:
        selector = ScoreSectorSelector("low")
        signals = [_sig("A", score=60, atr_pct=None), _sig("B", score=60, atr_pct=0.01)]
        ranked = selector.rank(signals)
        assert ranked[0].symbol == "B"


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestEdgeCases:
    """Edge cases for all selectors."""

    def test_empty_signals_fifo(self) -> None:
        result = FifoSelector().select(
            [], existing_sector_counts={}, current_open_count=0,
        )
        assert result == []

    def test_empty_signals_score_low(self) -> None:
        result = ScoreSectorSelector("low").select(
            [], existing_sector_counts={}, current_open_count=0,
        )
        assert result == []

    def test_single_signal_passes_all_constraints(self) -> None:
        s = _sig("X")
        result = FifoSelector().select(
            [s],
            existing_sector_counts={},
            current_open_count=0,
            max_per_sector=1,
            max_open_positions=1,
        )
        assert result == [s]

    def test_all_same_sector_cap_one(self) -> None:
        signals = [_sig(f"S{i}", sector="Tech") for i in range(5)]
        result = FifoSelector().select(
            signals,
            existing_sector_counts={},
            current_open_count=0,
            max_per_sector=1,
        )
        assert len(result) == 1
        assert result[0].symbol == "S0"

    def test_all_same_score_fifo_preserves_order(self) -> None:
        signals = [_sig("C", score=60), _sig("A", score=60), _sig("B", score=60)]
        ranked = FifoSelector().rank(signals)
        assert [s.symbol for s in ranked] == ["C", "A", "B"]

    def test_all_same_score_low_atr_sorts_by_atr(self) -> None:
        signals = [
            _sig("A", score=60, atr_pct=3.0),
            _sig("B", score=60, atr_pct=1.0),
            _sig("C", score=60, atr_pct=2.0),
        ]
        ranked = ScoreSectorSelector("low").rank(signals)
        assert [s.symbol for s in ranked] == ["B", "C", "A"]

    def test_max_per_sector_none_means_no_cap(self) -> None:
        signals = [_sig(f"S{i}", sector="Tech") for i in range(20)]
        result = FifoSelector().select(
            signals,
            existing_sector_counts={},
            current_open_count=0,
            max_per_sector=None,
        )
        assert len(result) == 20

    def test_max_open_positions_none_means_no_cap(self) -> None:
        signals = [_sig(f"S{i}") for i in range(20)]
        result = FifoSelector().select(
            signals,
            existing_sector_counts={},
            current_open_count=0,
            max_open_positions=None,
        )
        assert len(result) == 20


# ---------------------------------------------------------------------------
# Registry helpers
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestRegistry:
    """Tests for get_selector and list_selectors."""

    def test_get_selector_none_returns_fifo(self) -> None:
        selector = get_selector("none")
        assert isinstance(selector, FifoSelector)

    def test_get_selector_low_atr(self) -> None:
        selector = get_selector("score_sector_low_atr")
        assert isinstance(selector, ScoreSectorSelector)
        assert selector.name == "score_sector_low_atr"

    def test_get_selector_high_atr(self) -> None:
        selector = get_selector("score_sector_high_atr")
        assert isinstance(selector, ScoreSectorSelector)
        assert selector.name == "score_sector_high_atr"

    def test_get_selector_moderate_atr(self) -> None:
        selector = get_selector("score_sector_moderate_atr")
        assert isinstance(selector, ScoreSectorSelector)
        assert selector.name == "score_sector_moderate_atr"

    def test_get_selector_unknown_returns_fifo(self) -> None:
        selector = get_selector("does_not_exist")
        assert isinstance(selector, FifoSelector)

    def test_get_selector_empty_string_returns_fifo(self) -> None:
        selector = get_selector("")
        assert isinstance(selector, FifoSelector)

    def test_list_selectors_returns_all_selectors(self) -> None:
        selectors = list_selectors()
        assert len(selectors) == len(SELECTOR_REGISTRY)

    def test_list_selectors_has_required_keys(self) -> None:
        for entry in list_selectors():
            assert "name" in entry
            assert "description" in entry
            assert isinstance(entry["name"], str)
            assert isinstance(entry["description"], str)

    def test_list_selectors_names_match_registry(self) -> None:
        listed_names = {entry["name"] for entry in list_selectors()}
        registry_names = set(SELECTOR_REGISTRY.keys())
        assert listed_names == registry_names

    def test_registry_contains_expected_keys(self) -> None:
        expected = {
            "none",
            "score_sector_low_atr",
            "score_sector_high_atr",
            "score_sector_moderate_atr",
            "enriched_score",
            "enriched_score_high_atr",
        }
        assert set(SELECTOR_REGISTRY.keys()) == expected

    def test_get_selector_returns_same_instance_from_registry(self) -> None:
        """Registry singletons — same object returned each time."""
        assert get_selector("none") is get_selector("none")
        assert get_selector("score_sector_low_atr") is get_selector("score_sector_low_atr")

    def test_get_selector_enriched_score(self) -> None:
        selector = get_selector("enriched_score")
        assert isinstance(selector, EnrichedScoreSelector)
        assert selector.name == "enriched_score"

    def test_get_selector_enriched_score_high_atr(self) -> None:
        selector = get_selector("enriched_score_high_atr")
        assert isinstance(selector, EnrichedScoreSelector)
        assert selector.name == "enriched_score_high_atr"


# ---------------------------------------------------------------------------
# EnrichedScoreSelector
# ---------------------------------------------------------------------------

def _enriched_sig(
    symbol: str,
    score: int = 75,
    sector: str | None = "Technology",
    atr_pct: float | None = 2.0,
    cci_value: float | None = None,
    cci_direction: str | None = None,
    ma_distance_pct: float | None = None,
    rvol: float | None = None,
    candle_duration: str | None = None,
    candle_pattern: str | None = None,
) -> QualifyingSignal:
    """Factory for QualifyingSignal with optional enriched metadata."""
    metadata: dict | None = None
    if any(v is not None for v in [cci_value, cci_direction, ma_distance_pct, rvol, candle_duration, candle_pattern]):
        metadata = {
            "cci_value": cci_value,
            "cci_direction": cci_direction,
            "ma_distance_pct": ma_distance_pct,
            "rvol": rvol,
            "candle_duration": candle_duration,
            "candle_pattern": candle_pattern,
        }
    return QualifyingSignal(
        symbol=symbol, score=score, sector=sector, atr_pct=atr_pct, metadata=metadata
    )


@pytest.mark.unit
class TestEnrichedScoreSelectorIdentity:
    """Identity/metadata tests for EnrichedScoreSelector."""

    def test_name_default(self) -> None:
        # Arrange / Act
        selector = EnrichedScoreSelector()
        # Assert
        assert selector.name == "enriched_score"

    def test_name_high_atr(self) -> None:
        selector = EnrichedScoreSelector("high")
        assert selector.name == "enriched_score_high_atr"

    def test_description_contains_cascade_keywords(self) -> None:
        selector = EnrichedScoreSelector()
        desc = selector.description.lower()
        assert "score" in desc
        assert "candle" in desc

    def test_description_high_atr_mentions_highest(self) -> None:
        selector = EnrichedScoreSelector("high")
        assert "highest" in selector.description.lower()

    def test_description_low_atr_mentions_lowest(self) -> None:
        selector = EnrichedScoreSelector("low")
        assert "lowest" in selector.description.lower()


@pytest.mark.unit
class TestEnrichedScoreSelectorPrimarySort:
    """Score is the primary sort key — metadata never overrides a score difference."""

    @pytest.fixture
    def selector(self) -> EnrichedScoreSelector:
        return EnrichedScoreSelector()

    def test_higher_score_wins_over_better_metadata(self, selector: EnrichedScoreSelector) -> None:
        # Arrange: A has lower score but superior metadata
        signals = [
            _enriched_sig("A", score=75, candle_duration="3-day", cci_value=-180.0, rvol=3.0),
            _enriched_sig("B", score=100, candle_duration="1-day", cci_value=-110.0, rvol=1.1),
        ]
        # Act
        ranked = selector.rank(signals)
        # Assert: B wins because score dominates
        assert ranked[0].symbol == "B"
        assert ranked[1].symbol == "A"

    def test_rank_three_different_scores(self, selector: EnrichedScoreSelector) -> None:
        # Arrange
        signals = [
            _enriched_sig("A", score=75),
            _enriched_sig("B", score=100),
            _enriched_sig("C", score=90),
        ]
        # Act
        ranked = selector.rank(signals)
        # Assert
        assert [s.symbol for s in ranked] == ["B", "C", "A"]


@pytest.mark.unit
class TestEnrichedScoreSelectorCciDirection:
    """Tiebreaker 2: CCI direction — rising > flat > falling (momentum turning)."""

    @pytest.fixture
    def selector(self) -> EnrichedScoreSelector:
        return EnrichedScoreSelector()

    def test_rising_beats_flat(self, selector: EnrichedScoreSelector) -> None:
        signals = [
            _enriched_sig("A", score=75, cci_direction="flat"),
            _enriched_sig("B", score=75, cci_direction="rising"),
        ]
        ranked = selector.rank(signals)
        assert ranked[0].symbol == "B"

    def test_flat_beats_falling(self, selector: EnrichedScoreSelector) -> None:
        signals = [
            _enriched_sig("A", score=75, cci_direction="falling"),
            _enriched_sig("B", score=75, cci_direction="flat"),
        ]
        ranked = selector.rank(signals)
        assert ranked[0].symbol == "B"

    def test_rising_beats_falling(self, selector: EnrichedScoreSelector) -> None:
        signals = [
            _enriched_sig("A", score=75, cci_direction="falling"),
            _enriched_sig("B", score=75, cci_direction="rising"),
        ]
        ranked = selector.rank(signals)
        assert ranked[0].symbol == "B"

    def test_full_direction_ordering(self, selector: EnrichedScoreSelector) -> None:
        signals = [
            _enriched_sig("A", score=75, cci_direction="falling"),
            _enriched_sig("B", score=75, cci_direction="rising"),
            _enriched_sig("C", score=75, cci_direction="flat"),
        ]
        ranked = selector.rank(signals)
        assert [s.symbol for s in ranked] == ["B", "C", "A"]

    def test_none_direction_falls_back_to_zero(self, selector: EnrichedScoreSelector) -> None:
        signals = [
            _enriched_sig("A", score=75, cci_direction=None),
            _enriched_sig("B", score=75, cci_direction="rising"),
        ]
        ranked = selector.rank(signals)
        assert ranked[0].symbol == "B"


@pytest.mark.unit
class TestEnrichedScoreSelectorCandleQuality:
    """Tiebreaker 3: candle quality — 3-day > 2-day > 1-day."""

    @pytest.fixture
    def selector(self) -> EnrichedScoreSelector:
        return EnrichedScoreSelector()

    def test_three_day_beats_two_day(self, selector: EnrichedScoreSelector) -> None:
        # Tie CCI direction so candle quality decides
        signals = [
            _enriched_sig("A", score=75, cci_direction="rising", candle_duration="2-day"),
            _enriched_sig("B", score=75, cci_direction="rising", candle_duration="3-day"),
        ]
        ranked = selector.rank(signals)
        assert ranked[0].symbol == "B"

    def test_two_day_beats_one_day(self, selector: EnrichedScoreSelector) -> None:
        signals = [
            _enriched_sig("A", score=75, cci_direction="rising", candle_duration="1-day"),
            _enriched_sig("B", score=75, cci_direction="rising", candle_duration="2-day"),
        ]
        ranked = selector.rank(signals)
        assert ranked[0].symbol == "B"

    def test_full_candle_duration_ordering(self, selector: EnrichedScoreSelector) -> None:
        signals = [
            _enriched_sig("A", score=75, cci_direction="rising", candle_duration="1-day"),
            _enriched_sig("B", score=75, cci_direction="rising", candle_duration="3-day"),
            _enriched_sig("C", score=75, cci_direction="rising", candle_duration="2-day"),
        ]
        ranked = selector.rank(signals)
        assert [s.symbol for s in ranked] == ["B", "C", "A"]


@pytest.mark.unit
class TestEnrichedScoreSelectorRvol:
    """Tiebreaker 4: RVOL — higher volume conviction wins."""

    @pytest.fixture
    def selector(self) -> EnrichedScoreSelector:
        return EnrichedScoreSelector()

    def test_higher_rvol_wins(self, selector: EnrichedScoreSelector) -> None:
        # Tie all earlier tiebreakers
        signals = [
            _enriched_sig("A", score=75, cci_direction="rising", candle_duration="1-day", rvol=1.1),
            _enriched_sig("B", score=75, cci_direction="rising", candle_duration="1-day", rvol=3.0),
        ]
        ranked = selector.rank(signals)
        assert ranked[0].symbol == "B"

    def test_none_rvol_defaults_to_1(self, selector: EnrichedScoreSelector) -> None:
        signals = [
            _enriched_sig("A", score=75, cci_direction="rising", candle_duration="1-day", rvol=None),
            _enriched_sig("B", score=75, cci_direction="rising", candle_duration="1-day", rvol=2.5),
        ]
        ranked = selector.rank(signals)
        assert ranked[0].symbol == "B"


@pytest.mark.unit
class TestEnrichedScoreSelectorMaSweetSpot:
    """Tiebreaker 5: MA20 distance — moderate distance (sweet spot ~8.5%) preferred."""

    @pytest.fixture
    def selector(self) -> EnrichedScoreSelector:
        return EnrichedScoreSelector()

    def test_sweet_spot_beats_extreme(self, selector: EnrichedScoreSelector) -> None:
        # -8% is closer to 8.5% sweet spot than -20%
        signals = [
            _enriched_sig("A", score=75, cci_direction="rising", candle_duration="1-day", rvol=2.0, ma_distance_pct=-20.0),
            _enriched_sig("B", score=75, cci_direction="rising", candle_duration="1-day", rvol=2.0, ma_distance_pct=-8.0),
        ]
        ranked = selector.rank(signals)
        assert ranked[0].symbol == "B"

    def test_sweet_spot_beats_too_close(self, selector: EnrichedScoreSelector) -> None:
        # -9% is closer to 8.5% than -3%
        signals = [
            _enriched_sig("A", score=75, cci_direction="rising", candle_duration="1-day", rvol=2.0, ma_distance_pct=-3.0),
            _enriched_sig("B", score=75, cci_direction="rising", candle_duration="1-day", rvol=2.0, ma_distance_pct=-9.0),
        ]
        ranked = selector.rank(signals)
        assert ranked[0].symbol == "B"

    def test_none_ma_sorted_to_end(self, selector: EnrichedScoreSelector) -> None:
        signals = [
            _enriched_sig("A", score=75, cci_direction="rising", candle_duration="1-day", rvol=2.0, ma_distance_pct=None),
            _enriched_sig("B", score=75, cci_direction="rising", candle_duration="1-day", rvol=2.0, ma_distance_pct=-8.0),
        ]
        ranked = selector.rank(signals)
        assert ranked[0].symbol == "B"


@pytest.mark.unit
class TestEnrichedScoreSelectorAtrTiebreaker:
    """Tiebreaker 6: ATR — low preference selects calmer stocks first."""

    def test_low_atr_preference_selects_lower_atr_first(self) -> None:
        selector = EnrichedScoreSelector("low")
        signals = [
            _enriched_sig("A", score=75, atr_pct=4.0, cci_direction="rising", candle_duration="1-day", rvol=2.0, ma_distance_pct=-8.0),
            _enriched_sig("B", score=75, atr_pct=1.0, cci_direction="rising", candle_duration="1-day", rvol=2.0, ma_distance_pct=-8.0),
        ]
        ranked = selector.rank(signals)
        assert ranked[0].symbol == "B"

    def test_high_atr_preference_selects_higher_atr_first(self) -> None:
        selector = EnrichedScoreSelector("high")
        signals = [
            _enriched_sig("A", score=75, atr_pct=1.0, cci_direction="rising", candle_duration="1-day", rvol=2.0, ma_distance_pct=-8.0),
            _enriched_sig("B", score=75, atr_pct=4.0, cci_direction="rising", candle_duration="1-day", rvol=2.0, ma_distance_pct=-8.0),
        ]
        ranked = selector.rank(signals)
        assert ranked[0].symbol == "B"

    def test_none_atr_sorted_to_end_low_preference(self) -> None:
        selector = EnrichedScoreSelector("low")
        signals = [
            _enriched_sig("A", score=75, atr_pct=None, cci_direction="rising", candle_duration="1-day", rvol=2.0, ma_distance_pct=-8.0),
            _enriched_sig("B", score=75, atr_pct=2.0, cci_direction="rising", candle_duration="1-day", rvol=2.0, ma_distance_pct=-8.0),
        ]
        ranked = selector.rank(signals)
        assert ranked[-1].symbol == "A"

    def test_none_atr_treated_as_zero_high_preference(self) -> None:
        selector = EnrichedScoreSelector("high")
        signals = [
            _enriched_sig("A", score=75, atr_pct=None, cci_direction="rising", candle_duration="1-day", rvol=2.0, ma_distance_pct=-8.0),
            _enriched_sig("B", score=75, atr_pct=1.0, cci_direction="rising", candle_duration="1-day", rvol=2.0, ma_distance_pct=-8.0),
        ]
        ranked = selector.rank(signals)
        assert ranked[0].symbol == "B"


@pytest.mark.unit
class TestEnrichedScoreSelectorBackwardCompat:
    """Signals without metadata must be handled gracefully (None-safe)."""

    @pytest.fixture
    def selector(self) -> EnrichedScoreSelector:
        return EnrichedScoreSelector()

    def test_none_metadata_does_not_raise(self, selector: EnrichedScoreSelector) -> None:
        # Arrange: no metadata on any signal
        signals = [
            QualifyingSignal(symbol="A", score=75, sector="Tech", atr_pct=2.0),
            QualifyingSignal(symbol="B", score=75, sector="Tech", atr_pct=3.0),
        ]
        # Act / Assert: must not raise
        ranked = selector.rank(signals)
        assert len(ranked) == 2

    def test_none_metadata_ranks_by_atr_as_final_tiebreaker(self, selector: EnrichedScoreSelector) -> None:
        # Arrange: both signals lack metadata; ATR is the only discriminator
        signals = [
            QualifyingSignal(symbol="A", score=75, sector="Tech", atr_pct=4.0),
            QualifyingSignal(symbol="B", score=75, sector="Tech", atr_pct=1.0),
        ]
        # Act
        ranked = selector.rank(signals)
        # Assert: lower ATR wins in default (low) preference
        assert ranked[0].symbol == "B"

    def test_mixed_metadata_presence_no_error(self, selector: EnrichedScoreSelector) -> None:
        # Arrange: one signal has metadata, the other does not
        signals = [
            _enriched_sig("A", score=75, candle_duration="3-day", cci_value=-180.0, rvol=3.0),
            QualifyingSignal(symbol="B", score=75, sector="Tech", atr_pct=2.0),
        ]
        # Act
        ranked = selector.rank(signals)
        # Assert: A wins because 3-day > no metadata (falls back to 0)
        assert ranked[0].symbol == "A"

    def test_empty_signals_returns_empty(self, selector: EnrichedScoreSelector) -> None:
        assert selector.rank([]) == []

    def test_single_signal_returns_unchanged(self, selector: EnrichedScoreSelector) -> None:
        s = QualifyingSignal(symbol="X", score=75, sector="Tech", atr_pct=2.0)
        assert selector.rank([s]) == [s]


@pytest.mark.unit
class TestEnrichedScoreSelectorFullCascade:
    """End-to-end cascade test: all 6 tiebreakers applied in order."""

    def test_full_cascade_ordering(self) -> None:
        """
        Three signals all at score=75:
          A: CCI falling, 1-day candle, RVOL 1.1, MA -3%,  ATR 4.0
          B: CCI rising,  3-day candle, RVOL 3.0, MA -9%,  ATR 1.0
          C: CCI flat,    2-day candle, RVOL 2.0, MA -8%,  ATR 2.0

        Expected order: B (rising CCI) > C (flat CCI) > A (falling CCI)
        """
        selector = EnrichedScoreSelector()
        signals = [
            _enriched_sig("A", score=75, atr_pct=4.0, cci_direction="falling", candle_duration="1-day", rvol=1.1, ma_distance_pct=-3.0),
            _enriched_sig("B", score=75, atr_pct=1.0, cci_direction="rising", candle_duration="3-day", rvol=3.0, ma_distance_pct=-9.0),
            _enriched_sig("C", score=75, atr_pct=2.0, cci_direction="flat", candle_duration="2-day", rvol=2.0, ma_distance_pct=-8.0),
        ]
        ranked = selector.rank(signals)
        assert [s.symbol for s in ranked] == ["B", "C", "A"]

    def test_select_applies_constraints_after_ranking(self) -> None:
        """Sector constraint is applied on top of the cascade ranking."""
        selector = EnrichedScoreSelector()
        signals = [
            _enriched_sig("A", score=75, sector="Tech", atr_pct=4.0, cci_direction="falling", candle_duration="1-day"),
            _enriched_sig("B", score=75, sector="Tech", atr_pct=1.0, cci_direction="rising", candle_duration="3-day"),
            _enriched_sig("C", score=75, sector="Energy", atr_pct=2.0, cci_direction="flat", candle_duration="2-day"),
        ]
        # max 1 per sector
        result = selector.select(
            signals,
            existing_sector_counts={},
            current_open_count=0,
            max_per_sector=1,
        )
        symbols = {s.symbol for s in result}
        # B wins Tech slot (rising CCI), C wins Energy, A blocked
        assert "B" in symbols
        assert "C" in symbols
        assert "A" not in symbols
