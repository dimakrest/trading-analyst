"""Analytics computation for arena simulations.

This module provides pure-function analytics computation that is called
at simulation finalization to populate performance metrics.
"""
from decimal import Decimal

from app.models.arena import ArenaPosition, ArenaSimulation, ArenaSnapshot


def compute_simulation_analytics(
    simulation: ArenaSimulation,
    positions: list[ArenaPosition],
    snapshots: list[ArenaSnapshot],
) -> None:
    """Compute and set analytics metrics on the simulation object.

    Mutates simulation in-place. Called after all positions are closed.

    Args:
        simulation: ArenaSimulation to update with computed metrics.
        positions: All positions (open and closed) for the simulation.
        snapshots: All daily snapshots ordered by day number.
    """
    closed = [p for p in positions if p.realized_pnl is not None]
    if not closed:
        return

    # Total realized P&L
    simulation.total_realized_pnl = sum(p.realized_pnl for p in closed)

    # Average hold time in actual trading days.
    # Each snapshot represents one trading day, so we count snapshots whose date
    # falls within [entry_date, exit_date] — no external calendar library needed.
    trading_day_set = {s.snapshot_date for s in snapshots}
    hold_days = [
        sum(1 for d in trading_day_set if p.entry_date <= d <= p.exit_date)
        for p in closed
        if p.entry_date and p.exit_date
    ]
    if hold_days:
        simulation.avg_hold_days = Decimal(sum(hold_days)) / len(hold_days)

    # Separate winners and losers
    winners = [p for p in closed if p.realized_pnl > 0]
    losers = [p for p in closed if p.realized_pnl < 0]

    # Average win / average loss
    if winners:
        simulation.avg_win_pnl = sum(p.realized_pnl for p in winners) / len(winners)
    if losers:
        simulation.avg_loss_pnl = sum(p.realized_pnl for p in losers) / len(losers)

    # Profit factor — meaningful only when there are both wins and losses
    gross_wins = sum(p.realized_pnl for p in winners) if winners else Decimal("0")
    gross_losses = abs(sum(p.realized_pnl for p in losers)) if losers else Decimal("0")
    if gross_wins > 0 and gross_losses > 0:
        simulation.profit_factor = gross_wins / gross_losses

    # Sharpe ratio (annualized, from daily returns)
    if len(snapshots) >= 2:
        daily_returns = [float(s.daily_return_pct) / 100 for s in snapshots]
        n = len(daily_returns)
        mean_return = sum(daily_returns) / n
        variance = sum((r - mean_return) ** 2 for r in daily_returns) / (n - 1)
        std_dev = variance ** 0.5
        if std_dev > 0:
            simulation.sharpe_ratio = Decimal(str(
                (mean_return / std_dev) * (252 ** 0.5)
            )).quantize(Decimal("0.0001"))
