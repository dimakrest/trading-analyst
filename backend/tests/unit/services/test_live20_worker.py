"""Tests for the Live20Worker class.

Tests the worker that processes Live20 runs from the queue.
"""
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.live20_run import Live20Run
from app.models.recommendation import Recommendation, RecommendationSource
from app.services.job_queue_service import JobQueueService
from app.services.live20_worker import Live20Worker
from app.services.live20_service import Live20Result


async def create_live20_run(
    session_factory,
    status: str = "pending",
    input_symbols: list[str] | None = None,
    existing_recommendations: list[str] | None = None,
) -> Live20Run:
    """Helper to create a Live20Run with optional existing recommendations."""
    if input_symbols is None:
        input_symbols = ["AAPL", "MSFT", "GOOGL"]

    async with session_factory() as session:
        run = Live20Run(
            status=status,
            symbol_count=len(input_symbols),
            long_count=0,
            no_setup_count=0,
            input_symbols=input_symbols,
            retry_count=0,
            max_retries=3,
            processed_count=0,
        )
        session.add(run)
        await session.flush()

        # Create existing recommendations if specified
        if existing_recommendations:
            for symbol in existing_recommendations:
                rec = Recommendation(
                    stock=symbol,
                    source=RecommendationSource.LIVE_20.value,
                    recommendation="LONG",
                    confidence_score=80,
                    reasoning="Test recommendation",
                    live20_run_id=run.id,
                    live20_direction="LONG",
                )
                session.add(rec)

        await session.commit()
        await session.refresh(run)
        return run


async def get_run_by_id(session_factory, run_id: int) -> Live20Run | None:
    """Helper to get a Live20Run by ID."""
    from sqlalchemy import select

    async with session_factory() as session:
        result = await session.execute(
            select(Live20Run).where(Live20Run.id == run_id)
        )
        return result.scalar_one_or_none()


@pytest.fixture
def mock_queue_service():
    """Create a mock queue service."""
    service = MagicMock(spec=JobQueueService)
    service.worker_id = "live20-worker-test"
    service.is_cancelled = AsyncMock(return_value=False)
    return service


@pytest.fixture
def mock_live20_result():
    """Create a mock Live20Result for successful analysis."""
    mock_rec = MagicMock()
    mock_rec.id = 1
    mock_rec.stock = "AAPL"
    mock_rec.live20_direction = "LONG"
    mock_rec.confidence_score = 80

    return Live20Result(
        symbol="AAPL",
        status="success",
        recommendation=mock_rec,
    )


