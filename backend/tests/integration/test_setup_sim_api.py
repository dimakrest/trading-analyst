"""Integration tests for Setup Simulation API endpoint.

Tests verify:
1. Happy path — POST valid request returns 200 with correct response shape
2. Validation errors — missing fields, stop >= entry, future end date, start >= end → 422
3. Date range limit — > 5 years → 422
4. Unknown symbol — verify 422 with descriptive message
"""

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import AsyncClient

from app.core.exceptions import SymbolNotFoundError
from app.providers.base import PriceDataPoint

# Mark all tests in this module as integration tests
pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_price_data_point(
    symbol: str,
    d: date,
    open_: float = 100.0,
    high: float = 105.0,
    low: float = 98.0,
    close: float = 102.0,
    volume: int = 1_000_000,
) -> PriceDataPoint:
    """Build a PriceDataPoint for a given date."""
    return PriceDataPoint(
        symbol=symbol,
        timestamp=datetime.combine(d, datetime.min.time(), tzinfo=timezone.utc),
        open_price=Decimal(str(open_)),
        high_price=Decimal(str(high)),
        low_price=Decimal(str(low)),
        close_price=Decimal(str(close)),
        volume=volume,
    )


def make_bars(symbol: str, start: date, count: int, base: float = 100.0) -> list[PriceDataPoint]:
    """Generate a sequence of price data points from start date."""
    bars = []
    for i in range(count):
        d = start + timedelta(days=i)
        price = base + i * 0.5  # Gentle uptrend
        bars.append(
            make_price_data_point(
                symbol=symbol,
                d=d,
                open_=price,
                high=price * 1.02,
                low=price * 0.98,
                close=price * 1.01,
            )
        )
    return bars


def mock_data_service_with_bars(bars_by_symbol: dict[str, list[PriceDataPoint]]) -> MagicMock:
    """Build a mock DataService that returns given bars per symbol."""
    mock_ds = MagicMock()

    async def get_price_data(symbol: str, **kwargs) -> list[PriceDataPoint]:
        symbol = symbol.upper()
        if symbol not in bars_by_symbol:
            raise SymbolNotFoundError(f"Symbol not found: {symbol}")
        return bars_by_symbol[symbol]

    mock_ds.get_price_data = get_price_data
    return mock_ds


VALID_PAYLOAD = {
    "setups": [
        {
            "symbol": "AAPL",
            "entry_price": "101.0",
            "stop_loss_day1": "95.0",
            "trailing_stop_pct": "5.0",
            "start_date": "2024-01-02",
        }
    ],
    "end_date": "2024-06-01",
}


# ---------------------------------------------------------------------------
# Happy Path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_happy_path_valid_request_returns_200(
    app,
    async_client: AsyncClient,
) -> None:
    """POST valid request returns 200 with correct response shape."""
    from app.core.deps import get_data_service

    # Price rises above entry (101) on day 2, no stop triggered, ends at last close
    bars = make_bars("AAPL", start=date(2024, 1, 2), count=30, base=100.0)
    mock_ds = mock_data_service_with_bars({"AAPL": bars})
    app.dependency_overrides[get_data_service] = lambda: mock_ds

    try:
        response = await async_client.post("/api/v1/setup-sim/run", json=VALID_PAYLOAD)

        assert response.status_code == 200
        data = response.json()

        # Response must have top-level keys
        assert "summary" in data
        assert "setups" in data

        # Summary must have all required keys
        summary = data["summary"]
        for key in (
            "total_pnl", "total_pnl_pct", "total_capital_deployed",
            "total_trades", "winning_trades", "losing_trades",
            "win_rate", "avg_gain", "avg_loss", "position_size",
        ):
            assert key in summary, f"summary missing key: {key}"

        # Setups list has one entry matching our input
        assert len(data["setups"]) == 1
        setup = data["setups"][0]
        assert setup["symbol"] == "AAPL"
        assert "trades" in setup
        assert "times_triggered" in setup
        assert "pnl" in setup

    finally:
        app.dependency_overrides.pop(get_data_service, None)


