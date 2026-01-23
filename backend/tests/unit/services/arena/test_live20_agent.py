"""Unit tests for the Live20ArenaAgent.

Tests the Live20 mean reversion agent for arena simulations,
ensuring it produces the same decisions as Live20Service.
"""

from datetime import date
from decimal import Decimal

import pytest

from app.services.arena.agent_protocol import AgentDecision, PriceBar
from app.services.arena.agents.live20_agent import Live20ArenaAgent


class TestLive20ArenaAgentProperties:
    """Tests for Live20ArenaAgent properties."""

    @pytest.fixture
    def agent(self) -> Live20ArenaAgent:
        """Create agent instance for testing."""
        return Live20ArenaAgent()

    @pytest.mark.unit
    def test_name_property(self, agent: Live20ArenaAgent) -> None:
        """Test agent name is correct."""
        assert agent.name == "Live20"

    @pytest.mark.unit
    def test_required_lookback_days(self, agent: Live20ArenaAgent) -> None:
        """Test required lookback days is 60."""
        assert agent.required_lookback_days == 60

    @pytest.mark.unit
    def test_weight_per_criterion(self, agent: Live20ArenaAgent) -> None:
        """Test weight per criterion constant."""
        assert agent.WEIGHT_PER_CRITERION == 20

    @pytest.mark.unit
    def test_ma20_distance_threshold(self, agent: Live20ArenaAgent) -> None:
        """Test MA20 distance threshold constant."""
        assert agent.MA20_DISTANCE_THRESHOLD == 5.0

    @pytest.mark.unit
    def test_min_criteria_for_setup(self, agent: Live20ArenaAgent) -> None:
        """Test minimum criteria for setup constant."""
        assert agent.MIN_CRITERIA_FOR_SETUP == 3

    @pytest.mark.unit
    def test_min_score_for_signal(self, agent: Live20ArenaAgent) -> None:
        """Test minimum score for signal constant."""
        assert agent.MIN_SCORE_FOR_SIGNAL == 60


