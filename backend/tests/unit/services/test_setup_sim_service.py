"""Unit tests for the setup simulation service.

Tests cover simulate_setup() and run_simulation() functions with controlled
price bar sequences to verify entry/exit logic, stop mechanics, retriggering,
and aggregation calculations.
"""

from datetime import date
from decimal import Decimal

import pytest

from app.schemas.setup_sim import SetupDefinition, SetupResult, TradeResult
from app.services.arena.agent_protocol import PriceBar
from app.services.setup_sim_service import POSITION_SIZE, simulate_setup, run_simulation

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_bar(
    d: date,
    open_: float,
    high: float,
    low: float,
    close: float,
    volume: int = 1_000_000,
) -> PriceBar:
    """Construct a PriceBar from plain floats."""
    return PriceBar(
        date=d,
        open=Decimal(str(open_)),
        high=Decimal(str(high)),
        low=Decimal(str(low)),
        close=Decimal(str(close)),
        volume=volume,
    )


def make_setup(
    symbol: str = "AAPL",
    entry_price: float = 100.0,
    stop_loss_day1: float = 95.0,
    trailing_stop_pct: float = 5.0,
    start_date: date = date(2024, 1, 1),
) -> SetupDefinition:
    """Construct a SetupDefinition with sensible defaults."""
    return SetupDefinition(
        symbol=symbol,
        entry_price=Decimal(str(entry_price)),
        stop_loss_day1=Decimal(str(stop_loss_day1)),
        trailing_stop_pct=Decimal(str(trailing_stop_pct)),
        start_date=start_date,
    )


# ---------------------------------------------------------------------------
# simulate_setup() tests
# ---------------------------------------------------------------------------


class TestSimulateSetupEntryTrigger:
    """Entry trigger: price crosses above entry → position opens."""

    def test_entry_triggered_when_high_reaches_entry(self):
        """Position opens when bar.high >= entry_price."""
        setup = make_setup(entry_price=100.0, stop_loss_day1=95.0, trailing_stop_pct=5.0)

        bars = [
            # Day 1: price crosses entry at 100, stays well above day-1 stop
            make_bar(date(2024, 1, 2), open_=98.0, high=101.0, low=97.0, close=100.5),
            # Day 2: steady — no stop hit, no new high
            make_bar(date(2024, 1, 3), open_=100.5, high=100.8, low=96.0, close=100.6),
            # Day 3: end of data — position closed at last close
            make_bar(date(2024, 1, 4), open_=100.6, high=101.0, low=99.0, close=101.0),
        ]

        result = simulate_setup(setup, bars, end_date=date(2024, 1, 4))

        assert result.times_triggered == 1
        assert len(result.trades) == 1
        trade = result.trades[0]
        assert trade.entry_date == date(2024, 1, 2)
        assert trade.entry_price == Decimal("100.0")
        assert trade.exit_reason == "simulation_end"

    def test_no_entry_when_high_never_reaches_entry(self):
        """No trades when price never reaches entry_price."""
        setup = make_setup(entry_price=110.0, stop_loss_day1=105.0, trailing_stop_pct=5.0)

        bars = [
            make_bar(date(2024, 1, 2), open_=98.0, high=101.0, low=97.0, close=100.0),
            make_bar(date(2024, 1, 3), open_=100.0, high=102.0, low=99.0, close=101.0),
            make_bar(date(2024, 1, 4), open_=101.0, high=103.0, low=100.0, close=102.0),
        ]

        result = simulate_setup(setup, bars, end_date=date(2024, 1, 4))

        assert result.times_triggered == 0
        assert len(result.trades) == 0
        assert result.pnl == Decimal("0")

    def test_bars_before_start_date_ignored(self):
        """Bars before setup.start_date are skipped for entry consideration."""
        setup = make_setup(
            entry_price=100.0,
            stop_loss_day1=95.0,
            trailing_stop_pct=5.0,
            start_date=date(2024, 1, 5),
        )

        bars = [
            # This bar would trigger entry but is before start_date
            make_bar(date(2024, 1, 2), open_=98.0, high=105.0, low=97.0, close=104.0),
            # After start_date: price below entry
            make_bar(date(2024, 1, 5), open_=99.0, high=99.5, low=98.0, close=99.0),
            make_bar(date(2024, 1, 8), open_=99.0, high=99.5, low=98.0, close=99.0),
        ]

        result = simulate_setup(setup, bars, end_date=date(2024, 1, 8))

        assert result.times_triggered == 0
        assert len(result.trades) == 0

    def test_shares_calculated_correctly_from_position_size(self):
        """shares = int(POSITION_SIZE / fill_price)."""
        setup = make_setup(entry_price=50.0, stop_loss_day1=45.0, trailing_stop_pct=5.0)

        bars = [
            make_bar(date(2024, 1, 2), open_=49.0, high=51.0, low=48.0, close=50.5),
            make_bar(date(2024, 1, 3), open_=50.5, high=51.0, low=49.0, close=51.0),
        ]

        result = simulate_setup(setup, bars, end_date=date(2024, 1, 3))

        assert len(result.trades) == 1
        # int(1000 / 50.0) = 20
        assert result.trades[0].shares == int(POSITION_SIZE / Decimal("50.0"))


