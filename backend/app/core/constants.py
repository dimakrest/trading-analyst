"""Application-wide constants and thresholds.

All magic numbers should be defined here with clear documentation about their
purpose, source, and rationale. This centralizes configuration values and makes
them easy to tune and understand.
"""


class PatternThresholds:
    """Thresholds and constants for pattern detection algorithms."""

    # =========================================================================
    # Bull Flag Pattern Constants
    # =========================================================================
    # NOTE: Default values below are moderate. For stock-specific profiles,
    # use the BLUE_CHIP or GROWTH suffix constants.

    # Pole Requirements (Default/Moderate Profile)
    BULL_FLAG_MIN_POLE_GAIN = 0.15
    """
    Minimum gain required for the pole phase of bull flag pattern.
    15% minimum ensures significant upward momentum before consolidation.
    Source: Technical Analysis literature (Bulkowski, 2005)
    """

    BULL_FLAG_POLE_MIN_STRENGTH = 0.3
    """
    Minimum strength threshold for pole validity.
    Weak poles (< 30% strength) indicate insufficient momentum.
    """

    # Flag/Consolidation Phase
    BULL_FLAG_MAX_FLAG_RETRACEMENT = 0.5
    """
    Maximum retracement allowed during flag phase (50% of pole height).
    Deeper retracements suggest trend reversal rather than consolidation.
    Source: Classic chart pattern analysis
    """

    BULL_FLAG_SLOPE_TOLERANCE = 0.1
    """
    Tolerance for flag slope analysis.
    Allows for slight upward drift in consolidation phase.
    """

    BULL_FLAG_MAX_CONSOLIDATION_RANGE = 0.15
    """
    Maximum price range during consolidation phase (15%).
    Wider ranges indicate high volatility rather than consolidation.
    """

    # Pattern Strength Weights
    BULL_FLAG_POLE_STRENGTH_WEIGHT = 0.6
    BULL_FLAG_FLAG_STRENGTH_WEIGHT = 0.4
    """
    Weights for combining pole and flag strength into overall pattern strength.
    Pole is weighted higher (60%) as it's the primary momentum indicator.
    """

    BULL_FLAG_POLE_GAIN_WEIGHT = 0.4
    BULL_FLAG_POLE_LINEARITY_WEIGHT = 0.4
    BULL_FLAG_POLE_CONSISTENCY_WEIGHT = 0.2
    """
    Sub-weights for pole strength calculation.
    Gain and linearity are primary factors (40% each).
    """

    BULL_FLAG_FLAG_RETRACEMENT_WEIGHT = 0.3
    BULL_FLAG_FLAG_RANGE_WEIGHT = 0.3
    BULL_FLAG_FLAG_TREND_WEIGHT = 0.2
    BULL_FLAG_FLAG_VOLATILITY_WEIGHT = 0.2
    """
    Sub-weights for flag strength calculation.
    Retracement and range are primary factors (30% each).
    """

    # Duration Ratios
    BULL_FLAG_IDEAL_DURATION_RATIO_MIN = 0.3
    BULL_FLAG_IDEAL_DURATION_RATIO_MAX = 0.7
    """
    Ideal flag-to-pole duration ratio range (0.3-0.7).
    Classic patterns show flag lasting 30-70% of pole duration.
    """

    BULL_FLAG_DURATION_BONUS = 0.1
    """
    Strength bonus/penalty for duration ratio (±10%).
    """

    # Validation Thresholds
    BULL_FLAG_MIN_PATTERN_STRENGTH = 0.4
    """
    Minimum overall pattern strength to report (40%).
    Filters out weak or ambiguous patterns.
    """

    BULL_FLAG_MIN_SLOPE_R_VALUE = 0.7
    """
    Minimum R-value for pole slope regression (0.7).
    Ensures pole shows clear linear upward trend.
    """

    # Volume Analysis
    BULL_FLAG_VOLUME_CONFIRMATION_THRESHOLD = 1.2
    """
    Volume spike threshold for breakout confirmation (120%).
    Breakout volume should be 20% above average.
    """

    BULL_FLAG_VOLUME_SPIKE_CONFIRMATION = 1.5
    """
    Strong volume spike threshold (150%).
    Used for high-confidence breakout validation.
    """

    # Breakout Validation
    BULL_FLAG_MIN_FOLLOW_THROUGH_RATIO = 0.5
    """
    Minimum follow-through ratio for breakout validation (50%).
    Price should maintain at least 50% of breakout gain.
    """

    BULL_FLAG_REVERSAL_THRESHOLD = 0.99
    """
    Immediate reversal detection threshold (99%).
    Falls below 99% of resistance indicate failed breakout.
    """

    # Breakout Strength Weights
    BULL_FLAG_BREAKOUT_GAP_WEIGHT = 0.3
    BULL_FLAG_BREAKOUT_FOLLOW_THROUGH_WEIGHT = 0.3
    BULL_FLAG_BREAKOUT_POLE_CONTEXT_WEIGHT = 0.2
    BULL_FLAG_BREAKOUT_SPEED_WEIGHT = 0.2
    """
    Weights for breakout strength calculation.
    Gap and follow-through are primary indicators (30% each).
    """

    # Breakout Quality Scoring
    BULL_FLAG_BREAKOUT_QUALITY_STRONG = 0.8
    BULL_FLAG_BREAKOUT_QUALITY_MODERATE = 0.6
    BULL_FLAG_BREAKOUT_QUALITY_WEAK = 0.4
    BULL_FLAG_BREAKOUT_QUALITY_NEUTRAL = 0.5
    """
    Predefined quality scores for breakout validation.
    """

    # Price Targets
    BULL_FLAG_CONSERVATIVE_TARGET_MULTIPLIER = 0.5
    """Conservative target: Resistance + 50% of pole height."""

    BULL_FLAG_STANDARD_TARGET_MULTIPLIER = 1.0
    """Standard target: Resistance + 100% of pole height (full projection)."""

    BULL_FLAG_AGGRESSIVE_TARGET_MULTIPLIER = 1.5
    """Aggressive target: Resistance + 150% of pole height."""

    BULL_FLAG_FIBONACCI_127_MULTIPLIER = 1.272
    """Fibonacci 127.2% extension target."""

    BULL_FLAG_FIBONACCI_162_MULTIPLIER = 1.618
    """Fibonacci 161.8% (Golden Ratio) extension target."""

    # Stop Loss Levels
    BULL_FLAG_STOP_LOSS_FLAG_LOW_MULTIPLIER = 0.98
    """Stop loss: 2% below flag low."""

    BULL_FLAG_STOP_LOSS_RESISTANCE_MULTIPLIER = 0.99
    """Stop loss: 1% below resistance (for failed breakouts)."""

    # Success Probability
    BULL_FLAG_BASE_PROBABILITY_STRONG = 0.7
    """Base success probability for strong patterns (70%)."""

    BULL_FLAG_BASE_PROBABILITY_MODERATE = 0.5
    """Base success probability for moderate patterns (50%)."""

    # -------------------------------------------------------------------------
    # Bull Flag - Blue-Chip Stock Profile
    # -------------------------------------------------------------------------
    # Optimized for stable, low-volatility stocks (SPY, JNJ, PG)

    BULL_FLAG_MIN_POLE_GAIN_BLUE_CHIP = 0.12
    """Minimum pole gain for blue-chip (12%). Slightly lower for stable stocks."""

    BULL_FLAG_MAX_FLAG_RETRACEMENT_BLUE_CHIP = 0.20
    """Maximum flag retracement for blue-chip (20%). Much tighter than default."""

    BULL_FLAG_MIN_PATTERN_STRENGTH_BLUE_CHIP = 0.5
    """Minimum pattern strength for blue-chip (50%). Higher quality bar."""

    BULL_FLAG_IDEAL_DURATION_RATIO_MIN_BLUE_CHIP = 0.4
    """Ideal flag duration ratio min for blue-chip (0.4)."""

    BULL_FLAG_IDEAL_DURATION_RATIO_MAX_BLUE_CHIP = 0.8
    """Ideal flag duration ratio max for blue-chip (0.8)."""

    # -------------------------------------------------------------------------
    # Bull Flag - Volatile Growth Stock Profile
    # -------------------------------------------------------------------------
    # Optimized for high-volatility growth stocks (NNE, STNE, SOUN)

    BULL_FLAG_MIN_POLE_GAIN_GROWTH = 0.20
    """Minimum pole gain for growth (20%). Higher threshold for volatile stocks."""

    BULL_FLAG_MAX_FLAG_RETRACEMENT_GROWTH = 0.30
    """Maximum flag retracement for growth (30%). Allow deeper retracements."""

    BULL_FLAG_MIN_PATTERN_STRENGTH_GROWTH = 0.35
    """Minimum pattern strength for growth (35%). Lower bar for volatile patterns."""

    BULL_FLAG_IDEAL_DURATION_RATIO_MIN_GROWTH = 0.25
    """Ideal flag duration ratio min for growth (0.25). Shorter flags acceptable."""

    BULL_FLAG_IDEAL_DURATION_RATIO_MAX_GROWTH = 0.60
    """Ideal flag duration ratio max for growth (0.60)."""

    # =========================================================================
    # Confidence Scoring Constants
    # =========================================================================

    CONFIDENCE_VOLUME_WEIGHT = 0.25
    CONFIDENCE_PATTERN_CLARITY_WEIGHT = 0.35
    CONFIDENCE_MARKET_CONTEXT_WEIGHT = 0.20
    CONFIDENCE_TECHNICAL_STRENGTH_WEIGHT = 0.20
    """
    Weights for confidence score calculation.
    Pattern clarity is the primary factor (35%).
    Total must equal 1.0.
    Source: Tuned using expert-labeled pattern dataset
    """

    CONFIDENCE_MIN = 0.1
    """Minimum confidence score (10%)."""

    CONFIDENCE_MAX = 0.95
    """Maximum confidence score (95%). Never claim 100% certainty."""

    # =========================================================================
    # Moving Average Crossover Constants
    # =========================================================================

    MA_CROSSOVER_ANGLE_REFERENCE_DEGREES = 45.0
    """
    Reference angle for MA crossover strength calculation.
    45° is considered significant in technical analysis.
    Source: Murphy, J. (1999). Technical Analysis of Financial Markets.
    """

    MA_CROSSOVER_SEPARATION_WEIGHT = 0.6
    MA_CROSSOVER_ANGLE_WEIGHT = 0.4
    """
    Weights for combining separation and angle into pattern strength.
    60/40 split determined by historical analysis of 1000+ crossover patterns.
    Separation is a more reliable predictor than angle.
    """

    MA_CROSSOVER_MIN_STRENGTH = 0.1
    """
    Minimum pattern strength to report (0.0-1.0).
    Prevents reporting of noise/insignificant crossovers.
    """

    MA_CROSSOVER_FALLBACK_STRENGTH = 0.5
    """
    Fallback strength value (50%) when calculation fails.
    Used as neutral middle value for error cases.
    """

    MA_CROSSOVER_STRONG_PATTERN_STRENGTH = 0.8
    """Strong crossover pattern threshold (80%)."""

    MA_CROSSOVER_VERY_STRONG_PATTERN_STRENGTH = 0.9
    """Very strong crossover pattern threshold (90%)."""

    MA_CROSSOVER_VOLUME_CONFIRMATION_MULTIPLIER = 1.2
    """
    Volume confirmation multiplier (120%).
    Crossover volume should exceed average by 20% for confirmation.
    """

    MA_CROSSOVER_BULLISH_TREND_CONFIDENCE_BOOST = 1.2
    """
    Confidence boost for bullish crossover in uptrend (20% increase).
    Pattern more reliable when aligned with existing trend.
    """

    MA_CROSSOVER_BEARISH_TREND_CONFIDENCE_BOOST = 1.2
    """
    Confidence boost for bearish crossover in downtrend (20% increase).
    Pattern more reliable when aligned with existing trend.
    """

    MA_CROSSOVER_VOLUME_CONFIDENCE_BOOST = 1.1
    """
    Confidence boost when volume confirms (10% increase).
    Higher volume adds conviction to the pattern.
    """

    MA_CROSSOVER_BASE_CONFIDENCE = 0.5
    """
    Base confidence for crossover patterns (50%).
    Starting point before applying adjustments and boosts.
    """

    # =========================================================================
    # Cup and Handle Constants
    # =========================================================================
    # NOTE: Default values below are configured for blue-chip stocks.
    # For volatile growth stocks, use the GROWTH suffix constants.
    # See volatility-aware detection system architecture doc.

    # Cup Dimensions (Default/Blue-Chip Profile)
    CUP_MIN_WIDTH_DAYS = 30
    """Minimum cup width (30 days). Shorter formations are unreliable."""

    CUP_MAX_WIDTH_DAYS = 120
    """Maximum cup width (120 days). Longer formations lose relevance."""

    CUP_DEPTH_MIN_RATIO = 0.10
    """
    Minimum cup depth (10% from rim to bottom).
    Too shallow patterns lack significance.
    """

    CUP_DEPTH_MAX_RATIO = 0.50
    """
    Maximum cup depth (50% from rim to bottom).
    Too deep patterns suggest trend reversal, not continuation.
    Source: O'Neil, W. (1988). How to Make Money in Stocks.
    """

    # Handle Dimensions
    HANDLE_MIN_WIDTH_DAYS = 5
    """Minimum handle width (5 days). Shorter handles are too brief."""

    HANDLE_MAX_WIDTH_DAYS = 30
    """Maximum handle width (30 days). Longer handles lose pattern validity."""

    HANDLE_MAX_DEPTH_RATIO = 0.5
    """
    Maximum handle depth (50% of cup depth).
    According to William O'Neil, handles should be 10-15% deep on their own,
    but can be up to 50% of the cup's depth for valid patterns.
    """

    # Cup Validation
    CUP_MIN_SYMMETRY_SCORE = 0.6
    """
    Minimum symmetry score for cup validation (60%).
    Asymmetric cups are less reliable pattern indicators.
    """

    # -------------------------------------------------------------------------
    # Cup and Handle - Blue-Chip Stock Profile
    # -------------------------------------------------------------------------
    # Optimized for stable, low-volatility stocks (SPY, JNJ, PG)
    # Based on industry research and CANSLIM methodology

    CUP_RIM_TOLERANCE_BLUE_CHIP = 0.03
    """Rim tolerance for blue-chip stocks (3%). Tight tolerance for stable stocks."""

    CUP_DEPTH_MIN_RATIO_BLUE_CHIP = 0.10
    """Minimum cup depth for blue-chip (10%)."""

    CUP_DEPTH_MAX_RATIO_BLUE_CHIP = 0.30
    """Maximum cup depth for blue-chip (30%). Tightened from default 50%."""

    CUP_MIN_SYMMETRY_SCORE_BLUE_CHIP = 0.65
    """Minimum symmetry for blue-chip (65%). Higher standard for stable stocks."""

    HANDLE_MAX_DEPTH_RATIO_BLUE_CHIP = 0.15
    """Maximum handle depth for blue-chip (15%). Tightened from default 50%."""

    # -------------------------------------------------------------------------
    # Cup and Handle - Volatile Growth Stock Profile
    # -------------------------------------------------------------------------
    # Optimized for high-volatility growth stocks (NNE, STNE, SOUN, CEG)
    # Allows for larger price swings and less perfect symmetry

    CUP_RIM_TOLERANCE_GROWTH = 0.10
    """Rim tolerance for growth stocks (10%). Wider tolerance for volatile stocks."""

    CUP_DEPTH_MIN_RATIO_GROWTH = 0.08
    """Minimum cup depth for growth (8%). Slightly lower to catch shallower patterns."""

    CUP_DEPTH_MAX_RATIO_GROWTH = 0.50
    """Maximum cup depth for growth (50%). Allows deeper corrections."""

    CUP_MIN_SYMMETRY_SCORE_GROWTH = 0.35
    """Minimum symmetry for growth (35%). More flexible for volatile movements."""

    HANDLE_MAX_DEPTH_RATIO_GROWTH = 0.25
    """Maximum handle depth for growth (25%). More realistic than 50%."""

    CUP_V_SHAPED_MAX_SLOPE_RATIO = 0.0076
    """
    Maximum acceptable slope ratio to avoid V-shaped patterns (0.76% per day).
    Slopes steeper than this indicate sharp decline/recovery rather than gradual
    U-shaped cup formation. Based on technical analysis: cups should form gradually
    over 7-10 weeks. Patterns with slopes > 0.76%/day lack proper accumulation phase.
    """

    CUP_V_SHAPED_PENALTY = 0.35
    """
    Confidence penalty multiplier for V-shaped patterns (35%).
    V-shaped patterns lack the gradual accumulation phase of valid cups and should
    be heavily penalized. Steep slopes indicate panic selling/buying rather than
    measured consolidation, making the pattern much less reliable.
    """

    CUP_RIM_TOLERANCE = 0.03
    """
    Rim level tolerance (3%).
    Left and right rim should be within 3% to form valid pattern.
    """

    CUP_VOLUME_DECLINE_THRESHOLD = 0.8
    """
    Volume decline threshold during cup formation (80%).
    Volume should decrease to 80% or less of starting volume.
    """

    CUP_BOTTOM_RIM_RATIO = 0.95
    """
    Bottom must be at least 5% lower than rim average.
    Prevents false patterns where cup has insufficient depth.
    """

    # Cup Strength Weights
    CUP_SYMMETRY_WEIGHT = 0.4
    """Symmetry contributes 40% to cup strength calculation."""

    CUP_WIDTH_WEIGHT = 0.3
    """Width normalization contributes 30% to cup strength."""

    # Handle Validation and Scoring
    HANDLE_DEPTH_WEIGHT = 0.3
    """Handle depth contributes 30% to handle strength."""

    HANDLE_WIDTH_WEIGHT = 0.3
    """Handle width contributes 30% to handle strength."""

    HANDLE_SLOPE_WEIGHT = 0.2
    """Handle slope contributes 20% to handle strength."""

    HANDLE_VOLUME_WEIGHT = 0.2
    """Handle volume pattern contributes 20% to handle strength."""

    HANDLE_OPTIMAL_WIDTH_RATIO = 0.25
    """
    Optimal handle width is 25% of cup width.
    Used for handle width scoring normalization.
    """

    HANDLE_MAX_OPTIMAL_WIDTH_DAYS = 20
    """
    Maximum optimal handle width (20 days).
    Upper bound for handle width scoring.
    """

    HANDLE_WIDTH_TO_CUP_MAX_RATIO = 0.5
    """
    Handle width should not exceed 50% of cup width.
    Longer handles weaken the pattern.
    """

    # Cup and Handle Overlap Detection
    CUP_OVERLAP_THRESHOLD = 0.5
    """
    Minimum overlap ratio (50%) for cup boundary validation.
    Prevents counting the same cup multiple times.
    """

    # Cup Quality Scoring Weights
    CUP_QUALITY_SYMMETRY_WEIGHT = 0.4
    """Symmetry score weight in cup quality calculation (40%)."""

    CUP_QUALITY_DEPTH_WEIGHT = 0.3
    """Depth score weight in cup quality calculation (30%)."""

    CUP_QUALITY_WIDTH_WEIGHT = 0.3
    """Width score weight in cup quality calculation (30%)."""

    CUP_QUALITY_DEPTH_NORMALIZER = 0.3
    """
    Depth normalization divisor for quality scoring.
    Optimal cup depth around 30% for quality calculation.
    """

    CUP_QUALITY_WIDTH_NORMALIZER = 60
    """
    Width normalization divisor for quality scoring (60 days).
    Represents optimal cup width for pattern quality.
    """

    # Handle Search and Gap Tolerance
    HANDLE_GAP_TOLERANCE_DAYS = 5
    """
    Maximum gap allowed between cup end and handle start (5 days).
    Allows for small consolidation gaps in pattern formation.
    """

    HANDLE_MIN_WIDTH_FOR_ANALYSIS = 3
    """
    Minimum handle width for technical analysis (3 days).
    Shorter handles lack sufficient data points.
    """

    # Handle Validation Thresholds
    HANDLE_ABSOLUTE_MAX_DEPTH = 0.15
    """
    Absolute maximum handle depth (15%).
    Deeper handles invalidate the pattern regardless of cup depth.
    """

    HANDLE_RIM_TOLERANCE_ABOVE = 1.05
    """
    Maximum handle high as ratio of rim level (105%).
    Handle peaks above this indicate failed consolidation.
    """

    # Handle Quality Scoring - Base Weights
    HANDLE_DEPTH_SCORE_WEIGHT = 0.3
    """Handle depth quality contributes 30% to base score."""

    HANDLE_WIDTH_SCORE_WEIGHT = 0.3
    """Handle width quality contributes 30% to base score."""

    HANDLE_SLOPE_SCORE_WEIGHT = 0.2
    """Handle slope quality contributes 20% to base score."""

    HANDLE_RIM_PROXIMITY_WEIGHT = 0.2
    """Handle rim proximity contributes 20% to base score."""

    # Handle Quality Scoring - Thresholds
    HANDLE_OPTIMAL_DEPTH_THRESHOLD = 0.1
    """
    Optimal handle depth threshold (10%).
    Handle depths below this score highest in quality.
    """

    HANDLE_SLOPE_PENALTY_MULTIPLIER = 1000
    """
    Slope penalty multiplier for upward-sloping handles.
    Large multiplier heavily penalizes positive slopes.
    """

    # Handle Advanced Scoring Weights
    HANDLE_CONSOLIDATION_QUALITY_WEIGHT = 0.15
    """Consolidation quality contributes 15% to advanced score."""

    HANDLE_VOLATILITY_QUALITY_WEIGHT = 0.10
    """Volatility assessment contributes 10% to advanced score."""

    HANDLE_BREAKOUT_READINESS_WEIGHT = 0.15
    """Breakout readiness contributes 15% to advanced score."""

    HANDLE_PATTERN_INTEGRITY_WEIGHT = 0.10
    """Pattern integrity contributes 10% to advanced score."""

    HANDLE_BASE_SCORE_WEIGHT = 0.5
    """Base score weight in combined advanced scoring (50%)."""

    # Handle Consolidation Range Thresholds
    HANDLE_CONSOLIDATION_TIGHT_THRESHOLD = 0.02
    """Too tight consolidation threshold (2% range)."""

    HANDLE_CONSOLIDATION_IDEAL_THRESHOLD = 0.08
    """Ideal consolidation range threshold (8%)."""

    HANDLE_CONSOLIDATION_ACCEPTABLE_THRESHOLD = 0.15
    """Acceptable consolidation range threshold (15%)."""

    HANDLE_CONSOLIDATION_TIGHT_SCORE = 0.5
    """Score for too-tight consolidation."""

    HANDLE_CONSOLIDATION_IDEAL_SCORE = 1.0
    """Score for ideal consolidation."""

    HANDLE_CONSOLIDATION_ACCEPTABLE_SCORE = 0.7
    """Score for acceptable consolidation."""

    HANDLE_CONSOLIDATION_WIDE_SCORE = 0.3
    """Score for too-wide consolidation."""

    # Handle Volatility Thresholds
    HANDLE_VOLATILITY_VERY_LOW_THRESHOLD = 0.02
    """Very low volatility threshold (2% std dev)."""

    HANDLE_VOLATILITY_GOOD_THRESHOLD = 0.05
    """Good volatility threshold (5% std dev)."""

    HANDLE_VOLATILITY_MODERATE_THRESHOLD = 0.10
    """Moderate volatility threshold (10% std dev)."""

    HANDLE_VOLATILITY_VERY_LOW_SCORE = 1.0
    """Score for very low volatility."""

    HANDLE_VOLATILITY_GOOD_SCORE = 0.8
    """Score for good volatility."""

    HANDLE_VOLATILITY_MODERATE_SCORE = 0.5
    """Score for moderate volatility."""

    HANDLE_VOLATILITY_HIGH_SCORE = 0.2
    """Score for high volatility."""

    HANDLE_MIN_VOLATILITY_SCORE = 0.3
    """
    Minimum acceptable volatility score for validation (30%).
    Handles below this are too volatile to be valid.
    """

    # Handle Breakout Readiness Thresholds
    HANDLE_BREAKOUT_POSITION_EXCELLENT_THRESHOLD = 0.02
    """Excellent position: within 2% of rim level."""

    HANDLE_BREAKOUT_POSITION_GOOD_THRESHOLD = 0.05
    """Good position: within 5% of rim level."""

    HANDLE_BREAKOUT_POSITION_ACCEPTABLE_THRESHOLD = 0.10
    """Acceptable position: within 10% of rim level."""

    HANDLE_BREAKOUT_POSITION_EXCELLENT_SCORE = 1.0
    """Score for excellent breakout position."""

    HANDLE_BREAKOUT_POSITION_GOOD_SCORE = 0.8
    """Score for good breakout position."""

    HANDLE_BREAKOUT_POSITION_ACCEPTABLE_SCORE = 0.5
    """Score for acceptable breakout position."""

    HANDLE_BREAKOUT_POSITION_POOR_SCORE = 0.2
    """Score for poor breakout position."""

    HANDLE_BREAKOUT_TREND_NEUTRAL_SLOPE = -0.5
    """Neutral trend slope threshold for breakout analysis."""

    HANDLE_BREAKOUT_TREND_UPWARD_SCORE = 1.0
    """Score for upward trending handle toward rim."""

    HANDLE_BREAKOUT_TREND_FLAT_SCORE = 0.7
    """Score for flat or slightly downward handle."""

    HANDLE_BREAKOUT_TREND_DOWN_SCORE = 0.3
    """Score for downward trending handle."""

    HANDLE_BREAKOUT_TREND_NEUTRAL_SCORE = 0.5
    """Score when trend cannot be assessed."""

    # Handle Pattern Integrity Thresholds
    HANDLE_PATTERN_MIN_HIGHS = 2
    """Minimum number of local highs for pattern analysis."""

    HANDLE_SPIKE_LOW_THRESHOLD = 1.1
    """Low spike threshold: less than 10% price range."""

    HANDLE_SPIKE_MODERATE_THRESHOLD = 1.2
    """Moderate spike threshold: less than 20% price range."""

    HANDLE_SPIKE_LOW_SCORE = 1.0
    """Score for low spike."""

    HANDLE_SPIKE_MODERATE_SCORE = 0.7
    """Score for moderate spike."""

    HANDLE_SPIKE_HIGH_SCORE = 0.3
    """Score for high spike."""

    HANDLE_PATTERN_DECLINING_SCORE = 1.0
    """Score for proper declining highs pattern."""

    HANDLE_PATTERN_NON_DECLINING_SCORE = 0.6
    """Score for non-declining highs pattern."""

    HANDLE_PATTERN_INSUFFICIENT_SCORE = 0.5
    """Score when insufficient highs for assessment."""

    # Handle Technical Validation
    HANDLE_MAX_PRICE_RANGE_RATIO = 0.20
    """
    Maximum price range ratio for handle validation (20%).
    Larger ranges indicate uncontrolled price action.
    """

    HANDLE_MAX_SLOPE_RATIO = 0.01
    """
    Maximum slope ratio for upward bias detection (1%).
    Steeper upward slopes invalidate the pattern.
    """

    HANDLE_MAX_WIDTH_TO_CUP_RATIO = 0.4
    """
    Maximum handle width as ratio of cup width (40%).
    Longer handles weaken pattern proportionality.
    """

    # Pattern Validation Thresholds
    CUP_HANDLE_TOTAL_PATTERN_MULTIPLIER = 1.5
    """
    Maximum total pattern width multiplier (150% of max cup width).
    Prevents excessively long patterns from being reported.
    """

    # Volume Analysis - Comprehensive Thresholds
    VOLUME_CRITERIA_PASS_THRESHOLD = 0.75
    """
    Minimum ratio of volume criteria that must pass (75%).
    Ensures strong volume confirmation across multiple metrics.
    """

    VOLUME_CUP_SEGMENT_DIVISOR = 3
    """
    Number of segments for cup volume analysis (3 segments).
    Divides cup into early, middle, and late phases.
    """

    VOLUME_CUP_MIN_SEGMENT_SIZE = 1
    """Minimum segment size for valid volume analysis."""

    VOLUME_MIDDLE_INCREASE_TOLERANCE = 1.1
    """
    Allowed volume increase in middle segment (110%).
    Permits slight volume uptick during cup formation.
    """

    VOLUME_HANDLE_VS_EARLY_CUP_MAX = 0.8
    """
    Maximum handle volume vs early cup ratio (80%).
    Handle should be significantly lower than early cup.
    """

    VOLUME_HANDLE_VS_LATE_CUP_MAX = 1.5
    """
    Maximum handle volume vs late cup ratio (150%).
    Handle can be moderately higher than late cup.
    """

    VOLUME_HANDLE_CONSISTENCY_THRESHOLD = 0.5
    """
    Handle volume volatility threshold for consistency (50%).
    Lower volatility indicates stable low volume.
    """

    VOLUME_MA_MIN_LENGTH = 10
    """
    Minimum data points for volume moving average (10).
    Ensures smooth trend calculation.
    """

    VOLUME_MA_WINDOW_DIVISOR = 4
    """
    Divisor for calculating MA window (length / 4).
    Determines smoothing period for volume trends.
    """

    VOLUME_MA_MIN_VALID_POINTS = 5
    """
    Minimum valid MA points for trend analysis (5).
    Required for reliable trend slope calculation.
    """

    VOLUME_TREND_CONSISTENT_THRESHOLD = 0.1
    """
    Overall volume trend consistency threshold (10%).
    Slope below this indicates declining or stable volume.
    """

    VOLUME_CUP_TREND_THRESHOLD = 0.2
    """Cup volume trend threshold (20%)."""

    VOLUME_HANDLE_TREND_THRESHOLD = 0.5
    """Handle volume trend threshold (50%)."""

    VOLUME_SPIKE_DETECTION_MULTIPLIER = 3
    """
    Spike detection multiplier (3x median).
    Volumes above this are considered abnormal spikes.
    """

    VOLUME_TAPERING_MULTIPLIER = 1.5
    """
    Volume tapering validation multiplier (150%).
    Ensures reasonable volume distribution in cup.
    """

    # Volume Confidence Scoring
    VOLUME_CONFIDENCE_CUP_DECLINE_WEIGHT = 0.25
    """Cup volume decline contributes 25% to volume confidence."""

    VOLUME_CONFIDENCE_HANDLE_WEIGHT = 0.25
    """Handle volume characteristics contribute 25% to volume confidence."""

    VOLUME_CONFIDENCE_TREND_WEIGHT = 0.25
    """Volume trend consistency contributes 25% to volume confidence."""

    VOLUME_CONFIDENCE_DISTRIBUTION_WEIGHT = 0.25
    """Volume distribution validity contributes 25% to volume confidence."""

    VOLUME_DECLINE_EXCELLENT_RATIO = 0.6
    """
    Excellent volume decline ratio (60% or less).
    Strong volume contraction during cup formation.
    """

    VOLUME_DECLINE_EXCELLENT_SCORE = 0.25
    """Score for excellent volume decline."""

    VOLUME_DECLINE_GOOD_RATIO = 0.8
    """Good volume decline ratio (80% or less)."""

    VOLUME_DECLINE_GOOD_SCORE = 0.20
    """Score for good volume decline."""

    VOLUME_DECLINE_MODEST_RATIO = 1.0
    """Modest volume decline ratio (100% or less)."""

    VOLUME_DECLINE_MODEST_SCORE = 0.10
    """Score for modest volume decline."""

    # Pattern Strength Calculation
    CUP_STRENGTH_WEIGHT = 0.7
    """Cup quality contributes 70% to overall pattern strength."""

    HANDLE_STRENGTH_WEIGHT = 0.3
    """Handle quality contributes 30% to overall pattern strength."""

    CUP_STRENGTH_OPTIMAL_DEPTH = 0.25
    """Optimal cup depth for strength calculation (25%)."""

    CUP_STRENGTH_OPTIMAL_WIDTH = 60
    """Optimal cup width for strength calculation (60 days)."""

    HANDLE_STRENGTH_OPTIMAL_WIDTH = 15
    """Optimal handle width for strength calculation (15 days)."""

    # Confidence Calculation - Base and Weights
    CUP_HANDLE_BASE_CONFIDENCE = 0.4
    """Base confidence before adjustments (40%)."""

    CUP_HANDLE_CUP_QUALITY_WEIGHT = 0.40
    """Cup quality contributes 40% to total confidence."""

    CUP_HANDLE_HANDLE_QUALITY_WEIGHT = 0.20
    """Handle quality contributes 20% to total confidence."""

    CUP_HANDLE_VOLUME_WEIGHT = 0.25
    """Volume analysis contributes 25% to total confidence."""

    CUP_HANDLE_TECHNICAL_WEIGHT = 0.15
    """Technical integrity contributes 15% to total confidence."""

    # Confidence - Cup Quality Sub-weights
    CUP_CONFIDENCE_SYMMETRY_WEIGHT = 0.15
    """Symmetry contributes 15% to cup quality confidence."""

    CUP_CONFIDENCE_DEPTH_WEIGHT = 0.10
    """Optimal depth contributes 10% to cup quality confidence."""

    CUP_CONFIDENCE_WIDTH_WEIGHT = 0.15
    """Optimal width contributes 15% to cup quality confidence."""

    CUP_CONFIDENCE_DEPTH_OPTIMAL_MIN = 0.15
    """Minimum for optimal cup depth range (15%)."""

    CUP_CONFIDENCE_DEPTH_OPTIMAL_MAX = 0.35
    """Maximum for optimal cup depth range (35%)."""

    CUP_CONFIDENCE_DEPTH_PEAK = 0.25
    """Peak optimal cup depth (25%)."""

    CUP_CONFIDENCE_DEPTH_PEAK_TOLERANCE = 0.10
    """Tolerance around peak depth for scoring (±10%)."""

    CUP_CONFIDENCE_DEPTH_ACCEPTABLE_MIN = 0.10
    """Minimum acceptable cup depth (10%)."""

    CUP_CONFIDENCE_DEPTH_ACCEPTABLE_MAX = 0.50
    """Maximum acceptable cup depth (50%)."""

    CUP_CONFIDENCE_DEPTH_PARTIAL_SCORE = 0.05
    """Partial credit for acceptable depth range."""

    CUP_CONFIDENCE_WIDTH_OPTIMAL_MIN = 45
    """Minimum optimal cup width (45 days)."""

    CUP_CONFIDENCE_WIDTH_OPTIMAL_MAX = 90
    """Maximum optimal cup width (90 days)."""

    CUP_CONFIDENCE_WIDTH_PEAK = 67.5
    """Peak optimal cup width (67.5 days)."""

    CUP_CONFIDENCE_WIDTH_PEAK_TOLERANCE = 22.5
    """Tolerance around peak width (±22.5 days)."""

    CUP_CONFIDENCE_WIDTH_ACCEPTABLE_MIN = 30
    """Minimum acceptable cup width (30 days)."""

    CUP_CONFIDENCE_WIDTH_ACCEPTABLE_MAX = 120
    """Maximum acceptable cup width (120 days)."""

    CUP_CONFIDENCE_WIDTH_PARTIAL_SCORE = 0.08
    """Partial credit for acceptable width range."""

    # Confidence - Handle Quality Sub-weights
    HANDLE_CONFIDENCE_DEPTH_OPTIMAL_MAX = 0.08
    """Optimal handle depth (8% or less)."""

    HANDLE_CONFIDENCE_DEPTH_OPTIMAL_SCORE = 0.10
    """Score for optimal handle depth."""

    HANDLE_CONFIDENCE_DEPTH_GOOD_MAX = 0.12
    """Good handle depth (12% or less)."""

    HANDLE_CONFIDENCE_DEPTH_GOOD_SCORE = 0.07
    """Score for good handle depth."""

    HANDLE_CONFIDENCE_DEPTH_ACCEPTABLE_MAX = 0.15
    """Acceptable handle depth (15% or less)."""

    HANDLE_CONFIDENCE_DEPTH_ACCEPTABLE_SCORE = 0.04
    """Score for acceptable handle depth."""

    HANDLE_CONFIDENCE_WIDTH_OPTIMAL_MIN = 7
    """Minimum optimal handle width (7 days)."""

    HANDLE_CONFIDENCE_WIDTH_OPTIMAL_MAX = 15
    """Maximum optimal handle width (15 days)."""

    HANDLE_CONFIDENCE_WIDTH_OPTIMAL_SCORE = 0.10
    """Score for optimal handle width."""

    HANDLE_CONFIDENCE_WIDTH_ACCEPTABLE_MIN = 5
    """Minimum acceptable handle width (5 days)."""

    HANDLE_CONFIDENCE_WIDTH_ACCEPTABLE_MAX = 20
    """Maximum acceptable handle width (20 days)."""

    HANDLE_CONFIDENCE_WIDTH_ACCEPTABLE_SCORE = 0.06
    """Score for acceptable handle width."""

    # Technical Integrity Scoring Weights
    TECHNICAL_RIM_CONSISTENCY_WEIGHT = 0.30
    """Rim level consistency contributes 30% to technical score."""

    TECHNICAL_HANDLE_POSITION_WEIGHT = 0.25
    """Handle position contributes 25% to technical score."""

    TECHNICAL_PROPORTIONALITY_WEIGHT = 0.25
    """Pattern proportionality contributes 25% to technical score."""

    TECHNICAL_BOTTOM_POSITION_WEIGHT = 0.20
    """Cup bottom position contributes 20% to technical score."""

    # Technical Integrity - Rim Consistency
    TECHNICAL_RIM_EXCELLENT_TOLERANCE = 0.02
    """Excellent rim consistency (within 2%)."""

    TECHNICAL_RIM_EXCELLENT_SCORE = 0.30
    """Score for excellent rim consistency."""

    TECHNICAL_RIM_GOOD_TOLERANCE = 0.05
    """Good rim consistency (within 5%)."""

    TECHNICAL_RIM_GOOD_SCORE = 0.20
    """Score for good rim consistency."""

    TECHNICAL_RIM_ACCEPTABLE_TOLERANCE = 0.10
    """Acceptable rim consistency (within 10%)."""

    TECHNICAL_RIM_ACCEPTABLE_SCORE = 0.10
    """Score for acceptable rim consistency."""

    # Technical Integrity - Handle Position
    TECHNICAL_HANDLE_POSITION_EXCELLENT_MIN = 0.95
    """Excellent handle position: 95-102% of rim."""

    TECHNICAL_HANDLE_POSITION_EXCELLENT_MAX = 1.02
    """Excellent handle position maximum ratio."""

    TECHNICAL_HANDLE_POSITION_EXCELLENT_SCORE = 0.25
    """Score for excellent handle position."""

    TECHNICAL_HANDLE_POSITION_GOOD_MIN = 0.90
    """Good handle position: 90-105% of rim."""

    TECHNICAL_HANDLE_POSITION_GOOD_MAX = 1.05
    """Good handle position maximum ratio."""

    TECHNICAL_HANDLE_POSITION_GOOD_SCORE = 0.18
    """Score for good handle position."""

    TECHNICAL_HANDLE_POSITION_ACCEPTABLE_MIN = 0.85
    """Acceptable handle position: 85-110% of rim."""

    TECHNICAL_HANDLE_POSITION_ACCEPTABLE_MAX = 1.10
    """Acceptable handle position maximum ratio."""

    TECHNICAL_HANDLE_POSITION_ACCEPTABLE_SCORE = 0.10
    """Score for acceptable handle position."""

    # Technical Integrity - Proportionality
    TECHNICAL_PROPORTION_OPTIMAL_MIN = 0.70
    """Optimal proportion: cup is 70-85% of total."""

    TECHNICAL_PROPORTION_OPTIMAL_MAX = 0.85
    """Optimal proportion maximum."""

    TECHNICAL_PROPORTION_OPTIMAL_SCORE = 0.25
    """Score for optimal proportions."""

    TECHNICAL_PROPORTION_GOOD_MIN = 0.60
    """Good proportion: cup is 60-90% of total."""

    TECHNICAL_PROPORTION_GOOD_MAX = 0.90
    """Good proportion maximum."""

    TECHNICAL_PROPORTION_GOOD_SCORE = 0.18
    """Score for good proportions."""

    TECHNICAL_PROPORTION_ACCEPTABLE_MIN = 0.50
    """Acceptable proportion: cup is 50-95% of total."""

    TECHNICAL_PROPORTION_ACCEPTABLE_MAX = 0.95
    """Acceptable proportion maximum."""

    TECHNICAL_PROPORTION_ACCEPTABLE_SCORE = 0.10
    """Score for acceptable proportions."""

    # Technical Integrity - Bottom Position
    TECHNICAL_BOTTOM_OPTIMAL_MIN = 0.35
    """Optimal bottom position: 35-65% into cup."""

    TECHNICAL_BOTTOM_OPTIMAL_MAX = 0.65
    """Optimal bottom position maximum."""

    TECHNICAL_BOTTOM_OPTIMAL_SCORE = 0.20
    """Score for optimal bottom position."""

    TECHNICAL_BOTTOM_GOOD_MIN = 0.25
    """Good bottom position: 25-75% into cup."""

    TECHNICAL_BOTTOM_GOOD_MAX = 0.75
    """Good bottom position maximum."""

    TECHNICAL_BOTTOM_GOOD_SCORE = 0.12
    """Score for good bottom position."""

    TECHNICAL_BOTTOM_ACCEPTABLE_MIN = 0.15
    """Acceptable bottom position: 15-85% into cup."""

    TECHNICAL_BOTTOM_ACCEPTABLE_MAX = 0.85
    """Acceptable bottom position maximum."""

    TECHNICAL_BOTTOM_ACCEPTABLE_SCORE = 0.06
    """Score for acceptable bottom position."""

    # Volume Trend Classification
    VOLUME_TREND_U_SHAPED_DECLINE_MAX = 0.6
    """Maximum decline ratio for U-shaped classification (60%)."""

    VOLUME_TREND_U_SHAPED_SLOPE_MAX = -0.1
    """Maximum slope for U-shaped classification."""

    VOLUME_TREND_U_SHAPED_OVERALL_SLOPE_MAX = -0.05
    """Maximum overall slope for U-shaped classification."""

    VOLUME_TREND_DECLINING_RATIO_MAX = 0.8
    """Maximum decline ratio for declining classification (80%)."""

    VOLUME_TREND_STABLE_RATIO_MAX = 1.1
    """Maximum decline ratio for stable classification (110%)."""

    VOLUME_TREND_STABLE_SLOPE_MAX = 0.1
    """Maximum absolute slope for stable classification."""

    VOLUME_TREND_INCREASING_RATIO_MIN = 1.2
    """Minimum ratio for increasing classification (120%)."""

    VOLUME_TREND_INCREASING_SLOPE_MIN = 0.1
    """Minimum slope for increasing classification."""

    # Price Target and Risk Management
    STOP_LOSS_BELOW_HANDLE_MULTIPLIER = 0.95
    """
    Stop loss multiplier below handle low (95%).
    5% below handle low for conservative risk management.
    """

    PERCENTAGE_CONVERSION_MULTIPLIER = 100
    """
    Multiplier for converting ratios to percentages (100).
    Used in result formatting for depth and width values.
    """

    # Mathematical and Numerical Constants
    EPSILON_DIVISION_BY_ZERO = 1e-8
    """
    Epsilon value for preventing division by zero (1e-8).
    Small constant added to denominators in normalization.
    """

    ARRAY_CORRELATION_FIRST_INDEX = 0
    """First index for correlation matrix extraction."""

    ARRAY_CORRELATION_SECOND_INDEX = 1
    """Second index for correlation matrix extraction."""

    CUP_SYMMETRY_MIN_LENGTH = 3
    """
    Minimum target length for symmetry comparison (3 points).
    Shorter lengths insufficient for correlation analysis.
    """

    LINEAR_REGRESSION_POWER = 2
    """Power for squared terms in linear regression (x²)."""

    # Default Configuration
    CUP_HANDLE_MIN_DATA_POINTS = 60
    """
    Minimum data points for cup and handle detection (60).
    Reduced to work with typical 120-day data windows.
    """

    # =========================================================================
    # Support and Resistance Constants
    # =========================================================================
    # NOTE: Default values below are moderate. For stock-specific profiles,
    # use the BLUE_CHIP or GROWTH suffix constants.

    SUPPORT_RESISTANCE_TOUCH_PROXIMITY = 0.02
    """
    Price proximity threshold for level touches (2%).
    Prices within 2% of level are considered touches.
    """

    SUPPORT_RESISTANCE_MIN_TOUCHES = 2
    """Minimum touches required to confirm a support/resistance level."""

    SUPPORT_RESISTANCE_PIVOT_WINDOW = 5
    """
    Window size for pivot point detection (5 days).
    Looks 5 days before and after to identify local highs/lows.
    """

    SUPPORT_RESISTANCE_MIN_STRENGTH = 0.3
    """
    Minimum level strength to report (30%).
    Filters out weak or unreliable levels.
    """

    # -------------------------------------------------------------------------
    # Support/Resistance - Blue-Chip Stock Profile
    # -------------------------------------------------------------------------
    # Optimized for stable, low-volatility stocks (SPY, JNJ, PG)

    SUPPORT_RESISTANCE_TOUCH_PROXIMITY_BLUE_CHIP = 0.015
    """Touch proximity for blue-chip (1.5%). Tighter zones for stable stocks."""

    SUPPORT_RESISTANCE_MIN_TOUCHES_BLUE_CHIP = 2
    """Minimum touches for blue-chip (2). Same as default."""

    SUPPORT_RESISTANCE_MIN_STRENGTH_BLUE_CHIP = 0.4
    """Minimum strength for blue-chip (40%). Higher quality bar."""

    # -------------------------------------------------------------------------
    # Support/Resistance - Volatile Growth Stock Profile
    # -------------------------------------------------------------------------
    # Optimized for high-volatility growth stocks (NNE, STNE, SOUN)

    SUPPORT_RESISTANCE_TOUCH_PROXIMITY_GROWTH = 0.04
    """Touch proximity for growth (4%). Wider zones for volatile stocks."""

    SUPPORT_RESISTANCE_MIN_TOUCHES_GROWTH = 3
    """Minimum touches for growth (3). More confirmation needed."""

    SUPPORT_RESISTANCE_MIN_STRENGTH_GROWTH = 0.25
    """Minimum strength for growth (25%). Lower bar for volatile patterns."""

    SUPPORT_RESISTANCE_MAX_LEVELS = 10
    """
    Maximum number of levels to return per analysis.
    Prevents overwhelming output with too many levels.
    """

    SUPPORT_RESISTANCE_MAX_DISTANCE = 0.1
    """
    Maximum distance from current price for relevant levels (10%).
    Levels beyond this distance are less actionable.
    """

    # Level Strength Calculation Weights
    SUPPORT_RESISTANCE_TOUCH_WEIGHT = 0.30
    """Number of touches contributes 30% to level strength."""

    SUPPORT_RESISTANCE_TIME_WEIGHT = 0.20
    """Time span of level contributes 20% to level strength."""

    SUPPORT_RESISTANCE_PIVOT_WEIGHT = 0.25
    """Pivot significance contributes 25% to level strength."""

    SUPPORT_RESISTANCE_RESPECT_WEIGHT = 0.15
    """Level respect (price bounces) contributes 15% to level strength."""

    SUPPORT_RESISTANCE_VOLATILITY_WEIGHT = 0.10
    """Volatility significance contributes 10% to level strength."""

    # Neutral Scores (when data insufficient)
    SUPPORT_RESISTANCE_NEUTRAL_SCORE = 0.5
    """
    Neutral score (50%) used when calculation cannot be performed.
    Applied for volatility, respect, and time strength when data is missing.
    """

    # Volatility-Based Filtering
    SUPPORT_RESISTANCE_VOLATILITY_RATIO = 0.5
    """
    Levels must be stronger than 50% of price volatility.
    Prevents reporting levels that are within normal price noise.
    """

    # =========================================================================
    # General Pattern Detection Constants
    # =========================================================================

    MIN_DATA_POINTS_FOR_PATTERN = 20
    """Minimum number of data points required for reliable pattern detection."""

    MAX_PATTERN_AGE_DAYS = 90
    """
    Maximum age of pattern to consider valid (90 days).
    Older patterns are less relevant for trading decisions.
    """
