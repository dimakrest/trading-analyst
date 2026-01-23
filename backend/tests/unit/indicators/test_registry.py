"""Unit tests for indicator registry."""

import pytest

from app.indicators.registry import (
    IndicatorType,
    PriceData,
    calculate_cci,
    calculate_candle_pattern,
    calculate_indicators,
    calculate_ma20_distance,
    calculate_trend,
    calculate_volume_signal,
)


@pytest.fixture
def sample_price_data() -> PriceData:
    """Generate sample price data for testing."""
    # 30 days of synthetic data with a downtrend
    base_price = 100.0
    closes = [base_price - i * 0.5 for i in range(30)]  # Downtrend
    opens = [c + 0.2 for c in closes]
    highs = [max(o, c) + 0.5 for o, c in zip(opens, closes)]
    lows = [min(o, c) - 0.5 for o, c in zip(opens, closes)]
    volumes = [1000000 + i * 10000 for i in range(30)]

    return PriceData(
        opens=opens,
        highs=highs,
        lows=lows,
        closes=closes,
        volumes=volumes,
    )


class TestCalculateTrend:
    """Tests for calculate_trend function."""

    def test_returns_direction(self, sample_price_data: PriceData):
        """Should return trend direction."""
        result = calculate_trend(sample_price_data)
        assert "direction" in result
        assert result["direction"] in ["bullish", "bearish", "neutral"]

    def test_returns_strength(self, sample_price_data: PriceData):
        """Should return trend strength as percentage."""
        result = calculate_trend(sample_price_data)
        assert "strength" in result
        assert isinstance(result["strength"], float)

    def test_returns_period_days(self, sample_price_data: PriceData):
        """Should return period days."""
        result = calculate_trend(sample_price_data)
        assert result["period_days"] == 10

    def test_detects_downtrend(self, sample_price_data: PriceData):
        """Should detect bearish trend from downtrending data."""
        result = calculate_trend(sample_price_data)
        assert result["direction"] == "bearish"
        assert result["strength"] < 0  # Negative strength for downtrend


class TestCalculateMA20Distance:
    """Tests for calculate_ma20_distance function."""

    def test_returns_percent_distance(self, sample_price_data: PriceData):
        """Should return percent distance from MA20."""
        result = calculate_ma20_distance(sample_price_data)
        assert "percent_distance" in result
        assert isinstance(result["percent_distance"], float)

    def test_returns_current_price(self, sample_price_data: PriceData):
        """Should return current price."""
        result = calculate_ma20_distance(sample_price_data)
        assert "current_price" in result
        assert isinstance(result["current_price"], float)

    def test_returns_ma20_value(self, sample_price_data: PriceData):
        """Should return MA20 value."""
        result = calculate_ma20_distance(sample_price_data)
        assert "ma20_value" in result
        assert isinstance(result["ma20_value"], float)

    def test_returns_position(self, sample_price_data: PriceData):
        """Should return position relative to MA."""
        result = calculate_ma20_distance(sample_price_data)
        assert "position" in result
        assert result["position"] in ["above", "below", "at"]


class TestCalculateCandlePattern:
    """Tests for calculate_candle_pattern function."""

    def test_returns_raw_pattern(self, sample_price_data: PriceData):
        """Should return raw pattern name."""
        result = calculate_candle_pattern(sample_price_data)
        assert "raw_pattern" in result

    def test_returns_interpreted_pattern(self, sample_price_data: PriceData):
        """Should return interpreted pattern name."""
        result = calculate_candle_pattern(sample_price_data)
        assert "interpreted_pattern" in result

    def test_returns_is_reversal(self, sample_price_data: PriceData):
        """Should return is_reversal flag."""
        result = calculate_candle_pattern(sample_price_data)
        assert "is_reversal" in result
        assert isinstance(result["is_reversal"], bool)

    def test_returns_alignment_flags(self, sample_price_data: PriceData):
        """Should return alignment flags."""
        result = calculate_candle_pattern(sample_price_data)
        assert "aligned_for_long" in result
        assert "aligned_for_short" in result
        assert isinstance(result["aligned_for_long"], bool)
        assert isinstance(result["aligned_for_short"], bool)

    def test_returns_explanation(self, sample_price_data: PriceData):
        """Should return explanation."""
        result = calculate_candle_pattern(sample_price_data)
        assert "explanation" in result
        assert isinstance(result["explanation"], str)