@pytest.mark.unit
class TestLive20WorkerProcessJob:
    """Tests for the process_job method."""

    @pytest.mark.asyncio
    async def test_process_job_skips_already_processed(
        self, rollback_session_factory, mock_queue_service):
        """Should skip symbols that already have recommendations."""
        # Create run with AAPL already processed
        run = await create_live20_run(
            rollback_session_factory,
            status="running",
            input_symbols=["AAPL", "MSFT", "GOOGL"],
            existing_recommendations=["AAPL"],
        )

        worker = Live20Worker(rollback_session_factory, mock_queue_service)

        mock_result = MagicMock()
        mock_result.status = "success"
        mock_result.recommendation = MagicMock()
        mock_result.recommendation.id = 100
        mock_result.recommendation.live20_direction = "LONG"

        with patch(
            "app.services.live20_worker.Live20Service"
        ) as MockService:
            mock_service = MagicMock()
            mock_service._analyze_symbol = AsyncMock(return_value=mock_result)
            MockService.return_value = mock_service

            await worker.process_job(run)

            # Should only process MSFT and GOOGL (not AAPL)
            assert mock_service._analyze_symbol.call_count == 2
            called_symbols = [
                call[0][0] for call in mock_service._analyze_symbol.call_args_list
            ]
            assert "AAPL" not in called_symbols
            assert "MSFT" in called_symbols
            assert "GOOGL" in called_symbols

    @pytest.mark.asyncio
    async def test_process_job_checks_cancellation(
        self, rollback_session_factory, mock_queue_service):
        """Should check for cancellation before each batch."""
        run = await create_live20_run(
            rollback_session_factory,
            status="running",
            input_symbols=["AAPL", "MSFT", "GOOGL"],
        )

        # Cancel after first batch (first check returns False, second returns True)
        mock_queue_service.is_cancelled = AsyncMock(
            side_effect=[False, True]
        )

        worker = Live20Worker(rollback_session_factory, mock_queue_service)

        mock_result = MagicMock()
        mock_result.status = "success"
        mock_result.recommendation = MagicMock()
        mock_result.recommendation.id = 1
        mock_result.recommendation.live20_direction = "LONG"

        with patch(
            "app.services.live20_worker.Live20Service"
        ) as MockService:
            mock_service = MagicMock()
            mock_service._analyze_symbol = AsyncMock(return_value=mock_result)
            MockService.return_value = mock_service

            await worker.process_job(run)

            # Should process all 3 symbols in first batch before cancellation check stops it
            assert mock_service._analyze_symbol.call_count == 3

    @pytest.mark.asyncio
    async def test_process_job_stops_on_cancellation(
        self, rollback_session_factory, mock_queue_service):
        """Should stop processing when run is cancelled."""
        run = await create_live20_run(
            rollback_session_factory,
            status="running",
        )

        # Cancel immediately
        mock_queue_service.is_cancelled = AsyncMock(return_value=True)

        worker = Live20Worker(rollback_session_factory, mock_queue_service)

        with patch(
            "app.services.live20_worker.Live20Service"
        ) as MockService:
            mock_service = MagicMock()
            mock_service._analyze_symbol = AsyncMock()
            MockService.return_value = mock_service

            await worker.process_job(run)

            # Should not process any symbols
            mock_service._analyze_symbol.assert_not_called()

    @pytest.mark.asyncio
    async def test_process_job_all_done_early_return(
        self, rollback_session_factory, mock_queue_service):
        """Should return early if all symbols already processed."""
        # Create run with all symbols already processed
        run = await create_live20_run(
            rollback_session_factory,
            status="running",
            input_symbols=["AAPL", "MSFT"],
            existing_recommendations=["AAPL", "MSFT"],
        )

        worker = Live20Worker(rollback_session_factory, mock_queue_service)

        with patch(
            "app.services.live20_worker.Live20Service"
        ) as MockService:
            mock_service = MagicMock()
            mock_service._analyze_symbol = AsyncMock()
            MockService.return_value = mock_service

            await worker.process_job(run)

            # Should not process anything
            mock_service._analyze_symbol.assert_not_called()


