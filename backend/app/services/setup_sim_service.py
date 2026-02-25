"""Setup simulation service for backtesting user-defined trading setups.

Simulation assumptions for OHLC daily bar data:
- When both entry and stop could trigger on the same bar, we assume entry
  happened first (standard backtesting convention — intra-day order cannot
  be determined from daily OHLC data).
- Gap-down handling: if the bar opens below a stop level, exit is at the
  open price (not the stop price), matching real-world slippage behavior.
  This follows the same convention as the Arena simulation engine.
"""

from datetime import date
from decimal import Decimal

from app.schemas.setup_sim import (
    SetupDefinition, TradeResult, SetupResult,
    SimulationSummary, SetupSimulationResponse,
)
from app.services.arena.agent_protocol import PriceBar
from app.services.arena.trailing_stop import FixedPercentTrailingStop

POSITION_SIZE = Decimal("1000")


def simulate_setup(
    setup: SetupDefinition,
    price_bars: list[PriceBar],  # sorted oldest→newest
    end_date: date,
) -> SetupResult:
    """Simulate a single setup over the given price data."""
    trades: list[TradeResult] = []
    trailing_stop = FixedPercentTrailingStop(setup.trailing_stop_pct)

    # Active trade state (None when no position)
    active_entry_date: date | None = None
    active_entry_price: Decimal | None = None
    active_shares: int | None = None
    active_highest: Decimal | None = None
    active_stop: Decimal | None = None

    for bar in price_bars:
        if bar.date < setup.start_date:
            continue

        if active_entry_date is None:
            # --- No position: check for entry ---
            if bar.high >= setup.entry_price:
                # Determine fill price:
                # - If open >= entry (gapped above): fill at open
                # - If open < entry and high >= entry: fill at entry_price
                if bar.open >= setup.entry_price:
                    fill_price = bar.open
                else:
                    fill_price = setup.entry_price

                shares = int(POSITION_SIZE / fill_price)
                if shares == 0:
                    continue  # price too high for position size

                # Day 1: check fixed stop loss
                if bar.low <= setup.stop_loss_day1:
                    # Entered and stopped out same day
                    # Gap-down realism: exit at min(stop, open) — but on day 1
                    # entry and stop are on the same bar, so exit at stop price
                    # (price must have passed through entry first, then dropped to stop)
                    exit_price = setup.stop_loss_day1
                    pnl = (exit_price - fill_price) * shares
                    return_pct = (
                        (exit_price - fill_price) / fill_price * 100
                    ).quantize(Decimal("0.01"))
                    trades.append(TradeResult(
                        entry_date=bar.date, entry_price=fill_price,
                        exit_date=bar.date, exit_price=exit_price,
                        shares=shares, pnl=pnl.quantize(Decimal("0.01")),
                        return_pct=return_pct, exit_reason="stop_day1",
                    ))
                    # Position closed — can retrigger on next day
                else:
                    # Position opened, survives day 1
                    # Use FixedPercentTrailingStop.calculate_initial_stop() to avoid
                    # duplicating stop calculation logic
                    active_entry_date = bar.date
                    active_entry_price = fill_price
                    active_shares = shares
                    active_highest, active_stop = trailing_stop.calculate_initial_stop(
                        fill_price
                    )
                    # Update highest to include day-1 high (may be above entry)
                    if bar.high > active_highest:
                        active_highest = bar.high
                        new_stop = (
                            active_highest * (Decimal("1") - setup.trailing_stop_pct / Decimal("100"))
                        ).quantize(Decimal("0.0001"))
                        active_stop = max(new_stop, active_stop)
        else:
            # --- Day 2+: apply trailing stop ---
            # active_entry_date is not None → all active_* fields are set
            assert active_highest is not None
            assert active_stop is not None
            assert active_entry_price is not None
            assert active_shares is not None
            update = trailing_stop.update(
                current_high=bar.high,
                current_low=bar.low,
                previous_highest=active_highest,
                previous_stop=active_stop,
            )

            if update.stop_triggered:
                # Gap-down realism: if bar opens below stop, exit at open
                # (matching Arena engine convention)
                assert update.trigger_price is not None
                exit_price = min(update.trigger_price, bar.open)
                pnl = (exit_price - active_entry_price) * active_shares
                return_pct = (
                    (exit_price - active_entry_price) / active_entry_price * 100
                ).quantize(Decimal("0.01"))
                trades.append(TradeResult(
                    entry_date=active_entry_date, entry_price=active_entry_price,
                    exit_date=bar.date, exit_price=exit_price,
                    shares=active_shares, pnl=pnl.quantize(Decimal("0.01")),
                    return_pct=return_pct, exit_reason="trailing_stop",
                ))
                # Reset — can retrigger on next day
                active_entry_date = None
                active_entry_price = None
                active_shares = None
                active_highest = None
                active_stop = None
            else:
                active_highest = update.highest_price
                active_stop = update.stop_price

    # Close open position at end
    if active_entry_date is not None:
        # active_entry_date is not None → all active_* fields are set
        assert active_entry_price is not None
        assert active_shares is not None
        # Local aliases for type narrowing (Pyright doesn't narrow through nested blocks)
        open_entry_price: Decimal = active_entry_price
        open_shares: int = active_shares
        last_bar = price_bars[-1] if price_bars else None
        if last_bar:
            exit_price = last_bar.close
            pnl = (exit_price - open_entry_price) * open_shares
            return_pct = (
                (exit_price - open_entry_price) / open_entry_price * 100
            ).quantize(Decimal("0.01"))
            trades.append(TradeResult(
                entry_date=active_entry_date, entry_price=open_entry_price,
                exit_date=last_bar.date, exit_price=exit_price,
                shares=open_shares, pnl=pnl.quantize(Decimal("0.01")),
                return_pct=return_pct, exit_reason="simulation_end",
            ))

    return SetupResult(
        symbol=setup.symbol,
        entry_price=setup.entry_price,
        stop_loss_day1=setup.stop_loss_day1,
        trailing_stop_pct=setup.trailing_stop_pct,
        start_date=setup.start_date,
        times_triggered=len(trades),
        pnl=sum((t.pnl for t in trades), Decimal("0")),
        trades=trades,
    )


