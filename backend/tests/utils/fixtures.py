"""Common test fixtures for pattern detection framework.

This module provides reusable fixtures and mock objects for testing
pattern detectors and framework components.
"""
from datetime import datetime

import pytest

from app.detectors.base import BaseDetector
from app.models.pattern_results import PatternDirection
from app.models.pattern_results import PatternResult
from app.models.pattern_results import PatternStatus
from app.models.pattern_results import PatternType
from app.registry.detector_registry import DetectorRegistry
from tests.utils.mock_data import MockDataGenerator


class MockDetector(BaseDetector):
    """Mock detector for testing framework components"""

    def __init__(self, config=None):
        super().__init__(config)
        self._pattern_type = "mock_pattern"

    @property
    def pattern_type(self) -> str:
        return self._pattern_type

    def default_config(self):
        return {"min_data_points": 50, "mock_confidence": 0.75, "mock_strength": 0.8}

    async def detect(
        self, prices: list[float], dates: list[datetime], symbol: str
    ) -> list[PatternResult]:
        """Mock detection that always returns a predictable result"""
        try:
            self.validate_data(prices, dates)
        except Exception:
            return []

        # Create a mock pattern result
        return [
            PatternResult(
                pattern_type=PatternType.MA_CROSSOVER,
                symbol=symbol,
                start_date=dates[len(dates) // 4],
                end_date=dates[3 * len(dates) // 4],
                confidence=self.config["mock_confidence"],
                strength=self.config["mock_strength"],
                direction=PatternDirection.BULLISH,
                status=PatternStatus.COMPLETED,
                metadata={"test_detector": True, "mock_data": True},
            )
        ]


class ConfigurableMockDetector(BaseDetector):
    """Mock detector with configurable behavior for testing"""

    def __init__(self, config=None):
        super().__init__(config)
        self._pattern_type = "configurable_mock"

    @property
    def pattern_type(self) -> str:
        return self._pattern_type

    def default_config(self):
        return {
            "min_data_points": 50,
            "should_detect": True,
            "result_count": 1,
            "confidence": 0.75,
            "strength": 0.8,
            "direction": "bullish",
            "pattern_type": "ma_crossover",
        }

    async def detect(
        self, prices: list[float], dates: list[datetime], symbol: str
    ) -> list[PatternResult]:
        """Configurable mock detection"""
        try:
            self.validate_data(prices, dates)
        except Exception:
            return []

        if not self.config.get("should_detect", True):
            return []

        results = []
        result_count = self.config.get("result_count", 1)

        for i in range(result_count):
            # Map string direction to enum
            direction_map = {
                "bullish": PatternDirection.BULLISH,
                "bearish": PatternDirection.BEARISH,
                "neutral": PatternDirection.NEUTRAL,
            }
            direction = direction_map.get(
                self.config.get("direction", "bullish"), PatternDirection.BULLISH
            )

            # Map string pattern type to enum
            pattern_type_map = {
                "ma_crossover": PatternType.MA_CROSSOVER,
                "support_resistance": PatternType.SUPPORT_RESISTANCE,
                "cup_and_handle": PatternType.CUP_AND_HANDLE,
                "bull_flag": PatternType.BULL_FLAG,
            }
            pattern_type = pattern_type_map.get(
                self.config.get("pattern_type", "ma_crossover"), PatternType.MA_CROSSOVER
            )

            start_idx = len(dates) // 4 + i * 10
            end_idx = min(len(dates) - 1, start_idx + 50)

            result = PatternResult(
                pattern_type=pattern_type,
                symbol=symbol,
                start_date=dates[start_idx],
                end_date=dates[end_idx],
                confidence=self.config.get("confidence", 0.75),
                strength=self.config.get("strength", 0.8),
                direction=direction,
                status=PatternStatus.COMPLETED,
                metadata={"configurable_mock": True, "result_index": i},
            )
            results.append(result)

        return results


class FailingMockDetector(BaseDetector):
    """Mock detector that simulates failures for testing error handling"""

    def __init__(self, config=None):
        super().__init__(config)
        self._pattern_type = "failing_mock"
        # Fail during instantiation if configured to do so
        if self.config.get("fail_on_init", False):
            raise RuntimeError("Mock detector instantiation failure for testing")

    @property
    def pattern_type(self) -> str:
        return self._pattern_type

    def default_config(self):
        return {
            "min_data_points": 50,
            "should_fail": True,
            "fail_on_init": False,  # Don't fail by default (only when explicitly configured)
            "failure_type": "exception",  # 'exception', 'validation', 'empty'
        }

    async def detect(
        self, prices: list[float], dates: list[datetime], symbol: str
    ) -> list[PatternResult]:
        """Mock detection that can simulate various failure modes"""
        failure_type = self.config.get("failure_type", "exception")

        if failure_type == "exception" and self.config.get("should_fail", True):
            raise RuntimeError("Mock detector failure for testing")

        if failure_type == "validation":
            # Return empty results due to validation failure
            return []

        if failure_type == "empty":
            # Return empty results
            return []

        # If not failing, return a normal result
        try:
            self.validate_data(prices, dates)
            return [
                PatternResult(
                    pattern_type=PatternType.MA_CROSSOVER,
                    symbol=symbol,
                    start_date=dates[0],
                    end_date=dates[-1],
                    confidence=0.5,
                    strength=0.5,
                    direction=PatternDirection.NEUTRAL,
                    status=PatternStatus.COMPLETED,
                )
            ]
        except Exception:
            return []


@pytest.fixture
def mock_detector():
    """Fixture providing a basic mock detector"""
    return MockDetector()


@pytest.fixture
def configurable_mock_detector():
    """Fixture providing a configurable mock detector"""
    return ConfigurableMockDetector()


@pytest.fixture
def failing_mock_detector():
    """Fixture providing a failing mock detector"""
    return FailingMockDetector()


@pytest.fixture
def sample_price_data():
    """Fixture providing sample price data"""
    return MockDataGenerator.generate_price_series(days=100, seed=42)


@pytest.fixture
def ma_crossover_data():
    """Fixture providing MA crossover data"""
    return MockDataGenerator.generate_ma_crossover_data(crossover_type="golden")


@pytest.fixture
def death_cross_data():
    """Fixture providing death cross data"""
    return MockDataGenerator.generate_ma_crossover_data(crossover_type="death")


@pytest.fixture
def support_resistance_data():
    """Fixture providing support/resistance data"""
    return MockDataGenerator.generate_support_resistance_data()


@pytest.fixture
def cup_handle_data():
    """Fixture providing cup and handle pattern data"""
    return MockDataGenerator.generate_breakout_data(breakout_type="upward")


@pytest.fixture
def bull_flag_data():
    """Fixture providing bull flag pattern data"""
    return MockDataGenerator.generate_breakout_data(breakout_type="downward")


@pytest.fixture
def uptrend_data():
    """Fixture providing uptrend data"""
    return MockDataGenerator.generate_trend_data(trend_type="uptrend")


@pytest.fixture
def downtrend_data():
    """Fixture providing downtrend data"""
    return MockDataGenerator.generate_trend_data(trend_type="downtrend")


@pytest.fixture
def sideways_data():
    """Fixture providing sideways trend data"""
    return MockDataGenerator.generate_trend_data(trend_type="sideways")


@pytest.fixture
def noisy_data():
    """Fixture providing noisy data with no clear patterns"""
    return MockDataGenerator.generate_noisy_data()


@pytest.fixture
def large_dataset():
    """Fixture providing large dataset for performance testing"""
    return MockDataGenerator.generate_price_series(days=5000, seed=42)


@pytest.fixture
def fresh_registry():
    """Fixture providing a clean registry for testing"""
    registry = DetectorRegistry()
    registry.clear_registry()
    yield registry
    registry.clear_registry()


@pytest.fixture
def populated_registry(fresh_registry):
    """Fixture providing a registry with mock detectors registered"""
    fresh_registry.register_detector(
        name="mock_detector",
        detector_class=MockDetector,
        pattern_type=PatternType.MA_CROSSOVER,
        description="Mock detector for testing",
    )

    fresh_registry.register_detector(
        name="configurable_mock",
        detector_class=ConfigurableMockDetector,
        pattern_type=PatternType.SUPPORT_RESISTANCE,
        description="Configurable mock detector",
    )

    return fresh_registry


@pytest.fixture
def volume_data(sample_price_data):
    """Fixture providing volume data correlated with price data"""
    prices, dates = sample_price_data
    volumes = MockDataGenerator.generate_volume_series(prices)
    return volumes


@pytest.fixture
def multi_symbol_data():
    """Fixture providing data for multiple symbols"""
    symbols = ["AAPL", "GOOGL", "MSFT"]
    data = {}

    for i, symbol in enumerate(symbols):
        prices, dates = MockDataGenerator.generate_price_series(days=200, seed=100 + i)
        volumes = MockDataGenerator.generate_volume_series(prices)
        data[symbol] = {"prices": prices, "dates": dates, "volumes": volumes}

    return data


@pytest.fixture
def edge_case_data():
    """Fixture providing edge case data for testing robustness"""
    return {
        "empty_prices": ([], []),
        "single_price": ([100.0], [datetime.now()]),
        "constant_prices": ([100.0] * 50, [datetime.now() for _ in range(50)]),
        "negative_prices": ([-10.0, -5.0, -1.0], [datetime.now() for _ in range(3)]),
        "extreme_volatility": MockDataGenerator.generate_price_series(
            days=100, volatility=0.5, seed=999
        ),
    }