@pytest.mark.unit
class TestLive20WorkerResumeCountAccuracy:
    """Tests for accurate count recovery after resume."""

    @pytest.mark.asyncio
    async def test_resume_recovers_counts_from_existing_recommendations(
        self, rollback_session_factory, mock_queue_service):
        """Should recover accurate counts from existing recommendations on resume.

        This tests the critical scenario where a server crashes mid-processing:
        1. Run processes some symbols and creates recommendations
        2. Server crashes BEFORE final counts are written to run table
        3. On resume, counts must be recalculated from existing recommendations

        Without the fix, counts only reflect the resumed session (losing pre-crash counts).
        """
        # Create run with 4 symbols - simulate 2 already processed before crash
        async with rollback_session_factory() as session:
            run = Live20Run(
                status="running",
                symbol_count=4,
                long_count=0,  # Simulates crash: counts were never persisted
                no_setup_count=0,
                input_symbols=["AAPL", "MSFT", "GOOGL", "NVDA"],
                retry_count=0,
                max_retries=3,
                processed_count=2,  # But processed_count was updated after each symbol
            )
            session.add(run)
            await session.flush()

            # Create existing recommendations (from before crash)
            # AAPL was LONG, MSFT was NO_SETUP
            rec_aapl = Recommendation(
                stock="AAPL",
                source=RecommendationSource.LIVE_20.value,
                recommendation="LONG",
                confidence_score=85,
                reasoning="Strong breakout",
                live20_run_id=run.id,
                live20_direction="LONG",
            )
            rec_msft = Recommendation(
                stock="MSFT",
                source=RecommendationSource.LIVE_20.value,
                recommendation="NO_SETUP",
                confidence_score=75,
                reasoning="No setup",
                live20_run_id=run.id,
                live20_direction="NO_SETUP",
            )
            session.add(rec_aapl)
            session.add(rec_msft)
            await session.commit()
            await session.refresh(run)

        worker = Live20Worker(rollback_session_factory, mock_queue_service)

        # Mock results for remaining symbols: GOOGL=LONG, NVDA=NO_SETUP
        def create_mock_result(symbol: str, direction: str):
            mock_result = MagicMock()
            mock_result.status = "success"
            mock_result.recommendation = MagicMock()
            mock_result.recommendation.id = 100 + hash(symbol) % 100
            mock_result.recommendation.live20_direction = direction
            return mock_result

        googl_result = create_mock_result("GOOGL", "LONG")
        nvda_result = create_mock_result("NVDA", "NO_SETUP")

        with patch(
            "app.services.live20_worker.Live20Service"
        ) as MockService:
            mock_service = MagicMock()
            mock_service._analyze_symbol = AsyncMock(
                side_effect=[googl_result, nvda_result]
            )
            MockService.return_value = mock_service

            await worker.process_job(run)

            # Should only process remaining symbols (GOOGL and NVDA)
            assert mock_service._analyze_symbol.call_count == 2

        # Verify final counts include BOTH pre-crash AND resumed results
        updated_run = await get_run_by_id(rollback_session_factory, run.id)
        # AAPL (pre-crash) + GOOGL (resumed) = 2 LONG
        assert updated_run.long_count == 2
        # MSFT (pre-crash) + NVDA (resumed) = 2 NO_SETUP
        assert updated_run.no_setup_count == 2


@pytest.mark.unit
class TestLive20WorkerDirectionCounting:
    """Tests for direction counting in process_job."""

    @pytest.mark.asyncio
    async def test_process_job_counts_long(
        self, rollback_session_factory, mock_queue_service):
        """Should count LONG results correctly."""
        run = await create_live20_run(
            rollback_session_factory,
            status="running",
            input_symbols=["AAPL"],
        )

        worker = Live20Worker(rollback_session_factory, mock_queue_service)

        mock_result = MagicMock()
        mock_result.status = "success"
        mock_result.recommendation = MagicMock()
        mock_result.recommendation.id = 1
        mock_result.recommendation.live20_direction = "LONG"

        with patch(
            "app.services.live20_worker.Live20Service"
        ) as MockService:
            mock_service = MagicMock()
            mock_service._analyze_symbol = AsyncMock(return_value=mock_result)
            MockService.return_value = mock_service

            await worker.process_job(run)

        # Verify counts were updated
        updated_run = await get_run_by_id(rollback_session_factory, run.id)
        assert updated_run.long_count == 1
        assert updated_run.no_setup_count == 0

    @pytest.mark.asyncio
    async def test_process_job_counts_no_setup(
        self, rollback_session_factory, mock_queue_service):
        """Should count NO_SETUP results correctly."""
        run = await create_live20_run(
            rollback_session_factory,
            status="running",
            input_symbols=["AAPL"],
        )

        worker = Live20Worker(rollback_session_factory, mock_queue_service)

        mock_result = MagicMock()
        mock_result.status = "success"
        mock_result.recommendation = MagicMock()
        mock_result.recommendation.id = 1
        mock_result.recommendation.live20_direction = "NO_SETUP"

        with patch(
            "app.services.live20_worker.Live20Service"
        ) as MockService:
            mock_service = MagicMock()
            mock_service._analyze_symbol = AsyncMock(return_value=mock_result)
            MockService.return_value = mock_service

            await worker.process_job(run)

        updated_run = await get_run_by_id(rollback_session_factory, run.id)
        assert updated_run.no_setup_count == 1