class TestCalculateVolumeSignal:
    """Tests for calculate_volume_signal function."""

    def test_returns_rvol(self, sample_price_data: PriceData):
        """Should return relative volume."""
        result = calculate_volume_signal(sample_price_data)
        assert "rvol" in result
        assert isinstance(result["rvol"], float)

    def test_returns_approach(self, sample_price_data: PriceData):
        """Should return volume approach classification."""
        result = calculate_volume_signal(sample_price_data)
        assert "approach" in result

    def test_returns_alignment_flags(self, sample_price_data: PriceData):
        """Should return alignment flags."""
        result = calculate_volume_signal(sample_price_data)
        assert "aligned_for_long" in result
        assert "aligned_for_short" in result

    def test_returns_description(self, sample_price_data: PriceData):
        """Should return description."""
        result = calculate_volume_signal(sample_price_data)
        assert "description" in result
        assert isinstance(result["description"], str)


class TestCalculateCCI:
    """Tests for calculate_cci function."""

    def test_returns_value(self, sample_price_data: PriceData):
        """Should return CCI value."""
        result = calculate_cci(sample_price_data)
        assert "value" in result
        assert isinstance(result["value"], float)

    def test_returns_zone(self, sample_price_data: PriceData):
        """Should return CCI zone."""
        result = calculate_cci(sample_price_data)
        assert "zone" in result
        assert result["zone"] in ["overbought", "oversold", "neutral"]

    def test_returns_direction(self, sample_price_data: PriceData):
        """Should return CCI direction."""
        result = calculate_cci(sample_price_data)
        assert "direction" in result
        assert result["direction"] in ["rising", "falling", "flat"]

    def test_returns_alignment_flags(self, sample_price_data: PriceData):
        """Should return alignment flags."""
        result = calculate_cci(sample_price_data)
        assert "aligned_for_long" in result
        assert "aligned_for_short" in result
        assert isinstance(result["aligned_for_long"], bool)
        assert isinstance(result["aligned_for_short"], bool)


class TestCalculateIndicators:
    """Tests for calculate_indicators function."""

    def test_calculates_single_indicator(self, sample_price_data: PriceData):
        """Should calculate a single requested indicator."""
        result = calculate_indicators(sample_price_data, [IndicatorType.TREND])
        assert "trend" in result
        assert len(result) == 1

    def test_calculates_multiple_indicators(self, sample_price_data: PriceData):
        """Should calculate multiple requested indicators."""
        result = calculate_indicators(
            sample_price_data,
            [IndicatorType.TREND, IndicatorType.CCI, IndicatorType.VOLUME_SIGNAL],
        )
        assert "trend" in result
        assert "cci" in result
        assert "volume_signal" in result
        assert len(result) == 3

    def test_calculates_all_indicators(self, sample_price_data: PriceData):
        """Should calculate all indicators when all requested."""
        all_types = list(IndicatorType)
        result = calculate_indicators(sample_price_data, all_types)
        assert len(result) == len(all_types)

    def test_returns_empty_for_empty_list(self, sample_price_data: PriceData):
        """Should return empty dict for empty indicator list."""
        result = calculate_indicators(sample_price_data, [])
        assert result == {}

    def test_indicator_values_match_direct_calls(self, sample_price_data: PriceData):
        """Should return same values as direct function calls."""
        result = calculate_indicators(
            sample_price_data,
            [IndicatorType.TREND, IndicatorType.CCI],
        )

        direct_trend = calculate_trend(sample_price_data)
        direct_cci = calculate_cci(sample_price_data)

        assert result["trend"] == direct_trend
        assert result["cci"] == direct_cci
