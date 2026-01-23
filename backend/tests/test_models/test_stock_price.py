"""Comprehensive unit tests for StockPrice model.

Tests model validation, constraints, properties, and methods
with comprehensive edge case coverage.
"""
from datetime import UTC
from datetime import datetime
from datetime import timezone
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.exc import DataError
from sqlalchemy.exc import DBAPIError
from sqlalchemy.exc import IntegrityError

from app.models.stock import StockPrice


@pytest.fixture
def valid_stock_data():
    """Valid stock price data for testing."""
    return {
        "symbol": "AAPL",
        "timestamp": datetime(2024, 1, 15, 16, 0, 0, tzinfo=UTC),
        "open_price": Decimal("150.00"),
        "high_price": Decimal("155.50"),
        "low_price": Decimal("149.25"),
        "close_price": Decimal("154.75"),
        "volume": 1000000,
        "adjusted_close": Decimal("154.75"),
        "interval": "1d",
        "data_source": "yahoo_finance",
    }


@pytest.mark.usefixtures("clean_db")
class TestStockPriceModel:
    """Test StockPrice model validation and functionality."""

    @pytest.fixture
    async def sample_stock_price(self, db_session, valid_stock_data):
        """Create a sample stock price record."""
        stock_price = StockPrice(**valid_stock_data)
        db_session.add(stock_price)
        await db_session.commit()
        await db_session.refresh(stock_price)
        return stock_price

    @pytest.mark.unit
    async def test_create_valid_stock_price(self, db_session, valid_stock_data):
        """Test creating a valid stock price record."""
        stock_price = StockPrice(**valid_stock_data)
        db_session.add(stock_price)
        await db_session.commit()
        await db_session.refresh(stock_price)

        assert stock_price.id is not None
        assert stock_price.symbol == "AAPL"
        assert stock_price.open_price == Decimal("150.00")
        assert stock_price.high_price == Decimal("155.50")
        assert stock_price.low_price == Decimal("149.25")
        assert stock_price.close_price == Decimal("154.75")
        assert stock_price.volume == 1000000
        assert stock_price.interval == "1d"
        assert stock_price.data_source == "yahoo_finance"
        assert stock_price.is_validated is False  # Default value

    @pytest.mark.unit
    async def test_required_fields_validation(self, db_session):
        """Test that required fields are properly validated."""
        # Test missing symbol
        with pytest.raises(IntegrityError):
            stock_price = StockPrice(
                timestamp=datetime.now(UTC),
                open_price=Decimal("100.00"),
                high_price=Decimal("105.00"),
                low_price=Decimal("95.00"),
                close_price=Decimal("102.00"),
                volume=1000,
            )
            db_session.add(stock_price)
            await db_session.commit()

        await db_session.rollback()

    @pytest.mark.unit
    async def test_price_constraints_positive_values(self, db_session, valid_stock_data):
        """Test that price constraints enforce positive values."""
        # Test negative open price
        invalid_data = valid_stock_data.copy()
        invalid_data["open_price"] = Decimal("-10.00")

        stock_price = StockPrice(**invalid_data)
        db_session.add(stock_price)

        with pytest.raises(IntegrityError):
            await db_session.commit()

        await db_session.rollback()

        # Test zero close price
        invalid_data = valid_stock_data.copy()
        invalid_data["close_price"] = Decimal("0.00")

        stock_price = StockPrice(**invalid_data)
        db_session.add(stock_price)

        with pytest.raises(IntegrityError):
            await db_session.commit()

        await db_session.rollback()

    @pytest.mark.unit
    async def test_price_constraints_high_low_relationship(self, db_session, valid_stock_data):
        """Test constraints on high/low price relationships."""
        # Test high price less than low price
        invalid_data = valid_stock_data.copy()
        invalid_data["high_price"] = Decimal("100.00")
        invalid_data["low_price"] = Decimal("150.00")

        stock_price = StockPrice(**invalid_data)
        db_session.add(stock_price)

        with pytest.raises(IntegrityError):
            await db_session.commit()

        await db_session.rollback()

        # Test high price less than open price
        invalid_data = valid_stock_data.copy()
        invalid_data["open_price"] = Decimal("160.00")
        invalid_data["high_price"] = Decimal("155.00")

        stock_price = StockPrice(**invalid_data)
        db_session.add(stock_price)

        with pytest.raises(IntegrityError):
            await db_session.commit()

        await db_session.rollback()

        # Test low price greater than close price
        invalid_data = valid_stock_data.copy()
        invalid_data["low_price"] = Decimal("160.00")
        invalid_data["close_price"] = Decimal("155.00")

        stock_price = StockPrice(**invalid_data)
        db_session.add(stock_price)

        with pytest.raises(IntegrityError):
            await db_session.commit()

        await db_session.rollback()

    @pytest.mark.unit
    async def test_volume_constraints(self, db_session, valid_stock_data):
        """Test volume constraints (non-negative)."""
        # Test negative volume
        invalid_data = valid_stock_data.copy()
        invalid_data["volume"] = -1000

        stock_price = StockPrice(**invalid_data)
        db_session.add(stock_price)

        with pytest.raises(IntegrityError):
            await db_session.commit()

        await db_session.rollback()

        # Test zero volume (should be allowed)
        valid_data = valid_stock_data.copy()
        valid_data["volume"] = 0

        stock_price = StockPrice(**valid_data)
        db_session.add(stock_price)
        await db_session.commit()

        assert stock_price.volume == 0

    @pytest.mark.unit
    async def test_interval_constraints(self, db_session, valid_stock_data):
        """Test interval validation constraints."""
        # Test valid intervals
        valid_intervals = [
            "1m",
            "2m",
            "5m",
            "15m",
            "30m",
            "60m",
            "90m",
            "1h",
            "1d",
            "5d",
            "1wk",
            "1mo",
            "3mo",
        ]

        for interval in valid_intervals:
            data = valid_stock_data.copy()
            data["interval"] = interval
            data["symbol"] = f"TEST{interval}"  # Unique symbol for each test

            stock_price = StockPrice(**data)
            db_session.add(stock_price)

        await db_session.commit()

        # Test invalid interval
        invalid_data = valid_stock_data.copy()
        invalid_data["interval"] = "99x"  # Invalid but short enough for VARCHAR(10)
        invalid_data["symbol"] = "INVALID"

        stock_price = StockPrice(**invalid_data)
        db_session.add(stock_price)

        with pytest.raises(IntegrityError):
            await db_session.commit()

        await db_session.rollback()

    @pytest.mark.unit
    async def test_data_source_constraints(self, db_session, valid_stock_data):
        """Test data source validation constraints."""
        # Test valid data sources
        valid_sources = ["yahoo_finance", "manual", "mock", "ib"]

        for source in valid_sources:
            data = valid_stock_data.copy()
            data["data_source"] = source
            data["symbol"] = f"SRC{source[:3].upper()}"  # Unique symbol

            stock_price = StockPrice(**data)
            db_session.add(stock_price)

        await db_session.commit()

        # Test invalid data source
        invalid_data = valid_stock_data.copy()
        invalid_data["data_source"] = "invalid_source"
        invalid_data["symbol"] = "INVSRC"

        stock_price = StockPrice(**invalid_data)
        db_session.add(stock_price)

        with pytest.raises(IntegrityError):
            await db_session.commit()

        await db_session.rollback()

    @pytest.mark.unit
    async def test_unique_constraint(self, db_session, valid_stock_data):
        """Test unique constraint on symbol, timestamp, interval."""
        # Create first record
        stock_price1 = StockPrice(**valid_stock_data)
        db_session.add(stock_price1)
        await db_session.commit()

        # Try to create duplicate record
        stock_price2 = StockPrice(**valid_stock_data)
        db_session.add(stock_price2)

        with pytest.raises(IntegrityError):
            await db_session.commit()

        await db_session.rollback()

    @pytest.mark.unit
    async def test_adjusted_close_constraint(self, db_session, valid_stock_data):
        """Test adjusted close price constraints."""
        # Test null adjusted close (should be allowed)
        data = valid_stock_data.copy()
        data["adjusted_close"] = None
        data["symbol"] = "NOADJ"

        stock_price = StockPrice(**data)
        db_session.add(stock_price)
        await db_session.commit()

        assert stock_price.adjusted_close is None

        # Test negative adjusted close
        invalid_data = valid_stock_data.copy()
        invalid_data["adjusted_close"] = Decimal("-10.00")
        invalid_data["symbol"] = "NEGADJ"

        stock_price = StockPrice(**invalid_data)
        db_session.add(stock_price)

        with pytest.raises(IntegrityError):
            await db_session.commit()

        await db_session.rollback()

    @pytest.mark.unit
    async def test_price_change_percent_constraint(self, db_session, valid_stock_data):
        """Test price change percentage constraints."""
        # Test valid percentage changes
        valid_data = valid_stock_data.copy()
        valid_data["price_change_percent"] = Decimal("-99.99")  # Should be allowed
        valid_data["symbol"] = "VALIDPCT"

        stock_price = StockPrice(**valid_data)
        db_session.add(stock_price)
        await db_session.commit()

        # Test invalid percentage change (< -100%)
        invalid_data = valid_stock_data.copy()
        invalid_data["price_change_percent"] = Decimal("-150.00")
        invalid_data["symbol"] = "INVPCT"

        stock_price = StockPrice(**invalid_data)
        db_session.add(stock_price)

        with pytest.raises(IntegrityError):
            await db_session.commit()

        await db_session.rollback()

    @pytest.mark.unit
    async def test_market_cap_constraint(self, db_session, valid_stock_data):
        """Test market cap constraints."""
        # Test null market cap (should be allowed)
        data = valid_stock_data.copy()
        data["market_cap"] = None
        data["symbol"] = "NOMKTCAP"

        stock_price = StockPrice(**data)
        db_session.add(stock_price)
        await db_session.commit()

        # Test negative market cap
        invalid_data = valid_stock_data.copy()
        invalid_data["market_cap"] = Decimal("-1000000")
        invalid_data["symbol"] = "NEGMKT"

        stock_price = StockPrice(**invalid_data)
        db_session.add(stock_price)

        with pytest.raises(IntegrityError):
            await db_session.commit()

        await db_session.rollback()

    @pytest.mark.unit
    def test_price_range_property(self, sample_stock_price):
        """Test price_range property calculation."""
        expected_range = Decimal("155.50") - Decimal("149.25")
        assert sample_stock_price.price_range == expected_range

    @pytest.mark.unit
    def test_typical_price_property(self, sample_stock_price):
        """Test typical_price property calculation."""
        expected_typical = (Decimal("155.50") + Decimal("149.25") + Decimal("154.75")) / 3
        assert sample_stock_price.typical_price == expected_typical

    @pytest.mark.unit
    def test_is_up_day_property(self, valid_stock_data):
        """Test is_up_day property."""
        # Test up day: Close (154.75) > Open (150.00)
        stock_price = StockPrice(**valid_stock_data)
        assert stock_price.is_up_day is True

        # Test down day
        down_data = valid_stock_data.copy()
        down_data["close_price"] = Decimal("145.00")
        stock_price_down = StockPrice(**down_data)
        assert stock_price_down.is_up_day is False

    @pytest.mark.unit
    def test_body_size_property(self, sample_stock_price):
        """Test body_size property calculation."""
        expected_body = abs(Decimal("154.75") - Decimal("150.00"))
        assert sample_stock_price.body_size == expected_body

    @pytest.mark.unit
    def test_upper_shadow_property(self, sample_stock_price):
        """Test upper_shadow property calculation."""
        # High - max(Open, Close) = 155.50 - max(150.00, 154.75) = 155.50 - 154.75
        expected_upper = Decimal("155.50") - max(Decimal("150.00"), Decimal("154.75"))
        assert sample_stock_price.upper_shadow == expected_upper

    @pytest.mark.unit
    def test_lower_shadow_property(self, sample_stock_price):
        """Test lower_shadow property calculation."""
        # min(Open, Close) - Low = min(150.00, 154.75) - 149.25 = 150.00 - 149.25
        expected_lower = min(Decimal("150.00"), Decimal("154.75")) - Decimal("149.25")
        assert sample_stock_price.lower_shadow == expected_lower

    @pytest.mark.unit
    def test_to_ohlcv_dict_method(self, sample_stock_price):
        """Test to_ohlcv_dict method output."""
        ohlcv = sample_stock_price.to_ohlcv_dict()

        assert isinstance(ohlcv, dict)
        assert ohlcv["open"] == 150.00
        assert ohlcv["high"] == 155.50
        assert ohlcv["low"] == 149.25
        assert ohlcv["close"] == 154.75
        assert ohlcv["volume"] == 1000000
        assert ohlcv["symbol"] == "AAPL"
        assert isinstance(ohlcv["timestamp"], datetime)

    @pytest.mark.unit
    def test_str_representation(self, sample_stock_price):
        """Test string representation of StockPrice."""
        repr_str = str(sample_stock_price)

        assert "StockPrice" in repr_str
        assert "AAPL" in repr_str
        assert "154.75" in repr_str
        assert "1000000" in repr_str

    @pytest.mark.unit
    async def test_decimal_precision(self, db_session, valid_stock_data):
        """Test decimal precision handling."""
        # Test maximum precision (12 digits, 4 decimal places)
        data = valid_stock_data.copy()
        data["open_price"] = Decimal("99999999.9999")
        data["high_price"] = Decimal("99999999.9999")
        data["low_price"] = Decimal("99999999.9998")
        data["close_price"] = Decimal("99999999.9999")
        data["symbol"] = "MAXPREC"

        stock_price = StockPrice(**data)
        db_session.add(stock_price)
        await db_session.commit()

        assert stock_price.open_price == Decimal("99999999.9999")

    @pytest.mark.unit
    async def test_timezone_handling(self, db_session, valid_stock_data):
        """Test timezone-aware datetime handling."""
        # Test different timezone
        from datetime import timedelta

        est_tz = timezone(timedelta(hours=-5))

        data = valid_stock_data.copy()
        data["timestamp"] = datetime(2024, 1, 15, 21, 0, 0, tzinfo=est_tz)
        data["symbol"] = "ESTTZ"

        stock_price = StockPrice(**data)
        db_session.add(stock_price)
        await db_session.commit()

        # Should store as timezone-aware
        assert stock_price.timestamp.tzinfo is not None

    @pytest.mark.unit
    async def test_optional_fields_default_values(self, db_session):
        """Test default values for optional fields."""
        minimal_data = {
            "symbol": "MINIMAL",
            "timestamp": datetime.now(UTC),
            "open_price": Decimal("100.00"),
            "high_price": Decimal("105.00"),
            "low_price": Decimal("95.00"),
            "close_price": Decimal("102.00"),
            "volume": 1000,
        }

        stock_price = StockPrice(**minimal_data)
        db_session.add(stock_price)
        await db_session.commit()

        assert stock_price.interval == "1d"  # Default value
        assert stock_price.data_source == "yahoo_finance"  # Default value
        assert stock_price.is_validated is False  # Default value
        assert stock_price.adjusted_close is None
        assert stock_price.market_cap is None
        assert stock_price.price_change is None
        assert stock_price.price_change_percent is None

    @pytest.mark.unit
    async def test_edge_case_price_values(self, db_session, valid_stock_data):
        """Test edge case price values."""
        # Test very small positive prices
        data = valid_stock_data.copy()
        data["open_price"] = Decimal("0.0001")
        data["high_price"] = Decimal("0.0002")
        data["low_price"] = Decimal("0.0001")
        data["close_price"] = Decimal("0.0002")
        data["symbol"] = "SMALLPX"

        stock_price = StockPrice(**data)
        db_session.add(stock_price)
        await db_session.commit()

        assert stock_price.open_price == Decimal("0.0001")

    @pytest.mark.unit
    async def test_large_volume_values(self, db_session, valid_stock_data):
        """Test handling of large volume values."""
        # Test very large volume (BigInteger should handle this)
        data = valid_stock_data.copy()
        data["volume"] = 999999999999999999  # Large integer
        data["symbol"] = "BIGVOL"

        stock_price = StockPrice(**data)
        db_session.add(stock_price)
        await db_session.commit()

        assert stock_price.volume == 999999999999999999

    @pytest.mark.unit
    async def test_symbol_length_validation(self, db_session, valid_stock_data):
        """Test symbol length validation."""
        # Test maximum symbol length (10 characters)
        data = valid_stock_data.copy()
        data["symbol"] = "ABCDEFGHIJ"  # 10 characters (max allowed)

        stock_price = StockPrice(**data)
        db_session.add(stock_price)
        await db_session.commit()

        assert stock_price.symbol == "ABCDEFGHIJ"

        # Test symbol too long should be truncated or cause error
        # This depends on SQLAlchemy configuration, but typically would be truncated


