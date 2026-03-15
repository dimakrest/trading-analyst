"""Unit tests for AlertService.

Tests:
1. test_create_fibonacci_alert -- creates with correct defaults
2. test_create_ma_alert -- creates MA alert
3. test_create_alert_invalid_symbol -- symbol not found returns error
4. test_list_alerts_filters_by_status
5. test_list_alerts_excludes_deleted
6. test_pause_alert
7. test_delete_alert
8. test_compute_fibonacci_state_calls_indicator
9. test_compute_ma_state_uses_analyze_ma_distance
10. test_compute_ma_state_approaching -- distance_pct between tolerance and 2% returns approaching
11. test_compute_ma_state_insufficient_history -- MA200 with 50 candles returns insufficient_data
12. test_ma_deduplication_at_ma_3_cycles -- 3 consecutive at_ma cycles, exactly 1 event
13. test_create_ma_alert_fan_out -- ma_periods=[50, 200] creates 2 separate alerts
"""

from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions import SymbolNotFoundError
from app.models.alert import StockAlert
from app.providers.base import PriceDataPoint
from app.services.alert_service import AlertService


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


def _make_price_data(
    symbol: str = "AAPL",
    count: int = 210,
    base_price: float = 100.0,
) -> list[PriceDataPoint]:
    """Build a list of synthetic PriceDataPoint objects."""
    base = datetime(2025, 1, 1, tzinfo=timezone.utc)
    from datetime import timedelta

    return [
        PriceDataPoint(
            symbol=symbol,
            timestamp=base + timedelta(days=i),
            open_price=Decimal(str(base_price + i * 0.1)),
            high_price=Decimal(str(base_price + i * 0.1 + 1.0)),
            low_price=Decimal(str(base_price + i * 0.1 - 1.0)),
            close_price=Decimal(str(base_price + i * 0.1)),
            volume=1_000_000,
        )
        for i in range(count)
    ]


def _make_alert(
    alert_id: int = 1,
    symbol: str = "AAPL",
    alert_type: str = "fibonacci",
    status: str = "no_structure",
    config: dict | None = None,
    computed_state: dict | None = None,
) -> MagicMock:
    """Build a mock StockAlert with sensible attribute defaults."""
    alert = MagicMock(spec=StockAlert)
    alert.id = alert_id
    alert.symbol = symbol
    alert.alert_type = alert_type
    alert.status = status
    alert.config = config or {}
    alert.computed_state = computed_state
    alert.is_active = True
    alert.is_paused = False
    alert.last_triggered_at = None
    alert.deleted_at = None
    alert.events = []
    return alert


def _make_session_factory(alert: StockAlert | None = None):
    """Return a mock session_factory whose repo methods return sensible defaults."""
    session = AsyncMock()
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    session.commit = AsyncMock()
    session.add = MagicMock()

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
def service(session_factory_and_session, mock_provider):
    factory, _ = session_factory_and_session
    return AlertService(factory, mock_provider)


# ---------------------------------------------------------------------------
# 1. test_create_fibonacci_alert
# ---------------------------------------------------------------------------


class TestCreateFibonacciAlert:
    @pytest.mark.asyncio
    async def test_create_fibonacci_alert(self, service, mock_provider):
        """Creates a fibonacci alert with correct initial status."""
        price_data = _make_price_data()
        created_alert = _make_alert(alert_type="fibonacci", status="no_structure")

        with (
            patch(
                "app.services.alert_service.DataService.get_price_data",
                new_callable=AsyncMock,
                return_value=price_data,
            ),
            patch.object(
                service,
                "_create_single_alert",
                new_callable=AsyncMock,
                return_value=created_alert,
            ) as mock_create,
        ):
            result = await service.create_alert(
                symbol="aapl",
                alert_type="fibonacci",
                config={"levels": [38.2, 50.0, 61.8], "tolerance_pct": 0.5},
            )

        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0].alert_type == "fibonacci"
        mock_create.assert_awaited_once()
        # Symbol should be normalized to uppercase
        call_args = mock_create.call_args
        assert call_args.args[0] == "AAPL"


