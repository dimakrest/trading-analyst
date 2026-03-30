"""Unit tests for the TrailingStop module.

Tests FixedPercentTrailingStop, AtrTrailingStop, and TrailingStopUpdate for
position management.
"""

from decimal import Decimal

import pytest

from app.services.arena.trailing_stop import (
    AtrTrailingStop,
    FixedPercentTrailingStop,
    TrailingStopUpdate,
)


class TestTrailingStopUpdate:
    """Tests for TrailingStopUpdate dataclass."""

    @pytest.mark.unit
    def test_create_update_not_triggered(self) -> None:
        """Test creating update that was not triggered."""
        update = TrailingStopUpdate(
            highest_price=Decimal("110.00"),
            stop_price=Decimal("104.50"),
            stop_triggered=False,
        )

        assert update.highest_price == Decimal("110.00")
        assert update.stop_price == Decimal("104.50")
        assert update.stop_triggered is False
        assert update.trigger_price is None

    @pytest.mark.unit
    def test_create_update_triggered(self) -> None:
        """Test creating update that was triggered."""
        update = TrailingStopUpdate(
            highest_price=Decimal("110.00"),
            stop_price=Decimal("104.50"),
            stop_triggered=True,
            trigger_price=Decimal("104.50"),
        )

        assert update.stop_triggered is True
        assert update.trigger_price == Decimal("104.50")


class TestFixedPercentTrailingStopInit:
    """Tests for FixedPercentTrailingStop initialization."""

    @pytest.mark.unit
    def test_init_valid_percentage(self) -> None:
        """Test initialization with valid percentage."""
        stop = FixedPercentTrailingStop(Decimal("5.0"))

        assert stop.trail_pct == Decimal("5.0")

    @pytest.mark.unit
    def test_init_small_percentage(self) -> None:
        """Test initialization with small trailing percentage."""
        stop = FixedPercentTrailingStop(Decimal("0.5"))

        assert stop.trail_pct == Decimal("0.5")

    @pytest.mark.unit
    def test_init_large_percentage(self) -> None:
        """Test initialization with large trailing percentage."""
        stop = FixedPercentTrailingStop(Decimal("50.0"))

        assert stop.trail_pct == Decimal("50.0")

    @pytest.mark.unit
    def test_init_percentage_just_above_zero(self) -> None:
        """Test initialization with very small positive percentage."""
        stop = FixedPercentTrailingStop(Decimal("0.01"))

        assert stop.trail_pct == Decimal("0.01")

    @pytest.mark.unit
    def test_init_percentage_just_below_100(self) -> None:
        """Test initialization with percentage just below 100."""
        stop = FixedPercentTrailingStop(Decimal("99.99"))

        assert stop.trail_pct == Decimal("99.99")

    @pytest.mark.unit
    def test_init_zero_percentage_raises(self) -> None:
        """Test that zero percentage raises ValueError."""
        with pytest.raises(ValueError, match="must be between 0 and 100"):
            FixedPercentTrailingStop(Decimal("0"))

    @pytest.mark.unit
    def test_init_negative_percentage_raises(self) -> None:
        """Test that negative percentage raises ValueError."""
        with pytest.raises(ValueError, match="must be between 0 and 100"):
            FixedPercentTrailingStop(Decimal("-5.0"))

    @pytest.mark.unit
    def test_init_100_percentage_raises(self) -> None:
        """Test that exactly 100% raises ValueError."""
        with pytest.raises(ValueError, match="must be between 0 and 100"):
            FixedPercentTrailingStop(Decimal("100"))

    @pytest.mark.unit
    def test_init_above_100_percentage_raises(self) -> None:
        """Test that percentage above 100 raises ValueError."""
        with pytest.raises(ValueError, match="must be between 0 and 100"):
            FixedPercentTrailingStop(Decimal("150"))


