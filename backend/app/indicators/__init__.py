"""Technical indicators package for Trading Analyst.

This package provides efficient implementations of common technical indicators
used in pattern detection and financial analysis.

Available indicators:
- Simple Moving Average (SMA)
- Exponential Moving Average (EMA)
- Relative Strength Index (RSI)
- Bollinger Bands
- Volume Weighted Average Price (VWAP)
- Candlestick Pattern Detection
- Trend Analysis
- Volume Analysis
- Moving Average Analysis
- CCI Analysis
"""

from .technical import bollinger_bands
from .technical import bollinger_band_width
from .technical import exponential_moving_average
from .technical import percentile_rank
from .technical import relative_strength_index
from .technical import simple_moving_average
from .candlestick import (
    CandlePattern,
    CandleType,
    BodySize,
    CandleAnalysis,
    analyze_candle,
    analyze_latest_candle,
)
from .trend import (
    TrendDirection,
    detect_trend,
    detect_weekly_trend,
    detect_monthly_trend,
)
from .ma_analysis import (
    PricePosition,
    MASlope,
    MAAnalysis,
    analyze_ma_distance,
)
from .cci_analysis import (
    CCIZone,
    CCIDirection,
    CCISignalType,
    CCIAnalysis,
    analyze_cci,
)
from .rsi2_analysis import (
    RSI2Analysis,
    analyze_rsi2,
)
from .three_candle_patterns import (
    ThreeCandlePattern,
    ThreeCandleAnalysis,
    analyze_three_candles,
)
from .two_candle_patterns import (
    TwoCandlePattern,
    TwoCandleAnalysis,
    analyze_two_candles,
)
from .volume import (
    VolumeApproach,
    VolumeSignalAnalysis,
    calculate_volume_vs_previous_day,
    detect_volume_signal,
)
from .registry import (
    IndicatorType,
    PriceData,
    INDICATOR_REGISTRY,
    calculate_indicators,
)
from .multi_day_patterns import (
    PatternDuration,
    MultiDayPatternResult,
    analyze_multi_day_patterns,
)

__all__ = [
    "simple_moving_average",
    "exponential_moving_average",
    "relative_strength_index",
    "bollinger_bands",
    "bollinger_band_width",
    "percentile_rank",
    "CandlePattern",
    "CandleType",
    "BodySize",
    "CandleAnalysis",
    "analyze_candle",
    "analyze_latest_candle",
    "TrendDirection",
    "detect_trend",
    "detect_weekly_trend",
    "detect_monthly_trend",
    "PricePosition",
    "MASlope",
    "MAAnalysis",
    "analyze_ma_distance",
    "CCIZone",
    "CCIDirection",
    "CCISignalType",
    "CCIAnalysis",
    "analyze_cci",
    "RSI2Analysis",
    "analyze_rsi2",
    "ThreeCandlePattern",
    "ThreeCandleAnalysis",
    "analyze_three_candles",
    "TwoCandlePattern",
    "TwoCandleAnalysis",
    "analyze_two_candles",
    "VolumeApproach",
    "VolumeSignalAnalysis",
    "calculate_volume_vs_previous_day",
    "detect_volume_signal",
    "IndicatorType",
    "PriceData",
    "INDICATOR_REGISTRY",
    "calculate_indicators",
    "PatternDuration",
    "MultiDayPatternResult",
    "analyze_multi_day_patterns",
]
