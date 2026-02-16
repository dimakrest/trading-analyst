"""Unit tests for Live20Evaluator shared module."""

import pytest

from app.services.live20_evaluator import (
    CriterionResult,
    Live20Direction,
    Live20Evaluator,
)
from app.indicators.cci_analysis import CCIAnalysis
from app.indicators.rsi2_analysis import RSI2Analysis
from app.models.recommendation import ScoringAlgorithm


class TestLive20EvaluatorConstants:
    """Test evaluator constants."""

    def test_weight_per_criterion(self):
        """Verify WEIGHT_PER_CRITERION is 20."""
        evaluator = Live20Evaluator()
        assert evaluator.WEIGHT_PER_CRITERION == 20

    def test_ma20_distance_threshold(self):
        """Verify MA20_DISTANCE_THRESHOLD is 5.0."""
        evaluator = Live20Evaluator()
        assert evaluator.MA20_DISTANCE_THRESHOLD == 5.0

    def test_min_criteria_for_setup(self):
        """Verify MIN_CRITERIA_FOR_SETUP is 3."""
        evaluator = Live20Evaluator()
        assert evaluator.MIN_CRITERIA_FOR_SETUP == 3


class TestLive20EvaluatorEvaluateCriteria:
    """Test evaluate_criteria method."""

    @pytest.fixture
    def evaluator(self):
        """Create Live20Evaluator instance."""
        return Live20Evaluator()

    @pytest.fixture
    def sample_price_data(self):
        """Generate 30 days of sample downtrend price data.

        Creates data that represents a downtrend scenario with:
        - Declining prices over the period
        - Declining volume (seller exhaustion)
        """
        base_price = 100.0
        opens = []
        highs = []
        lows = []
        closes = []
        volumes = []

        for i in range(30):
            # Declining prices for downtrend
            price = base_price - (i * 0.5)
            opens.append(price + 0.5)
            highs.append(price + 1.0)
            lows.append(price - 0.5)
            closes.append(price)
            volumes.append(1000000 - (i * 10000))  # Declining volume

        return opens, highs, lows, closes, volumes

    def test_returns_five_criteria(self, evaluator, sample_price_data):
        """Verify evaluate_criteria returns exactly 5 criteria."""
        # Arrange
        opens, highs, lows, closes, volumes = sample_price_data

        # Act
        criteria, _, _, _ = evaluator.evaluate_criteria(opens, highs, lows, closes, volumes)

        # Assert
        assert len(criteria) == 5

    def test_criteria_names(self, evaluator, sample_price_data):
        """Verify criteria names are trend, ma20_distance, candle, volume, momentum."""
        # Arrange
        opens, highs, lows, closes, volumes = sample_price_data

        # Act
        criteria, _, _, _ = evaluator.evaluate_criteria(opens, highs, lows, closes, volumes)

        # Assert
        names = [c.name for c in criteria]
        assert names == ["trend", "ma20_distance", "candle", "volume", "momentum"]

    def test_all_criteria_have_binary_scores_20(self, evaluator, sample_price_data):
        """Verify each criterion has binary scores of 20 for CCI (default)."""
        # Arrange
        opens, highs, lows, closes, volumes = sample_price_data

        # Act
        criteria, _, _, _ = evaluator.evaluate_criteria(opens, highs, lows, closes, volumes)

        # Assert - with default CCI, all criteria have score_for_long and score_for_short = 20
        for c in criteria:
            assert c.score_for_long == 20, f"Criterion {c.name} has score_for_long {c.score_for_long}, expected 20"
            assert c.score_for_short == 20, f"Criterion {c.name} has score_for_short {c.score_for_short}, expected 20"

    def test_returns_volume_signal(self, evaluator, sample_price_data):
        """Verify volume_signal has aligned_for_long, aligned_for_short, rvol attributes."""
        # Arrange
        opens, highs, lows, closes, volumes = sample_price_data

        # Act
        _, volume_signal, _, _ = evaluator.evaluate_criteria(opens, highs, lows, closes, volumes)

        # Assert
        assert hasattr(volume_signal, "aligned_for_long")
        assert hasattr(volume_signal, "aligned_for_short")
        assert hasattr(volume_signal, "rvol")

    def test_returns_cci_analysis(self, evaluator, sample_price_data):
        """Verify cci_analysis has zone, direction, value attributes."""
        # Arrange
        opens, highs, lows, closes, volumes = sample_price_data

        # Act
        _, _, cci_analysis, _ = evaluator.evaluate_criteria(opens, highs, lows, closes, volumes)

        # Assert
        assert hasattr(cci_analysis, "zone")
        assert hasattr(cci_analysis, "direction")
        assert hasattr(cci_analysis, "value")

    def test_returns_candle_explanation(self, evaluator, sample_price_data):
        """Verify candle_explanation is a string."""
        # Arrange
        opens, highs, lows, closes, volumes = sample_price_data

        # Act
        _, _, _, candle_explanation = evaluator.evaluate_criteria(
            opens, highs, lows, closes, volumes
        )

        # Assert
        assert isinstance(candle_explanation, str)