class TestFixedPercentTrailingStopCalculateInitial:
    """Tests for FixedPercentTrailingStop.calculate_initial_stop() method."""

    @pytest.mark.unit
    def test_calculate_initial_stop_5_percent(self) -> None:
        """Test initial stop calculation with 5% trail."""
        stop = FixedPercentTrailingStop(Decimal("5.0"))

        highest, stop_price = stop.calculate_initial_stop(Decimal("100.00"))

        assert highest == Decimal("100.00")
        assert stop_price == Decimal("95.0000")  # 100 * 0.95

    @pytest.mark.unit
    def test_calculate_initial_stop_10_percent(self) -> None:
        """Test initial stop calculation with 10% trail."""
        stop = FixedPercentTrailingStop(Decimal("10.0"))

        highest, stop_price = stop.calculate_initial_stop(Decimal("100.00"))

        assert highest == Decimal("100.00")
        assert stop_price == Decimal("90.0000")  # 100 * 0.90

    @pytest.mark.unit
    def test_calculate_initial_stop_small_price(self) -> None:
        """Test initial stop with small entry price."""
        stop = FixedPercentTrailingStop(Decimal("5.0"))

        highest, stop_price = stop.calculate_initial_stop(Decimal("1.50"))

        assert highest == Decimal("1.50")
        assert stop_price == Decimal("1.4250")  # 1.50 * 0.95

    @pytest.mark.unit
    def test_calculate_initial_stop_large_price(self) -> None:
        """Test initial stop with large entry price."""
        stop = FixedPercentTrailingStop(Decimal("5.0"))

        highest, stop_price = stop.calculate_initial_stop(Decimal("5000.00"))

        assert highest == Decimal("5000.00")
        assert stop_price == Decimal("4750.0000")  # 5000 * 0.95

    @pytest.mark.unit
    def test_calculate_initial_stop_precision(self) -> None:
        """Test that initial stop has correct decimal precision."""
        stop = FixedPercentTrailingStop(Decimal("7.0"))

        highest, stop_price = stop.calculate_initial_stop(Decimal("123.45"))

        assert highest == Decimal("123.45")
        # Should be quantized to 4 decimal places
        assert stop_price == Decimal("114.8085")  # 123.45 * 0.93


class TestFixedPercentTrailingStopUpdate:
    """Tests for FixedPercentTrailingStop.update() method."""

    @pytest.fixture
    def stop_5pct(self) -> FixedPercentTrailingStop:
        """Create 5% trailing stop."""
        return FixedPercentTrailingStop(Decimal("5.0"))

    @pytest.mark.unit
    def test_update_new_high_raises_stop(self, stop_5pct: FixedPercentTrailingStop) -> None:
        """Test that new high price raises the stop."""
        # Entry at 100, now price rises to 110
        update = stop_5pct.update(
            current_high=Decimal("110.00"),
            current_low=Decimal("105.00"),
            previous_highest=Decimal("100.00"),
            previous_stop=Decimal("95.00"),
        )

        assert update.stop_triggered is False
        assert update.highest_price == Decimal("110.00")
        assert update.stop_price == Decimal("104.5000")  # 110 * 0.95
        assert update.trigger_price is None

    @pytest.mark.unit
    def test_update_no_new_high_keeps_stop(self, stop_5pct: FixedPercentTrailingStop) -> None:
        """Test that without new high, stop stays the same."""
        # Previous high was 110, current price stays below
        update = stop_5pct.update(
            current_high=Decimal("108.00"),
            current_low=Decimal("106.00"),
            previous_highest=Decimal("110.00"),
            previous_stop=Decimal("104.50"),
        )

        assert update.stop_triggered is False
        assert update.highest_price == Decimal("110.00")
        assert update.stop_price == Decimal("104.50")  # Unchanged

    @pytest.mark.unit
    def test_update_stop_can_only_move_up(self, stop_5pct: FixedPercentTrailingStop) -> None:
        """Test that stop never moves down even if calculated lower."""
        # This shouldn't happen in practice, but test the invariant
        # If highest was 110 (stop at 104.5), and current high is 105 (would be 99.75)
        # Stop should stay at 104.50

        update = stop_5pct.update(
            current_high=Decimal("105.00"),
            current_low=Decimal("103.00"),
            previous_highest=Decimal("110.00"),
            previous_stop=Decimal("104.50"),
        )

        assert update.stop_price == Decimal("104.50")  # Never goes down
        assert update.highest_price == Decimal("110.00")  # Keep previous highest

    @pytest.mark.unit
    def test_update_triggers_when_low_touches_stop(
        self, stop_5pct: FixedPercentTrailingStop
    ) -> None:
        """Test that stop triggers when low equals stop price."""
        update = stop_5pct.update(
            current_high=Decimal("106.00"),
            current_low=Decimal("104.50"),  # Exactly at stop
            previous_highest=Decimal("110.00"),
            previous_stop=Decimal("104.50"),
        )

        assert update.stop_triggered is True
        assert update.trigger_price == Decimal("104.50")
        assert update.highest_price == Decimal("110.00")  # Preserved
        assert update.stop_price == Decimal("104.50")  # Preserved

    @pytest.mark.unit
    def test_update_triggers_when_low_below_stop(
        self, stop_5pct: FixedPercentTrailingStop
    ) -> None:
        """Test that stop triggers when low goes below stop price."""
        update = stop_5pct.update(
            current_high=Decimal("106.00"),
            current_low=Decimal("103.00"),  # Below stop at 104.50
            previous_highest=Decimal("110.00"),
            previous_stop=Decimal("104.50"),
        )

        assert update.stop_triggered is True
        assert update.trigger_price == Decimal("104.50")  # Exit at stop price

    @pytest.mark.unit
    def test_update_does_not_trigger_when_low_above_stop(
        self, stop_5pct: FixedPercentTrailingStop
    ) -> None:
        """Test that stop doesn't trigger when low stays above stop."""
        update = stop_5pct.update(
            current_high=Decimal("108.00"),
            current_low=Decimal("105.00"),  # Above stop at 104.50
            previous_highest=Decimal("110.00"),
            previous_stop=Decimal("104.50"),
        )

        assert update.stop_triggered is False
        assert update.trigger_price is None


