"""Technical indicators utility module.

This module provides shared technical indicator calculation functions used by
both AnalyticsService and SimulationService to avoid code duplication.

All functions use pandas and numpy for calculations, following the same approach
as the original AnalyticsService implementation.
"""
import numpy as np
import pandas as pd


def calculate_sma(data: pd.DataFrame, column: str = "Close", window: int = 50) -> pd.Series:
    """Calculate Simple Moving Average.

    Args:
        data: DataFrame with OHLCV data
        column: Column name to calculate SMA on (default: "Close")
        window: Number of periods for the moving average

    Returns:
        Series with SMA values
    """
    return data[column].rolling(window=window).mean()


def calculate_atr(data: pd.DataFrame, period: int = 14) -> pd.Series:
    """Calculate Average True Range.

    True Range = max(high - low, |high - prev_close|, |low - prev_close|)
    ATR = Simple Moving Average of True Range over period

    Args:
        data: DataFrame with OHLCV data (must have High, Low, Close columns)
        period: Number of periods for ATR calculation (default: 14)

    Returns:
        Series with ATR values
    """
    high_low = data["High"] - data["Low"]
    high_close = np.abs(data["High"] - data["Close"].shift())
    low_close = np.abs(data["Low"] - data["Close"].shift())
    true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    atr = true_range.rolling(window=period).mean()
    return atr
