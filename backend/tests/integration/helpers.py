"""Helper functions for integration tests.

This module provides utility functions for setting up test data,
making API assertions, and common test operations.
"""
from datetime import datetime
from datetime import timedelta
from typing import Any

from httpx import AsyncClient
from httpx import Response


async def assert_successful_response(
    response: Response, expected_status: int = 200, expected_keys: list[str] | None = None
) -> dict[str, Any]:
    """Assert API response is successful and contains expected data.

    Args:
        response: HTTP response object
        expected_status: Expected HTTP status code
        expected_keys: Expected keys in JSON response

    Returns:
        Parsed JSON response data

    Raises:
        AssertionError: If response doesn't meet expectations
    """
    assert (
        response.status_code == expected_status
    ), f"Expected status {expected_status}, got {response.status_code}: {response.text}"

    try:
        data = response.json()
    except Exception as e:
        raise AssertionError(f"Failed to parse JSON response: {e}") from e

    if expected_keys:
        for key in expected_keys:
            assert key in data, f"Expected key '{key}' not found in response: {list(data.keys())}"

    return data


async def assert_error_response(
    response: Response, expected_status: int, expected_error_substring: str | None = None
) -> dict[str, Any]:
    """Assert API response is an error with expected details.

    Args:
        response: HTTP response object
        expected_status: Expected HTTP error status code
        expected_error_substring: Substring expected in error message

    Returns:
        Parsed error response data

    Raises:
        AssertionError: If error response doesn't meet expectations
    """
    assert (
        response.status_code == expected_status
    ), f"Expected error status {expected_status}, got {response.status_code}"

    try:
        data = response.json()
    except Exception as e:
        raise AssertionError(f"Failed to parse error JSON response: {e}") from e

    if expected_error_substring:
        detail = data.get("detail", "")
        assert expected_error_substring.lower() in str(detail).lower(), (
            f"Expected error substring '{expected_error_substring}' "
            f"not found in detail: {detail}"
        )

    return data


def generate_test_date_range(days_back: int = 120) -> tuple[datetime, datetime]:
    """Generate consistent test date range.

    Args:
        days_back: Number of days back from now for start date

    Returns:
        Tuple of (start_date, end_date)
    """
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days_back)
    return start_date, end_date


async def wait_for_async_task(
    client: AsyncClient, task_url: str, max_wait_seconds: int = 30, poll_interval: float = 0.5
) -> dict[str, Any]:
    """Poll an async task endpoint until completion.

    Args:
        client: Async HTTP client
        task_url: URL to poll for task status
        max_wait_seconds: Maximum time to wait
        poll_interval: Seconds between polls

    Returns:
        Final task result

    Raises:
        TimeoutError: If task doesn't complete in time
        AssertionError: If task fails
    """
    import asyncio

    start_time = datetime.utcnow()
    max_duration = timedelta(seconds=max_wait_seconds)

    while True:
        response = await client.get(task_url)
        assert response.status_code == 200

        data = response.json()
        status = data.get("status")

        if status == "completed":
            return data
        elif status == "failed":
            error = data.get("error", "Unknown error")
            raise AssertionError(f"Task failed: {error}")

        # Check timeout
        if datetime.utcnow() - start_time > max_duration:
            raise TimeoutError(f"Task did not complete within {max_wait_seconds} seconds")

        await asyncio.sleep(poll_interval)


def validate_pattern_response(pattern_data: dict[str, Any]) -> None:
    """Validate pattern response structure and data types.

    Args:
        pattern_data: Pattern response dictionary

    Raises:
        AssertionError: If pattern data is invalid
    """
    required_fields = {
        "symbol": str,
        "pattern_type": str,
        "start_date": str,
        "end_date": str,
        "confidence": (int, float),
    }

    for field, expected_type in required_fields.items():
        assert field in pattern_data, f"Missing required field: {field}"
        value = pattern_data[field]
        assert isinstance(value, expected_type), (
            f"Field '{field}' has wrong type: "
            f"expected {expected_type}, got {type(value)}"
        )

    # Validate confidence range
    confidence = pattern_data["confidence"]
    assert 0.0 <= confidence <= 1.0, f"Confidence {confidence} out of range [0.0, 1.0]"

    # Validate dates if present
    if "start_date" in pattern_data and "end_date" in pattern_data:
        try:
            start = datetime.fromisoformat(pattern_data["start_date"].replace("Z", "+00:00"))
            end = datetime.fromisoformat(pattern_data["end_date"].replace("Z", "+00:00"))
            assert start <= end, f"Start date {start} is after end date {end}"
        except ValueError as e:
            raise AssertionError(f"Invalid date format: {e}") from e


async def create_test_symbol_with_data(
    client: AsyncClient, symbol: str = "TEST", days: int = 120
) -> dict[str, Any]:
    """Create a test symbol with price data via API.

    Args:
        client: Async HTTP client
        symbol: Stock symbol to create
        days: Number of days of historical data

    Returns:
        Symbol creation response data
    """
    # This would call the appropriate API endpoints to create test data
    # For now, return placeholder
    return {"symbol": symbol, "days_created": days, "status": "created"}