"""Thread-safe token-bucket API rate limiter, standard library only.

rate: tokens replenished per second (strictly positive).
capacity: maximum burst tokens (strictly positive).
allow(cost): take a request's token cost atomically, if available.

The optional clock injection makes deterministic testing possible and permits
the caller to use a monotonic clock source under unusual runtime constraints.
"""
from __future__ import annotations

import math
import threading
import time
from typing import Callable


class TokenBucket:
    """A lazy-refilled, monotonic-clock token bucket with a burst cap."""

    def __init__(
        self,
        rate: float,
        capacity: float,
        *,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if not callable(clock):
            raise TypeError("clock must be callable")
        self._rate = self._positive_finite(rate, "rate")
        self._capacity = self._positive_finite(capacity, "capacity")
        self._clock = clock
        self._lock = threading.RLock()
        self._tokens = self._capacity
        self._updated = float(self._clock())
        if not math.isfinite(self._updated):
            raise ValueError("clock must return a finite number")

    @staticmethod
    def _positive_finite(value: float, field: str) -> float:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError(f"{field} must be a positive finite number")
        number = float(value)
        if number <= 0 or not math.isfinite(number):
            raise ValueError(f"{field} must be a positive finite number")
        return number

    def _refill(self) -> None:
        now = float(self._clock())
        if not math.isfinite(now):
            raise ValueError("clock must return a finite number")
        elapsed = max(0.0, now - self._updated)
        self._tokens = min(self._capacity, self._tokens + elapsed * self._rate)
        # If a user-provided clock goes backwards, do not mint extra tokens
        # or move the reference timestamp backwards.
        self._updated = max(now, self._updated)

    def allow(self, cost: float = 1.0) -> bool:
        """Consume cost tokens if present, otherwise refuse with no deduction."""
        cost = self._positive_finite(cost, "cost")
        with self._lock:
            self._refill()
            if self._tokens + 1e-12 < cost:
                return False
            self._tokens = max(0.0, self._tokens - cost)
            return True

    def try_acquire(self, tokens: float = 1.0) -> bool:
        """Alias for allow(), convenient in HTTP middleware integrations."""
        return self.allow(tokens)

    def retry_after(self, cost: float = 1.0) -> float:
        """Seconds until cost tokens are available; inf if above capacity."""
        cost = self._positive_finite(cost, "cost")
        with self._lock:
            self._refill()
            if cost > self._capacity:
                return math.inf
            return max(0.0, (cost - self._tokens) / self._rate)

    @property
    def available(self) -> float:
        """Return the current token balance after replenishment."""
        with self._lock:
            self._refill()
            return self._tokens

    @property
    def rate(self) -> float:
        return self._rate

    @property
    def capacity(self) -> float:
        return self._capacity


# Descriptive alias for integrations that prefer RateLimiter.
RateLimiter = TokenBucket