@pytest.mark.unit
class TestLive20WorkerProcessedCount:
    """Tests for processed_count updating."""

    @pytest.mark.asyncio
    async def test_process_job_updates_processed_count(
        self, rollback_session_factory, mock_queue_service):
        """Should update processed_count after each symbol."""
        run = await create_live20_run(
            rollback_session_factory,
            status="running",
            input_symbols=["AAPL", "MSFT"],
        )

        worker = Live20Worker(rollback_session_factory, mock_queue_service)

        mock_result = MagicMock()
        mock_result.status = "success"
        mock_result.recommendation = MagicMock()
        mock_result.recommendation.id = 1
        mock_result.recommendation.live20_direction = "LONG"

        with patch(
            "app.services.live20_worker.Live20Service"
        ) as MockService:
            mock_service = MagicMock()
            mock_service._analyze_symbol = AsyncMock(return_value=mock_result)
            MockService.return_value = mock_service

            await worker.process_job(run)

        updated_run = await get_run_by_id(rollback_session_factory, run.id)
        assert updated_run.processed_count == 2

    @pytest.mark.asyncio
    async def test_process_job_updates_count_on_error(
        self, rollback_session_factory, mock_queue_service):
        """Should still update processed_count when analysis fails."""
        run = await create_live20_run(
            rollback_session_factory,
            status="running",
            input_symbols=["AAPL"],
        )

        worker = Live20Worker(rollback_session_factory, mock_queue_service)

        # Create error result
        error_result = Live20Result(
            symbol="AAPL",
            status="error",
            error_message="Data unavailable",
        )

        with patch(
            "app.services.live20_worker.Live20Service"
        ) as MockService:
            mock_service = MagicMock()
            mock_service._analyze_symbol = AsyncMock(return_value=error_result)
            MockService.return_value = mock_service

            await worker.process_job(run)

        updated_run = await get_run_by_id(rollback_session_factory, run.id)
        # Should still increment processed_count even for errors
        assert updated_run.processed_count == 1


