"""Alert monitor background service.

Periodically checks all active, non-paused alerts, computes their current state
using technical indicators, and persists status transitions as AlertEvent records.

Design decisions:
- DataService is instantiated per cycle (not at construction time) to prevent
  stale connections.
- Price data is fetched sequentially per symbol to respect Yahoo rate limits.
  Internal DataService caching ensures each symbol is fetched only once even if
  multiple alerts share the same symbol.
- A concurrent-run guard prevents overlapping cycles when computation takes longer
  than the configured interval.
- Each alert uses its own DB session/transaction for error isolation.
- Errors in one alert do not crash the cycle for other alerts.
- The monitor is a pure async service with no FastAPI dependency.
"""
import asyncio
import logging
from collections import defaultdict
from typing import Any

from app.core.config import get_settings
from app.repositories.alert_repository import AlertRepository
from app.services.alert_service import AlertService
from app.services.data_service import DataService

logger = logging.getLogger(__name__)
settings = get_settings()


class AlertMonitorService:
    """Background service that periodically computes and persists alert state.

    Lifecycle:
        monitor = AlertMonitorService(session_factory, provider)
        task = asyncio.create_task(monitor.start())
        # ... on shutdown:
        await monitor.stop()
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
    """

    def __init__(self, session_factory: Any, provider: Any) -> None:
        """Initialise with a session factory and market data provider.

        Args:
            session_factory: async_sessionmaker used to open short-lived DB sessions.
            provider: MarketDataProviderInterface (e.g., YahooFinanceProvider).
        """
        self._running = False
        self._running_cycle = False
        self._session_factory = session_factory
        self._provider = provider

    async def start(self) -> None:
        """Enter the monitoring loop.

        Runs until stop() is called. Each iteration:
        1. Runs a monitoring cycle (with concurrent-run guard).
        2. Sleeps for alert_monitor_interval seconds.

        Exceptions from individual cycles are caught and logged; the loop
        continues unless stop() has been called.
        """
        self._running = True
        logger.info(
            f"AlertMonitorService starting "
            f"(interval={settings.alert_monitor_interval}s, "
            f"batch_size={settings.alert_monitor_batch_size})"
        )
        while self._running:
            try:
                await self._run_cycle()
            except Exception:
                logger.exception("Alert monitor cycle failed")
            await asyncio.sleep(settings.alert_monitor_interval)

    async def stop(self) -> None:
        """Signal the monitoring loop to exit after the current sleep."""
        self._running = False
        logger.info("AlertMonitorService stopping")

    async def _run_cycle(self) -> None:
        """Execute one monitoring cycle with concurrent-run guard.

        If a previous cycle is still running, this invocation is skipped with a
        warning log. This prevents runaway memory and resource growth when
        computation takes longer than the configured interval (R17).
        """
        if self._running_cycle:
            logger.warning(
                "Previous monitor cycle still running, skipping this interval"
            )
            return

        self._running_cycle = True
        try:
            await self._run_cycle_inner()
        finally:
            self._running_cycle = False

    async def _run_cycle_inner(self) -> None:
        """Core monitoring logic: fetch, compute, and persist alert states.

        Flow:
        1. Fetch all active, non-paused alerts (single short-lived session).
        2. Group by symbol.
        3. Truncate to alert_monitor_batch_size symbols.
        4. For each symbol: fetch price data once; then compute and persist each
           alert's state in its own session/transaction.
        """
        # DataService is instantiated per cycle to prevent stale connections (R8)
        data_service = DataService(
            session_factory=self._session_factory,
            provider=self._provider,
        )

        # Fetch alerts in a short-lived session
        async with self._session_factory() as session:
            repo = AlertRepository(session)
            alerts = await repo.list_active_unpaused()

        if not alerts:
            logger.debug("No active alerts to process")
            return

        # Group by symbol to share one price fetch per symbol
        alerts_by_symbol: dict[str, list] = defaultdict(list)
        for alert in alerts:
            alerts_by_symbol[alert.symbol].append(alert)

        # Batch size limit (R20): cap symbols per cycle to avoid thundering herd
        symbols_to_process = list(alerts_by_symbol.keys())[
            : settings.alert_monitor_batch_size
        ]

        logger.info(
            f"Alert monitor cycle: {len(alerts)} alerts across "
            f"{len(alerts_by_symbol)} symbols, "
            f"processing {len(symbols_to_process)} this cycle"
        )

        alert_service = AlertService(self._session_factory, self._provider)

        # Sequential per symbol (O2): respects Yahoo Finance rate limits
        for symbol in symbols_to_process:
            symbol_alerts = alerts_by_symbol[symbol]

            try:
                price_data = await data_service.get_price_data(symbol, interval="1d")
            except Exception:
                logger.exception(
                    f"Failed to fetch price data for {symbol}, skipping symbol"
                )
                continue

            # Per-alert error isolation (R1) with per-alert DB session (R21)
            for alert in symbol_alerts:
                try:
                    new_state = await alert_service.compute_alert_state(
                        alert, price_data
                    )
                    async with self._session_factory() as session:
                        repo = AlertRepository(session)
                        await repo.update_state(alert.id, new_state)
                        for event in new_state.get("events", []):
                            await repo.create_event(alert.id, event)
                        if new_state.get("events"):
                            await repo.update_last_triggered(alert.id)
                        await session.commit()
                except Exception:
                    logger.exception(
                        f"Alert id={alert.id} ({alert.symbol}) failed during cycle"
                    )