class TestFixedPercentTrailingStopScenarios:
    """Integration-style tests for realistic trading scenarios."""

    @pytest.mark.unit
    def test_full_trade_lifecycle_profit(self) -> None:
        """Test complete trade lifecycle with profit tracking.

        Verifies trailing stop progressively locks in gains:
        - Entry: $100 (stop: $95)
        - Day 2: Rise to $105 (stop: $99.75)
        - Day 3: Rise to $110 (stop: $104.50)
        - Day 4: Consolidate at $108 (stop stays: $104.50)
        - Day 5: Fall to $103 (triggers stop for +4.5% profit)
        """
        stop = FixedPercentTrailingStop(Decimal("5.0"))

        # Entry at $100
        highest, stop_price = stop.calculate_initial_stop(Decimal("100.00"))
        assert highest == Decimal("100.00")
        assert stop_price == Decimal("95.0000")

        # Day 2: Price rises to $105
        update = stop.update(
            current_high=Decimal("105.00"),
            current_low=Decimal("101.00"),
            previous_highest=highest,
            previous_stop=stop_price,
        )
        assert not update.stop_triggered
        assert update.highest_price == Decimal("105.00")
        assert update.stop_price == Decimal("99.7500")
        highest, stop_price = update.highest_price, update.stop_price

        # Day 3: Price rises to $110
        update = stop.update(
            current_high=Decimal("110.00"),
            current_low=Decimal("104.00"),
            previous_highest=highest,
            previous_stop=stop_price,
        )
        assert not update.stop_triggered
        assert update.highest_price == Decimal("110.00")
        assert update.stop_price == Decimal("104.5000")
        highest, stop_price = update.highest_price, update.stop_price

        # Day 4: Price consolidates
        update = stop.update(
            current_high=Decimal("108.00"),
            current_low=Decimal("106.00"),
            previous_highest=highest,
            previous_stop=stop_price,
        )
        assert not update.stop_triggered
        assert update.highest_price == Decimal("110.00")
        assert update.stop_price == Decimal("104.5000")
        highest, stop_price = update.highest_price, update.stop_price

        # Day 5: Price drops and triggers stop
        update = stop.update(
            current_high=Decimal("107.00"),
            current_low=Decimal("103.00"),
            previous_highest=highest,
            previous_stop=stop_price,
        )
        assert update.stop_triggered
        assert update.trigger_price == Decimal("104.5000")

    @pytest.mark.unit
    def test_full_trade_lifecycle_loss(self) -> None:
        """Test immediate stop loss trigger on first day decline."""
        stop = FixedPercentTrailingStop(Decimal("5.0"))

        # Entry at $100 with stop at $95
        highest, stop_price = stop.calculate_initial_stop(Decimal("100.00"))

        # Day 2: Price drops immediately below stop
        update = stop.update(
            current_high=Decimal("98.00"),
            current_low=Decimal("94.00"),
            previous_highest=highest,
            previous_stop=stop_price,
        )
        assert update.stop_triggered
        assert update.trigger_price == Decimal("95.0000")

    @pytest.mark.unit
    def test_narrow_trailing_stop_2_percent(self) -> None:
        """Test with narrow 2% trailing stop."""
        stop = FixedPercentTrailingStop(Decimal("2.0"))

        highest, stop_price = stop.calculate_initial_stop(Decimal("100.00"))
        assert stop_price == Decimal("98.0000")

        # Small move up
        update = stop.update(
            current_high=Decimal("102.00"),
            current_low=Decimal("100.50"),
            previous_highest=highest,
            previous_stop=stop_price,
        )
        assert not update.stop_triggered
        assert update.stop_price == Decimal("99.9600")  # 102 * 0.98

    @pytest.mark.unit
    def test_wide_trailing_stop_20_percent(self) -> None:
        """Test with wide 20% trailing stop."""
        stop = FixedPercentTrailingStop(Decimal("20.0"))

        highest, stop_price = stop.calculate_initial_stop(Decimal("100.00"))
        assert stop_price == Decimal("80.0000")

        # Price rises significantly
        update = stop.update(
            current_high=Decimal("150.00"),
            current_low=Decimal("140.00"),
            previous_highest=highest,
            previous_stop=stop_price,
        )
        assert not update.stop_triggered
        assert update.stop_price == Decimal("120.0000")  # 150 * 0.80

    @pytest.mark.unit
    def test_multiple_days_without_new_highs(self) -> None:
        """Test that stop stays constant during consolidation."""
        stop = FixedPercentTrailingStop(Decimal("5.0"))

        # Entry at $100, price rises to $110
        highest, stop_price = stop.calculate_initial_stop(Decimal("100.00"))
        update = stop.update(
            current_high=Decimal("110.00"),
            current_low=Decimal("108.00"),
            previous_highest=highest,
            previous_stop=stop_price,
        )
        highest, stop_price = update.highest_price, update.stop_price

        # 3 days of consolidation
        for _ in range(3):
            update = stop.update(
                current_high=Decimal("109.00"),
                current_low=Decimal("106.00"),
                previous_highest=highest,
                previous_stop=stop_price,
            )
            assert update.highest_price == Decimal("110.00")
            assert update.stop_price == Decimal("104.5000")
            highest, stop_price = update.highest_price, update.stop_price

    @pytest.mark.unit
    def test_penny_stock_small_values(self) -> None:
        """Test with penny stock small values."""
        stop = FixedPercentTrailingStop(Decimal("5.0"))

        # Entry at $0.50
        highest, stop_price = stop.calculate_initial_stop(Decimal("0.50"))
        assert stop_price == Decimal("0.4750")

        # Price rises to $0.60
        update = stop.update(
            current_high=Decimal("0.60"),
            current_low=Decimal("0.55"),
            previous_highest=highest,
            previous_stop=stop_price,
        )
        assert update.stop_price == Decimal("0.5700")

    @pytest.mark.unit
    def test_high_precision_values(self) -> None:
        """Test with high precision decimal values."""
        stop = FixedPercentTrailingStop(Decimal("5.0"))

        highest, stop_price = stop.calculate_initial_stop(Decimal("123.45678"))

        update = stop.update(
            current_high=Decimal("130.12345"),
            current_low=Decimal("125.98765"),
            previous_highest=highest,
            previous_stop=stop_price,
        )

        # Verify it handles high precision without errors
        assert update.stop_triggered is False
        assert update.highest_price == Decimal("130.12345")


