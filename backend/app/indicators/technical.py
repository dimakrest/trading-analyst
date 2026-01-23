"""Technical indicators implementation for Trading Analyst.

This module provides efficient, NumPy-based implementations of common technical
indicators used in financial analysis and pattern detection.

All functions are designed to handle edge cases gracefully and return NaN values
for insufficient data points where appropriate.
"""

import warnings

import numpy as np
from numpy.typing import NDArray


def simple_moving_average(
    prices: list[float] | NDArray[np.float64], period: int
) -> NDArray[np.float64]:
    """Calculate Simple Moving Average (SMA).

    The SMA is calculated as the arithmetic mean of the last n periods.
    Formula: SMA = (P1 + P2 + ... + Pn) / n

    Args:
        prices: Price data as list or numpy array
        period: Number of periods for the average (must be > 0)

    Returns:
        Array of SMA values. NaN for insufficient data points.

    Raises:
        ValueError: If period <= 0 or prices is empty

    Example:
        >>> prices = [1, 2, 3, 4, 5]
        >>> sma = simple_moving_average(prices, 3)
        >>> # Returns [NaN, NaN, 2.0, 3.0, 4.0]
    """
    if period <= 0:
        raise ValueError("Period must be greater than 0")

    prices_array = np.array(prices, dtype=float)

    if len(prices_array) == 0:
        raise ValueError("Prices array cannot be empty")

    if len(prices_array) < period:
        return np.full(len(prices_array), np.nan)

    sma = np.full(len(prices_array), np.nan)

    # Use convolution for efficient calculation
    kernel = np.ones(period) / period
    valid_sma = np.convolve(prices_array, kernel, mode="valid")
    sma[period - 1 :] = valid_sma

    return sma


def exponential_moving_average(
    prices: list[float] | NDArray[np.float64], period: int
) -> NDArray[np.float64]:
    """Calculate Exponential Moving Average (EMA).

    The EMA gives more weight to recent prices, making it more responsive
    to price changes than SMA.
    Formula: EMA = α * Price + (1 - α) * Previous_EMA
    where α = 2 / (period + 1)

    Args:
        prices: Price data as list or numpy array
        period: Number of periods for the average (must be > 0)

    Returns:
        Array of EMA values. First value is the first price.

    Raises:
        ValueError: If period <= 0 or prices is empty

    Example:
        >>> prices = [1, 2, 3, 4, 5]
        >>> ema = exponential_moving_average(prices, 3)
    """
    if period <= 0:
        raise ValueError("Period must be greater than 0")

    prices_array = np.array(prices, dtype=float)

    if len(prices_array) == 0:
        raise ValueError("Prices array cannot be empty")

    alpha = 2.0 / (period + 1)
    ema = np.full(len(prices_array), np.nan)
    ema[0] = prices_array[0]  # Initialize with first price

    for i in range(1, len(prices_array)):
        ema[i] = alpha * prices_array[i] + (1 - alpha) * ema[i - 1]

    return ema


def relative_strength_index(
    prices: list[float] | NDArray[np.float64], period: int = 14
) -> NDArray[np.float64]:
    """Calculate Relative Strength Index (RSI).

    RSI is a momentum oscillator that measures the speed and magnitude
    of price changes. Values range from 0 to 100.
    Formula: RSI = 100 - (100 / (1 + RS))
    where RS = Average Gain / Average Loss

    Args:
        prices: Price data as list or numpy array
        period: RSI calculation period (default 14, must be > 0)

    Returns:
        Array of RSI values (0-100). NaN for insufficient data.

    Raises:
        ValueError: If period <= 0 or prices is empty

    Example:
        >>> prices = [44, 44.34, 44.09, 44.15, 43.61, 44.33, 44.83]
        >>> rsi = relative_strength_index(prices, 6)
    """
    if period <= 0:
        raise ValueError("Period must be greater than 0")

    prices_array = np.array(prices, dtype=float)

    if len(prices_array) == 0:
        raise ValueError("Prices array cannot be empty")

    if len(prices_array) < 2:
        return np.full(len(prices_array), np.nan)

    # Calculate price changes
    delta = np.diff(prices_array)

    # Separate gains and losses
    gains = np.where(delta > 0, delta, 0)
    losses = np.where(delta < 0, -delta, 0)

    # Calculate average gains and losses using SMA
    avg_gains = simple_moving_average(gains, period)
    avg_losses = simple_moving_average(losses, period)

    # Calculate RSI, avoiding division by zero
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        rs = np.where(avg_losses != 0, avg_gains / avg_losses, 0)
        rsi = 100 - (100 / (1 + rs))

    # Handle edge cases where avg_losses is 0 (all gains)
    rsi = np.where(avg_losses == 0, 100, rsi)

    # Prepend NaN for first price (no delta available)
    return np.concatenate([[np.nan], rsi])


