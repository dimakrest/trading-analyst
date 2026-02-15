"""Worker for processing arena simulation jobs from the queue.

This worker picks up pending ArenaSimulation entries from the database
and processes them with resume capability and cancellation support.
"""

import logging
import time

from app.models.arena import ArenaSimulation
from app.services.arena.simulation_engine import SimulationEngine
from app.services.job_worker import JobWorker

logger = logging.getLogger(__name__)


class ArenaWorker(JobWorker[ArenaSimulation]):
    """Worker that processes arena simulation jobs from the queue.

    Implements resume capability by tracking current_day progress,
    and supports graceful cancellation between simulation days.
    """

    async def process_job(self, simulation: ArenaSimulation) -> None:
        """Process an arena simulation job with resume capability.

        Resumes from partial completion by checking simulation.current_day.
        Checks for cancellation before each day's processing.

        Args:
            simulation: The ArenaSimulation to process
        """
        worker_id = self.queue_service.worker_id
        simulation_id = simulation.id

        logger.info(
            f"[{worker_id}] Simulation {simulation_id}: starting processing "
            f"(day {simulation.current_day}/{simulation.total_days}, "
            f"status={simulation.status})"
        )

        # Create simulation engine with a new session
        # We need a fresh session because the simulation object came from
        # a different session (the queue service session)
        async with self.session_factory() as session:
            engine = SimulationEngine(session, self.session_factory)

            # Load simulation in this session
            sim = await session.get(ArenaSimulation, simulation_id)
            if not sim:
                logger.error(f"[{worker_id}] Simulation {simulation_id} not found")
                return

            # Initialize simulation if not yet started
            if not sim.is_initialized:
                logger.info(f"[{worker_id}] Simulation {simulation_id}: initializing")
                await engine.initialize_simulation(simulation_id)

                # Refresh to get updated state (only refresh scalar attributes needed by the worker)
                await session.refresh(sim, attribute_names=["current_day", "total_days", "status"])
                logger.info(
                    f"[{worker_id}] Simulation {simulation_id}: initialized "
                    f"with {sim.total_days} trading days"
                )

            # Process days until completion
            while sim.current_day < sim.total_days:
                # Check for cancellation before each day
                if await self.queue_service.is_cancelled(simulation_id):
                    logger.info(
                        f"[{worker_id}] Simulation {simulation_id} cancelled, "
                        f"stopping at day {sim.current_day}"
                    )
                    return

                # Process one day
                start_time = time.monotonic()
                snapshot = await engine.step_day(simulation_id)
                elapsed = time.monotonic() - start_time

                if snapshot is None:
                    # Simulation completed (step_day returns None when done)
                    break

                # Refresh simulation to get updated current_day
                await session.refresh(sim, attribute_names=["current_day", "total_days", "status"])

                logger.info(
                    f"[{worker_id}] Simulation {simulation_id}: "
                    f"day {sim.current_day}/{sim.total_days} complete, "
                    f"equity=${snapshot.total_equity}, took {elapsed:.2f}s"
                )

            # Log completion summary (refresh state after session work)
            await session.refresh(
                sim,
                attribute_names=[
                    "current_day",
                    "total_days",
                    "status",
                    "total_trades",
                    "total_return_pct",
                ],
            )
            logger.info(
                f"[{worker_id}] Simulation {simulation_id} completed: "
                f"{sim.total_trades} trades, "
                f"return {sim.total_return_pct}%"
            )