class TestTrailingStopEdgeCases:
    """Tests for edge cases in trailing stop behavior."""

    @pytest.mark.unit
    def test_stop_at_exact_entry_price(self) -> None:
        """Test when price returns to exact entry price."""
        stop = FixedPercentTrailingStop(Decimal("5.0"))

        highest, stop_price = stop.calculate_initial_stop(Decimal("100.00"))

        # Price consolidates at entry level
        update = stop.update(
            current_high=Decimal("100.00"),
            current_low=Decimal("96.00"),  # Above stop at 95
            previous_highest=highest,
            previous_stop=stop_price,
        )
        assert not update.stop_triggered
        assert update.highest_price == Decimal("100.00")

    @pytest.mark.unit
    def test_gap_down_below_stop(self) -> None:
        """Test gap down that opens completely below stop level.

        Verifies that when price gaps down below stop, exit price
        is the stop level (not the actual gap price).
        """
        stop = FixedPercentTrailingStop(Decimal("5.0"))

        highest, stop_price = stop.calculate_initial_stop(Decimal("100.00"))

        # Gap down - entire bar is below stop
        update = stop.update(
            current_high=Decimal("92.00"),
            current_low=Decimal("90.00"),
            previous_highest=highest,
            previous_stop=stop_price,
        )
        assert update.stop_triggered
        assert update.trigger_price == Decimal("95.0000")

    @pytest.mark.unit
    def test_very_small_percentage(self) -> None:
        """Test with very small trailing percentage."""
        stop = FixedPercentTrailingStop(Decimal("0.1"))

        highest, stop_price = stop.calculate_initial_stop(Decimal("100.00"))
        assert stop_price == Decimal("99.9000")  # Very tight stop

    @pytest.mark.unit
    def test_consecutive_new_highs(self) -> None:
        """Test stop adjustment with consecutive new highs.

        Verifies that each new high raises the trailing stop
        progressively to lock in more gains.
        """
        stop = FixedPercentTrailingStop(Decimal("5.0"))

        highest, stop_price = stop.calculate_initial_stop(Decimal("100.00"))

        prices = [105, 110, 115, 120, 125]
        for price in prices:
            update = stop.update(
                current_high=Decimal(str(price)),
                current_low=Decimal(str(price - 3)),
                previous_highest=highest,
                previous_stop=stop_price,
            )
            assert not update.stop_triggered
            highest, stop_price = update.highest_price, update.stop_price

        # Final state after all new highs
        assert highest == Decimal("125")
        assert stop_price == Decimal("118.7500")


