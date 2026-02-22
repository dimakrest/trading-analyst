"""Unit tests for compute_simulation_analytics().

Tests use lightweight dataclass stand-ins for the ORM models — no DB required.
"""
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

import pytest

from app.services.arena.analytics import compute_simulation_analytics


# ---------------------------------------------------------------------------
# Minimal stand-ins for ORM models (no DB needed)
# ---------------------------------------------------------------------------


@dataclass
class FakeSimulation:
    """Minimal ArenaSimulation substitute."""
    avg_hold_days: Decimal | None = None
    avg_win_pnl: Decimal | None = None
    avg_loss_pnl: Decimal | None = None
    profit_factor: Decimal | None = None
    sharpe_ratio: Decimal | None = None
    total_realized_pnl: Decimal | None = None


@dataclass
class FakePosition:
    """Minimal ArenaPosition substitute."""
    realized_pnl: Decimal | None
    entry_date: date | None = None
    exit_date: date | None = None


@dataclass
class FakeSnapshot:
    """Minimal ArenaSnapshot substitute."""
    snapshot_date: date
    daily_return_pct: Decimal
    day_number: int = 0


# ---------------------------------------------------------------------------
# Helper factories
# ---------------------------------------------------------------------------


def make_position(
    pnl: float,
    entry: date | None = None,
    exit_: date | None = None,
) -> FakePosition:
    return FakePosition(
        realized_pnl=Decimal(str(pnl)) if pnl is not None else None,
        entry_date=entry,
        exit_date=exit_,
    )