class TestLive20EvaluatorDetermineDirection:
    """Test determine_direction_and_score method."""

    @pytest.fixture
    def evaluator(self):
        """Create Live20Evaluator instance."""
        return Live20Evaluator()

    def test_long_direction_when_3_long_aligned(self, evaluator):
        """Test 3 criteria aligned for LONG returns direction=LONG, score=60."""
        # Arrange
        criteria = [
            CriterionResult("trend", "bearish", True, False, 20, 20),
            CriterionResult("ma20", "-6%", True, False, 20, 20),
            CriterionResult("candle", "hammer", True, False, 20, 20),
            CriterionResult("volume", "1.5x", False, False, 20, 20),
            CriterionResult("cci", "oversold", False, False, 20, 20),
        ]

        # Act
        direction, score = evaluator.determine_direction_and_score(criteria)

        # Assert
        assert direction == Live20Direction.LONG
        assert score == 60

    def test_short_direction_when_3_short_aligned(self, evaluator):
        """Test 3 criteria aligned for SHORT returns direction=SHORT, score=60."""
        # Arrange
        criteria = [
            CriterionResult("trend", "bullish", False, True, 20, 20),
            CriterionResult("ma20", "+6%", False, True, 20, 20),
            CriterionResult("candle", "shooting_star", False, True, 20, 20),
            CriterionResult("volume", "1.5x", False, False, 20, 20),
            CriterionResult("cci", "overbought", False, False, 20, 20),
        ]

        # Act
        direction, score = evaluator.determine_direction_and_score(criteria)

        # Assert
        assert direction == Live20Direction.SHORT
        assert score == 60

    def test_no_setup_when_less_than_3_aligned(self, evaluator):
        """Test only 1 aligned returns direction=NO_SETUP, score=20."""
        # Arrange
        criteria = [
            CriterionResult("trend", "bearish", True, False, 20, 20),
            CriterionResult("ma20", "-2%", False, False, 20, 20),
            CriterionResult("candle", "doji", False, False, 20, 20),
            CriterionResult("volume", "1.0x", False, False, 20, 20),
            CriterionResult("cci", "neutral", False, False, 20, 20),
        ]

        # Act
        direction, score = evaluator.determine_direction_and_score(criteria)

        # Assert
        assert direction == Live20Direction.NO_SETUP
        assert score == 20

    def test_long_wins_tie_with_more_aligned(self, evaluator):
        """Test 4 LONG, 1 SHORT returns LONG, score=80."""
        # Arrange
        criteria = [
            CriterionResult("trend", "bearish", True, False, 20, 20),
            CriterionResult("ma20", "-6%", True, False, 20, 20),
            CriterionResult("candle", "hammer", True, False, 20, 20),
            CriterionResult("volume", "1.5x", True, False, 20, 20),
            CriterionResult("cci", "overbought", False, True, 20, 20),  # SHORT aligned
        ]

        # Act
        direction, score = evaluator.determine_direction_and_score(criteria)

        # Assert
        assert direction == Live20Direction.LONG
        assert score == 80

    def test_max_score_is_100(self, evaluator):
        """Test 5 aligned returns score=100."""
        # Arrange
        criteria = [
            CriterionResult("trend", "bearish", True, False, 20, 20),
            CriterionResult("ma20", "-6%", True, False, 20, 20),
            CriterionResult("candle", "hammer", True, False, 20, 20),
            CriterionResult("volume", "1.5x", True, False, 20, 20),
            CriterionResult("cci", "oversold", True, False, 20, 20),
        ]

        # Act
        direction, score = evaluator.determine_direction_and_score(criteria)

        # Assert
        assert direction == Live20Direction.LONG
        assert score == 100

    def test_no_setup_when_equal_alignment(self, evaluator):
        """Test when LONG and SHORT have equal alignment (both 2), returns NO_SETUP."""
        # Arrange
        criteria = [
            CriterionResult("trend", "bearish", True, False, 20, 20),  # LONG
            CriterionResult("ma20", "+6%", False, True, 20, 20),  # SHORT
            CriterionResult("candle", "hammer", True, False, 20, 20),  # LONG
            CriterionResult("volume", "1.5x", False, True, 20, 20),  # SHORT
            CriterionResult("cci", "neutral", False, False, 20, 20),  # Neither
        ]

        # Act
        direction, score = evaluator.determine_direction_and_score(criteria)

        # Assert
        assert direction == Live20Direction.NO_SETUP
        assert score == 40  # max(2, 2) * 20

    def test_short_wins_when_more_short_aligned(self, evaluator):
        """Test 4 SHORT, 1 LONG returns SHORT, score=80."""
        # Arrange
        criteria = [
            CriterionResult("trend", "bullish", False, True, 20, 20),  # SHORT
            CriterionResult("ma20", "+6%", False, True, 20, 20),  # SHORT
            CriterionResult("candle", "shooting_star", False, True, 20, 20),  # SHORT
            CriterionResult("volume", "0.8x", False, True, 20, 20),  # SHORT
            CriterionResult("cci", "oversold", True, False, 20, 20),  # LONG
        ]

        # Act
        direction, score = evaluator.determine_direction_and_score(criteria)

        # Assert
        assert direction == Live20Direction.SHORT
        assert score == 80


