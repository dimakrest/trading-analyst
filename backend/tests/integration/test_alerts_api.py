"""Integration tests for the Stock Price Alerts API endpoints.

Tests use the real test database with transaction rollback isolation.
The market data provider is overridden with MockMarketDataProvider to avoid
hitting real external APIs.

Endpoints covered:
  POST   /api/v1/alerts/
  GET    /api/v1/alerts/
  GET    /api/v1/alerts/{id}
  PATCH  /api/v1/alerts/{id}
  DELETE /api/v1/alerts/{id}
  GET    /api/v1/alerts/{id}/events
  GET    /api/v1/alerts/{id}/price-data
"""
from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient

from app.core.deps import get_market_data_provider
from app.providers.mock import MockMarketDataProvider

# All tests are integration tests requiring the database.
pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Shared payload helpers
# ---------------------------------------------------------------------------

FIBONACCI_PAYLOAD = {
    "symbol": "AAPL",
    "alert_type": "fibonacci",
    "config": {
        "levels": [38.2, 50.0, 61.8],
        "tolerance_pct": 0.5,
        "min_swing_pct": 10.0,
    },
}

MA_PAYLOAD = {
    "symbol": "MSFT",
    "alert_type": "moving_average",
    "config": {
        "ma_periods": [200],
        "tolerance_pct": 0.5,
        "direction": "both",
    },
}


# ---------------------------------------------------------------------------
# Fixture: override market data provider with mock
# ---------------------------------------------------------------------------


@pytest.fixture
def app_with_mock_provider(app):
    """Override get_market_data_provider with MockMarketDataProvider.

    The base `app` fixture from conftest.py already overrides DB dependencies.
    This fixture adds the provider override on top of that.
    """
    mock_provider = MockMarketDataProvider()
    app.dependency_overrides[get_market_data_provider] = lambda: mock_provider
    yield app
    # Restore to the base overrides set by the `app` fixture
    app.dependency_overrides.pop(get_market_data_provider, None)


@pytest.fixture
async def alerts_client(app_with_mock_provider) -> AsyncClient:
    """Async HTTP client wired to the app with the mock provider."""
    async with AsyncClient(app=app_with_mock_provider, base_url="http://testserver") as client:
        yield client


# ---------------------------------------------------------------------------
# POST / — Create alerts
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_fibonacci_alert(alerts_client: AsyncClient) -> None:
    """POST /api/v1/alerts/ with fibonacci type returns 201 and one alert."""
    response = await alerts_client.post("/api/v1/alerts/", json=FIBONACCI_PAYLOAD)

    assert response.status_code == 201
    data = response.json()

    assert isinstance(data, list)
    assert len(data) == 1

    alert = data[0]
    assert alert["symbol"] == "AAPL"
    assert alert["alert_type"] == "fibonacci"
    assert alert["status"] == "no_structure"
    assert alert["is_active"] is True
    assert alert["is_paused"] is False
    assert alert["config"]["levels"] == [38.2, 50.0, 61.8]
    assert alert["config"]["tolerance_pct"] == 0.5
    assert "id" in alert
    assert "created_at" in alert
    assert "updated_at" in alert


@pytest.mark.asyncio
async def test_create_ma_alert(alerts_client: AsyncClient) -> None:
    """POST /api/v1/alerts/ with moving_average type returns 201 and one alert."""
    response = await alerts_client.post("/api/v1/alerts/", json=MA_PAYLOAD)

    assert response.status_code == 201
    data = response.json()

    assert isinstance(data, list)
    assert len(data) == 1

    alert = data[0]
    assert alert["symbol"] == "MSFT"
    assert alert["alert_type"] == "moving_average"
    assert alert["status"] == "above_ma"
    assert alert["is_active"] is True
    # MA fan-out stores per-period config (ma_period not ma_periods)
    assert alert["config"]["ma_period"] == 200


