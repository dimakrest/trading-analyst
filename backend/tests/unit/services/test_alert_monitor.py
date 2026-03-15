"""Unit tests for AlertMonitorService.

Tests:
1. test_run_cycle_processes_active_alerts
2. test_run_cycle_groups_by_symbol -- single price fetch per symbol
3. test_run_cycle_persists_state
4. test_run_cycle_creates_events
5. test_run_cycle_handles_data_error -- other symbols still processed
6. test_run_cycle_isolates_alert_errors -- one alert error doesn't prevent others
7. test_stop_exits_loop
8. test_concurrent_cycle_guard
9. test_batch_size_limits_symbols
"""

import asyncio
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

from app.models.alert import StockAlert
from app.services.alert_monitor import AlertMonitorService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_alert(
    alert_id: int = 1,
    symbol: str = "AAPL",
    alert_type: str = "fibonacci",
    status: str = "no_structure",
    config: dict | None = None,
) -> MagicMock:
    """Build a mock StockAlert with sensible attribute defaults."""
    alert = MagicMock(spec=StockAlert)
    alert.id = alert_id
    alert.symbol = symbol
    alert.alert_type = alert_type
    alert.status = status
    alert.config = config or {}
    alert.computed_state = None
    alert.is_active = True
    alert.is_paused = False
    alert.last_triggered_at = None
    alert.deleted_at = None
    alert.events = []
    return alert


def _make_session_factory():
    """Return a mock session_factory."""
    session = AsyncMock()
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    session.commit = AsyncMock()
    session.add = MagicMock()
    session.execute = AsyncMock()

    factory = MagicMock()
    factory.return_value.__aenter__ = AsyncMock(return_value=session)
    factory.return_value.__aexit__ = AsyncMock(return_value=False)
    return factory, session


@pytest.fixture
def mock_provider():
    return MagicMock()


@pytest.fixture
def session_factory_and_session():
    return _make_session_factory()


@pytest.fixture
def monitor(session_factory_and_session, mock_provider):
    factory, _ = session_factory_and_session
    return AlertMonitorService(factory, mock_provider)


_COMPUTED_STATE_WITH_EVENT = {
    "status": "at_level",
    "computed_state": {"swing_high": 140.0, "swing_low": 110.0},
    "events": [
        {
            "event_type": "level_hit",
            "previous_status": "retracing",
            "new_status": "at_level",
            "price_at_event": 125.0,
            "details": {"level_pct": 50.0, "level_price": 125.0},
        }
    ],
}

_COMPUTED_STATE_NO_EVENT = {
    "status": "retracing",
    "computed_state": {},
    "events": [],
}


# ---------------------------------------------------------------------------
# 1. test_run_cycle_processes_active_alerts
# ---------------------------------------------------------------------------


class TestRunCycleProcessesActiveAlerts:
    @pytest.mark.asyncio
    async def test_run_cycle_processes_active_alerts(self, monitor):
        """Fetches only active, non-paused alerts and processes them."""
        active_alert = _make_alert(alert_id=1, symbol="AAPL")

        with (
            patch(
                "app.services.alert_monitor.AlertRepository.list_active_unpaused",
                new_callable=AsyncMock,
                return_value=[active_alert],
            ),
            patch(
                "app.services.alert_monitor.DataService.get_price_data",
                new_callable=AsyncMock,
                return_value=[MagicMock()],
            ),
            patch(
                "app.services.alert_monitor.AlertService.compute_alert_state",
                new_callable=AsyncMock,
                return_value=_COMPUTED_STATE_NO_EVENT,
            ),
            patch(
                "app.services.alert_monitor.AlertRepository.update_state",
                new_callable=AsyncMock,
            ) as mock_update,
        ):
            await monitor._run_cycle_inner()

        mock_update.assert_awaited_once_with(1, _COMPUTED_STATE_NO_EVENT)


# ---------------------------------------------------------------------------
# 2. test_run_cycle_groups_by_symbol
# ---------------------------------------------------------------------------


class TestRunCycleGroupsBySymbol:
    @pytest.mark.asyncio
    async def test_run_cycle_groups_by_symbol(self, monitor):
        """Price data is fetched once per symbol even with multiple alerts."""
        alert1 = _make_alert(alert_id=1, symbol="AAPL")
        alert2 = _make_alert(alert_id=2, symbol="AAPL")
        alert3 = _make_alert(alert_id=3, symbol="NVDA")

        with (
            patch(
                "app.services.alert_monitor.AlertRepository.list_active_unpaused",
                new_callable=AsyncMock,
                return_value=[alert1, alert2, alert3],
            ),
            patch(
                "app.services.alert_monitor.DataService.get_price_data",
                new_callable=AsyncMock,
                return_value=[MagicMock()],
            ) as mock_price,
            patch(
                "app.services.alert_monitor.AlertService.compute_alert_state",
                new_callable=AsyncMock,
                return_value=_COMPUTED_STATE_NO_EVENT,
            ),
            patch(
                "app.services.alert_monitor.AlertRepository.update_state",
                new_callable=AsyncMock,
            ),
        ):
            await monitor._run_cycle_inner()

        # Two symbols: AAPL and NVDA => two price fetches total
        assert mock_price.await_count == 2
        symbols_fetched = {c.args[0] for c in mock_price.await_args_list}
        assert symbols_fetched == {"AAPL", "NVDA"}


