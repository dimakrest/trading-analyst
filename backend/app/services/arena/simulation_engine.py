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
from app.models.stock_sector import StockSector
from app.services.arena.agent_protocol import AgentDecision, PriceBar
from app.services.arena.analytics import compute_simulation_analytics
from app.services.arena.agent_registry import get_agent
from app.services.arena.trailing_stop import AtrTrailingStop, FixedPercentTrailingStop
from app.services.data_service import DataService
from app.services.portfolio_selector import EnrichedScoreSelector, QualifyingSignal, get_selector
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

    # Below 1bp indicates missing or corrupt ATR data, not genuine low volatility.
    _MIN_ATR_PCT = 0.01

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
        # Cache window metadata used by _load_auxiliary_symbol_cache to detect under-coverage.
        # Structure: {simulation_id: {symbol: {"data_start": date, "data_end": date}}}
        self._price_cache_meta: dict[int, dict[str, dict[str, date]]] = {}
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
        # Pre-load auxiliary symbols required by optional filters (regime, circuit breaker, MA50).
        await self._load_filter_auxiliary_caches(
            simulation.id,
            simulation.agent_config,
            simulation.start_date,
            simulation.end_date,
            simulation_symbols=simulation.symbols,
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

        # Position sizing config — read all sizing-related fields once
        position_size_pct: float | None = simulation.agent_config.get("position_size_pct")
        # Resolve sizing_mode: explicit > legacy position_size_pct > fixed.
        # Legacy simulations may have position_size_pct without sizing_mode;
        # treat them as fixed_pct for backward compatibility.
        sizing_mode: str = simulation.agent_config.get("sizing_mode") or (
            "fixed_pct" if position_size_pct is not None else "fixed"
        )
        risk_per_trade_pct: Decimal = Decimal(
            str(simulation.agent_config.get("risk_per_trade_pct", 2.5))
        )
        win_streak_bonus_pct: Decimal = Decimal(
            str(simulation.agent_config.get("win_streak_bonus_pct", 0.3))
        )
        max_risk_pct: Decimal = Decimal(
            str(simulation.agent_config.get("max_risk_pct", 4.0))
        )

        # Ensure price cache is loaded (handles resume case)
        if simulation_id not in self._price_cache:
            await self._load_price_cache(
                simulation_id,
                simulation.symbols,
                simulation.start_date,
                simulation.end_date,
                agent.required_lookback_days,
            )
            # Load auxiliary symbols required by optional filters (regime, circuit breaker, MA50).
            await self._load_filter_auxiliary_caches(
                simulation_id,
                simulation.agent_config,
                simulation.start_date,
                simulation.end_date,
                simulation_symbols=simulation.symbols,
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

        # Per-day ATR memoization: avoid recalculating ATR multiple times per symbol per day.
        _day_atr_cache: dict[str, float | None] = {}

        def _get_atr_for_day(symbol: str) -> float | None:
            if symbol not in _day_atr_cache:
                _day_atr_cache[symbol] = self._calculate_symbol_atr_pct(
                    simulation_id, symbol, current_date
                )
            return _day_atr_cache[symbol]

        # Compute current equity once before processing symbols (for equity-based sizing).
        # Doing this outside the loop avoids O(n²) and ensures the same equity
        # baseline is used for all pending positions opened on the same day.
        pos_value = Decimal("0")
        for pos in positions_by_symbol.values():
            if pos.status == PositionStatus.OPEN.value:
                pos_bar = self._get_cached_bar_for_date(
                    simulation_id, pos.symbol, current_date
                )
                if pos_bar:
                    pos_value += pos.shares * pos_bar.close
        current_equity = cash + pos_value

        # Determine effective_position_size for fixed/fixed_pct modes.
        # For risk_based mode the size is computed per-symbol at open time
        # because it depends on that symbol's ATR.
        if sizing_mode == "fixed_pct":
            # Schema validator guarantees position_size_pct is set when
            # sizing_mode='fixed_pct' goes through the API. The fallback to
            # simulation.position_size handles legacy/direct DB writes only.
            if position_size_pct is not None:
                effective_position_size = current_equity * (
                    Decimal(str(position_size_pct)) / Decimal("100")
                )
            else:
                effective_position_size = simulation.position_size
        else:
            # fixed or risk_based fallback default
            effective_position_size = simulation.position_size

        # Snapshot the win-streak counter at the start of the day so all
        # sizing decisions for "today" use the same value, regardless of
        # the order in which symbols are processed within the loop.
        # Without this snapshot, a winning close on symbol #1 would bleed
        # into the same-day sizing of symbol #2.
        streak_at_day_start = simulation.consecutive_wins

        # Build O(1) trading-day index lookup (used for max-hold-days checks).
        trading_days_idx: dict[date, int] = {d: i for i, d in enumerate(trading_days)}

        # Process each symbol
        decisions: dict[str, dict] = {}
        # Collect BUY signals for portfolio selection (processed after symbol loop)
        buy_signals: list[tuple[str, AgentDecision, PriceBar]] = []

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
                # Compute per-symbol position size for risk_based mode.
                # fixed/fixed_pct use the pre-computed effective_position_size.
                #
                # risk_skip_reason is set when risk-based sizing cannot honor
                # its risk promise for this symbol — the pending position will
                # be cancelled with INSUFFICIENT_DATA below rather than fall
                # back to a different size that doesn't reflect user intent.
                risk_skip_reason: str | None = None
                if sizing_mode == "risk_based":
                    # Schema validator guarantees stop_type='atr' (and therefore
                    # atr_trailing_stop is non-None) when sizing_mode='risk_based'.
                    assert atr_trailing_stop is not None, (
                        "atr_trailing_stop must be set when sizing_mode='risk_based'"
                    )

                    symbol_atr_pct = _get_atr_for_day(symbol)
                    if symbol_atr_pct is None or symbol_atr_pct < self._MIN_ATR_PCT:
                        # ATR data is missing/corrupt — we cannot compute the
                        # promised risk %, so refuse the trade rather than open
                        # a misleadingly-sized position. Logged in decisions[].
                        risk_skip_reason = (
                            f"Risk-based sizing requires ATR data; got "
                            f"{symbol_atr_pct} (min {self._MIN_ATR_PCT}%)"
                        )
                        symbol_effective_size = Decimal("0")
                    else:
                        # Use the SAME clamp the actual stop will use, so the
                        # risk math and the stop placement can never diverge.
                        clamped_pct = atr_trailing_stop.compute_clamped_pct(
                            symbol_atr_pct
                        )
                        stop_distance_per_share = today_bar.open * (
                            Decimal(str(clamped_pct)) / Decimal("100")
                        )

                        streak_bonus = (
                            Decimal(streak_at_day_start) * win_streak_bonus_pct
                        )
                        effective_risk = min(
                            risk_per_trade_pct + streak_bonus, max_risk_pct
                        )
                        risk_amount = current_equity * (
                            effective_risk / Decimal("100")
                        )
                        calculated_risk_shares = (
                            int(risk_amount / stop_distance_per_share)
                            if stop_distance_per_share > 0
                            else 0
                        )
                        raw_size = (
                            Decimal(calculated_risk_shares) * today_bar.open
                            if calculated_risk_shares > 0
                            else Decimal("0")
                        )
                        # Cap against actual buying power (cash), not total
                        # equity. Capping at equity over-states the buying
                        # power available and silently shifts the trade off
                        # the user-configured risk% — we log when this fires.
                        if raw_size > cash:
                            logger.info(
                                "Risk-based size capped by cash for %s on %s: "
                                "raw=%s cash=%s (risk%% no longer honored)",
                                symbol,
                                current_date,
                                raw_size,
                                cash,
                            )
                            symbol_effective_size = cash
                        else:
                            symbol_effective_size = raw_size
                else:
                    symbol_effective_size = effective_position_size

                # Calculate shares
                calculated_shares = int(symbol_effective_size / today_bar.open)
                cost = calculated_shares * today_bar.open if calculated_shares > 0 else Decimal("0")

                if risk_skip_reason is not None:
                    # Risk-based sizing refused to size this trade.
                    pending.status = PositionStatus.CLOSED.value
                    pending.exit_reason = ExitReason.INSUFFICIENT_DATA.value
                    pending.agent_reasoning = f"Position skipped: {risk_skip_reason}"
                elif calculated_shares < 1:
                    # Price too high for position size - cancel pending
                    pending.status = PositionStatus.CLOSED.value
                    pending.exit_reason = ExitReason.INSUFFICIENT_CAPITAL.value
                    pending.agent_reasoning = (
                        f"Position skipped: price ${today_bar.open} > "
                        f"position size ${symbol_effective_size:.2f}"
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

                    # Initialize trailing stop — ATR or fixed.
                    if atr_trailing_stop is not None:
                        symbol_atr_pct = _get_atr_for_day(symbol)
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
                    cash = self._close_position(
                        position=position,
                        simulation=simulation,
                        exit_reason=ExitReason.STOP_HIT,
                        exit_price=exit_price,
                        exit_date=current_date,
                        cash=cash,
                    )
                    del positions_by_symbol[symbol]
                else:
                    # Stop not triggered — update tracked high and stop level.
                    position.highest_price = update.highest_price
                    position.current_stop = update.stop_price

                    # --- Layer 8: Breakeven stop floor ---
                    # Once the position has gained enough, pin the stop at entry
                    # so a winner can never turn into a loser.
                    if breakeven_trigger_pct is not None and position.entry_price:
                        breakeven_threshold = position.entry_price * (
                            Decimal("1") + Decimal(str(breakeven_trigger_pct)) / Decimal("100")
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
                        ratchet_threshold = position.entry_price * (
                            Decimal("1") + Decimal(str(ratchet_trigger_pct)) / Decimal("100")
                        )
                        if position.highest_price >= ratchet_threshold:
                            ratchet_stop = position.highest_price * (
                                Decimal("1") - Decimal(str(ratchet_trail_pct)) / Decimal("100")
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
                            pos_atr_pct = _get_atr_for_day(symbol)
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
                            cash = self._close_position(
                                position=position,
                                simulation=simulation,
                                exit_reason=ExitReason.TAKE_PROFIT,
                                exit_price=exit_price,
                                exit_date=current_date,
                                cash=cash,
                            )
                            del positions_by_symbol[symbol]

                    # --- Layer 6: Max Holding Period ---
                    # Only check positions that are still open after stop and
                    # take-profit checks above.
                    if (
                        max_hold_days is not None
                        and symbol in positions_by_symbol
                        and position.entry_date is not None
                    ):
                        entry_idx = trading_days_idx.get(position.entry_date)
                        current_idx = trading_days_idx.get(current_date)
                        if entry_idx is None or current_idx is None:
                            hold_days = 0
                        else:
                            hold_days = current_idx - entry_idx

                        # Use extended hold for profitable positions
                        effective_hold_limit = max_hold_days
                        if (
                            max_hold_days_profit is not None
                            and position.entry_price
                            and today_bar.close > position.entry_price
                        ):
                            effective_hold_limit = max_hold_days_profit

                        if hold_days >= effective_hold_limit:
                            cash = self._close_position(
                                position=position,
                                simulation=simulation,
                                exit_reason=ExitReason.MAX_HOLD,
                                exit_price=today_bar.close,
                                exit_date=current_date,
                                cash=cash,
                            )
                            del positions_by_symbol[symbol]

            # Get agent decision (only if not already holding)
            has_position = symbol in positions_by_symbol
            decision = await agent.evaluate(symbol, price_history, current_date, has_position)

            decisions[symbol] = {
                "action": decision.action,
                "score": decision.score,
                "reasoning": decision.reasoning,
            }

            # Collect BUY signals for portfolio selection (don't create PENDING yet).
            # today_bar rides along so Layer 10 filters don't re-scan the price cache.
            if decision.action == "BUY" and not has_position:
                buy_signals.append((symbol, decision, today_bar))

        # --- Layer 10: Entry Filters ---
        # Filter order: circuit breaker (day-level gate) -> IBS (per-symbol) ->
        # MA50 (per-symbol) -> portfolio selection.
        # Circuit breaker is cheapest (one ATR calc), IBS is next (one bar lookup),
        # MA50 is most expensive (50-bar history). Early filters reduce work for later ones.
        # Note: when circuit breaker fires, IBS/MA50 don't run on empty buy_signals,
        # so filtered symbols show only circuit_breaker_filtered=True (no ibs_filtered
        # or ma50_filtered annotations). The absence of ma50_filtered on an
        # ibs_filtered symbol is NOT an implicit MA50 pass -- IBS caught it first.

        # --- Circuit Breaker ---
        # Declare before the block so these are in scope for snapshot construction.
        circuit_breaker_state: str = "disabled"
        circuit_breaker_atr_pct_today: float | None = None

        circuit_breaker_threshold = simulation.agent_config.get("circuit_breaker_atr_threshold")
        if circuit_breaker_threshold is not None:
            market_symbol = simulation.agent_config.get("circuit_breaker_symbol", "SPY")
            market_atr_pct = self._calculate_symbol_atr_pct(simulation_id, market_symbol, current_date)
            circuit_breaker_atr_pct_today = market_atr_pct  # record even when below threshold or None

            if market_atr_pct is None:
                # SPY data unavailable: fail-open so entries proceed, but make the
                # bypass explicit in state and logs so operators can see it.
                circuit_breaker_state = "data_unavailable"
                logger.warning(
                    "Circuit breaker skipped for simulation %s on %s: ATR unavailable for %s. "
                    "Entries proceed (fail-open). Check market-data feed health.",
                    simulation_id, current_date, market_symbol,
                )
            elif market_atr_pct >= circuit_breaker_threshold:
                circuit_breaker_state = "triggered"
                # Empty buy_signals is a no-op; the state column is the audit record.
                for symbol, _decision, _today_bar in buy_signals:
                    decisions[symbol]["circuit_breaker_filtered"] = True
                    decisions[symbol]["portfolio_selected"] = False
                buy_signals = []
            else:
                circuit_breaker_state = "clear"

        # --- IBS Filter ---
        # Prune BUY signals by Internal Bar Strength before portfolio selection.
        # IBS = (close - low) / (high - low); signals with IBS >= threshold are
        # filtered out (stock already near daily high). Zero-range days use
        # neutral IBS=0.5.
        ibs_max = simulation.agent_config.get("ibs_max_threshold")
        if ibs_max is not None:
            filtered_buy_signals: list[tuple[str, AgentDecision, PriceBar]] = []
            for symbol, decision, today_bar in buy_signals:
                if today_bar.high != today_bar.low:
                    ibs = float(
                        (today_bar.close - today_bar.low) / (today_bar.high - today_bar.low)
                    )
                else:
                    ibs = 0.5
                if ibs < ibs_max:
                    filtered_buy_signals.append((symbol, decision, today_bar))
                else:
                    decisions[symbol]["ibs_filtered"] = True
                    decisions[symbol]["ibs_value"] = round(ibs, 4)
                    decisions[symbol]["portfolio_selected"] = False
            buy_signals = filtered_buy_signals

        # --- MA50 Filter ---
        # Only buy stocks trading above their 50-day moving average (trend-following gate).
        # Inactive for symbols with <50 bars of history; logs debug for skipped evaluations.
        # Note: price_history from the agent evaluation loop is not in scope here --
        # must fetch from cache explicitly.
        ma50_filter_enabled = simulation.agent_config.get("ma50_filter_enabled", False)
        if ma50_filter_enabled:
            ma50_filtered_buy_signals: list[tuple[str, AgentDecision, PriceBar]] = []
            for symbol, decision, today_bar in buy_signals:
                ph = self._get_cached_price_history(
                    simulation_id, symbol,
                    current_date - timedelta(days=90), current_date,
                )
                # ph[-1].date == current_date is guaranteed for symbols in buy_signals
                # (agent loop NO_DATA guard), but checked explicitly for defensive
                # correctness against data gaps that could cause silent pricing errors.
                if ph and len(ph) >= 50 and ph[-1].date == current_date:
                    closes = [float(bar.close) for bar in ph[-50:]]
                    ma50 = sum(closes) / len(closes)
                    today_close = float(ph[-1].close)
                    if today_close < ma50:
                        decisions[symbol]["ma50_filtered"] = True
                        decisions[symbol]["portfolio_selected"] = False
                        continue
                else:
                    # Skip filter, allow entry. Possible reasons:
                    #   (a) empty cache — should not happen after Fix #3 pre-loads 90d;
                    #       emits a warning so any data-fetch failure is immediately visible.
                    #   (b) <50 bars — rare after Fix #3 but kept as defense-in-depth.
                    #   (c) stale bar — data gap where last cached bar predates current_date.
                    if not ph:
                        logger.warning(
                            "MA50 filter skipped for %s on %s: price cache is empty "
                            "(expected ≥50 bars after pre-load; check data fetch)",
                            symbol, current_date,
                        )
                    elif len(ph) < 50:
                        logger.debug(
                            "MA50 filter skipped for %s: only %d bars available",
                            symbol, len(ph),
                        )
                    elif ph[-1].date != current_date:
                        logger.debug(
                            "MA50 filter skipped for %s: last bar date %s != %s",
                            symbol, ph[-1].date, current_date,
                        )
                ma50_filtered_buy_signals.append((symbol, decision, today_bar))
            buy_signals = ma50_filtered_buy_signals

        # --- Portfolio Selection ---
        # Read strategy configuration from agent_config (defaults preserve original behavior)
        strategy_name = simulation.agent_config.get("portfolio_strategy", "none")
        max_per_sector: int | None = simulation.agent_config.get("max_per_sector")
        max_open_positions: int | None = simulation.agent_config.get("max_open_positions")

        # --- Layer 7: Market Regime Filter ---
        # Dynamically adjust max_open_positions based on regime symbol trend.
        # This runs AFTER reading the base max_open_positions so the bull regime
        # can optionally override it and the bear regime reduces it.
        # regime_state_value is also reused below for the snapshot column.
        regime_state_value: str | None = None
        if simulation.agent_config.get("regime_filter", False):
            regime_symbol: str = simulation.agent_config.get("regime_symbol", "SPY")
            sma_period: int = simulation.agent_config.get("regime_sma_period", 20)
            regime_state_value = self._detect_market_regime(
                simulation_id, current_date, regime_symbol, sma_period
            )
            if regime_state_value == "bear":
                bear_max: int = simulation.agent_config.get("regime_bear_max_positions", 1)
                max_open_positions = bear_max
            elif regime_state_value == "bull":
                bull_max: int | None = simulation.agent_config.get("regime_bull_max_positions")
                if bull_max is not None:
                    max_open_positions = bull_max
            # neutral: leave max_open_positions unchanged

        selector = get_selector(strategy_name)

        # Override ma_sweet_spot_center if configured for enriched selectors
        ma_sweet_spot_center = simulation.agent_config.get("ma_sweet_spot_center")
        if ma_sweet_spot_center is not None and isinstance(selector, EnrichedScoreSelector):
            selector = EnrichedScoreSelector(
                atr_preference=selector._atr_preference,
                ma_sweet_spot_center=ma_sweet_spot_center,
            )

        # Build qualifying signals with sector and ATR data from caches
        qualifying: list[QualifyingSignal] = []
        sim_sector_map = self._sector_cache.get(simulation_id, {})
        for symbol, decision, _today_bar in buy_signals:
            qualifying.append(
                QualifyingSignal(
                    symbol=symbol,
                    score=decision.score or 0,
                    sector=sim_sector_map.get(symbol),
                    atr_pct=_get_atr_for_day(symbol),
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
        for symbol, decision, _today_bar in buy_signals:
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

        # Create snapshot (regime_state_value computed in the regime filter block above)
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
            circuit_breaker_state=circuit_breaker_state,
            circuit_breaker_atr_pct=(
                Decimal(str(circuit_breaker_atr_pct_today))
                if circuit_breaker_atr_pct_today is not None
                else None
            ),
            regime_state=regime_state_value,
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


    async def _load_filter_auxiliary_caches(
        self,
        simulation_id: int,
        agent_config: dict,
        start_date: date,
        end_date: date,
        simulation_symbols: list[str] | None = None,
    ) -> None:
        """Load auxiliary symbols required by optional filters (regime, circuit breaker, MA50).

        Each filter is loaded only when enabled in agent_config. The underlying
        ``_load_auxiliary_symbol_cache`` is window-aware: if a symbol is already cached
        but the existing window starts later than requested, it tops up the missing prefix.

        MA50 filter requires ≥50 trading bars per symbol. 90 calendar days guarantees this:
        5 trading days / 7 calendar days × 90 ≈ 64 trading bars — a safe margin above 50.
        When ma50_filter_enabled=True and an agent's normal required_lookback_days + 30 < 90,
        we pre-load every simulation symbol with the full 90-day window here so the filter
        never silently skips evaluation. (circuit breaker follows the same pattern.)
        """
        if agent_config.get("regime_filter", False):
            sma_period = agent_config.get("regime_sma_period", 20)
            await self._load_auxiliary_symbol_cache(
                simulation_id,
                agent_config.get("regime_symbol", "SPY"),
                start_date,
                end_date,
                lookback_days=sma_period * 2 + 30,
            )
        if agent_config.get("circuit_breaker_atr_threshold") is not None:
            await self._load_auxiliary_symbol_cache(
                simulation_id,
                agent_config.get("circuit_breaker_symbol", "SPY"),
                start_date,
                end_date,
                lookback_days=90,
            )
        if agent_config.get("ma50_filter_enabled", False) and simulation_symbols:
            # Top up each simulation symbol to ≥90 calendar days of history so the
            # MA50 filter always has ≥50 trading bars available.
            for symbol in simulation_symbols:
                await self._load_auxiliary_symbol_cache(
                    simulation_id,
                    symbol,
                    start_date,
                    end_date,
                    lookback_days=90,
                )

    async def _load_auxiliary_symbol_cache(
        self,
        simulation_id: int,
        symbol: str,
        start_date: date,
        end_date: date,
        lookback_days: int,
    ) -> None:
        """Fetch symbol into the price cache with lookback, topping up if window is too short.

        Window-aware idempotence: if the symbol is already cached but its recorded
        ``data_start`` is later than the newly requested ``data_start``, the missing
        prefix is fetched and prepended. This prevents a second caller that needs a
        longer lookback (e.g. MA50 needing 90 d when the main cache only loaded 40 d)
        from silently receiving a truncated history.

        Simulation symbols loaded by the main ``_load_price_cache`` call are not tracked
        in ``_price_cache_meta`` initially; when MA50's aux-cache call arrives for those
        symbols, it is treated as the first call and seeds meta. The prepend-merge path
        only fires when the existing entry was loaded with a shorter window.

        Args:
            simulation_id: Simulation ID for cache key.
            symbol: Ticker to load.
            start_date: Simulation start date.
            end_date: Simulation end date.
            lookback_days: Extra historical days to load before start_date.
                Regime filter uses sma_period * 2 + 30; circuit breaker and MA50 use 90.
        """
        cache = self._price_cache.setdefault(simulation_id, {})
        meta = self._price_cache_meta.setdefault(simulation_id, {})
        requested_data_start = start_date - timedelta(days=lookback_days)

        if symbol in cache and symbol in meta:
            existing_data_start: date = meta[symbol]["data_start"]
            if existing_data_start <= requested_data_start:
                return  # Existing window already covers the requested range

            # Top up: fetch the missing prefix [requested_data_start, existing_data_start)
            prefix_end = existing_data_start - timedelta(days=1)
            if prefix_end < requested_data_start:
                return  # Nothing to fetch (gap is zero days)

            prefix_records = await self.data_service.get_price_data(
                symbol=symbol,
                start_date=datetime.combine(
                    requested_data_start, datetime.min.time(), tzinfo=timezone.utc
                ),
                end_date=datetime.combine(
                    prefix_end, datetime.max.time(), tzinfo=timezone.utc
                ),
                interval="1d",
            )
            prefix_bars = [
                PriceBar(
                    date=r.timestamp.date(),
                    open=Decimal(str(r.open_price)),
                    high=Decimal(str(r.high_price)),
                    low=Decimal(str(r.low_price)),
                    close=Decimal(str(r.close_price)),
                    volume=int(r.volume),
                )
                for r in prefix_records
            ]
            # Merge: prepend prefix, then sort ascending by date (defensive — prefix
            # should already precede existing bars, but sort ensures invariant holds).
            merged = sorted(prefix_bars + cache[symbol], key=lambda b: b.date)
            cache[symbol] = merged
            meta[symbol]["data_start"] = requested_data_start
            logger.debug(
                "Simulation %s: topped up %s cache by %d bars (new data_start=%s)",
                simulation_id, symbol, len(prefix_bars), requested_data_start,
            )
            return

        if symbol in cache:
            # Symbol was loaded by _load_price_cache (no meta entry yet); treat this
            # call as the first to seed meta. We do NOT know the exact data_start that
            # _load_price_cache used, so infer it from the oldest bar date in cache.
            existing_bars = cache[symbol]
            if existing_bars:
                inferred_start = existing_bars[0].date
                meta[symbol] = {"data_start": inferred_start, "data_end": end_date}
                if inferred_start <= requested_data_start:
                    return  # Main load already covers the requested window
            # Fall through to full fetch if cache is empty or window is insufficient

        data_start = requested_data_start

        records = await self.data_service.get_price_data(
            symbol=symbol,
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
        cache[symbol] = bars
        meta[symbol] = {"data_start": data_start, "data_end": end_date}
        logger.debug(
            "Simulation %s: loaded %d %s bars for auxiliary symbol cache (lookback_days=%d)",
            simulation_id, len(bars), symbol, lookback_days,
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
        regime_close = float(bars[-1].close)
        regime = "bull" if regime_close > sma else "bear"
        logger.debug(
            f"Simulation {simulation_id}: {regime_symbol} regime={regime} "
            f"close={regime_close:.2f} sma{sma_period}={sma:.2f} on {current_date}"
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

    def _close_position(
        self,
        position: ArenaPosition,
        simulation: ArenaSimulation,
        exit_reason: ExitReason,
        exit_price: Decimal,
        exit_date: date,
        cash: Decimal,
        update_streak: bool = True,
    ) -> Decimal:
        """Close a single position and update simulation counters.

        Sets all exit fields on the position, increments trade counters, and
        (optionally) updates the consecutive_wins streak. Returns the updated
        cash balance.

        Args:
            position: Open position to close. Must have entry_price and shares
                set (i.e. must have actually been opened).
            simulation: Parent simulation (counters updated in-place).
            exit_reason: Why the position was closed.
            exit_price: Price at which to exit.
            exit_date: Date of exit.
            cash: Current cash balance before this close.
            update_streak: When True (default), update consecutive_wins. Set
                to False from end-of-simulation force-closes so the streak
                counter reflects only trader-driven closes.

        Returns:
            Updated cash balance after receiving position proceeds.

        Raises:
            ValueError: If position.entry_price or position.shares is None
                (i.e. caller passed a position that was never opened).
        """
        if position.entry_price is None or position.shares is None:
            msg = (
                f"Cannot close position {position.id}: entry_price or shares "
                f"is None (entry_price={position.entry_price}, "
                f"shares={position.shares})"
            )
            raise ValueError(msg)

        realized_pnl = (exit_price - position.entry_price) * position.shares
        return_pct = (exit_price - position.entry_price) / position.entry_price * 100

        position.status = PositionStatus.CLOSED.value
        position.exit_date = exit_date
        position.exit_price = exit_price
        position.exit_reason = exit_reason.value
        position.realized_pnl = realized_pnl
        position.return_pct = return_pct

        simulation.total_trades += 1
        if realized_pnl > 0:
            simulation.winning_trades += 1
            if update_streak:
                simulation.consecutive_wins += 1
        elif update_streak:
            # Breakeven (pnl == 0) also resets streak — conservative by design.
            simulation.consecutive_wins = 0

        return cash + position.shares * exit_price

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

        # Pass cash=Decimal("0") because the returned cash balance is discarded
        # at end-of-simulation; final equity is recomputed in _finalize_simulation.
        # update_streak=False so the persisted consecutive_wins counter
        # reflects only trader-driven closes — forced end-of-sim exits should
        # not pollute analytics that read the field after finalization.
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

            self._close_position(
                position=position,
                simulation=simulation,
                exit_reason=reason,
                exit_price=bar.close,
                exit_date=close_date,
                cash=Decimal("0"),
                update_streak=False,
            )

        return list(open_positions)

    def clear_simulation_cache(self, simulation_id: int) -> None:
        """Clear all in-memory caches for a completed simulation.

        Caches are per-engine-instance and not thread-safe by design.
        Each ArenaWorker creates one engine per simulation and runs
        sequentially, so no concurrency issues exist.
        """
        self._price_cache.pop(simulation_id, None)
        self._price_cache_meta.pop(simulation_id, None)
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
