"""Async token-bucket rate limiter, per source."""

from __future__ import annotations

import asyncio
import time
from collections import defaultdict


class RateLimiter:
    """Simple async token-bucket rate limiter.

    Each source gets its own bucket with a configurable rate (tokens/sec).
    """

    def __init__(self) -> None:
        self._rates: dict[str, float] = {}
        self._last_time: dict[str, float] = defaultdict(lambda: 0.0)
        self._tokens: dict[str, float] = defaultdict(lambda: 1.0)
        self._lock = asyncio.Lock()

    def configure(self, source: str, rate: float) -> None:
        """Set the rate limit for a source (requests per second)."""
        self._rates[source] = rate
        self._tokens[source] = min(rate, 1.0)

    async def acquire(self, source: str) -> None:
        """Wait until a token is available for the given source."""
        rate = self._rates.get(source)
        if rate is None or rate <= 0:
            return

        async with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_time[source]
            self._tokens[source] = min(rate, self._tokens[source] + elapsed * rate)
            self._last_time[source] = now

            if self._tokens[source] < 1.0:
                wait = (1.0 - self._tokens[source]) / rate
                await asyncio.sleep(wait)
                self._tokens[source] = 0.0
                self._last_time[source] = time.monotonic()
            else:
                self._tokens[source] -= 1.0


# Global instance
rate_limiter = RateLimiter()
