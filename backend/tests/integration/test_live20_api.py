"""Integration tests for Live 20 API endpoints.

These tests require a running test database.
Mark all tests with @pytest.mark.integration to skip in unit test runs.
"""

from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.recommendation import Recommendation, RecommendationSource


# Mark all tests in this module as integration tests
pytestmark = pytest.mark.integration


@pytest.fixture
async def sample_live20_results(db_session: AsyncSession):
    """Create sample Live 20 results for testing."""
    results = [
        Recommendation(
            stock="AAPL",
            source=RecommendationSource.LIVE_20.value,
            recommendation="LONG",
            confidence_score=80,
            reasoning="Live 20 mean reversion analysis",
            entry_price=Decimal("150.50"),
                        live20_trend_direction="bearish",
            live20_trend_aligned=True,
            live20_ma20_distance_pct=Decimal("-6.5"),
            live20_ma20_aligned=True,
            live20_candle_pattern="hammer",
            live20_candle_aligned=True,
            live20_volume_trend="decreasing",
            live20_volume_aligned=True,
            live20_cci_value=Decimal("-110.0"),
            live20_cci_zone="oversold",
            live20_cci_aligned=True,
            live20_criteria_aligned=4,
            live20_direction="LONG",
        ),
        Recommendation(
            stock="TSLA",
            source=RecommendationSource.LIVE_20.value,
            recommendation="SHORT",
            confidence_score=60,
            reasoning="Live 20 mean reversion analysis",
            entry_price=Decimal("200.25"),
                        live20_trend_direction="bullish",
            live20_trend_aligned=True,
            live20_ma20_distance_pct=Decimal("7.2"),
            live20_ma20_aligned=True,
            live20_candle_pattern="shooting_star",
            live20_candle_aligned=True,
            live20_volume_trend="decreasing",
            live20_volume_aligned=False,
            live20_cci_value=Decimal("105.0"),
            live20_cci_zone="overbought",
            live20_cci_aligned=True,
            live20_criteria_aligned=3,
            live20_direction="SHORT",
        ),
        Recommendation(
            stock="MSFT",
            source=RecommendationSource.LIVE_20.value,
            recommendation="NO_SETUP",
            confidence_score=40,
            reasoning="Live 20 mean reversion analysis",
            entry_price=Decimal("350.00"),
                        live20_trend_direction="neutral",
            live20_trend_aligned=False,
            live20_ma20_distance_pct=Decimal("2.0"),
            live20_ma20_aligned=False,
            live20_candle_pattern="doji",
            live20_candle_aligned=True,
            live20_volume_trend="stable",
            live20_volume_aligned=False,
            live20_cci_value=Decimal("10.0"),
            live20_cci_zone="neutral",
            live20_cci_aligned=False,
            live20_criteria_aligned=2,
            live20_direction="NO_SETUP",
        ),
    ]

    for result in results:
        db_session.add(result)
    await db_session.commit()

    # Refresh to get IDs
    for result in results:
        await db_session.refresh(result)

    return results


@pytest.mark.asyncio
async def test_analyze_symbols_creates_pending_run(async_client: AsyncClient):
    """Test POST /api/v1/live-20/analyze creates a pending run.

    Verifies the async queue pattern where the endpoint creates a run with
    status='pending' and returns immediately. A background worker processes the run.
    """
    response = await async_client.post(
        "/api/v1/live-20/analyze",
        json={"symbols": ["AAPL", "TSLA"]},
    )

    assert response.status_code == 200
    data = response.json()

    # Verify async response structure
    assert "run_id" in data
    assert data["run_id"] is not None
    assert isinstance(data["run_id"], int)
    assert data["status"] == "pending"
    assert data["total"] == 2
    assert data["message"] == "Run queued for processing"


@pytest.mark.asyncio
async def test_analyze_symbols_normalizes_input(async_client: AsyncClient):
    """Test symbol normalization (uppercase conversion and whitespace stripping)."""
    response = await async_client.post(
        "/api/v1/live-20/analyze",
        json={"symbols": ["  aapl  ", "tsla", "MSFT"]},
    )

    assert response.status_code == 200
    data = response.json()

    # Should have normalized 3 symbols
    assert data["total"] == 3
    assert data["status"] == "pending"

    # Verify normalized symbols are stored by checking the run
    run_response = await async_client.get(f"/api/v1/live-20/runs/{data['run_id']}")
    run_data = run_response.json()
    assert run_data["input_symbols"] == ["AAPL", "TSLA", "MSFT"]