# =============================================================================
# AtrTrailingStop tests
# =============================================================================


class TestAtrTrailingStopInit:
    """Tests for AtrTrailingStop initialization."""

    @pytest.mark.unit
    def test_default_parameters(self) -> None:
        """Test default constructor values."""
        stop = AtrTrailingStop()

        assert stop.atr_multiplier == 2.0
        assert stop.min_pct == 2.0
        assert stop.max_pct == 10.0

    @pytest.mark.unit
    def test_custom_parameters(self) -> None:
        """Test custom constructor values."""
        stop = AtrTrailingStop(atr_multiplier=3.0, min_pct=1.5, max_pct=8.0)

        assert stop.atr_multiplier == 3.0
        assert stop.min_pct == 1.5
        assert stop.max_pct == 8.0

    @pytest.mark.unit
    def test_zero_atr_multiplier_raises(self) -> None:
        """Test that atr_multiplier=0 raises ValueError."""
        with pytest.raises(ValueError, match="atr_multiplier must be positive"):
            AtrTrailingStop(atr_multiplier=0.0)

    @pytest.mark.unit
    def test_negative_atr_multiplier_raises(self) -> None:
        """Test that negative atr_multiplier raises ValueError."""
        with pytest.raises(ValueError, match="atr_multiplier must be positive"):
            AtrTrailingStop(atr_multiplier=-1.0)

    @pytest.mark.unit
    def test_zero_min_pct_raises(self) -> None:
        """Test that min_pct=0 raises ValueError."""
        with pytest.raises(ValueError, match="min_pct must be positive"):
            AtrTrailingStop(min_pct=0.0)

    @pytest.mark.unit
    def test_max_pct_100_raises(self) -> None:
        """Test that max_pct=100 raises ValueError."""
        with pytest.raises(ValueError, match="max_pct must be less than 100"):
            AtrTrailingStop(max_pct=100.0)

    @pytest.mark.unit
    def test_min_pct_exceeds_max_pct_raises(self) -> None:
        """Test that min_pct > max_pct raises ValueError."""
        with pytest.raises(ValueError, match="min_pct .* must not exceed max_pct"):
            AtrTrailingStop(min_pct=8.0, max_pct=5.0)

    @pytest.mark.unit
    def test_min_pct_equals_max_pct_is_valid(self) -> None:
        """Test that min_pct == max_pct is allowed (degenerate but valid)."""
        stop = AtrTrailingStop(min_pct=5.0, max_pct=5.0)
        assert stop.min_pct == stop.max_pct == 5.0


