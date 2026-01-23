"""Indicator registry for dynamic indicator calculation.

This module provides a registry pattern for indicator calculations,
enabling the unified analysis endpoint to calculate requested indicators
dynamically.
"""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable

from app.indicators.candlestick import analyze_latest_candle
from app.indicators.candlestick_interpretation import interpret_pattern_in_context
from app.indicators.cci_analysis import CCIDirection, CCIZone, analyze_cci
from app.indicators.ma_analysis import analyze_ma_distance
from app.indicators.trend import detect_trend
from app.indicators.volume import detect_volume_signal

logger = logging.getLogger(__name__)


class IndicatorType(str, Enum):
    """Available indicator types for analysis endpoint."""

    TREND = "trend"
    MA20_DISTANCE = "ma20_distance"
    CANDLE_PATTERN = "candle_pattern"
    VOLUME_SIGNAL = "volume_signal"
    CCI = "cci"


@dataclass
class PriceData:
    """Container for OHLCV price data arrays."""

    opens: list[float]
    highs: list[float]
    lows: list[float]
    closes: list[float]
    volumes: list[float]


def calculate_trend(price_data: PriceData) -> dict[str, Any]:
    """Calculate 10-day trend indicator."""
    closes = price_data.closes
    trend = detect_trend(closes, period=10)

    # Calculate strength as % change over period
    if len(closes) >= 10:
        strength = ((closes[-1] - closes[-10]) / closes[-10]) * 100
    else:
        strength = 0.0

    return {
        "direction": trend.value,
        "strength": round(strength, 2),
        "period_days": 10,
    }


def calculate_ma20_distance(price_data: PriceData) -> dict[str, Any]:
    """Calculate MA20 distance indicator."""
    closes = price_data.closes
    ma_analysis = analyze_ma_distance(closes, period=20)

    return {
        "percent_distance": round(ma_analysis.distance_pct, 2),
        "current_price": round(closes[-1], 2),
        "ma20_value": round(ma_analysis.ma_value, 2),
        "position": ma_analysis.price_position.value,
    }


def calculate_candle_pattern(price_data: PriceData) -> dict[str, Any]:
    """Calculate candlestick pattern indicator."""
    opens = price_data.opens
    highs = price_data.highs
    lows = price_data.lows
    closes = price_data.closes

    # Get trend for context interpretation
    trend = detect_trend(closes, period=10)

    # Analyze the most recent candle
    candle = analyze_latest_candle(opens, highs, lows, closes)
    pattern_interpretation = interpret_pattern_in_context(candle, trend)

    # is_reversal is true if pattern aligns for either long or short
    is_reversal = (
        pattern_interpretation.aligned_for_long or pattern_interpretation.aligned_for_short
    )

    return {
        "raw_pattern": candle.raw_pattern.value,
        "interpreted_pattern": pattern_interpretation.interpreted_pattern.value,
        "is_reversal": is_reversal,
        "aligned_for_long": pattern_interpretation.aligned_for_long,
        "aligned_for_short": pattern_interpretation.aligned_for_short,
        "explanation": pattern_interpretation.explanation,
    }


def calculate_volume_signal(price_data: PriceData) -> dict[str, Any]:
    """Calculate volume signal indicator."""
    opens = price_data.opens
    closes = price_data.closes
    volumes = price_data.volumes

    volume_signal = detect_volume_signal(opens, closes, volumes)

    return {
        "rvol": round(volume_signal.rvol, 2),
        "approach": volume_signal.approach.value,
        "aligned_for_long": volume_signal.aligned_for_long,
        "aligned_for_short": volume_signal.aligned_for_short,
        "description": volume_signal.description,
    }


def calculate_cci(price_data: PriceData) -> dict[str, Any]:
    """Calculate CCI momentum indicator."""
    highs = price_data.highs
    lows = price_data.lows
    closes = price_data.closes

    cci_analysis = analyze_cci(highs, lows, closes, period=14)

    # Determine alignment (same logic as existing endpoint)
    aligned_for_long = cci_analysis.zone == CCIZone.OVERSOLD or (
        cci_analysis.zone == CCIZone.NEUTRAL and cci_analysis.direction == CCIDirection.RISING
    )
    aligned_for_short = cci_analysis.zone == CCIZone.OVERBOUGHT or (
        cci_analysis.zone == CCIZone.NEUTRAL and cci_analysis.direction == CCIDirection.FALLING
    )

    return {
        "value": round(cci_analysis.value, 2),
        "zone": cci_analysis.zone.value,
        "direction": cci_analysis.direction.value,
        "aligned_for_long": aligned_for_long,
        "aligned_for_short": aligned_for_short,
    }


# Registry mapping indicator types to calculation functions
INDICATOR_REGISTRY: dict[IndicatorType, Callable[[PriceData], dict[str, Any]]] = {
    IndicatorType.TREND: calculate_trend,
    IndicatorType.MA20_DISTANCE: calculate_ma20_distance,
    IndicatorType.CANDLE_PATTERN: calculate_candle_pattern,
    IndicatorType.VOLUME_SIGNAL: calculate_volume_signal,
    IndicatorType.CCI: calculate_cci,
}


def calculate_indicators(
    price_data: PriceData,
    indicator_types: list[IndicatorType],
) -> dict[str, dict[str, Any]]:
    """Calculate multiple indicators from price data.

    Args:
        price_data: OHLCV price data
        indicator_types: List of indicators to calculate

    Returns:
        Dictionary mapping indicator names to their results
    """
    results = {}
    for indicator_type in indicator_types:
        calculator = INDICATOR_REGISTRY.get(indicator_type)
        if calculator:
            try:
                results[indicator_type.value] = calculator(price_data)
            except Exception as e:
                logger.error(f"Error calculating {indicator_type.value}: {e}")
                results[indicator_type.value] = {"error": str(e)}
    return results