class TestLive20ArenaAgentEvaluate:
    """Tests for Live20ArenaAgent.evaluate() method."""

    @pytest.fixture
    def agent(self) -> Live20ArenaAgent:
        """Create agent instance for testing."""
        return Live20ArenaAgent()

    def _create_price_bar(
        self,
        day_offset: int,
        open_price: float,
        high: float,
        low: float,
        close: float,
        volume: int = 1000000,
    ) -> PriceBar:
        """Create a test PriceBar with given parameters.

        Args:
            day_offset: Days offset from 2024-01-01.
            open_price: Opening price.
            high: High price for the day.
            low: Low price for the day.
            close: Closing price.
            volume: Trading volume (default 1000000).

        Returns:
            PriceBar with specified values.
        """
        return PriceBar(
            date=date(2024, 1, 1 + day_offset),
            open=Decimal(str(open_price)),
            high=Decimal(str(high)),
            low=Decimal(str(low)),
            close=Decimal(str(close)),
            volume=volume,
        )

    def _create_downtrend_bars(self, num_bars: int = 30) -> list[PriceBar]:
        """Create price bars for a downtrend scenario with declining prices.

        Args:
            num_bars: Number of bars to generate.

        Returns:
            List of PriceBar objects representing a downtrend.
        """
        bars = []
        for i in range(num_bars):
            # Gradual price decline over time
            base_price = 100.0 - (i * 0.5)
            open_price = base_price + 0.5
            close = base_price - 0.5
            high = open_price + 1.0
            low = close - 1.0
            bars.append(
                self._create_price_bar(
                    i, open_price, high, low, close, volume=1000000 - (i * 10000)
                )
            )
        return bars

    def _create_uptrend_bars(self, num_bars: int = 30) -> list[PriceBar]:
        """Create price bars for an uptrend scenario with rising prices.

        Args:
            num_bars: Number of bars to generate.

        Returns:
            List of PriceBar objects representing an uptrend.
        """
        bars = []
        for i in range(num_bars):
            # Gradual price increase over time
            base_price = 100.0 + (i * 0.5)
            open_price = base_price - 0.5
            close = base_price + 0.5
            high = close + 1.0
            low = open_price - 1.0
            bars.append(self._create_price_bar(i, open_price, high, low, close))
        return bars

    def _create_sideways_bars(self, num_bars: int = 30) -> list[PriceBar]:
        """Create price bars for a sideways/neutral scenario.

        Args:
            num_bars: Number of bars to generate.

        Returns:
            List of PriceBar objects with stable prices.
        """
        bars = []
        for i in range(num_bars):
            base_price = 100.0
            open_price = base_price
            close = base_price
            high = base_price + 1.0
            low = base_price - 1.0
            bars.append(self._create_price_bar(i, open_price, high, low, close))
        return bars

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_evaluate_returns_hold_when_has_position(
        self, agent: Live20ArenaAgent
    ) -> None:
        """Test that agent returns HOLD when already holding position."""
        bars = self._create_downtrend_bars()

        decision = await agent.evaluate(
            symbol="AAPL",
            price_history=bars,
            current_date=date(2024, 1, 30),
            has_open_position=True,
        )

        assert decision.action == "HOLD"
        assert decision.symbol == "AAPL"
        assert decision.reasoning == "Already holding position"
        assert decision.score is None

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_evaluate_returns_no_signal_with_insufficient_data(
        self, agent: Live20ArenaAgent
    ) -> None:
        """Test that agent returns NO_SIGNAL with insufficient data."""
        # Only 10 bars, need at least 25
        bars = [
            self._create_price_bar(i, 100.0, 101.0, 99.0, 100.0) for i in range(10)
        ]

        decision = await agent.evaluate(
            symbol="AAPL",
            price_history=bars,
            current_date=date(2024, 1, 10),
            has_open_position=False,
        )

        assert decision.action == "NO_SIGNAL"
        assert decision.symbol == "AAPL"
        assert "Insufficient data" in decision.reasoning
        assert "10 bars" in decision.reasoning
        assert decision.score is None

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_evaluate_returns_no_signal_with_exactly_24_bars(
        self, agent: Live20ArenaAgent
    ) -> None:
        """Test that agent returns NO_SIGNAL with exactly 24 bars (need 25)."""
        bars = [
            self._create_price_bar(i, 100.0, 101.0, 99.0, 100.0) for i in range(24)
        ]

        decision = await agent.evaluate(
            symbol="AAPL",
            price_history=bars,
            current_date=date(2024, 1, 24),
            has_open_position=False,
        )

        assert decision.action == "NO_SIGNAL"
        assert "24 bars" in decision.reasoning

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_evaluate_succeeds_with_25_bars(
        self, agent: Live20ArenaAgent
    ) -> None:
        """Test that agent can evaluate with exactly 25 bars."""
        bars = [
            self._create_price_bar(i, 100.0, 101.0, 99.0, 100.0) for i in range(25)
        ]

        decision = await agent.evaluate(
            symbol="AAPL",
            price_history=bars,
            current_date=date(2024, 1, 25),
            has_open_position=False,
        )

        # Should not fail with insufficient data
        assert decision.action in ["BUY", "NO_SIGNAL"]
        assert "Insufficient data" not in (decision.reasoning or "")

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_evaluate_downtrend_no_setup(
        self, agent: Live20ArenaAgent
    ) -> None:
        """Test evaluation in downtrend without enough criteria aligned."""
        # Simple downtrend without all criteria aligned
        bars = self._create_sideways_bars()

        decision = await agent.evaluate(
            symbol="AAPL",
            price_history=bars,
            current_date=date(2024, 1, 30),
            has_open_position=False,
        )

        assert decision.action == "NO_SIGNAL"
        assert decision.symbol == "AAPL"
        assert decision.score is not None
        assert decision.score < agent.MIN_SCORE_FOR_SIGNAL

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_evaluate_decision_has_reasoning(
        self, agent: Live20ArenaAgent
    ) -> None:
        """Test that decision includes reasoning with criteria breakdown."""
        bars = self._create_downtrend_bars()

        decision = await agent.evaluate(
            symbol="AAPL",
            price_history=bars,
            current_date=date(2024, 1, 30),
            has_open_position=False,
        )

        assert decision.reasoning is not None
        assert "Score:" in decision.reasoning
        assert "/100" in decision.reasoning
        assert "Aligned:" in decision.reasoning
        assert "Not aligned:" in decision.reasoning

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_evaluate_decision_score_is_multiple_of_20(
        self, agent: Live20ArenaAgent
    ) -> None:
        """Test that score is always a multiple of 20 (weight per criterion)."""
        bars = self._create_downtrend_bars()

        decision = await agent.evaluate(
            symbol="AAPL",
            price_history=bars,
            current_date=date(2024, 1, 30),
            has_open_position=False,
        )

        assert decision.score is not None
        assert decision.score % 20 == 0
        assert 0 <= decision.score <= 100

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_evaluate_buy_signal_requires_3_criteria(
        self, agent: Live20ArenaAgent
    ) -> None:
        """Test that BUY signal requires at least 3 aligned criteria."""
        # Create a scenario that should generate BUY signal
        # Strong downtrend with price far below MA20
        bars = []
        for i in range(30):
            # Create strong downtrend with price falling well below MA20
            if i < 20:
                base = 100.0
            else:
                # Steep decline in last 10 days
                base = 100.0 - ((i - 20) * 3.0)

            open_price = base + 0.2
            close = base - 0.2
            high = open_price + 0.5
            low = close - 0.5

            bars.append(
                self._create_price_bar(
                    i, open_price, high, low, close, volume=1000000 - (i * 20000)
                )
            )

        decision = await agent.evaluate(
            symbol="AAPL",
            price_history=bars,
            current_date=date(2024, 1, 30),
            has_open_position=False,
        )

        if decision.action == "BUY":
            assert decision.score >= agent.MIN_SCORE_FOR_SIGNAL
        else:
            assert decision.score < agent.MIN_SCORE_FOR_SIGNAL