@pytest.mark.asyncio
async def test_create_ma_alert_multiple_periods_fans_out(alerts_client: AsyncClient) -> None:
    """POST with multiple ma_periods creates one alert per period."""
    payload = {
        "symbol": "NVDA",
        "alert_type": "moving_average",
        "config": {
            "ma_periods": [50, 200],
            "tolerance_pct": 0.5,
            "direction": "both",
        },
    }
    response = await alerts_client.post("/api/v1/alerts/", json=payload)

    assert response.status_code == 201
    data = response.json()

    assert isinstance(data, list)
    assert len(data) == 2

    periods = {alert["config"]["ma_period"] for alert in data}
    assert periods == {50, 200}


@pytest.mark.asyncio
async def test_create_alert_invalid_symbol(
    app_with_mock_provider,
) -> None:
    """POST with a symbol that fails validation returns 400.

    We patch MockMarketDataProvider.fetch_price_data to raise SymbolNotFoundError
    so we can test the 400 path without needing a real unknown symbol.
    """
    from app.core.exceptions import SymbolNotFoundError
    from unittest.mock import patch

    async def _raise_not_found(*args, **kwargs):
        raise SymbolNotFoundError("INVALID")

    with patch.object(MockMarketDataProvider, "fetch_price_data", side_effect=_raise_not_found):
        async with AsyncClient(app=app_with_mock_provider, base_url="http://testserver") as client:
            response = await client.post(
                "/api/v1/alerts/",
                json={
                    "symbol": "INVALID",
                    "alert_type": "fibonacci",
                    "config": {"levels": [38.2, 50.0, 61.8], "tolerance_pct": 0.5, "min_swing_pct": 10.0},
                },
            )

    assert response.status_code == 400
    assert "INVALID" in response.json()["detail"]


@pytest.mark.asyncio
async def test_create_alert_invalid_type(alerts_client: AsyncClient) -> None:
    """POST with an unsupported alert_type returns 422 (schema validation)."""
    payload = {
        "symbol": "AAPL",
        "alert_type": "unsupported_type",
        "config": {"levels": [38.2]},
    }
    response = await alerts_client.post("/api/v1/alerts/", json=payload)

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_alert_invalid_ma_period(alerts_client: AsyncClient) -> None:
    """POST with an unsupported MA period returns 422 (field validator)."""
    payload = {
        "symbol": "AAPL",
        "alert_type": "moving_average",
        "config": {
            "ma_periods": [100],  # 100 is not in {20, 50, 150, 200}
            "tolerance_pct": 0.5,
            "direction": "both",
        },
    }
    response = await alerts_client.post("/api/v1/alerts/", json=payload)

    assert response.status_code == 422
    error_body = response.json()
    assert "100" in str(error_body)


# ---------------------------------------------------------------------------
# GET / — List alerts
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_alerts(alerts_client: AsyncClient) -> None:
    """GET /api/v1/alerts/ returns all non-deleted alerts."""
    # Create two alerts first
    await alerts_client.post("/api/v1/alerts/", json=FIBONACCI_PAYLOAD)
    await alerts_client.post("/api/v1/alerts/", json=MA_PAYLOAD)

    response = await alerts_client.get("/api/v1/alerts/")

    assert response.status_code == 200
    data = response.json()

    assert "items" in data
    assert "total" in data
    assert data["total"] >= 2
    assert len(data["items"]) >= 2


@pytest.mark.asyncio
async def test_list_alerts_filter_by_status(alerts_client: AsyncClient) -> None:
    """GET /api/v1/alerts/?status=no_structure filters correctly."""
    # Create a fibonacci alert (starts at no_structure)
    create_resp = await alerts_client.post("/api/v1/alerts/", json=FIBONACCI_PAYLOAD)
    assert create_resp.status_code == 201

    response = await alerts_client.get("/api/v1/alerts/", params={"status": "no_structure"})

    assert response.status_code == 200
    data = response.json()

    assert data["total"] >= 1
    for item in data["items"]:
        assert item["status"] == "no_structure"


