"""Integration tests for Live 20 portfolio recommendation endpoint.

Tests verify:
1. POST /runs/{run_id}/recommend filters by min_score and direction
2. Various strategies produce different orderings
3. max_per_sector and max_positions constraints are applied
4. Non-existent run returns 404
5. Invalid strategy name returns 400
6. No qualifying signals returns empty list
"""

from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.live20_run import Live20Run
from app.models.recommendation import Recommendation, RecommendationSource

# Mark all tests in this module as integration tests
pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def run_with_mixed_recommendations(db_session: AsyncSession) -> Live20Run:
    """Create a completed Live20Run with a variety of LONG recommendations for testing.

    Symbols:
        AAPL  — score 90, sector XLK, atr 2.0%  (high score, low ATR)
        MSFT  — score 85, sector XLK, atr 4.0%  (high score, same sector)
        GOOGL — score 80, sector XLK, atr 3.0%  (high score, same sector)
        TSLA  — score 75, sector XLY, atr 8.0%  (different sector, high ATR)
        NVDA  — score 70, sector XLK, atr 5.0%  (lower score)
        AMD   — score 55, sector XLK, atr 1.5%  (below default threshold)
        NFLX  — score 65, sector XLC, atr 3.5%  (NO_SETUP — excluded)
    """
    run = Live20Run(
        input_symbols=["AAPL", "MSFT", "GOOGL", "TSLA", "NVDA", "AMD", "NFLX"],
        symbol_count=7,
        long_count=6,
        no_setup_count=1,
        short_count=0,
        status="completed",
        processed_count=7,
    )
    db_session.add(run)
    await db_session.flush()

    recommendations = [
        Recommendation(
            stock="AAPL",
            source=RecommendationSource.LIVE_20.value,
            recommendation="LONG",
            reasoning="test",
            confidence_score=90,
            live20_direction="LONG",
            live20_sector_etf="XLK",
            live20_atr=Decimal("2.0000"),
            live20_run_id=run.id,
        ),
        Recommendation(
            stock="MSFT",
            source=RecommendationSource.LIVE_20.value,
            recommendation="LONG",
            reasoning="test",
            confidence_score=85,
            live20_direction="LONG",
            live20_sector_etf="XLK",
            live20_atr=Decimal("4.0000"),
            live20_run_id=run.id,
        ),
        Recommendation(
            stock="GOOGL",
            source=RecommendationSource.LIVE_20.value,
            recommendation="LONG",
            reasoning="test",
            confidence_score=80,
            live20_direction="LONG",
            live20_sector_etf="XLK",
            live20_atr=Decimal("3.0000"),
            live20_run_id=run.id,
        ),
        Recommendation(
            stock="TSLA",
            source=RecommendationSource.LIVE_20.value,
            recommendation="LONG",
            reasoning="test",
            confidence_score=75,
            live20_direction="LONG",
            live20_sector_etf="XLY",
            live20_atr=Decimal("8.0000"),
            live20_run_id=run.id,
        ),
        Recommendation(
            stock="NVDA",
            source=RecommendationSource.LIVE_20.value,
            recommendation="LONG",
            reasoning="test",
            confidence_score=70,
            live20_direction="LONG",
            live20_sector_etf="XLK",
            live20_atr=Decimal("5.0000"),
            live20_run_id=run.id,
        ),
        # Below default 60 threshold — should be excluded at default min_score
        Recommendation(
            stock="AMD",
            source=RecommendationSource.LIVE_20.value,
            recommendation="LONG",
            reasoning="test",
            confidence_score=55,
            live20_direction="LONG",
            live20_sector_etf="XLK",
            live20_atr=Decimal("1.5000"),
            live20_run_id=run.id,
        ),
        # NO_SETUP — always excluded
        Recommendation(
            stock="NFLX",
            source=RecommendationSource.LIVE_20.value,
            recommendation="NO_SETUP",
            reasoning="test",
            confidence_score=65,
            live20_direction="NO_SETUP",
            live20_sector_etf="XLC",
            live20_atr=Decimal("3.5000"),
            live20_run_id=run.id,
        ),
    ]

    for rec in recommendations:
        db_session.add(rec)
    await db_session.commit()

    return run


