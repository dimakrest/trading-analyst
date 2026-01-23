"""Unit tests for the Agent Protocol module.

Tests AgentDecision, PriceBar dataclasses and BaseAgent abstract class.
"""
from datetime import date
from decimal import Decimal

import pytest

from app.services.arena.agent_protocol import AgentDecision
from app.services.arena.agent_protocol import BaseAgent
from app.services.arena.agent_protocol import PriceBar


class TestAgentDecision:
    """Tests for AgentDecision dataclass."""

    @pytest.mark.unit
    def test_create_valid_buy_decision(self):
        """Test creating a valid BUY decision."""
        decision = AgentDecision(
            symbol="AAPL",
            action="BUY",
            score=85,
            reasoning="Strong mean reversion signal",
        )

        assert decision.symbol == "AAPL"
        assert decision.action == "BUY"
        assert decision.score == 85
        assert decision.reasoning == "Strong mean reversion signal"

    @pytest.mark.unit
    def test_create_valid_hold_decision(self):
        """Test creating a valid HOLD decision."""
        decision = AgentDecision(
            symbol="GOOGL",
            action="HOLD",
            score=60,
            reasoning="Already holding position",
        )

        assert decision.action == "HOLD"

    @pytest.mark.unit
    def test_create_valid_no_signal_decision(self):
        """Test creating a valid NO_SIGNAL decision."""
        decision = AgentDecision(
            symbol="MSFT",
            action="NO_SIGNAL",
            score=30,
            reasoning="Criteria not met",
        )

        assert decision.action == "NO_SIGNAL"

    @pytest.mark.unit
    def test_decision_optional_fields(self):
        """Test decision with only required fields."""
        decision = AgentDecision(
            symbol="TSLA",
            action="BUY",
        )

        assert decision.symbol == "TSLA"
        assert decision.action == "BUY"
        assert decision.score is None
        assert decision.reasoning is None

    @pytest.mark.unit
    def test_decision_invalid_action(self):
        """Test that invalid action raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            AgentDecision(
                symbol="AAPL",
                action="SELL",  # Invalid action
            )

        assert "Invalid action" in str(exc_info.value)
        assert "SELL" in str(exc_info.value)

    @pytest.mark.unit
    def test_decision_invalid_action_lowercase(self):
        """Test that lowercase action raises ValueError."""
        with pytest.raises(ValueError):
            AgentDecision(
                symbol="AAPL",
                action="buy",  # Should be uppercase
            )

    @pytest.mark.unit
    def test_decision_empty_action(self):
        """Test that empty action raises ValueError."""
        with pytest.raises(ValueError):
            AgentDecision(
                symbol="AAPL",
                action="",
            )


class TestPriceBar:
    """Tests for PriceBar dataclass."""

    @pytest.mark.unit
    def test_create_valid_price_bar(self):
        """Test creating a valid price bar."""
        bar = PriceBar(
            date=date(2024, 1, 15),
            open=Decimal("150.00"),
            high=Decimal("155.00"),
            low=Decimal("148.00"),
            close=Decimal("154.00"),
            volume=1000000,
        )

        assert bar.date == date(2024, 1, 15)
        assert bar.open == Decimal("150.00")
        assert bar.high == Decimal("155.00")
        assert bar.low == Decimal("148.00")
        assert bar.close == Decimal("154.00")
        assert bar.volume == 1000000

    @pytest.mark.unit
    def test_price_bar_all_same_price(self):
        """Test price bar where all prices are equal (doji-like)."""
        bar = PriceBar(
            date=date(2024, 1, 15),
            open=Decimal("150.00"),
            high=Decimal("150.00"),
            low=Decimal("150.00"),
            close=Decimal("150.00"),
            volume=500000,
        )

        assert bar.high == bar.low == bar.open == bar.close

    @pytest.mark.unit
    def test_price_bar_zero_volume(self):
        """Test price bar with zero volume."""
        bar = PriceBar(
            date=date(2024, 1, 15),
            open=Decimal("150.00"),
            high=Decimal("155.00"),
            low=Decimal("148.00"),
            close=Decimal("154.00"),
            volume=0,
        )

        assert bar.volume == 0

    @pytest.mark.unit
    def test_price_bar_high_less_than_low(self):
        """Test that high < low raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            PriceBar(
                date=date(2024, 1, 15),
                open=Decimal("150.00"),
                high=Decimal("145.00"),  # Invalid: less than low
                low=Decimal("148.00"),
                close=Decimal("154.00"),
                volume=1000000,
            )

        assert "High price" in str(exc_info.value)
        assert "low price" in str(exc_info.value)

    @pytest.mark.unit
    def test_price_bar_high_less_than_open(self):
        """Test that high < open raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            PriceBar(
                date=date(2024, 1, 15),
                open=Decimal("155.00"),
                high=Decimal("154.00"),  # Invalid: less than open
                low=Decimal("148.00"),
                close=Decimal("152.00"),
                volume=1000000,
            )

        assert "High price" in str(exc_info.value)
        assert "open and close" in str(exc_info.value)

    @pytest.mark.unit
    def test_price_bar_high_less_than_close(self):
        """Test that high < close raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            PriceBar(
                date=date(2024, 1, 15),
                open=Decimal("150.00"),
                high=Decimal("154.00"),  # Invalid: less than close
                low=Decimal("148.00"),
                close=Decimal("156.00"),
                volume=1000000,
            )

        assert "High price" in str(exc_info.value)

    @pytest.mark.unit
    def test_price_bar_low_greater_than_open(self):
        """Test that low > open raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            PriceBar(
                date=date(2024, 1, 15),
                open=Decimal("145.00"),
                high=Decimal("155.00"),
                low=Decimal("148.00"),  # Invalid: greater than open
                close=Decimal("152.00"),
                volume=1000000,
            )

        assert "Low price" in str(exc_info.value)

    @pytest.mark.unit
    def test_price_bar_low_greater_than_close(self):
        """Test that low > close raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            PriceBar(
                date=date(2024, 1, 15),
                open=Decimal("150.00"),
                high=Decimal("155.00"),
                low=Decimal("148.00"),  # Invalid: greater than close
                close=Decimal("145.00"),
                volume=1000000,
            )

        assert "Low price" in str(exc_info.value)

    @pytest.mark.unit
    def test_price_bar_negative_volume(self):
        """Test that negative volume raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            PriceBar(
                date=date(2024, 1, 15),
                open=Decimal("150.00"),
                high=Decimal("155.00"),
                low=Decimal("148.00"),
                close=Decimal("154.00"),
                volume=-1000,
            )

        assert "Volume" in str(exc_info.value)
        assert "negative" in str(exc_info.value)


class TestBaseAgent:
    """Tests for BaseAgent abstract class."""

    @pytest.mark.unit
    def test_base_agent_is_abstract(self):
        """Test that BaseAgent cannot be instantiated directly."""
        with pytest.raises(TypeError) as exc_info:
            BaseAgent()

        assert "abstract" in str(exc_info.value).lower()

    @pytest.mark.unit
    def test_base_agent_subclass_implementation(self):
        """Test that a proper subclass can be instantiated."""

        class MockAgent(BaseAgent):
            """Mock agent for testing."""

            @property
            def name(self) -> str:
                return "MockAgent"

            @property
            def required_lookback_days(self) -> int:
                return 30

            async def evaluate(
                self,
                symbol: str,
                price_history: list[PriceBar],
                current_date: date,
                has_open_position: bool,
            ) -> AgentDecision:
                return AgentDecision(
                    symbol=symbol,
                    action="NO_SIGNAL",
                    score=50,
                    reasoning="Mock evaluation",
                )

        agent = MockAgent()
        assert agent.name == "MockAgent"
        assert agent.required_lookback_days == 30

    @pytest.mark.unit
    async def test_base_agent_evaluate_method(self):
        """Test that evaluate method works correctly."""

        class TestAgent(BaseAgent):
            """Test agent for evaluation testing."""

            @property
            def name(self) -> str:
                return "TestAgent"

            @property
            def required_lookback_days(self) -> int:
                return 10

            async def evaluate(
                self,
                symbol: str,
                price_history: list[PriceBar],
                current_date: date,
                has_open_position: bool,
            ) -> AgentDecision:
                if has_open_position:
                    return AgentDecision(symbol=symbol, action="HOLD")
                if len(price_history) >= self.required_lookback_days:
                    return AgentDecision(symbol=symbol, action="BUY", score=80)
                return AgentDecision(symbol=symbol, action="NO_SIGNAL")

        agent = TestAgent()

        # Create sample price history
        price_history = [
            PriceBar(
                date=date(2024, 1, i),
                open=Decimal("100"),
                high=Decimal("105"),
                low=Decimal("98"),
                close=Decimal("102"),
                volume=1000000,
            )
            for i in range(1, 15)
        ]

        # Test with open position
        decision = await agent.evaluate("AAPL", price_history, date(2024, 1, 15), True)
        assert decision.action == "HOLD"

        # Test with sufficient history
        decision = await agent.evaluate("AAPL", price_history, date(2024, 1, 15), False)
        assert decision.action == "BUY"
        assert decision.score == 80

        # Test with insufficient history
        short_history = price_history[:5]
        decision = await agent.evaluate("AAPL", short_history, date(2024, 1, 6), False)
        assert decision.action == "NO_SIGNAL"

    @pytest.mark.unit
    def test_base_agent_incomplete_implementation(self):
        """Test that incomplete subclass cannot be instantiated."""

        class IncompleteAgent(BaseAgent):
            """Agent missing required methods."""

            @property
            def name(self) -> str:
                return "IncompleteAgent"

            # Missing required_lookback_days and evaluate

        with pytest.raises(TypeError):
            IncompleteAgent()

    @pytest.mark.unit
    def test_base_agent_missing_name(self):
        """Test that subclass missing name cannot be instantiated."""

        class MissingNameAgent(BaseAgent):
            """Agent missing name property."""

            @property
            def required_lookback_days(self) -> int:
                return 30

            async def evaluate(
                self,
                symbol: str,
                price_history: list[PriceBar],
                current_date: date,
                has_open_position: bool,
            ) -> AgentDecision:
                return AgentDecision(symbol=symbol, action="NO_SIGNAL")

        with pytest.raises(TypeError):
            MissingNameAgent()