class TestLive20EvaluatorGetMa20Distance:
    """Test get_ma20_distance method."""

    @pytest.fixture
    def evaluator(self):
        """Create Live20Evaluator instance."""
        return Live20Evaluator()

    def test_returns_float(self, evaluator):
        """Verify get_ma20_distance returns a float."""
        # Arrange
        closes = [100.0] * 25

        # Act
        distance = evaluator.get_ma20_distance(closes)

        # Assert
        assert isinstance(distance, float)

    def test_flat_prices_return_zero(self, evaluator):
        """Verify 25 flat prices should return near-zero distance."""
        # Arrange
        closes = [100.0] * 25

        # Act
        distance = evaluator.get_ma20_distance(closes)

        # Assert
        assert abs(distance) < 0.1  # Near zero

    def test_price_above_ma20_returns_positive(self, evaluator):
        """Verify price above MA20 returns positive distance."""
        # Arrange - price rises at the end
        closes = [100.0] * 20 + [115.0] * 5

        # Act
        distance = evaluator.get_ma20_distance(closes)

        # Assert
        assert distance > 0, f"Expected positive distance, got {distance}"

    def test_price_below_ma20_returns_negative(self, evaluator):
        """Verify price below MA20 returns negative distance."""
        # Arrange - price drops at the end
        closes = [100.0] * 20 + [85.0] * 5

        # Act
        distance = evaluator.get_ma20_distance(closes)

        # Assert
        assert distance < 0, f"Expected negative distance, got {distance}"


