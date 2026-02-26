"""Tests for trading calendar service."""
from datetime import date, datetime, timezone

import pytest

from app.services.trading_calendar_service import (
    count_trading_days_in_range,
    get_first_trading_day_on_or_after,
    get_last_complete_trading_day,
    get_market_status,
    get_next_trading_day,
    get_trading_days_in_range,
    is_trading_day,
)


@pytest.mark.unit
class TestIsTradingDay:
    """Tests for is_trading_day function."""

    def test_weekday_is_trading_day(self) -> None:
        """Regular weekday should be trading day."""
        # Wednesday, December 18, 2024
        assert is_trading_day(date(2024, 12, 18)) is True

    def test_weekend_not_trading_day(self) -> None:
        """Weekend should not be trading day."""
        # Saturday, December 21, 2024
        assert is_trading_day(date(2024, 12, 21)) is False
        # Sunday, December 22, 2024
        assert is_trading_day(date(2024, 12, 22)) is False

    def test_christmas_not_trading_day(self) -> None:
        """Christmas should not be trading day."""
        assert is_trading_day(date(2024, 12, 25)) is False

    def test_thanksgiving_not_trading_day(self) -> None:
        """Thanksgiving (4th Thursday Nov) should not be trading day."""
        # Thanksgiving 2024 is November 28
        assert is_trading_day(date(2024, 11, 28)) is False

    def test_mlk_day_not_trading_day(self) -> None:
        """MLK Day (3rd Monday Jan) should not be trading day."""
        # MLK Day 2025 is January 20
        assert is_trading_day(date(2025, 1, 20)) is False


@pytest.mark.unit
class TestGetTradingDaysInRange:
    """Tests for get_trading_days_in_range function."""

    def test_simple_range(self) -> None:
        """Get trading days in a simple range."""
        # Mon Dec 16 to Fri Dec 20, 2024 = 5 trading days
        days = get_trading_days_in_range(date(2024, 12, 16), date(2024, 12, 20))
        assert len(days) == 5
        assert all(isinstance(d, date) for d in days)

    def test_range_with_weekend(self) -> None:
        """Range spanning weekend excludes Sat/Sun."""
        # Thu Dec 19 to Mon Dec 23, 2024
        # Thu, Fri, (Sat, Sun excluded), Mon = 3 days
        days = get_trading_days_in_range(date(2024, 12, 19), date(2024, 12, 23))
        assert len(days) == 3

    def test_range_with_holiday(self) -> None:
        """Range with Christmas excludes holiday."""
        # Mon Dec 23 to Thu Dec 26, 2024
        # Mon, Tue, (Wed Dec 25 = Christmas), Thu = 3 days
        days = get_trading_days_in_range(date(2024, 12, 23), date(2024, 12, 26))
        assert len(days) == 3
        assert date(2024, 12, 25) not in days

    def test_single_day_range(self) -> None:
        """Single day range returns that day if trading day."""
        days = get_trading_days_in_range(date(2024, 12, 18), date(2024, 12, 18))
        assert len(days) == 1
        assert days[0] == date(2024, 12, 18)

    def test_empty_range_weekend(self) -> None:
        """Weekend-only range returns empty list."""
        days = get_trading_days_in_range(date(2024, 12, 21), date(2024, 12, 22))
        assert len(days) == 0


@pytest.mark.unit
class TestCountTradingDaysInRange:
    """Tests for count_trading_days_in_range function."""

    def test_count_matches_list_length(self) -> None:
        """Count should match length of get_trading_days_in_range."""
        start = date(2024, 12, 1)
        end = date(2024, 12, 31)
        count = count_trading_days_in_range(start, end)
        days = get_trading_days_in_range(start, end)
        assert count == len(days)