def bollinger_bands(
    prices: list[float] | NDArray[np.float64], period: int = 20, std_dev: float = 2.0
) -> tuple[NDArray[np.float64], NDArray[np.float64], NDArray[np.float64]]:
    """Calculate Bollinger Bands.

    Bollinger Bands consist of a middle band (SMA) and two outer bands
    that are standard deviations away from the middle band.

    Args:
        prices: Price data as list or numpy array
        period: Moving average period (default 20, must be > 0)
        std_dev: Standard deviation multiplier (default 2.0, must be > 0)

    Returns:
        Tuple of (upper_band, middle_band, lower_band) as numpy arrays

    Raises:
        ValueError: If period <= 0, std_dev <= 0, or prices is empty

    Example:
        >>> prices = [20, 21, 22, 23, 24, 25, 26, 27, 28, 29]
        >>> upper, middle, lower = bollinger_bands(prices, 5, 2.0)
    """
    if period <= 0:
        raise ValueError("Period must be greater than 0")

    if std_dev <= 0:
        raise ValueError("Standard deviation multiplier must be greater than 0")

    prices_array = np.array(prices, dtype=float)

    if len(prices_array) == 0:
        raise ValueError("Prices array cannot be empty")

    # Calculate middle band (SMA)
    middle_band = simple_moving_average(prices_array, period)

    # Calculate rolling standard deviation efficiently
    std = np.full(len(prices_array), np.nan)

    if len(prices_array) >= period:
        # Use pandas-style rolling std calculation for efficiency
        for i in range(period - 1, len(prices_array)):
            window_data = prices_array[i - period + 1 : i + 1]
            std[i] = np.std(window_data, ddof=0)  # Population std, not sample

    # Calculate upper and lower bands
    upper_band = middle_band + (std_dev * std)
    lower_band = middle_band - (std_dev * std)

    return upper_band, middle_band, lower_band


def typical_price(
    high: list[float] | NDArray[np.float64],
    low: list[float] | NDArray[np.float64],
    close: list[float] | NDArray[np.float64],
) -> NDArray[np.float64]:
    """Calculate Typical Price.

    Typical Price is the average of high, low, and close prices.
    Formula: TP = (High + Low + Close) / 3

    Args:
        high: High prices as list or numpy array
        low: Low prices as list or numpy array
        close: Close prices as list or numpy array

    Returns:
        Array of typical price values

    Raises:
        ValueError: If arrays have different lengths or are empty

    Example:
        >>> high = [102, 103, 104]
        >>> low = [98, 99, 100]
        >>> close = [100, 101, 102]
        >>> tp = typical_price(high, low, close)
    """
    high_array = np.array(high, dtype=float)
    low_array = np.array(low, dtype=float)
    close_array = np.array(close, dtype=float)

    if len(high_array) != len(low_array) or len(high_array) != len(close_array):
        raise ValueError("High, low, and close arrays must have same length")

    if len(high_array) == 0:
        raise ValueError("Arrays cannot be empty")

    result: NDArray[np.float64] = (high_array + low_array + close_array) / 3.0
    return result