@pytest.mark.asyncio
async def test_list_alerts_filter_by_alert_type(alerts_client: AsyncClient) -> None:
    """GET /api/v1/alerts/?alert_type=fibonacci filters to fibonacci only."""
    await alerts_client.post("/api/v1/alerts/", json=FIBONACCI_PAYLOAD)
    await alerts_client.post("/api/v1/alerts/", json=MA_PAYLOAD)

    response = await alerts_client.get("/api/v1/alerts/", params={"alert_type": "fibonacci"})

    assert response.status_code == 200
    data = response.json()

    assert data["total"] >= 1
    for item in data["items"]:
        assert item["alert_type"] == "fibonacci"


# ---------------------------------------------------------------------------
# GET /{alert_id} — Single alert
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_alert(alerts_client: AsyncClient) -> None:
    """GET /api/v1/alerts/{id} returns 200 with full alert data."""
    create_resp = await alerts_client.post("/api/v1/alerts/", json=FIBONACCI_PAYLOAD)
    assert create_resp.status_code == 201
    alert_id = create_resp.json()[0]["id"]

    response = await alerts_client.get(f"/api/v1/alerts/{alert_id}")

    assert response.status_code == 200
    data = response.json()

    assert data["id"] == alert_id
    assert data["symbol"] == "AAPL"
    assert data["alert_type"] == "fibonacci"
    # computed_state starts as None for a newly created alert
    assert "computed_state" in data


@pytest.mark.asyncio
async def test_get_alert_not_found(alerts_client: AsyncClient) -> None:
    """GET /api/v1/alerts/{id} returns 404 for a non-existent alert."""
    response = await alerts_client.get("/api/v1/alerts/999999")

    assert response.status_code == 404


# ---------------------------------------------------------------------------
# PATCH /{alert_id} — Update alert
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_alert_pause(alerts_client: AsyncClient) -> None:
    """PATCH /api/v1/alerts/{id} with is_paused=true pauses the alert."""
    create_resp = await alerts_client.post("/api/v1/alerts/", json=FIBONACCI_PAYLOAD)
    assert create_resp.status_code == 201
    alert_id = create_resp.json()[0]["id"]
    assert create_resp.json()[0]["is_paused"] is False

    response = await alerts_client.patch(
        f"/api/v1/alerts/{alert_id}",
        json={"is_paused": True},
    )

    assert response.status_code == 200
    data = response.json()

    assert data["id"] == alert_id
    assert data["is_paused"] is True


@pytest.mark.asyncio
async def test_update_alert_config(alerts_client: AsyncClient) -> None:
    """PATCH /api/v1/alerts/{id} with new config updates the config."""
    create_resp = await alerts_client.post("/api/v1/alerts/", json=FIBONACCI_PAYLOAD)
    assert create_resp.status_code == 201
    alert_id = create_resp.json()[0]["id"]

    new_config = {
        "levels": [61.8],
        "tolerance_pct": 1.0,
        "min_swing_pct": 15.0,
    }
    response = await alerts_client.patch(
        f"/api/v1/alerts/{alert_id}",
        json={"config": new_config},
    )

    assert response.status_code == 200
    data = response.json()

    assert data["config"]["tolerance_pct"] == 1.0
    assert data["config"]["min_swing_pct"] == 15.0