class TestSimulateSetupDay1Stop:
    """Day-1 stop: price hits day-1 stop on entry day → closed at stop."""

    def test_day1_stop_triggered_same_bar_as_entry(self):
        """When entry bar low <= stop_loss_day1, trade closes at stop price."""
        setup = make_setup(entry_price=100.0, stop_loss_day1=95.0, trailing_stop_pct=5.0)

        bars = [
            # Entry bar: high reaches entry, low pierces stop
            make_bar(date(2024, 1, 2), open_=98.0, high=101.0, low=94.0, close=97.0),
        ]

        result = simulate_setup(setup, bars, end_date=date(2024, 1, 2))

        assert len(result.trades) == 1
        trade = result.trades[0]
        assert trade.entry_date == date(2024, 1, 2)
        assert trade.exit_date == date(2024, 1, 2)
        assert trade.entry_price == Decimal("100.0")
        assert trade.exit_price == Decimal("95.0")
        assert trade.exit_reason == "stop_day1"
        # P&L is negative: (95 - 100) * shares
        shares = int(POSITION_SIZE / Decimal("100.0"))
        expected_pnl = (Decimal("95.0") - Decimal("100.0")) * shares
        assert trade.pnl == expected_pnl.quantize(Decimal("0.01"))

    def test_day1_stop_at_exact_stop_level(self):
        """Day-1 stop triggers when bar.low equals stop_loss_day1 exactly."""
        setup = make_setup(entry_price=100.0, stop_loss_day1=95.0, trailing_stop_pct=5.0)

        bars = [
            make_bar(date(2024, 1, 2), open_=98.0, high=101.0, low=95.0, close=96.0),
        ]

        result = simulate_setup(setup, bars, end_date=date(2024, 1, 2))

        assert len(result.trades) == 1
        assert result.trades[0].exit_reason == "stop_day1"
        assert result.trades[0].exit_price == Decimal("95.0")

    def test_day1_no_stop_when_low_above_stop(self):
        """Position survives day 1 when bar.low > stop_loss_day1."""
        setup = make_setup(entry_price=100.0, stop_loss_day1=95.0, trailing_stop_pct=5.0)

        bars = [
            # low=96 > stop=95: survives day 1
            make_bar(date(2024, 1, 2), open_=98.0, high=101.0, low=96.0, close=100.0),
            # Day 2: close out at end
            make_bar(date(2024, 1, 3), open_=100.0, high=101.0, low=98.0, close=101.0),
        ]

        result = simulate_setup(setup, bars, end_date=date(2024, 1, 3))

        assert len(result.trades) == 1
        assert result.trades[0].exit_reason == "simulation_end"
        assert result.trades[0].exit_date == date(2024, 1, 3)


