"""Mock data generators for testing pattern detection framework.

This module provides realistic mock stock data generators that can create
various market conditions and patterns for testing purposes.
"""
import random
from datetime import datetime
from datetime import timedelta

import numpy as np


class MockDataGenerator:
    """Generate realistic mock stock data for testing"""

    @staticmethod
    def generate_price_series(
        start_price: float = 100.0,
        days: int = 252,  # One trading year
        volatility: float = 0.02,
        trend: float = 0.0005,  # Daily trend
        seed: int | None = None,
    ) -> tuple[list[float], list[datetime]]:
        """Generate realistic price series with trend and volatility

        Args:
            start_price: Starting price
            days: Number of trading days
            volatility: Daily volatility (standard deviation)
            trend: Daily trend (mean return)
            seed: Random seed for reproducibility

        Returns:
            Tuple of (prices, dates)
        """
        if seed is not None:
            np.random.seed(seed)
            random.seed(seed)

        # Generate dates (weekdays only)
        start_date = datetime(2024, 1, 1)
        dates = []
        current_date = start_date
        while len(dates) < days:
            if current_date.weekday() < 5:  # Monday=0, Friday=4
                dates.append(current_date)
            current_date += timedelta(days=1)

        # Generate returns using geometric Brownian motion
        dt = 1.0  # Daily timestep
        returns = np.random.normal(trend, volatility, days)

        # Convert to prices
        prices = [start_price]
        for i in range(1, days):
            price = prices[-1] * (1 + returns[i])
            prices.append(max(0.01, price))  # Prevent negative prices

        return prices, dates

    @staticmethod
    def generate_ma_crossover_data(
        crossover_day: int = 100,
        crossover_type: str = "golden",  # "golden" or "death"
        signal_strength: float = 1.0,
    ) -> tuple[list[float], list[datetime]]:
        """Generate data with a clear MA crossover signal"""
        days = 250
        prices, dates = MockDataGenerator.generate_price_series(
            days=days, volatility=0.015, seed=42
        )

        # Manipulate prices around crossover to ensure clear signal
        if crossover_type == "golden":
            # Create upward momentum around crossover
            for i in range(crossover_day - 10, min(len(prices), crossover_day + 20)):
                if i < len(prices):
                    multiplier = 1 + (signal_strength * 0.002 * (i - crossover_day + 10))
                    prices[i] *= multiplier
        else:  # death cross
            # Create downward momentum around crossover
            for i in range(crossover_day - 10, min(len(prices), crossover_day + 20)):
                if i < len(prices):
                    multiplier = 1 - (signal_strength * 0.002 * (i - crossover_day + 10))
                    prices[i] *= max(0.5, multiplier)

        return prices, dates

    @staticmethod
    def generate_support_resistance_data(
        support_level: float = 95.0, resistance_level: float = 105.0, touches: int = 4
    ) -> tuple[list[float], list[datetime]]:
        """Generate data with clear support/resistance levels"""
        days = 200
        prices, dates = MockDataGenerator.generate_price_series(
            start_price=100.0, days=days, volatility=0.01, seed=123
        )

        # Add clear touches to support/resistance levels
        touch_points = np.linspace(20, days - 20, touches)
        for i, touch_day in enumerate(touch_points):
            touch_day = int(touch_day)
            if i % 2 == 0:  # Support touch
                prices[touch_day] = support_level + random.uniform(-0.5, 0.5)
            else:  # Resistance touch
                prices[touch_day] = resistance_level + random.uniform(-0.5, 0.5)

        return prices, dates

    @staticmethod
    def generate_volume_series(
        prices: list[float], avg_volume: float = 1000000, volume_volatility: float = 0.3
    ) -> list[float]:
        """Generate volume series correlated with price movements"""
        volumes = []
        prev_price = prices[0]

        for price in prices:
            # Higher volume on larger price moves
            price_change = abs(price - prev_price) / prev_price if prev_price > 0 else 0
            volume_multiplier = 1 + (price_change * 2)  # More volume on big moves

            # Add random variation
            volume = avg_volume * volume_multiplier * np.random.lognormal(0, volume_volatility)
            volumes.append(max(1000, volume))  # Minimum volume
            prev_price = price

        return volumes

    @staticmethod
    def generate_breakout_data(
        breakout_day: int = 100,
        breakout_type: str = "upward",  # "upward" or "downward"
        resistance_level: float = 105.0,
        support_level: float = 95.0,
    ) -> tuple[list[float], list[datetime]]:
        """Generate data with a clear breakout pattern"""
        days = 250
        prices, dates = MockDataGenerator.generate_price_series(
            days=days, volatility=0.008, seed=456
        )

        # Create consolidation before breakout
        consolidation_start = max(20, breakout_day - 50)
        for i in range(consolidation_start, breakout_day):
            if i < len(prices):
                # Keep prices within range
                if breakout_type == "upward":
                    prices[i] = min(prices[i], resistance_level - 0.5)
                    prices[i] = max(prices[i], support_level)
                else:
                    prices[i] = max(prices[i], support_level + 0.5)
                    prices[i] = min(prices[i], resistance_level)

        # Create breakout
        if breakout_type == "upward":
            for i in range(breakout_day, min(len(prices), breakout_day + 30)):
                if i < len(prices):
                    multiplier = 1 + (0.01 * (i - breakout_day + 1))
                    prices[i] = max(prices[i] * multiplier, resistance_level + 1.0)
        else:
            for i in range(breakout_day, min(len(prices), breakout_day + 30)):
                if i < len(prices):
                    multiplier = 1 - (0.01 * (i - breakout_day + 1))
                    prices[i] = min(prices[i] * multiplier, support_level - 1.0)

        return prices, dates

    @staticmethod
    def generate_trend_data(
        trend_type: str = "uptrend",  # "uptrend", "downtrend", "sideways"
        strength: float = 1.0,
        days: int = 200,
    ) -> tuple[list[float], list[datetime]]:
        """Generate data with a clear trend"""
        if trend_type == "uptrend":
            trend = 0.001 * strength
            volatility = 0.015
        elif trend_type == "downtrend":
            trend = -0.001 * strength
            volatility = 0.015
        else:  # sideways
            trend = 0.0
            volatility = 0.01

        return MockDataGenerator.generate_price_series(
            days=days, trend=trend, volatility=volatility, seed=789
        )

    @staticmethod
    def generate_noisy_data(
        days: int = 200, noise_level: float = 0.05
    ) -> tuple[list[float], list[datetime]]:
        """Generate very noisy data with no clear patterns"""
        return MockDataGenerator.generate_price_series(
            days=days, volatility=noise_level, trend=0.0, seed=999
        )

    @staticmethod
    def generate_realistic_stock_data(
        symbol: str = "TEST",
        days: int = 252,
        start_price: float = 100.0,
        volatility: float = 0.02,
        trend: str = "mixed",
        seed: int | None = None,
    ) -> list[dict]:
        """Generate realistic stock data in dictionary format for testing.

        Args:
            symbol: Stock symbol
            days: Number of trading days
            start_price: Starting price
            volatility: Daily volatility
            trend: Trend type ('bullish', 'bearish', 'mixed', 'sideways')
            seed: Random seed for reproducibility

        Returns:
            List of dictionaries with stock data
        """
        if seed is not None:
            np.random.seed(seed)
            random.seed(seed)

        # Set trend parameters based on type
        if trend == "bullish":
            trend_value = 0.0008
        elif trend == "bearish":
            trend_value = -0.0008
        elif trend == "sideways":
            trend_value = 0.0
            volatility *= 0.5  # Lower volatility for sideways
        else:  # mixed
            trend_value = 0.0002

        prices, dates = MockDataGenerator.generate_price_series(
            start_price=start_price, days=days, volatility=volatility, trend=trend_value, seed=seed
        )

        volumes = MockDataGenerator.generate_volume_series(prices)

        # Create dictionary format
        stock_data = []
        for i, (price, date) in enumerate(zip(prices, dates, strict=False)):
            # Create OHLC data
            high = price * (1 + random.uniform(0, volatility))
            low = price * (1 - random.uniform(0, volatility))
            open_price = prices[i - 1] if i > 0 else price

            stock_data.append(
                {
                    "symbol": symbol,
                    "date": date.isoformat(),
                    "open": str(round(open_price, 2)),
                    "high": str(round(high, 2)),
                    "low": str(round(low, 2)),
                    "close": str(round(price, 2)),
                    "volume": str(int(volumes[i])),
                }
            )

        return stock_data

    @staticmethod
    def generate_complex_market_data(
        symbol: str = "TEST",
        days: int = 300,
        start_price: float = 100.0,
        scenarios: list[dict] = None,
    ) -> list[dict]:
        """Generate complex market data with multiple scenarios.

        Args:
            symbol: Stock symbol
            days: Total number of days
            start_price: Starting price
            scenarios: List of scenario dictionaries

        Returns:
            List of dictionaries with stock data
        """
        if scenarios is None:
            scenarios = [
                {"type": "trend", "direction": "up", "duration": 100, "strength": 0.7},
                {"type": "consolidation", "duration": 50},
                {"type": "trend", "direction": "down", "duration": 150, "strength": 0.8},
            ]

        all_prices = []
        current_price = start_price

        for scenario in scenarios:
            scenario_days = scenario.get("duration", 50)

            if scenario["type"] == "trend":
                direction = scenario.get("direction", "up")
                strength = scenario.get("strength", 0.5)
                trend_value = 0.001 * strength if direction == "up" else -0.001 * strength
                volatility = 0.015
            elif scenario["type"] == "consolidation":
                trend_value = 0.0
                volatility = scenario.get("volatility", 0.01)
            else:
                trend_value = 0.0005
                volatility = 0.02

            scenario_prices, _ = MockDataGenerator.generate_price_series(
                start_price=current_price,
                days=scenario_days,
                trend=trend_value,
                volatility=volatility,
            )

            all_prices.extend(scenario_prices)
            current_price = scenario_prices[-1]

        # Trim to desired length
        all_prices = all_prices[:days]

        # Generate dates
        start_date = datetime(2024, 1, 1)
        dates = []
        current_date = start_date
        while len(dates) < len(all_prices):
            if current_date.weekday() < 5:
                dates.append(current_date)
            current_date += timedelta(days=1)

        # Create stock data format
        volumes = MockDataGenerator.generate_volume_series(all_prices)

        stock_data = []
        for i, (price, date) in enumerate(zip(all_prices, dates, strict=False)):
            high = price * 1.02
            low = price * 0.98
            open_price = all_prices[i - 1] if i > 0 else price

            stock_data.append(
                {
                    "symbol": symbol,
                    "date": date.isoformat(),
                    "open": str(round(open_price, 2)),
                    "high": str(round(high, 2)),
                    "low": str(round(low, 2)),
                    "close": str(round(price, 2)),
                    "volume": str(int(volumes[i])),
                }
            )

        return stock_data

    @staticmethod
    def generate_trending_data(
        symbol: str = "TEST", days: int = 200, direction: str = "up", volatility: float = 0.02
    ) -> list[dict]:
        """Generate trending data in dictionary format."""
        trend_value = 0.001 if direction == "up" else -0.001

        prices, dates = MockDataGenerator.generate_price_series(
            days=days, trend=trend_value, volatility=volatility
        )

        volumes = MockDataGenerator.generate_volume_series(prices)

        stock_data = []
        for i, (price, date) in enumerate(zip(prices, dates, strict=False)):
            high = price * 1.02
            low = price * 0.98
            open_price = prices[i - 1] if i > 0 else price

            stock_data.append(
                {
                    "symbol": symbol,
                    "date": date.isoformat(),
                    "open": str(round(open_price, 2)),
                    "high": str(round(high, 2)),
                    "low": str(round(low, 2)),
                    "close": str(round(price, 2)),
                    "volume": str(int(volumes[i])),
                }
            )

        return stock_data

    @staticmethod
    def generate_sideways_data(
        symbol: str = "TEST", days: int = 200, volatility: float = 0.01
    ) -> list[dict]:
        """Generate sideways/consolidating data in dictionary format."""
        return MockDataGenerator.generate_realistic_stock_data(
            symbol=symbol, days=days, volatility=volatility, trend="sideways"
        )

    @staticmethod
    def generate_conflicting_signals_data(symbol: str = "TEST", days: int = 200) -> list[dict]:
        """Generate data that might produce conflicting pattern signals."""
        # Create choppy market conditions
        prices = []
        current_price = 100.0

        for i in range(days):
            # Create alternating up/down moves to create conflicting signals
            if i % 20 < 10:  # Upward phase
                change = random.uniform(0.002, 0.008)
            else:  # Downward phase
                change = random.uniform(-0.008, -0.002)

            current_price *= 1 + change
            prices.append(current_price)

        # Generate dates
        start_date = datetime(2024, 1, 1)
        dates = []
        current_date = start_date
        while len(dates) < days:
            if current_date.weekday() < 5:
                dates.append(current_date)
            current_date += timedelta(days=1)

        volumes = MockDataGenerator.generate_volume_series(prices)

        stock_data = []
        for i, (price, date) in enumerate(zip(prices, dates, strict=False)):
            high = price * 1.015
            low = price * 0.985
            open_price = prices[i - 1] if i > 0 else price

            stock_data.append(
                {
                    "symbol": symbol,
                    "date": date.isoformat(),
                    "open": str(round(open_price, 2)),
                    "high": str(round(high, 2)),
                    "low": str(round(low, 2)),
                    "close": str(round(price, 2)),
                    "volume": str(int(volumes[i])),
                }
            )

        return stock_data