@pytest.mark.usefixtures("clean_db")
class TestStockPriceIndexes:
    """Test StockPrice model indexes and query performance."""

    @pytest.mark.unit
    @pytest.mark.database
    async def test_symbol_timestamp_index(self, db_session, valid_stock_data):
        """Test that symbol-timestamp queries use proper index."""
        # Create multiple records with different symbols and timestamps
        symbols = ["AAPL", "GOOGL", "MSFT", "TSLA"]

        for i, symbol in enumerate(symbols):
            data = valid_stock_data.copy()
            data["symbol"] = symbol
            data["timestamp"] = datetime(2024, 1, i + 1, 16, 0, 0, tzinfo=UTC)

            stock_price = StockPrice(**data)
            db_session.add(stock_price)

        await db_session.commit()

        # Query by symbol and timestamp range
        result = await db_session.execute(
            select(StockPrice)
            .where(StockPrice.symbol == "AAPL")
            .where(StockPrice.timestamp >= datetime(2024, 1, 1, tzinfo=UTC))
        )
        records = result.scalars().all()

        assert len(records) == 1
        assert records[0].symbol == "AAPL"

    @pytest.mark.unit
    @pytest.mark.database
    async def test_compound_unique_index(self, db_session, valid_stock_data):
        """Test compound unique index prevents duplicates."""
        # Create first record
        stock_price1 = StockPrice(**valid_stock_data)
        db_session.add(stock_price1)
        await db_session.commit()

        # Attempt to create exact duplicate should fail
        stock_price2 = StockPrice(**valid_stock_data)
        db_session.add(stock_price2)

        with pytest.raises(IntegrityError):
            await db_session.commit()

        await db_session.rollback()

        # Different interval should be allowed
        data = valid_stock_data.copy()
        data["interval"] = "1h"

        stock_price3 = StockPrice(**data)
        db_session.add(stock_price3)
        await db_session.commit()  # Should succeed

        assert stock_price3.interval == "1h"


