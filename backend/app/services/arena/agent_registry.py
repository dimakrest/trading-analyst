"""Registry for arena agents.

This module provides a central registry for all available trading agents
in the arena simulation system, allowing dynamic agent instantiation by type.
"""

from app.services.arena.agent_protocol import BaseAgent
from app.services.arena.agents.live20_agent import Live20ArenaAgent

# Agent type to class mapping
AGENT_REGISTRY: dict[str, type[BaseAgent]] = {
    "live20": Live20ArenaAgent,
}


def get_agent(agent_type: str, config: dict | None = None) -> BaseAgent:
    """Get an agent instance by type.

    Args:
        agent_type: Agent type identifier (e.g., "live20").
        config: Optional agent configuration passed to agent constructor.

    Returns:
        Agent instance.

    Raises:
        ValueError: If agent type is not registered.
    """
    agent_class = AGENT_REGISTRY.get(agent_type.lower())
    if not agent_class:
        available = ", ".join(AGENT_REGISTRY.keys())
        msg = f"Unknown agent type: {agent_type}. Available: {available}"
        raise ValueError(msg)

    return agent_class(config=config)


def list_agents() -> list[dict[str, str | int]]:
    """List all available agents.

    Returns:
        List of agent info dicts with type, name, and required_lookback_days.
    """
    result: list[dict[str, str | int]] = []
    for agent_type, agent_class in AGENT_REGISTRY.items():
        agent = agent_class(config=None)
        result.append(
            {
                "type": agent_type,
                "name": agent.name,
                "required_lookback_days": agent.required_lookback_days,
            }
        )
    return result