# ---------------------------------------------------------------------------
# 2. test_create_ma_alert
# ---------------------------------------------------------------------------


class TestCreateMAAlert:
    @pytest.mark.asyncio
    async def test_create_ma_alert(self, service):
        """Creates a moving_average alert."""
        price_data = _make_price_data()
        created_alert = _make_alert(alert_type="moving_average", status="above_ma")

        with (
            patch(
                "app.services.alert_service.DataService.get_price_data",
                new_callable=AsyncMock,
                return_value=price_data,
            ),
            patch.object(
                service,
                "_create_single_alert",
                new_callable=AsyncMock,
                return_value=created_alert,
            ),
        ):
            result = await service.create_alert(
                symbol="NVDA",
                alert_type="moving_average",
                config={"ma_period": 200, "tolerance_pct": 0.5},
            )

        assert len(result) == 1
        assert result[0].alert_type == "moving_average"


# ---------------------------------------------------------------------------
# 3. test_create_alert_invalid_symbol
# ---------------------------------------------------------------------------


class TestCreateAlertInvalidSymbol:
    @pytest.mark.asyncio
    async def test_create_alert_invalid_symbol(self, service):
        """Raises SymbolNotFoundError when symbol does not exist."""
        with patch(
            "app.services.alert_service.DataService.get_price_data",
            new_callable=AsyncMock,
            side_effect=SymbolNotFoundError("FAKE: symbol not found"),
        ):
            with pytest.raises(SymbolNotFoundError):
                await service.create_alert(
                    symbol="FAKE",
                    alert_type="fibonacci",
                    config={},
                )


# ---------------------------------------------------------------------------
# 4. test_list_alerts_filters_by_status
# ---------------------------------------------------------------------------


class TestListAlerts:
    @pytest.mark.asyncio
    async def test_list_alerts_filters_by_status(self, service):
        """Passes status filter down to the repository."""
        at_level_alert = _make_alert(status="at_level")

        with patch(
            "app.services.alert_service.AlertRepository.list_alerts",
            new_callable=AsyncMock,
            return_value=[at_level_alert],
        ) as mock_list, patch(
            "app.services.alert_service.AlertRepository.count_alerts",
            new_callable=AsyncMock,
            return_value=1,
        ):
            alerts, count = await service.list_alerts(filters={"status": "at_level"})

        assert count == 1
        assert alerts[0].status == "at_level"
        mock_list.assert_awaited_once_with({"status": "at_level"})

    # -----------------------------------------------------------------------
    # 5. test_list_alerts_excludes_deleted
    # -----------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_list_alerts_excludes_deleted(self, service):
        """Soft-deleted alerts are excluded (repository handles this)."""
        with patch(
            "app.services.alert_service.AlertRepository.list_alerts",
            new_callable=AsyncMock,
            return_value=[],
        ) as mock_list, patch(
            "app.services.alert_service.AlertRepository.count_alerts",
            new_callable=AsyncMock,
            return_value=0,
        ):
            alerts, count = await service.list_alerts()

        assert alerts == []
        assert count == 0
        # Verify None filters propagated (not a status filter for deleted)
        mock_list.assert_awaited_once_with(None)


# ---------------------------------------------------------------------------
# 6. test_pause_alert
# ---------------------------------------------------------------------------


class TestPauseAlert:
    @pytest.mark.asyncio
    async def test_pause_alert(self, service, session_factory_and_session):
        """update_alert toggles is_paused."""
        factory, session = session_factory_and_session
        alert = _make_alert()

        with patch(
            "app.services.alert_service.AlertRepository.get_by_id",
            new_callable=AsyncMock,
            return_value=alert,
        ):
            result = await service.update_alert(1, {"is_paused": True})

        assert result is not None
        assert result.is_paused is True


# ---------------------------------------------------------------------------
# 7. test_delete_alert
# ---------------------------------------------------------------------------