@pytest.mark.unit
class TestLive20WorkerFailedSymbolsTracking:
    """Tests for failed_symbols tracking."""

    @pytest.mark.asyncio
    async def test_process_job_tracks_failed_symbols(
        self, rollback_session_factory, mock_queue_service):
        """Should track failed symbols with their error messages."""
        run = await create_live20_run(
            rollback_session_factory,
            status="running",
            input_symbols=["AAPL", "MSFT"],
        )

        worker = Live20Worker(rollback_session_factory, mock_queue_service)

        # First symbol succeeds, second fails
        success_result = MagicMock()
        success_result.status = "success"
        success_result.recommendation = MagicMock()
        success_result.recommendation.id = 1
        success_result.recommendation.live20_direction = "LONG"

        error_result = Live20Result(
            symbol="MSFT",
            status="error",
            error_message="Data unavailable for MSFT",
        )

        with patch(
            "app.services.live20_worker.Live20Service"
        ) as MockService:
            mock_service = MagicMock()
            mock_service._analyze_symbol = AsyncMock(
                side_effect=[success_result, error_result]
            )
            MockService.return_value = mock_service

            await worker.process_job(run)

        updated_run = await get_run_by_id(rollback_session_factory, run.id)
        assert updated_run.failed_symbols is not None
        assert "MSFT" in updated_run.failed_symbols
        assert updated_run.failed_symbols["MSFT"] == "Data unavailable for MSFT"
        # AAPL should not be in failed_symbols
        assert "AAPL" not in updated_run.failed_symbols

    @pytest.mark.asyncio
    async def test_process_job_tracks_multiple_failures(
        self, rollback_session_factory, mock_queue_service):
        """Should track multiple failed symbols."""
        run = await create_live20_run(
            rollback_session_factory,
            status="running",
            input_symbols=["AAPL", "MSFT", "GOOGL"],
        )

        worker = Live20Worker(rollback_session_factory, mock_queue_service)

        # All three fail with different errors
        error_results = [
            Live20Result(symbol="AAPL", status="error", error_message="Rate limited"),
            Live20Result(symbol="MSFT", status="error", error_message="Data unavailable"),
            Live20Result(symbol="GOOGL", status="error", error_message="API timeout"),
        ]

        with patch(
            "app.services.live20_worker.Live20Service"
        ) as MockService:
            mock_service = MagicMock()
            mock_service._analyze_symbol = AsyncMock(side_effect=error_results)
            MockService.return_value = mock_service

            await worker.process_job(run)

        updated_run = await get_run_by_id(rollback_session_factory, run.id)
        assert updated_run.failed_symbols is not None
        assert len(updated_run.failed_symbols) == 3
        assert updated_run.failed_symbols["AAPL"] == "Rate limited"
        assert updated_run.failed_symbols["MSFT"] == "Data unavailable"
        assert updated_run.failed_symbols["GOOGL"] == "API timeout"

    @pytest.mark.asyncio
    async def test_process_job_handles_none_error_message(
        self, rollback_session_factory, mock_queue_service):
        """Should handle None error_message with default text."""
        run = await create_live20_run(
            rollback_session_factory,
            status="running",
            input_symbols=["AAPL"],
        )

        worker = Live20Worker(rollback_session_factory, mock_queue_service)

        # Error result with None message
        error_result = Live20Result(
            symbol="AAPL",
            status="error",
            error_message=None,
        )

        with patch(
            "app.services.live20_worker.Live20Service"
        ) as MockService:
            mock_service = MagicMock()
            mock_service._analyze_symbol = AsyncMock(return_value=error_result)
            MockService.return_value = mock_service

            await worker.process_job(run)

        updated_run = await get_run_by_id(rollback_session_factory, run.id)
        assert updated_run.failed_symbols is not None
        assert updated_run.failed_symbols["AAPL"] == "Unknown error"

    @pytest.mark.asyncio
    async def test_process_job_no_failures_no_failed_symbols(
        self, rollback_session_factory, mock_queue_service):
        """Should not set failed_symbols when all succeed."""
        run = await create_live20_run(
            rollback_session_factory,
            status="running",
            input_symbols=["AAPL"],
        )

        worker = Live20Worker(rollback_session_factory, mock_queue_service)

        success_result = MagicMock()
        success_result.status = "success"
        success_result.recommendation = MagicMock()
        success_result.recommendation.id = 1
        success_result.recommendation.live20_direction = "LONG"

        with patch(
            "app.services.live20_worker.Live20Service"
        ) as MockService:
            mock_service = MagicMock()
            mock_service._analyze_symbol = AsyncMock(return_value=success_result)
            MockService.return_value = mock_service

            await worker.process_job(run)

        updated_run = await get_run_by_id(rollback_session_factory, run.id)
        # Should be None (not empty dict) when no failures
        assert updated_run.failed_symbols is None

    @pytest.mark.asyncio
    async def test_process_job_persists_failed_symbols_after_each_batch(
        self, rollback_session_factory, mock_queue_service):
        """Should persist failed_symbols after each batch to prevent infinite retry on crash.

        Critical crash scenario:
        1. Batch 1 processes. Symbol "A" fails.
        2. processed_count updated to 10. failed_symbols MUST also be in DB.
        3. Worker crashes.
        4. Worker restarts. Symbol "A" must be in failed_symbols to avoid reprocessing.

        Without the fix, failed_symbols only saved at the end, so crash loses the data.

        This test simulates cancellation after first batch to verify that failed_symbols
        from that batch were persisted (simulating a crash scenario).
        """
        # Use 25 symbols to test multiple batches (10, 10, 5)
        symbols = [f"SYM{i}" for i in range(25)]
        run = await create_live20_run(
            rollback_session_factory,
            status="running",
            input_symbols=symbols,
        )

        # Cancel after first batch (simulating crash after batch 1)
        mock_queue_service.is_cancelled = AsyncMock(
            side_effect=[False, True]  # Process batch 1, then cancel
        )

        worker = Live20Worker(rollback_session_factory, mock_queue_service)

        call_count = [0]

        async def analyze_with_failure(symbol):
            """Fail SYM3 in the first batch."""
            call_count[0] += 1

            if symbol == "SYM3":
                return Live20Result(
                    symbol=symbol,
                    status="error",
                    error_message="SYM3 data unavailable",
                )

            # Success for other symbols
            mock_result = MagicMock()
            mock_result.status = "success"
            mock_result.recommendation = MagicMock()
            mock_result.recommendation.id = call_count[0]
            mock_result.recommendation.live20_direction = "LONG"
            return mock_result

        with patch(
            "app.services.live20_worker.Live20Service"
        ) as MockService:
            mock_service = MagicMock()
            mock_service._analyze_symbol = AsyncMock(side_effect=analyze_with_failure)
            MockService.return_value = mock_service

            await worker.process_job(run)

        # Verify that SYM3's failure was persisted even though we "crashed" after batch 1
        updated_run = await get_run_by_id(rollback_session_factory, run.id)
        assert updated_run.failed_symbols is not None
        assert "SYM3" in updated_run.failed_symbols
        assert updated_run.failed_symbols["SYM3"] == "SYM3 data unavailable"

        # Verify only first batch was processed (10 symbols)
        assert updated_run.processed_count == 10
        assert call_count[0] == 10

    @pytest.mark.asyncio
    async def test_failed_symbols_accumulates_across_batches(
        self, rollback_session_factory, mock_queue_service):
        """Should accumulate failed_symbols across multiple batches."""
        # Use symbols that span multiple batches
        symbols = [f"SYM{i}" for i in range(25)]
        run = await create_live20_run(
            rollback_session_factory,
            status="running",
            input_symbols=symbols,
        )

        worker = Live20Worker(rollback_session_factory, mock_queue_service)

        # Fail one symbol per batch
        def create_result(symbol):
            """Create error for SYM5, SYM15, success for others."""
            if symbol in ["SYM5", "SYM15"]:
                return Live20Result(
                    symbol=symbol,
                    status="error",
                    error_message=f"{symbol} failed",
                )
            mock_result = MagicMock()
            mock_result.status = "success"
            mock_result.recommendation = MagicMock()
            mock_result.recommendation.id = int(symbol[3:]) + 100
            mock_result.recommendation.live20_direction = "LONG"
            return mock_result

        with patch(
            "app.services.live20_worker.Live20Service"
        ) as MockService:
            mock_service = MagicMock()
            mock_service._analyze_symbol = AsyncMock(
                side_effect=lambda sym: create_result(sym)
            )
            MockService.return_value = mock_service

            await worker.process_job(run)

        # Check that both failures are recorded
        updated_run = await get_run_by_id(rollback_session_factory, run.id)
        assert updated_run.failed_symbols is not None
        assert len(updated_run.failed_symbols) == 2
        assert "SYM5" in updated_run.failed_symbols
        assert "SYM15" in updated_run.failed_symbols

    @pytest.mark.asyncio
    async def test_failed_symbols_preserved_on_resume(
        self, rollback_session_factory, mock_queue_service):
        """Should preserve existing failed_symbols when resuming a run."""
        # Create a run with existing failed_symbols (simulating a previous crash)
        async with rollback_session_factory() as session:
            run = Live20Run(
                status="running",
                symbol_count=3,
                long_count=0,
                no_setup_count=0,
                input_symbols=["AAPL", "MSFT", "GOOGL"],
                retry_count=0,
                max_retries=3,
                processed_count=1,
                failed_symbols={"AAPL": "Previous crash error"},
            )
            session.add(run)
            await session.commit()
            await session.refresh(run)

        worker = Live20Worker(rollback_session_factory, mock_queue_service)

        # MSFT fails, GOOGL succeeds
        def create_result(symbol):
            if symbol == "MSFT":
                return Live20Result(
                    symbol=symbol,
                    status="error",
                    error_message="MSFT failed now",
                )
            mock_result = MagicMock()
            mock_result.status = "success"
            mock_result.recommendation = MagicMock()
            mock_result.recommendation.id = 1
            mock_result.recommendation.live20_direction = "LONG"
            return mock_result

        with patch(
            "app.services.live20_worker.Live20Service"
        ) as MockService:
            mock_service = MagicMock()
            mock_service._analyze_symbol = AsyncMock(
                side_effect=lambda sym: create_result(sym)
            )
            MockService.return_value = mock_service

            await worker.process_job(run)

        # Should have BOTH old and new failures
        updated_run = await get_run_by_id(rollback_session_factory, run.id)
        assert updated_run.failed_symbols is not None
        assert len(updated_run.failed_symbols) == 2
        assert updated_run.failed_symbols["AAPL"] == "Previous crash error"
        assert updated_run.failed_symbols["MSFT"] == "MSFT failed now"