class TestCriterionResultDataclass:
    """Test CriterionResult dataclass behavior."""

    def test_criterion_result_creation(self):
        """Verify CriterionResult can be created with all fields."""
        # Act
        criterion = CriterionResult(
            name="test",
            value="test_value",
            aligned_for_long=True,
            aligned_for_short=False,
            score_for_long=20,
            score_for_short=15,
        )

        # Assert
        assert criterion.name == "test"
        assert criterion.value == "test_value"
        assert criterion.aligned_for_long is True
        assert criterion.aligned_for_short is False
        assert criterion.score_for_long == 20
        assert criterion.score_for_short == 15

    def test_criterion_result_equality(self):
        """Verify CriterionResult equality comparison works."""
        # Arrange
        criterion1 = CriterionResult("trend", "bearish", True, False, 20, 20)
        criterion2 = CriterionResult("trend", "bearish", True, False, 20, 20)

        # Assert
        assert criterion1 == criterion2


class TestLive20DirectionConstants:
    """Test Live20Direction constants."""

    def test_long_constant(self):
        """Verify LONG constant value."""
        assert Live20Direction.LONG == "LONG"

    def test_short_constant(self):
        """Verify SHORT constant value."""
        assert Live20Direction.SHORT == "SHORT"

    def test_no_setup_constant(self):
        """Verify NO_SETUP constant value."""
        assert Live20Direction.NO_SETUP == "NO_SETUP"