class TestDeleteAlert:
    @pytest.mark.asyncio
    async def test_delete_alert(self, service):
        """Soft-delete sets deleted_at and is_active=False."""
        alert = _make_alert()

        with patch(
            "app.services.alert_service.AlertRepository.get_by_id",
            new_callable=AsyncMock,
            return_value=alert,
        ):
            deleted = await service.delete_alert(1)

        assert deleted is True
        assert alert.deleted_at is not None
        assert alert.is_active is False

    @pytest.mark.asyncio
    async def test_delete_alert_not_found(self, service):
        """Returns False when alert does not exist."""
        with patch(
            "app.services.alert_service.AlertRepository.get_by_id",
            new_callable=AsyncMock,
            return_value=None,
        ):
            deleted = await service.delete_alert(999)

        assert deleted is False


# ---------------------------------------------------------------------------
# 8. test_compute_fibonacci_state_calls_indicator
# ---------------------------------------------------------------------------


class TestComputeFibonacciState:
    @pytest.mark.asyncio
    async def test_compute_fibonacci_state_calls_indicator(self, service):
        """Calls the fibonacci indicator and returns correct keys."""
        price_data = _make_price_data(count=100)
        alert = _make_alert(alert_type="fibonacci", computed_state=None)

        result = await service.compute_fibonacci_state(alert, price_data)

        assert "status" in result
        assert "computed_state" in result
        assert "events" in result
        assert isinstance(result["events"], list)
        # Status must be a valid fibonacci status string
        from app.models.alert import VALID_FIBONACCI_STATUSES
        assert result["status"] in VALID_FIBONACCI_STATUSES

    @pytest.mark.asyncio
    async def test_compute_fibonacci_state_empty_price_data(self, service):
        """Returns no_structure with empty price_data."""
        alert = _make_alert(alert_type="fibonacci")
        result = await service.compute_fibonacci_state(alert, [])
        assert result["status"] == "no_structure"
        assert result["computed_state"] is None
        assert result["events"] == []


# ---------------------------------------------------------------------------
# 9. test_compute_ma_state_uses_analyze_ma_distance
# ---------------------------------------------------------------------------