class TestAtrTrailingStopCalculateInitial:
    """Tests for AtrTrailingStop.calculate_initial_stop()."""

    @pytest.fixture
    def atr_stop(self) -> AtrTrailingStop:
        """Standard ATR stop with 2x multiplier, 2-10% clamp."""
        return AtrTrailingStop(atr_multiplier=2.0, min_pct=2.0, max_pct=10.0)

    @pytest.mark.unit
    def test_normal_atr_computes_correctly(self, atr_stop: AtrTrailingStop) -> None:
        """Test trail_pct = 2.0 * 3.5 = 7.0, within [2, 10] clamp."""
        highest, stop, trail_pct = atr_stop.calculate_initial_stop(
            entry_price=Decimal("100.00"), atr_pct=3.5
        )

        assert highest == Decimal("100.00")
        assert trail_pct == Decimal("7.0")
        # stop = 100 * (1 - 0.07) = 93.00
        assert stop == Decimal("93.0000")

    @pytest.mark.unit
    def test_clamp_to_min_pct(self, atr_stop: AtrTrailingStop) -> None:
        """Test trail_pct clamped to min when 2 * atr_pct < min_pct."""
        # 2.0 * 0.5 = 1.0 < min_pct=2.0 → clamps to 2.0
        highest, stop, trail_pct = atr_stop.calculate_initial_stop(
            entry_price=Decimal("100.00"), atr_pct=0.5
        )

        assert trail_pct == Decimal("2.0")
        # stop = 100 * 0.98 = 98.00
        assert stop == Decimal("98.0000")

    @pytest.mark.unit
    def test_clamp_to_max_pct(self, atr_stop: AtrTrailingStop) -> None:
        """Test trail_pct clamped to max when 2 * atr_pct > max_pct."""
        # 2.0 * 8.0 = 16.0 > max_pct=10.0 → clamps to 10.0
        highest, stop, trail_pct = atr_stop.calculate_initial_stop(
            entry_price=Decimal("100.00"), atr_pct=8.0
        )

        assert trail_pct == Decimal("10.0")
        # stop = 100 * 0.90 = 90.00
        assert stop == Decimal("90.0000")

    @pytest.mark.unit
    def test_zero_atr_pct_raises(self, atr_stop: AtrTrailingStop) -> None:
        """Test that atr_pct=0 raises ValueError."""
        with pytest.raises(ValueError, match="atr_pct must be positive"):
            atr_stop.calculate_initial_stop(Decimal("100.00"), 0.0)

    @pytest.mark.unit
    def test_negative_atr_pct_raises(self, atr_stop: AtrTrailingStop) -> None:
        """Test that negative atr_pct raises ValueError."""
        with pytest.raises(ValueError, match="atr_pct must be positive"):
            atr_stop.calculate_initial_stop(Decimal("100.00"), -1.0)

    @pytest.mark.unit
    def test_returns_three_tuple(self, atr_stop: AtrTrailingStop) -> None:
        """Test that calculate_initial_stop returns a 3-tuple."""
        result = atr_stop.calculate_initial_stop(Decimal("50.00"), 3.0)
        assert len(result) == 3

    @pytest.mark.unit
    def test_stop_precision_quantized_to_4_places(
        self, atr_stop: AtrTrailingStop
    ) -> None:
        """Test that stop price is quantized to 4 decimal places."""
        _, stop, _ = atr_stop.calculate_initial_stop(
            entry_price=Decimal("123.45"), atr_pct=3.5
        )
        # Verify 4 decimal places
        assert stop == stop.quantize(Decimal("0.0001"))

    @pytest.mark.unit
    def test_highest_equals_entry_price(self, atr_stop: AtrTrailingStop) -> None:
        """Test that highest price equals entry price at initiation."""
        entry = Decimal("250.75")
        highest, _, _ = atr_stop.calculate_initial_stop(entry, 4.0)

        assert highest == entry

    @pytest.mark.unit
    def test_exact_boundary_not_clamped(self) -> None:
        """Test that atr_pct exactly at boundary is not clamped."""
        stop = AtrTrailingStop(atr_multiplier=2.0, min_pct=2.0, max_pct=10.0)
        # 2.0 * 5.0 = 10.0, exactly at max_pct — no clamp needed
        _, _, trail_pct = stop.calculate_initial_stop(Decimal("100.00"), 5.0)

        assert trail_pct == Decimal("10.0")