def commodity_channel_index(
    high: list[float] | NDArray[np.float64],
    low: list[float] | NDArray[np.float64],
    close: list[float] | NDArray[np.float64],
    period: int = 20,
) -> NDArray[np.float64]:
    """Calculate Commodity Channel Index (CCI).

    CCI measures the current price level relative to an average price level
    over a given period. High positive readings indicate prices are well above
    their average, which is strength. Low negative readings indicate prices
    are well below their average, which is weakness.

    Formula: CCI = (TP - SMA(TP)) / (0.015 * Mean Deviation)
    where TP = Typical Price = (High + Low + Close) / 3

    Args:
        high: High prices as list or numpy array
        low: Low prices as list or numpy array
        close: Close prices as list or numpy array
        period: CCI calculation period (default 20, must be > 0)

    Returns:
        Array of CCI values. NaN for insufficient data.

    Raises:
        ValueError: If period <= 0, arrays have different lengths, or arrays are empty

    Example:
        >>> high = [102, 103, 104, 105, 106]
        >>> low = [98, 99, 100, 101, 102]
        >>> close = [100, 101, 102, 103, 104]
        >>> cci = commodity_channel_index(high, low, close, 5)
    """
    if period <= 0:
        raise ValueError("Period must be greater than 0")

    # Calculate typical price (this validates array lengths and emptiness)
    tp = typical_price(high, low, close)

    if len(tp) < period:
        return np.full(len(tp), np.nan)

    # Calculate SMA of typical price
    tp_sma = simple_moving_average(tp, period)

    # Calculate mean deviation
    mean_dev = np.full(len(tp), np.nan)
    for i in range(period - 1, len(tp)):
        window = tp[i - period + 1 : i + 1]
        mean_dev[i] = np.mean(np.abs(window - tp_sma[i]))

    # Calculate CCI
    # Constant 0.015 is Lambert's constant to scale CCI to +/- 100 range
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        cci = np.where(mean_dev != 0, (tp - tp_sma) / (0.015 * mean_dev), 0)

    # Set NaN for insufficient data
    cci[:period - 1] = np.nan

    return cci


def detect_cci_signals(
    cci_values: list[float] | NDArray[np.float64],
) -> list[str | None]:
    """Detect CCI trading signals based on +100/-100 crossovers.

    Signal Types:
    - "momentum_bullish": CCI crosses above +100 (upward momentum)
    - "momentum_bearish": CCI crosses below -100 (downward momentum)
    - "reversal_buy": CCI was below -100 and crosses back above -100
    - "reversal_sell": CCI was above +100 and crosses back below +100

    Args:
        cci_values: Array of CCI values

    Returns:
        List of signal strings (or None for no signal) for each data point
    """
    cci_array = np.array(cci_values, dtype=float)
    signals: list[str | None] = [None] * len(cci_array)

    if len(cci_array) < 2:
        return signals

    # Track if we're in overbought (>100) or oversold (<-100) territory
    was_above_100 = False
    was_below_minus_100 = False

    for i in range(1, len(cci_array)):
        prev = cci_array[i - 1]
        curr = cci_array[i]

        # Skip if either value is NaN
        if np.isnan(prev) or np.isnan(curr):
            continue

        # Momentum signals: crossing the threshold
        if prev <= 100 and curr > 100:
            signals[i] = "momentum_bullish"
            was_above_100 = True
        elif prev >= -100 and curr < -100:
            signals[i] = "momentum_bearish"
            was_below_minus_100 = True

        # Reversal signals: crossing back through threshold
        elif was_above_100 and prev >= 100 and curr < 100:
            signals[i] = "reversal_sell"
            was_above_100 = False
        elif was_below_minus_100 and prev <= -100 and curr > -100:
            signals[i] = "reversal_buy"
            was_below_minus_100 = False

        # Update territory tracking
        # Reset opposite flag when entering extreme territory (handles gap moves)
        if curr > 100:
            was_above_100 = True
            was_below_minus_100 = False  # Exited oversold territory
        elif curr < -100:
            was_below_minus_100 = True
            was_above_100 = False  # Exited overbought territory

    return signals