@pytest.fixture
async def empty_run(db_session: AsyncSession) -> Live20Run:
    """Create a completed Live20Run with no qualifying LONG signals."""
    run = Live20Run(
        input_symbols=["AAPL"],
        symbol_count=1,
        long_count=0,
        no_setup_count=1,
        short_count=0,
        status="completed",
        processed_count=1,
    )
    db_session.add(run)
    await db_session.flush()

    db_session.add(
        Recommendation(
            stock="AAPL",
            source=RecommendationSource.LIVE_20.value,
            recommendation="NO_SETUP",
            reasoning="test",
            confidence_score=30,
            live20_direction="NO_SETUP",
            live20_run_id=run.id,
        )
    )
    await db_session.commit()
    return run


# ---------------------------------------------------------------------------
# 404 and error cases
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_recommend_nonexistent_run_returns_404(async_client: AsyncClient) -> None:
    """POST /runs/{run_id}/recommend with nonexistent run_id returns 404."""
    response = await async_client.post(
        "/api/v1/live-20/runs/999999/recommend",
        json={"min_score": 60, "strategy": "score_sector_low_atr"},
    )
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_recommend_invalid_strategy_returns_400(
    async_client: AsyncClient,
    run_with_mixed_recommendations: Live20Run,
) -> None:
    """POST /runs/{run_id}/recommend with unknown strategy returns 400."""
    run_id = run_with_mixed_recommendations.id
    response = await async_client.post(
        f"/api/v1/live-20/runs/{run_id}/recommend",
        json={"min_score": 60, "strategy": "this_does_not_exist"},
    )
    assert response.status_code == 400
    assert "this_does_not_exist" in response.json()["detail"]


# ---------------------------------------------------------------------------
# Empty result cases
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_recommend_no_qualifying_signals_returns_empty_list(
    async_client: AsyncClient,
    empty_run: Live20Run,
) -> None:
    """POST /runs/{run_id}/recommend with no qualifying signals returns empty items list."""
    response = await async_client.post(
        f"/api/v1/live-20/runs/{empty_run.id}/recommend",
        json={"min_score": 60, "strategy": "score_sector_low_atr"},
    )
    assert response.status_code == 200
    data = response.json()

    assert data["items"] == []
    assert data["total_qualifying"] == 0
    assert data["total_selected"] == 0
    assert data["strategy"] == "score_sector_low_atr"


@pytest.mark.asyncio
async def test_recommend_high_min_score_filters_all_out(
    async_client: AsyncClient,
    run_with_mixed_recommendations: Live20Run,
) -> None:
    """min_score=95 filters out all signals, returning empty list."""
    run_id = run_with_mixed_recommendations.id
    response = await async_client.post(
        f"/api/v1/live-20/runs/{run_id}/recommend",
        json={"min_score": 95, "strategy": "score_sector_low_atr"},
    )
    assert response.status_code == 200
    data = response.json()

    assert data["items"] == []
    assert data["total_qualifying"] == 0
    assert data["total_selected"] == 0


# ---------------------------------------------------------------------------
# Filtering — min_score
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_recommend_default_min_score_excludes_low_confidence(
    async_client: AsyncClient,
    run_with_mixed_recommendations: Live20Run,
) -> None:
    """Default min_score=60 excludes AMD (score=55) and NFLX (NO_SETUP, score=65)."""
    run_id = run_with_mixed_recommendations.id
    response = await async_client.post(
        f"/api/v1/live-20/runs/{run_id}/recommend",
        json={"min_score": 60, "strategy": "none"},
    )
    assert response.status_code == 200
    data = response.json()

    symbols = [item["symbol"] for item in data["items"]]
    assert "AMD" not in symbols    # score=55, below threshold
    assert "NFLX" not in symbols   # NO_SETUP direction