class TestSimulateSetupTrailingStop:
    """Trailing stop: price rises then drops by trailing % → closed at stop."""

    def test_trailing_stop_triggers_after_price_rise_and_fall(self):
        """Position closed via trailing stop when price drops from high."""
        # 5% trailing stop, entry at 100 → initial stop at 95
        setup = make_setup(entry_price=100.0, stop_loss_day1=94.0, trailing_stop_pct=5.0)

        bars = [
            # Day 1: entry at 100, high 102 — stop moves to 102 * 0.95 = 96.9
            make_bar(date(2024, 1, 2), open_=98.0, high=102.0, low=97.0, close=101.0),
            # Day 2: new high 110 — stop moves to 110 * 0.95 = 104.5
            make_bar(date(2024, 1, 3), open_=101.0, high=110.0, low=101.0, close=109.0),
            # Day 3: price drops to 103 — low touches below stop (104.5)
            make_bar(date(2024, 1, 4), open_=109.0, high=109.5, low=103.0, close=104.0),
        ]

        result = simulate_setup(setup, bars, end_date=date(2024, 1, 10))

        assert len(result.trades) == 1
        trade = result.trades[0]
        assert trade.exit_reason == "trailing_stop"
        assert trade.exit_date == date(2024, 1, 4)
        # Stop was at 110 * 0.95 = 104.5, open was 109 → exit at min(104.5, 109) = 104.5
        assert trade.exit_price == Decimal("104.5")
        assert trade.pnl > 0  # Profitable trade

    def test_trailing_stop_only_moves_up(self):
        """Trailing stop does not decrease when price pulls back."""
        setup = make_setup(entry_price=100.0, stop_loss_day1=94.0, trailing_stop_pct=10.0)

        bars = [
            # Day 1: entry at 100, high 110 → stop at 110 * 0.90 = 99
            make_bar(date(2024, 1, 2), open_=99.0, high=110.0, low=99.0, close=108.0),
            # Day 2: price drops to 103 (above stop 99), high stays at 110
            make_bar(date(2024, 1, 3), open_=108.0, high=110.0, low=103.0, close=105.0),
            # Day 3: price rises to 120 → stop at 120 * 0.90 = 108
            make_bar(date(2024, 1, 4), open_=105.0, high=120.0, low=104.0, close=118.0),
            # Day 4: price drops to 107 — stop was 108, triggers
            make_bar(date(2024, 1, 5), open_=118.0, high=118.5, low=107.0, close=108.0),
        ]

        result = simulate_setup(setup, bars, end_date=date(2024, 1, 10))

        assert len(result.trades) == 1
        trade = result.trades[0]
        assert trade.exit_reason == "trailing_stop"
        assert trade.exit_date == date(2024, 1, 5)
        # Stop at 108, open at 118 → exit at min(108, 118) = 108
        assert trade.exit_price == Decimal("108")


class TestSimulateSetupRetriggering:
    """Retriggering: after stop-out, price crosses entry again → new trade."""

    def test_setup_retriggered_after_day1_stop(self):
        """Setup triggers a second trade after being stopped out on day 1."""
        setup = make_setup(entry_price=100.0, stop_loss_day1=95.0, trailing_stop_pct=5.0)

        bars = [
            # Trade 1: entry + day-1 stop triggered on same bar
            make_bar(date(2024, 1, 2), open_=98.0, high=101.0, low=94.0, close=97.0),
            # Gap day: price below entry
            make_bar(date(2024, 1, 3), open_=97.0, high=99.0, low=96.0, close=98.0),
            # Trade 2: price crosses entry again
            make_bar(date(2024, 1, 4), open_=99.0, high=101.5, low=98.5, close=101.0),
            # Trade 2 continues to end
            make_bar(date(2024, 1, 5), open_=101.0, high=102.0, low=99.0, close=101.5),
        ]

        result = simulate_setup(setup, bars, end_date=date(2024, 1, 5))

        assert result.times_triggered == 2
        assert len(result.trades) == 2
        assert result.trades[0].exit_reason == "stop_day1"
        assert result.trades[1].exit_reason == "simulation_end"

    def test_setup_retriggered_after_trailing_stop(self):
        """Setup triggers a second trade after trailing stop exit."""
        setup = make_setup(entry_price=100.0, stop_loss_day1=94.0, trailing_stop_pct=5.0)

        bars = [
            # Trade 1: entry at 100
            make_bar(date(2024, 1, 2), open_=98.0, high=102.0, low=97.0, close=101.0),
            # Trade 1: high at 110 → stop at 104.5; low at 103 triggers stop
            # close must be >= low and <= high, open must be >= low; close=104.5
            make_bar(date(2024, 1, 3), open_=104.5, high=110.0, low=103.0, close=104.5),
            # Gap: price below entry
            make_bar(date(2024, 1, 4), open_=99.0, high=99.5, low=98.0, close=99.0),
            # Trade 2: price crosses entry again
            make_bar(date(2024, 1, 5), open_=99.5, high=101.0, low=99.0, close=100.5),
            # Trade 2 at end
            make_bar(date(2024, 1, 8), open_=100.5, high=101.5, low=99.5, close=101.0),
        ]

        result = simulate_setup(setup, bars, end_date=date(2024, 1, 8))

        assert result.times_triggered == 2
        assert result.trades[0].exit_reason == "trailing_stop"
        assert result.trades[1].exit_reason == "simulation_end"

    def test_multiple_retriggering_counts_all_trades(self):
        """Verify all three trades are counted when setup retriggeres twice."""
        setup = make_setup(entry_price=100.0, stop_loss_day1=95.0, trailing_stop_pct=5.0)

        bars = [
            # Trade 1: day-1 stop
            make_bar(date(2024, 1, 2), open_=98.0, high=101.0, low=94.0, close=97.0),
            # Trade 2: day-1 stop again
            make_bar(date(2024, 1, 3), open_=99.0, high=101.0, low=94.0, close=97.0),
            # Trade 3: survives to end
            make_bar(date(2024, 1, 4), open_=99.0, high=101.0, low=97.0, close=100.5),
            make_bar(date(2024, 1, 5), open_=100.5, high=101.0, low=98.0, close=101.0),
        ]

        result = simulate_setup(setup, bars, end_date=date(2024, 1, 5))

        assert result.times_triggered == 3
        assert len(result.trades) == 3


