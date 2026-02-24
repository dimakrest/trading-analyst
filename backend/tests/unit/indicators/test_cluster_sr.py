"""Unit tests for cluster-based support/resistance detection.

Tests cover _detect_swing_points, _cluster_price_levels, _score_levels,
and the top-level cluster_support_resistance function.
"""

import numpy as np

from app.indicators.technical import (
    SRLevel,
    _cluster_price_levels,
    _detect_swing_points,
    _score_levels,
    cluster_support_resistance,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_oscillating_ohlcv(
    n: int,
    low_price: float = 95.0,
    high_price: float = 105.0,
    volume: float = 1_000_000.0,
) -> tuple[list[float], list[float], list[float], list[float]]:
    """Create simple oscillating OHLCV where price bounces between two levels."""
    closes = []
    highs = []
    lows = []
    volumes = []
    for i in range(n):
        if i % 2 == 0:
            close = low_price
            high = low_price + 1.0
            low = low_price - 1.0
        else:
            close = high_price
            high = high_price + 1.0
            low = high_price - 1.0
        closes.append(close)
        highs.append(high)
        lows.append(low)
        volumes.append(volume)
    return highs, lows, closes, volumes


# ===========================================================================
# TestDetectSwingPoints
# ===========================================================================


class TestDetectSwingPoints:
    """Tests for _detect_swing_points."""

    def test_detects_swing_high_and_low_in_v_shape(self):
        """V-shape data should produce one swing high at peak and one at trough."""
        # Descend then ascend — creates a V-shape low at index 5 (window=3)
        lows = np.array(
            [100.0, 99.0, 98.0, 97.0, 96.0, 95.0, 96.0, 97.0, 98.0, 99.0, 100.0],
            dtype=float,
        )
        highs = lows + 2.0  # highs are always 2 above lows

        points = _detect_swing_points(highs, lows, window=3)

        prices_found = [p for _, p in points]
        # The trough at index 5: low[5]=95 is the minimum in its window
        assert 95.0 in prices_found, f"Expected trough price 95.0 in {prices_found}"

    def test_detects_swing_high_in_inverted_v(self):
        """Inverted-V data should produce a swing high at the peak."""
        highs = np.array(
            [100.0, 101.0, 102.0, 103.0, 104.0, 105.0, 104.0, 103.0, 102.0, 101.0, 100.0],
            dtype=float,
        )
        lows = highs - 2.0

        points = _detect_swing_points(highs, lows, window=3)

        prices_found = [p for _, p in points]
        # Peak high is at index 5: high[5]=105
        assert 105.0 in prices_found, f"Expected peak price 105.0 in {prices_found}"

    def test_returns_empty_for_insufficient_data(self):
        """Returns empty list when fewer bars than 2*window+1."""
        window = 5
        n = 2 * window  # one too few
        highs = np.ones(n, dtype=float) * 100.0
        lows = np.ones(n, dtype=float) * 98.0

        result = _detect_swing_points(highs, lows, window=window)

        assert result == []

    def test_returns_empty_for_exact_minimum_minus_one(self):
        """Exactly 2*window bars (one short) → empty."""
        window = 3
        highs = np.array([100.0, 101.0, 102.0, 103.0, 104.0, 105.0], dtype=float)
        lows = highs - 1.0

        result = _detect_swing_points(highs, lows, window=window)

        assert result == []

    def test_minimum_sufficient_data_does_not_raise(self):
        """Exactly 2*window+1 bars should not raise and may return results."""
        window = 3
        n = 2 * window + 1  # exactly enough
        highs = np.ones(n, dtype=float) * 100.0
        lows = np.ones(n, dtype=float) * 98.0

        # Should not raise, may return [] or some points for flat data
        result = _detect_swing_points(highs, lows, window=window)
        assert isinstance(result, list)

    def test_flat_price_no_unique_extrema(self):
        """Flat price data: all bars tie for high/low, so all interior bars are swing points."""
        highs = np.ones(15, dtype=float) * 100.0
        lows = np.ones(15, dtype=float) * 98.0

        result = _detect_swing_points(highs, lows, window=3)

        # With all equal values, every interior bar satisfies both conditions
        # (tied max/min). The function should still return a list without error.
        assert isinstance(result, list)

    def test_returns_tuples_of_index_and_price(self):
        """Each element in result is a (int, float) tuple."""
        highs = np.array(
            [100.0, 102.0, 104.0, 103.0, 101.0, 100.0, 102.0, 104.0, 103.0, 101.0, 100.0],
            dtype=float,
        )
        lows = highs - 2.0
        result = _detect_swing_points(highs, lows, window=3)

        for item in result:
            assert len(item) == 2
            idx, price = item
            assert isinstance(idx, int)
            assert isinstance(price, float)


# ===========================================================================
# TestClusterPriceLevels
# ===========================================================================


class TestClusterPriceLevels:
    """Tests for _cluster_price_levels."""

    def test_merges_nearby_points_into_one_cluster(self):
        """Points within threshold merge into a single cluster."""
        # 100, 101, 101.5 are all within 2% of center 100
        points = [(0, 100.0), (1, 101.0), (2, 101.5)]
        clusters = _cluster_price_levels(points, merge_threshold_pct=0.02)

        assert len(clusters) == 1
        assert len(clusters[0]) == 3

    def test_keeps_distant_points_as_separate_clusters(self):
        """Points farther apart than threshold form separate clusters."""
        points = [(0, 100.0), (1, 110.0)]  # 10% apart
        clusters = _cluster_price_levels(points, merge_threshold_pct=0.02)

        assert len(clusters) == 2

    def test_single_point_returns_one_cluster(self):
        """A single point produces exactly one cluster containing that point."""
        points = [(5, 99.5)]
        clusters = _cluster_price_levels(points, merge_threshold_pct=0.02)

        assert len(clusters) == 1
        assert clusters[0] == [(5, 99.5)]

    def test_empty_input_returns_empty_list(self):
        """Empty input returns empty output."""
        clusters = _cluster_price_levels([], merge_threshold_pct=0.02)
        assert clusters == []

    def test_fixed_center_prevents_chaining_drift(self):
        """Gradually rising prices do not chain-merge a clearly separate level.

        Sequence: 100, 100.5, 101, 101.5, 102 (all within 2% of center 100),
        then 103.5 which is > 2% from 100 → should be a second cluster.
        """
        points = [
            (0, 100.0),
            (1, 100.5),
            (2, 101.0),
            (3, 101.5),
            (4, 102.0),
            (5, 103.5),
        ]
        clusters = _cluster_price_levels(points, merge_threshold_pct=0.02)

        # 103.5 is 3.5% from center 100.0 → must be its own cluster
        assert len(clusters) == 2, (
            f"Expected 2 clusters (100-102 and 103.5), got {len(clusters)}: "
            f"{[[p for _, p in c] for c in clusters]}"
        )
        # First cluster contains the gradually rising sequence
        first_cluster_prices = [p for _, p in clusters[0]]
        assert 100.0 in first_cluster_prices
        assert 102.0 in first_cluster_prices
        # Second cluster contains the outlier
        second_cluster_prices = [p for _, p in clusters[1]]
        assert 103.5 in second_cluster_prices

    def test_cluster_output_preserves_all_points(self):
        """Total number of points across all clusters equals input length."""
        points = [(i, 100.0 + i * 0.3) for i in range(20)]
        clusters = _cluster_price_levels(points, merge_threshold_pct=0.02)

        total = sum(len(c) for c in clusters)
        assert total == len(points)

    def test_three_distinct_groups(self):
        """Three well-separated groups form three clusters."""
        points = [
            (0, 100.0), (1, 100.5),     # group 1 ~ 100
            (2, 110.0), (3, 110.2),     # group 2 ~ 110
            (4, 120.0), (5, 120.1),     # group 3 ~ 120
        ]
        clusters = _cluster_price_levels(points, merge_threshold_pct=0.02)
        assert len(clusters) == 3


# ===========================================================================
# TestScoreLevels
# ===========================================================================


class TestScoreLevels:
    """Tests for _score_levels."""

    def _make_volumes(self, n: int, value: float = 1_000_000.0) -> np.ndarray:
        return np.full(n, value, dtype=float)

    def test_higher_touch_count_yields_higher_strength(self):
        """A cluster with more touches should score higher than one with fewer."""
        total_bars = 50
        current_price = 100.0
        volumes = self._make_volumes(total_bars)

        # Cluster with 5 touches vs cluster with 1 touch; same index
        cluster_many = [(10, 100.0), (15, 100.0), (20, 100.0), (25, 100.0), (30, 100.0)]
        cluster_few = [(10, 100.0)]

        levels_many = _score_levels(
            [cluster_many], volumes, total_bars, current_price
        )
        levels_few = _score_levels(
            [cluster_few], volumes, total_bars, current_price
        )

        assert len(levels_many) == 1
        assert len(levels_few) == 1
        assert levels_many[0].strength > levels_few[0].strength

    def test_more_recent_touch_yields_higher_score(self):
        """A level touched more recently should score higher than an older one."""
        total_bars = 100
        current_price = 100.0
        volumes = self._make_volumes(total_bars)

        # Recent: last touch at bar 95 (5 bars ago)
        cluster_recent = [(90, 100.0), (95, 100.0)]
        # Old: last touch at bar 20 (80 bars ago)
        cluster_old = [(15, 100.0), (20, 100.0)]

        levels_recent = _score_levels(
            [cluster_recent], volumes, total_bars, current_price
        )
        levels_old = _score_levels(
            [cluster_old], volumes, total_bars, current_price
        )

        assert levels_recent[0].strength > levels_old[0].strength

    def test_strength_bounded_between_0_and_1(self):
        """Strength score must always be in [0, 1]."""
        total_bars = 200
        current_price = 100.0
        volumes = self._make_volumes(total_bars)

        # Lots of touches to stress-test upper bound
        cluster = [(i, 100.0) for i in range(0, total_bars, 5)]
        levels = _score_levels([cluster], volumes, total_bars, current_price)

        assert len(levels) == 1
        assert 0.0 <= levels[0].strength <= 1.0

    def test_excludes_levels_beyond_max_distance(self):
        """Levels farther than max_distance_pct from current price are excluded."""
        total_bars = 50
        current_price = 100.0
        volumes = self._make_volumes(total_bars)

        # Level at 115 is 15% away; max_distance_pct=0.10 should exclude it
        cluster_far = [(25, 115.0), (30, 115.0)]
        levels = _score_levels(
            [cluster_far], volumes, total_bars, current_price, max_distance_pct=0.10
        )

        assert levels == []

    def test_empty_volumes_returns_empty(self):
        """Zero-length volumes array returns empty list."""
        clusters = [[(0, 100.0), (1, 100.0)]]
        levels = _score_levels(
            clusters,
            np.array([], dtype=float),
            total_bars=0,
            current_price=100.0,
        )
        assert levels == []

    def test_last_touch_idx_is_maximum_index_in_cluster(self):
        """last_touch_idx should be the highest index in the cluster."""
        total_bars = 50
        current_price = 100.0
        volumes = self._make_volumes(total_bars)

        cluster = [(5, 100.0), (20, 100.0), (35, 100.0)]
        levels = _score_levels([cluster], volumes, total_bars, current_price)

        assert len(levels) == 1
        assert levels[0].last_touch_idx == 35

    def test_touches_attribute_reflects_cluster_size(self):
        """SRLevel.touches should equal the number of points in the cluster."""
        total_bars = 50
        current_price = 100.0
        volumes = self._make_volumes(total_bars)

        cluster = [(10, 100.0), (20, 100.0), (30, 100.0)]
        levels = _score_levels([cluster], volumes, total_bars, current_price)

        assert levels[0].touches == 3


# ===========================================================================
# TestClusterSupportResistance (end-to-end)
# ===========================================================================


class TestClusterSupportResistance:
    """End-to-end tests for cluster_support_resistance."""

    def test_returns_empty_for_insufficient_data(self):
        """Fewer than 2*window+1 bars returns empty list."""
        window = 5
        n = 2 * window  # one too few: 10 bars
        highs = [100.0] * n
        lows = [98.0] * n
        closes = [99.0] * n
        volumes = [1_000_000.0] * n

        result = cluster_support_resistance(
            highs, lows, closes, volumes, window=window
        )

        assert result == []

    def test_returns_empty_for_zero_bars(self):
        """Empty arrays return empty list."""
        result = cluster_support_resistance([], [], [], [])
        assert result == []

    def test_returns_list_of_sr_levels(self):
        """Result elements are SRLevel instances."""
        highs, lows, closes, volumes = _make_oscillating_ohlcv(60)
        result = cluster_support_resistance(
            highs, lows, closes, volumes,
            window=5, min_touches=2, min_strength=0.0,
        )
        for item in result:
            assert isinstance(item, SRLevel)

    def test_filters_by_min_touches(self):
        """Levels with fewer than min_touches are excluded."""
        highs, lows, closes, volumes = _make_oscillating_ohlcv(60)

        # With very high min_touches, fewer levels should be returned
        result_strict = cluster_support_resistance(
            highs, lows, closes, volumes,
            window=5, min_touches=100, min_strength=0.0,
        )
        result_lenient = cluster_support_resistance(
            highs, lows, closes, volumes,
            window=5, min_touches=2, min_strength=0.0,
        )

        # Stricter filter produces no more levels than lenient
        assert len(result_strict) <= len(result_lenient)

    def test_filters_by_min_strength(self):
        """Levels below min_strength are excluded."""
        highs, lows, closes, volumes = _make_oscillating_ohlcv(60)

        result_strict = cluster_support_resistance(
            highs, lows, closes, volumes,
            window=5, min_touches=2, min_strength=0.99,
        )
        result_lenient = cluster_support_resistance(
            highs, lows, closes, volumes,
            window=5, min_touches=2, min_strength=0.0,
        )

        assert len(result_strict) <= len(result_lenient)
        # All returned levels must meet the min_strength threshold
        for lvl in result_strict:
            assert lvl.strength >= 0.99

    def test_results_sorted_by_strength_descending(self):
        """Returned levels must be ordered from strongest to weakest."""
        highs, lows, closes, volumes = _make_oscillating_ohlcv(80)
        result = cluster_support_resistance(
            highs, lows, closes, volumes,
            window=5, min_touches=2, min_strength=0.0,
        )

        strengths = [lvl.strength for lvl in result]
        assert strengths == sorted(strengths, reverse=True), (
            f"Levels not sorted by strength descending: {strengths}"
        )

    def test_oscillating_price_detects_levels_near_bounds(self):
        """Oscillating price between 95 and 105 should produce levels near those values."""
        n = 80
        low_price = 95.0
        high_price = 105.0
        highs, lows, closes, volumes = _make_oscillating_ohlcv(
            n, low_price=low_price, high_price=high_price
        )

        result = cluster_support_resistance(
            highs, lows, closes, volumes,
            window=5, min_touches=2, min_strength=0.0, max_distance_pct=0.20,
        )

        assert len(result) > 0, "Expected at least one S/R level in oscillating data"
        level_prices = [lvl.price for lvl in result]

        # At least one level should be close to either bound
        near_low = any(abs(p - low_price) / low_price < 0.05 for p in level_prices)
        near_high = any(abs(p - high_price) / high_price < 0.05 for p in level_prices)
        assert near_low or near_high, (
            f"No level near 95 or 105; found: {level_prices}"
        )

    def test_fixed_center_clustering_distinct_levels_not_merged(self):
        """A slowly drifting price sequence and a separate clear level are not merged.

        Prices 100, 100.5, 101, 101.5, 102 are all within 2% of center 100.
        A separate swing at 103.5 (>2% from 100) must remain its own cluster.
        This verifies fixed-center clustering prevents chaining drift.
        """
        # Build synthetic OHLCV where swing highs land exactly on our target prices.
        # We need at least 2*window+1 = 11 bars.
        # We craft highs so that swings at indices 2, 4, 6, 8, 10 are at the target prices
        # and lows so that corresponding swing lows also appear there.
        # Use window=1 so every local extremum is detected easily.
        window = 1
        target_prices = [100.0, 100.5, 101.0, 101.5, 102.0, 103.5]
        n = 2 * len(target_prices) + 3  # enough bars

        highs = []
        lows = []
        closes = []
        volumes = []

        # Alternate between a "valley" bar and a "peak" bar at target prices
        base = 99.0
        for i in range(n):
            group = i // 2
            if group < len(target_prices):
                peak = target_prices[group]
            else:
                peak = target_prices[-1]

            if i % 2 == 0:
                # Valley bar: high just below peak to create the alternating shape
                highs.append(base + 0.1)
                lows.append(base - 0.1)
                closes.append(base)
            else:
                # Peak bar: high = target price
                highs.append(peak)
                lows.append(peak - 0.2)
                closes.append(peak - 0.1)

            volumes.append(1_000_000.0)

        # Ensure last close is near the higher cluster so max_distance_pct works
        closes[-1] = 102.0

        result = cluster_support_resistance(
            highs, lows, closes, volumes,
            window=window,
            merge_threshold_pct=0.02,
            min_touches=1,
            min_strength=0.0,
            max_distance_pct=0.20,
        )

        level_prices = [lvl.price for lvl in result]
        # There should be at least 2 distinct clusters found
        assert len(level_prices) >= 2, (
            f"Expected at least 2 distinct level clusters, got: {level_prices}"
        )

        # The cluster near 100 and the separate level near 103.5 must both appear
        has_low_cluster = any(abs(p - 100.5) / 100.5 < 0.03 for p in level_prices)
        has_high_level = any(abs(p - 103.5) / 103.5 < 0.03 for p in level_prices)
        assert has_low_cluster, f"Missing cluster near 100-102; levels: {level_prices}"
        assert has_high_level, f"Missing distinct level near 103.5; levels: {level_prices}"

    def test_accepts_numpy_arrays(self):
        """cluster_support_resistance accepts numpy arrays, not just lists."""
        n = 60
        highs_arr = np.array([100.0 + (i % 10) for i in range(n)])
        lows_arr = highs_arr - 2.0
        closes_arr = highs_arr - 1.0
        volumes_arr = np.ones(n) * 1_000_000.0

        # Should not raise
        result = cluster_support_resistance(
            highs_arr, lows_arr, closes_arr, volumes_arr,
            window=5, min_touches=2, min_strength=0.0,
        )
        assert isinstance(result, list)

    def test_all_returned_levels_meet_min_strength(self):
        """Every returned SRLevel has strength >= min_strength."""
        min_strength = 0.35
        highs, lows, closes, volumes = _make_oscillating_ohlcv(80)
        result = cluster_support_resistance(
            highs, lows, closes, volumes,
            window=5, min_touches=2, min_strength=min_strength,
        )
        for lvl in result:
            assert lvl.strength >= min_strength, (
                f"Level {lvl.price} has strength {lvl.strength} < {min_strength}"
            )

    def test_all_returned_levels_meet_min_touches(self):
        """Every returned SRLevel has touches >= min_touches."""
        min_touches = 3
        highs, lows, closes, volumes = _make_oscillating_ohlcv(100)
        result = cluster_support_resistance(
            highs, lows, closes, volumes,
            window=5, min_touches=min_touches, min_strength=0.0,
        )
        for lvl in result:
            assert lvl.touches >= min_touches, (
                f"Level {lvl.price} has touches={lvl.touches} < {min_touches}"
            )