class TestMultiDayPatternIntegration:
    """Test multi-day pattern integration in Live20 evaluator.

    Verifies that the evaluator correctly uses the multi-day pattern detection
    with priority: 3-day > 2-day > 1-day.
    """

    @pytest.fixture
    def evaluator(self):
        """Create Live20Evaluator instance."""
        return Live20Evaluator()

    def test_three_day_morning_star_detected(self, evaluator):
        """Test that 3-day Morning Star pattern is detected and used."""
        base_opens = [100.0] * 27 + [110.0, 97.0, 100.0]
        base_highs = [101.0] * 27 + [112.0, 98.0, 115.0]
        base_lows = [99.0] * 27 + [98.0, 96.5, 99.0]
        base_closes = [100.0] * 27 + [100.0, 97.3, 112.0]
        volumes = [1000000.0] * 30

        criteria, _, _, candle_explanation = evaluator.evaluate_criteria(
            base_opens, base_highs, base_lows, base_closes, volumes
        )
        candle_criterion = criteria[2]

        assert candle_criterion.name == "candle"
        assert candle_criterion.value == "morning_star"
        assert candle_criterion.aligned_for_long is True
        assert candle_criterion.aligned_for_short is False
        assert "3-day" in candle_explanation

    def test_three_day_evening_star_detected(self, evaluator):
        """Test that 3-day Evening Star pattern is detected and used."""
        base_opens = [100.0] * 27 + [100.0, 112.0, 110.0]
        base_highs = [101.0] * 27 + [112.0, 114.0, 112.0]
        base_lows = [99.0] * 27 + [99.0, 111.0, 97.0]
        base_closes = [100.0] * 27 + [110.0, 112.1, 98.0]
        volumes = [1000000.0] * 30

        criteria, _, _, candle_explanation = evaluator.evaluate_criteria(
            base_opens, base_highs, base_lows, base_closes, volumes
        )
        candle_criterion = criteria[2]

        assert candle_criterion.name == "candle"
        assert candle_criterion.value == "evening_star"
        assert candle_criterion.aligned_for_long is False
        assert candle_criterion.aligned_for_short is True
        assert "3-day" in candle_explanation

    def test_two_day_piercing_line_when_no_three_day(self, evaluator):
        """Test that 2-day patterns are used when no 3-day pattern exists."""
        base_opens = [100.0] * 27 + [105.0, 110.0, 95.0]
        base_highs = [101.0] * 27 + [106.0, 112.0, 107.0]
        base_lows = [99.0] * 27 + [104.0, 98.0, 94.0]
        base_closes = [100.0] * 27 + [105.5, 100.0, 106.0]
        volumes = [1000000.0] * 30

        criteria, _, _, candle_explanation = evaluator.evaluate_criteria(
            base_opens, base_highs, base_lows, base_closes, volumes
        )
        candle_criterion = criteria[2]

        assert candle_criterion.name == "candle"
        assert candle_criterion.value == "piercing_line"
        assert candle_criterion.aligned_for_long is True
        assert "2-day" in candle_explanation

    def test_two_day_dark_cloud_cover_when_no_three_day(self, evaluator):
        """Test Dark Cloud Cover (2-day) is detected when no 3-day pattern."""
        base_opens = [100.0] * 27 + [95.0, 100.0, 112.0]
        base_highs = [101.0] * 27 + [96.0, 111.0, 114.0]
        base_lows = [99.0] * 27 + [94.0, 99.0, 103.0]
        base_closes = [100.0] * 27 + [95.5, 110.0, 104.0]
        volumes = [1000000.0] * 30

        criteria, _, _, candle_explanation = evaluator.evaluate_criteria(
            base_opens, base_highs, base_lows, base_closes, volumes
        )
        candle_criterion = criteria[2]

        assert candle_criterion.name == "candle"
        assert candle_criterion.value == "dark_cloud_cover"
        assert candle_criterion.aligned_for_short is True
        assert "2-day" in candle_explanation

    def test_one_day_pattern_fallback(self, evaluator):
        """Test that 1-day patterns are used when no multi-day pattern exists."""
        base_opens = [100.0] * 30
        base_highs = [101.0] * 29 + [102.0]
        base_lows = [99.0] * 29 + [90.0]
        base_closes = [100.0] * 29 + [101.5]
        volumes = [1000000.0] * 30

        criteria, _, _, candle_explanation = evaluator.evaluate_criteria(
            base_opens, base_highs, base_lows, base_closes, volumes
        )
        candle_criterion = criteria[2]

        assert candle_criterion.name == "candle"
        assert candle_criterion.value is not None

    def test_three_day_three_white_soldiers(self, evaluator):
        """Test Three White Soldiers (3-day) pattern detection."""
        base_opens = [100.0] * 27 + [100.0, 105.0, 110.0]
        base_highs = [101.0] * 27 + [106.0, 111.0, 118.0]
        base_lows = [99.0] * 27 + [99.0, 104.0, 109.0]
        base_closes = [100.0] * 27 + [105.0, 110.0, 117.0]
        volumes = [1000000.0] * 30

        criteria, _, _, candle_explanation = evaluator.evaluate_criteria(
            base_opens, base_highs, base_lows, base_closes, volumes
        )
        candle_criterion = criteria[2]

        assert candle_criterion.name == "candle"
        assert candle_criterion.value == "three_white_soldiers"
        assert candle_criterion.aligned_for_long is True
        assert candle_criterion.aligned_for_short is False
        assert "3-day" in candle_explanation

    def test_three_day_three_black_crows(self, evaluator):
        """Test Three Black Crows (3-day) pattern detection."""
        base_opens = [100.0] * 27 + [120.0, 115.0, 110.0]
        base_highs = [101.0] * 27 + [121.0, 116.0, 111.0]
        base_lows = [99.0] * 27 + [114.0, 109.0, 104.0]
        base_closes = [100.0] * 27 + [115.0, 110.0, 105.0]
        volumes = [1000000.0] * 30

        criteria, _, _, candle_explanation = evaluator.evaluate_criteria(
            base_opens, base_highs, base_lows, base_closes, volumes
        )
        candle_criterion = criteria[2]

        assert candle_criterion.name == "candle"
        assert candle_criterion.value == "three_black_crows"
        assert candle_criterion.aligned_for_long is False
        assert candle_criterion.aligned_for_short is True
        assert "3-day" in candle_explanation

    def test_high_tight_flag_not_aligned_for_mean_reversion(self, evaluator):
        """Test High Tight Flag (continuation) is NOT aligned for mean reversion."""
        base_opens = [100.0] * 27 + [100.0, 104.2, 104.1]
        base_highs = [101.0] * 27 + [104.5, 104.5, 104.3]
        base_lows = [99.0] * 27 + [99.5, 103.5, 103.6]
        base_closes = [100.0] * 27 + [104.0, 104.0, 103.9]
        volumes = [1000000.0] * 30

        criteria, _, _, candle_explanation = evaluator.evaluate_criteria(
            base_opens, base_highs, base_lows, base_closes, volumes
        )
        candle_criterion = criteria[2]

        assert candle_criterion.name == "candle"
        assert candle_criterion.value == "high_tight_flag"
        assert candle_criterion.aligned_for_long is False
        assert candle_criterion.aligned_for_short is False
        assert "continuation" in candle_explanation.lower()

    def test_candle_explanation_includes_duration(self, evaluator):
        """Test that candle explanation includes pattern duration info."""
        base_opens = [100.0] * 27 + [110.0, 97.0, 100.0]
        base_highs = [101.0] * 27 + [112.0, 98.0, 115.0]
        base_lows = [99.0] * 27 + [98.0, 96.5, 99.0]
        base_closes = [100.0] * 27 + [100.0, 97.3, 112.0]
        volumes = [1000000.0] * 30

        criteria, _, _, candle_explanation = evaluator.evaluate_criteria(
            base_opens, base_highs, base_lows, base_closes, volumes
        )

        assert "3-day" in candle_explanation or "three" in candle_explanation.lower()

    def test_two_day_bullish_harami(self, evaluator):
        """Test Bullish Harami (2-day) pattern detection."""
        base_opens = [100.0] * 27 + [95.0, 110.0, 102.0]
        base_highs = [101.0] * 27 + [96.0, 112.0, 105.0]
        base_lows = [99.0] * 27 + [94.0, 98.0, 101.0]
        base_closes = [100.0] * 27 + [95.5, 100.0, 104.0]
        volumes = [1000000.0] * 30

        criteria, _, _, candle_explanation = evaluator.evaluate_criteria(
            base_opens, base_highs, base_lows, base_closes, volumes
        )
        candle_criterion = criteria[2]

        assert candle_criterion.name == "candle"
        assert candle_criterion.value == "bullish_harami"
        assert candle_criterion.aligned_for_long is True
        assert "2-day" in candle_explanation