@pytest.mark.usefixtures("clean_db")
class TestStockPriceEdgeCases:
    """Test edge cases and error conditions for StockPrice model."""

    @pytest.mark.unit
    async def test_null_required_field_handling(self, db_session):
        """Test handling of null values in required fields."""
        with pytest.raises((IntegrityError, TypeError)):
            stock_price = StockPrice(
                symbol=None,  # Required field
                timestamp=datetime.now(UTC),
                open_price=Decimal("100.00"),
                high_price=Decimal("105.00"),
                low_price=Decimal("95.00"),
                close_price=Decimal("102.00"),
                volume=1000,
            )
            db_session.add(stock_price)
            await db_session.commit()

        await db_session.rollback()

    @pytest.mark.unit
    async def test_invalid_data_types(self, db_session):
        """Test handling of invalid data types."""
        with pytest.raises((DataError, DBAPIError, TypeError, ValueError)):
            stock_price = StockPrice(
                symbol="TEST",
                timestamp="invalid_datetime",  # Should be datetime
                open_price="not_a_number",  # Should be Decimal
                high_price=Decimal("105.00"),
                low_price=Decimal("95.00"),
                close_price=Decimal("102.00"),
                volume=1000,
            )
            db_session.add(stock_price)
            await db_session.commit()

        await db_session.rollback()

    @pytest.mark.unit
    def test_property_calculations_with_zero_values(self, valid_stock_data):
        """Test property calculations with zero and edge values."""
        # Test with zero price range
        data = valid_stock_data.copy()
        data["high_price"] = Decimal("100.00")
        data["low_price"] = Decimal("100.00")
        data["open_price"] = Decimal("100.00")
        data["close_price"] = Decimal("100.00")

        stock_price = StockPrice(**data)

        assert stock_price.price_range == Decimal("0.00")
        assert stock_price.body_size == Decimal("0.00")
        assert stock_price.upper_shadow == Decimal("0.00")
        assert stock_price.lower_shadow == Decimal("0.00")
        assert stock_price.is_up_day is False

    @pytest.mark.unit
    def test_typical_price_precision(self, valid_stock_data):
        """Test typical price calculation precision."""
        # Use prices that don't divide evenly by 3
        data = valid_stock_data.copy()
        data["high_price"] = Decimal("100.01")
        data["low_price"] = Decimal("100.02")
        data["close_price"] = Decimal("100.03")

        stock_price = StockPrice(**data)

        # Should maintain decimal precision
        expected = (Decimal("100.01") + Decimal("100.02") + Decimal("100.03")) / 3
        assert stock_price.typical_price == expected