def macd(
    prices: list[float] | NDArray[np.float64],
    fast_period: int = 12,
    slow_period: int = 26,
    signal_period: int = 9,
) -> tuple[NDArray[np.float64], NDArray[np.float64], NDArray[np.float64]]:
    """Calculate Moving Average Convergence Divergence (MACD).

    MACD Line = EMA(fast_period) - EMA(slow_period)
    Signal Line = EMA(MACD Line, signal_period)
    Histogram = MACD Line - Signal Line

    Args:
        prices: Price data as list or numpy array
        fast_period: Fast EMA period (default 12)
        slow_period: Slow EMA period (default 26)
        signal_period: Signal line EMA period (default 9)

    Returns:
        Tuple of (macd_line, signal_line, histogram) as numpy arrays

    Raises:
        ValueError: If periods are invalid or prices is empty

    Example:
        >>> prices = [100, 101, 102, 103, 104, ...]  # Need 35+ prices
        >>> macd_line, signal_line, histogram = macd(prices)
    """
    if fast_period <= 0 or slow_period <= 0 or signal_period <= 0:
        raise ValueError("All periods must be greater than 0")
    if fast_period >= slow_period:
        raise ValueError("Fast period must be less than slow period")

    prices_array = np.array(prices, dtype=float)

    if len(prices_array) == 0:
        raise ValueError("Prices array cannot be empty")

    # Calculate EMAs
    fast_ema = exponential_moving_average(prices_array, fast_period)
    slow_ema = exponential_moving_average(prices_array, slow_period)

    # MACD Line
    macd_line = fast_ema - slow_ema

    # Signal Line (EMA of MACD)
    signal_line = exponential_moving_average(macd_line, signal_period)

    # Histogram
    histogram = macd_line - signal_line

    return macd_line, signal_line, histogram