class TestRSI2Integration:
    """Test RSI-2 algorithm integration in evaluator."""

    @pytest.fixture
    def evaluator(self):
        """Create Live20Evaluator instance."""
        return Live20Evaluator()

    @pytest.fixture
    def sample_price_data(self):
        """Generate sample price data for testing."""
        # 30 days of downtrend (for RSI-2 oversold)
        base_price = 100.0
        opens = []
        highs = []
        lows = []
        closes = []
        volumes = []

        for i in range(30):
            price = base_price - (i * 0.5)
            opens.append(price + 0.5)
            highs.append(price + 1.0)
            lows.append(price - 0.5)
            closes.append(price)
            volumes.append(1000000)

        return opens, highs, lows, closes, volumes

    def test_evaluate_with_rsi2_returns_rsi2_analysis(self, evaluator, sample_price_data):
        """Test that RSI-2 algorithm returns RSI2Analysis instance."""
        opens, highs, lows, closes, volumes = sample_price_data

        criteria, _, momentum_analysis, _ = evaluator.evaluate_criteria(
            opens, highs, lows, closes, volumes,
            scoring_algorithm=ScoringAlgorithm.RSI2
        )

        assert isinstance(momentum_analysis, RSI2Analysis)
        assert hasattr(momentum_analysis, "value")
        assert hasattr(momentum_analysis, "long_score")
        assert hasattr(momentum_analysis, "short_score")

    def test_evaluate_with_cci_returns_cci_analysis(self, evaluator, sample_price_data):
        """Test that CCI algorithm (default) returns CCIAnalysis instance."""
        opens, highs, lows, closes, volumes = sample_price_data

        criteria, _, momentum_analysis, _ = evaluator.evaluate_criteria(
            opens, highs, lows, closes, volumes,
            scoring_algorithm=ScoringAlgorithm.CCI
        )

        assert isinstance(momentum_analysis, CCIAnalysis)
        assert hasattr(momentum_analysis, "zone")
        assert hasattr(momentum_analysis, "direction")
        assert hasattr(momentum_analysis, "value")

    def test_momentum_criterion_name_is_momentum_for_both_algorithms(self, evaluator, sample_price_data):
        """Test that both CCI and RSI-2 use criterion name 'momentum'."""
        opens, highs, lows, closes, volumes = sample_price_data

        # Test CCI
        criteria_cci, _, _, _ = evaluator.evaluate_criteria(
            opens, highs, lows, closes, volumes,
            scoring_algorithm=ScoringAlgorithm.CCI
        )
        momentum_cci = [c for c in criteria_cci if c.name == "momentum"]
        assert len(momentum_cci) == 1

        # Test RSI-2
        criteria_rsi2, _, _, _ = evaluator.evaluate_criteria(
            opens, highs, lows, closes, volumes,
            scoring_algorithm=ScoringAlgorithm.RSI2
        )
        momentum_rsi2 = [c for c in criteria_rsi2 if c.name == "momentum"]
        assert len(momentum_rsi2) == 1

    def test_cci_regression_sum_equals_count_times_20(self, evaluator, sample_price_data):
        """Test CCI backward compatibility: sum of aligned scores == aligned_count * 20."""
        opens, highs, lows, closes, volumes = sample_price_data

        criteria, _, _, _ = evaluator.evaluate_criteria(
            opens, highs, lows, closes, volumes,
            scoring_algorithm=ScoringAlgorithm.CCI
        )

        direction, score = evaluator.determine_direction_and_score(criteria)

        # Count aligned criteria
        if direction == "LONG":
            aligned_count = sum(1 for c in criteria if c.aligned_for_long)
            expected_score = aligned_count * 20
        elif direction == "SHORT":
            aligned_count = sum(1 for c in criteria if c.aligned_for_short)
            expected_score = aligned_count * 20
        else:
            long_count = sum(1 for c in criteria if c.aligned_for_long)
            short_count = sum(1 for c in criteria if c.aligned_for_short)
            expected_score = max(long_count, short_count) * 20

        assert score == expected_score, f"CCI regression failed: score={score}, expected={expected_score}"

    def test_rsi2_graduated_scoring_example(self, evaluator):
        """Test RSI-2 graduated scoring with specific example."""
        # Create data with specific RSI-2 value to produce 15 pts
        # Strong oversold (5-15 range)
        closes = [100.0] * 5 + [98.0, 96.0, 94.0, 92.0, 90.0]
        opens = [c + 0.5 for c in closes]
        highs = [c + 1.0 for c in closes]
        lows = [c - 0.5 for c in closes]
        volumes = [1000000] * len(closes)

        criteria, _, momentum_analysis, _ = evaluator.evaluate_criteria(
            opens, highs, lows, closes, volumes,
            scoring_algorithm=ScoringAlgorithm.RSI2
        )

        # Find momentum criterion
        momentum_criterion = [c for c in criteria if c.name == "momentum"][0]

        # RSI-2 should have graduated score (not binary 0/20)
        assert isinstance(momentum_analysis, RSI2Analysis)
        assert momentum_analysis.long_score in [0, 5, 10, 15, 20]
        # Downtrend should produce oversold RSI-2
        assert momentum_analysis.long_score > 0

    def test_rsi2_alignment_based_on_score_gt_zero(self, evaluator, sample_price_data):
        """Test that RSI-2 alignment is determined by score > 0."""
        opens, highs, lows, closes, volumes = sample_price_data

        criteria, _, momentum_analysis, _ = evaluator.evaluate_criteria(
            opens, highs, lows, closes, volumes,
            scoring_algorithm=ScoringAlgorithm.RSI2
        )

        momentum_criterion = [c for c in criteria if c.name == "momentum"][0]

        # Alignment should match score > 0
        assert momentum_criterion.aligned_for_long == (momentum_analysis.long_score > 0)
        assert momentum_criterion.aligned_for_short == (momentum_analysis.short_score > 0)