@pytest.mark.unit
class TestLive20WorkerConcurrency:
    """Test concurrent batch processing in Live20Worker."""

    @pytest.mark.asyncio
    async def test_processes_symbols_in_batches(
        self, rollback_session_factory, mock_queue_service):
        """Test that symbols are processed in batches of BATCH_SIZE."""
        # Create a run with 25 symbols (should be 3 batches: 10, 10, 5)
        symbols = [f"SYM{i}" for i in range(25)]
        run = await create_live20_run(
            rollback_session_factory,
            status="running",
            input_symbols=symbols,
        )

        worker = Live20Worker(rollback_session_factory, mock_queue_service)

        mock_result = MagicMock()
        mock_result.status = "success"
        mock_result.recommendation = MagicMock()
        mock_result.recommendation.id = 1
        mock_result.recommendation.live20_direction = "LONG"

        with patch(
            "app.services.live20_worker.Live20Service"
        ) as MockService:
            mock_service = MagicMock()
            mock_service._analyze_symbol = AsyncMock(return_value=mock_result)
            MockService.return_value = mock_service

            await worker.process_job(run)

            # Verify all 25 symbols were analyzed
            assert mock_service._analyze_symbol.call_count == 25

    @pytest.mark.asyncio
    async def test_cancellation_checked_between_batches(
        self, rollback_session_factory, mock_queue_service):
        """Test that cancellation is checked between batches (not between symbols)."""
        # Create a run with 25 symbols (3 batches: 10, 10, 5)
        symbols = [f"SYM{i}" for i in range(25)]
        run = await create_live20_run(
            rollback_session_factory,
            status="running",
            input_symbols=symbols,
        )

        # Make is_cancelled return False on first call (before batch 1),
        # True on second call (before batch 2)
        mock_queue_service.is_cancelled = AsyncMock(
            side_effect=[False, True]
        )

        worker = Live20Worker(rollback_session_factory, mock_queue_service)

        mock_result = MagicMock()
        mock_result.status = "success"
        mock_result.recommendation = MagicMock()
        mock_result.recommendation.id = 1
        mock_result.recommendation.live20_direction = "LONG"

        with patch(
            "app.services.live20_worker.Live20Service"
        ) as MockService:
            mock_service = MagicMock()
            mock_service._analyze_symbol = AsyncMock(return_value=mock_result)
            MockService.return_value = mock_service

            await worker.process_job(run)

            # Should process only first batch (10 symbols) before cancellation
            # The cancellation happens BEFORE each batch, so after first batch
            # completes (10 symbols), the second cancellation check stops it
            assert mock_service._analyze_symbol.call_count == 10

    @pytest.mark.asyncio
    async def test_individual_failures_dont_fail_batch(
        self, rollback_session_factory, mock_queue_service):
        """Test that one symbol failure doesn't fail the entire batch."""
        run = await create_live20_run(
            rollback_session_factory,
            status="running",
            input_symbols=["GOOD1", "BAD", "GOOD2"],
        )

        worker = Live20Worker(rollback_session_factory, mock_queue_service)

        # Create a function that raises exception for "BAD" symbol
        async def analyze_conditional(symbol):
            if symbol == "BAD":
                raise Exception("API error")
            # Return success for other symbols
            mock_result = MagicMock()
            mock_result.status = "success"
            mock_result.recommendation = MagicMock()
            mock_result.recommendation.id = 1
            mock_result.recommendation.live20_direction = "LONG"
            return mock_result

        with patch(
            "app.services.live20_worker.Live20Service"
        ) as MockService:
            mock_service = MagicMock()
            mock_service._analyze_symbol = AsyncMock(side_effect=analyze_conditional)
            MockService.return_value = mock_service

            await worker.process_job(run)

            # All 3 should be attempted (gather with return_exceptions=True allows this)
            assert mock_service._analyze_symbol.call_count == 3

        # Verify "BAD" is in failed_symbols
        updated_run = await get_run_by_id(rollback_session_factory, run.id)
        assert updated_run.failed_symbols is not None
        assert "BAD" in updated_run.failed_symbols
        assert "API error" in updated_run.failed_symbols["BAD"]