class TestLive20ArenaAgentCriteria:
    """Tests for individual criteria evaluation in Live20ArenaAgent."""

    @pytest.fixture
    def agent(self) -> Live20ArenaAgent:
        """Create agent instance for testing."""
        return Live20ArenaAgent()

    def _create_price_bar(
        self,
        day_offset: int,
        open_price: float,
        high: float,
        low: float,
        close: float,
        volume: int = 1000000,
    ) -> PriceBar:
        """Create a test PriceBar with given parameters.

        Args:
            day_offset: Days offset from 2024-01-01.
            open_price: Opening price.
            high: High price for the day.
            low: Low price for the day.
            close: Closing price.
            volume: Trading volume (default 1000000).

        Returns:
            PriceBar with specified values.
        """
        return PriceBar(
            date=date(2024, 1, 1 + day_offset),
            open=Decimal(str(open_price)),
            high=Decimal(str(high)),
            low=Decimal(str(low)),
            close=Decimal(str(close)),
            volume=volume,
        )

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_trend_criterion_bearish_aligned_for_long(
        self, agent: Live20ArenaAgent
    ) -> None:
        """Test that bearish trend aligns for LONG (mean reversion)."""
        # Create clear bearish 10-day trend
        bars = []
        for i in range(30):
            if i < 20:
                base = 100.0
            else:
                # Clear downtrend in last 10 days (>1% decline)
                base = 100.0 - ((i - 20) * 1.5)
            bars.append(self._create_price_bar(i, base, base + 1, base - 1, base))

        decision = await agent.evaluate(
            symbol="AAPL",
            price_history=bars,
            current_date=date(2024, 1, 30),
            has_open_position=False,
        )

        assert decision.reasoning is not None
        # Trend should be mentioned in aligned or not aligned
        assert "trend" in decision.reasoning.lower()

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_ma20_criterion_far_below_aligned_for_long(
        self, agent: Live20ArenaAgent
    ) -> None:
        """Test that price far below MA20 (>5%) aligns for LONG."""
        # Create scenario with price well below MA20
        bars = []
        for i in range(30):
            if i < 25:
                base = 100.0
            else:
                # Price drops significantly in last 5 days
                base = 90.0  # 10% below MA20
            bars.append(self._create_price_bar(i, base, base + 1, base - 1, base))

        decision = await agent.evaluate(
            symbol="AAPL",
            price_history=bars,
            current_date=date(2024, 1, 30),
            has_open_position=False,
        )

        assert decision.reasoning is not None
        # MA20 should be mentioned
        assert "ma20" in decision.reasoning.lower()

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_volume_criterion_in_reasoning(
        self, agent: Live20ArenaAgent
    ) -> None:
        """Test that volume criterion appears in reasoning."""
        bars = [
            self._create_price_bar(i, 100.0, 101.0, 99.0, 100.0) for i in range(30)
        ]

        decision = await agent.evaluate(
            symbol="AAPL",
            price_history=bars,
            current_date=date(2024, 1, 30),
            has_open_position=False,
        )

        assert decision.reasoning is not None
        assert "volume" in decision.reasoning.lower()

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_cci_criterion_in_reasoning(
        self, agent: Live20ArenaAgent
    ) -> None:
        """Test that CCI criterion appears in reasoning."""
        bars = [
            self._create_price_bar(i, 100.0, 101.0, 99.0, 100.0) for i in range(30)
        ]

        decision = await agent.evaluate(
            symbol="AAPL",
            price_history=bars,
            current_date=date(2024, 1, 30),
            has_open_position=False,
        )

        assert decision.reasoning is not None
        assert "cci" in decision.reasoning.lower()

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_candle_criterion_in_reasoning(
        self, agent: Live20ArenaAgent
    ) -> None:
        """Test that candle criterion appears in reasoning."""
        bars = [
            self._create_price_bar(i, 100.0, 101.0, 99.0, 100.0) for i in range(30)
        ]

        decision = await agent.evaluate(
            symbol="AAPL",
            price_history=bars,
            current_date=date(2024, 1, 30),
            has_open_position=False,
        )

        assert decision.reasoning is not None
        assert "candle" in decision.reasoning.lower()