@pytest.mark.asyncio
async def test_happy_path_multiple_setups(
    app,
    async_client: AsyncClient,
) -> None:
    """Multiple setups in one request all receive results."""
    from app.core.deps import get_data_service

    bars_aapl = make_bars("AAPL", start=date(2024, 1, 2), count=30, base=100.0)
    bars_msft = make_bars("MSFT", start=date(2024, 1, 2), count=30, base=200.0)
    mock_ds = mock_data_service_with_bars({"AAPL": bars_aapl, "MSFT": bars_msft})
    app.dependency_overrides[get_data_service] = lambda: mock_ds

    payload = {
        "setups": [
            {
                "symbol": "AAPL",
                "entry_price": "101.0",
                "stop_loss_day1": "95.0",
                "trailing_stop_pct": "5.0",
                "start_date": "2024-01-02",
            },
            {
                "symbol": "MSFT",
                "entry_price": "201.0",
                "stop_loss_day1": "190.0",
                "trailing_stop_pct": "5.0",
                "start_date": "2024-01-02",
            },
        ],
        "end_date": "2024-06-01",
    }

    try:
        response = await async_client.post("/api/v1/setup-sim/run", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert len(data["setups"]) == 2
        symbols = {s["symbol"] for s in data["setups"]}
        assert symbols == {"AAPL", "MSFT"}

    finally:
        app.dependency_overrides.pop(get_data_service, None)


@pytest.mark.asyncio
async def test_happy_path_trade_fields_present(
    app,
    async_client: AsyncClient,
) -> None:
    """Individual trade records contain all required fields."""
    from app.core.deps import get_data_service

    # Construct bars that guarantee at least one trade:
    # entry at 101, no day-1 stop, position held to end
    bars = make_bars("AAPL", start=date(2024, 1, 2), count=10, base=100.0)
    mock_ds = mock_data_service_with_bars({"AAPL": bars})
    app.dependency_overrides[get_data_service] = lambda: mock_ds

    try:
        response = await async_client.post("/api/v1/setup-sim/run", json=VALID_PAYLOAD)
        assert response.status_code == 200

        data = response.json()
        setup = data["setups"][0]

        if setup["times_triggered"] > 0:
            trade = setup["trades"][0]
            for key in (
                "entry_date", "entry_price", "exit_date", "exit_price",
                "shares", "pnl", "return_pct", "exit_reason",
            ):
                assert key in trade, f"trade missing key: {key}"

            assert trade["exit_reason"] in ("stop_day1", "trailing_stop", "simulation_end")

    finally:
        app.dependency_overrides.pop(get_data_service, None)


@pytest.mark.asyncio
async def test_happy_path_symbol_case_insensitive(
    app,
    async_client: AsyncClient,
) -> None:
    """Symbol is normalized to uppercase before lookup."""
    from app.core.deps import get_data_service

    bars = make_bars("AAPL", start=date(2024, 1, 2), count=20, base=100.0)
    mock_ds = mock_data_service_with_bars({"AAPL": bars})
    app.dependency_overrides[get_data_service] = lambda: mock_ds

    payload = {
        "setups": [
            {
                "symbol": "aapl",  # lowercase
                "entry_price": "101.0",
                "stop_loss_day1": "95.0",
                "trailing_stop_pct": "5.0",
                "start_date": "2024-01-02",
            }
        ],
        "end_date": "2024-06-01",
    }

    try:
        response = await async_client.post("/api/v1/setup-sim/run", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["setups"][0]["symbol"] == "AAPL"

    finally:
        app.dependency_overrides.pop(get_data_service, None)


# ---------------------------------------------------------------------------
# Validation — 422 errors
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_validation_missing_symbol_returns_422(async_client: AsyncClient) -> None:
    """Missing required field 'symbol' in setup returns 422."""
    payload = {
        "setups": [
            {
                # symbol is missing
                "entry_price": "100.0",
                "stop_loss_day1": "95.0",
                "trailing_stop_pct": "5.0",
                "start_date": "2024-01-02",
            }
        ],
        "end_date": "2024-06-01",
    }

    response = await async_client.post("/api/v1/setup-sim/run", json=payload)

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_validation_stop_gte_entry_returns_422(async_client: AsyncClient) -> None:
    """stop_loss_day1 >= entry_price returns 422."""
    payload = {
        "setups": [
            {
                "symbol": "AAPL",
                "entry_price": "100.0",
                "stop_loss_day1": "100.0",  # equal to entry → invalid
                "trailing_stop_pct": "5.0",
                "start_date": "2024-01-02",
            }
        ],
        "end_date": "2024-06-01",
    }

    response = await async_client.post("/api/v1/setup-sim/run", json=payload)

    assert response.status_code == 422
    body = response.json()
    assert "stop_loss_day1" in str(body) or "entry_price" in str(body)


@pytest.mark.asyncio
async def test_validation_stop_above_entry_returns_422(async_client: AsyncClient) -> None:
    """stop_loss_day1 > entry_price returns 422."""
    payload = {
        "setups": [
            {
                "symbol": "AAPL",
                "entry_price": "100.0",
                "stop_loss_day1": "105.0",  # above entry → invalid
                "trailing_stop_pct": "5.0",
                "start_date": "2024-01-02",
            }
        ],
        "end_date": "2024-06-01",
    }

    response = await async_client.post("/api/v1/setup-sim/run", json=payload)

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_validation_future_end_date_returns_422(async_client: AsyncClient) -> None:
    """end_date in the future returns 422."""
    future_date = (date.today() + timedelta(days=30)).isoformat()
    payload = {
        "setups": [
            {
                "symbol": "AAPL",
                "entry_price": "100.0",
                "stop_loss_day1": "95.0",
                "trailing_stop_pct": "5.0",
                "start_date": "2024-01-02",
            }
        ],
        "end_date": future_date,
    }

    response = await async_client.post("/api/v1/setup-sim/run", json=payload)

    assert response.status_code == 422
    body = response.json()
    assert "future" in str(body).lower() or "end_date" in str(body)


@pytest.mark.asyncio
async def test_validation_start_date_gte_end_date_returns_422(async_client: AsyncClient) -> None:
    """start_date >= end_date returns 422."""
    payload = {
        "setups": [
            {
                "symbol": "AAPL",
                "entry_price": "100.0",
                "stop_loss_day1": "95.0",
                "trailing_stop_pct": "5.0",
                "start_date": "2024-06-01",  # same as end_date
            }
        ],
        "end_date": "2024-06-01",
    }

    response = await async_client.post("/api/v1/setup-sim/run", json=payload)

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_validation_start_after_end_date_returns_422(async_client: AsyncClient) -> None:
    """start_date after end_date returns 422."""
    payload = {
        "setups": [
            {
                "symbol": "AAPL",
                "entry_price": "100.0",
                "stop_loss_day1": "95.0",
                "trailing_stop_pct": "5.0",
                "start_date": "2024-07-01",  # after end_date
            }
        ],
        "end_date": "2024-06-01",
    }

    response = await async_client.post("/api/v1/setup-sim/run", json=payload)

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_validation_empty_setups_list_returns_422(async_client: AsyncClient) -> None:
    """Empty setups list returns 422 (min_length=1)."""
    payload = {
        "setups": [],
        "end_date": "2024-06-01",
    }

    response = await async_client.post("/api/v1/setup-sim/run", json=payload)

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_validation_negative_entry_price_returns_422(async_client: AsyncClient) -> None:
    """entry_price <= 0 returns 422."""
    payload = {
        "setups": [
            {
                "symbol": "AAPL",
                "entry_price": "-10.0",
                "stop_loss_day1": "95.0",
                "trailing_stop_pct": "5.0",
                "start_date": "2024-01-02",
            }
        ],
        "end_date": "2024-06-01",
    }

    response = await async_client.post("/api/v1/setup-sim/run", json=payload)

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_validation_trailing_stop_pct_zero_returns_422(async_client: AsyncClient) -> None:
    """trailing_stop_pct = 0 returns 422 (gt=0 constraint)."""
    payload = {
        "setups": [
            {
                "symbol": "AAPL",
                "entry_price": "100.0",
                "stop_loss_day1": "95.0",
                "trailing_stop_pct": "0",
                "start_date": "2024-01-02",
            }
        ],
        "end_date": "2024-06-01",
    }

    response = await async_client.post("/api/v1/setup-sim/run", json=payload)

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_validation_trailing_stop_pct_100_returns_422(async_client: AsyncClient) -> None:
    """trailing_stop_pct = 100 returns 422 (lt=100 constraint)."""
    payload = {
        "setups": [
            {
                "symbol": "AAPL",
                "entry_price": "100.0",
                "stop_loss_day1": "95.0",
                "trailing_stop_pct": "100",
                "start_date": "2024-01-02",
            }
        ],
        "end_date": "2024-06-01",
    }

    response = await async_client.post("/api/v1/setup-sim/run", json=payload)

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_validation_invalid_symbol_format_returns_422(async_client: AsyncClient) -> None:
    """Symbol with invalid characters returns 422."""
    payload = {
        "setups": [
            {
                "symbol": "INVALID SYMBOL!",
                "entry_price": "100.0",
                "stop_loss_day1": "95.0",
                "trailing_stop_pct": "5.0",
                "start_date": "2024-01-02",
            }
        ],
        "end_date": "2024-06-01",
    }

    response = await async_client.post("/api/v1/setup-sim/run", json=payload)

    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Date Range Limit — > 5 years → 422
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_date_range_over_5_years_returns_422(async_client: AsyncClient) -> None:
    """Date range exceeding 5 years (1825 days) returns 422."""
    # 5 years + 1 day = 1826 days
    end_date = date(2025, 1, 1)
    start_date = end_date - timedelta(days=1826)

    payload = {
        "setups": [
            {
                "symbol": "AAPL",
                "entry_price": "100.0",
                "stop_loss_day1": "95.0",
                "trailing_stop_pct": "5.0",
                "start_date": start_date.isoformat(),
            }
        ],
        "end_date": end_date.isoformat(),
    }

    response = await async_client.post("/api/v1/setup-sim/run", json=payload)

    assert response.status_code == 422
    body = response.json()
    assert "1826" in str(body) or "5 year" in str(body).lower() or "1825" in str(body)


@pytest.mark.asyncio
async def test_date_range_exactly_5_years_is_valid(
    app,
    async_client: AsyncClient,
) -> None:
    """Date range of exactly 1825 days passes validation (boundary condition)."""
    from app.core.deps import get_data_service

    end_date = date(2025, 1, 1)
    start_date = end_date - timedelta(days=1825)

    bars = make_bars("AAPL", start=start_date, count=10, base=100.0)
    mock_ds = mock_data_service_with_bars({"AAPL": bars})
    app.dependency_overrides[get_data_service] = lambda: mock_ds

    payload = {
        "setups": [
            {
                "symbol": "AAPL",
                "entry_price": "100.0",
                "stop_loss_day1": "95.0",
                "trailing_stop_pct": "5.0",
                "start_date": start_date.isoformat(),
            }
        ],
        "end_date": end_date.isoformat(),
    }

    try:
        response = await async_client.post("/api/v1/setup-sim/run", json=payload)
        # Should pass validation and return 200
        assert response.status_code == 200

    finally:
        app.dependency_overrides.pop(get_data_service, None)


# ---------------------------------------------------------------------------
# Unknown Symbol — 422 with descriptive message
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_unknown_symbol_returns_422_with_message(
    app,
    async_client: AsyncClient,
) -> None:
    """SymbolNotFoundError from DataService returns 422 with descriptive message."""
    from app.core.deps import get_data_service

    # Mock DataService raises SymbolNotFoundError for unknown symbol
    mock_ds = mock_data_service_with_bars({})  # No symbols → will raise
    app.dependency_overrides[get_data_service] = lambda: mock_ds

    payload = {
        "setups": [
            {
                "symbol": "XYZUNK",
                "entry_price": "100.0",
                "stop_loss_day1": "95.0",
                "trailing_stop_pct": "5.0",
                "start_date": "2024-01-02",
            }
        ],
        "end_date": "2024-06-01",
    }

    try:
        response = await async_client.post("/api/v1/setup-sim/run", json=payload)

        assert response.status_code == 422
        body = response.json()
        detail = str(body.get("detail", ""))
        assert "XYZUNK" in detail or "not found" in detail.lower() or "Symbol" in detail

    finally:
        app.dependency_overrides.pop(get_data_service, None)


@pytest.mark.asyncio
async def test_data_service_api_error_returns_502(
    app,
    async_client: AsyncClient,
) -> None:
    """APIError from DataService returns 502 Bad Gateway."""
    from app.core.deps import get_data_service
    from app.core.exceptions import APIError

    mock_ds = MagicMock()
    mock_ds.get_price_data = AsyncMock(side_effect=APIError("Provider unavailable"))
    app.dependency_overrides[get_data_service] = lambda: mock_ds

    try:
        response = await async_client.post("/api/v1/setup-sim/run", json=VALID_PAYLOAD)

        assert response.status_code == 502
        body = response.json()
        assert "unavailable" in str(body).lower() or "provider" in str(body).lower()

    finally:
        app.dependency_overrides.pop(get_data_service, None)
