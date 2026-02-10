"""Unit tests for PricingCalculator.

Tests pricing calculation logic including:
- Entry price calculation (current_price, breakout_confirmation)
- Stop loss calculation (atr_based)
- ATR calculation and inclusion in results
- Edge cases (insufficient data, ATR calculation failures)
"""

from decimal import Decimal

import pytest

from app.services.pricing_strategies.calculator import PricingCalculator
from app.services.pricing_strategies.types import EntryStrategy, ExitStrategy, PricingConfig


class TestPricingCalculator:
    """Test suite for PricingCalculator."""

    @pytest.fixture
    def sample_price_data(self):
        """Create sample price data with known ATR.

        Using simple data where we can calculate ATR manually:
        - 30 days of data to ensure enough for 14-period ATR
        - Consistent ranges to make ATR predictable
        """
        # Simple uptrend with consistent volatility
        closes = [100.0 + i for i in range(30)]
        highs = [c + 2.0 for c in closes]  # High = close + 2
        lows = [c - 2.0 for c in closes]   # Low = close - 2

        return closes, highs, lows

    def test_calculate_long_current_price_strategy(self, sample_price_data):
        """Test LONG direction with CURRENT_PRICE entry strategy."""
        closes, highs, lows = sample_price_data

        config = PricingConfig(
            entry_strategy=EntryStrategy.CURRENT_PRICE,
            exit_strategy=ExitStrategy.ATR_BASED,
            atr_multiplier=0.5,
        )
        calculator = PricingCalculator(config)

        result = calculator.calculate("LONG", closes, highs, lows)

        assert result is not None
        assert result.entry_price == Decimal("129.0000")  # Latest close
        assert result.atr is not None
        assert result.atr > Decimal("0")
        # Stop loss should be entry - (atr * multiplier)
        # With consistent 4-point range, ATR should be approximately 4.0
        assert result.stop_loss is not None
        assert result.stop_loss < result.entry_price
        assert result.entry_strategy == EntryStrategy.CURRENT_PRICE
        assert result.exit_strategy == ExitStrategy.ATR_BASED

    def test_calculate_short_current_price_strategy(self, sample_price_data):
        """Test SHORT direction with CURRENT_PRICE entry strategy."""
        closes, highs, lows = sample_price_data

        config = PricingConfig(
            entry_strategy=EntryStrategy.CURRENT_PRICE,
            exit_strategy=ExitStrategy.ATR_BASED,
            atr_multiplier=0.5,
        )
        calculator = PricingCalculator(config)

        result = calculator.calculate("SHORT", closes, highs, lows)

        assert result is not None
        assert result.entry_price == Decimal("129.0000")  # Latest close
        assert result.atr is not None
        assert result.atr > Decimal("0")
        # Stop loss should be entry + (atr * multiplier)
        assert result.stop_loss is not None
        assert result.stop_loss > result.entry_price
        assert result.entry_strategy == EntryStrategy.CURRENT_PRICE
        assert result.exit_strategy == ExitStrategy.ATR_BASED

    def test_calculate_long_breakout_confirmation_strategy(self, sample_price_data):
        """Test LONG direction with BREAKOUT_CONFIRMATION entry strategy."""
        closes, highs, lows = sample_price_data

        config = PricingConfig(
            entry_strategy=EntryStrategy.BREAKOUT_CONFIRMATION,
            exit_strategy=ExitStrategy.ATR_BASED,
            breakout_offset_pct=2.0,
            atr_multiplier=0.5,
        )
        calculator = PricingCalculator(config)

        result = calculator.calculate("LONG", closes, highs, lows)

        assert result is not None
        # Entry should be current_price * (1 + 0.02) = 129 * 1.02 = 131.58
        assert result.entry_price == Decimal("131.5800")
        assert result.atr is not None
        assert result.stop_loss is not None
        assert result.stop_loss < result.entry_price
        assert result.entry_strategy == EntryStrategy.BREAKOUT_CONFIRMATION

    def test_calculate_short_breakout_confirmation_strategy(self, sample_price_data):
        """Test SHORT direction with BREAKOUT_CONFIRMATION entry strategy."""
        closes, highs, lows = sample_price_data

        config = PricingConfig(
            entry_strategy=EntryStrategy.BREAKOUT_CONFIRMATION,
            exit_strategy=ExitStrategy.ATR_BASED,
            breakout_offset_pct=2.0,
            atr_multiplier=0.5,
        )
        calculator = PricingCalculator(config)

        result = calculator.calculate("SHORT", closes, highs, lows)

        assert result is not None
        # Entry should be current_price * (1 - 0.02) = 129 * 0.98 = 126.42
        assert result.entry_price == Decimal("126.4200")
        assert result.atr is not None
        assert result.stop_loss is not None
        assert result.stop_loss > result.entry_price
        assert result.entry_strategy == EntryStrategy.BREAKOUT_CONFIRMATION

    def test_calculate_no_setup_returns_none(self, sample_price_data):
        """Test NO_SETUP direction returns None (no pricing)."""
        closes, highs, lows = sample_price_data

        config = PricingConfig()
        calculator = PricingCalculator(config)

        result = calculator.calculate("NO_SETUP", closes, highs, lows)

        assert result is None

    def test_calculate_insufficient_data_for_atr(self):
        """Test behavior when insufficient data for ATR calculation."""
        # Only 10 days of data (need 15 for 14-period ATR)
        closes = [100.0 + i for i in range(10)]
        highs = [c + 2.0 for c in closes]
        lows = [c - 2.0 for c in closes]

        config = PricingConfig()
        calculator = PricingCalculator(config)

        result = calculator.calculate("LONG", closes, highs, lows)

        # Should still return result but with None for stop_loss and atr
        assert result is not None
        assert result.entry_price == Decimal("109.0000")
        assert result.stop_loss is None
        assert result.atr is None

    def test_calculate_atr_value_included_in_result(self, sample_price_data):
        """Test that ATR value is included in PricingResult and matches expectations.

        Verifies:
        1. ATR is not None when calculated successfully
        2. ATR value is reasonable (>0, consistent with data volatility)
        3. ATR is used correctly in stop loss calculation
        """
        closes, highs, lows = sample_price_data

        config = PricingConfig(
            entry_strategy=EntryStrategy.CURRENT_PRICE,
            exit_strategy=ExitStrategy.ATR_BASED,
            atr_multiplier=0.5,
        )
        calculator = PricingCalculator(config)

        result = calculator.calculate("LONG", closes, highs, lows)

        assert result is not None
        assert result.atr is not None

        # Verify ATR is a positive Decimal with expected precision
        assert isinstance(result.atr, Decimal)
        assert result.atr > Decimal("0")

        # With our test data (high-low range of 4), ATR should be approximately 4.0
        # Allow some variance due to True Range calculation including gaps
        assert Decimal("3.0") < result.atr < Decimal("5.0")

        # Verify stop loss calculation uses the ATR correctly
        # For LONG: stop_loss = entry - (atr * multiplier)
        expected_stop_loss = result.entry_price - (result.atr * Decimal(str(config.atr_multiplier)))
        assert abs(result.stop_loss - expected_stop_loss) < Decimal("0.01")

    def test_calculate_different_atr_multipliers(self, sample_price_data):
        """Test stop loss calculation with different ATR multipliers."""
        closes, highs, lows = sample_price_data

        # Test with multiplier = 1.0
        config_1x = PricingConfig(atr_multiplier=1.0)
        calc_1x = PricingCalculator(config_1x)
        result_1x = calc_1x.calculate("LONG", closes, highs, lows)

        # Test with multiplier = 2.0
        config_2x = PricingConfig(atr_multiplier=2.0)
        calc_2x = PricingCalculator(config_2x)
        result_2x = calc_2x.calculate("LONG", closes, highs, lows)

        assert result_1x is not None
        assert result_2x is not None

        # Same entry price
        assert result_1x.entry_price == result_2x.entry_price

        # Same ATR value
        assert result_1x.atr == result_2x.atr

        # Different stop losses (2x should be further from entry)
        assert result_1x.stop_loss is not None
        assert result_2x.stop_loss is not None

        distance_1x = result_1x.entry_price - result_1x.stop_loss
        distance_2x = result_2x.entry_price - result_2x.stop_loss

        # Distance for 2x should be approximately double distance for 1x
        assert abs(distance_2x - (distance_1x * 2)) < Decimal("0.01")