class TestSimulateSetupEndOfSim:
    """End-of-sim close: open position at end date → closed at last close."""

    def test_open_position_closed_at_last_bar_close(self):
        """Position still open at end is closed at last bar's close price."""
        setup = make_setup(entry_price=100.0, stop_loss_day1=95.0, trailing_stop_pct=5.0)

        bars = [
            make_bar(date(2024, 1, 2), open_=98.0, high=101.0, low=97.0, close=100.5),
            make_bar(date(2024, 1, 3), open_=100.5, high=102.0, low=99.5, close=101.8),
            # high must be >= close (105.0), so high=105.0
            make_bar(date(2024, 1, 4), open_=101.8, high=105.0, low=100.0, close=105.0),
        ]

        result = simulate_setup(setup, bars, end_date=date(2024, 1, 4))

        assert len(result.trades) == 1
        trade = result.trades[0]
        assert trade.exit_reason == "simulation_end"
        assert trade.exit_date == date(2024, 1, 4)
        assert trade.exit_price == Decimal("105.0")  # last bar close

    def test_pnl_correct_for_profitable_end_of_sim_close(self):
        """P&L is positive when exit price > entry price at simulation end."""
        setup = make_setup(entry_price=100.0, stop_loss_day1=95.0, trailing_stop_pct=5.0)

        bars = [
            # Entry at 100, close at 110 at end
            make_bar(date(2024, 1, 2), open_=98.0, high=101.0, low=97.0, close=101.0),
            make_bar(date(2024, 1, 3), open_=101.0, high=112.0, low=100.0, close=110.0),
        ]

        result = simulate_setup(setup, bars, end_date=date(2024, 1, 3))

        shares = int(POSITION_SIZE / Decimal("100.0"))
        expected_pnl = (Decimal("110.0") - Decimal("100.0")) * shares
        assert result.trades[0].pnl == expected_pnl.quantize(Decimal("0.01"))
        assert result.pnl > 0


class TestSimulateSetupGapUp:
    """Gap-up entry: bar opens above entry → fill at open price."""

    def test_gap_up_entry_fills_at_open_not_entry(self):
        """When bar.open >= entry_price, fill price is bar.open."""
        setup = make_setup(entry_price=100.0, stop_loss_day1=95.0, trailing_stop_pct=5.0)

        bars = [
            # Gap-up: opens at 105 (above entry 100), no day-1 stop
            make_bar(date(2024, 1, 2), open_=105.0, high=108.0, low=104.0, close=106.0),
            make_bar(date(2024, 1, 3), open_=106.0, high=107.0, low=104.5, close=106.5),
        ]

        result = simulate_setup(setup, bars, end_date=date(2024, 1, 3))

        assert len(result.trades) == 1
        trade = result.trades[0]
        # Fill at open, not entry_price
        assert trade.entry_price == Decimal("105.0")

    def test_gap_up_shares_based_on_open_price(self):
        """Shares are calculated using the actual fill price (open), not entry."""
        setup = make_setup(entry_price=100.0, stop_loss_day1=95.0, trailing_stop_pct=5.0)

        bars = [
            make_bar(date(2024, 1, 2), open_=105.0, high=108.0, low=104.0, close=106.0),
            make_bar(date(2024, 1, 3), open_=106.0, high=107.0, low=104.5, close=106.5),
        ]

        result = simulate_setup(setup, bars, end_date=date(2024, 1, 3))

        # int(1000 / 105) = 9
        assert result.trades[0].shares == int(POSITION_SIZE / Decimal("105.0"))


