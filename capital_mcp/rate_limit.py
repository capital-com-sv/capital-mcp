"""Rate limiting implementation using token bucket algorithm."""

import asyncio
import time


class TokenBucket:
    """Token bucket rate limiter (async-safe)."""

    def __init__(self, capacity: float, refill_rate: float):
        """
        Initialize token bucket.

        Args:
            capacity: Maximum number of tokens in the bucket
            refill_rate: Tokens added per second
        """
        self.capacity = capacity
        self.refill_rate = refill_rate
        self.tokens = capacity
        self.last_refill = time.monotonic()
        self._lock = asyncio.Lock()

    async def _refill(self) -> None:
        """Refill tokens based on elapsed time."""
        now = time.monotonic()
        elapsed = now - self.last_refill
        self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)
        self.last_refill = now

    async def acquire(
        self,
        tokens: float = 1.0,
        timeout: float | None = None,  # NOSONAR asyncio.timeout() requires Python 3.11+
    ) -> bool:
        """
        Acquire tokens from the bucket.

        Args:
            tokens: Number of tokens to acquire
            timeout: Maximum time to wait (None = wait forever)

        Returns:
            True if tokens acquired, False if timeout
        """
        start_time = time.monotonic()

        while True:
            async with self._lock:
                await self._refill()

                if self.tokens >= tokens:
                    self.tokens -= tokens
                    return True

            # Check timeout
            if timeout is not None:
                elapsed = time.monotonic() - start_time
                if elapsed >= timeout:
                    return False

            # Wait a bit before retrying
            await asyncio.sleep(0.01)

    async def try_acquire(self, tokens: float = 1.0) -> bool:
        """
        Try to acquire tokens without blocking.

        Args:
            tokens: Number of tokens to acquire

        Returns:
            True if tokens acquired, False otherwise
        """
        async with self._lock:
            await self._refill()

            if self.tokens >= tokens:
                self.tokens -= tokens
                return True

            return False

    async def available_tokens(self) -> float:
        """Get current number of available tokens."""
        async with self._lock:
            await self._refill()
            return self.tokens


class RateLimiter:
    """
    Multi-tier rate limiter for Capital.com API.

    Enforces:
    - Global: 10 requests/second per user
    - Session: 1 request/second for POST /session
    - Trading: 1 request per 0.1 seconds for POST /positions, POST /workingorders
    """

    def __init__(self) -> None:
        # Global rate limit: 10 req/s
        self.global_limiter = TokenBucket(capacity=10.0, refill_rate=10.0)

        # Session rate limit: 1 req/s
        self.session_limiter = TokenBucket(capacity=1.0, refill_rate=1.0)

        # Trading rate limit: 1 req per 0.1s = 10 req/s
        self.trading_limiter = TokenBucket(capacity=10.0, refill_rate=10.0)

    async def acquire_global(
        self,
        timeout: float | None = 10.0,  # NOSONAR asyncio.timeout() requires Python 3.11+
    ) -> bool:
        """
        Acquire global rate limit token.

        Args:
            timeout: Maximum wait time in seconds

        Returns:
            True if acquired, False if timeout
        """
        return await self.global_limiter.acquire(tokens=1.0, timeout=timeout)

    async def acquire_session(
        self,
        timeout: float | None = 10.0,  # NOSONAR asyncio.timeout() requires Python 3.11+
    ) -> bool:
        """
        Acquire session rate limit token (for POST /session).

        Args:
            timeout: Maximum wait time in seconds

        Returns:
            True if acquired, False if timeout
        """
        # Must also pass global limit
        if not await self.global_limiter.acquire(tokens=1.0, timeout=timeout):
            return False
        return await self.session_limiter.acquire(tokens=1.0, timeout=timeout)

    async def acquire_trading(
        self,
        timeout: float | None = 10.0,  # NOSONAR asyncio.timeout() requires Python 3.11+
    ) -> bool:
        """
        Acquire trading rate limit token (for POST /positions, POST /workingorders).

        Args:
            timeout: Maximum wait time in seconds

        Returns:
            True if acquired, False if timeout
        """
        # Must also pass global limit
        if not await self.global_limiter.acquire(tokens=1.0, timeout=timeout):
            return False
        return await self.trading_limiter.acquire(tokens=1.0, timeout=timeout)

    async def get_state(self) -> dict[str, float]:
        """Get current state of all limiters."""
        return {
            "global_tokens": await self.global_limiter.available_tokens(),
            "session_tokens": await self.session_limiter.available_tokens(),
            "trading_tokens": await self.trading_limiter.available_tokens(),
        }


# Global rate limiter instance
_rate_limiter: RateLimiter | None = None


def get_rate_limiter() -> RateLimiter:
    """Get or create the global rate limiter instance."""
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter()
    return _rate_limiter


def reset_rate_limiter() -> None:
    """Reset the global rate limiter (mainly for testing)."""
    global _rate_limiter
    _rate_limiter = None
