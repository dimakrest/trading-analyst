"""Arena simulation engine for orchestrating trading simulations.

This module provides the core simulation engine that orchestrates day-by-day
trading simulations. It manages:
- Price data loading and caching
- Position lifecycle (pending -> open -> closed)
- Trailing stop management
- Daily snapshot creation
- Performance metrics calculation
"""

import asyncio
import logging
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import noload

from app.models.arena import (
    ArenaPosition,
    ArenaSimulation,
    ArenaSnapshot,
    ExitReason,
    PositionStatus,
    SimulationStatus,
)
from app.services.arena.analytics import compute_simulation_analytics
from app.models.stock_sector import StockSector
from app.services.arena.agent_protocol import AgentDecision, PriceBar
from app.services.arena.agent_registry import get_agent
from app.services.arena.trailing_stop import AtrTrailingStop, FixedPercentTrailingStop
from app.services.data_service import DataService
from app.services.portfolio_selector import QualifyingSignal, get_selector
from app.utils.technical_indicators import calculate_atr_percentage

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

    def __init__(
        self,
        session: AsyncSession,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """Initialize the simulation engine.

        Args:
            session: Database session for persistence operations.
            session_factory: Factory for creating async database sessions for DataService.
        """
        self.session = session
        self.data_service = DataService(session_factory=session_factory)
        # In-memory caches (populated during init or first step_day for resume)
        self._trading_days_cache: dict[int, list[date]] = {}
        self._peak_equity: dict[int, Decimal] = {}
        self._max_drawdown: dict[int, Decimal] = {}
        # Price data cache: {simulation_id: {symbol: [PriceBar, ...]}}
        self._price_cache: dict[int, dict[str, list[PriceBar]]] = {}
        # Sector cache: {simulation_id: {symbol: sector_name | None}}
        self._sector_cache: dict[int, dict[str, str | None]] = {}

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
        simulation = await self.session.get(
            ArenaSimulation,
            simulation_id,
            options=[noload(ArenaSimulation.positions), noload(ArenaSimulation.snapshots)],
        )
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
            logger.info(f"Simulation {simulation_id} already initialized, skipping")
            return simulation

        # Get agent to know lookback requirements
        agent = get_agent(simulation.agent_type, simulation.agent_config)
        lookback_days = agent.required_lookback_days

        # Pre-load all price data into memory cache (replaces the old loop that
        # loaded data through DataService and discarded the results)
        await self._load_price_cache(
            simulation.id,
            simulation.symbols,
            simulation.start_date,
            simulation.end_date,
            lookback_days,
        )
        # Regime filter: pre-load regime symbol (e.g. SPY) into price cache
        if simulation.agent_config.get("regime_filter", False):
            await self._load_regime_symbol_cache(
                simulation.id,
                simulation.agent_config.get("regime_symbol", "SPY"),
                simulation.start_date,
                simulation.end_date,
                simulation.agent_config.get("regime_sma_period", 20),
            )
        # Prefetch any missing sector data from Yahoo Finance (non-blocking on failure)
        try:
            sector_name_map = await self.data_service.batch_prefetch_sectors(
                simulation.symbols, self.session
            )
            # Directly populate cache with freshly fetched data
            self._sector_cache[simulation.id] = sector_name_map
            missing_count = sum(1 for v in sector_name_map.values() if v is None)
            if missing_count:
                logger.info(
                    f"Simulation {simulation.id}: {missing_count}/{len(simulation.symbols)} "
                    f"symbols have no sector data after prefetch"
                )
        except Exception as e:
            logger.warning(f"Sector prefetch failed for simulation {simulation.id}: {e}")
            # Fall back to DB-only load
            await self._load_sector_cache(simulation.id, simulation.symbols)

        # Get trading days from cache
        trading_days = self._get_trading_days_from_cache(
            simulation.id, simulation.start_date, simulation.end_date
        )
        self._trading_days_cache[simulation.id] = trading_days

        if not trading_days:
            msg = "No trading days found in date range"
            raise ValueError(msg)

        # Update simulation state
        simulation.total_days = len(trading_days)
        simulation.status = SimulationStatus.RUNNING.value

        # Initialize drawdown tracking (no snapshots yet, use initial capital)
        self._peak_equity[simulation.id] = simulation.initial_capital
        self._max_drawdown[simulation.id] = Decimal("0")

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
        simulation = await self.session.get(
            ArenaSimulation,
            simulation_id,
            options=[noload(ArenaSimulation.positions), noload(ArenaSimulation.snapshots)],
        )
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
        stop_type: str = simulation.agent_config.get("stop_type", "fixed")
        trail_pct = Decimal(str(simulation.agent_config.get("trailing_stop_pct", 5.0)))

        # Build the stop object used for fixed-percent updates.
        # For ATR stops each position carries its own trail_pct (set at entry),
        # so we construct AtrTrailingStop to handle the initial calculation and
        # use its update() method (which accepts a per-call trail_pct) for updates.
        fixed_trailing_stop = FixedPercentTrailingStop(trail_pct)
        atr_trailing_stop: AtrTrailingStop | None = None
        if stop_type == "atr":
            atr_trailing_stop = AtrTrailingStop(
                atr_multiplier=float(
                    simulation.agent_config.get("atr_stop_multiplier", 2.0)
                ),
                min_pct=float(simulation.agent_config.get("atr_stop_min_pct", 2.0)),
                max_pct=float(simulation.agent_config.get("atr_stop_max_pct", 10.0)),
            )

        # Exit rule parameters (None = feature disabled)
        take_profit_pct: float | None = simulation.agent_config.get("take_profit_pct")
        take_profit_atr_mult: float | None = simulation.agent_config.get(
            "take_profit_atr_mult"
        )
        max_hold_days: int | None = simulation.agent_config.get("max_hold_days")
        max_hold_days_profit: int | None = simulation.agent_config.get(
            "max_hold_days_profit"
        )

        # Breakeven & profit ratcheting (None = feature disabled)
        breakeven_trigger_pct: float | None = simulation.agent_config.get("breakeven_trigger_pct")
        ratchet_trigger_pct: float | None = simulation.agent_config.get("ratchet_trigger_pct")
        ratchet_trail_pct: float | None = simulation.agent_config.get("ratchet_trail_pct")

        # Position sizing: percentage of equity (overrides fixed position_size)
        position_size_pct: float | None = simulation.agent_config.get("position_size_pct")

        # Ensure price cache is loaded (handles resume case)
        if simulation_id not in self._price_cache:
            await self._load_price_cache(
                simulation_id,
                simulation.symbols,
                simulation.start_date,
                simulation.end_date,
                agent.required_lookback_days,
            )
            # Regime filter: load regime symbol if enabled
            if simulation.agent_config.get("regime_filter", False):
                await self._load_regime_symbol_cache(
                    simulation_id,
                    simulation.agent_config.get("regime_symbol", "SPY"),
                    simulation.start_date,
                    simulation.end_date,
                    simulation.agent_config.get("regime_sma_period", 20),
                )
            await self._load_sector_cache(simulation_id, simulation.symbols)

        # Use cached trading days (lazy-load for resume case)
        if simulation_id not in self._trading_days_cache:
            self._trading_days_cache[simulation_id] = self._get_trading_days_from_cache(
                simulation_id, simulation.start_date, simulation.end_date
            )
        trading_days = self._trading_days_cache[simulation_id]

        # Check if simulation is complete
        if simulation.current_day >= len(trading_days):
            # Close all positions and finalize
            closed_positions = await self._close_all_positions(
                simulation, trading_days[-1], ExitReason.SIMULATION_END
            )
            await self._finalize_simulation(simulation, closed_positions)
            return None

        current_date = trading_days[simulation.current_day]

        # Get previous snapshot for cash balance
        prev_snapshot = await self._get_latest_snapshot(simulation.id)
        cash = prev_snapshot.cash if prev_snapshot else simulation.initial_capital

        # Load open positions
        open_positions = await self._get_open_positions(simulation.id)
        positions_by_symbol: dict[str, ArenaPosition] = {p.symbol: p for p in open_positions}

        # Batch-load pending positions (1 query instead of N)
        pending_result = await self.session.execute(
            select(ArenaPosition)
            .where(ArenaPosition.simulation_id == simulation.id)
            .where(ArenaPosition.status == PositionStatus.PENDING.value)
        )
        pending_by_symbol: dict[str, ArenaPosition] = {
            p.symbol: p for p in pending_result.scalars().all()
        }

        # Process each symbol
        decisions: dict[str, dict] = {}
        # Collect BUY signals for portfolio selection (processed after symbol loop)
        buy_signals: list[tuple[str, AgentDecision]] = []

        for symbol in simulation.symbols:
            # Get price history up to current date
            price_history = self._get_cached_price_history(
                simulation_id,
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
            pending = pending_by_symbol.get(symbol)
            if pending:
                # Calculate position size (percentage of equity or fixed)
                if position_size_pct is not None:
                    # Compute current equity for percentage-based sizing
                    pos_value = Decimal("0")
                    for pos in positions_by_symbol.values():
                        if pos.status == PositionStatus.OPEN.value:
                            pos_bar = self._get_cached_bar_for_date(
                                simulation_id, pos.symbol, current_date
                            )
                            if pos_bar:
                                pos_value += pos.shares * pos_bar.close
                    current_equity = cash + pos_value
                    effective_position_size = current_equity * Decimal(
                        str(position_size_pct / 100)
                    )
                else:
                    effective_position_size = simulation.position_size

                # Calculate shares
                calculated_shares = int(effective_position_size / today_bar.open)
                cost = calculated_shares * today_bar.open if calculated_shares > 0 else Decimal("0")

                if calculated_shares < 1:
                    # Price too high for position size - cancel pending
                    pending.status = PositionStatus.CLOSED.value
                    pending.exit_reason = ExitReason.INSUFFICIENT_CAPITAL.value
                    pending.agent_reasoning = (
                        f"Position skipped: price ${today_bar.open} > "
                        f"position size ${effective_position_size:.2f}"
                    )
                elif cost > cash:
                    # Not enough cash to open position - cancel pending
                    pending.status = PositionStatus.CLOSED.value
                    pending.exit_reason = ExitReason.INSUFFICIENT_CAPITAL.value
                    pending.agent_reasoning = (
                        f"Position skipped: insufficient cash ${cash:.2f} < " f"cost ${cost:.2f}"
                    )
                else:
                    # Open position at today's open
                    pending.status = PositionStatus.OPEN.value
                    pending.entry_date = current_date
                    pending.entry_price = today_bar.open
                    pending.shares = calculated_shares

                    # Initialize trailing stop — ATR or fixed
                    if atr_trailing_stop is not None:
                        symbol_atr_pct = self._calculate_symbol_atr_pct(
                            simulation_id, symbol, current_date
                        )
                        if symbol_atr_pct is not None and symbol_atr_pct > 0:
                            highest, stop, computed_trail_pct = (
                                atr_trailing_stop.calculate_initial_stop(
                                    today_bar.open, symbol_atr_pct
                                )
                            )
                            # Store computed trail_pct so daily updates use the
                            # same distance that was set at entry (per-position).
                            pending.trailing_stop_pct = computed_trail_pct
                        else:
                            # No ATR data — degrade gracefully to fixed stop
                            highest, stop = fixed_trailing_stop.calculate_initial_stop(
                                today_bar.open
                            )
                    else:
                        highest, stop = fixed_trailing_stop.calculate_initial_stop(
                            today_bar.open
                        )
                    pending.highest_price = highest
                    pending.current_stop = stop

                    cash -= cost
                    positions_by_symbol[symbol] = pending

            # Update existing position
            position = positions_by_symbol.get(symbol)
            if position and position.status == PositionStatus.OPEN.value:
                # Update trailing stop — ATR stops use the per-position trail_pct
                # stored at entry time; fixed stops use the class-level value.
                if atr_trailing_stop is not None:
                    update = atr_trailing_stop.update(
                        current_high=today_bar.high,
                        current_low=today_bar.low,
                        previous_highest=position.highest_price,
                        previous_stop=position.current_stop,
                        trail_pct=position.trailing_stop_pct,
                    )
                else:
                    update = fixed_trailing_stop.update(
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
                    return_pct = (exit_price - position.entry_price) / position.entry_price * 100

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
                    # Stop not triggered — update tracked high and stop level.
                    position.highest_price = update.highest_price
                    position.current_stop = update.stop_price

                    # --- Layer 8: Breakeven stop floor ---
                    # Once the position has gained enough, pin the stop at entry
                    # so a winner can never turn into a loser.
                    if breakeven_trigger_pct is not None and position.entry_price:
                        breakeven_threshold = position.entry_price * Decimal(
                            str(1 + breakeven_trigger_pct / 100)
                        )
                        if position.highest_price >= breakeven_threshold:
                            position.current_stop = max(
                                position.current_stop, position.entry_price
                            )

                    # --- Layer 8: Profit ratcheting — tighter trail at high gains ---
                    if (
                        ratchet_trigger_pct is not None
                        and ratchet_trail_pct is not None
                        and position.entry_price
                    ):
                        ratchet_threshold = position.entry_price * Decimal(
                            str(1 + ratchet_trigger_pct / 100)
                        )
                        if position.highest_price >= ratchet_threshold:
                            ratchet_stop = position.highest_price * (
                                Decimal("1") - Decimal(str(ratchet_trail_pct / 100))
                            )
                            position.current_stop = max(
                                position.current_stop, ratchet_stop
                            )

                    # --- Layer 5: Take Profit ---
                    # Check AFTER the trailing stop so that a stop exit always
                    # takes precedence. Trigger on intraday high; exit at
                    # max(target_price, today_open) for gap-up handling.
                    if take_profit_pct is not None or take_profit_atr_mult is not None:
                        unrealized_return_pct_at_high = float(
                            (today_bar.high - position.entry_price)
                            / position.entry_price
                            * 100
                        )
                        take_profit_triggered = False
                        tp_target_pct: float | None = None

                        if (
                            take_profit_pct is not None
                            and unrealized_return_pct_at_high >= take_profit_pct
                        ):
                            take_profit_triggered = True
                            tp_target_pct = take_profit_pct

                        if not take_profit_triggered and take_profit_atr_mult is not None:
                            pos_atr_pct = self._calculate_symbol_atr_pct(
                                simulation_id, symbol, current_date
                            )
                            if pos_atr_pct is not None and pos_atr_pct > 0:
                                atr_target = take_profit_atr_mult * pos_atr_pct
                                if unrealized_return_pct_at_high >= atr_target:
                                    take_profit_triggered = True
                                    tp_target_pct = atr_target

                        if take_profit_triggered:
                            tp_target_price = position.entry_price * (
                                1 + Decimal(str(tp_target_pct)) / 100
                            )
                            exit_price = max(tp_target_price, today_bar.open)
                            realized_pnl = (
                                exit_price - position.entry_price
                            ) * position.shares
                            return_pct = (
                                (exit_price - position.entry_price)
                                / position.entry_price
                                * 100
                            )

                            position.status = PositionStatus.CLOSED.value
                            position.exit_date = current_date
                            position.exit_price = exit_price
                            position.exit_reason = ExitReason.TAKE_PROFIT.value
                            position.realized_pnl = realized_pnl
                            position.return_pct = return_pct

                            cash += position.shares * exit_price

                            simulation.total_trades += 1
                            if realized_pnl > 0:
                                simulation.winning_trades += 1

                            del positions_by_symbol[symbol]

                    # --- Layer 6: Max Holding Period ---
                    # Only check positions that are still open after stop and
                    # take-profit checks above.
                    if (
                        max_hold_days is not None
                        and symbol in positions_by_symbol
                        and position.entry_date is not None
                    ):
                        trading_days = self._trading_days_cache.get(simulation_id, [])
                        try:
                            entry_idx = trading_days.index(position.entry_date)
                            current_idx = trading_days.index(current_date)
                            hold_days = current_idx - entry_idx
                        except ValueError:
                            hold_days = 0

                        # Use extended hold for profitable positions
                        effective_hold_limit = max_hold_days
                        if (
                            max_hold_days_profit is not None
                            and position.entry_price
                            and today_bar.close > position.entry_price
                        ):
                            effective_hold_limit = max_hold_days_profit

                        if hold_days >= effective_hold_limit:
                            exit_price = today_bar.close
                            realized_pnl = (
                                exit_price - position.entry_price
                            ) * position.shares
                            return_pct = (
                                (exit_price - position.entry_price)
                                / position.entry_price
                                * 100
                            )

                            position.status = PositionStatus.CLOSED.value
                            position.exit_date = current_date
                            position.exit_price = exit_price
                            position.exit_reason = ExitReason.MAX_HOLD.value
                            position.realized_pnl = realized_pnl
                            position.return_pct = return_pct

                            cash += position.shares * exit_price

                            simulation.total_trades += 1
                            if realized_pnl > 0:
                                simulation.winning_trades += 1

                            del positions_by_symbol[symbol]

            # Get agent decision (only if not already holding)
            has_position = symbol in positions_by_symbol
            decision = await agent.evaluate(symbol, price_history, current_date, has_position)

            decisions[symbol] = {
                "action": decision.action,
                "score": decision.score,
                "reasoning": decision.reasoning,
            }

            # Collect BUY signals for portfolio selection (don't create PENDING yet)
            if decision.action == "BUY" and not has_position:
                buy_signals.append((symbol, decision))

        # --- Portfolio Selection ---
        # Read strategy configuration from agent_config (defaults preserve original behavior)
        strategy_name = simulation.agent_config.get("portfolio_strategy", "none")
        max_per_sector: int | None = simulation.agent_config.get("max_per_sector")
        max_open_positions: int | None = simulation.agent_config.get("max_open_positions")

        # --- Layer 7: Market Regime Filter ---
        # Dynamically adjust max_open_positions based on regime symbol trend.
        # This runs AFTER reading the base max_open_positions so the bull regime
        # can optionally override it and the bear regime reduces it.
        if simulation.agent_config.get("regime_filter", False):
            regime_symbol: str = simulation.agent_config.get("regime_symbol", "SPY")
            sma_period: int = simulation.agent_config.get("regime_sma_period", 20)
            regime = self._detect_market_regime(simulation_id, current_date, regime_symbol, sma_period)
            if regime == "bear":
                bear_max: int = simulation.agent_config.get("regime_bear_max_positions", 1)
                max_open_positions = bear_max
            else:
                bull_max: int | None = simulation.agent_config.get("regime_bull_max_positions")
                if bull_max is not None:
                    max_open_positions = bull_max

        selector = get_selector(strategy_name)

        # Build qualifying signals with sector and ATR data from caches
        qualifying: list[QualifyingSignal] = []
        sim_sector_map = self._sector_cache.get(simulation_id, {})
        for symbol, decision in buy_signals:
            qualifying.append(
                QualifyingSignal(
                    symbol=symbol,
                    score=decision.score,
                    sector=sim_sector_map.get(symbol),
                    atr_pct=self._calculate_symbol_atr_pct(simulation_id, symbol, current_date),
                    metadata=decision.metadata,
                )
            )

        # Count existing open positions by sector for constraint enforcement
        existing_sector_counts: dict[str, int] = {}
        for sym in positions_by_symbol:
            sector = sim_sector_map.get(sym)
            sector_key = sector or f"__unknown_{sym}"
            existing_sector_counts[sector_key] = existing_sector_counts.get(sector_key, 0) + 1

        # Run portfolio selector to get the ordered selected subset
        selected = selector.select(
            signals=qualifying,
            existing_sector_counts=existing_sector_counts,
            current_open_count=len(positions_by_symbol),
            max_per_sector=max_per_sector,
            max_open_positions=max_open_positions,
        )
        selected_symbols = {s.symbol for s in selected}

        # Create PENDING positions for selected signals only
        for symbol, decision in buy_signals:
            is_selected = symbol in selected_symbols
            # Annotate decision for transparency in snapshots
            decisions[symbol]["portfolio_selected"] = is_selected
            if is_selected:
                # For ATR stops the actual trail_pct is computed at position
                # open time (next day) when we have the entry price.  Store
                # the configured fixed trail_pct as a placeholder; it will be
                # overwritten when the position transitions from PENDING → OPEN.
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
                today_bar = self._get_cached_bar_for_date(simulation_id, position.symbol, current_date)
                if today_bar:
                    positions_value += position.shares * today_bar.close

        total_equity = cash + positions_value

        # Calculate daily P&L
        prev_equity = prev_snapshot.total_equity if prev_snapshot else simulation.initial_capital
        daily_pnl = total_equity - prev_equity
        daily_return_pct = (daily_pnl / prev_equity * 100) if prev_equity else Decimal("0")
        cumulative_return_pct = (
            (total_equity - simulation.initial_capital) / simulation.initial_capital * 100
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

        # Cross-check: verify snapshot values are internally consistent
        # This catches bugs in snapshot construction (e.g., wrong argument order)
        # rather than the calculation itself, where total_equity is defined as
        # cash + positions_value and thus can never mismatch inline.
        if abs(snapshot.total_equity - (snapshot.cash + snapshot.positions_value)) > Decimal(
            "0.01"
        ):
            logger.error(
                f"Simulation {simulation_id} day {simulation.current_day}: "
                f"snapshot equity mismatch: {snapshot.total_equity} != "
                f"{snapshot.cash} + {snapshot.positions_value}"
            )
            raise ValueError(
                f"Accounting error: snapshot equity mismatch "
                f"({snapshot.total_equity} != {snapshot.cash} + {snapshot.positions_value})"
            )

        # Update simulation state
        simulation.current_day += 1
        simulation.final_equity = total_equity
        simulation.total_return_pct = cumulative_return_pct

        # Incremental max drawdown (O(1) instead of O(n))
        sim_id = simulation.id
        if sim_id not in self._peak_equity:
            await self._init_drawdown_state(simulation)
        peak = self._peak_equity[sim_id]
        if total_equity > peak:
            peak = total_equity
            self._peak_equity[sim_id] = peak
        if peak > 0:
            dd = (peak - total_equity) / peak * 100
            current_max = self._max_drawdown.get(sim_id, Decimal("0"))
            if dd > current_max:
                self._max_drawdown[sim_id] = dd
                simulation.max_drawdown_pct = dd

        # Validate accounting invariants before commit
        if cash < 0:
            logger.error(
                f"Simulation {simulation_id} day {simulation.current_day}: "
                f"cash went negative: {cash}"
            )
            raise ValueError(f"Accounting error: cash is negative ({cash})")

        if positions_value < 0:
            logger.error(
                f"Simulation {simulation_id} day {simulation.current_day}: "
                f"positions_value is negative: {positions_value}"
            )
            raise ValueError(f"Accounting error: positions_value is negative ({positions_value})")

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

        simulation = await self.session.get(
            ArenaSimulation,
            simulation_id,
            options=[noload(ArenaSimulation.positions), noload(ArenaSimulation.snapshots)],
        )
        return simulation

    # =========================================================================
    # Helper Methods
    # =========================================================================

    async def _init_drawdown_state(self, simulation: ArenaSimulation) -> None:
        """Initialize peak equity and max drawdown from existing snapshots.

        Called on first step_day() when resuming a simulation to reconstruct
        the incremental drawdown tracking state.
        """
        sim_id = simulation.id
        if sim_id in self._peak_equity:
            return  # Already initialized

        result = await self.session.execute(
            select(ArenaSnapshot.total_equity)
            .where(ArenaSnapshot.simulation_id == sim_id)
            .order_by(ArenaSnapshot.day_number)
        )
        equities = [row[0] for row in result.all()]

        # Use initial_capital as starting peak. On day 0, total_equity ==
        # initial_capital (no positions opened, cash == initial_capital),
        # so this is equivalent to the original equities[0] approach.
        peak = simulation.initial_capital
        max_dd = Decimal("0")
        for equity in equities:
            if equity > peak:
                peak = equity
            if peak > 0:
                dd = (peak - equity) / peak * 100
                max_dd = max(max_dd, dd)

        self._peak_equity[sim_id] = peak
        self._max_drawdown[sim_id] = max_dd

    async def _load_price_cache(
        self,
        simulation_id: int,
        symbols: list[str],
        start_date: date,
        end_date: date,
        lookback_days: int,
    ) -> None:
        """Load all price data into memory for a simulation.

        Called during initialization and lazy-loaded on resume.
        All subsequent price lookups use this cache instead of DB queries.

        Args:
            simulation_id: Simulation ID for cache key.
            symbols: List of symbols to load.
            start_date: Simulation start date.
            end_date: Simulation end date.
            lookback_days: Agent's required lookback period.

        Raises:
            ValueError: If any symbol fails to load (fail-fast approach).
        """
        if simulation_id in self._price_cache:
            return  # Already loaded

        data_start = start_date - timedelta(days=lookback_days + 30)

        # Create inner function for parallel fetching
        async def fetch_symbol_data(symbol: str) -> tuple[str, list[PriceBar]]:
            """Fetch and transform data for a single symbol.

            Returns:
                Tuple of (symbol, price_bars)

            Raises:
                Exception: Any error during fetch/transform propagates
            """
            records = await self.data_service.get_price_data(
                symbol=symbol,
                start_date=datetime.combine(
                    data_start, datetime.min.time(), tzinfo=timezone.utc
                ),
                end_date=datetime.combine(
                    end_date, datetime.max.time(), tzinfo=timezone.utc
                ),
                interval="1d",
            )
            price_bars = [
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
            return (symbol, price_bars)

        # Execute all fetches concurrently (fail-fast on any error)
        tasks = [fetch_symbol_data(symbol) for symbol in symbols]
        results = await asyncio.gather(*tasks)

        # Build cache from results
        cache: dict[str, list[PriceBar]] = {symbol: bars for symbol, bars in results}
        self._price_cache[simulation_id] = cache

    @staticmethod
    def _symbols_for_cache(symbols: list[str], agent_config: dict) -> list[str]:
        """Return the full symbol list to load into the price cache.

        Adds the regime symbol when the regime filter is enabled, so it is
        fetched alongside simulation symbols in a single parallel batch.
        Deduplicates to avoid a redundant fetch when the regime symbol is
        already in the simulation symbol list.

        Args:
            symbols: Simulation symbol list.
            agent_config: Simulation agent configuration dict.

        Returns:
            Deduplicated list of symbols to load into the price cache.
        """
        if not agent_config.get("regime_filter"):
            return symbols
        regime_symbol: str = agent_config.get("regime_symbol", "SPY")
        if regime_symbol in symbols:
            return symbols
        return [*symbols, regime_symbol]

    def _get_regime(
        self,
        simulation_id: int,
        regime_symbol: str,
        current_date: date,
        sma_period: int,
    ) -> str:
        """Thin wrapper around _detect_market_regime for use inside step_day.

        Args:
            simulation_id: Simulation ID for cache lookup.
            regime_symbol: Ticker to use as regime indicator.
            current_date: Current simulation date (inclusive upper bound).
            sma_period: SMA period for regime detection.

        Returns:
            'bull', 'bear', or 'neutral'.
        """
        return self._detect_market_regime(simulation_id, current_date, regime_symbol, sma_period)

    async def _load_regime_symbol_cache(
        self,
        simulation_id: int,
        regime_symbol: str,
        start_date: date,
        end_date: date,
        sma_period: int,
    ) -> None:
        """Fetch regime symbol (e.g. SPY) into the price cache with SMA lookback.

        Merges into the existing cache without overwriting simulation symbol data.
        The regime symbol is deliberately not added to simulation.symbols so it
        never participates in position or trading-day logic.

        Args:
            simulation_id: Simulation ID for cache key.
            regime_symbol: Ticker to use as regime indicator (e.g. 'SPY').
            start_date: Simulation start date.
            end_date: Simulation end date.
            sma_period: SMA period; extra lookback = sma_period * 2 + 30 days.
        """
        cache = self._price_cache.setdefault(simulation_id, {})
        if regime_symbol in cache:
            return  # Already loaded

        extra_lookback = sma_period * 2 + 30
        data_start = start_date - timedelta(days=extra_lookback)

        records = await self.data_service.get_price_data(
            symbol=regime_symbol,
            start_date=datetime.combine(data_start, datetime.min.time(), tzinfo=timezone.utc),
            end_date=datetime.combine(end_date, datetime.max.time(), tzinfo=timezone.utc),
            interval="1d",
        )
        bars = [
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
        cache[regime_symbol] = bars
        logger.debug(
            f"Simulation {simulation_id}: loaded {len(bars)} {regime_symbol} bars for regime filter"
        )

    def _detect_market_regime(
        self,
        simulation_id: int,
        current_date: date,
        regime_symbol: str,
        sma_period: int,
    ) -> str:
        """Detect market regime using regime symbol close vs its SMA.

        No look-ahead: only uses bars up to and including current_date.

        Args:
            simulation_id: Simulation ID for cache lookup.
            current_date: The current simulation date (inclusive upper bound).
            regime_symbol: Ticker to look up in price cache (e.g. 'SPY').
            sma_period: Number of periods for the simple moving average.

        Returns:
            'bull' if close > SMA(period), 'bear' otherwise.
            'neutral' if insufficient data.
        """
        bars = self._get_cached_price_history(
            simulation_id,
            regime_symbol,
            current_date - timedelta(days=sma_period * 2 + 30),
            current_date,
        )
        if len(bars) < sma_period:
            logger.debug(
                f"Simulation {simulation_id}: insufficient {regime_symbol} bars "
                f"({len(bars)} < {sma_period}) for regime on {current_date}, defaulting to neutral"
            )
            return "neutral"

        recent_closes = [float(b.close) for b in bars[-sma_period:]]
        sma = sum(recent_closes) / len(recent_closes)
        spy_close = float(bars[-1].close)
        regime = "bull" if spy_close > sma else "bear"
        logger.debug(
            f"Simulation {simulation_id}: {regime_symbol} regime={regime} "
            f"close={spy_close:.2f} sma{sma_period}={sma:.2f} on {current_date}"
        )
        return regime

    async def _load_sector_cache(self, simulation_id: int, symbols: list[str]) -> None:
        """Batch-load sector data for all symbols. One query, no Yahoo API calls.

        Symbols not found in the DB are stored as None and treated as their own
        unique sector by the portfolio selector (never blocked by a sector cap).

        Args:
            simulation_id: Simulation ID for cache key.
            symbols: List of symbols to look up.
        """
        if simulation_id in self._sector_cache:
            return  # Already loaded

        result = await self.session.execute(
            select(StockSector.symbol, StockSector.sector).where(
                StockSector.symbol.in_(symbols)
            )
        )
        sector_map = {row.symbol: row.sector for row in result.all()}
        # Symbols not in DB → None (treated as unique sector by selector)
        self._sector_cache[simulation_id] = {s: sector_map.get(s) for s in symbols}

    def _calculate_symbol_atr_pct(
        self, simulation_id: int, symbol: str, current_date: date
    ) -> float | None:
        """Calculate ATR% for a symbol from cached price data.

        Uses a 90-day window (enough for 14-period Wilder's ATR).
        Returns None if insufficient price data is available.

        Args:
            simulation_id: Simulation ID for cache lookup.
            symbol: Stock symbol.
            current_date: The current simulation date (end of window).

        Returns:
            ATR as a percentage of price (e.g., 4.25 for 4.25%), or None.
        """
        price_history = self._get_cached_price_history(
            simulation_id,
            symbol,
            current_date - timedelta(days=90),
            current_date,
        )
        if not price_history or len(price_history) < 15:
            return None
        highs = [float(bar.high) for bar in price_history]
        lows = [float(bar.low) for bar in price_history]
        closes = [float(bar.close) for bar in price_history]
        return calculate_atr_percentage(highs, lows, closes)

    def _get_cached_price_history(
        self, simulation_id: int, symbol: str, start: date, end: date
    ) -> list[PriceBar]:
        """Get price history from in-memory cache with date filtering."""
        all_bars = self._price_cache.get(simulation_id, {}).get(symbol, [])
        return [b for b in all_bars if start <= b.date <= end]

    def _get_cached_bar_for_date(
        self, simulation_id: int, symbol: str, target_date: date
    ) -> PriceBar | None:
        """Get single bar from in-memory cache."""
        all_bars = self._price_cache.get(simulation_id, {}).get(symbol, [])
        for bar in reversed(all_bars):
            if bar.date == target_date:
                return bar
        return None

    def _get_trading_days_from_cache(
        self, simulation_id: int, start: date, end: date
    ) -> list[date]:
        """Get trading days from price cache.

        Args:
            simulation_id: Simulation ID.
            start: Start date.
            end: End date.

        Returns:
            Sorted list of trading dates where we have data for at least one symbol.
        """
        all_dates: set[date] = set()
        symbol_cache = self._price_cache.get(simulation_id, {})
        for bars in symbol_cache.values():
            for bar in bars:
                if start <= bar.date <= end:
                    all_dates.add(bar.date)
        return sorted(all_dates)

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

    async def _get_latest_snapshot(self, simulation_id: int) -> ArenaSnapshot | None:
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

    async def _get_open_positions(self, simulation_id: int) -> Sequence[ArenaPosition]:
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

    async def _close_all_positions(
        self, simulation: ArenaSimulation, close_date: date, reason: ExitReason
    ) -> list[ArenaPosition]:
        """Close all open positions at end of simulation.

        Args:
            simulation: Simulation object.
            close_date: Date to close positions.
            reason: Exit reason for all positions.

        Returns:
            List of all positions that were open (now closed).
        """
        open_positions = await self._get_open_positions(simulation.id)

        for position in open_positions:
            bar = self._get_cached_bar_for_date(simulation.id, position.symbol, close_date)
            if not bar:
                logger.warning(
                    "No price bar found for %s on %s — position %d left unclosed",
                    position.symbol,
                    close_date,
                    position.id,
                )
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

        return list(open_positions)

    def clear_simulation_cache(self, simulation_id: int) -> None:
        """Clear all in-memory caches for a completed simulation.

        Caches are per-engine-instance and not thread-safe by design.
        Each ArenaWorker creates one engine per simulation and runs
        sequentially, so no concurrency issues exist.
        """
        self._price_cache.pop(simulation_id, None)
        self._trading_days_cache.pop(simulation_id, None)
        self._peak_equity.pop(simulation_id, None)
        self._max_drawdown.pop(simulation_id, None)
        self._sector_cache.pop(simulation_id, None)

    async def _get_all_snapshots(self, simulation_id: int) -> list[ArenaSnapshot]:
        """Get all snapshots for a simulation ordered by day number.

        Args:
            simulation_id: Simulation ID.

        Returns:
            List of snapshots ordered by day_number ascending.
        """
        result = await self.session.execute(
            select(ArenaSnapshot)
            .where(ArenaSnapshot.simulation_id == simulation_id)
            .order_by(ArenaSnapshot.day_number)
        )
        return list(result.scalars().all())

    async def _finalize_simulation(
        self, simulation: ArenaSimulation, positions: list[ArenaPosition]
    ) -> None:
        """Compute analytics, mark simulation as completed, and commit.

        Args:
            simulation: Simulation to finalize.
            positions: Closed positions used to compute analytics metrics.
        """
        snapshots = await self._get_all_snapshots(simulation.id)
        compute_simulation_analytics(simulation, positions, snapshots)

        simulation.status = SimulationStatus.COMPLETED.value
        await self.session.commit()
        self.clear_simulation_cache(simulation.id)  # Free memory
        logger.info(
            f"Simulation {simulation.id} completed: "
            f"{simulation.total_trades} trades, "
            f"return {simulation.total_return_pct}%"
        )
