"""Integration tests for Live20 RSI-2 pipeline.

Tests the full pipeline from API request through worker processing to database
storage, verifying that scoring_algorithm flows correctly and fields are
populated exclusively (CCI vs RSI-2).
"""
import pytest
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.recommendation import Recommendation, RecommendationSource
from app.repositories.live20_run_repository import Live20RunRepository
from app.schemas.live20 import Live20AnalyzeRequest
from app.services.live20_service import Live20Service


# Mark all tests in this module as integration tests
pytestmark = pytest.mark.integration


class TestLive20RSI2Pipeline:
    """Test RSI-2 scoring algorithm integration through full pipeline."""

    @pytest.mark.asyncio
    async def test_rsi2_run_creates_rsi2_fields_nulls_cci(
        self,
        test_session_factory,
        db_session: AsyncSession,
    ):
        """RSI-2 run should populate rsi2 fields and NULL CCI fields."""
        # Create a Live20 service with RSI-2 algorithm
        service = Live20Service(test_session_factory, scoring_algorithm="rsi2")

        # Analyze a symbol (using AAPL which should have data)
        result = await service._analyze_symbol("AAPL")

        # Skip test if insufficient data (test environment may not have price data)
        if result.status == "error" and "Insufficient data" in (result.error_message or ""):
            pytest.skip("Insufficient price data in test environment")

        assert result.status == "success", f"Analysis failed: {result.error_message}"
        assert result.recommendation is not None

        rec = result.recommendation

        # Verify scoring algorithm is set
        assert rec.live20_scoring_algorithm == "rsi2"

        # Verify RSI-2 fields are populated
        assert rec.live20_rsi2_value is not None
        assert isinstance(rec.live20_rsi2_value, Decimal)
        assert 0 <= rec.live20_rsi2_value <= 100
        assert rec.live20_rsi2_score is not None
        assert rec.live20_rsi2_score in [0, 5, 10, 15, 20]

        # Verify CCI fields are NULL (exclusive)
        assert rec.live20_cci_value is None
        assert rec.live20_cci_direction is None
        assert rec.live20_cci_zone is None
        assert rec.live20_cci_aligned is None

    @pytest.mark.asyncio
    async def test_cci_run_creates_cci_fields_nulls_rsi2(
        self,
        test_session_factory,
        db_session: AsyncSession,
    ):
        """CCI run (default) should populate CCI fields and NULL RSI-2 fields."""
        # Create a Live20 service with default (CCI) algorithm
        service = Live20Service(test_session_factory, scoring_algorithm="cci")

        # Analyze a symbol
        result = await service._analyze_symbol("AAPL")

        # Skip test if insufficient data (test environment may not have price data)
        if result.status == "error" and "Insufficient data" in (result.error_message or ""):
            pytest.skip("Insufficient price data in test environment")

        assert result.status == "success", f"Analysis failed: {result.error_message}"
        assert result.recommendation is not None

        rec = result.recommendation

        # Verify scoring algorithm is set
        assert rec.live20_scoring_algorithm == "cci"

        # Verify CCI fields are populated
        assert rec.live20_cci_value is not None
        assert isinstance(rec.live20_cci_value, Decimal)
        assert rec.live20_cci_direction is not None
        assert rec.live20_cci_direction in ["rising", "falling", "flat"]
        assert rec.live20_cci_zone is not None
        assert rec.live20_cci_zone in ["oversold", "neutral", "overbought"]
        assert rec.live20_cci_aligned is not None

        # Verify RSI-2 fields are NULL (exclusive)
        assert rec.live20_rsi2_value is None
        assert rec.live20_rsi2_score is None

    @pytest.mark.asyncio
    async def test_api_defaults_to_cci_when_no_algorithm_specified(
        self,
        test_session_factory,
        db_session: AsyncSession,
    ):
        """When no scoring_algorithm specified, should default to CCI."""
        # Create a run without specifying scoring_algorithm
        repo = Live20RunRepository(db_session)
        run = await repo.create(
            input_symbols=["AAPL"],
            symbol_count=1,
            status="pending",
        )

        assert run.scoring_algorithm == "cci"

    @pytest.mark.asyncio
    async def test_api_accepts_rsi2_algorithm(
        self,
        test_session_factory,
        db_session: AsyncSession,
    ):
        """API should accept scoring_algorithm='rsi2' parameter."""
        # Create a run with RSI-2 algorithm
        repo = Live20RunRepository(db_session)
        run = await repo.create(
            input_symbols=["AAPL"],
            symbol_count=1,
            status="pending",
            scoring_algorithm="rsi2",
        )

        assert run.scoring_algorithm == "rsi2"

    @pytest.mark.asyncio
    async def test_live20_request_schema_validates_scoring_algorithm(self):
        """Live20AnalyzeRequest should validate scoring_algorithm field."""
        # Valid CCI
        request = Live20AnalyzeRequest(
            symbols=["AAPL"],
            scoring_algorithm="cci"
        )
        assert request.scoring_algorithm == "cci"

        # Valid RSI-2
        request = Live20AnalyzeRequest(
            symbols=["AAPL"],
            scoring_algorithm="rsi2"
        )
        assert request.scoring_algorithm == "rsi2"

        # Invalid algorithm should raise validation error
        with pytest.raises(Exception):  # Pydantic ValidationError
            Live20AnalyzeRequest(
                symbols=["AAPL"],
                scoring_algorithm="invalid"
            )

    @pytest.mark.asyncio
    async def test_rsi2_graduated_scoring_in_recommendation(
        self,
        test_session_factory,
        db_session: AsyncSession,
    ):
        """RSI-2 graduated scores should flow through to recommendation."""
        service = Live20Service(test_session_factory, scoring_algorithm="rsi2")

        # Analyze a symbol - we can't predict exact RSI-2 value, but we can
        # verify the score matches one of the graduated values
        result = await service._analyze_symbol("AAPL")

        # Skip test if insufficient data (test environment may not have price data)
        if result.status == "error" and "Insufficient data" in (result.error_message or ""):
            pytest.skip("Insufficient price data in test environment")

        assert result.status == "success", f"Analysis failed: {result.error_message}"
        rec = result.recommendation

        # Graduated scoring: only valid values are 0, 5, 10, 15, 20
        assert rec.live20_rsi2_score in [0, 5, 10, 15, 20]

        # Confidence score should be sum of all aligned scores
        # (not necessarily a multiple of 20 with RSI-2)
        assert 0 <= rec.confidence_score <= 100

    @pytest.mark.asyncio
    async def test_cci_backward_compatibility_score_multiple_of_20(
        self,
        test_session_factory,
        db_session: AsyncSession,
    ):
        """CCI scoring should remain binary (scores are multiples of 20)."""
        service = Live20Service(test_session_factory, scoring_algorithm="cci")

        result = await service._analyze_symbol("AAPL")

        # Skip test if insufficient data (test environment may not have price data)
        if result.status == "error" and "Insufficient data" in (result.error_message or ""):
            pytest.skip("Insufficient price data in test environment")

        assert result.status == "success", f"Analysis failed: {result.error_message}"
        rec = result.recommendation

        # CCI uses binary scoring, so total score should be multiple of 20
        assert rec.confidence_score % 20 == 0
        assert 0 <= rec.confidence_score <= 100