def run_simulation(
    setup_results: list[SetupResult],
) -> SetupSimulationResponse:
    """Aggregate individual setup results into a simulation response."""
    all_trades = [t for sr in setup_results for t in sr.trades]

    total_pnl: Decimal = sum((sr.pnl for sr in setup_results), Decimal("0"))
    total_trades = len(all_trades)
    winners = [t for t in all_trades if t.pnl > 0]
    losers = [t for t in all_trades if t.pnl <= 0]

    # Use actual capital deployed (entry_price * shares) for accurate P&L %
    total_capital_deployed: Decimal = sum(
        (t.entry_price * t.shares for t in all_trades), Decimal("0")
    )

    summary = SimulationSummary(
        total_pnl=total_pnl.quantize(Decimal("0.01")),
        total_pnl_pct=(
            (total_pnl / total_capital_deployed * 100).quantize(Decimal("0.01"))
            if total_capital_deployed > 0 else Decimal("0")
        ),
        total_capital_deployed=total_capital_deployed.quantize(Decimal("0.01")),
        total_trades=total_trades,
        winning_trades=len(winners),
        losing_trades=len(losers),
        win_rate=(
            (Decimal(len(winners)) / Decimal(total_trades) * 100).quantize(Decimal("0.01"))
            if total_trades > 0 else None
        ),
        avg_gain=(
            (sum((t.pnl for t in winners), Decimal("0")) / len(winners)).quantize(Decimal("0.01"))
            if winners else None
        ),
        avg_loss=(
            (sum((t.pnl for t in losers), Decimal("0")) / len(losers)).quantize(Decimal("0.01"))
            if losers else None
        ),
        position_size=POSITION_SIZE,
    )

    return SetupSimulationResponse(summary=summary, setups=setup_results)
