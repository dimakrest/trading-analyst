"""Trading calendar service using exchange_calendars library.

This module provides NYSE trading calendar functionality for Arena simulations and Live20 analysis.
It handles trading day validation, range queries, and counting operations needed for
multi-day simulation scheduling and execution.

The service uses the exchange_calendars library for accurate NYSE calendar data,
including proper handling of weekends, holidays, and special market closures.

Key functions:
- is_trading_day: Validate if a specific date is a trading day
- get_trading_days_in_range: Get all trading days in a date range
- count_trading_days_in_range: Efficiently count trading days
- get_market_status: Get current market status (pre_market, market_open, after_hours, closed)
- get_last_complete_trading_day: Get most recent trading day with complete data
- get_next_trading_day: Get next trading day after given date
- get_first_trading_day_on_or_after: Get first trading day on or after given date

The NYSE calendar is cached using lru_cache to minimize overhead when accessed
repeatedly during simulation operations.
"""

import logging
from datetime import date, datetime, timedelta, timezone
from functools import lru_cache
from zoneinfo import ZoneInfo

import exchange_calendars as xcals

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_nyse_calendar() -> xcals.ExchangeCalendar:
    """Get NYSE calendar (cached).

    Returns:
        ExchangeCalendar: NYSE exchange calendar instance
    """
    return xcals.get_calendar("XNYS")


def get_trading_days_in_range(start_date: date, end_date: date) -> list[date]:
    """Get all valid NYSE trading days in a date range (inclusive).

    Args:
        start_date: Start date (inclusive)
        end_date: End date (inclusive)

    Returns:
        List of trading days as date objects
    """
    calendar = get_nyse_calendar()
    # exchange_calendars uses pandas Timestamps
    sessions = calendar.sessions_in_range(start_date.isoformat(), end_date.isoformat())
    return [session.date() for session in sessions]


def is_trading_day(check_date: date) -> bool:
    """Check if a date is a valid NYSE trading day.

    Args:
        check_date: Date to check

    Returns:
        True if trading day, False otherwise
    """
    calendar = get_nyse_calendar()
    return calendar.is_session(check_date.isoformat())


def count_trading_days_in_range(start_date: date, end_date: date) -> int:
    """Count trading days in a range without generating full list.

    Args:
        start_date: Start date (inclusive)
        end_date: End date (inclusive)

    Returns:
        Number of trading days
    """
    return len(get_trading_days_in_range(start_date, end_date))


def _to_eastern(timestamp: datetime) -> datetime:
    """Convert timestamp to US/Eastern timezone.

    Args:
        timestamp: The datetime to convert (will be treated as UTC if naive)

    Returns:
        Datetime converted to US/Eastern timezone
    """
    eastern = ZoneInfo("US/Eastern")
    if timestamp.tzinfo is None:
        logger.warning(
            "Naive datetime received in _to_eastern(), assuming UTC: %s", timestamp
        )
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    return timestamp.astimezone(eastern)


def get_market_status(timestamp: datetime | None = None) -> str:
    """Get current market status.

    Uses exchange_calendars to get accurate session times, including early close days
    (e.g., 1:00 PM ET close on day after Thanksgiving, Christmas Eve, July 3rd).

    Args:
        timestamp: The timestamp to check. If None, uses current time.

    Returns:
        One of: "pre_market", "market_open", "after_hours", "closed"
    """
    if timestamp is None:
        timestamp = datetime.now(timezone.utc)

    eastern_time = _to_eastern(timestamp)
    trading_date = eastern_time.date()

    if not is_trading_day(trading_date):
        return "closed"

    # Get actual session times from calendar (handles early closes)
    calendar = get_nyse_calendar()
    session_open = calendar.session_open(trading_date)
    session_close = calendar.session_close(trading_date)

    # Convert Pandas Timestamps to Python datetimes for comparison
    # session_open/close are in UTC, convert to Eastern for comparison
    market_open = _to_eastern(session_open.to_pydatetime())
    market_close = _to_eastern(session_close.to_pydatetime())

    if eastern_time < market_open:
        return "pre_market"
    if eastern_time <= market_close:
        return "market_open"
    return "after_hours"


def get_last_complete_trading_day(timestamp: datetime | None = None) -> date:
    """Get the most recent trading day that has complete data.

    Logic:
    - If after-hours: return today (today's data is complete)
    - Otherwise: return previous trading day

    Args:
        timestamp: The timestamp to check. If None, uses current time.

    Returns:
        The date of the last complete trading day.
    """
    if timestamp is None:
        timestamp = datetime.now(timezone.utc)

    eastern_time = _to_eastern(timestamp)
    current_date = eastern_time.date()

    market_status = get_market_status(timestamp)

    if market_status == "after_hours":
        return current_date

    # For pre_market, market_open, or closed: find previous trading day
    check_date = current_date - timedelta(days=1)
    while not is_trading_day(check_date):
        check_date -= timedelta(days=1)

    return check_date


def get_next_trading_day(from_date: date) -> date:
    """Get the next trading day after the given date.

    Args:
        from_date: The starting date.

    Returns:
        The next trading day after from_date.
    """
    check_date = from_date + timedelta(days=1)
    while not is_trading_day(check_date):
        check_date += timedelta(days=1)
    return check_date


def get_first_trading_day_on_or_after(from_date: date) -> date:
    """Get the first trading day on or after the given date.

    Returns from_date if it is a trading day, otherwise returns the next
    trading day. Useful for normalizing requests starting on holidays/weekends.

    Args:
        from_date: The starting date.

    Returns:
        The first trading day on or after from_date.
    """
    if is_trading_day(from_date):
        return from_date
    return get_next_trading_day(from_date)
