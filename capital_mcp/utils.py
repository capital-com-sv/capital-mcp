"""Utility functions for Capital.com MCP Server."""

import asyncio
from collections.abc import Callable
from typing import Any, TypeVar

T = TypeVar("T")


async def poll_until(
    fn: Callable[[], Any],
    condition: Callable[[Any], bool],
    *,
    timeout_s: float = 15.0,
    poll_interval_ms: int = 500,
    initial_delay_ms: int = 200,
) -> Any | None:
    """
    Poll a function until a condition is met or timeout.

    Args:
        fn: Async function to call
        condition: Condition function that checks the result
        timeout_s: Timeout in seconds
        poll_interval_ms: Poll interval in milliseconds
        initial_delay_ms: Initial delay before first poll

    Returns:
        Result if condition met, None if timeout
    """
    import time

    start_time = time.monotonic()

    # Initial delay
    if initial_delay_ms > 0:
        await asyncio.sleep(initial_delay_ms / 1000.0)

    attempt = 0
    while True:
        elapsed = time.monotonic() - start_time
        if elapsed >= timeout_s:
            return None

        try:
            result = await fn()
            if condition(result):
                return result
        except Exception:
            # Continue polling on errors
            pass

        # Wait before next attempt
        await asyncio.sleep(poll_interval_ms / 1000.0)
        attempt += 1


def format_iso_datetime(dt: Any | None) -> str | None:
    """Format datetime to ISO 8601 string."""
    if dt is None:
        return None
    if isinstance(dt, str):
        return dt
    try:
        from datetime import datetime

        if isinstance(dt, datetime):
            return dt.isoformat().replace("+00:00", "Z") if dt.tzinfo else dt.isoformat() + "Z"
    except Exception:
        pass
    return str(dt)


def parse_float_safe(value: Any, default: float = 0.0) -> float:
    """Safely parse a value to float."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def parse_int_safe(value: Any, default: int = 0) -> int:
    """Safely parse a value to int."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