@pytest.mark.asyncio
async def test_recommend_lower_min_score_includes_more_signals(
    async_client: AsyncClient,
    run_with_mixed_recommendations: Live20Run,
) -> None:
    """min_score=50 includes AMD (score=55) but still excludes NFLX (NO_SETUP).

    max_per_sector=None is required so AMD (XLK) is not blocked by sector cap.
    """
    run_id = run_with_mixed_recommendations.id
    response = await async_client.post(
        f"/api/v1/live-20/runs/{run_id}/recommend",
        json={"min_score": 50, "strategy": "none", "max_per_sector": None},
    )
    assert response.status_code == 200
    data = response.json()

    symbols = [item["symbol"] for item in data["items"]]
    assert "AMD" in symbols        # score=55 >= 50
    assert "NFLX" not in symbols   # NO_SETUP direction always excluded


# ---------------------------------------------------------------------------
# Strategy — score_sector_low_atr
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_recommend_score_sector_low_atr_ordering(
    async_client: AsyncClient,
    run_with_mixed_recommendations: Live20Run,
) -> None:
    """score_sector_low_atr ranks by score desc then ATR asc; sector cap = 2 by default."""
    run_id = run_with_mixed_recommendations.id
    response = await async_client.post(
        f"/api/v1/live-20/runs/{run_id}/recommend",
        json={
            "min_score": 60,
            "strategy": "score_sector_low_atr",
            "max_per_sector": 2,
            "max_positions": None,
        },
    )
    assert response.status_code == 200
    data = response.json()

    assert data["strategy"] == "score_sector_low_atr"
    items = data["items"]
    symbols = [i["symbol"] for i in items]

    # AAPL (score=90, XLK), MSFT (score=85, XLK) — top 2 XLK by score then low ATR
    # TSLA (score=75, XLY) — only XLY stock
    # GOOGL (score=80, XLK) and NVDA (score=70, XLK) blocked because max_per_sector=2 for XLK
    assert "AAPL" in symbols
    assert "MSFT" in symbols
    assert "TSLA" in symbols
    assert "GOOGL" not in symbols  # XLK already at max (2)
    assert "NVDA" not in symbols   # XLK already at max (2)
    assert "AMD" not in symbols    # below min_score=60

    # AAPL should be first (highest score in XLK)
    assert symbols[0] == "AAPL"


# ---------------------------------------------------------------------------
# Strategy — score_sector_high_atr
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_recommend_score_sector_high_atr_ordering(
    async_client: AsyncClient,
    run_with_mixed_recommendations: Live20Run,
) -> None:
    """score_sector_high_atr ranks by score desc then ATR desc (high ATR preferred)."""
    run_id = run_with_mixed_recommendations.id
    response = await async_client.post(
        f"/api/v1/live-20/runs/{run_id}/recommend",
        json={
            "min_score": 60,
            "strategy": "score_sector_high_atr",
            "max_per_sector": 2,
            "max_positions": None,
        },
    )
    assert response.status_code == 200
    data = response.json()

    assert data["strategy"] == "score_sector_high_atr"
    items = data["items"]
    symbols = [i["symbol"] for i in items]

    # AAPL (score=90, XLK, atr=2%), MSFT (score=85, XLK, atr=4%) — top 2 XLK
    # TSLA (score=75, XLY, atr=8%) — only XLY stock
    assert "AAPL" in symbols
    assert "MSFT" in symbols
    assert "TSLA" in symbols

    # Within same score group, high ATR is preferred — but scores differ here,
    # so higher score always comes first regardless of ATR preference
    assert symbols[0] == "AAPL"  # score=90, highest

    # MSFT (atr=4%) beats GOOGL (atr=3%) within XLK at score=85 vs 80
    # but we already have 2 in XLK so GOOGL is blocked
    assert "GOOGL" not in symbols