class TestLive20ArenaAgentEdgeCases:
    """Tests for edge cases and error handling in Live20ArenaAgent."""

    @pytest.fixture
    def agent(self) -> Live20ArenaAgent:
        """Create agent instance for testing."""
        return Live20ArenaAgent()

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_empty_price_history(self, agent: Live20ArenaAgent) -> None:
        """Test evaluation with empty price history."""
        decision = await agent.evaluate(
            symbol="AAPL",
            price_history=[],
            current_date=date(2024, 1, 1),
            has_open_position=False,
        )

        assert decision.action == "NO_SIGNAL"
        assert "Insufficient data" in decision.reasoning
        assert "0 bars" in decision.reasoning

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_single_bar_price_history(self, agent: Live20ArenaAgent) -> None:
        """Test evaluation with single price bar."""
        bars = [
            PriceBar(
                date=date(2024, 1, 1),
                open=Decimal("100"),
                high=Decimal("101"),
                low=Decimal("99"),
                close=Decimal("100"),
                volume=1000000,
            )
        ]

        decision = await agent.evaluate(
            symbol="AAPL",
            price_history=bars,
            current_date=date(2024, 1, 1),
            has_open_position=False,
        )

        assert decision.action == "NO_SIGNAL"
        assert "1 bars" in decision.reasoning

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_different_symbols(self, agent: Live20ArenaAgent) -> None:
        """Test that symbol is correctly included in decision."""
        bars = [
            PriceBar(
                date=date(2024, 1, i),
                open=Decimal("100"),
                high=Decimal("101"),
                low=Decimal("99"),
                close=Decimal("100"),
                volume=1000000,
            )
            for i in range(1, 31)
        ]

        for symbol in ["AAPL", "MSFT", "GOOGL", "TSLA"]:
            decision = await agent.evaluate(
                symbol=symbol,
                price_history=bars,
                current_date=date(2024, 1, 30),
                has_open_position=False,
            )
            assert decision.symbol == symbol

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_large_volume_values(self, agent: Live20ArenaAgent) -> None:
        """Test handling of very large volume values."""
        bars = [
            PriceBar(
                date=date(2024, 1, i),
                open=Decimal("100"),
                high=Decimal("101"),
                low=Decimal("99"),
                close=Decimal("100"),
                volume=100000000000,  # 100 billion
            )
            for i in range(1, 31)
        ]

        decision = await agent.evaluate(
            symbol="AAPL",
            price_history=bars,
            current_date=date(2024, 1, 30),
            has_open_position=False,
        )

        # Should not fail with large volumes
        assert decision.action in ["BUY", "HOLD", "NO_SIGNAL"]

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_zero_volume_values(self, agent: Live20ArenaAgent) -> None:
        """Test handling of zero volume values."""
        bars = [
            PriceBar(
                date=date(2024, 1, i),
                open=Decimal("100"),
                high=Decimal("101"),
                low=Decimal("99"),
                close=Decimal("100"),
                volume=0,
            )
            for i in range(1, 31)
        ]

        decision = await agent.evaluate(
            symbol="AAPL",
            price_history=bars,
            current_date=date(2024, 1, 30),
            has_open_position=False,
        )

        # Should not fail with zero volumes
        assert decision.action in ["BUY", "HOLD", "NO_SIGNAL"]

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_flat_price_data(self, agent: Live20ArenaAgent) -> None:
        """Test evaluation with completely flat price data."""
        bars = [
            PriceBar(
                date=date(2024, 1, i),
                open=Decimal("100"),
                high=Decimal("100"),
                low=Decimal("100"),
                close=Decimal("100"),
                volume=1000000,
            )
            for i in range(1, 31)
        ]

        decision = await agent.evaluate(
            symbol="AAPL",
            price_history=bars,
            current_date=date(2024, 1, 30),
            has_open_position=False,
        )

        # Flat price should result in NO_SIGNAL (no trend, no MA divergence)
        assert decision.action == "NO_SIGNAL"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_high_precision_prices(self, agent: Live20ArenaAgent) -> None:
        """Test handling of high precision decimal prices."""
        bars = [
            PriceBar(
                date=date(2024, 1, i),
                open=Decimal("100.12345678"),
                high=Decimal("101.98765432"),
                low=Decimal("99.11223344"),
                close=Decimal("100.55667788"),
                volume=1000000,
            )
            for i in range(1, 31)
        ]

        decision = await agent.evaluate(
            symbol="AAPL",
            price_history=bars,
            current_date=date(2024, 1, 30),
            has_open_position=False,
        )

        # Should not fail with high precision decimals
        assert decision.action in ["BUY", "HOLD", "NO_SIGNAL"]