class TestGraduatedScoring:
    """Test graduated scoring behavior with RSI-2."""

    @pytest.fixture
    def evaluator(self):
        """Create Live20Evaluator instance."""
        return Live20Evaluator()

    def test_direction_determined_by_count_not_score(self, evaluator):
        """Test that direction is determined by aligned COUNT, not score sum."""
        # 3 binary criteria aligned for LONG (20 pts each) + 1 RSI-2 (5 pts) = 65 total
        # vs 2 binary criteria aligned for SHORT (20 pts each) = 40 total
        # Direction should be LONG (3 > 2 count), even though we could imagine
        # a scenario where SHORT has higher score

        criteria = [
            CriterionResult("trend", "bearish", True, False, 20, 20),  # LONG
            CriterionResult("ma20", "-6%", True, False, 20, 20),  # LONG
            CriterionResult("candle", "hammer", True, False, 20, 20),  # LONG
            CriterionResult("volume", "1.5x", False, False, 20, 20),  # Neither
            CriterionResult("momentum", "RSI-2: 35", True, False, 5, 0),  # LONG 5pts
        ]

        direction, score = evaluator.determine_direction_and_score(criteria)

        # Direction is LONG (4 aligned count)
        assert direction == Live20Direction.LONG
        # Score is 20+20+20+5 = 65
        assert score == 65

    def test_graduated_scoring_total(self, evaluator):
        """Test that total score correctly sums graduated scores."""
        # 2 binary (20 each) + 1 RSI-2 (15) + 2 binary (20 each) = 95
        criteria = [
            CriterionResult("trend", "bearish", True, False, 20, 20),
            CriterionResult("ma20", "-6%", True, False, 20, 20),
            CriterionResult("candle", "hammer", True, False, 20, 20),
            CriterionResult("volume", "1.5x", True, False, 20, 20),
            CriterionResult("momentum", "RSI-2: 10", True, False, 15, 0),  # 15pts
        ]

        direction, score = evaluator.determine_direction_and_score(criteria)

        assert direction == Live20Direction.LONG
        assert score == 95  # 20+20+20+20+15

    def test_no_setup_uses_max_score(self, evaluator):
        """Test NO_SETUP uses max(long_score, short_score)."""
        # Only 2 aligned for LONG, 1 for SHORT = NO_SETUP
        # But scores differ: LONG=45, SHORT=20
        criteria = [
            CriterionResult("trend", "bearish", True, False, 20, 20),  # LONG 20
            CriterionResult("ma20", "-2%", False, False, 20, 20),  # Neither
            CriterionResult("candle", "doji", False, False, 20, 20),  # Neither
            CriterionResult("volume", "1.0x", False, True, 20, 20),  # SHORT 20
            CriterionResult("momentum", "RSI-2: 10", True, False, 15, 0),  # LONG 15
        ]

        direction, score = evaluator.determine_direction_and_score(criteria)

        assert direction == Live20Direction.NO_SETUP
        # max(20+15, 20) = 35
        assert score == 35


