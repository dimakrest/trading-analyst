"""Volume analysis for Trading Analyst.

Provides functions to analyze volume trends and patterns using period-based
comparisons and volume-to-average calculations.

All functions analyze volume data relative to historical averages to identify
volume trends that may signal strength or weakness in price movements.
"""

from dataclasses import dataclass
from enum import Enum

import numpy as np
from numpy.typing import NDArray


class VolumeApproach(str, Enum):
    """Volume signal approach classification."""
    NONE = "none"


def calculate_volume_vs_previous_day(
    volumes: list[float] | NDArray[np.float64],
) -> float:
    """Calculate current volume as a percentage change from the previous day.

    Compares the most recent volume to the previous day's volume to determine
    if current volume is increasing, decreasing, or stable relative to yesterday.

    Args:
        volumes: Array of volume data

    Returns:
        Percentage change (e.g., 50.0 means current volume is +50% vs previous day,
        -20.0 means current volume is -20% vs previous day).
        Returns 0.0 if insufficient data or previous volume is zero.
    """
    volumes_array = np.array(volumes, dtype=float)

    if len(volumes_array) < 2:
        return 0.0  # Need at least 2 days of data

    current_volume = volumes_array[-1]
    previous_volume = volumes_array[-2]

    if previous_volume == 0:
        return 0.0  # Can't compare to zero

    return ((current_volume / previous_volume) - 1) * 100


@dataclass
class VolumeSignalAnalysis:
    """Result of combined volume signal analysis.

    This analysis uses a simplified volume ratio approach for conviction detection.
    The rvol field represents today's volume divided by yesterday's volume, which
    differs from traditional RVOL (current volume / 10-day average).
    """
    approach: VolumeApproach
    aligned_for_long: bool
    rvol: float  # Today/yesterday volume ratio (simplified conviction metric)
    description: str  # Human-readable explanation


def detect_volume_signal(
    opens: list[float] | NDArray[np.float64],
    closes: list[float] | NDArray[np.float64],
    volumes: list[float] | NDArray[np.float64],
) -> VolumeSignalAnalysis:
    """Detect volume signal by comparing today's volume to yesterday's.

    Simple conviction check:
    - LONG: Today's volume > yesterday's AND green candle (buyers stepping in)
    - SHORT: Today's volume > yesterday's AND red candle (sellers stepping in)
    - No alignment: Volume not higher (no conviction)

    Uses a simplified volume ratio (today/yesterday) rather than traditional
    RVOL (current/10-day average) for faster conviction detection.

    Args:
        opens: Array of opening prices
        closes: Array of closing prices
        volumes: Array of volume data

    Returns:
        VolumeSignalAnalysis with alignment, volume ratio, and description
    """
    opens_array = np.array(opens, dtype=float)
    closes_array = np.array(closes, dtype=float)
    volumes_array = np.array(volumes, dtype=float)

    # Need at least 2 data points (today and yesterday)
    if len(opens_array) < 2 or len(closes_array) < 2 or len(volumes_array) < 2:
        return VolumeSignalAnalysis(
            approach=VolumeApproach.NONE,
            aligned_for_long=False,
            rvol=1.0,
            description="Insufficient data for volume signal detection",
        )

    # Calculate volume ratio (today vs yesterday)
    today_volume = volumes_array[-1]
    yesterday_volume = volumes_array[-2]

    if yesterday_volume == 0:
        volume_ratio = 1.0
    else:
        volume_ratio = round(today_volume / yesterday_volume, 2)

    # Determine candle color
    # Note: Doji candles (open == close) are neither green nor red,
    # resulting in no alignment even with higher volume (indecision signal)
    current_open = opens_array[-1]
    current_close = closes_array[-1]
    is_green_candle = current_close > current_open
    is_red_candle = current_close < current_open

    # Higher volume = conviction
    higher_volume = today_volume > yesterday_volume

    # Alignment logic
    if higher_volume and is_green_candle:
        return VolumeSignalAnalysis(
            approach=VolumeApproach.NONE,  # No longer using complex approaches
            aligned_for_long=True,
            rvol=volume_ratio,
            description=f"Volume conviction: {volume_ratio}x yesterday, buyers stepping in",
        )
    if higher_volume and is_red_candle:
        return VolumeSignalAnalysis(
            approach=VolumeApproach.NONE,
            aligned_for_long=False,
            rvol=volume_ratio,
            description=f"Volume conviction: {volume_ratio}x yesterday, sellers stepping in",
        )

    # No conviction (volume not higher)
    return VolumeSignalAnalysis(
        approach=VolumeApproach.NONE,
        aligned_for_long=False,
        rvol=volume_ratio,
        description=f"No volume conviction: {volume_ratio}x yesterday",
    )
