"""Redis-backed rate limiting with an in-memory fallback for local development.

A fixed-window counter is stored in Redis when REDIS_URL is configured so limits
apply consistently across API instances. When Redis is unavailable, a per-process
sliding window is used so development still works without fabricated results.
"""

from __future__ import annotations

import logging
import time
from collections import defaultdict, deque
from typing import Deque

from ..config import get_settings

logger = logging.getLogger("pitsense.rate_limit")


class RateLimiter:
    def __init__(self) -> None:
        self.settings = get_settings()
        self._redis = None
        if self.settings.redis_url:
            try:
                from redis import Redis

                self._redis = Redis.from_url(self.settings.redis_url)
            except Exception as exc:
                logger.warning("Redis rate limiting unavailable: %s", type(exc).__name__)
                self._redis = None
        self._local: dict[str, Deque[float]] = defaultdict(deque)

    def hit(self, key: str, limit: int, window_seconds: int) -> bool:
        """Record one request. Return True if allowed, False if over the limit."""
        if limit <= 0 or window_seconds <= 0:
            return True
        if self._redis is not None:
            try:
                count = self._redis.incr(key)
                if count == 1:
                    self._redis.expire(key, window_seconds)
                return count <= limit
            except Exception as exc:
                logger.warning("Redis rate limit check failed; using in-memory fallback: %s", type(exc).__name__)
        return self._local_hit(key, limit, window_seconds)

    def _local_hit(self, key: str, limit: int, window_seconds: int) -> bool:
        now = time.monotonic()
        events = self._local[key]
        cutoff = now - window_seconds
        while events and events[0] < cutoff:
            events.popleft()
        if len(events) >= limit:
            return False
        events.append(now)
        return True


_limiter: RateLimiter | None = None


def get_limiter() -> RateLimiter:
    global _limiter
    if _limiter is None:
        _limiter = RateLimiter()
    return _limiter