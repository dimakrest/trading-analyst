"""
Regression tests for race condition in sync_price_data.

Bug: Concurrent calls to sync_price_data for the same symbol cause duplicate key errors
     because of non-atomic SELECT-then-INSERT pattern.
Fix: Use PostgreSQL UPSERT with ON CONFLICT DO UPDATE.

NOTE: The race condition is timing-dependent and may not trigger reliably in test environments.
These tests verify the expected UPSERT behavior that the fix will provide:
1. Concurrent syncs should not cause errors
2. Duplicate inserts should update existing records instead of failing
3. Direct INSERT of duplicates should be handled gracefully
"""

import asyncio
import copy
from datetime import datetime, timezone
from typing import Callable

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.stock_price import StockPriceRepository


@pytest_asyncio.fixture(autouse=True)
async def clean_stock_prices(test_session_factory):
    """Clean stock_prices before each test to prevent data leakage."""
    async with test_session_factory() as session:
        await session.execute(text("DELETE FROM stock_prices"))
        await session.commit()
    yield


@pytest.fixture
async def price_repo(
    db_session: AsyncSession,
) -> StockPriceRepository:
    """Create a StockPriceRepository instance."""
    return StockPriceRepository(db_session)


@pytest.fixture
def sample_price_data() -> list[dict]:
    """Sample price data for testing concurrent inserts."""
    return [
        {
            "symbol": "TEST_ETF",
            "timestamp": datetime(2025, 6, 23, 4, 0, 0, tzinfo=timezone.utc),
            "interval": "1d",
            "open_price": 100.0,
            "high_price": 105.0,
            "low_price": 99.0,
            "close_price": 104.0,
            "volume": 1000000,
            "data_source": "yahoo_finance",
        },
        {
            "symbol": "TEST_ETF",
            "timestamp": datetime(2025, 6, 24, 4, 0, 0, tzinfo=timezone.utc),
            "interval": "1d",
            "open_price": 104.0,
            "high_price": 108.0,
            "low_price": 103.0,
            "close_price": 107.0,
            "volume": 1200000,
            "data_source": "yahoo_finance",
        },
    ]