class TestSimulateSetupGapDownExit:
    """Gap-down trailing stop exit: bar opens below trailing stop → exit at open."""

    def test_gap_down_exits_at_open_not_stop_price(self):
        """When bar.open < trailing stop price, exit is at open (not stop)."""
        # 5% trailing stop, entry at 100 → initial stop 95
        setup = make_setup(entry_price=100.0, stop_loss_day1=94.0, trailing_stop_pct=5.0)

        bars = [
            # Day 1: entry at 100, high 110 → stop at 104.5
            make_bar(date(2024, 1, 2), open_=99.0, high=110.0, low=99.0, close=108.0),
            # Day 2: gaps DOWN to 100, opens far below stop (104.5) → exit at open
            make_bar(date(2024, 1, 3), open_=100.0, high=101.0, low=99.0, close=100.5),
        ]

        result = simulate_setup(setup, bars, end_date=date(2024, 1, 10))

        assert len(result.trades) == 1
        trade = result.trades[0]
        assert trade.exit_reason == "trailing_stop"
        # open (100) < stop (104.5) → exit at open
        assert trade.exit_price == Decimal("100.0")
        # P&L is (100 - 100) * shares = 0 — break-even in this case
        # but entry was at 100, exit at 100 → pnl = 0
        assert trade.pnl == Decimal("0.00")

    def test_gap_down_exit_price_is_min_of_stop_and_open(self):
        """exit_price = min(trigger_price, bar.open) convention."""
        setup = make_setup(entry_price=100.0, stop_loss_day1=93.0, trailing_stop_pct=5.0)

        bars = [
            # Day 1: entry at 100, high=120 → stop at 120 * 0.95 = 114
            make_bar(date(2024, 1, 2), open_=98.0, high=120.0, low=97.0, close=118.0),
            # Day 2: open at 110 (below stop 114) → exit at 110
            make_bar(date(2024, 1, 3), open_=110.0, high=112.0, low=109.0, close=111.0),
        ]

        result = simulate_setup(setup, bars, end_date=date(2024, 1, 10))

        assert len(result.trades) == 1
        trade = result.trades[0]
        assert trade.exit_price == Decimal("110.0")  # open, not stop (114)
        assert trade.exit_reason == "trailing_stop"


class TestSimulateSetupMultipleTrades:
    """Multiple trades on same setup — verify all trades tracked."""

    def test_pnl_is_sum_of_all_trades(self):
        """SetupResult.pnl equals the sum of all individual trade P&Ls."""
        setup = make_setup(entry_price=100.0, stop_loss_day1=95.0, trailing_stop_pct=5.0)

        bars = [
            # Trade 1: day-1 stop → loss
            make_bar(date(2024, 1, 2), open_=98.0, high=101.0, low=94.0, close=97.0),
            # Trade 2: survives to end → profit
            make_bar(date(2024, 1, 3), open_=99.0, high=101.0, low=97.0, close=100.5),
            make_bar(date(2024, 1, 4), open_=100.5, high=110.0, low=100.0, close=108.0),
        ]

        result = simulate_setup(setup, bars, end_date=date(2024, 1, 4))

        assert len(result.trades) == 2
        expected_pnl = sum(t.pnl for t in result.trades)
        assert result.pnl == expected_pnl

    def test_times_triggered_equals_trade_count(self):
        """times_triggered always equals len(trades)."""
        setup = make_setup(entry_price=100.0, stop_loss_day1=95.0, trailing_stop_pct=5.0)

        bars = [
            make_bar(date(2024, 1, 2), open_=98.0, high=101.0, low=94.0, close=97.0),
            make_bar(date(2024, 1, 3), open_=99.0, high=101.0, low=94.0, close=97.0),
            make_bar(date(2024, 1, 4), open_=99.0, high=101.0, low=97.0, close=100.5),
        ]

        result = simulate_setup(setup, bars, end_date=date(2024, 1, 4))

        assert result.times_triggered == len(result.trades)

    def test_zero_position_size_skip_when_price_too_high(self):
        """Setup with entry price > POSITION_SIZE yields 0 shares — bars skipped."""
        # POSITION_SIZE is $1000; entry at $1500 → int(1000/1500) = 0 → skip
        setup = make_setup(
            entry_price=1500.0,
            stop_loss_day1=1400.0,
            trailing_stop_pct=5.0,
        )

        bars = [
            make_bar(date(2024, 1, 2), open_=1490.0, high=1510.0, low=1480.0, close=1505.0),
            make_bar(date(2024, 1, 3), open_=1505.0, high=1510.0, low=1495.0, close=1508.0),
        ]

        result = simulate_setup(setup, bars, end_date=date(2024, 1, 3))

        assert result.times_triggered == 0
        assert len(result.trades) == 0