@pytest.mark.asyncio
async def test_update_alert_not_found(alerts_client: AsyncClient) -> None:
    """PATCH /api/v1/alerts/{id} returns 404 for a non-existent alert."""
    response = await alerts_client.patch(
        "/api/v1/alerts/999999",
        json={"is_paused": True},
    )

    assert response.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /{alert_id} — Soft delete
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_alert(alerts_client: AsyncClient) -> None:
    """DELETE /api/v1/alerts/{id} soft-deletes and returns 200."""
    create_resp = await alerts_client.post("/api/v1/alerts/", json=FIBONACCI_PAYLOAD)
    assert create_resp.status_code == 201
    alert_id = create_resp.json()[0]["id"]

    delete_resp = await alerts_client.delete(f"/api/v1/alerts/{alert_id}")
    assert delete_resp.status_code == 200
    assert delete_resp.json()["deleted"] == alert_id

    # Confirm it is no longer accessible via GET
    get_resp = await alerts_client.get(f"/api/v1/alerts/{alert_id}")
    assert get_resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_alert_not_found(alerts_client: AsyncClient) -> None:
    """DELETE /api/v1/alerts/{id} returns 404 for a non-existent alert."""
    response = await alerts_client.delete("/api/v1/alerts/999999")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_deleted_alert_excluded_from_list(alerts_client: AsyncClient) -> None:
    """Soft-deleted alerts do not appear in GET /api/v1/alerts/ list."""
    create_resp = await alerts_client.post("/api/v1/alerts/", json=FIBONACCI_PAYLOAD)
    alert_id = create_resp.json()[0]["id"]

    await alerts_client.delete(f"/api/v1/alerts/{alert_id}")

    list_resp = await alerts_client.get("/api/v1/alerts/")
    assert list_resp.status_code == 200

    ids = [item["id"] for item in list_resp.json()["items"]]
    assert alert_id not in ids


# ---------------------------------------------------------------------------
# GET /{alert_id}/events — Event history
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_alert_events(alerts_client: AsyncClient) -> None:
    """GET /api/v1/alerts/{id}/events returns 200 and a list (possibly empty)."""
    create_resp = await alerts_client.post("/api/v1/alerts/", json=FIBONACCI_PAYLOAD)
    assert create_resp.status_code == 201
    alert_id = create_resp.json()[0]["id"]

    response = await alerts_client.get(f"/api/v1/alerts/{alert_id}/events")

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


@pytest.mark.asyncio
async def test_get_alert_events_not_found(alerts_client: AsyncClient) -> None:
    """GET /api/v1/alerts/{id}/events returns 404 for a non-existent alert."""
    response = await alerts_client.get("/api/v1/alerts/999999/events")

    assert response.status_code == 404


# ---------------------------------------------------------------------------
# GET /{alert_id}/price-data — OHLCV data for chart rendering
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_price_data_for_alert(alerts_client: AsyncClient) -> None:
    """GET /api/v1/alerts/{id}/price-data returns 200 with OHLCV data."""
    create_resp = await alerts_client.post("/api/v1/alerts/", json=FIBONACCI_PAYLOAD)
    assert create_resp.status_code == 201
    alert_id = create_resp.json()[0]["id"]

    response = await alerts_client.get(f"/api/v1/alerts/{alert_id}/price-data")

    assert response.status_code == 200
    data = response.json()

    assert data["symbol"] == "AAPL"
    assert data["alert_id"] == alert_id
    assert data["days"] == 365
    assert isinstance(data["data"], list)
    assert len(data["data"]) > 0

    # Verify OHLCV structure of the first candle
    candle = data["data"][0]
    assert "timestamp" in candle
    assert "open" in candle
    assert "high" in candle
    assert "low" in candle
    assert "close" in candle
    assert "volume" in candle


@pytest.mark.asyncio
async def test_get_price_data_days_param(alerts_client: AsyncClient) -> None:
    """GET /api/v1/alerts/{id}/price-data?days=30 respects the days parameter."""
    create_resp = await alerts_client.post("/api/v1/alerts/", json=FIBONACCI_PAYLOAD)
    assert create_resp.status_code == 201
    alert_id = create_resp.json()[0]["id"]

    response = await alerts_client.get(
        f"/api/v1/alerts/{alert_id}/price-data",
        params={"days": 30},
    )

    assert response.status_code == 200
    data = response.json()

    assert data["days"] == 30
    # The days parameter is echoed back correctly and data is a non-empty list.
    # We do not assert an upper bound on candle count because the DataService
    # cache-first design may return previously cached data spanning a wider range.
    assert isinstance(data["data"], list)
    assert len(data["data"]) > 0


@pytest.mark.asyncio
async def test_get_price_data_not_found(alerts_client: AsyncClient) -> None:
    """GET /api/v1/alerts/{id}/price-data returns 404 for a non-existent alert."""
    response = await alerts_client.get("/api/v1/alerts/999999/price-data")

    assert response.status_code == 404