class TestSyncPriceDataRaceCondition:
    """
    REGRESSION TEST: Concurrent sync_price_data calls must not cause duplicate key errors.

    Bug: Multiple concurrent tasks calling sync_price_data for the same symbol
         all see 0 existing records and try to INSERT the same data.
    Fix: Use PostgreSQL UPSERT (ON CONFLICT DO UPDATE) instead of SELECT-then-INSERT.
    """

    @pytest.mark.asyncio
    async def test_concurrent_sync_price_data_no_duplicate_error(
        self,
        db_session: AsyncSession,
        sample_price_data: list[dict],
        test_session_factory: Callable,
    ):
        """
        Simulate race condition: 7 concurrent tasks sync same price data.

        This simulates a scenario where 7 concurrent analyses
        all need the same sector ETF data for the same date range.

        Expected behavior:
        - All 7 tasks should complete without errors
        - Database should have exactly 2 records (one per timestamp)
        - No duplicate key violations
        """
        num_concurrent_tasks = 7
        errors: list[Exception] = []

        # Use a barrier to ensure all tasks start the sync_price_data call simultaneously
        # This maximizes the chance of hitting the race condition
        barrier = asyncio.Barrier(num_concurrent_tasks)

        async def sync_task():
            """Individual task that syncs price data with its own session."""
            try:
                # Deep copy to ensure each task has completely independent data
                task_data = copy.deepcopy(sample_price_data)
                async with test_session_factory() as session:
                    repo = StockPriceRepository(session)
                    # Wait for all tasks to be ready before starting
                    await barrier.wait()
                    await repo.sync_price_data(
                        symbol="TEST_ETF",
                        new_data=task_data,
                        interval="1d",
                    )
                    await session.commit()
            except Exception as e:
                errors.append(e)

        # Run 7 concurrent tasks (simulating 7 hourly analyses)
        tasks = [asyncio.create_task(sync_task()) for _ in range(num_concurrent_tasks)]
        await asyncio.gather(*tasks, return_exceptions=True)

        # Verify no errors occurred
        assert len(errors) == 0, f"Expected no errors but got: {errors}"

        # Verify exactly 2 records exist (not 14 = 7 tasks * 2 records)
        async with test_session_factory() as session:
            repo = StockPriceRepository(session)
            records = await repo.get_price_data_by_date_range(
                symbol="TEST_ETF",
                start_date=datetime(2025, 6, 22, tzinfo=timezone.utc),
                end_date=datetime(2025, 6, 25, tzinfo=timezone.utc),
                interval="1d",
            )
            assert len(records) == 2, f"Expected 2 records but got {len(records)}"

    @pytest.mark.asyncio
    async def test_sync_price_data_updates_existing_on_conflict(
        self,
        price_repo: StockPriceRepository,
        sample_price_data: list[dict],
        db_session: AsyncSession,
    ):
        """
        Verify that conflicting inserts UPDATE existing records instead of failing.

        This tests the UPSERT behavior: when a record with the same
        (symbol, timestamp, interval) already exists, it should be updated.
        """
        # First sync - should insert 2 records
        result1 = await price_repo.sync_price_data(
            symbol="TEST_ETF",
            new_data=sample_price_data.copy(),
            interval="1d",
        )
        await db_session.commit()

        # Modify the price data (shift all prices up by 5.0 to maintain constraints)
        # The database has constraints like high_price >= close_price, so we must
        # update all price fields consistently
        modified_data = [
            {
                **d,
                "open_price": d["open_price"] + 5.0,
                "high_price": d["high_price"] + 5.0,
                "low_price": d["low_price"] + 5.0,
                "close_price": d["close_price"] + 5.0,
            }
            for d in sample_price_data
        ]

        # Second sync - should update existing records, not fail
        result2 = await price_repo.sync_price_data(
            symbol="TEST_ETF",
            new_data=modified_data,
            interval="1d",
        )
        await db_session.commit()

        # Verify records were updated
        records = await price_repo.get_price_data_by_date_range(
            symbol="TEST_ETF",
            start_date=datetime(2025, 6, 22, tzinfo=timezone.utc),
            end_date=datetime(2025, 6, 25, tzinfo=timezone.utc),
            interval="1d",
        )
        assert len(records) == 2

        # Verify close prices were updated
        for record in records:
            original = next(d for d in sample_price_data if d["timestamp"] == record.timestamp)
            assert float(record.close_price) == original["close_price"] + 5.0

    @pytest.mark.asyncio
    async def test_sync_price_data_handles_race_condition_gracefully(
        self,
        price_repo: StockPriceRepository,
        sample_price_data: list[dict],
        db_session: AsyncSession,
    ):
        """
        Verify that sync_price_data uses UPSERT to handle duplicate inserts gracefully.

        This test simulates what happens when sync_price_data is called with data
        that already exists in the database. With the UPSERT fix, this should
        update existing records instead of failing with a duplicate key error.

        OLD BEHAVIOR (BUG): sync_price_data used SELECT-then-INSERT which failed
        when concurrent tasks tried to insert the same data.

        NEW BEHAVIOR (FIX): sync_price_data uses UPSERT (ON CONFLICT DO UPDATE)
        which handles conflicts atomically at the database level.
        """
        # First, insert the data normally
        result1 = await price_repo.sync_price_data(
            symbol="TEST_ETF",
            new_data=sample_price_data.copy(),
            interval="1d",
        )
        await db_session.commit()
        assert result1["inserted"] == 2

        # Verify records were inserted
        records_before = await price_repo.get_price_data_by_date_range(
            symbol="TEST_ETF",
            start_date=datetime(2025, 6, 22, tzinfo=timezone.utc),
            end_date=datetime(2025, 6, 25, tzinfo=timezone.utc),
            interval="1d",
        )
        assert len(records_before) == 2

        # Now call sync_price_data again with the same data
        # This simulates what happens in a race condition: another task tries to
        # insert the same data. With UPSERT, this should succeed without errors.
        result2 = await price_repo.sync_price_data(
            symbol="TEST_ETF",
            new_data=sample_price_data.copy(),
            interval="1d",
        )
        await db_session.commit()

        # UPSERT reports affected rows (both inserts and updates)
        assert result2["inserted"] == 2, "UPSERT should report 2 affected rows"

        # Verify we still have exactly 2 records (not 4)
        records_after = await price_repo.get_price_data_by_date_range(
            symbol="TEST_ETF",
            start_date=datetime(2025, 6, 22, tzinfo=timezone.utc),
            end_date=datetime(2025, 6, 25, tzinfo=timezone.utc),
            interval="1d",
        )
        assert len(records_after) == 2, "Should still have exactly 2 records after re-sync"

    @pytest.mark.asyncio
    async def test_sync_price_data_updates_last_fetched_at_on_conflict(
        self,
        price_repo: StockPriceRepository,
        sample_price_data: list[dict],
        db_session: AsyncSession,
    ):
        """
        Verify that last_fetched_at is updated when records are upserted.

        This is critical for cache freshness tracking - when we re-sync data,
        last_fetched_at must be refreshed so the cache knows the data is fresh.
        """
        # First sync - insert records
        await price_repo.sync_price_data(
            symbol="TEST_ETF",
            new_data=sample_price_data.copy(),
            interval="1d",
        )
        await db_session.commit()

        # Get initial last_fetched_at values
        records_before = await price_repo.get_price_data_by_date_range(
            symbol="TEST_ETF",
            start_date=datetime(2025, 6, 22, tzinfo=timezone.utc),
            end_date=datetime(2025, 6, 25, tzinfo=timezone.utc),
            interval="1d",
        )
        initial_fetch_times = {r.timestamp: r.last_fetched_at for r in records_before}

        # Wait a bit to ensure time difference
        await asyncio.sleep(0.1)

        # Second sync - should update existing records
        await price_repo.sync_price_data(
            symbol="TEST_ETF",
            new_data=sample_price_data.copy(),
            interval="1d",
        )
        await db_session.commit()

        # Expire all cached objects to force fresh fetch from database
        # Without this, SQLAlchemy returns cached objects from identity map
        db_session.expire_all()

        # Verify last_fetched_at was updated
        records_after = await price_repo.get_price_data_by_date_range(
            symbol="TEST_ETF",
            start_date=datetime(2025, 6, 22, tzinfo=timezone.utc),
            end_date=datetime(2025, 6, 25, tzinfo=timezone.utc),
            interval="1d",
        )

        for record in records_after:
            initial_time = initial_fetch_times[record.timestamp]
            assert record.last_fetched_at > initial_time, (
                f"last_fetched_at should be updated on upsert. "
                f"Initial: {initial_time}, After: {record.last_fetched_at}"
            )