# ---------------------------------------------------------------------------
# run_simulation() tests
# ---------------------------------------------------------------------------


class TestRunSimulationAggregation:
    """Aggregation: multiple setups, verify totals."""

    def _make_setup_result(
        self,
        symbol: str,
        trades: list[TradeResult],
    ) -> SetupResult:
        return SetupResult(
            symbol=symbol,
            entry_price=Decimal("100"),
            stop_loss_day1=Decimal("95"),
            trailing_stop_pct=Decimal("5"),
            start_date=date(2024, 1, 1),
            times_triggered=len(trades),
            pnl=sum(t.pnl for t in trades),
            trades=trades,
        )

    def _make_trade(
        self,
        entry_price: float,
        exit_price: float,
        shares: int,
        exit_reason: str = "trailing_stop",
    ) -> TradeResult:
        ep = Decimal(str(entry_price))
        xp = Decimal(str(exit_price))
        pnl = (xp - ep) * shares
        return_pct = ((xp - ep) / ep * 100).quantize(Decimal("0.01"))
        return TradeResult(
            entry_date=date(2024, 1, 2),
            entry_price=ep,
            exit_date=date(2024, 1, 5),
            exit_price=xp,
            shares=shares,
            pnl=pnl.quantize(Decimal("0.01")),
            return_pct=return_pct,
            exit_reason=exit_reason,
        )

    def test_total_trades_sums_across_setups(self):
        """total_trades equals sum of all trades from all setups."""
        setup1_trades = [self._make_trade(100.0, 110.0, 9)]
        setup2_trades = [
            self._make_trade(50.0, 55.0, 18),
            self._make_trade(50.0, 48.0, 18),
        ]
        results = [
            self._make_setup_result("AAPL", setup1_trades),
            self._make_setup_result("MSFT", setup2_trades),
        ]

        response = run_simulation(results)

        assert response.summary.total_trades == 3

    def test_total_pnl_sums_across_setups(self):
        """total_pnl equals sum of P&L across all setups."""
        # Trade 1: entry 100, exit 110, 9 shares → pnl = 90
        # Trade 2: entry 100, exit 90, 10 shares → pnl = -100
        t1 = self._make_trade(100.0, 110.0, 9)
        t2 = self._make_trade(100.0, 90.0, 10)
        results = [
            self._make_setup_result("AAPL", [t1]),
            self._make_setup_result("MSFT", [t2]),
        ]

        response = run_simulation(results)

        expected = t1.pnl + t2.pnl
        assert response.summary.total_pnl == expected.quantize(Decimal("0.01"))

    def test_winning_and_losing_trades_counted_correctly(self):
        """winning_trades and losing_trades split on pnl > 0 vs pnl <= 0."""
        t_win = self._make_trade(100.0, 120.0, 9)   # pnl > 0
        t_loss = self._make_trade(100.0, 90.0, 9)   # pnl < 0
        t_breakeven = self._make_trade(100.0, 100.0, 9)  # pnl == 0 → loser

        results = [self._make_setup_result("AAPL", [t_win, t_loss, t_breakeven])]

        response = run_simulation(results)

        assert response.summary.winning_trades == 1
        assert response.summary.losing_trades == 2


