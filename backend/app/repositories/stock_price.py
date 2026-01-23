"""StockPrice repository for time-series financial data operations.

This repository provides specialized queries for financial time-series data
including OHLCV operations, technical analysis support, and bulk data handling
optimized for high-volume financial data operations.
"""
import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import and_
from sqlalchemy import asc
from sqlalchemy import desc
from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy import update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.stock import StockPrice
from app.repositories.base import BaseRepository
from app.repositories.base import DatabaseError

logger = logging.getLogger(__name__)


class StockPriceRepository(BaseRepository[StockPrice]):
    """Repository for StockPrice model with time-series and financial data optimizations.

    Provides specialized methods for:
    - Time-series queries optimized for financial data
    - OHLCV data retrieval and filtering
    - Technical analysis support operations
    - Bulk data operations for data feeds
    - Date range and symbol-based filtering
    - Performance optimizations for high-volume data
    """

    def __init__(self, session: AsyncSession):
        """Initialize repository with StockPrice model."""
        super().__init__(StockPrice, session)

    # ===== TIME-SERIES QUERIES =====

    async def get_price_data_by_date_range(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime,
        interval: str = "1d",
        include_extended_hours: bool = False,
    ) -> list[StockPrice]:
        """Get price data for a symbol within a date range.

        Args:
            symbol: Stock symbol (e.g., 'AAPL')
            start_date: Start date for data retrieval
            end_date: End date for data retrieval
            interval: Data interval ('1d', '1h', '5m', etc.)
            include_extended_hours: Include extended trading hours data

        Returns:
            List of StockPrice records ordered by timestamp

        Raises:
            DatabaseError: If database operation fails
        """
        try:
            query = (
                select(self.model)
                .where(
                    and_(
                        self.model.symbol == symbol.upper(),
                        self.model.interval == interval,
                        self.model.timestamp >= start_date,
                        self.model.timestamp <= end_date,
                    )
                )
                .order_by(asc(self.model.timestamp))
            )

            result = await self.session.execute(query)
            price_data = result.scalars().all()

            self.logger.debug(
                f"Retrieved {len(price_data)} price records for {symbol} "
                f"from {start_date} to {end_date} with interval {interval}"
            )

            return list(price_data)

        except SQLAlchemyError as e:
            self.logger.error(f"Failed to get price data for {symbol}: {e}")
            raise DatabaseError(f"Database error retrieving price data: {str(e)}")

    async def get_latest_prices(
        self, symbols: list[str], interval: str = "1d", limit_per_symbol: int = 1
    ) -> dict[str, list[StockPrice]]:
        """Get the latest price data for multiple symbols.

        Args:
            symbols: List of stock symbols
            interval: Data interval
            limit_per_symbol: Number of latest records per symbol

        Returns:
            Dictionary mapping symbol to list of latest price records

        Raises:
            DatabaseError: If database operation fails
        """
        if not symbols:
            return {}

        try:
            # Subquery with row numbers using window function
            ranked_query = (
                select(
                    self.model,
                    func.row_number()
                    .over(partition_by=self.model.symbol, order_by=desc(self.model.timestamp))
                    .label("rn"),
                )
                .where(
                    and_(
                        self.model.symbol.in_([s.upper() for s in symbols]),
                        self.model.interval == interval,
                    )
                )
                .subquery()
            )

            # Main query to get latest records
            query = (
                select(ranked_query)
                .where(ranked_query.c.rn <= limit_per_symbol)
                .order_by(ranked_query.c.symbol, desc(ranked_query.c.timestamp))
            )

            result = await self.session.execute(query)
            rows = result.all()

            # Group results by symbol
            prices_by_symbol = {}
            for row in rows:
                symbol = row.symbol

                # Create StockPrice object
                price_record = StockPrice()
                for column in self.model.__table__.columns:
                    setattr(price_record, column.name, getattr(row, column.name))

                if symbol not in prices_by_symbol:
                    prices_by_symbol[symbol] = []
                prices_by_symbol[symbol].append(price_record)

            self.logger.debug(f"Retrieved latest prices for {len(prices_by_symbol)} symbols")
            return prices_by_symbol

        except SQLAlchemyError as e:
            self.logger.error(f"Failed to get latest prices: {e}")
            raise DatabaseError(f"Database error retrieving latest prices: {str(e)}")

    async def get_historical_data_with_intervals(
        self, symbol: str, intervals: list[str], lookback_days: int = 30
    ) -> dict[str, list[StockPrice]]:
        """Get historical data for multiple intervals.

        Args:
            symbol: Stock symbol
            intervals: List of intervals to retrieve
            lookback_days: Number of days to look back

        Returns:
            Dictionary mapping interval to list of price records

        Raises:
            DatabaseError: If database operation fails
        """
        try:
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=lookback_days)

            query = (
                select(self.model)
                .where(
                    and_(
                        self.model.symbol == symbol.upper(),
                        self.model.interval.in_(intervals),
                        self.model.timestamp >= cutoff_date,
                    )
                )
                .order_by(asc(self.model.interval), asc(self.model.timestamp))
            )

            result = await self.session.execute(query)
            all_data = result.scalars().all()

            # Group by interval
            data_by_interval = {interval: [] for interval in intervals}
            for record in all_data:
                if record.interval in data_by_interval:
                    data_by_interval[record.interval].append(record)

            self.logger.debug(
                f"Retrieved historical data for {symbol} across {len(intervals)} intervals"
            )

            return data_by_interval

        except SQLAlchemyError as e:
            self.logger.error(f"Failed to get historical data for {symbol}: {e}")
            raise DatabaseError(f"Database error retrieving historical data: {str(e)}")

    async def get_price_data_around_event(
        self,
        symbol: str,
        event_date: datetime,
        days_before: int = 10,
        days_after: int = 10,
        interval: str = "1d",
    ) -> list[StockPrice]:
        """Get price data around a specific event date.

        Args:
            symbol: Stock symbol
            event_date: Date of the event
            days_before: Number of trading days before event
            days_after: Number of trading days after event
            interval: Data interval

        Returns:
            List of StockPrice records around the event

        Raises:
            DatabaseError: If database operation fails
        """
        try:
            start_date = event_date - timedelta(days=days_before + 5)  # Buffer for weekends
            end_date = event_date + timedelta(days=days_after + 5)

            query = (
                select(self.model)
                .where(
                    and_(
                        self.model.symbol == symbol.upper(),
                        self.model.interval == interval,
                        self.model.timestamp >= start_date,
                        self.model.timestamp <= end_date,
                    )
                )
                .order_by(asc(self.model.timestamp))
            )

            result = await self.session.execute(query)
            price_data = result.scalars().all()

            self.logger.debug(
                f"Retrieved {len(price_data)} records around event date {event_date} for {symbol}"
            )

            return list(price_data)

        except SQLAlchemyError as e:
            self.logger.error(f"Failed to get event data for {symbol}: {e}")
            raise DatabaseError(f"Database error retrieving event data: {str(e)}")

    # ===== TECHNICAL ANALYSIS SUPPORT =====

    async def get_ohlcv_data(
        self, symbol: str, start_date: datetime, end_date: datetime, interval: str = "1d"
    ) -> list[dict[str, Any]]:
        """Get OHLCV data formatted for technical analysis libraries.

        Args:
            symbol: Stock symbol
            start_date: Start date
            end_date: End date
            interval: Data interval

        Returns:
            List of OHLCV dictionaries

        Raises:
            DatabaseError: If database operation fails
        """
        try:
            price_data = await self.get_price_data_by_date_range(
                symbol, start_date, end_date, interval
            )

            ohlcv_data = [record.to_ohlcv_dict() for record in price_data]

            self.logger.debug(f"Converted {len(ohlcv_data)} records to OHLCV format for {symbol}")
            return ohlcv_data

        except Exception as e:
            self.logger.error(f"Failed to get OHLCV data for {symbol}: {e}")
            raise DatabaseError(f"Error retrieving OHLCV data: {str(e)}")

    async def calculate_price_changes(
        self, symbol: str, interval: str = "1d", days_back: int = 30
    ) -> list[StockPrice]:
        """Calculate and update price changes for recent data.

        Args:
            symbol: Stock symbol
            interval: Data interval
            days_back: Number of days to calculate changes for

        Returns:
            List of updated StockPrice records

        Raises:
            DatabaseError: If database operation fails
        """
        try:
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_back)

            # Get data ordered by timestamp
            query = (
                select(self.model)
                .where(
                    and_(
                        self.model.symbol == symbol.upper(),
                        self.model.interval == interval,
                        self.model.timestamp >= cutoff_date,
                    )
                )
                .order_by(asc(self.model.timestamp))
            )

            result = await self.session.execute(query)
            price_records = result.scalars().all()

            # Calculate changes
            updated_records = []
            for i, record in enumerate(price_records):
                if i > 0:
                    prev_record = price_records[i - 1]
                    price_change = record.close_price - prev_record.close_price
                    price_change_percent = (price_change / prev_record.close_price) * 100

                    record.price_change = price_change
                    record.price_change_percent = price_change_percent
                    updated_records.append(record)

            await self.session.flush()

            self.logger.info(f"Calculated price changes for {len(updated_records)} records")
            return updated_records

        except SQLAlchemyError as e:
            self.logger.error(f"Failed to calculate price changes for {symbol}: {e}")
            raise DatabaseError(f"Database error calculating price changes: {str(e)}")

    async def get_volume_weighted_average_price(
        self, symbol: str, start_date: datetime, end_date: datetime, interval: str = "1d"
    ) -> Decimal | None:
        """Calculate volume-weighted average price (VWAP) for a period.

        Args:
            symbol: Stock symbol
            start_date: Start date
            end_date: End date
            interval: Data interval

        Returns:
            VWAP as Decimal or None if no data

        Raises:
            DatabaseError: If database operation fails
        """
        try:
            query = select(
                func.sum(self.model.close_price * self.model.volume).label("weighted_price"),
                func.sum(self.model.volume).label("total_volume"),
            ).where(
                and_(
                    self.model.symbol == symbol.upper(),
                    self.model.interval == interval,
                    self.model.timestamp >= start_date,
                    self.model.timestamp <= end_date,
                    self.model.volume > 0,
                )
            )

            result = await self.session.execute(query)
            row = result.first()

            if row and row.total_volume and row.total_volume > 0:
                vwap = Decimal(str(row.weighted_price / row.total_volume))
                self.logger.debug(f"Calculated VWAP for {symbol}: {vwap}")
                return vwap

            return None

        except SQLAlchemyError as e:
            self.logger.error(f"Failed to calculate VWAP for {symbol}: {e}")
            raise DatabaseError(f"Database error calculating VWAP: {str(e)}")

    async def get_price_extremes(
        self, symbol: str, days_back: int = 252, interval: str = "1d"  # 1 year of trading days
    ) -> dict[str, Any]:
        """Get price extremes (highs and lows) for a symbol.

        Args:
            symbol: Stock symbol
            days_back: Number of days to look back
            interval: Data interval

        Returns:
            Dictionary with price extremes and dates

        Raises:
            DatabaseError: If database operation fails
        """
        try:
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_back)

            query = select(
                func.max(self.model.high_price).label("max_high"),
                func.min(self.model.low_price).label("min_low"),
                func.avg(self.model.close_price).label("avg_close"),
                func.avg(self.model.volume).label("avg_volume"),
            ).where(
                and_(
                    self.model.symbol == symbol.upper(),
                    self.model.interval == interval,
                    self.model.timestamp >= cutoff_date,
                )
            )

            result = await self.session.execute(query)
            row = result.first()

            # Get the dates of extremes
            max_high_query = (
                select(self.model.timestamp, self.model.high_price)
                .where(
                    and_(
                        self.model.symbol == symbol.upper(),
                        self.model.interval == interval,
                        self.model.timestamp >= cutoff_date,
                        self.model.high_price == row.max_high,
                    )
                )
                .order_by(desc(self.model.timestamp))
                .limit(1)
            )

            min_low_query = (
                select(self.model.timestamp, self.model.low_price)
                .where(
                    and_(
                        self.model.symbol == symbol.upper(),
                        self.model.interval == interval,
                        self.model.timestamp >= cutoff_date,
                        self.model.low_price == row.min_low,
                    )
                )
                .order_by(desc(self.model.timestamp))
                .limit(1)
            )

            max_result = await self.session.execute(max_high_query)
            min_result = await self.session.execute(min_low_query)

            max_row = max_result.first()
            min_row = min_result.first()

            extremes = {
                "max_high": row.max_high,
                "max_high_date": max_row.timestamp if max_row else None,
                "min_low": row.min_low,
                "min_low_date": min_row.timestamp if min_row else None,
                "avg_close": row.avg_close,
                "avg_volume": row.avg_volume,
                "period_days": days_back,
            }

            self.logger.debug(f"Retrieved price extremes for {symbol}: {extremes}")
            return extremes

        except SQLAlchemyError as e:
            self.logger.error(f"Failed to get price extremes for {symbol}: {e}")
            raise DatabaseError(f"Database error retrieving price extremes: {str(e)}")

    # ===== BULK DATA OPERATIONS =====

    async def bulk_insert_price_data(
        self,
        price_data_list: list[dict[str, Any]],
        batch_size: int = 1000,
        skip_duplicates: bool = True,
    ) -> int:
        """Bulk insert price data efficiently.

        Args:
            price_data_list: List of price data dictionaries
            batch_size: Number of records per batch
            skip_duplicates: Skip duplicate entries (based on unique constraint)

        Returns:
            Number of successfully inserted records

        Raises:
            DatabaseError: If database operation fails
        """
        if not price_data_list:
            return 0

        try:
            total_inserted = 0

            # Process in batches
            for i in range(0, len(price_data_list), batch_size):
                batch = price_data_list[i : i + batch_size]

                if skip_duplicates:
                    # Use upsert for each batch
                    inserted_count = await self.bulk_upsert(
                        batch,
                        conflict_fields=["symbol", "timestamp", "interval"],
                        update_fields=["close_price", "volume", "updated_at"],
                    )
                    total_inserted += inserted_count
                else:
                    # Regular batch insert
                    created_records = await self.create_many(batch)
                    total_inserted += len(created_records)

                self.logger.debug(
                    f"Processed batch {i//batch_size + 1}, inserted {len(batch)} records"
                )

            self.logger.info(f"Bulk inserted {total_inserted} price records")
            return total_inserted

        except Exception as e:
            self.logger.error(f"Failed bulk insert of price data: {e}")
            raise DatabaseError(f"Database error in bulk insert: {str(e)}")

    async def bulk_update_technical_indicators(
        self, symbol: str, updates: list[dict[str, Any]], interval: str = "1d"
    ) -> int:
        """Bulk update technical indicators for existing price data.

        Args:
            symbol: Stock symbol
            updates: List of update dictionaries with timestamp and indicator values
            interval: Data interval

        Returns:
            Number of updated records

        Raises:
            DatabaseError: If database operation fails
        """
        try:
            updated_count = 0

            for update_data in updates:
                if "timestamp" not in update_data:
                    continue

                timestamp = update_data.pop("timestamp")

                # Find matching record
                query = select(self.model).where(
                    and_(
                        self.model.symbol == symbol.upper(),
                        self.model.timestamp == timestamp,
                        self.model.interval == interval,
                    )
                )

                result = await self.session.execute(query)
                record = result.scalar_one_or_none()

                if record:
                    # Update technical indicator fields
                    for field, value in update_data.items():
                        if hasattr(record, field):
                            setattr(record, field, value)

                    updated_count += 1

            await self.session.flush()

            self.logger.info(f"Updated technical indicators for {updated_count} records")
            return updated_count

        except SQLAlchemyError as e:
            self.logger.error(f"Failed to bulk update technical indicators: {e}")
            raise DatabaseError(f"Database error updating indicators: {str(e)}")

    async def upsert_many(
        self,
        data: list[dict[str, Any]],
    ) -> int:
        """
        Insert or update multiple stock price records atomically.

        Uses PostgreSQL's INSERT ... ON CONFLICT DO UPDATE to handle
        concurrent inserts without race conditions.

        Args:
            data: List of price data dictionaries with keys matching StockPrice model

        Returns:
            Number of affected rows

        Raises:
            DatabaseError: If database operation fails
        """
        if not data:
            return 0

        try:
            # Build INSERT statement
            stmt = insert(self.model).values(data)

            # Define columns to update on conflict (all price/volume columns + metadata)
            update_columns = {
                "open_price": stmt.excluded.open_price,
                "high_price": stmt.excluded.high_price,
                "low_price": stmt.excluded.low_price,
                "close_price": stmt.excluded.close_price,
                "volume": stmt.excluded.volume,
                "data_source": stmt.excluded.data_source,
                "updated_at": stmt.excluded.updated_at,
                "last_fetched_at": stmt.excluded.last_fetched_at,
            }

            # Add ON CONFLICT clause targeting the unique constraint
            stmt = stmt.on_conflict_do_update(
                index_elements=["symbol", "timestamp", "interval"],
                set_=update_columns,
            )

            result = await self.session.execute(stmt)
            affected_rows = result.rowcount

            self.logger.debug(f"Upserted {affected_rows} {self.model.__name__} records")
            return affected_rows

        except SQLAlchemyError as e:
            await self.session.rollback()
            self.logger.error(f"Failed to upsert {self.model.__name__} batch: {e}")
            raise DatabaseError(
                f"Database error upserting {self.model.__name__} batch: {str(e)}"
            )

    async def sync_price_data(
        self, symbol: str, new_data: list[dict[str, Any]], interval: str = "1d"
    ) -> dict[str, int]:
        """Synchronize price data for a symbol (insert new, update existing).

        Uses PostgreSQL UPSERT to handle concurrent syncs atomically.

        Args:
            symbol: Stock symbol
            new_data: List of new price data
            interval: Data interval

        Returns:
            Dictionary with counts of affected records

        Raises:
            DatabaseError: If database operation fails
        """
        try:
            if not new_data:
                return {"inserted": 0, "updated": 0}

            # Normalize data: ensure symbol is uppercase and interval is set
            normalized_data = []
            for data in new_data:
                record = {**data}
                record["symbol"] = symbol.upper()
                record["interval"] = interval

                # Normalize timestamp to UTC if present
                ts = record.get("timestamp")
                if ts is not None and ts.tzinfo is not None:
                    record["timestamp"] = ts.astimezone(timezone.utc)
                elif ts is not None:
                    record["timestamp"] = ts.replace(tzinfo=timezone.utc)

                # Explicitly set updated_at and last_fetched_at for UPSERT operations
                # On INSERT: server_default=func.now() would work, but we set it explicitly
                # On UPDATE: stmt.excluded values need these to avoid NULL
                record["updated_at"] = datetime.now(timezone.utc)
                record["last_fetched_at"] = datetime.now(timezone.utc)

                normalized_data.append(record)

            # Use UPSERT to handle inserts and updates atomically
            # This prevents race conditions when multiple concurrent tasks
            # try to sync the same symbol/timestamp
            affected_rows = await self.upsert_many(normalized_data)

            # Note: We can't distinguish inserts from updates with UPSERT,
            # so we report all as "inserted" for backwards compatibility
            sync_stats = {"inserted": affected_rows, "updated": 0}

            self.logger.info(
                f"Synced price data for {symbol}: {affected_rows} records affected"
            )

            return sync_stats

        except Exception as e:
            self.logger.error(f"Failed to sync price data for {symbol}: {e}")
            raise DatabaseError(f"Database error syncing price data: {str(e)}")

    # ===== UTILITY AND OPTIMIZATION METHODS =====

    async def cleanup_old_intraday_data(
        self, days_to_keep: int = 30, intraday_intervals: list[str] = None
    ) -> int:
        """Clean up old intraday data to manage database size.

        Args:
            days_to_keep: Number of days of intraday data to keep
            intraday_intervals: List of intraday intervals to clean up

        Returns:
            Number of deleted records

        Raises:
            DatabaseError: If database operation fails
        """
        if intraday_intervals is None:
            intraday_intervals = ["1m", "2m", "5m", "15m", "30m", "60m", "90m", "1h"]

        try:
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_to_keep)

            deleted_count = await self.delete_batch(
                filters={
                    "timestamp": {"operator": "lt", "value": cutoff_date},
                    "interval": intraday_intervals,
                },
                soft_delete=False,  # Hard delete for cleanup
            )

            self.logger.info(f"Cleaned up {deleted_count} old intraday records")
            return deleted_count

        except Exception as e:
            self.logger.error(f"Failed to cleanup old intraday data: {e}")
            raise DatabaseError(f"Database error cleaning up data: {str(e)}")

    async def get_data_quality_report(
        self, symbol: str | None = None, interval: str = "1d", days_back: int = 30
    ) -> dict[str, Any]:
        """Generate data quality report for price data.

        Args:
            symbol: Specific symbol or None for all symbols
            interval: Data interval
            days_back: Number of days to analyze

        Returns:
            Data quality report dictionary

        Raises:
            DatabaseError: If database operation fails
        """
        try:
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_back)

            base_query = select(self.model).where(
                and_(self.model.interval == interval, self.model.timestamp >= cutoff_date)
            )

            if symbol:
                base_query = base_query.where(self.model.symbol == symbol.upper())

            # Get validation stats
            validated_query = base_query.where(self.model.is_validated == True)
            total_query = base_query

            total_result = await self.session.execute(
                select(func.count()).select_from(total_query.subquery())
            )
            validated_result = await self.session.execute(
                select(func.count()).select_from(validated_query.subquery())
            )

            total_records = total_result.scalar()
            validated_records = validated_result.scalar()

            # Get data source distribution
            source_query = (
                select(self.model.data_source, func.count().label("count"))
                .where(and_(self.model.interval == interval, self.model.timestamp >= cutoff_date))
                .group_by(self.model.data_source)
            )

            if symbol:
                source_query = source_query.where(self.model.symbol == symbol.upper())

            source_result = await self.session.execute(source_query)
            source_distribution = {row.data_source: row.count for row in source_result}

            quality_report = {
                "symbol": symbol,
                "interval": interval,
                "period_days": days_back,
                "total_records": total_records,
                "validated_records": validated_records,
                "validation_rate": (validated_records / total_records * 100)
                if total_records > 0
                else 0,
                "data_source_distribution": source_distribution,
                "generated_at": datetime.now(timezone.utc),
            }

            self.logger.debug(f"Generated data quality report: {quality_report}")
            return quality_report

        except SQLAlchemyError as e:
            self.logger.error(f"Failed to generate data quality report: {e}")
            raise DatabaseError(f"Database error generating quality report: {str(e)}")

    async def get_by_symbol_and_timeframe(
        self, symbol: str, start_date: datetime, end_date: datetime, interval: str = "1d"
    ) -> list[StockPrice]:
        """Get stock price data for a specific symbol and timeframe.

        This method is used by pattern detection services to get reference price data.

        Args:
            symbol: Stock symbol (e.g., 'AAPL')
            start_date: Start date for data retrieval
            end_date: End date for data retrieval
            interval: Data interval ('1d', '1h', '5m', etc.)

        Returns:
            List of StockPrice records for the symbol and timeframe

        Raises:
            DatabaseError: If database operation fails
        """
        try:
            return await self.get_price_data_by_date_range(
                symbol=symbol, start_date=start_date, end_date=end_date, interval=interval
            )

        except Exception as e:
            self.logger.error(f"Failed to get stock price reference for {symbol}: {e}")
            raise DatabaseError(f"Error retrieving stock price reference: {str(e)}")

    async def get_symbols_with_data(self, interval: str = "1d", min_records: int = 10) -> list[str]:
        """Get list of symbols that have sufficient data.

        Args:
            interval: Data interval
            min_records: Minimum number of records required

        Returns:
            List of symbols with sufficient data

        Raises:
            DatabaseError: If database operation fails
        """
        try:
            query = (
                select(self.model.symbol, func.count().label("record_count"))
                .where(self.model.interval == interval)
                .group_by(self.model.symbol)
                .having(func.count() >= min_records)
                .order_by(self.model.symbol)
            )

            result = await self.session.execute(query)
            symbols = [row.symbol for row in result]

            self.logger.debug(f"Found {len(symbols)} symbols with at least {min_records} records")
            return symbols

        except SQLAlchemyError as e:
            self.logger.error(f"Failed to get symbols with data: {e}")
            raise DatabaseError(f"Database error retrieving symbols: {str(e)}")

    # ===== CACHE OPERATIONS =====

    async def get_cached_price_data(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime,
        interval: str,
        ttl_seconds: int,
    ) -> tuple[list[StockPrice], bool]:
        """
        Get price data from cache, checking freshness.

        Returns:
            (price_data, is_fresh) where:
            - price_data: List of StockPrice records
            - is_fresh: True if all data is within TTL, False otherwise
        """
        # Query data in date range
        price_data = await self.get_price_data_by_date_range(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            interval=interval,
        )

        if not price_data:
            return ([], False)

        # Check if data is fresh (within TTL)
        now = datetime.now(timezone.utc)
        ttl_threshold = now - timedelta(seconds=ttl_seconds)

        # Check freshness of most recent fetch
        # (Assumes batch fetch updates all records together)
        latest_fetch = max(record.last_fetched_at for record in price_data)
        is_fresh = latest_fetch >= ttl_threshold

        return (price_data, is_fresh)

    async def update_last_fetched_at(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime,
        interval: str,
    ) -> int:
        """
        Update last_fetched_at timestamp for records in date range.

        Returns:
            Number of records updated
        """
        stmt = (
            update(StockPrice)
            .where(
                StockPrice.symbol == symbol.upper(),
                StockPrice.interval == interval,
                StockPrice.timestamp >= start_date,
                StockPrice.timestamp <= end_date,
            )
            .values(last_fetched_at=datetime.now(timezone.utc))
        )

        result = await self.session.execute(stmt)
        await self.session.flush()

        return result.rowcount