@pytest.mark.unit
class TestGetMarketStatus:
    """Test market status detection."""

    def test_pre_market(self) -> None:
        """Before 9:30 AM ET on trading day should be pre_market."""
        # Tuesday 8:00 AM ET = 13:00 UTC
        timestamp = datetime(2024, 12, 3, 13, 0, tzinfo=timezone.utc)
        assert get_market_status(timestamp) == "pre_market"

    def test_market_open_at_930(self) -> None:
        """At 9:30 AM ET should be market_open."""
        # Tuesday 9:30 AM ET = 14:30 UTC
        timestamp = datetime(2024, 12, 3, 14, 30, tzinfo=timezone.utc)
        assert get_market_status(timestamp) == "market_open"

    def test_market_open_midday(self) -> None:
        """Midday on trading day should be market_open."""
        # Tuesday 12:00 PM ET = 17:00 UTC
        timestamp = datetime(2024, 12, 3, 17, 0, tzinfo=timezone.utc)
        assert get_market_status(timestamp) == "market_open"

    def test_market_open_at_close(self) -> None:
        """At 4:00 PM ET should still be market_open."""
        # Tuesday 4:00 PM ET = 21:00 UTC
        timestamp = datetime(2024, 12, 3, 21, 0, tzinfo=timezone.utc)
        assert get_market_status(timestamp) == "market_open"

    def test_after_hours(self) -> None:
        """After 4:00 PM ET should be after_hours."""
        # Tuesday 5:00 PM ET = 22:00 UTC
        timestamp = datetime(2024, 12, 3, 22, 0, tzinfo=timezone.utc)
        assert get_market_status(timestamp) == "after_hours"

    def test_closed_weekend(self) -> None:
        """Weekend should be closed."""
        # Saturday
        timestamp = datetime(2024, 12, 7, 14, 0, tzinfo=timezone.utc)
        assert get_market_status(timestamp) == "closed"

    def test_closed_holiday_new_years(self) -> None:
        """New Year's Day should be closed."""
        # New Year's Day 2025 (Wednesday)
        timestamp = datetime(2025, 1, 1, 14, 30, tzinfo=timezone.utc)
        assert get_market_status(timestamp) == "closed"

    def test_closed_holiday_mlk_day(self) -> None:
        """MLK Day should be closed."""
        # MLK Day 2025 (3rd Monday in January = Jan 20)
        timestamp = datetime(2025, 1, 20, 14, 30, tzinfo=timezone.utc)
        assert get_market_status(timestamp) == "closed"

    def test_closed_holiday_thanksgiving(self) -> None:
        """Thanksgiving should be closed."""
        # Thanksgiving 2024 (4th Thursday in November = Nov 28)
        timestamp = datetime(2024, 11, 28, 14, 30, tzinfo=timezone.utc)
        assert get_market_status(timestamp) == "closed"

    def test_after_hours_early_close_day(self) -> None:
        """After 1:00 PM ET on early close day (day after Thanksgiving) should be after_hours."""
        # Nov 29, 2024 (day after Thanksgiving) at 2:00 PM ET = 19:00 UTC
        # Market closes at 1:00 PM ET on this day
        timestamp = datetime(2024, 11, 29, 19, 0, tzinfo=timezone.utc)
        assert get_market_status(timestamp) == "after_hours"

    def test_market_open_early_close_day(self) -> None:
        """At 12:00 PM ET on early close day should be market_open."""
        # Nov 29, 2024 (day after Thanksgiving) at 12:00 PM ET = 17:00 UTC
        # Market is still open (closes at 1:00 PM ET)
        timestamp = datetime(2024, 11, 29, 17, 0, tzinfo=timezone.utc)
        assert get_market_status(timestamp) == "market_open"