class TestRunSimulationWinRate:
    """Win rate: mix of winners and losers."""

    def _make_trade(self, entry: float, exit_: float, shares: int) -> TradeResult:
        ep, xp = Decimal(str(entry)), Decimal(str(exit_))
        pnl = (xp - ep) * shares
        return TradeResult(
            entry_date=date(2024, 1, 2),
            entry_price=ep,
            exit_date=date(2024, 1, 5),
            exit_price=xp,
            shares=shares,
            pnl=pnl.quantize(Decimal("0.01")),
            return_pct=((xp - ep) / ep * 100).quantize(Decimal("0.01")),
            exit_reason="trailing_stop",
        )

    def test_win_rate_is_none_when_zero_trades(self):
        """win_rate is None when total_trades == 0."""
        results = [
            SetupResult(
                symbol="AAPL",
                entry_price=Decimal("100"),
                stop_loss_day1=Decimal("95"),
                trailing_stop_pct=Decimal("5"),
                start_date=date(2024, 1, 1),
                times_triggered=0,
                pnl=Decimal("0"),
                trades=[],
            )
        ]

        response = run_simulation(results)

        assert response.summary.win_rate is None
        assert response.summary.avg_gain is None
        assert response.summary.avg_loss is None

    def test_win_rate_100_pct_when_all_winners(self):
        """100% win rate when all trades are profitable."""
        trades = [self._make_trade(100.0, 110.0, 9) for _ in range(3)]
        results = [
            SetupResult(
                symbol="AAPL",
                entry_price=Decimal("100"),
                stop_loss_day1=Decimal("95"),
                trailing_stop_pct=Decimal("5"),
                start_date=date(2024, 1, 1),
                times_triggered=3,
                pnl=sum(t.pnl for t in trades),
                trades=trades,
            )
        ]

        response = run_simulation(results)

        assert response.summary.win_rate == Decimal("100.00")
        assert response.summary.avg_loss is None

    def test_win_rate_50_pct_with_two_wins_two_losses(self):
        """50% win rate with 2 winners and 2 losers."""
        trades = [
            self._make_trade(100.0, 110.0, 9),
            self._make_trade(100.0, 110.0, 9),
            self._make_trade(100.0, 90.0, 9),
            self._make_trade(100.0, 90.0, 9),
        ]
        results = [
            SetupResult(
                symbol="AAPL",
                entry_price=Decimal("100"),
                stop_loss_day1=Decimal("95"),
                trailing_stop_pct=Decimal("5"),
                start_date=date(2024, 1, 1),
                times_triggered=4,
                pnl=sum(t.pnl for t in trades),
                trades=trades,
            )
        ]

        response = run_simulation(results)

        assert response.summary.win_rate == Decimal("50.00")

    def test_avg_gain_and_avg_loss_computed_correctly(self):
        """avg_gain and avg_loss are averages of winning/losing trade P&Ls."""
        t_win1 = self._make_trade(100.0, 120.0, 9)   # pnl = 180
        t_win2 = self._make_trade(100.0, 110.0, 9)   # pnl = 90
        t_loss = self._make_trade(100.0, 90.0, 9)    # pnl = -90

        results = [
            SetupResult(
                symbol="AAPL",
                entry_price=Decimal("100"),
                stop_loss_day1=Decimal("95"),
                trailing_stop_pct=Decimal("5"),
                start_date=date(2024, 1, 1),
                times_triggered=3,
                pnl=t_win1.pnl + t_win2.pnl + t_loss.pnl,
                trades=[t_win1, t_win2, t_loss],
            )
        ]

        response = run_simulation(results)

        expected_avg_gain = ((t_win1.pnl + t_win2.pnl) / 2).quantize(Decimal("0.01"))
        expected_avg_loss = t_loss.pnl.quantize(Decimal("0.01"))

        assert response.summary.avg_gain == expected_avg_gain
        assert response.summary.avg_loss == expected_avg_loss


class TestRunSimulationZeroTrades:
    """Zero trades: no entries triggered, all metrics handle gracefully."""

    def test_zero_trades_all_metrics_are_zero_or_none(self):
        """With no trades, totals are 0 and rate/avg fields are None."""
        results = [
            SetupResult(
                symbol="AAPL",
                entry_price=Decimal("100"),
                stop_loss_day1=Decimal("95"),
                trailing_stop_pct=Decimal("5"),
                start_date=date(2024, 1, 1),
                times_triggered=0,
                pnl=Decimal("0"),
                trades=[],
            ),
            SetupResult(
                symbol="MSFT",
                entry_price=Decimal("200"),
                stop_loss_day1=Decimal("190"),
                trailing_stop_pct=Decimal("5"),
                start_date=date(2024, 1, 1),
                times_triggered=0,
                pnl=Decimal("0"),
                trades=[],
            ),
        ]

        response = run_simulation(results)

        summary = response.summary
        assert summary.total_trades == 0
        assert summary.winning_trades == 0
        assert summary.losing_trades == 0
        assert summary.total_pnl == Decimal("0.00")
        assert summary.total_pnl_pct == Decimal("0")
        assert summary.total_capital_deployed == Decimal("0.00")
        assert summary.win_rate is None
        assert summary.avg_gain is None
        assert summary.avg_loss is None

    def test_position_size_always_reported(self):
        """position_size is always POSITION_SIZE regardless of trade count."""
        results = [
            SetupResult(
                symbol="AAPL",
                entry_price=Decimal("100"),
                stop_loss_day1=Decimal("95"),
                trailing_stop_pct=Decimal("5"),
                start_date=date(2024, 1, 1),
                times_triggered=0,
                pnl=Decimal("0"),
                trades=[],
            )
        ]

        response = run_simulation(results)

        assert response.summary.position_size == POSITION_SIZE