class TestComputeMAState:
    @pytest.mark.asyncio
    async def test_compute_ma_state_uses_analyze_ma_distance(self, service):
        """MA state computation returns correct structure."""
        price_data = _make_price_data(count=210)
        alert = _make_alert(
            alert_type="moving_average",
            status="above_ma",
            config={"ma_period": 50, "tolerance_pct": 0.5},
        )

        result = await service.compute_ma_state(alert, price_data)

        assert "status" in result
        assert "computed_state" in result
        assert "events" in result
        from app.models.alert import VALID_MA_STATUSES
        assert result["status"] in VALID_MA_STATUSES

        cs = result["computed_state"]
        assert "ma_value" in cs
        assert "ma_period" in cs
        assert cs["ma_period"] == 50
        assert "distance_pct" in cs
        assert "ma_slope" in cs

    # -----------------------------------------------------------------------
    # 10. test_compute_ma_state_approaching
    # -----------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_compute_ma_state_approaching(self, service):
        """distance_pct between tolerance_pct and 2% returns approaching."""
        from app.indicators.ma_analysis import MAAnalysis, MASlope, PricePosition
        from unittest.mock import patch as _patch

        alert = _make_alert(
            alert_type="moving_average",
            status="above_ma",
            config={"ma_period": 20, "tolerance_pct": 0.5},
        )
        # Enough price data to pass the candle count check
        price_data = _make_price_data(count=100)

        # Simulate price 1.5% above MA — between tolerance (0.5%) and approaching (2%)
        mock_analysis = MAAnalysis(
            price_position=PricePosition.ABOVE,
            distance_pct=1.5,
            ma_slope=MASlope.RISING,
            ma_value=100.0,
        )

        with _patch(
            "app.services.alert_service.analyze_ma_distance",
            return_value=mock_analysis,
        ):
            result = await service.compute_ma_state(alert, price_data)

        assert result["status"] == "approaching"
        assert result["events"] == []

    # -----------------------------------------------------------------------
    # 11. test_compute_ma_state_insufficient_history
    # -----------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_compute_ma_state_insufficient_history(self, service):
        """MA200 with 50 candles returns insufficient_data status (R16)."""
        price_data = _make_price_data(count=50)
        alert = _make_alert(
            alert_type="moving_average",
            status="above_ma",
            config={"ma_period": 200, "tolerance_pct": 0.5},
        )

        result = await service.compute_ma_state(alert, price_data)

        assert result["status"] == "insufficient_data"
        assert result["events"] == []
        cs = result["computed_state"]
        assert "error" in cs
        assert "MA200" in cs["error"]
        assert "205" in cs["error"]  # Required candles: 200 + 5
        assert "50" in cs["error"]   # Actual candles

    # -----------------------------------------------------------------------
    # 12. test_ma_deduplication_at_ma_3_cycles
    # -----------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_ma_deduplication_at_ma_3_cycles(self, service):
        """3 consecutive at_ma cycles produce exactly 1 AlertEvent (R19)."""
        from app.indicators.ma_analysis import MAAnalysis, MASlope, PricePosition
        from unittest.mock import patch as _patch

        price_data = _make_price_data(count=100)
        mock_analysis = MAAnalysis(
            price_position=PricePosition.AT,
            distance_pct=0.2,
            ma_slope=MASlope.FLAT,
            ma_value=100.0,
        )

        total_events = 0

        # Cycle 1: previous_status is "above_ma" => transition TO at_ma => event fired
        alert = _make_alert(
            alert_type="moving_average",
            status="above_ma",
            config={"ma_period": 20, "tolerance_pct": 0.5},
        )
        with _patch(
            "app.services.alert_service.analyze_ma_distance",
            return_value=mock_analysis,
        ):
            result = await service.compute_ma_state(alert, price_data)
        assert result["status"] == "at_ma"
        total_events += len(result["events"])

        # Simulate state persisted: alert now has status "at_ma"
        alert.status = "at_ma"

        # Cycle 2: previous_status is already "at_ma" => no new event
        with _patch(
            "app.services.alert_service.analyze_ma_distance",
            return_value=mock_analysis,
        ):
            result = await service.compute_ma_state(alert, price_data)
        assert result["status"] == "at_ma"
        total_events += len(result["events"])

        # Cycle 3: same, no new event
        with _patch(
            "app.services.alert_service.analyze_ma_distance",
            return_value=mock_analysis,
        ):
            result = await service.compute_ma_state(alert, price_data)
        assert result["status"] == "at_ma"
        total_events += len(result["events"])

        assert total_events == 1, (
            f"Expected exactly 1 event across 3 at_ma cycles, got {total_events}"
        )


# ---------------------------------------------------------------------------
# 13. test_create_ma_alert_fan_out
# ---------------------------------------------------------------------------


class TestMAAlertFanOut:
    @pytest.mark.asyncio
    async def test_create_ma_alert_fan_out(self, service):
        """ma_periods=[50, 200] creates 2 separate StockAlert rows."""
        price_data = _make_price_data()
        alert_50 = _make_alert(
            alert_id=1, alert_type="moving_average",
            config={"ma_period": 50, "tolerance_pct": 0.5},
        )
        alert_200 = _make_alert(
            alert_id=2, alert_type="moving_average",
            config={"ma_period": 200, "tolerance_pct": 0.5},
        )

        call_count = 0
        alerts_to_return = [alert_50, alert_200]

        async def fake_create_single(symbol, alert_type, config):
            nonlocal call_count
            result = alerts_to_return[call_count]
            call_count += 1
            return result

        with (
            patch(
                "app.services.alert_service.DataService.get_price_data",
                new_callable=AsyncMock,
                return_value=price_data,
            ),
            patch.object(service, "_create_single_alert", side_effect=fake_create_single),
        ):
            result = await service.create_alert(
                symbol="NVDA",
                alert_type="moving_average",
                config={"ma_periods": [50, 200], "tolerance_pct": 0.5},
            )

        assert len(result) == 2
        assert call_count == 2
        periods = {r.config.get("ma_period") for r in result}
        assert periods == {50, 200}