def stochastic_oscillator(
    high: list[float] | NDArray[np.float64],
    low: list[float] | NDArray[np.float64],
    close: list[float] | NDArray[np.float64],
    k_period: int = 14,
    d_period: int = 3,
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """Calculate Stochastic Oscillator (%K and %D).

    %K = (Current Close - Lowest Low) / (Highest High - Lowest Low) * 100
    %D = SMA(%K, d_period)

    Args:
        high: High prices as list or numpy array
        low: Low prices as list or numpy array
        close: Close prices as list or numpy array
        k_period: Lookback period for %K (default 14)
        d_period: Smoothing period for %D (default 3)

    Returns:
        Tuple of (k_values, d_values) as numpy arrays

    Raises:
        ValueError: If arrays have different lengths or periods are invalid

    Example:
        >>> high = [110, 112, 115, ...]
        >>> low = [100, 102, 105, ...]
        >>> close = [105, 108, 110, ...]
        >>> k, d = stochastic_oscillator(high, low, close)
    """
    if k_period <= 0 or d_period <= 0:
        raise ValueError("Periods must be greater than 0")

    high_array = np.array(high, dtype=float)
    low_array = np.array(low, dtype=float)
    close_array = np.array(close, dtype=float)

    if len(high_array) != len(low_array) or len(high_array) != len(close_array):
        raise ValueError("High, low, and close arrays must have same length")

    if len(high_array) == 0:
        raise ValueError("Arrays cannot be empty")

    n = len(high_array)
    k_values = np.full(n, np.nan)

    for i in range(k_period - 1, n):
        highest_high = np.max(high_array[i - k_period + 1 : i + 1])
        lowest_low = np.min(low_array[i - k_period + 1 : i + 1])

        if highest_high != lowest_low:
            k_values[i] = ((close_array[i] - lowest_low) / (highest_high - lowest_low)) * 100
        else:
            k_values[i] = 50  # Neutral when no range

    # %D is SMA of %K
    d_values = simple_moving_average(k_values, d_period)

    return k_values, d_values


def average_directional_index(
    high: list[float] | NDArray[np.float64],
    low: list[float] | NDArray[np.float64],
    close: list[float] | NDArray[np.float64],
    period: int = 14,
) -> tuple[NDArray[np.float64], NDArray[np.float64], NDArray[np.float64]]:
    """Calculate Average Directional Index (ADX) with Plus/Minus DI.

    ADX measures trend strength (0-100), regardless of direction.
    +DI measures upward trend strength.
    -DI measures downward trend strength.

    Args:
        high: High prices as list or numpy array
        low: Low prices as list or numpy array
        close: Close prices as list or numpy array
        period: ADX calculation period (default 14)

    Returns:
        Tuple of (adx, plus_di, minus_di) as numpy arrays

    Raises:
        ValueError: If arrays have different lengths or period is invalid

    Example:
        >>> high = [110, 112, 115, ...]
        >>> low = [100, 102, 105, ...]
        >>> close = [105, 108, 110, ...]
        >>> adx, plus_di, minus_di = average_directional_index(high, low, close)
    """
    if period <= 0:
        raise ValueError("Period must be greater than 0")

    high_array = np.array(high, dtype=float)
    low_array = np.array(low, dtype=float)
    close_array = np.array(close, dtype=float)

    if len(high_array) != len(low_array) or len(high_array) != len(close_array):
        raise ValueError("High, low, and close arrays must have same length")

    if len(high_array) == 0:
        raise ValueError("Arrays cannot be empty")

    n = len(high_array)

    # Calculate True Range
    tr = np.zeros(n)
    tr[0] = high_array[0] - low_array[0]
    for i in range(1, n):
        hl = high_array[i] - low_array[i]
        hc = abs(high_array[i] - close_array[i - 1])
        lc = abs(low_array[i] - close_array[i - 1])
        tr[i] = max(hl, hc, lc)

    # Calculate +DM and -DM
    plus_dm = np.zeros(n)
    minus_dm = np.zeros(n)
    for i in range(1, n):
        up_move = high_array[i] - high_array[i - 1]
        down_move = low_array[i - 1] - low_array[i]

        if up_move > down_move and up_move > 0:
            plus_dm[i] = up_move
        if down_move > up_move and down_move > 0:
            minus_dm[i] = down_move

    # Wilder's cumulative smoothing for TR, +DM, -DM
    # Formula: result = prev - prev/period + value (produces "smoothed sum")
    # Used for values that will be normalized by division (e.g., +DI = smoothed_+DM / ATR)
    def wilder_smooth_cumulative(
        arr: NDArray[np.float64], smooth_period: int
    ) -> NDArray[np.float64]:
        result = np.full(len(arr), np.nan)
        if len(arr) < smooth_period:
            return result

        # Find the first non-NaN index to handle arrays that start with NaN
        first_valid_idx = 0
        for i in range(len(arr)):
            if not np.isnan(arr[i]):
                first_valid_idx = i
                break
        else:
            return result

        valid_count = len(arr) - first_valid_idx
        if valid_count < smooth_period:
            return result

        init_idx = first_valid_idx + smooth_period - 1
        # Initial value is SUM (cumulative)
        result[init_idx] = np.sum(arr[first_valid_idx : first_valid_idx + smooth_period])

        for i in range(init_idx + 1, len(arr)):
            result[i] = result[i - 1] - (result[i - 1] / smooth_period) + arr[i]
        return result

    # Wilder's average smoothing for DX → ADX
    # Formula: result = prev * (period-1)/period + value/period (produces "smoothed average")
    # Used for values that are already normalized percentages (e.g., DX is 0-100)
    def wilder_smooth_average(
        arr: NDArray[np.float64], smooth_period: int
    ) -> NDArray[np.float64]:
        result = np.full(len(arr), np.nan)
        if len(arr) < smooth_period:
            return result

        # Find the first non-NaN index to handle arrays that start with NaN
        first_valid_idx = 0
        for i in range(len(arr)):
            if not np.isnan(arr[i]):
                first_valid_idx = i
                break
        else:
            return result

        valid_count = len(arr) - first_valid_idx
        if valid_count < smooth_period:
            return result

        init_idx = first_valid_idx + smooth_period - 1
        # Initial value is AVERAGE
        result[init_idx] = np.mean(arr[first_valid_idx : first_valid_idx + smooth_period])

        for i in range(init_idx + 1, len(arr)):
            result[i] = (
                result[i - 1] * (smooth_period - 1) / smooth_period
                + arr[i] / smooth_period
            )
        return result

    atr = wilder_smooth_cumulative(tr, period)
    smoothed_plus_dm = wilder_smooth_cumulative(plus_dm, period)
    smoothed_minus_dm = wilder_smooth_cumulative(minus_dm, period)

    # Calculate +DI and -DI
    plus_di = np.full(n, np.nan)
    minus_di = np.full(n, np.nan)

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        valid = atr != 0
        plus_di[valid] = (smoothed_plus_dm[valid] / atr[valid]) * 100
        minus_di[valid] = (smoothed_minus_dm[valid] / atr[valid]) * 100

    # Calculate DX and ADX
    dx = np.full(n, np.nan)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        sum_di = plus_di + minus_di
        valid = sum_di != 0
        dx[valid] = (np.abs(plus_di[valid] - minus_di[valid]) / sum_di[valid]) * 100

    # ADX is smoothed DX (using average smoothing since DX is already a percentage 0-100)
    adx = wilder_smooth_average(dx, period)

    return adx, plus_di, minus_di


def bollinger_band_width(
    prices: list[float] | NDArray[np.float64],
    period: int = 20,
    std_dev: float = 2.0,
) -> NDArray[np.float64]:
    """Calculate Bollinger Band Width (BBW).

    BBW measures the width of Bollinger Bands relative to the middle band.
    Formula: BBW = (Upper Band - Lower Band) / Middle Band

    Lower values indicate tighter consolidation (squeeze).
    Higher values indicate expanded volatility.

    Args:
        prices: Price data as list or numpy array
        period: Moving average period (default 20)
        std_dev: Standard deviation multiplier (default 2.0)

    Returns:
        Array of BBW values. NaN for insufficient data.
    """
    upper, middle, lower = bollinger_bands(prices, period, std_dev)

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        bbw = np.where(middle != 0, (upper - lower) / middle, np.nan)

    return bbw


def percentile_rank(
    values: list[float] | NDArray[np.float64],
    lookback: int = 90,
) -> NDArray[np.float64]:
    """Calculate rolling percentile rank.

    For each value, calculates what percentile it falls into
    relative to the previous `lookback` values.

    A value in the 5th percentile means it's lower than 95% of recent values.
    For BBW, low percentile = tight squeeze = high energy potential.

    Args:
        values: Data values as list or numpy array
        lookback: Number of periods for percentile calculation (default 90)

    Returns:
        Array of percentile values (0-100). NaN for insufficient data.
    """
    values_array = np.array(values, dtype=float)
    n = len(values_array)
    result = np.full(n, np.nan)

    for i in range(lookback - 1, n):
        window = values_array[i - lookback + 1 : i + 1]
        # Handle NaN values in window
        valid_values = window[~np.isnan(window)]
        if len(valid_values) < lookback // 2:  # Require at least half valid
            continue
        current = values_array[i]
        if np.isnan(current):
            continue
        # Percentile: what % of values are below current
        percentile = (np.sum(valid_values < current) / len(valid_values)) * 100
        result[i] = percentile

    return result


def support_resistance_levels(
    high: list[float] | NDArray[np.float64],
    low: list[float] | NDArray[np.float64],
    close: list[float] | NDArray[np.float64],
    num_levels: int = 3,
) -> tuple[list[float | None], list[float | None], float | None]:
    """Calculate support, resistance levels and pivot point using Standard Pivot Points.

    Pivot Point (PP) = (High + Low + Close) / 3
    Support 1 (S1) = (2 * PP) - High
    Resistance 1 (R1) = (2 * PP) - Low
    Support 2 (S2) = PP - (High - Low)
    Resistance 2 (R2) = PP + (High - Low)
    Support 3 (S3) = Low - 2 * (High - PP)
    Resistance 3 (R3) = High + 2 * (PP - Low)

    Args:
        high: High prices (uses most recent for calculation)
        low: Low prices (uses most recent for calculation)
        close: Close prices (uses most recent for calculation)
        num_levels: Number of support/resistance levels to return (default 3)

    Returns:
        Tuple of (support_levels, resistance_levels, pivot_point)
        Each list has num_levels values, sorted by proximity to current price

    Example:
        >>> high = [105, 108, 110]
        >>> low = [100, 103, 105]
        >>> close = [103, 106, 108]
        >>> support, resistance, pivot = support_resistance_levels(high, low, close)
    """
    high_array = np.array(high, dtype=float)
    low_array = np.array(low, dtype=float)
    close_array = np.array(close, dtype=float)

    if len(high_array) == 0:
        return [None] * num_levels, [None] * num_levels, None

    # Use most recent candle for pivot calculation
    h = high_array[-1]
    low_val = low_array[-1]
    c = close_array[-1]

    pp = (h + low_val + c) / 3

    # Calculate levels
    r1 = (2 * pp) - low_val
    s1 = (2 * pp) - h
    r2 = pp + (h - low_val)
    s2 = pp - (h - low_val)
    r3 = h + 2 * (pp - low_val)
    s3 = low_val - 2 * (h - pp)

    support_levels: list[float | None] = [s1, s2, s3][:num_levels]
    resistance_levels: list[float | None] = [r1, r2, r3][:num_levels]

    return support_levels, resistance_levels, pp