class TestAtrTrailingStopUpdate:
    """Tests for AtrTrailingStop.update()."""

    @pytest.fixture
    def atr_stop(self) -> AtrTrailingStop:
        """ATR stop with 7% trail stored at entry."""
        return AtrTrailingStop(atr_multiplier=2.0, min_pct=2.0, max_pct=10.0)

    @pytest.mark.unit
    def test_no_new_high_stop_unchanged(self, atr_stop: AtrTrailingStop) -> None:
        """Test that stop stays unchanged when no new high is made."""
        update = atr_stop.update(
            current_high=Decimal("108.00"),
            current_low=Decimal("106.00"),
            previous_highest=Decimal("110.00"),
            previous_stop=Decimal("102.30"),
            trail_pct=Decimal("7.0"),
        )

        assert update.stop_triggered is False
        assert update.highest_price == Decimal("110.00")
        assert update.stop_price == Decimal("102.30")

    @pytest.mark.unit
    def test_new_high_raises_stop(self, atr_stop: AtrTrailingStop) -> None:
        """Test that new high moves the stop up."""
        # Previous: highest=100, stop=93 (7% trail)
        # New high: 110 → new stop = 110 * 0.93 = 102.30
        update = atr_stop.update(
            current_high=Decimal("110.00"),
            current_low=Decimal("105.00"),
            previous_highest=Decimal("100.00"),
            previous_stop=Decimal("93.0000"),
            trail_pct=Decimal("7.0"),
        )

        assert update.stop_triggered is False
        assert update.highest_price == Decimal("110.00")
        assert update.stop_price == Decimal("102.3000")  # 110 * 0.93

    @pytest.mark.unit
    def test_stop_triggered_at_stop_price(self, atr_stop: AtrTrailingStop) -> None:
        """Test stop triggers when low == stop price."""
        update = atr_stop.update(
            current_high=Decimal("110.00"),
            current_low=Decimal("102.30"),  # exactly at stop
            previous_highest=Decimal("110.00"),
            previous_stop=Decimal("102.30"),
            trail_pct=Decimal("7.0"),
        )

        assert update.stop_triggered is True
        assert update.trigger_price == Decimal("102.30")

    @pytest.mark.unit
    def test_stop_triggered_below_stop_price(self, atr_stop: AtrTrailingStop) -> None:
        """Test stop triggers when low goes below stop price."""
        update = atr_stop.update(
            current_high=Decimal("110.00"),
            current_low=Decimal("99.00"),  # below stop at 102.30
            previous_highest=Decimal("110.00"),
            previous_stop=Decimal("102.30"),
            trail_pct=Decimal("7.0"),
        )

        assert update.stop_triggered is True
        assert update.trigger_price == Decimal("102.30")

    @pytest.mark.unit
    def test_stop_only_moves_up(self, atr_stop: AtrTrailingStop) -> None:
        """Test that stop never moves down."""
        # previous_highest=110 means stop should be 102.30 (at 7%).
        # current_high=105 would compute 105 * 0.93 = 97.65 — below previous_stop.
        # The stop must stay at previous_stop.
        update = atr_stop.update(
            current_high=Decimal("105.00"),
            current_low=Decimal("103.00"),
            previous_highest=Decimal("110.00"),
            previous_stop=Decimal("102.30"),
            trail_pct=Decimal("7.0"),
        )

        assert update.stop_triggered is False
        assert update.stop_price == Decimal("102.30")  # unchanged
        assert update.highest_price == Decimal("110.00")  # unchanged

    @pytest.mark.unit
    def test_gap_down_triggers_at_stop_not_open(self, atr_stop: AtrTrailingStop) -> None:
        """Test gap-down scenario where entire bar is below stop.

        The update() return value reports trigger_price=previous_stop.
        The caller (simulation engine) then uses min(trigger_price, open)
        to handle gap-down fills correctly.
        """
        update = atr_stop.update(
            current_high=Decimal("91.00"),
            current_low=Decimal("89.00"),
            previous_highest=Decimal("100.00"),
            previous_stop=Decimal("93.00"),
            trail_pct=Decimal("7.0"),
        )

        assert update.stop_triggered is True
        assert update.trigger_price == Decimal("93.00")

    @pytest.mark.unit
    def test_different_positions_use_different_trail_pct(
        self, atr_stop: AtrTrailingStop
    ) -> None:
        """Test that per-position trail_pct is respected independently.

        Simulates two positions with different ATR-computed trail percentages
        sharing a single AtrTrailingStop instance.
        """
        # Position A: 5% trail (calm stock)
        update_a = atr_stop.update(
            current_high=Decimal("110.00"),
            current_low=Decimal("105.00"),
            previous_highest=Decimal("100.00"),
            previous_stop=Decimal("95.00"),
            trail_pct=Decimal("5.0"),
        )
        # Position B: 7% trail (volatile stock)
        update_b = atr_stop.update(
            current_high=Decimal("110.00"),
            current_low=Decimal("105.00"),
            previous_highest=Decimal("100.00"),
            previous_stop=Decimal("93.00"),
            trail_pct=Decimal("7.0"),
        )

        assert update_a.stop_triggered is False
        assert update_b.stop_triggered is False
        # A: 110 * 0.95 = 104.50
        assert update_a.stop_price == Decimal("104.5000")
        # B: 110 * 0.93 = 102.30
        assert update_b.stop_price == Decimal("102.3000")


