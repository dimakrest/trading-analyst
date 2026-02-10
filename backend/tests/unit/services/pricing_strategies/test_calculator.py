"""Tests for pricing calculator."""

from decimal import Decimal

import pytest

from app.services.pricing_strategies import (
    PricingCalculator,
    PricingConfig,
    EntryStrategy,
    ExitStrategy,
)


class TestPricingCalculator:
    """Tests for PricingCalculator class."""

    @pytest.fixture
    def sample_prices(self):
        """Sample price data for testing."""
        # 20 days of data with known values
        return {
            "closes": [100.0 + i * 0.5 for i in range(20)],  # 100 to 109.5
            "highs": [101.0 + i * 0.5 for i in range(20)],
            "lows": [99.0 + i * 0.5 for i in range(20)],
        }

    def test_current_price_long(self, sample_prices):
        """Test CURRENT_PRICE entry for LONG direction."""
        config = PricingConfig(entry_strategy=EntryStrategy.CURRENT_PRICE)
        calculator = PricingCalculator(config)

        result = calculator.calculate(
            "LONG",
            sample_prices["closes"],
            sample_prices["highs"],
            sample_prices["lows"],
        )

        assert result is not None
        assert result.entry_price == Decimal("109.5")  # Latest close
        assert result.entry_strategy == EntryStrategy.CURRENT_PRICE
        assert result.stop_loss is not None
        assert result.stop_loss < result.entry_price  # Stop below entry for LONG

    def test_current_price_short(self, sample_prices):
        """Test CURRENT_PRICE entry for SHORT direction."""
        config = PricingConfig(entry_strategy=EntryStrategy.CURRENT_PRICE)
        calculator = PricingCalculator(config)

        result = calculator.calculate(
            "SHORT",
            sample_prices["closes"],
            sample_prices["highs"],
            sample_prices["lows"],
        )

        assert result is not None
        assert result.entry_price == Decimal("109.5")  # Latest close
        assert result.stop_loss is not None
        assert result.stop_loss > result.entry_price  # Stop above entry for SHORT

    def test_breakout_confirmation_long(self, sample_prices):
        """Test BREAKOUT_CONFIRMATION entry for LONG direction (2% above)."""
        config = PricingConfig(
            entry_strategy=EntryStrategy.BREAKOUT_CONFIRMATION,
            breakout_offset_pct=2.0,
        )
        calculator = PricingCalculator(config)

        result = calculator.calculate(
            "LONG",
            sample_prices["closes"],
            sample_prices["highs"],
            sample_prices["lows"],
        )

        assert result is not None
        # 109.5 * 1.02 = 111.69
        assert float(result.entry_price) == pytest.approx(111.69, rel=0.01)
        assert result.entry_strategy == EntryStrategy.BREAKOUT_CONFIRMATION

    def test_breakout_confirmation_short(self, sample_prices):
        """Test BREAKOUT_CONFIRMATION entry for SHORT direction (2% below)."""
        config = PricingConfig(
            entry_strategy=EntryStrategy.BREAKOUT_CONFIRMATION,
            breakout_offset_pct=2.0,
        )
        calculator = PricingCalculator(config)

        result = calculator.calculate(
            "SHORT",
            sample_prices["closes"],
            sample_prices["highs"],
            sample_prices["lows"],
        )

        assert result is not None
        # 109.5 * 0.98 = 107.31
        assert float(result.entry_price) == pytest.approx(107.31, rel=0.01)

    def test_no_setup_returns_none(self, sample_prices):
        """Test NO_SETUP direction returns None."""
        calculator = PricingCalculator()

        result = calculator.calculate(
            "NO_SETUP",
            sample_prices["closes"],
            sample_prices["highs"],
            sample_prices["lows"],
        )

        assert result is None

    def test_atr_stop_loss_calculation(self):
        """Test ATR-based stop loss with known ATR percentage."""
        # Create data with consistent $2 daily range (ATR should be ~2)
        closes = [100.0] * 20
        highs = [101.0] * 20
        lows = [99.0] * 20

        config = PricingConfig(atr_multiplier=0.5)
        calculator = PricingCalculator(config)

        result = calculator.calculate("LONG", closes, highs, lows)

        assert result is not None
        # ATR should be returned as percentage: ~2.0% for $2 ATR on $100 stock
        assert result.atr is not None
        assert float(result.atr) == pytest.approx(2.0, rel=0.1)
        # Stop should be entry - (0.5 * ATR_dollars)
        # ATR_dollars = 2% of 100 = 2, so stop ~ 100 - 1.0 = 99.0
        assert result.stop_loss is not None
        assert float(result.stop_loss) == pytest.approx(99.0, rel=0.1)

    def test_insufficient_data_returns_none_stop_loss(self):
        """Test that insufficient data returns entry but None stop_loss."""
        # Only 10 days - not enough for 14-period ATR
        closes = [100.0] * 10
        highs = [101.0] * 10
        lows = [99.0] * 10

        calculator = PricingCalculator()
        result = calculator.calculate("LONG", closes, highs, lows)

        assert result is not None
        assert result.entry_price == Decimal("100.0")
        assert result.stop_loss is None  # ATR failed, human must define risk

    def test_config_to_dict_roundtrip(self):
        """Test PricingConfig serialization/deserialization."""
        config = PricingConfig(
            entry_strategy=EntryStrategy.BREAKOUT_CONFIRMATION,
            atr_multiplier=0.75,
        )

        data = config.to_dict()
        restored = PricingConfig.from_dict(data)

        assert restored.entry_strategy == config.entry_strategy
        assert restored.atr_multiplier == config.atr_multiplier

    def test_default_config(self):
        """Test default configuration values."""
        config = PricingConfig()

        assert config.entry_strategy == EntryStrategy.CURRENT_PRICE
        assert config.exit_strategy == ExitStrategy.ATR_BASED
        assert config.breakout_offset_pct == 2.0
        assert config.atr_multiplier == 0.5

    def test_calculator_default_config(self, sample_prices):
        """Test calculator uses default config when none provided."""
        calculator = PricingCalculator()  # No config

        result = calculator.calculate(
            "LONG",
            sample_prices["closes"],
            sample_prices["highs"],
            sample_prices["lows"],
        )

        assert result is not None
        assert result.entry_strategy == EntryStrategy.CURRENT_PRICE
        assert result.exit_strategy == ExitStrategy.ATR_BASED

    def test_from_dict_with_defaults(self):
        """Test from_dict uses defaults for missing keys."""
        data = {"entry_strategy": "breakout_confirmation"}
        config = PricingConfig.from_dict(data)

        assert config.entry_strategy == EntryStrategy.BREAKOUT_CONFIRMATION
        assert config.exit_strategy == ExitStrategy.ATR_BASED  # default
        assert config.breakout_offset_pct == 2.0  # default
        assert config.atr_multiplier == 0.5  # default

    def test_from_dict_empty(self):
        """Test from_dict with empty dict uses all defaults."""
        config = PricingConfig.from_dict({})

        assert config.entry_strategy == EntryStrategy.CURRENT_PRICE
        assert config.exit_strategy == ExitStrategy.ATR_BASED

    def test_exit_strategy_in_result(self, sample_prices):
        """Test exit strategy is included in result."""
        config = PricingConfig(exit_strategy=ExitStrategy.ATR_BASED)
        calculator = PricingCalculator(config)

        result = calculator.calculate(
            "LONG",
            sample_prices["closes"],
            sample_prices["highs"],
            sample_prices["lows"],
        )

        assert result is not None
        assert result.exit_strategy == ExitStrategy.ATR_BASED

    def test_stop_loss_short_direction(self):
        """Test stop loss is above entry for SHORT positions."""
        closes = [100.0] * 20
        highs = [101.0] * 20
        lows = [99.0] * 20

        config = PricingConfig(atr_multiplier=0.5)
        calculator = PricingCalculator(config)

        result = calculator.calculate("SHORT", closes, highs, lows)

        assert result is not None
        assert result.stop_loss is not None
        # For SHORT, stop should be ABOVE entry
        assert result.stop_loss > result.entry_price

    def test_atr_percentage_different_price_ranges(self):
        """Test ATR percentage is accurate across different price ranges."""
        config = PricingConfig()
        calculator = PricingCalculator(config)

        # Test penny stock ($5): $0.25 ATR = 5%
        penny_closes = [5.0] * 20
        penny_highs = [5.125] * 20
        penny_lows = [4.875] * 20
        penny_result = calculator.calculate("LONG", penny_closes, penny_highs, penny_lows)
        assert penny_result is not None
        assert penny_result.atr is not None
        assert float(penny_result.atr) == pytest.approx(5.0, rel=0.1)

        # Test high-priced stock ($500): $5 ATR = 1%
        high_closes = [500.0] * 20
        high_highs = [502.5] * 20
        high_lows = [497.5] * 20
        high_result = calculator.calculate("LONG", high_closes, high_highs, high_lows)
        assert high_result is not None
        assert high_result.atr is not None
        assert float(high_result.atr) == pytest.approx(1.0, rel=0.1)

    def test_atr_percentage_stop_loss_consistency(self):
        """Test that stop loss calculation works correctly with ATR percentage."""
        closes = [150.0] * 20
        highs = [153.0] * 20  # $6 range (153-147)
        lows = [147.0] * 20

        config = PricingConfig(atr_multiplier=0.5)
        calculator = PricingCalculator(config)

        result = calculator.calculate("LONG", closes, highs, lows)

        assert result is not None
        # ATR should be 4% (6/150 * 100)
        assert result.atr is not None
        assert float(result.atr) == pytest.approx(4.0, rel=0.1)
        # Stop loss: entry - (0.5 * 4% of 150) = 150 - 3.0 = 147.0
        assert result.stop_loss is not None
        assert float(result.stop_loss) == pytest.approx(147.0, rel=0.1)

    def test_breakout_confirmation_custom_percentage(self, sample_prices):
        """Test BREAKOUT_CONFIRMATION with custom percentage."""
        config = PricingConfig(
            entry_strategy=EntryStrategy.BREAKOUT_CONFIRMATION,
            breakout_offset_pct=5.0,  # 5% offset instead of 2%
        )
        calculator = PricingCalculator(config)

        result = calculator.calculate(
            "LONG",
            sample_prices["closes"],
            sample_prices["highs"],
            sample_prices["lows"],
        )

        assert result is not None
        # 109.5 * 1.05 = 114.975
        assert float(result.entry_price) == pytest.approx(114.975, rel=0.01)

    def test_custom_atr_multiplier(self):
        """Test custom ATR multiplier for stop loss."""
        closes = [100.0] * 20
        highs = [101.0] * 20
        lows = [99.0] * 20

        # ATR ~ 2.0% of 100 = 2.0, with multiplier 1.0, stop distance ~ 2.0
        config = PricingConfig(atr_multiplier=1.0)
        calculator = PricingCalculator(config)

        result = calculator.calculate("LONG", closes, highs, lows)

        assert result is not None
        # ATR should be percentage: ~2.0%
        assert result.atr is not None
        assert float(result.atr) == pytest.approx(2.0, rel=0.1)
        assert result.stop_loss is not None
        # Stop should be entry - (1.0 * ATR_dollars) ~ 100 - 2 = 98
        assert float(result.stop_loss) == pytest.approx(98.0, rel=0.1)