# ---------------------------------------------------------------------------
# 3. test_run_cycle_persists_state
# ---------------------------------------------------------------------------


class TestRunCyclePersistsState:
    @pytest.mark.asyncio
    async def test_run_cycle_persists_state(self, monitor):
        """Computed state is written to the database via update_state."""
        alert = _make_alert(alert_id=42, symbol="TSLA")

        with (
            patch(
                "app.services.alert_monitor.AlertRepository.list_active_unpaused",
                new_callable=AsyncMock,
                return_value=[alert],
            ),
            patch(
                "app.services.alert_monitor.DataService.get_price_data",
                new_callable=AsyncMock,
                return_value=[MagicMock()],
            ),
            patch(
                "app.services.alert_monitor.AlertService.compute_alert_state",
                new_callable=AsyncMock,
                return_value=_COMPUTED_STATE_NO_EVENT,
            ),
            patch(
                "app.services.alert_monitor.AlertRepository.update_state",
                new_callable=AsyncMock,
            ) as mock_update,
        ):
            await monitor._run_cycle_inner()

        mock_update.assert_awaited_once_with(42, _COMPUTED_STATE_NO_EVENT)


# ---------------------------------------------------------------------------
# 4. test_run_cycle_creates_events
# ---------------------------------------------------------------------------


class TestRunCycleCreatesEvents:
    @pytest.mark.asyncio
    async def test_run_cycle_creates_events(self, monitor):
        """When new_state has events, create_event is called and last_triggered_at updated."""
        alert = _make_alert(alert_id=5, symbol="MSFT")

        with (
            patch(
                "app.services.alert_monitor.AlertRepository.list_active_unpaused",
                new_callable=AsyncMock,
                return_value=[alert],
            ),
            patch(
                "app.services.alert_monitor.DataService.get_price_data",
                new_callable=AsyncMock,
                return_value=[MagicMock()],
            ),
            patch(
                "app.services.alert_monitor.AlertService.compute_alert_state",
                new_callable=AsyncMock,
                return_value=_COMPUTED_STATE_WITH_EVENT,
            ),
            patch(
                "app.services.alert_monitor.AlertRepository.update_state",
                new_callable=AsyncMock,
            ),
            patch(
                "app.services.alert_monitor.AlertRepository.create_event",
                new_callable=AsyncMock,
            ) as mock_create_event,
            patch(
                "app.services.alert_monitor.AlertRepository.update_last_triggered",
                new_callable=AsyncMock,
            ) as mock_update_last,
        ):
            await monitor._run_cycle_inner()

        mock_create_event.assert_awaited_once()
        event_arg = mock_create_event.call_args.args[1]
        assert event_arg["event_type"] == "level_hit"

        mock_update_last.assert_awaited_once_with(5)


# ---------------------------------------------------------------------------
# 5. test_run_cycle_handles_data_error
# ---------------------------------------------------------------------------


class TestRunCycleHandlesDataError:
    @pytest.mark.asyncio
    async def test_run_cycle_handles_data_error(self, monitor):
        """When price fetch fails for one symbol, other symbols are still processed."""
        alert_aapl = _make_alert(alert_id=1, symbol="AAPL")
        alert_nvda = _make_alert(alert_id=2, symbol="NVDA")

        fetch_call_count = 0

        async def fake_get_price_data(symbol, interval="1d"):
            nonlocal fetch_call_count
            fetch_call_count += 1
            if symbol == "AAPL":
                raise RuntimeError("Yahoo API timeout")
            return [MagicMock()]

        with (
            patch(
                "app.services.alert_monitor.AlertRepository.list_active_unpaused",
                new_callable=AsyncMock,
                return_value=[alert_aapl, alert_nvda],
            ),
            patch(
                "app.services.alert_monitor.DataService.get_price_data",
                new_callable=AsyncMock,
                side_effect=fake_get_price_data,
            ),
            patch(
                "app.services.alert_monitor.AlertService.compute_alert_state",
                new_callable=AsyncMock,
                return_value=_COMPUTED_STATE_NO_EVENT,
            ),
            patch(
                "app.services.alert_monitor.AlertRepository.update_state",
                new_callable=AsyncMock,
            ) as mock_update,
        ):
            await monitor._run_cycle_inner()

        # AAPL failed, but NVDA was still processed
        assert fetch_call_count == 2
        mock_update.assert_awaited_once()
        call_alert_id = mock_update.call_args.args[0]
        assert call_alert_id == 2  # NVDA alert


