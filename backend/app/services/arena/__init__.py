"""Arena simulation services.

This package contains services for running trading agent arena simulations.
"""

from app.services.arena.agent_protocol import AgentDecision, BaseAgent, PriceBar
from app.services.arena.agent_registry import get_agent, list_agents
from app.services.arena.arena_worker import ArenaWorker
from app.services.arena.simulation_engine import SimulationEngine
from app.services.arena.trailing_stop import FixedPercentTrailingStop, TrailingStopUpdate

__all__ = [
    "AgentDecision",
    "ArenaWorker",
    "BaseAgent",
    "FixedPercentTrailingStop",
    "PriceBar",
    "SimulationEngine",
    "TrailingStopUpdate",
    "get_agent",
    "list_agents",
]
