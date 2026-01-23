"""Regression tests for StockPriceRepository sync_price_data behavior.

These tests verify the UPSERT-based sync_price_data implementation correctly
handles various edge cases including timezone normalization.

NOTE: After the UPSERT fix, sync_price_data no longer distinguishes between
inserts and updates - it uses PostgreSQL's ON CONFLICT DO UPDATE which
handles both atomically. The return value reports affected rows.
"""
import pytest
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from unittest.mock import AsyncMock, patch

from app.repositories.stock_price import StockPriceRepository


class TestSyncPriceDataTimezoneHandling:
    """Regression tests for sync_price_data timezone normalization."""

    @pytest.mark.asyncio
    async def test_sync_matches_same_moment_different_timezones(self):
        """
        REGRESSION TEST: Same moment in different timezones must be normalized.

        Verifies that timestamps are normalized to UTC before being passed
        to the UPSERT operation, ensuring consistent handling of different
        timezone representations of the same moment.
        """
        # Setup mock session
        mock_session = AsyncMock()
        repo = StockPriceRepository(mock_session)

        # New data comes in as EDT
        edt = ZoneInfo("America/New_York")
        edt_timestamp = datetime(2025, 4, 14, 0, 0, 0, tzinfo=edt)

        new_data = [{
            "symbol": "META",
            "timestamp": edt_timestamp,  # EDT, not UTC
            "interval": "1d",
            "close_price": 500.0,
        }]

        # Mock upsert_many to capture the call and verify normalization
        with patch.object(repo, 'upsert_many', new_callable=AsyncMock) as mock_upsert:
            mock_upsert.return_value = 1  # 1 affected row

            result = await repo.sync_price_data("META", new_data, "1d")

            # Verify upsert_many was called
            mock_upsert.assert_called_once()

            # Verify the timestamp was normalized to UTC
            call_args = mock_upsert.call_args[0][0]  # First positional arg (data list)
            assert len(call_args) == 1
            normalized_ts = call_args[0]["timestamp"]
            assert normalized_ts.tzinfo == timezone.utc
            # 00:00 EDT = 04:00 UTC
            assert normalized_ts.hour == 4

            # Verify result format
            assert result["inserted"] == 1  # UPSERT reports affected rows

    @pytest.mark.asyncio
    async def test_sync_inserts_genuinely_new_timestamps(self):
        """New timestamps should be upserted correctly."""
        mock_session = AsyncMock()
        repo = StockPriceRepository(mock_session)

        new_timestamp = datetime(2025, 4, 15, 4, 0, 0, tzinfo=timezone.utc)

        new_data = [{
            "symbol": "META",
            "timestamp": new_timestamp,
            "interval": "1d",
            "close_price": 510.0,
        }]

        with patch.object(repo, 'upsert_many', new_callable=AsyncMock) as mock_upsert:
            mock_upsert.return_value = 1

            result = await repo.sync_price_data("META", new_data, "1d")

            assert result["inserted"] == 1
            mock_upsert.assert_called_once()

    @pytest.mark.asyncio
    async def test_sync_handles_naive_datetime_from_db(self):
        """
        Naive datetimes in new data should be treated as UTC.

        The sync_price_data method normalizes naive datetimes by adding
        UTC timezone info before passing to UPSERT.
        """
        mock_session = AsyncMock()
        repo = StockPriceRepository(mock_session)

        # New data with naive datetime
        naive_timestamp = datetime(2025, 4, 14, 4, 0, 0)

        new_data = [{
            "symbol": "META",
            "timestamp": naive_timestamp,
            "interval": "1d",
            "close_price": 500.0,
        }]

        with patch.object(repo, 'upsert_many', new_callable=AsyncMock) as mock_upsert:
            mock_upsert.return_value = 1

            result = await repo.sync_price_data("META", new_data, "1d")

            # Verify the timestamp was normalized to UTC
            call_args = mock_upsert.call_args[0][0]
            normalized_ts = call_args[0]["timestamp"]
            assert normalized_ts.tzinfo == timezone.utc

    @pytest.mark.asyncio
    async def test_sync_handles_naive_datetime_in_new_data(self):
        """
        Naive datetimes in new data should be treated as UTC.
        """
        mock_session = AsyncMock()
        repo = StockPriceRepository(mock_session)

        # New data is naive (should be treated as UTC)
        naive_timestamp = datetime(2025, 4, 14, 4, 0, 0)

        new_data = [{
            "symbol": "META",
            "timestamp": naive_timestamp,
            "interval": "1d",
            "close_price": 500.0,
        }]

        with patch.object(repo, 'upsert_many', new_callable=AsyncMock) as mock_upsert:
            mock_upsert.return_value = 1

            result = await repo.sync_price_data("META", new_data, "1d")

            # Verify the timestamp was given UTC timezone
            call_args = mock_upsert.call_args[0][0]
            normalized_ts = call_args[0]["timestamp"]
            assert normalized_ts.tzinfo == timezone.utc
            assert normalized_ts.hour == 4  # Same hour, just with UTC tz

    @pytest.mark.asyncio
    async def test_sync_handles_empty_data(self):
        """Empty data list should return zero counts without DB query."""
        mock_session = AsyncMock()
        repo = StockPriceRepository(mock_session)

        result = await repo.sync_price_data("META", [], "1d")

        assert result == {"inserted": 0, "updated": 0}
        # Should not execute any DB query for empty data
        mock_session.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_sync_handles_data_without_timestamp(self):
        """Data without timestamp should still be passed to UPSERT."""
        mock_session = AsyncMock()
        repo = StockPriceRepository(mock_session)

        # Data missing timestamp key
        new_data = [{
            "symbol": "META",
            "interval": "1d",
            "close_price": 500.0,
        }]

        with patch.object(repo, 'upsert_many', new_callable=AsyncMock) as mock_upsert:
            mock_upsert.return_value = 1

            result = await repo.sync_price_data("META", new_data, "1d")

            assert result["inserted"] == 1
            mock_upsert.assert_called_once()
            # Verify the data was passed without timestamp modification
            call_args = mock_upsert.call_args[0][0]
            assert "timestamp" not in call_args[0] or call_args[0]["timestamp"] is None

    @pytest.mark.asyncio
    async def test_sync_handles_mixed_timezones_in_batch(self):
        """
        Test handling a batch with mixed timezone representations.

        All timestamps should be normalized to UTC before UPSERT.
        """
        mock_session = AsyncMock()
        repo = StockPriceRepository(mock_session)

        edt = ZoneInfo("America/New_York")

        # Mix of timezone representations
        new_data = [
            {
                "symbol": "META",
                "timestamp": datetime(2025, 4, 14, 0, 0, 0, tzinfo=edt),  # EDT
                "interval": "1d",
                "close_price": 500.0,
            },
            {
                "symbol": "META",
                "timestamp": datetime(2025, 4, 15, 4, 0, 0, tzinfo=timezone.utc),  # UTC
                "interval": "1d",
                "close_price": 505.0,
            },
            {
                "symbol": "META",
                "timestamp": datetime(2025, 4, 16, 4, 0, 0),  # Naive
                "interval": "1d",
                "close_price": 510.0,
            },
        ]

        with patch.object(repo, 'upsert_many', new_callable=AsyncMock) as mock_upsert:
            mock_upsert.return_value = 3

            result = await repo.sync_price_data("META", new_data, "1d")

            assert result["inserted"] == 3  # All 3 affected
            mock_upsert.assert_called_once()

            # Verify all timestamps are normalized to UTC
            call_args = mock_upsert.call_args[0][0]
            for record in call_args:
                assert record["timestamp"].tzinfo == timezone.utc

    @pytest.mark.asyncio
    async def test_sync_normalizes_symbol_to_uppercase(self):
        """Verify symbol is normalized to uppercase."""
        mock_session = AsyncMock()
        repo = StockPriceRepository(mock_session)

        new_data = [{
            "symbol": "meta",  # lowercase
            "timestamp": datetime(2025, 4, 14, 4, 0, 0, tzinfo=timezone.utc),
            "interval": "1d",
            "close_price": 500.0,
        }]

        with patch.object(repo, 'upsert_many', new_callable=AsyncMock) as mock_upsert:
            mock_upsert.return_value = 1

            await repo.sync_price_data("meta", new_data, "1d")

            call_args = mock_upsert.call_args[0][0]
            assert call_args[0]["symbol"] == "META"

    @pytest.mark.asyncio
    async def test_sync_sets_interval_from_parameter(self):
        """Verify interval is set from the method parameter."""
        mock_session = AsyncMock()
        repo = StockPriceRepository(mock_session)

        new_data = [{
            "symbol": "META",
            "timestamp": datetime(2025, 4, 14, 4, 0, 0, tzinfo=timezone.utc),
            "interval": "1h",  # Different from parameter
            "close_price": 500.0,
        }]

        with patch.object(repo, 'upsert_many', new_callable=AsyncMock) as mock_upsert:
            mock_upsert.return_value = 1

            await repo.sync_price_data("META", new_data, "1d")  # 1d parameter

            call_args = mock_upsert.call_args[0][0]
            assert call_args[0]["interval"] == "1d"  # Parameter overrides data
