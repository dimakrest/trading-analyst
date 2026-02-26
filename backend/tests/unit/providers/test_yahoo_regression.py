"""Regression tests for Yahoo provider timezone handling.

Tests verify that the Yahoo provider correctly normalizes timestamps to UTC,
preventing duplicate key errors when storing data with timezone-aware comparisons.
"""
from datetime import datetime
from datetime import timezone
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

from app.providers.base import PriceDataRequest
from app.providers.yahoo import YahooFinanceProvider


class TestYahooTimezoneNormalization:
    """Regression tests for Yahoo provider timezone handling."""

    @pytest.fixture
    def provider(self) -> YahooFinanceProvider:
        """Create YahooFinanceProvider instance for testing.

        Returns:
            YahooFinanceProvider: Provider instance.
        """
        return YahooFinanceProvider()

    @pytest.mark.asyncio
    async def test_transform_data_normalizes_edt_to_utc(self, provider: YahooFinanceProvider):
        """Test EDT timestamps are normalized to UTC.

        Regression: Yahoo returns America/New_York timestamps that must be
        converted to UTC before storage to prevent duplicate key errors.

        Args:
            provider: YahooFinanceProvider instance fixture.
        """

        # Simulate yfinance DataFrame with EDT timestamp (what Yahoo actually returns)
        edt = ZoneInfo("America/New_York")
        edt_timestamp = pd.Timestamp("2025-04-14 00:00:00", tz=edt)

        mock_df = pd.DataFrame(
            {
                "Open": [100.0],
                "High": [105.0],
                "Low": [99.0],
                "Close": [104.0],
                "Volume": [1000000],
            },
            index=[edt_timestamp],
        )

        request = PriceDataRequest(
            symbol="META",
            start_date=datetime(2025, 4, 1, tzinfo=timezone.utc),
            end_date=datetime(2025, 4, 30, tzinfo=timezone.utc),
            interval="1d",
        )

        result = await provider._transform_data(mock_df, request)

        # CRITICAL ASSERTION: Timestamp must be UTC, not EDT
        assert result[0].timestamp.tzinfo == timezone.utc
        # 2025-04-14 00:00:00 EDT = 2025-04-14 04:00:00 UTC
        assert result[0].timestamp == datetime(2025, 4, 14, 4, 0, 0, tzinfo=timezone.utc)

    @pytest.mark.asyncio
    async def test_transform_data_normalizes_est_to_utc(self, provider: YahooFinanceProvider):
        """Test EST timestamps are normalized to UTC.

        Regression: Winter timestamps use EST (UTC-5) not EDT (UTC-4).

        Args:
            provider: YahooFinanceProvider instance fixture.
        """
        # January is EST (not EDT)
        est = ZoneInfo("America/New_York")
        est_timestamp = pd.Timestamp("2025-01-15 00:00:00", tz=est)

        mock_df = pd.DataFrame(
            {
                "Open": [100.0],
                "High": [105.0],
                "Low": [99.0],
                "Close": [104.0],
                "Volume": [1000000],
            },
            index=[est_timestamp],
        )

        request = PriceDataRequest(
            symbol="META",
            start_date=datetime(2025, 1, 1, tzinfo=timezone.utc),
            end_date=datetime(2025, 1, 31, tzinfo=timezone.utc),
            interval="1d",
        )

        result = await provider._transform_data(mock_df, request)

        assert result[0].timestamp.tzinfo == timezone.utc
        # 2025-01-15 00:00:00 EST = 2025-01-15 05:00:00 UTC (5 hour offset in winter)
        assert result[0].timestamp == datetime(2025, 1, 15, 5, 0, 0, tzinfo=timezone.utc)

    @pytest.mark.asyncio
    async def test_transform_data_handles_naive_timestamps(self, provider: YahooFinanceProvider):
        """Test naive timestamps get UTC timezone attached.

        Args:
            provider: YahooFinanceProvider instance fixture.
        """
        # Some edge cases return naive timestamps
        naive_timestamp = pd.Timestamp("2025-04-14 00:00:00")

        mock_df = pd.DataFrame(
            {
                "Open": [100.0],
                "High": [105.0],
                "Low": [99.0],
                "Close": [104.0],
                "Volume": [1000000],
            },
            index=[naive_timestamp],
        )

        request = PriceDataRequest(
            symbol="META",
            start_date=datetime(2025, 4, 1, tzinfo=timezone.utc),
            end_date=datetime(2025, 4, 30, tzinfo=timezone.utc),
            interval="1d",
        )

        result = await provider._transform_data(mock_df, request)

        assert result[0].timestamp.tzinfo == timezone.utc
        # Naive timestamp treated as UTC, so no hour offset
        assert result[0].timestamp == datetime(2025, 4, 14, 0, 0, 0, tzinfo=timezone.utc)

    @pytest.mark.asyncio
    async def test_transform_data_preserves_already_utc_timestamps(
        self, provider: YahooFinanceProvider
    ):
        """Test already-UTC timestamps remain unchanged.

        Args:
            provider: YahooFinanceProvider instance fixture.
        """
        utc_timestamp = pd.Timestamp("2025-04-14 04:00:00", tz="UTC")

        mock_df = pd.DataFrame(
            {
                "Open": [100.0],
                "High": [105.0],
                "Low": [99.0],
                "Close": [104.0],
                "Volume": [1000000],
            },
            index=[utc_timestamp],
        )

        request = PriceDataRequest(
            symbol="META",
            start_date=datetime(2025, 4, 1, tzinfo=timezone.utc),
            end_date=datetime(2025, 4, 30, tzinfo=timezone.utc),
            interval="1d",
        )

        result = await provider._transform_data(mock_df, request)

        assert result[0].timestamp.tzinfo == timezone.utc
        assert result[0].timestamp == datetime(2025, 4, 14, 4, 0, 0, tzinfo=timezone.utc)

    @pytest.mark.asyncio
    async def test_transform_data_handles_multiple_rows(self, provider: YahooFinanceProvider):
        """Test multiple rows are all normalized to UTC.

        Args:
            provider: YahooFinanceProvider instance fixture.
        """
        edt = ZoneInfo("America/New_York")
        timestamps = [
            pd.Timestamp("2025-04-14 00:00:00", tz=edt),
            pd.Timestamp("2025-04-15 00:00:00", tz=edt),
            pd.Timestamp("2025-04-16 00:00:00", tz=edt),
        ]

        mock_df = pd.DataFrame(
            {
                "Open": [100.0, 101.0, 102.0],
                "High": [105.0, 106.0, 107.0],
                "Low": [99.0, 100.0, 101.0],
                "Close": [104.0, 105.0, 106.0],
                "Volume": [1000000, 1100000, 1200000],
            },
            index=timestamps,
        )

        request = PriceDataRequest(
            symbol="META",
            start_date=datetime(2025, 4, 1, tzinfo=timezone.utc),
            end_date=datetime(2025, 4, 30, tzinfo=timezone.utc),
            interval="1d",
        )

        result = await provider._transform_data(mock_df, request)

        assert len(result) == 3
        for point in result:
            assert point.timestamp.tzinfo == timezone.utc

        # All should be converted with 4-hour offset
        assert result[0].timestamp == datetime(2025, 4, 14, 4, 0, 0, tzinfo=timezone.utc)
        assert result[1].timestamp == datetime(2025, 4, 15, 4, 0, 0, tzinfo=timezone.utc)
        assert result[2].timestamp == datetime(2025, 4, 16, 4, 0, 0, tzinfo=timezone.utc)