class TestRunSimulationCapitalDeployed:
    """Capital deployed: equals sum of (entry_price * shares) across all trades."""

    def _make_trade(self, entry_price: float, shares: int) -> TradeResult:
        ep = Decimal(str(entry_price))
        xp = ep * Decimal("1.05")  # 5% gain
        pnl = (xp - ep) * shares
        return TradeResult(
            entry_date=date(2024, 1, 2),
            entry_price=ep,
            exit_date=date(2024, 1, 5),
            exit_price=xp,
            shares=shares,
            pnl=pnl.quantize(Decimal("0.01")),
            return_pct=Decimal("5.00"),
            exit_reason="trailing_stop",
        )

    def test_capital_deployed_equals_entry_times_shares_not_position_size(self):
        """total_capital_deployed = sum(entry_price * shares), not POSITION_SIZE * N."""
        # entry at $105, shares = int(1000/105) = 9
        # actual capital = 9 * 105 = 945 (not 1000)
        t1 = self._make_trade(entry_price=105.0, shares=9)
        # entry at $50, shares = int(1000/50) = 20
        # actual capital = 20 * 50 = 1000
        t2 = self._make_trade(entry_price=50.0, shares=20)

        results = [
            SetupResult(
                symbol="AAPL",
                entry_price=Decimal("105"),
                stop_loss_day1=Decimal("99"),
                trailing_stop_pct=Decimal("5"),
                start_date=date(2024, 1, 1),
                times_triggered=1,
                pnl=t1.pnl,
                trades=[t1],
            ),
            SetupResult(
                symbol="MSFT",
                entry_price=Decimal("50"),
                stop_loss_day1=Decimal("47"),
                trailing_stop_pct=Decimal("5"),
                start_date=date(2024, 1, 1),
                times_triggered=1,
                pnl=t2.pnl,
                trades=[t2],
            ),
        ]

        response = run_simulation(results)

        expected_capital = (
            Decimal("9") * Decimal("105.0") + Decimal("20") * Decimal("50.0")
        ).quantize(Decimal("0.01"))
        assert response.summary.total_capital_deployed == expected_capital

    def test_total_pnl_pct_uses_actual_capital_not_position_size(self):
        """total_pnl_pct = total_pnl / total_capital_deployed * 100."""
        # 9 shares at $105 = $945 capital deployed
        # exit at $115.50 → pnl = 9 * 10.50 = 94.50
        # expected pnl_pct = 94.50 / 945 * 100 = 10.00%
        ep = Decimal("105.0")
        xp = Decimal("115.5")
        shares = 9
        pnl = (xp - ep) * shares  # 94.50
        trade = TradeResult(
            entry_date=date(2024, 1, 2),
            entry_price=ep,
            exit_date=date(2024, 1, 5),
            exit_price=xp,
            shares=shares,
            pnl=pnl.quantize(Decimal("0.01")),
            return_pct=Decimal("10.00"),
            exit_reason="trailing_stop",
        )
        results = [
            SetupResult(
                symbol="AAPL",
                entry_price=ep,
                stop_loss_day1=Decimal("99"),
                trailing_stop_pct=Decimal("5"),
                start_date=date(2024, 1, 1),
                times_triggered=1,
                pnl=trade.pnl,
                trades=[trade],
            )
        ]

        response = run_simulation(results)

        capital = (ep * shares).quantize(Decimal("0.01"))  # 945.00
        expected_pct = (pnl / capital * 100).quantize(Decimal("0.01"))
        assert response.summary.total_pnl_pct == expected_pct


class TestRunSimulationResponseStructure:
    """Verify response contains all required fields."""

    def test_response_contains_setups(self):
        """Response includes original setup results in setups field."""
        setup_result = SetupResult(
            symbol="AAPL",
            entry_price=Decimal("100"),
            stop_loss_day1=Decimal("95"),
            trailing_stop_pct=Decimal("5"),
            start_date=date(2024, 1, 1),
            times_triggered=0,
            pnl=Decimal("0"),
            trades=[],
        )

        response = run_simulation([setup_result])

        assert len(response.setups) == 1
        assert response.setups[0].symbol == "AAPL"

    def test_summary_position_size_is_1000(self):
        """Summary always reports position_size = 1000."""
        response = run_simulation([
            SetupResult(
                symbol="AAPL",
                entry_price=Decimal("100"),
                stop_loss_day1=Decimal("95"),
                trailing_stop_pct=Decimal("5"),
                start_date=date(2024, 1, 1),
                times_triggered=0,
                pnl=Decimal("0"),
                trades=[],
            )
        ])

        assert response.summary.position_size == Decimal("1000")