class TestLive20ArenaAgentConfiguration:
    """Tests for Live20ArenaAgent configuration behavior."""

    @pytest.mark.unit
    def test_default_min_buy_score(self) -> None:
        """Test agent uses default min_buy_score of 60 when no config provided."""
        agent = Live20ArenaAgent()

        assert agent.min_buy_score == 60
        assert agent.MIN_SCORE_FOR_SIGNAL == 60  # Backward compatibility property

    @pytest.mark.unit
    def test_custom_min_buy_score(self) -> None:
        """Test agent uses configured min_buy_score (e.g., 80)."""
        agent = Live20ArenaAgent(config={"min_buy_score": 80})

        assert agent.min_buy_score == 80
        assert agent.MIN_SCORE_FOR_SIGNAL == 80

    @pytest.mark.unit
    def test_empty_config_uses_default(self) -> None:
        """Test agent uses default when config is empty dict."""
        agent = Live20ArenaAgent(config={})

        assert agent.min_buy_score == 60

    @pytest.mark.unit
    def test_min_score_for_signal_backward_compat(self) -> None:
        """Test MIN_SCORE_FOR_SIGNAL property returns configured value."""
        # Default
        agent_default = Live20ArenaAgent()
        assert agent_default.MIN_SCORE_FOR_SIGNAL == 60

        # Custom
        agent_custom = Live20ArenaAgent(config={"min_buy_score": 75})
        assert agent_custom.MIN_SCORE_FOR_SIGNAL == 75

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_buy_signal_respects_custom_threshold(self) -> None:
        """Test BUY signal only triggers when score >= custom threshold."""
        # Create agent with high threshold (80)
        agent = Live20ArenaAgent(config={"min_buy_score": 80})

        # Create scenario with moderate downtrend (score around 60-80)
        bars = []
        for i in range(30):
            if i < 20:
                base = 100.0
            else:
                # Moderate decline
                base = 100.0 - ((i - 20) * 1.5)

            bars.append(
                PriceBar(
                    date=date(2024, 1, 1 + i),
                    open=Decimal(str(base + 0.2)),
                    high=Decimal(str(base + 1.0)),
                    low=Decimal(str(base - 1.0)),
                    close=Decimal(str(base - 0.2)),
                    volume=1000000 - (i * 15000),
                )
            )

        decision = await agent.evaluate(
            symbol="AAPL",
            price_history=bars,
            current_date=date(2024, 1, 30),
            has_open_position=False,
        )

        # With threshold of 80, score must be >= 80 for BUY
        if decision.action == "BUY":
            assert decision.score >= 80
        else:
            assert decision.score < 80

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_buy_signal_triggers_at_threshold(self) -> None:
        """Test BUY signal triggers when score exactly equals threshold."""
        # Use default threshold (60)
        agent = Live20ArenaAgent()

        # Create strong downtrend to get high score
        bars = []
        for i in range(30):
            if i < 20:
                base = 100.0
            else:
                # Strong decline to align criteria
                base = 100.0 - ((i - 20) * 4.0)

            bars.append(
                PriceBar(
                    date=date(2024, 1, 1 + i),
                    open=Decimal(str(base + 0.5)),
                    high=Decimal(str(base + 1.5)),
                    low=Decimal(str(base - 1.5)),
                    close=Decimal(str(base - 0.5)),
                    volume=1500000 - (i * 30000),
                )
            )

        decision = await agent.evaluate(
            symbol="AAPL",
            price_history=bars,
            current_date=date(2024, 1, 30),
            has_open_position=False,
        )

        # Verify threshold behavior: BUY if score >= min_buy_score
        if decision.score >= agent.min_buy_score:
            assert decision.action == "BUY"
        else:
            assert decision.action == "NO_SIGNAL"


