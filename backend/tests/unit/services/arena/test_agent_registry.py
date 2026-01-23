"""Unit tests for the Agent Registry module.

Tests AGENT_REGISTRY, get_agent(), and list_agents() functions.
"""

import pytest

from app.services.arena.agent_protocol import BaseAgent
from app.services.arena.agent_registry import AGENT_REGISTRY, get_agent, list_agents
from app.services.arena.agents.live20_agent import Live20ArenaAgent


class TestAgentRegistry:
    """Tests for AGENT_REGISTRY constant."""

    @pytest.mark.unit
    def test_registry_contains_live20(self) -> None:
        """Test that registry contains live20 agent."""
        assert "live20" in AGENT_REGISTRY

    @pytest.mark.unit
    def test_registry_live20_is_correct_class(self) -> None:
        """Test that live20 maps to Live20ArenaAgent."""
        assert AGENT_REGISTRY["live20"] is Live20ArenaAgent

    @pytest.mark.unit
    def test_registry_not_empty(self) -> None:
        """Test that registry is not empty."""
        assert len(AGENT_REGISTRY) > 0

    @pytest.mark.unit
    def test_registry_values_are_base_agent_subclasses(self) -> None:
        """Test that all registry values are BaseAgent subclasses."""
        for agent_type, agent_class in AGENT_REGISTRY.items():
            assert issubclass(
                agent_class, BaseAgent
            ), f"{agent_type} should be a BaseAgent subclass"


class TestGetAgent:
    """Tests for get_agent() function."""

    @pytest.mark.unit
    def test_get_agent_live20(self) -> None:
        """Test getting live20 agent by type."""
        agent = get_agent("live20")

        assert isinstance(agent, Live20ArenaAgent)
        assert agent.name == "Live20"

    @pytest.mark.unit
    def test_get_agent_case_insensitive(self) -> None:
        """Test that get_agent is case insensitive."""
        agent1 = get_agent("live20")
        agent2 = get_agent("LIVE20")
        agent3 = get_agent("Live20")

        assert isinstance(agent1, Live20ArenaAgent)
        assert isinstance(agent2, Live20ArenaAgent)
        assert isinstance(agent3, Live20ArenaAgent)

    @pytest.mark.unit
    def test_get_agent_unknown_type_raises(self) -> None:
        """Test that unknown agent type raises ValueError."""
        with pytest.raises(ValueError, match="Unknown agent type"):
            get_agent("unknown_agent")

    @pytest.mark.unit
    def test_get_agent_empty_type_raises(self) -> None:
        """Test that empty agent type raises ValueError."""
        with pytest.raises(ValueError, match="Unknown agent type"):
            get_agent("")

    @pytest.mark.unit
    def test_get_agent_with_none_config(self) -> None:
        """Test get_agent with None config uses default configuration."""
        agent = get_agent("live20", config=None)

        assert isinstance(agent, Live20ArenaAgent)
        assert agent.min_buy_score == 60

    @pytest.mark.unit
    def test_get_agent_with_empty_config(self) -> None:
        """Test get_agent with empty config dict uses defaults."""
        agent = get_agent("live20", config={})

        assert isinstance(agent, Live20ArenaAgent)
        assert agent.min_buy_score == 60

    @pytest.mark.unit
    def test_get_agent_with_custom_config(self) -> None:
        """Test get_agent passes custom config to agent constructor."""
        config = {"min_buy_score": 80}
        agent = get_agent("live20", config=config)

        assert isinstance(agent, Live20ArenaAgent)
        assert agent.min_buy_score == 80

    @pytest.mark.unit
    def test_get_agent_returns_new_instance(self) -> None:
        """Test that get_agent returns a new instance each time."""
        agent1 = get_agent("live20")
        agent2 = get_agent("live20")

        assert agent1 is not agent2  # Different instances


class TestListAgents:
    """Tests for list_agents() function."""

    @pytest.mark.unit
    def test_list_agents_not_empty(self) -> None:
        """Test that list_agents returns non-empty list."""
        agents = list_agents()

        assert len(agents) > 0

    @pytest.mark.unit
    def test_list_agents_contains_live20(self) -> None:
        """Test that list_agents includes live20."""
        agents = list_agents()

        agent_types = [a["type"] for a in agents]
        assert "live20" in agent_types

    @pytest.mark.unit
    def test_list_agents_structure(self) -> None:
        """Test that list_agents returns correct structure."""
        agents = list_agents()

        for agent in agents:
            assert "type" in agent
            assert "name" in agent
            assert "required_lookback_days" in agent

    @pytest.mark.unit
    def test_list_agents_live20_info(self) -> None:
        """Test that live20 info is correct in list_agents."""
        agents = list_agents()

        live20_info = next(a for a in agents if a["type"] == "live20")

        assert live20_info["name"] == "Live20"
        assert live20_info["required_lookback_days"] == 60

    @pytest.mark.unit
    def test_list_agents_matches_registry(self) -> None:
        """Test that list_agents covers all agents in registry."""
        agents = list_agents()
        agent_types = [a["type"] for a in agents]

        for registry_type in AGENT_REGISTRY.keys():
            assert registry_type in agent_types

    @pytest.mark.unit
    def test_list_agents_returns_correct_count(self) -> None:
        """Test that list_agents returns same count as registry."""
        agents = list_agents()

        assert len(agents) == len(AGENT_REGISTRY)

    @pytest.mark.unit
    def test_list_agents_type_values_are_strings(self) -> None:
        """Test that type values are strings."""
        agents = list_agents()

        for agent in agents:
            assert isinstance(agent["type"], str)

    @pytest.mark.unit
    def test_list_agents_name_values_are_strings(self) -> None:
        """Test that name values are strings."""
        agents = list_agents()

        for agent in agents:
            assert isinstance(agent["name"], str)

    @pytest.mark.unit
    def test_list_agents_lookback_values_are_integers(self) -> None:
        """Test that required_lookback_days values are integers."""
        agents = list_agents()

        for agent in agents:
            assert isinstance(agent["required_lookback_days"], int)
            assert agent["required_lookback_days"] > 0