@pytest.mark.unit
class TestGetLastCompleteTradingDay:
    """Test last complete trading day calculation."""

    def test_after_hours_returns_today(self) -> None:
        """After hours should return today."""
        # Tuesday 5:00 PM ET
        timestamp = datetime(2024, 12, 3, 22, 0, tzinfo=timezone.utc)
        assert get_last_complete_trading_day(timestamp) == date(2024, 12, 3)

    def test_pre_market_returns_previous_day(self) -> None:
        """Pre market should return previous trading day."""
        # Tuesday 8:00 AM ET -> Monday Dec 2
        timestamp = datetime(2024, 12, 3, 13, 0, tzinfo=timezone.utc)
        assert get_last_complete_trading_day(timestamp) == date(2024, 12, 2)

    def test_market_open_returns_previous_day(self) -> None:
        """During market hours should return previous trading day."""
        # Tuesday 11:00 AM ET -> Monday Dec 2
        timestamp = datetime(2024, 12, 3, 16, 0, tzinfo=timezone.utc)
        assert get_last_complete_trading_day(timestamp) == date(2024, 12, 2)

    def test_weekend_returns_friday(self) -> None:
        """Weekend should return Friday."""
        # Saturday Dec 7 -> Friday Dec 6
        timestamp = datetime(2024, 12, 7, 16, 0, tzinfo=timezone.utc)
        assert get_last_complete_trading_day(timestamp) == date(2024, 12, 6)

    def test_monday_pre_market_returns_friday(self) -> None:
        """Monday pre-market should return Friday."""
        # Monday 8:00 AM ET -> Friday
        timestamp = datetime(2024, 12, 9, 13, 0, tzinfo=timezone.utc)
        assert get_last_complete_trading_day(timestamp) == date(2024, 12, 6)


@pytest.mark.unit
class TestGetNextTradingDay:
    """Test next trading day calculation."""

    def test_weekday_to_weekday(self) -> None:
        """Weekday should return next weekday."""
        # Monday -> Tuesday
        assert get_next_trading_day(date(2024, 12, 2)) == date(2024, 12, 3)

    def test_friday_to_monday(self) -> None:
        """Friday should skip weekend to Monday."""
        # Friday -> Monday (skips weekend)
        assert get_next_trading_day(date(2024, 12, 6)) == date(2024, 12, 9)

    def test_day_before_holiday(self) -> None:
        """Day before holiday should skip holiday."""
        # Dec 31, 2024 -> Jan 2, 2025 (skips New Year's)
        assert get_next_trading_day(date(2024, 12, 31)) == date(2025, 1, 2)


@pytest.mark.unit
class TestGetFirstTradingDayOnOrAfter:
    """Test first trading day on or after calculation."""

    def test_trading_day_returns_same(self) -> None:
        """Trading day should return itself."""
        # Monday is trading day -> return Monday
        assert get_first_trading_day_on_or_after(date(2024, 12, 2)) == date(2024, 12, 2)

    def test_weekend_returns_monday(self) -> None:
        """Saturday should return Monday."""
        # Saturday -> Monday
        assert get_first_trading_day_on_or_after(date(2024, 12, 7)) == date(2024, 12, 9)

    def test_sunday_returns_monday(self) -> None:
        """Sunday should return Monday."""
        # Sunday -> Monday
        assert get_first_trading_day_on_or_after(date(2024, 12, 8)) == date(2024, 12, 9)

    def test_new_years_returns_jan_2(self) -> None:
        """New Year's Day should return next trading day."""
        # New Year's Day 2025 (Wed) -> Jan 2
        assert get_first_trading_day_on_or_after(date(2025, 1, 1)) == date(2025, 1, 2)

    def test_christmas_returns_dec_26(self) -> None:
        """Christmas should return next trading day."""
        # Christmas 2024 (Wed) -> Dec 26
        assert get_first_trading_day_on_or_after(date(2024, 12, 25)) == date(2024, 12, 26)

    def test_mlk_day_returns_next_day(self) -> None:
        """MLK Day should return next trading day."""
        # MLK Day 2025 (Jan 20, Monday) -> Jan 21
        assert get_first_trading_day_on_or_after(date(2025, 1, 20)) == date(2025, 1, 21)

    def test_thanksgiving_returns_friday(self) -> None:
        """Thanksgiving should return next trading day (Friday)."""
        # Thanksgiving 2024 (Nov 28, Thursday) -> Nov 29 (Friday, market open)
        assert get_first_trading_day_on_or_after(date(2024, 11, 28)) == date(2024, 11, 29)
