"""Worker for processing Live20 runs from the queue.

This worker picks up pending Live20Run entries from the database
and processes them with resume capability and cancellation support.
"""
import asyncio
import logging

from sqlalchemy import update

from app.core.config import get_settings
from app.models.live20_run import Live20Run
from app.models.recommendation import Recommendation
from app.services.job_worker import JobWorker
from app.services.live20_service import Live20Direction, Live20Service

logger = logging.getLogger(__name__)


class Live20Worker(JobWorker[Live20Run]):
    """Worker that processes Live20 runs from the queue.

    Implements resume capability by checking existing recommendations before
    processing, and supports graceful cancellation between individual symbols.
    """

    async def process_job(self, run: Live20Run) -> None:
        """Process a Live20 run with resume capability.

        Resumes from partial completion by checking run.recommendations
        for already-processed symbols. Live20 always creates a recommendation
        for every symbol analyzed (including NO_SETUP results), so resume
        correctly tracks all processed symbols.

        Args:
            run: The Live20Run to process
        """
        worker_id = self.queue_service.worker_id

        # Get already-processed symbols from recommendations
        # Note: Live20 creates recommendations for ALL symbols (including NO_SETUP)
        processed_symbols: set[str] = set()
        for rec in run.recommendations:
            processed_symbols.add(rec.stock)

        # Get remaining symbols to process
        remaining = [s for s in run.input_symbols if s not in processed_symbols]

        logger.info(
            f"[{worker_id}] Run {run.id}: {len(processed_symbols)} processed, "
            f"{len(remaining)} remaining"
        )

        if not remaining:
            logger.info(f"[{worker_id}] Run {run.id}: All symbols already processed")
            return

        # Create Live20Service for analysis (algorithm is run-level, not per-symbol)
        service = Live20Service(
            self.session_factory,
            scoring_algorithm=run.scoring_algorithm or "cci",
        )

        # Track counts for updating run at the end
        # Recalculate from existing recommendations to ensure accuracy on resume
        # (counts in run.* may be stale if server crashed before final update)
        if processed_symbols:
            long_count = sum(
                1
                for rec in run.recommendations
                if rec.live20_direction == Live20Direction.LONG
            )
            short_count = sum(
                1
                for rec in run.recommendations
                if rec.live20_direction == Live20Direction.SHORT
            )
            no_setup_count = sum(
                1
                for rec in run.recommendations
                if rec.live20_direction == Live20Direction.NO_SETUP
            )
        else:
            long_count = 0
            short_count = 0
            no_setup_count = 0
        failed_symbols: dict[str, str] = dict(run.failed_symbols or {})

        # Process remaining symbols in concurrent batches
        batch_size = get_settings().live20_batch_size
        for batch_start in range(0, len(remaining), batch_size):
            # CHECK CANCELLATION before each batch
            if await self.queue_service.is_cancelled(run.id):
                logger.info(
                    f"[{worker_id}] Run {run.id} cancelled, stopping processing"
                )
                return

            batch = remaining[batch_start:batch_start + batch_size]
            logger.info(
                f"[{worker_id}] Processing batch {batch_start // batch_size + 1} "
                f"({len(batch)} symbols) for run {run.id}"
            )

            # Create tasks for batch
            tasks = [
                service._analyze_symbol(symbol)
                for symbol in batch
            ]

            # Process batch concurrently
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Collect recommendation IDs to update in a single transaction
            recommendation_ids_to_link: list[int] = []

            # Process results from batch
            for symbol, result in zip(batch, results):
                if isinstance(result, Exception):
                    logger.warning(
                        f"[{worker_id}] {symbol} analysis failed with exception: {result}"
                    )
                    failed_symbols[symbol] = str(result)
                elif result.status == "success" and result.recommendation:
                    # Collect recommendation ID for batch update
                    recommendation_ids_to_link.append(result.recommendation.id)

                    # Update counts based on direction
                    direction = result.recommendation.live20_direction
                    if direction == Live20Direction.LONG:
                        long_count += 1
                    elif direction == Live20Direction.SHORT:
                        short_count += 1
                    else:
                        no_setup_count += 1

                    logger.debug(
                        f"[{worker_id}] {symbol}: {direction} "
                        f"({result.recommendation.confidence_score}%)"
                    )
                else:
                    logger.warning(
                        f"[{worker_id}] {symbol} analysis failed: {result.error_message}"
                    )
                    failed_symbols[symbol] = result.error_message or "Unknown error"

            # Batch update: link recommendations and update progress in single transaction
            async with self.session_factory() as session:
                # Link all successful recommendations to this run
                if recommendation_ids_to_link:
                    await session.execute(
                        update(Recommendation)
                        .where(Recommendation.id.in_(recommendation_ids_to_link))
                        .values(live20_run_id=run.id)
                    )

                # Update processed_count and failed_symbols
                await session.execute(
                    update(Live20Run)
                    .where(Live20Run.id == run.id)
                    .values(
                        processed_count=Live20Run.processed_count + len(batch),
                        failed_symbols=failed_symbols if failed_symbols else None,
                    )
                )
                await session.commit()

        # Update final counts on the run (including failed_symbols)
        async with self.session_factory() as session:
            await session.execute(
                update(Live20Run)
                .where(Live20Run.id == run.id)
                .values(
                    long_count=long_count,
                    short_count=short_count,
                    no_setup_count=no_setup_count,
                    failed_symbols=failed_symbols if failed_symbols else None,
                )
            )
            await session.commit()

        failed_count = len(failed_symbols)
        logger.info(
            f"[{worker_id}] Run {run.id} completed: "
            f"LONG={long_count}, SHORT={short_count}, NO_SETUP={no_setup_count}, "
            f"FAILED={failed_count}"
        )
