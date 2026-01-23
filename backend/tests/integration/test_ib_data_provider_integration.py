"""Integration tests for IB Data Provider.

These tests require a running IB Gateway/TWS connection on the default port (7497).
They verify real-time integration with Interactive Brokers for data fetching and validation.

Mark with @pytest.mark.skip to skip by default - run manually when IB Gateway is available.
Mark with @pytest.mark.integration to indicate these are integration tests.
Mark with @pytest.mark.external to indicate they make real API calls to IB.
"""
from datetime import datetime
from datetime import timedelta
from datetime import timezone

import pytest

from app.providers.base import PriceDataRequest
from app.providers.ib_data import IBDataProvider


@pytest.mark.skip(reason="Requires running IB Gateway - run manually")
@pytest.mark.integration
@pytest.mark.external
@pytest.mark.asyncio
class TestIBDataProviderIntegration:
    """Integration tests for IBDataProvider with real IB Gateway.

    These tests verify integration with Interactive Brokers Gateway/TWS for:
    - Real-time data fetching with various intervals
    - Symbol validation and market data
    - Proper connection lifecycle management
    """

    async def test_fetch_15min_data_for_aapl(self) -> None:
        """Test fetching 15-minute intraday data for AAPL.

        This test verifies:
        - Connection to IB Gateway succeeds
        - 15-minute price data can be fetched for a valid ticker
        - Data points are structured correctly with valid price relationships
        - Volume data is realistic (non-negative)

        Note:
            Results depend on market hours - may return 0 bars outside trading hours.
        """
        provider = IBDataProvider()

        try:
            await provider.connect()

            request = PriceDataRequest(
                symbol="AAPL",
                start_date=datetime.now(timezone.utc) - timedelta(days=1),
                end_date=datetime.now(timezone.utc),
                interval="15m",
            )

            result = await provider.fetch_price_data(request)

            # Should have some bars (depends on market hours)
            assert isinstance(result, list)
            assert len(result) >= 0

            if result:
                # Verify data structure and price relationships
                first_bar = result[0]
                assert first_bar.symbol == "AAPL"
                assert first_bar.open_price > 0
                assert first_bar.high_price >= first_bar.low_price
                assert first_bar.low_price > 0
                assert first_bar.close_price > 0
                assert first_bar.volume >= 0

        finally:
            await provider.disconnect()

    async def test_validate_symbol(self) -> None:
        """Test symbol validation and market data retrieval from IB.

        This test verifies:
        - Connection to IB Gateway succeeds
        - Valid ticker symbol (AAPL) is recognized
        - Symbol info includes required attributes (symbol, currency)
        - Currency is correct for US equities

        Raises:
            SymbolNotFoundError: If symbol is not valid in IB database (not expected here)
        """
        provider = IBDataProvider()

        try:
            await provider.connect()

            # Validate known symbol
            info = await provider.validate_symbol("AAPL")

            # Verify symbol info structure
            assert info is not None
            assert info.symbol == "AAPL"
            assert info.currency == "USD"

        finally:
            await provider.disconnect()
