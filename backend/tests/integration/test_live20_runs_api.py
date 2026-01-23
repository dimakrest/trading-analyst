"""Integration tests for Live 20 Runs API endpoints.

Tests verify the complete functionality of the Live 20 runs management system:
1. Run creation via analyze endpoint with run_id tracking (async queue pattern)
2. Run listing with pagination support
3. Filtering capabilities (date range, direction, symbol search)
4. Run detail retrieval with linked recommendations
5. Soft-delete functionality
6. Error handling (404 for non-existent/deleted runs)

All tests use real database operations to verify end-to-end behavior.
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from urllib.parse import quote

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.live20_run import Live20Run
from app.models.recommendation import Recommendation, RecommendationSource

# Mark all tests in this module as integration tests
pytestmark = pytest.mark.integration


@pytest.fixture
async def sample_run_with_recommendations(db_session: AsyncSession) -> Live20Run:
    """Create a sample Live20Run with linked recommendations for testing.

    Creates a run with three symbols (AAPL, MSFT, GOOGL) and one recommendation
    for each direction (LONG, SHORT, NO_SETUP) to facilitate filtering tests.
    """
    # Create run with counts matching recommendations
    run = Live20Run(
        input_symbols=["AAPL", "MSFT", "GOOGL"],
        symbol_count=3,
        long_count=1,
        short_count=1,
        no_setup_count=1,
        status="completed",
        processed_count=3,
    )
    db_session.add(run)
    await db_session.flush()

    # Create one recommendation for each direction
    recommendations = [
        Recommendation(
            stock="AAPL",
            source=RecommendationSource.LIVE_20.value,
            recommendation="LONG",
            confidence_score=80,
            reasoning="Live 20 mean reversion analysis",
            entry_price=Decimal("150.50"),
                        live20_direction="LONG",
            live20_run_id=run.id,
        ),
        Recommendation(
            stock="MSFT",
            source=RecommendationSource.LIVE_20.value,
            recommendation="SHORT",
            confidence_score=60,
            reasoning="Live 20 mean reversion analysis",
            entry_price=Decimal("350.00"),
                        live20_direction="SHORT",
            live20_run_id=run.id,
        ),
        Recommendation(
            stock="GOOGL",
            source=RecommendationSource.LIVE_20.value,
            recommendation="NO_SETUP",
            confidence_score=40,
            reasoning="Live 20 mean reversion analysis",
            entry_price=Decimal("140.00"),
                        live20_direction="NO_SETUP",
            live20_run_id=run.id,
        ),
    ]

    for rec in recommendations:
        db_session.add(rec)

    await db_session.commit()
    await db_session.refresh(run)

    return run


@pytest.mark.asyncio
async def test_analyze_creates_pending_run_and_returns_run_id(async_client: AsyncClient):
    """Test that POST /analyze creates a pending Live20Run and returns immediately.

    With the async queue pattern:
    1. A run is created FIRST with status='pending'
    2. Response returns immediately with run_id
    3. Worker processes the symbols in the background
    """
    response = await async_client.post(
        "/api/v1/live-20/analyze",
        json={"symbols": ["AAPL", "TSLA"]},
    )

    assert response.status_code == 200
    data = response.json()

    # Verify run_id is returned
    assert "run_id" in data
    assert data["run_id"] is not None
    assert isinstance(data["run_id"], int)

    # Verify async response structure
    assert data["status"] == "pending"
    assert data["total"] == 2
    assert data["message"] == "Run queued for processing"

    # Verify the run was actually created in the database
    run_response = await async_client.get(f"/api/v1/live-20/runs/{data['run_id']}")
    assert run_response.status_code == 200
    run_data = run_response.json()
    assert run_data["status"] == "pending"
    assert run_data["symbol_count"] == 2
    assert run_data["input_symbols"] == ["AAPL", "TSLA"]


@pytest.mark.asyncio
async def test_analyze_always_creates_run(async_client: AsyncClient):
    """Test that a run is always created, even for potentially invalid symbols.

    With the async queue pattern, we create a run FIRST, then process.
    Error handling happens during processing by the worker, not at creation time.
    """
    response = await async_client.post(
        "/api/v1/live-20/analyze",
        json={"symbols": ["INVALID_SYMBOL"]},
    )

    assert response.status_code == 200
    data = response.json()

    # Run is always created with the async pattern
    assert data["run_id"] is not None
    assert data["status"] == "pending"
    assert data["total"] == 1


@pytest.mark.asyncio
async def test_list_runs_empty(async_client: AsyncClient):
    """Test GET /runs with empty database."""
    response = await async_client.get("/api/v1/live-20/runs")

    assert response.status_code == 200
    data = response.json()

    assert data["items"] == []
    assert data["total"] == 0
    assert data["has_more"] is False
    assert data["limit"] == 20
    assert data["offset"] == 0


@pytest.mark.asyncio
async def test_list_runs_with_data(async_client: AsyncClient, sample_run_with_recommendations):
    """Test GET /runs returns runs with summary data."""
    response = await async_client.get("/api/v1/live-20/runs")

    assert response.status_code == 200
    data = response.json()

    assert data["total"] == 1
    assert data["has_more"] is False
    assert len(data["items"]) == 1

    run = data["items"][0]
    assert run["id"] == sample_run_with_recommendations.id
    assert run["status"] == "completed"
    assert run["symbol_count"] == 3
    assert run["processed_count"] == 3
    assert run["long_count"] == 1
    assert run["short_count"] == 1
    assert run["no_setup_count"] == 1
    assert "created_at" in run


@pytest.mark.asyncio
async def test_list_runs_pagination(async_client: AsyncClient, db_session: AsyncSession):
    """Test GET /runs pagination with limit and offset."""
    # Create 5 runs
    for i in range(5):
        run = Live20Run(
            input_symbols=["SYM1", "SYM2"],
            symbol_count=2,
            long_count=1,
            short_count=0,
            no_setup_count=1,
        )
        db_session.add(run)
    await db_session.commit()

    # Get first page (limit=2)
    response = await async_client.get("/api/v1/live-20/runs?limit=2&offset=0")
    assert response.status_code == 200
    data = response.json()

    assert data["total"] == 5
    assert data["has_more"] is True
    assert data["limit"] == 2
    assert data["offset"] == 0
    assert len(data["items"]) == 2

    # Get second page (limit=2, offset=2)
    response = await async_client.get("/api/v1/live-20/runs?limit=2&offset=2")
    data = response.json()

    assert data["total"] == 5
    assert data["has_more"] is True
    assert data["limit"] == 2
    assert data["offset"] == 2
    assert len(data["items"]) == 2


@pytest.mark.asyncio
async def test_list_runs_filter_by_direction_long(async_client: AsyncClient, db_session: AsyncSession):
    """Test GET /runs?has_direction=LONG filters correctly."""
    # Create run with LONG
    run1 = Live20Run(
        input_symbols=["AAPL"],
        symbol_count=1,
        long_count=1,
        short_count=0,
        no_setup_count=0,
    )
    # Create run with SHORT only
    run2 = Live20Run(
        input_symbols=["TSLA"],
        symbol_count=1,
        long_count=0,
        short_count=1,
        no_setup_count=0,
    )
    db_session.add(run1)
    db_session.add(run2)
    await db_session.commit()

    response = await async_client.get("/api/v1/live-20/runs?has_direction=LONG")
    assert response.status_code == 200
    data = response.json()

    # Should only return run1
    assert data["total"] == 1
    assert data["items"][0]["long_count"] > 0


@pytest.mark.asyncio
async def test_list_runs_filter_by_direction_short(async_client: AsyncClient, db_session: AsyncSession):
    """Test GET /runs?has_direction=SHORT filters correctly."""
    # Create run with SHORT
    run1 = Live20Run(
        input_symbols=["TSLA"],
        symbol_count=1,
        long_count=0,
        short_count=1,
        no_setup_count=0,
    )
    # Create run with LONG only
    run2 = Live20Run(
        input_symbols=["AAPL"],
        symbol_count=1,
        long_count=1,
        short_count=0,
        no_setup_count=0,
    )
    db_session.add(run1)
    db_session.add(run2)
    await db_session.commit()

    response = await async_client.get("/api/v1/live-20/runs?has_direction=SHORT")
    assert response.status_code == 200
    data = response.json()

    # Should only return run1
    assert data["total"] == 1
    assert data["items"][0]["short_count"] > 0


@pytest.mark.asyncio
async def test_list_runs_filter_by_symbol(async_client: AsyncClient, db_session: AsyncSession):
    """Test GET /runs?symbol=AAPL filters correctly."""
    # Create run with AAPL
    run1 = Live20Run(
        input_symbols=["AAPL", "MSFT"],
        symbol_count=2,
        long_count=1,
        short_count=1,
        no_setup_count=0,
    )
    # Create run without AAPL
    run2 = Live20Run(
        input_symbols=["TSLA", "GOOGL"],
        symbol_count=2,
        long_count=1,
        short_count=1,
        no_setup_count=0,
    )
    db_session.add(run1)
    db_session.add(run2)
    await db_session.commit()

    response = await async_client.get("/api/v1/live-20/runs?symbol=AAPL")
    assert response.status_code == 200
    data = response.json()

    # Should only return run1
    assert data["total"] == 1


@pytest.mark.asyncio
async def test_list_runs_filter_by_date_range(async_client: AsyncClient, db_session: AsyncSession):
    """Test GET /runs?date_from=X filters runs by creation date correctly."""
    now = datetime.now(timezone.utc)
    yesterday = now - timedelta(days=1)

    # Create run from yesterday (manually set created_at)
    run1 = Live20Run(
        input_symbols=["AAPL"],
        symbol_count=1,
        long_count=1,
        short_count=0,
        no_setup_count=0,
    )
    run1.created_at = yesterday
    db_session.add(run1)
    await db_session.flush()

    # Create run from now
    run2 = Live20Run(
        input_symbols=["TSLA"],
        symbol_count=1,
        long_count=0,
        short_count=1,
        no_setup_count=0,
    )
    db_session.add(run2)
    await db_session.commit()

    # Filter to only get today's run using URL-encoded datetime
    date_from_encoded = quote(now.isoformat())
    response = await async_client.get(
        f"/api/v1/live-20/runs?date_from={date_from_encoded}"
    )
    assert response.status_code == 200
    data = response.json()

    # Should only return run2 (created after date_from)
    assert data["total"] == 1


@pytest.mark.asyncio
async def test_get_run_details(async_client: AsyncClient, sample_run_with_recommendations):
    """Test GET /runs/{run_id} returns full run details with recommendations."""
    run_id = sample_run_with_recommendations.id

    response = await async_client.get(f"/api/v1/live-20/runs/{run_id}")
    assert response.status_code == 200
    data = response.json()

    # Verify run metadata
    assert data["id"] == run_id
    assert data["status"] == "completed"
    assert data["symbol_count"] == 3
    assert data["processed_count"] == 3
    assert data["long_count"] == 1
    assert data["short_count"] == 1
    assert data["no_setup_count"] == 1
    assert data["input_symbols"] == ["AAPL", "MSFT", "GOOGL"]

    # Verify recommendations are included
    assert "results" in data
    assert len(data["results"]) == 3

    # Verify recommendations are sorted by confidence_score descending
    assert data["results"][0]["confidence_score"] >= data["results"][1]["confidence_score"]
    assert data["results"][1]["confidence_score"] >= data["results"][2]["confidence_score"]

    # Verify recommendation structure contains required fields
    result = data["results"][0]
    assert "id" in result
    assert "stock" in result
    assert "recommendation" in result
    assert "confidence_score" in result


@pytest.mark.asyncio
async def test_get_run_not_found(async_client: AsyncClient):
    """Test GET /runs/{run_id} returns 404 for non-existent run."""
    response = await async_client.get("/api/v1/live-20/runs/99999")
    assert response.status_code == 404
    assert "Run not found" in response.json()["detail"]


@pytest.mark.asyncio
async def test_get_run_soft_deleted(async_client: AsyncClient, db_session: AsyncSession):
    """Test GET /runs/{run_id} excludes soft-deleted runs."""
    # Create and soft-delete a run
    run = Live20Run(
        input_symbols=["AAPL"],
        symbol_count=1,
        long_count=1,
        short_count=0,
        no_setup_count=0,
    )
    run.deleted_at = datetime.now(timezone.utc)
    db_session.add(run)
    await db_session.commit()
    await db_session.refresh(run)

    # Try to get soft-deleted run
    response = await async_client.get(f"/api/v1/live-20/runs/{run.id}")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_run_success(async_client: AsyncClient, sample_run_with_recommendations):
    """Test DELETE /runs/{run_id} soft-deletes completed run successfully."""
    run_id = sample_run_with_recommendations.id

    response = await async_client.delete(f"/api/v1/live-20/runs/{run_id}")
    assert response.status_code == 204

    # Verify run is soft-deleted and no longer accessible via GET
    get_response = await async_client.get(f"/api/v1/live-20/runs/{run_id}")
    assert get_response.status_code == 404


@pytest.mark.asyncio
async def test_delete_run_not_found(async_client: AsyncClient):
    """Test DELETE /runs/{run_id} returns 404 for non-existent run."""
    response = await async_client.delete("/api/v1/live-20/runs/99999")
    assert response.status_code == 404
    assert "Run not found" in response.json()["detail"]


@pytest.mark.asyncio
async def test_list_runs_excludes_soft_deleted(async_client: AsyncClient, db_session: AsyncSession):
    """Test GET /runs excludes soft-deleted runs."""
    # Create active run
    run1 = Live20Run(
        input_symbols=["AAPL"],
        symbol_count=1,
        long_count=1,
        short_count=0,
        no_setup_count=0,
    )
    # Create soft-deleted run
    run2 = Live20Run(
        input_symbols=["TSLA"],
        symbol_count=1,
        long_count=0,
        short_count=1,
        no_setup_count=0,
    )
    run2.deleted_at = datetime.now(timezone.utc)

    db_session.add(run1)
    db_session.add(run2)
    await db_session.commit()

    response = await async_client.get("/api/v1/live-20/runs")
    assert response.status_code == 200
    data = response.json()

    # Should only return active run
    assert data["total"] == 1


@pytest.mark.asyncio
async def test_list_runs_validation_errors(async_client: AsyncClient):
    """Test GET /runs returns validation errors for invalid parameters."""
    # Invalid limit (exceeds maximum of 100)
    response = await async_client.get("/api/v1/live-20/runs?limit=150")
    assert response.status_code == 422

    # Invalid limit (below minimum of 1)
    response = await async_client.get("/api/v1/live-20/runs?limit=0")
    assert response.status_code == 422

    # Invalid offset (negative value)
    response = await async_client.get("/api/v1/live-20/runs?offset=-1")
    assert response.status_code == 422

    # Invalid has_direction (not one of LONG/SHORT/NO_SETUP)
    response = await async_client.get("/api/v1/live-20/runs?has_direction=INVALID")
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_get_run_details_includes_failed_symbols(
    async_client: AsyncClient, db_session: AsyncSession
):
    """Test GET /runs/{run_id} returns failed_symbols when present."""
    # Create run with failed symbols
    run = Live20Run(
        input_symbols=["AAPL", "MSFT", "INVALID"],
        symbol_count=3,
        long_count=1,
        short_count=1,
        no_setup_count=0,
        status="completed",
        processed_count=3,
        failed_symbols={"INVALID": "Symbol not found"},
    )
    db_session.add(run)
    await db_session.commit()
    await db_session.refresh(run)

    response = await async_client.get(f"/api/v1/live-20/runs/{run.id}")
    assert response.status_code == 200
    data = response.json()

    # Verify failed_symbols is included in response
    assert "failed_symbols" in data
    assert data["failed_symbols"] == {"INVALID": "Symbol not found"}


@pytest.mark.asyncio
async def test_get_run_details_empty_failed_symbols(
    async_client: AsyncClient, sample_run_with_recommendations
):
    """Test GET /runs/{run_id} returns empty dict when no failures."""
    run_id = sample_run_with_recommendations.id

    response = await async_client.get(f"/api/v1/live-20/runs/{run_id}")
    assert response.status_code == 200
    data = response.json()

    # Verify failed_symbols is an empty dict
    assert "failed_symbols" in data
    assert data["failed_symbols"] == {}


@pytest.mark.asyncio
async def test_get_run_details_multiple_failed_symbols(
    async_client: AsyncClient, db_session: AsyncSession
):
    """Test GET /runs/{run_id} returns multiple failed symbols."""
    # Create run with multiple failed symbols
    run = Live20Run(
        input_symbols=["AAPL", "INVALID1", "INVALID2", "INVALID3"],
        symbol_count=4,
        long_count=1,
        short_count=0,
        no_setup_count=0,
        status="completed",
        processed_count=4,
        failed_symbols={
            "INVALID1": "Rate limited",
            "INVALID2": "Data unavailable",
            "INVALID3": "API timeout",
        },
    )
    db_session.add(run)
    await db_session.commit()
    await db_session.refresh(run)

    response = await async_client.get(f"/api/v1/live-20/runs/{run.id}")
    assert response.status_code == 200
    data = response.json()

    # Verify all failed symbols are present
    assert len(data["failed_symbols"]) == 3
    assert data["failed_symbols"]["INVALID1"] == "Rate limited"
    assert data["failed_symbols"]["INVALID2"] == "Data unavailable"
    assert data["failed_symbols"]["INVALID3"] == "API timeout"


@pytest.mark.asyncio
async def test_list_runs_includes_failed_count(
    async_client: AsyncClient, db_session: AsyncSession
):
    """Test GET /runs list summary includes failed_count."""
    # Create run with failed symbols
    run = Live20Run(
        input_symbols=["AAPL", "INVALID1", "INVALID2"],
        symbol_count=3,
        long_count=1,
        short_count=0,
        no_setup_count=0,
        status="completed",
        processed_count=3,
        failed_symbols={
            "INVALID1": "Rate limited",
            "INVALID2": "Data unavailable",
        },
    )
    db_session.add(run)
    await db_session.commit()

    response = await async_client.get("/api/v1/live-20/runs")
    assert response.status_code == 200
    data = response.json()

    # Verify failed_count is present and correct
    assert data["total"] == 1
    assert data["items"][0]["failed_count"] == 2


@pytest.mark.asyncio
async def test_delete_pending_run_returns_400(
    async_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """DELETE on pending run returns 400 - use cancel endpoint instead."""
    # Create pending run
    run = Live20Run(
        input_symbols=["AAPL", "MSFT"],
        symbol_count=2,
        status="pending",
    )
    db_session.add(run)
    await db_session.commit()
    await db_session.refresh(run)
    run_id = run.id

    # DELETE should return 400
    response = await async_client.delete(f"/api/v1/live-20/runs/{run_id}")
    assert response.status_code == 400
    assert "Cannot delete pending run" in response.json()["detail"]
    assert "cancel" in response.json()["detail"].lower()

    # Verify status unchanged
    await db_session.refresh(run)
    assert run.status == "pending"


@pytest.mark.asyncio
async def test_delete_running_run_returns_400(
    async_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """DELETE on running run returns 400 - use cancel endpoint instead."""
    run = Live20Run(
        input_symbols=["AAPL", "MSFT", "GOOGL"],
        symbol_count=3,
        status="running",
    )
    db_session.add(run)
    await db_session.commit()
    await db_session.refresh(run)
    run_id = run.id

    response = await async_client.delete(f"/api/v1/live-20/runs/{run_id}")
    assert response.status_code == 400
    assert "Cannot delete running run" in response.json()["detail"]
    assert "cancel" in response.json()["detail"].lower()

    # Verify status unchanged
    await db_session.refresh(run)
    assert run.status == "running"


@pytest.mark.asyncio
async def test_delete_completed_run_soft_deletes(
    async_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """DELETE on completed run soft-deletes it."""
    run = Live20Run(
        input_symbols=["AAPL"],
        symbol_count=1,
        status="completed",
    )
    db_session.add(run)
    await db_session.commit()
    await db_session.refresh(run)
    run_id = run.id

    response = await async_client.delete(f"/api/v1/live-20/runs/{run_id}")
    assert response.status_code == 204

    # Verify soft-deleted (deleted_at set, not in list)
    await db_session.refresh(run)
    assert run.deleted_at is not None


@pytest.mark.asyncio
async def test_delete_cancelled_run_soft_deletes(
    async_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """DELETE on already-cancelled run soft-deletes it."""
    run = Live20Run(
        input_symbols=["AAPL"],
        symbol_count=1,
        status="cancelled",
    )
    db_session.add(run)
    await db_session.commit()
    await db_session.refresh(run)
    run_id = run.id

    response = await async_client.delete(f"/api/v1/live-20/runs/{run_id}")
    assert response.status_code == 204

    await db_session.refresh(run)
    assert run.deleted_at is not None


@pytest.mark.asyncio
async def test_cancel_pending_run_success(
    async_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """POST /runs/{id}/cancel sets pending run to cancelled."""
    run = Live20Run(
        input_symbols=["AAPL", "MSFT"],
        symbol_count=2,
        status="pending",
    )
    db_session.add(run)
    await db_session.commit()
    await db_session.refresh(run)
    run_id = run.id

    response = await async_client.post(f"/api/v1/live-20/runs/{run_id}/cancel")
    assert response.status_code == 204

    # Verify status changed to cancelled
    await db_session.refresh(run)
    assert run.status == "cancelled"


@pytest.mark.asyncio
async def test_cancel_running_run_success(
    async_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """POST /runs/{id}/cancel sets running run to cancelled."""
    run = Live20Run(
        input_symbols=["AAPL", "MSFT", "GOOGL"],
        symbol_count=3,
        status="running",
    )
    db_session.add(run)
    await db_session.commit()
    await db_session.refresh(run)
    run_id = run.id

    response = await async_client.post(f"/api/v1/live-20/runs/{run_id}/cancel")
    assert response.status_code == 204

    await db_session.refresh(run)
    assert run.status == "cancelled"


@pytest.mark.asyncio
async def test_cancel_completed_run_fails(
    async_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """POST /runs/{id}/cancel on completed run returns 400."""
    run = Live20Run(
        input_symbols=["AAPL"],
        symbol_count=1,
        status="completed",
    )
    db_session.add(run)
    await db_session.commit()
    await db_session.refresh(run)
    run_id = run.id

    response = await async_client.post(f"/api/v1/live-20/runs/{run_id}/cancel")
    assert response.status_code == 400
    assert "Cannot cancel completed run" in response.json()["detail"]


@pytest.mark.asyncio
async def test_cancel_cancelled_run_fails(
    async_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """POST /runs/{id}/cancel on already-cancelled run returns 400."""
    run = Live20Run(
        input_symbols=["AAPL"],
        symbol_count=1,
        status="cancelled",
    )
    db_session.add(run)
    await db_session.commit()
    await db_session.refresh(run)
    run_id = run.id

    response = await async_client.post(f"/api/v1/live-20/runs/{run_id}/cancel")
    assert response.status_code == 400
    assert "Cannot cancel cancelled run" in response.json()["detail"]


@pytest.mark.asyncio
async def test_cancel_failed_run_fails(
    async_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """POST /runs/{id}/cancel on failed run returns 400."""
    run = Live20Run(
        input_symbols=["AAPL"],
        symbol_count=1,
        status="failed",
    )
    db_session.add(run)
    await db_session.commit()
    await db_session.refresh(run)
    run_id = run.id

    response = await async_client.post(f"/api/v1/live-20/runs/{run_id}/cancel")
    assert response.status_code == 400
    assert "Cannot cancel failed run" in response.json()["detail"]


@pytest.mark.asyncio
async def test_cancel_nonexistent_run_fails(
    async_client: AsyncClient,
) -> None:
    """POST /runs/{id}/cancel on non-existent run returns 404."""
    response = await async_client.post("/api/v1/live-20/runs/99999/cancel")
    assert response.status_code == 404
    assert "Run not found" in response.json()["detail"]