class TestAtrTrailingStopLifecycle:
    """Integration-style tests for realistic ATR trailing stop lifecycle."""

    @pytest.mark.unit
    def test_full_lifecycle_profit(self) -> None:
        """Test a profitable trade: entry → rise → pullback → stop exit.

        atr_pct=3.5, multiplier=2.0 → trail_pct=7.0%
        - Entry $100: stop $93.00
        - Day 2: High $108 → stop $100.44
        - Day 3: High $115 → stop $106.95
        - Day 4: Consolidate, low $107 → no trigger (107 > 106.95)
        - Day 5: Drop to $106 → stop triggers at $106.95
        """
        atr_stop = AtrTrailingStop(atr_multiplier=2.0, min_pct=2.0, max_pct=10.0)

        # Entry at $100, ATR 3.5%
        highest, stop, trail_pct = atr_stop.calculate_initial_stop(
            Decimal("100.00"), 3.5
        )
        assert trail_pct == Decimal("7.0")
        assert stop == Decimal("93.0000")

        # Day 2: high $108
        update = atr_stop.update(
            Decimal("108.00"), Decimal("103.00"), highest, stop, trail_pct
        )
        assert not update.stop_triggered
        assert update.highest_price == Decimal("108.00")
        assert update.stop_price == Decimal("100.4400")  # 108 * 0.93
        highest, stop = update.highest_price, update.stop_price

        # Day 3: high $115
        update = atr_stop.update(
            Decimal("115.00"), Decimal("110.00"), highest, stop, trail_pct
        )
        assert not update.stop_triggered
        assert update.highest_price == Decimal("115.00")
        assert update.stop_price == Decimal("106.9500")  # 115 * 0.93
        highest, stop = update.highest_price, update.stop_price

        # Day 4: consolidation (no new high)
        update = atr_stop.update(
            Decimal("113.00"), Decimal("108.00"), highest, stop, trail_pct
        )
        assert not update.stop_triggered
        assert update.highest_price == Decimal("115.00")
        assert update.stop_price == Decimal("106.9500")
        highest, stop = update.highest_price, update.stop_price

        # Day 5: drop triggers stop
        update = atr_stop.update(
            Decimal("110.00"), Decimal("106.00"), highest, stop, trail_pct
        )
        assert update.stop_triggered
        assert update.trigger_price == Decimal("106.9500")

    @pytest.mark.unit
    def test_volatile_stock_gets_wider_stop(self) -> None:
        """Volatile stock (high ATR) gets wider stop than calm stock."""
        atr_stop = AtrTrailingStop(atr_multiplier=2.0, min_pct=2.0, max_pct=10.0)
        entry = Decimal("100.00")

        # Volatile: ATR 4%, trail = 8%
        _, stop_volatile, trail_volatile = atr_stop.calculate_initial_stop(entry, 4.0)
        # Calm: ATR 1.5%, trail = 3%
        _, stop_calm, trail_calm = atr_stop.calculate_initial_stop(entry, 1.5)

        assert trail_volatile > trail_calm
        assert stop_volatile < stop_calm  # wider stop = lower stop price

    @pytest.mark.unit
    def test_min_clamp_protects_overly_tight_stop(self) -> None:
        """Very low ATR stock gets the minimum stop, not a dangerously tight one."""
        atr_stop = AtrTrailingStop(atr_multiplier=2.0, min_pct=2.0, max_pct=10.0)
        # atr_pct=0.3 → raw=0.6 → clamped to 2.0
        _, _, trail_pct = atr_stop.calculate_initial_stop(Decimal("100.00"), 0.3)

        assert trail_pct == Decimal("2.0")

    @pytest.mark.unit
    def test_max_clamp_caps_very_wide_stop(self) -> None:
        """Very volatile stock gets the maximum stop, not an excessively wide one."""
        atr_stop = AtrTrailingStop(atr_multiplier=2.0, min_pct=2.0, max_pct=10.0)
        # atr_pct=9.0 → raw=18.0 → clamped to 10.0
        _, _, trail_pct = atr_stop.calculate_initial_stop(Decimal("100.00"), 9.0)

        assert trail_pct == Decimal("10.0")