# ---------------------------------------------------------------------------
# Strategy — none (FIFO)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_recommend_none_strategy_no_reordering(
    async_client: AsyncClient,
    run_with_mixed_recommendations: Live20Run,
) -> None:
    """'none' strategy preserves DB query order (confidence_score desc) with no sector cap."""
    run_id = run_with_mixed_recommendations.id
    response = await async_client.post(
        f"/api/v1/live-20/runs/{run_id}/recommend",
        json={
            "min_score": 60,
            "strategy": "none",
            "max_per_sector": None,
            "max_positions": None,
        },
    )
    assert response.status_code == 200
    data = response.json()

    assert data["strategy"] == "none"
    items = data["items"]
    symbols = [i["symbol"] for i in items]

    # All 5 qualifying LONG signals included (AMD excluded by min_score, NFLX by direction)
    assert len(items) == 5
    assert set(symbols) == {"AAPL", "MSFT", "GOOGL", "TSLA", "NVDA"}

    # FifoSelector preserves the input list order passed to select(); our qualifying list
    # is ordered by confidence_score desc from the DB query — verify it is still ordered
    scores = [i["score"] for i in items]
    assert scores == sorted(scores, reverse=True)


# ---------------------------------------------------------------------------
# Constraints — max_positions
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_recommend_max_positions_limits_total_selected(
    async_client: AsyncClient,
    run_with_mixed_recommendations: Live20Run,
) -> None:
    """max_positions=2 limits total selected to at most 2 regardless of strategy."""
    run_id = run_with_mixed_recommendations.id
    response = await async_client.post(
        f"/api/v1/live-20/runs/{run_id}/recommend",
        json={
            "min_score": 60,
            "strategy": "score_sector_low_atr",
            "max_per_sector": None,
            "max_positions": 2,
        },
    )
    assert response.status_code == 200
    data = response.json()

    assert data["total_selected"] == 2
    assert len(data["items"]) == 2

    # Qualifying signals still reflects all signals that passed min_score (5 signals)
    assert data["total_qualifying"] == 5


# ---------------------------------------------------------------------------
# Response shape
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_recommend_response_shape(
    async_client: AsyncClient,
    run_with_mixed_recommendations: Live20Run,
) -> None:
    """Verify the full response schema is correctly shaped."""
    run_id = run_with_mixed_recommendations.id
    response = await async_client.post(
        f"/api/v1/live-20/runs/{run_id}/recommend",
        json={"min_score": 60, "strategy": "score_sector_low_atr"},
    )
    assert response.status_code == 200
    data = response.json()

    # Top-level fields
    assert "strategy" in data
    assert "strategy_description" in data
    assert "items" in data
    assert "total_qualifying" in data
    assert "total_selected" in data

    assert isinstance(data["strategy"], str)
    assert isinstance(data["strategy_description"], str)
    assert isinstance(data["items"], list)
    assert isinstance(data["total_qualifying"], int)
    assert isinstance(data["total_selected"], int)
    assert data["total_selected"] == len(data["items"])

    # Item shape
    if data["items"]:
        item = data["items"][0]
        assert "symbol" in item
        assert "score" in item
        assert "sector" in item
        assert "atr_pct" in item
        assert isinstance(item["symbol"], str)
        assert isinstance(item["score"], int)


@pytest.mark.asyncio
async def test_recommend_strategy_description_is_populated(
    async_client: AsyncClient,
    run_with_mixed_recommendations: Live20Run,
) -> None:
    """strategy_description is a non-empty string matching the selector's description."""
    run_id = run_with_mixed_recommendations.id
    response = await async_client.post(
        f"/api/v1/live-20/runs/{run_id}/recommend",
        json={"min_score": 60, "strategy": "score_sector_high_atr"},
    )
    assert response.status_code == 200
    data = response.json()

    assert data["strategy"] == "score_sector_high_atr"
    assert "high" in data["strategy_description"].lower() or "atr" in data["strategy_description"].lower()
