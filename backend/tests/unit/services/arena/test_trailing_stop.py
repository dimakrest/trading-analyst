"""Unit tests for the TrailingStop module.

Tests FixedPercentTrailingStop and TrailingStopUpdate for position management.
"""

from decimal import Decimal

import pytest

from app.services.arena.trailing_stop import FixedPercentTrailingStop, TrailingStopUpdate


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
