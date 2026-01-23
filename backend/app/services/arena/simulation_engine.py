"""Arena simulation engine for orchestrating trading simulations.

This module provides the core simulation engine that orchestrates day-by-day
trading simulations. It manages:
- Price data loading and caching
- Position lifecycle (pending -> open -> closed)
- Trailing stop management
- Daily snapshot creation
- Performance metrics calculation
"""

import logging
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.arena import (
    ArenaPosition,
    ArenaSimulation,
    ArenaSnapshot,
    ExitReason,
    PositionStatus,
    SimulationStatus,
)
from app.services.arena.agent_protocol import PriceBar
from app.services.arena.agent_registry import get_agent
from app.services.arena.trailing_stop import FixedPercentTrailingStop
from app.services.data_service import DataService

logger = logging.getLogger(__name__)


class SimulationEngine:
    """Orchestrates arena simulation execution.

    Responsibilities:
    - Load historical price data
    - Step through simulation day-by-day
    - Manage position lifecycle (open, update stops, close)
    - Create daily snapshots
    - Calculate performance metrics

    Example:
        >>> engine = SimulationEngine(session)
        >>> await engine.initialize_simulation(simulation_id)
        >>> while (snapshot := await engine.step_day(simulation_id)) is not None:
        ...     print(f"Day {snapshot.day_number}: ${snapshot.total_equity}")
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialize the simulation engine.

        Args:
            session: Database session for persistence operations.
        """
        self.session = session
        self.data_service = DataService(session=session)

    async def initialize_simulation(
        self,
        simulation_id: int,
    ) -> ArenaSimulation:
        """Initialize a simulation for execution.

        Validates the simulation state, loads required price data,
        calculates trading days, and sets the simulation to RUNNING status.

        Args:
            simulation_id: ID of the simulation to initialize.

        Returns:
            Initialized simulation object with updated state.

        Raises:
            ValueError: If simulation not found or already started.
        """
        simulation = await self.session.get(ArenaSimulation, simulation_id)
        if not simulation:
            msg = f"Simulation {simulation_id} not found"
            raise ValueError(msg)

        # Reject terminal states - these simulations should not be reinitialized
        terminal_statuses = {
            SimulationStatus.COMPLETED.value,
            SimulationStatus.CANCELLED.value,
            SimulationStatus.FAILED.value,
        }
        if simulation.status in terminal_statuses:
            msg = f"Simulation cannot be initialized: status is {simulation.status}"
            raise ValueError(msg)

        # Already initialized - skip (idempotent for retries)
        if simulation.is_initialized:
            logger.info(
                f"Simulation {simulation_id} already initialized, skipping"
            )
            return simulation

        # Get agent to know lookback requirements
        agent = get_agent(simulation.agent_type, simulation.agent_config)
        lookback_days = agent.required_lookback_days

        # Pre-load price data for all symbols with lookback period
        data_start = simulation.start_date - timedelta(days=lookback_days + 30)
        for symbol in simulation.symbols:
            await self.data_service.get_price_data(
                symbol=symbol,
                start_date=datetime.combine(
                    data_start, datetime.min.time(), tzinfo=timezone.utc
                ),
                end_date=datetime.combine(
                    simulation.end_date, datetime.max.time(), tzinfo=timezone.utc
                ),
                interval="1d",
            )

        # Get trading days in simulation range
        trading_days = await self._get_trading_days(
            simulation.symbols, simulation.start_date, simulation.end_date
        )

        if not trading_days:
            msg = "No trading days found in date range"
            raise ValueError(msg)

        # Update simulation state
        simulation.total_days = len(trading_days)
        simulation.status = SimulationStatus.RUNNING.value

        await self.session.commit()
        await self.session.refresh(simulation)

        logger.info(
            f"Initialized simulation {simulation_id}: "
            f"{len(simulation.symbols)} symbols, {simulation.total_days} trading days"
        )

        return simulation

    async def step_day(
        self,
        simulation_id: int,
    ) -> ArenaSnapshot | None:
        """Execute one simulation day.

        Processes a single trading day:
        1. Opens pending positions at today's open price
        2. Updates trailing stops for open positions
        3. Closes positions where stop is triggered
        4. Gets agent decisions for new entries
        5. Creates pending positions for BUY signals
        6. Creates daily snapshot with portfolio state

        Atomicity:
            Day processing is transactional - all changes (positions, cash,
            snapshot) commit together at the end of this method. If the worker
            crashes mid-execution, no partial state is persisted. On retry,
            the entire day re-processes from the last committed snapshot.
            Do not add intermediate commits within this method.

        Args:
            simulation_id: ID of simulation to advance.

        Returns:
            Snapshot for the day, or None if simulation complete.

        Raises:
            ValueError: If simulation not found or not in RUNNING status.
        """
        simulation = await self.session.get(ArenaSimulation, simulation_id)
        if not simulation:
            msg = f"Simulation {simulation_id} not found"
            raise ValueError(msg)

        if simulation.status == SimulationStatus.COMPLETED.value:
            return None

        if simulation.status != SimulationStatus.RUNNING.value:
            msg = f"Simulation not running: {simulation.status}"
            raise ValueError(msg)

        # Get agent and trailing stop config
        agent = get_agent(simulation.agent_type, simulation.agent_config)
        trail_pct = Decimal(str(simulation.agent_config.get("trailing_stop_pct", 5.0)))
        trailing_stop = FixedPercentTrailingStop(trail_pct)

        # Get trading days
        trading_days = await self._get_trading_days(
            simulation.symbols, simulation.start_date, simulation.end_date
        )

        # Check if simulation is complete
        if simulation.current_day >= len(trading_days):
            # Close all positions and finalize
            await self._close_all_positions(
                simulation, trading_days[-1], ExitReason.SIMULATION_END
            )
            await self._finalize_simulation(simulation)
            return None

        current_date = trading_days[simulation.current_day]

        # Get previous snapshot for cash balance
        prev_snapshot = await self._get_latest_snapshot(simulation.id)
        cash = prev_snapshot.cash if prev_snapshot else simulation.initial_capital

        # Load open positions
        open_positions = await self._get_open_positions(simulation.id)
        positions_by_symbol: dict[str, ArenaPosition] = {
            p.symbol: p for p in open_positions
        }

        # Process each symbol
        decisions: dict[str, dict] = {}

        for symbol in simulation.symbols:
            # Get price history up to current date
            price_history = await self._get_price_history(
                symbol,
                current_date - timedelta(days=agent.required_lookback_days + 30),
                current_date,
            )

            if not price_history:
                decisions[symbol] = {"action": "NO_DATA", "reasoning": "No price data"}
                continue

            # Get today's bar for position updates
            today_bar = self._find_bar_for_date(price_history, current_date)
            if not today_bar:
                decisions[symbol] = {
                    "action": "NO_DATA",
                    "reasoning": "No data for today",
                }
                continue

            # Check for pending position to open
            pending = await self._get_pending_position(simulation.id, symbol)
            if pending:
                # Calculate shares
                calculated_shares = int(simulation.position_size / today_bar.open)
                cost = calculated_shares * today_bar.open if calculated_shares > 0 else Decimal("0")

                if calculated_shares < 1:
                    # Price too high for position size - cancel pending
                    pending.status = PositionStatus.CLOSED.value
                    pending.exit_reason = ExitReason.INSUFFICIENT_CAPITAL.value
                    pending.agent_reasoning = (
                        f"Position skipped: price ${today_bar.open} > "
                        f"position size ${simulation.position_size}"
                    )
                elif cost > cash:
                    # Not enough cash to open position - cancel pending
                    pending.status = PositionStatus.CLOSED.value
                    pending.exit_reason = ExitReason.INSUFFICIENT_CAPITAL.value
                    pending.agent_reasoning = (
                        f"Position skipped: insufficient cash ${cash:.2f} < "
                        f"cost ${cost:.2f}"
                    )
                else:
                    # Open position at today's open
                    pending.status = PositionStatus.OPEN.value
                    pending.entry_date = current_date
                    pending.entry_price = today_bar.open
                    pending.shares = calculated_shares

                    # Initialize trailing stop
                    highest, stop = trailing_stop.calculate_initial_stop(today_bar.open)
                    pending.highest_price = highest
                    pending.current_stop = stop

                    cash -= cost
                    positions_by_symbol[symbol] = pending

            # Update existing position
            position = positions_by_symbol.get(symbol)
            if position and position.status == PositionStatus.OPEN.value:
                # Update trailing stop
                update = trailing_stop.update(
                    current_high=today_bar.high,
                    current_low=today_bar.low,
                    previous_highest=position.highest_price,
                    previous_stop=position.current_stop,
                )

                if update.stop_triggered:
                    # Close position at stop price or open price (whichever is worse)
                    # Gap-down handling: if stock opens below stop, we get filled at open
                    exit_price = min(update.trigger_price, today_bar.open)
                    realized_pnl = (exit_price - position.entry_price) * position.shares
                    return_pct = (
                        (exit_price - position.entry_price) / position.entry_price * 100
                    )

                    position.status = PositionStatus.CLOSED.value
                    position.exit_date = current_date
                    position.exit_price = exit_price
                    position.exit_reason = ExitReason.STOP_HIT.value
                    position.realized_pnl = realized_pnl
                    position.return_pct = return_pct

                    cash += position.shares * exit_price

                    simulation.total_trades += 1
                    if realized_pnl > 0:
                        simulation.winning_trades += 1

                    del positions_by_symbol[symbol]
                else:
                    # Update stop levels
                    position.highest_price = update.highest_price
                    position.current_stop = update.stop_price

            # Get agent decision (only if not already holding)
            has_position = symbol in positions_by_symbol
            decision = await agent.evaluate(
                symbol, price_history, current_date, has_position
            )

            decisions[symbol] = {
                "action": decision.action,
                "score": decision.score,
                "reasoning": decision.reasoning,
            }

            # Create pending position for BUY signals
            if decision.action == "BUY" and not has_position:
                new_position = ArenaPosition(
                    simulation_id=simulation.id,
                    symbol=symbol,
                    status=PositionStatus.PENDING.value,
                    signal_date=current_date,
                    trailing_stop_pct=trail_pct,
                    agent_reasoning=decision.reasoning,
                    agent_score=decision.score,
                )
                self.session.add(new_position)

        # Calculate portfolio value
        positions_value = Decimal("0")
        for position in positions_by_symbol.values():
            if position.status == PositionStatus.OPEN.value:
                # Get current price
                today_bar = await self._get_bar_for_date(position.symbol, current_date)
                if today_bar:
                    positions_value += position.shares * today_bar.close

        total_equity = cash + positions_value

        # Calculate daily P&L
        prev_equity = (
            prev_snapshot.total_equity if prev_snapshot else simulation.initial_capital
        )
        daily_pnl = total_equity - prev_equity
        daily_return_pct = (
            (daily_pnl / prev_equity * 100) if prev_equity else Decimal("0")
        )
        cumulative_return_pct = (
            (total_equity - simulation.initial_capital)
            / simulation.initial_capital
            * 100
        )

        # Create snapshot
        snapshot = ArenaSnapshot(
            simulation_id=simulation.id,
            snapshot_date=current_date,
            day_number=simulation.current_day,
            cash=cash,
            positions_value=positions_value,
            total_equity=total_equity,
            daily_pnl=daily_pnl,
            daily_return_pct=daily_return_pct,
            cumulative_return_pct=cumulative_return_pct,
            open_position_count=len(positions_by_symbol),
            decisions=decisions,
        )
        self.session.add(snapshot)

        # Update simulation state
        simulation.current_day += 1
        simulation.final_equity = total_equity
        simulation.total_return_pct = cumulative_return_pct

        # Update max drawdown
        await self._update_max_drawdown(simulation)

        await self.session.commit()
        await self.session.refresh(snapshot)

        logger.debug(
            f"Simulation {simulation_id} day {simulation.current_day}: "
            f"equity=${total_equity}, positions={len(positions_by_symbol)}"
        )

        return snapshot

    async def run_to_completion(
        self,
        simulation_id: int,
    ) -> ArenaSimulation:
        """Run simulation to completion.

        Continuously steps through days until the simulation is complete.

        Args:
            simulation_id: ID of simulation to run.

        Returns:
            Completed simulation object.
        """
        while True:
            snapshot = await self.step_day(simulation_id)
            if snapshot is None:
                break

        simulation = await self.session.get(ArenaSimulation, simulation_id)
        return simulation

    # =========================================================================
    # Helper Methods
    # =========================================================================

    async def _get_trading_days(
        self, symbols: list[str], start: date, end: date
    ) -> list[date]:
        """Get trading days in range where we have data for at least one symbol.

        Args:
            symbols: List of stock symbols.
            start: Start date.
            end: End date.

        Returns:
            Sorted list of trading dates.
        """
        all_dates: set[date] = set()
        for symbol in symbols:
            records = await self.data_service.get_price_data(
                symbol=symbol,
                start_date=datetime.combine(
                    start, datetime.min.time(), tzinfo=timezone.utc
                ),
                end_date=datetime.combine(end, datetime.max.time(), tzinfo=timezone.utc),
                interval="1d",
            )
            for r in records:
                record_date = r.timestamp.date()
                if start <= record_date <= end:
                    all_dates.add(record_date)
        return sorted(all_dates)

    async def _get_price_history(
        self, symbol: str, start: date, end: date
    ) -> list[PriceBar]:
        """Get price history as PriceBar objects.

        Args:
            symbol: Stock symbol.
            start: Start date.
            end: End date.

        Returns:
            List of PriceBar objects sorted by date.
        """
        records = await self.data_service.get_price_data(
            symbol=symbol,
            start_date=datetime.combine(
                start, datetime.min.time(), tzinfo=timezone.utc
            ),
            end_date=datetime.combine(end, datetime.max.time(), tzinfo=timezone.utc),
            interval="1d",
        )
        return [
            PriceBar(
                date=r.timestamp.date(),
                open=Decimal(str(r.open_price)),
                high=Decimal(str(r.high_price)),
                low=Decimal(str(r.low_price)),
                close=Decimal(str(r.close_price)),
                volume=int(r.volume),
            )
            for r in records
        ]

    def _find_bar_for_date(
        self, price_history: list[PriceBar], target_date: date
    ) -> PriceBar | None:
        """Find a price bar for a specific date in the history.

        Args:
            price_history: List of price bars.
            target_date: Date to find.

        Returns:
            PriceBar for the date or None if not found.
        """
        for bar in reversed(price_history):
            if bar.date == target_date:
                return bar
        return None

    async def _get_bar_for_date(
        self, symbol: str, target_date: date
    ) -> PriceBar | None:
        """Get single bar for specific date by querying the database.

        Args:
            symbol: Stock symbol.
            target_date: Target date.

        Returns:
            PriceBar for the date or None if not found.
        """
        history = await self._get_price_history(symbol, target_date, target_date)
        return history[0] if history else None

    async def _get_latest_snapshot(
        self, simulation_id: int
    ) -> ArenaSnapshot | None:
        """Get most recent snapshot for a simulation.

        Args:
            simulation_id: Simulation ID.

        Returns:
            Latest snapshot or None if no snapshots exist.
        """
        result = await self.session.execute(
            select(ArenaSnapshot)
            .where(ArenaSnapshot.simulation_id == simulation_id)
            .order_by(ArenaSnapshot.day_number.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def _get_open_positions(
        self, simulation_id: int
    ) -> Sequence[ArenaPosition]:
        """Get all open positions for a simulation.

        Args:
            simulation_id: Simulation ID.

        Returns:
            Sequence of open positions.
        """
        result = await self.session.execute(
            select(ArenaPosition)
            .where(ArenaPosition.simulation_id == simulation_id)
            .where(ArenaPosition.status == PositionStatus.OPEN.value)
        )
        return result.scalars().all()

    async def _get_pending_position(
        self, simulation_id: int, symbol: str
    ) -> ArenaPosition | None:
        """Get pending position for a symbol.

        Args:
            simulation_id: Simulation ID.
            symbol: Stock symbol.

        Returns:
            Pending position or None if no pending position exists.
        """
        result = await self.session.execute(
            select(ArenaPosition)
            .where(ArenaPosition.simulation_id == simulation_id)
            .where(ArenaPosition.symbol == symbol)
            .where(ArenaPosition.status == PositionStatus.PENDING.value)
        )
        return result.scalar_one_or_none()

    async def _close_all_positions(
        self, simulation: ArenaSimulation, close_date: date, reason: ExitReason
    ) -> None:
        """Close all open positions at end of simulation.

        Args:
            simulation: Simulation object.
            close_date: Date to close positions.
            reason: Exit reason for all positions.
        """
        open_positions = await self._get_open_positions(simulation.id)

        for position in open_positions:
            bar = await self._get_bar_for_date(position.symbol, close_date)
            if not bar:
                continue

            exit_price = bar.close
            realized_pnl = (exit_price - position.entry_price) * position.shares
            return_pct = (exit_price - position.entry_price) / position.entry_price * 100

            position.status = PositionStatus.CLOSED.value
            position.exit_date = close_date
            position.exit_price = exit_price
            position.exit_reason = reason.value
            position.realized_pnl = realized_pnl
            position.return_pct = return_pct

            simulation.total_trades += 1
            if realized_pnl > 0:
                simulation.winning_trades += 1

    async def _finalize_simulation(self, simulation: ArenaSimulation) -> None:
        """Mark simulation as completed.

        Args:
            simulation: Simulation to finalize.
        """
        simulation.status = SimulationStatus.COMPLETED.value
        await self.session.commit()
        logger.info(
            f"Simulation {simulation.id} completed: "
            f"{simulation.total_trades} trades, "
            f"return {simulation.total_return_pct}%"
        )

    async def _update_max_drawdown(self, simulation: ArenaSimulation) -> None:
        """Update max drawdown based on equity curve.

        Calculates the maximum drawdown from peak equity to any subsequent
        trough. This is a key risk metric for trading strategies.

        Args:
            simulation: Simulation to update.
        """
        result = await self.session.execute(
            select(ArenaSnapshot.total_equity)
            .where(ArenaSnapshot.simulation_id == simulation.id)
            .order_by(ArenaSnapshot.day_number)
        )
        equities = [row[0] for row in result.all()]

        if len(equities) < 2:
            return

        peak = equities[0]
        max_dd = Decimal("0")

        for equity in equities:
            if equity > peak:
                peak = equity
            if peak > 0:
                drawdown = (peak - equity) / peak * 100
                max_dd = max(max_dd, drawdown)

        simulation.max_drawdown_pct = max_dd