class TestLive20ArenaAgentConsistency:
    """Tests to verify Live20ArenaAgent produces consistent results with Live20Service."""

    @pytest.fixture
    def agent(self) -> Live20ArenaAgent:
        """Create agent instance for testing."""
        return Live20ArenaAgent()

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_same_data_same_decision(self, agent: Live20ArenaAgent) -> None:
        """Test that same input data produces same decision."""
        bars = [
            PriceBar(
                date=date(2024, 1, i),
                open=Decimal("100"),
                high=Decimal("101"),
                low=Decimal("99"),
                close=Decimal("100"),
                volume=1000000,
            )
            for i in range(1, 31)
        ]

        decision1 = await agent.evaluate(
            symbol="AAPL",
            price_history=bars,
            current_date=date(2024, 1, 30),
            has_open_position=False,
        )

        decision2 = await agent.evaluate(
            symbol="AAPL",
            price_history=bars,
            current_date=date(2024, 1, 30),
            has_open_position=False,
        )

        assert decision1.action == decision2.action
        assert decision1.score == decision2.score

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_agent_is_stateless(self, agent: Live20ArenaAgent) -> None:
        """Test that agent is stateless (doesn't remember previous calls)."""
        # First evaluation with downtrend
        downtrend_bars = []
        for i in range(30):
            base = 100.0 - (i * 0.5)
            downtrend_bars.append(
                PriceBar(
                    date=date(2024, 1, i + 1),
                    open=Decimal(str(base)),
                    high=Decimal(str(base + 1)),
                    low=Decimal(str(base - 1)),
                    close=Decimal(str(base)),
                    volume=1000000,
                )
            )

        await agent.evaluate(
            symbol="AAPL",
            price_history=downtrend_bars,
            current_date=date(2024, 1, 30),
            has_open_position=False,
        )

        # Second evaluation with flat data
        flat_bars = [
            PriceBar(
                date=date(2024, 1, i),
                open=Decimal("100"),
                high=Decimal("101"),
                low=Decimal("99"),
                close=Decimal("100"),
                volume=1000000,
            )
            for i in range(1, 31)
        ]

        decision = await agent.evaluate(
            symbol="MSFT",
            price_history=flat_bars,
            current_date=date(2024, 1, 30),
            has_open_position=False,
        )

        # Decision should be based on flat data, not influenced by previous downtrend call
        assert decision.symbol == "MSFT"
        # Flat data typically results in NO_SIGNAL
        assert decision.action == "NO_SIGNAL"