@pytest.mark.asyncio
async def test_analyze_symbols_validation_errors(async_client: AsyncClient):
    """Test validation errors for invalid requests."""
    # Empty symbols list should fail
    response = await async_client.post(
        "/api/v1/live-20/analyze",
        json={"symbols": []},
    )
    assert response.status_code == 422

    # Too many symbols (> 500) should fail
    response = await async_client.post(
        "/api/v1/live-20/analyze",
        json={"symbols": [f"SYM{i}" for i in range(501)]},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_get_results_all(async_client: AsyncClient, sample_live20_results):
    """Test retrieving all Live 20 results without filters."""
    response = await async_client.get("/api/v1/live-20/results")

    assert response.status_code == 200
    data = response.json()

    # Verify structure
    assert "results" in data
    assert "total" in data
    assert "counts" in data

    # Verify counts
    assert data["total"] == 3
    assert data["counts"]["long"] == 1
    assert data["counts"]["short"] == 1
    assert data["counts"]["no_setup"] == 1

    # Verify results are ordered by created_at desc (most recent first)
    assert len(data["results"]) == 3


@pytest.mark.asyncio
async def test_get_results_filter_by_long(async_client: AsyncClient, sample_live20_results):
    """Test filtering results by LONG direction."""
    response = await async_client.get("/api/v1/live-20/results?direction=LONG")

    assert response.status_code == 200
    data = response.json()

    # Should only return LONG results
    assert data["total"] == 1
    assert all(r["direction"] == "LONG" for r in data["results"])

    # Counts should still reflect all results
    assert data["counts"]["long"] == 1
    assert data["counts"]["short"] == 1
    assert data["counts"]["no_setup"] == 1

    # Verify symbol
    assert data["results"][0]["stock"] == "AAPL"


@pytest.mark.asyncio
async def test_get_results_filter_by_short(async_client: AsyncClient, sample_live20_results):
    """Test filtering results by SHORT direction."""
    response = await async_client.get("/api/v1/live-20/results?direction=SHORT")

    assert response.status_code == 200
    data = response.json()

    assert data["total"] == 1
    assert all(r["direction"] == "SHORT" for r in data["results"])
    assert data["results"][0]["stock"] == "TSLA"


@pytest.mark.asyncio
async def test_get_results_filter_by_no_setup(async_client: AsyncClient, sample_live20_results):
    """Test filtering results by NO_SETUP direction."""
    response = await async_client.get("/api/v1/live-20/results?direction=NO_SETUP")

    assert response.status_code == 200
    data = response.json()

    assert data["total"] == 1
    assert all(r["direction"] == "NO_SETUP" for r in data["results"])
    assert data["results"][0]["stock"] == "MSFT"


@pytest.mark.asyncio
async def test_get_results_min_score_filter(async_client: AsyncClient, sample_live20_results):
    """Test filtering results by minimum confidence score."""
    response = await async_client.get("/api/v1/live-20/results?min_score=70")

    assert response.status_code == 200
    data = response.json()

    # Should only return results with score >= 70
    assert data["total"] == 1
    assert all(r["confidence_score"] >= 70 for r in data["results"])
    assert data["results"][0]["stock"] == "AAPL"


@pytest.mark.asyncio
async def test_get_results_combined_filters(async_client: AsyncClient, sample_live20_results):
    """Test combining direction and minimum score filters."""
    response = await async_client.get(
        "/api/v1/live-20/results?direction=LONG&min_score=70"
    )

    assert response.status_code == 200
    data = response.json()

    # Should only return LONG results with score >= 70
    assert data["total"] == 1
    assert data["results"][0]["stock"] == "AAPL"
    assert data["results"][0]["confidence_score"] == 80
    assert data["results"][0]["direction"] == "LONG"


@pytest.mark.asyncio
async def test_get_results_invalid_direction(async_client: AsyncClient):
    """Test validation error for invalid direction parameter."""
    response = await async_client.get("/api/v1/live-20/results?direction=INVALID")
    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_get_results_invalid_min_score(async_client: AsyncClient):
    """Test validation errors for invalid min_score values."""
    # Score above maximum (> 100)
    response = await async_client.get("/api/v1/live-20/results?min_score=150")
    assert response.status_code == 422

    # Negative score
    response = await async_client.get("/api/v1/live-20/results?min_score=-10")
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_get_results_invalid_limit(async_client: AsyncClient):
    """Test validation errors for invalid limit values."""
    # Limit above maximum (> 500)
    response = await async_client.get("/api/v1/live-20/results?limit=600")
    assert response.status_code == 422

    # Zero or negative limit
    response = await async_client.get("/api/v1/live-20/results?limit=0")
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_results_decimal_serialization(async_client: AsyncClient, sample_live20_results):
    """Test proper JSON serialization of Decimal fields as floats."""
    response = await async_client.get("/api/v1/live-20/results?direction=LONG")

    assert response.status_code == 200
    data = response.json()

    # Verify Decimal fields are returned as floats
    result = data["results"][0]
    assert isinstance(result["entry_price"], float)
    assert isinstance(result["ma20_distance_pct"], float)
    assert isinstance(result["cci_value"], float)


@pytest.mark.asyncio
async def test_results_empty_database(async_client: AsyncClient):
    """Test behavior when no results exist in database."""
    response = await async_client.get("/api/v1/live-20/results")

    assert response.status_code == 200
    data = response.json()

    assert data["total"] == 0
    assert data["counts"]["long"] == 0
    assert data["counts"]["short"] == 0
    assert data["counts"]["no_setup"] == 0
    assert data["results"] == []


@pytest.mark.asyncio
async def test_analyze_with_multiple_lists(async_client: AsyncClient):
    """Test analysis with multiple source lists (new multi-list format)."""
    response = await async_client.post(
        "/api/v1/live-20/analyze",
        json={
            "symbols": ["AAPL", "TSLA", "MSFT"],
            "source_lists": [
                {"id": 1, "name": "Tech Giants"},
                {"id": 2, "name": "Growth Stocks"},
            ],
        },
    )

    assert response.status_code == 200
    data = response.json()

    # Verify async response structure
    assert data["status"] == "pending"
    assert data["total"] == 3

    # Verify source_lists are stored by checking the run detail
    run_response = await async_client.get(f"/api/v1/live-20/runs/{data['run_id']}")
    run_data = run_response.json()

    assert run_data["source_lists"] is not None
    assert len(run_data["source_lists"]) == 2
    assert run_data["source_lists"][0]["id"] == 1
    assert run_data["source_lists"][0]["name"] == "Tech Giants"
    assert run_data["source_lists"][1]["id"] == 2
    assert run_data["source_lists"][1]["name"] == "Growth Stocks"

    # Legacy fields should be None when using source_lists
    assert run_data["stock_list_id"] is None
    assert run_data["stock_list_name"] is None


@pytest.mark.asyncio
async def test_analyze_backward_compatibility_single_list(async_client: AsyncClient):
    """Test backward compatibility with legacy stock_list_id format."""
    response = await async_client.post(
        "/api/v1/live-20/analyze",
        json={
            "symbols": ["AAPL", "TSLA"],
            "stock_list_id": 5,
            "stock_list_name": "Tech Stocks",
        },
    )

    assert response.status_code == 200
    data = response.json()

    # Verify async response structure
    assert data["status"] == "pending"
    assert data["total"] == 2

    # Verify legacy fields are stored
    run_response = await async_client.get(f"/api/v1/live-20/runs/{data['run_id']}")
    run_data = run_response.json()

    assert run_data["stock_list_id"] == 5
    assert run_data["stock_list_name"] == "Tech Stocks"
    assert run_data["source_lists"] is None


@pytest.mark.asyncio
async def test_analyze_rejects_both_list_formats(async_client: AsyncClient):
    """Test validation error when both list formats are provided simultaneously."""
    response = await async_client.post(
        "/api/v1/live-20/analyze",
        json={
            "symbols": ["AAPL", "TSLA"],
            "stock_list_id": 5,
            "stock_list_name": "Tech Stocks",
            "source_lists": [
                {"id": 1, "name": "Tech Giants"},
            ],
        },
    )

    assert response.status_code == 422
    error_data = response.json()

    # Verify error message indicates the format conflict
    assert "detail" in error_data
    error_str = str(error_data["detail"])
    assert "stock_list_id" in error_str or "source_lists" in error_str


@pytest.mark.asyncio
async def test_analyze_max_500_symbols(async_client: AsyncClient):
    """Test enforcement of 500 symbol maximum limit."""
    # Exactly 500 symbols should succeed
    symbols_500 = [f"SYM{i}" for i in range(500)]
    response = await async_client.post(
        "/api/v1/live-20/analyze",
        json={"symbols": symbols_500},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 500

    # 501 symbols should fail validation
    symbols_501 = [f"SYM{i}" for i in range(501)]
    response = await async_client.post(
        "/api/v1/live-20/analyze",
        json={"symbols": symbols_501},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_analyze_max_10_lists(async_client: AsyncClient):
    """Test enforcement of 10 source lists maximum limit."""
    # Exactly 10 lists should succeed
    lists_10 = [{"id": i, "name": f"List {i}"} for i in range(1, 11)]
    response = await async_client.post(
        "/api/v1/live-20/analyze",
        json={
            "symbols": ["AAPL", "TSLA"],
            "source_lists": lists_10,
        },
    )
    assert response.status_code == 200

    # 11 lists should fail validation
    lists_11 = [{"id": i, "name": f"List {i}"} for i in range(1, 12)]
    response = await async_client.post(
        "/api/v1/live-20/analyze",
        json={
            "symbols": ["AAPL", "TSLA"],
            "source_lists": lists_11,
        },
    )
    assert response.status_code == 422