# ---------------------------------------------------------------------------
# 6. test_run_cycle_isolates_alert_errors
# ---------------------------------------------------------------------------


class TestRunCycleIsolatesAlertErrors:
    @pytest.mark.asyncio
    async def test_run_cycle_isolates_alert_errors(self, monitor):
        """One alert throwing during compute does not prevent other alerts from processing."""
        alert1 = _make_alert(alert_id=1, symbol="AAPL")
        alert2 = _make_alert(alert_id=2, symbol="AAPL")
        alert3 = _make_alert(alert_id=3, symbol="AAPL")

        call_count = 0

        async def fake_compute(alert, price_data):
            nonlocal call_count
            call_count += 1
            if alert.id == 2:
                raise RuntimeError("Computation exploded on alert 2")
            return _COMPUTED_STATE_NO_EVENT

        with (
            patch(
                "app.services.alert_monitor.AlertRepository.list_active_unpaused",
                new_callable=AsyncMock,
                return_value=[alert1, alert2, alert3],
            ),
            patch(
                "app.services.alert_monitor.DataService.get_price_data",
                new_callable=AsyncMock,
                return_value=[MagicMock()],
            ),
            patch(
                "app.services.alert_monitor.AlertService.compute_alert_state",
                new_callable=AsyncMock,
                side_effect=fake_compute,
            ),
            patch(
                "app.services.alert_monitor.AlertRepository.update_state",
                new_callable=AsyncMock,
            ) as mock_update,
        ):
            await monitor._run_cycle_inner()

        # All 3 alerts attempted; alert 2 failed but 1 and 3 succeeded
        assert call_count == 3
        assert mock_update.await_count == 2
        updated_ids = {c.args[0] for c in mock_update.await_args_list}
        assert updated_ids == {1, 3}


# ---------------------------------------------------------------------------
# 7. test_stop_exits_loop
# ---------------------------------------------------------------------------


class TestStopExitsLoop:
    @pytest.mark.asyncio
    async def test_stop_exits_loop(self, monitor):
        """Calling stop() breaks the monitoring loop."""
        cycle_count = 0

        async def fake_run_cycle():
            nonlocal cycle_count
            cycle_count += 1
            # After the first cycle, stop the monitor
            if cycle_count >= 1:
                await monitor.stop()

        with (
            patch.object(monitor, "_run_cycle", side_effect=fake_run_cycle),
            patch("app.services.alert_monitor.asyncio.sleep", new_callable=AsyncMock),
        ):
            await monitor.start()

        assert not monitor._running
        assert cycle_count >= 1


# ---------------------------------------------------------------------------
# 8. test_concurrent_cycle_guard
# ---------------------------------------------------------------------------


class TestConcurrentCycleGuard:
    @pytest.mark.asyncio
    async def test_concurrent_cycle_guard(self, monitor):
        """Second _run_cycle call returns immediately if previous is still running (R17)."""
        inner_call_count = 0
        gate = asyncio.Event()

        async def slow_inner():
            nonlocal inner_call_count
            inner_call_count += 1
            await gate.wait()  # Block until released

        with patch.object(monitor, "_run_cycle_inner", side_effect=slow_inner):
            # Start first cycle — it will block on gate
            task1 = asyncio.create_task(monitor._run_cycle())
            # Give it a moment to set _running_cycle = True
            await asyncio.sleep(0)

            # Now run the second _run_cycle; should skip immediately
            await monitor._run_cycle()

            # Release the gate so task1 can finish
            gate.set()
            await task1

        # Inner was called exactly once — second invocation was skipped
        assert inner_call_count == 1


# ---------------------------------------------------------------------------
# 9. test_batch_size_limits_symbols
# ---------------------------------------------------------------------------


class TestBatchSizeLimitsSymbols:
    @pytest.mark.asyncio
    async def test_batch_size_limits_symbols(self, monitor):
        """With 60 alerts across 60 symbols and batch_size=50, only 50 are processed."""
        alerts = [
            _make_alert(alert_id=i, symbol=f"SYM{i:03d}")
            for i in range(1, 61)
        ]

        with (
            patch(
                "app.services.alert_monitor.AlertRepository.list_active_unpaused",
                new_callable=AsyncMock,
                return_value=alerts,
            ),
            patch(
                "app.services.alert_monitor.DataService.get_price_data",
                new_callable=AsyncMock,
                return_value=[MagicMock()],
            ) as mock_price,
            patch(
                "app.services.alert_monitor.AlertService.compute_alert_state",
                new_callable=AsyncMock,
                return_value=_COMPUTED_STATE_NO_EVENT,
            ),
            patch(
                "app.services.alert_monitor.AlertRepository.update_state",
                new_callable=AsyncMock,
            ),
            patch(
                "app.services.alert_monitor.settings",
                alert_monitor_batch_size=50,
                alert_monitor_interval=300,
            ),
        ):
            await monitor._run_cycle_inner()

        # Only 50 symbols should be fetched
        assert mock_price.await_count == 50
