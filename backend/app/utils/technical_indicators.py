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


def calculate_atr_percentage(
    highs: list[float],
    lows: list[float],
    closes: list[float],
    period: int = 14,
    price_override: float | None = None,
) -> float | None:
    """Calculate latest ATR as percentage of price.

    Standalone volatility metric independent of any pricing/entry strategy.
    Uses the latest closing price as denominator by default, or a custom price.

    Args:
        highs: List of high prices (oldest to newest)
        lows: List of low prices (oldest to newest)
        closes: List of closing prices (oldest to newest)
        period: ATR period (default 14)
        price_override: Optional price to use as denominator (defaults to closes[-1])

    Returns:
        Latest ATR as percentage (e.g., 4.25 for 4.25%), or None if insufficient data
    """
    if len(closes) < period + 1:
        return None

    denominator = price_override if price_override is not None else closes[-1]
    if denominator <= 0:
        return None

    df = pd.DataFrame({"High": highs, "Low": lows, "Close": closes})
    atr_series = calculate_atr(df, period=period)

    latest_atr_dollars = atr_series.iloc[-1]
    if pd.isna(latest_atr_dollars):
        return None

    return (float(latest_atr_dollars) / denominator) * 100