class TestCriterionNames:
    """Test criterion names are standardized."""

    @pytest.fixture
    def evaluator(self):
        """Create Live20Evaluator instance."""
        return Live20Evaluator()

    def test_cci_criterion_name_is_momentum(self, evaluator):
        """Test CCI criterion uses name 'momentum' not 'cci'."""
        closes = [100.0] * 30
        opens = [c + 0.5 for c in closes]
        highs = [c + 1.0 for c in closes]
        lows = [c - 0.5 for c in closes]
        volumes = [1000000] * 30

        criteria, _, _, _ = evaluator.evaluate_criteria(
            opens, highs, lows, closes, volumes,
            scoring_algorithm=ScoringAlgorithm.CCI
        )

        names = [c.name for c in criteria]
        assert "momentum" in names
        assert "cci" not in names

    def test_all_criteria_names(self, evaluator):
        """Test all 5 criteria have expected names."""
        closes = [100.0] * 30
        opens = [c + 0.5 for c in closes]
        highs = [c + 1.0 for c in closes]
        lows = [c - 0.5 for c in closes]
        volumes = [1000000] * 30

        criteria, _, _, _ = evaluator.evaluate_criteria(
            opens, highs, lows, closes, volumes
        )

        names = [c.name for c in criteria]
        expected = ["trend", "ma20_distance", "candle", "volume", "momentum"]
        assert names == expected