@pytest.mark.unit
class TestLive20WorkerLogging:
    """Tests for Live20Worker logging."""

    @pytest.mark.asyncio
    async def test_logs_resume_count(
        self, rollback_session_factory, mock_queue_service, caplog
    ):
        """Should log how many symbols are already processed."""
        import logging

        caplog.set_level(logging.INFO)

        run = await create_live20_run(
            rollback_session_factory,
            status="running",
            input_symbols=["AAPL", "MSFT", "GOOGL"],
            existing_recommendations=["AAPL"],
        )

        worker = Live20Worker(rollback_session_factory, mock_queue_service)

        mock_result = MagicMock()
        mock_result.status = "success"
        mock_result.recommendation = MagicMock()
        mock_result.recommendation.id = 1
        mock_result.recommendation.live20_direction = "LONG"

        with patch(
            "app.services.live20_worker.Live20Service"
        ) as MockService:
            mock_service = MagicMock()
            mock_service._analyze_symbol = AsyncMock(return_value=mock_result)
            MockService.return_value = mock_service

            await worker.process_job(run)

        log_messages = [record.message for record in caplog.records]
        # Should log "1 processed, 2 remaining"
        assert any("1 processed" in msg for msg in log_messages)
        assert any("2 remaining" in msg for msg in log_messages)

    @pytest.mark.asyncio
    async def test_logs_cancellation(
        self, rollback_session_factory, mock_queue_service, caplog
    ):
        """Should log when run is cancelled."""
        import logging

        caplog.set_level(logging.INFO)

        run = await create_live20_run(
            rollback_session_factory,
            status="running",
        )

        mock_queue_service.is_cancelled = AsyncMock(return_value=True)

        worker = Live20Worker(rollback_session_factory, mock_queue_service)

        await worker.process_job(run)

        log_messages = [record.message for record in caplog.records]
        assert any("cancelled" in msg.lower() for msg in log_messages)

    @pytest.mark.asyncio
    async def test_logs_completion_summary(
        self, rollback_session_factory, mock_queue_service, caplog
    ):
        """Should log completion summary with counts."""
        import logging

        caplog.set_level(logging.INFO)

        run = await create_live20_run(
            rollback_session_factory,
            status="running",
            input_symbols=["AAPL"],
        )

        worker = Live20Worker(rollback_session_factory, mock_queue_service)

        mock_result = MagicMock()
        mock_result.status = "success"
        mock_result.recommendation = MagicMock()
        mock_result.recommendation.id = 1
        mock_result.recommendation.live20_direction = "LONG"

        with patch(
            "app.services.live20_worker.Live20Service"
        ) as MockService:
            mock_service = MagicMock()
            mock_service._analyze_symbol = AsyncMock(return_value=mock_result)
            MockService.return_value = mock_service

            await worker.process_job(run)

        log_messages = [record.message for record in caplog.records]
        # Should log completion with LONG count
        assert any("completed" in msg.lower() and "LONG" in msg for msg in log_messages)