def make_snapshot(snapshot_date: date, daily_return_pct: float) -> FakeSnapshot:
    return FakeSnapshot(
        snapshot_date=snapshot_date,
        daily_return_pct=Decimal(str(daily_return_pct)),
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestNoClosedPositions:
    """When no positions have a realized_pnl, all metrics stay None."""

    @pytest.mark.unit
    def test_open_positions_leave_all_metrics_none(self) -> None:
        sim = FakeSimulation()
        positions = [FakePosition(realized_pnl=None)]
        snapshots = [make_snapshot(date(2025, 1, 2), 0.5)]

        compute_simulation_analytics(sim, positions, snapshots)

        assert sim.total_realized_pnl is None
        assert sim.avg_hold_days is None
        assert sim.avg_win_pnl is None
        assert sim.avg_loss_pnl is None
        assert sim.profit_factor is None
        assert sim.sharpe_ratio is None

    @pytest.mark.unit
    def test_empty_positions_leave_all_metrics_none(self) -> None:
        sim = FakeSimulation()
        snapshots = [make_snapshot(date(2025, 1, 2), 0.5)]

        compute_simulation_analytics(sim, [], snapshots)

        assert sim.total_realized_pnl is None


class TestAllWinners:
    """When every trade is profitable, avg_loss_pnl and profit_factor stay None."""

    @pytest.mark.unit
    def test_avg_loss_pnl_is_none(self) -> None:
        sim = FakeSimulation()
        positions = [make_position(100.0), make_position(200.0)]
        snapshots = [
            make_snapshot(date(2025, 1, 2), 1.0),
            make_snapshot(date(2025, 1, 3), 2.0),
        ]

        compute_simulation_analytics(sim, positions, snapshots)

        assert sim.avg_loss_pnl is None

    @pytest.mark.unit
    def test_profit_factor_is_none_when_no_losses(self) -> None:
        sim = FakeSimulation()
        positions = [make_position(100.0)]
        snapshots = [
            make_snapshot(date(2025, 1, 2), 0.5),
            make_snapshot(date(2025, 1, 3), 0.5),
        ]

        compute_simulation_analytics(sim, positions, snapshots)

        assert sim.profit_factor is None

    @pytest.mark.unit
    def test_avg_win_pnl_computed_correctly(self) -> None:
        sim = FakeSimulation()
        positions = [make_position(100.0), make_position(300.0)]
        snapshots = [
            make_snapshot(date(2025, 1, 2), 1.0),
            make_snapshot(date(2025, 1, 3), 2.0),
        ]

        compute_simulation_analytics(sim, positions, snapshots)

        assert sim.avg_win_pnl == Decimal("200.00")


class TestAllLosers:
    """When every trade loses money, avg_win_pnl and profit_factor stay None."""

    @pytest.mark.unit
    def test_avg_win_pnl_is_none(self) -> None:
        sim = FakeSimulation()
        positions = [make_position(-50.0), make_position(-150.0)]
        snapshots = [
            make_snapshot(date(2025, 1, 2), -0.5),
            make_snapshot(date(2025, 1, 3), -1.5),
        ]

        compute_simulation_analytics(sim, positions, snapshots)

        assert sim.avg_win_pnl is None

    @pytest.mark.unit
    def test_profit_factor_is_none_when_no_wins(self) -> None:
        sim = FakeSimulation()
        positions = [make_position(-100.0)]
        snapshots = [
            make_snapshot(date(2025, 1, 2), -1.0),
            make_snapshot(date(2025, 1, 3), -1.0),
        ]

        compute_simulation_analytics(sim, positions, snapshots)

        assert sim.profit_factor is None

    @pytest.mark.unit
    def test_avg_loss_pnl_computed_correctly(self) -> None:
        sim = FakeSimulation()
        positions = [make_position(-100.0), make_position(-300.0)]
        snapshots = [
            make_snapshot(date(2025, 1, 2), -1.0),
            make_snapshot(date(2025, 1, 3), -2.0),
        ]

        compute_simulation_analytics(sim, positions, snapshots)

        assert sim.avg_loss_pnl == Decimal("-200.00")


class TestMixedTrades:
    """Mixed wins and losses: all metrics computed."""

    @pytest.mark.unit
    def test_all_metrics_computed(self) -> None:
        sim = FakeSimulation()
        # 2 winners (+100, +300), 1 loser (-200)
        positions = [
            make_position(100.0),
            make_position(300.0),
            make_position(-200.0),
        ]
        snapshots = [
            make_snapshot(date(2025, 1, 2), 1.0),
            make_snapshot(date(2025, 1, 3), -0.5),
            make_snapshot(date(2025, 1, 6), 2.0),
        ]

        compute_simulation_analytics(sim, positions, snapshots)

        assert sim.total_realized_pnl == Decimal("200.00")
        assert sim.avg_win_pnl == Decimal("200.00")
        assert sim.avg_loss_pnl == Decimal("-200.00")
        # profit_factor = 400 / 200 = 2.0
        assert sim.profit_factor == Decimal("2.0")
        # sharpe_ratio is set (not None) when std_dev > 0
        assert sim.sharpe_ratio is not None

    @pytest.mark.unit
    def test_profit_factor_calculation(self) -> None:
        sim = FakeSimulation()
        # gross wins = 600, gross losses = 200 → profit factor = 3.0
        positions = [
            make_position(200.0),
            make_position(400.0),
            make_position(-200.0),
        ]
        snapshots = [
            make_snapshot(date(2025, 1, 2), 1.0),
            make_snapshot(date(2025, 1, 3), 2.0),
        ]

        compute_simulation_analytics(sim, positions, snapshots)

        assert sim.profit_factor == Decimal("3.0")


class TestSingleTrade:
    """Single closed trade: averages equal to that trade's values."""

    @pytest.mark.unit
    def test_single_winner_averages(self) -> None:
        sim = FakeSimulation()
        positions = [make_position(150.0)]
        snapshots = [
            make_snapshot(date(2025, 1, 2), 1.5),
            make_snapshot(date(2025, 1, 3), 0.5),
        ]

        compute_simulation_analytics(sim, positions, snapshots)

        assert sim.total_realized_pnl == Decimal("150.00")
        assert sim.avg_win_pnl == Decimal("150.00")
        assert sim.avg_loss_pnl is None

    @pytest.mark.unit
    def test_single_loser_averages(self) -> None:
        sim = FakeSimulation()
        positions = [make_position(-75.0)]
        snapshots = [
            make_snapshot(date(2025, 1, 2), -0.75),
            make_snapshot(date(2025, 1, 3), -0.25),
        ]

        compute_simulation_analytics(sim, positions, snapshots)

        assert sim.total_realized_pnl == Decimal("-75.00")
        assert sim.avg_loss_pnl == Decimal("-75.00")
        assert sim.avg_win_pnl is None


class TestSharpeEdgeCases:
    """Sharpe ratio edge cases."""

    @pytest.mark.unit
    def test_single_snapshot_sharpe_is_none(self) -> None:
        """N-1 denominator requires at least 2 data points."""
        sim = FakeSimulation()
        positions = [make_position(100.0)]
        snapshots = [make_snapshot(date(2025, 1, 2), 1.0)]

        compute_simulation_analytics(sim, positions, snapshots)

        assert sim.sharpe_ratio is None

    @pytest.mark.unit
    def test_zero_variance_sharpe_is_none(self) -> None:
        """All identical daily returns → std_dev == 0 → Sharpe is None."""
        sim = FakeSimulation()
        positions = [make_position(100.0)]
        snapshots = [
            make_snapshot(date(2025, 1, 2), 1.0),
            make_snapshot(date(2025, 1, 3), 1.0),
            make_snapshot(date(2025, 1, 6), 1.0),
        ]

        compute_simulation_analytics(sim, positions, snapshots)

        assert sim.sharpe_ratio is None

    @pytest.mark.unit
    def test_negative_sharpe_for_all_negative_returns(self) -> None:
        """All negative daily returns → negative mean → negative Sharpe."""
        sim = FakeSimulation()
        positions = [make_position(-100.0)]
        snapshots = [
            make_snapshot(date(2025, 1, 2), -1.0),
            make_snapshot(date(2025, 1, 3), -2.0),
            make_snapshot(date(2025, 1, 6), -1.5),
        ]

        compute_simulation_analytics(sim, positions, snapshots)

        assert sim.sharpe_ratio is not None
        assert sim.sharpe_ratio < 0

    @pytest.mark.unit
    def test_positive_sharpe_for_positive_returns(self) -> None:
        """Positive daily returns → positive Sharpe."""
        sim = FakeSimulation()
        positions = [make_position(200.0)]
        snapshots = [
            make_snapshot(date(2025, 1, 2), 1.0),
            make_snapshot(date(2025, 1, 3), 2.0),
            make_snapshot(date(2025, 1, 6), 1.5),
        ]

        compute_simulation_analytics(sim, positions, snapshots)

        assert sim.sharpe_ratio is not None
        assert sim.sharpe_ratio > 0

    @pytest.mark.unit
    def test_sharpe_ratio_exact_value(self) -> None:
        """Sharpe ratio matches hand-calculated expected value.

        Verifies the annualization factor (sqrt(252)) and quantization (0.0001)
        are applied correctly so a scaling error would be caught.

        Input:
            daily_return_pct = [1.00, 2.00, 3.00] (as percentages stored in DB)
        Calculation:
            daily_returns = [0.01, 0.02, 0.03]
            mean = 0.02, std_dev = 0.01
            sharpe = (0.02 / 0.01) * sqrt(252) = 2 * 15.8745... = 31.7490...
        """
        sim = FakeSimulation()
        positions = [FakePosition(realized_pnl=Decimal("100"))]
        snapshots = [
            FakeSnapshot(
                snapshot_date=date(2024, 1, 3),
                daily_return_pct=Decimal("1.00"),
                day_number=1,
            ),
            FakeSnapshot(
                snapshot_date=date(2024, 1, 4),
                daily_return_pct=Decimal("2.00"),
                day_number=2,
            ),
            FakeSnapshot(
                snapshot_date=date(2024, 1, 5),
                daily_return_pct=Decimal("3.00"),
                day_number=3,
            ),
        ]

        compute_simulation_analytics(sim, positions, snapshots)

        assert sim.sharpe_ratio == Decimal("31.7490")


class TestHoldTimeCalculation:
    """Average hold duration calculated from trading days in snapshots."""

    @pytest.mark.unit
    def test_single_day_hold(self) -> None:
        """Position opened and closed on the same day = 1 trading day."""
        sim = FakeSimulation()
        d = date(2025, 1, 2)
        positions = [make_position(50.0, entry=d, exit_=d)]
        snapshots = [
            make_snapshot(d, 0.5),
            make_snapshot(date(2025, 1, 3), 0.0),
        ]

        compute_simulation_analytics(sim, positions, snapshots)

        assert sim.avg_hold_days == Decimal("1")

    @pytest.mark.unit
    def test_multi_day_hold(self) -> None:
        """Position spanning 3 trading days → avg_hold_days == 3."""
        sim = FakeSimulation()
        d1 = date(2025, 1, 2)
        d2 = date(2025, 1, 3)
        d3 = date(2025, 1, 6)
        positions = [make_position(100.0, entry=d1, exit_=d3)]
        snapshots = [
            make_snapshot(d1, 0.5),
            make_snapshot(d2, 0.3),
            make_snapshot(d3, 0.2),
        ]

        compute_simulation_analytics(sim, positions, snapshots)

        assert sim.avg_hold_days == Decimal("3")

    @pytest.mark.unit
    def test_average_hold_across_multiple_positions(self) -> None:
        """Average of 1-day and 3-day hold = 2 trading days."""
        sim = FakeSimulation()
        d1 = date(2025, 1, 2)
        d2 = date(2025, 1, 3)
        d3 = date(2025, 1, 6)
        d4 = date(2025, 1, 7)
        # pos1: held d1 only (1 day), pos2: held d2..d4 (3 days)
        positions = [
            make_position(50.0, entry=d1, exit_=d1),
            make_position(50.0, entry=d2, exit_=d4),
        ]
        snapshots = [
            make_snapshot(d1, 0.1),
            make_snapshot(d2, 0.2),
            make_snapshot(d3, 0.3),
            make_snapshot(d4, 0.4),
        ]

        compute_simulation_analytics(sim, positions, snapshots)

        # (1 + 3) / 2 = 2
        assert sim.avg_hold_days == Decimal("2")

    @pytest.mark.unit
    def test_hold_days_none_when_missing_entry_exit_dates(self) -> None:
        """Positions without entry/exit dates are skipped; avg_hold_days stays None."""
        sim = FakeSimulation()
        positions = [make_position(100.0, entry=None, exit_=None)]
        snapshots = [
            make_snapshot(date(2025, 1, 2), 1.0),
            make_snapshot(date(2025, 1, 3), 1.0),
        ]

        compute_simulation_analytics(sim, positions, snapshots)

        assert sim.avg_hold_days is None
