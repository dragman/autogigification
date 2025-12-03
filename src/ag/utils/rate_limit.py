import time
from contextlib import contextmanager
from typing import Optional


class RateLimiter:
    """Simple sleep-based rate limiter for API calls."""

    def __init__(self, min_interval_seconds: float = 1.0):
        self.min_interval = min_interval_seconds
        self._next_allowed: float = 0.0

    def wait(self) -> None:
        now = time.monotonic()
        delay = self._next_allowed - now
        if delay > 0:
            time.sleep(delay)
        self._next_allowed = time.monotonic() + self.min_interval

    def __enter__(self) -> "RateLimiter":
        self.wait()
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> bool:
        # Ensure next allowed is at least min_interval from exit.
        self._next_allowed = max(self._next_allowed, time.monotonic() + self.min_interval)
        return False


@contextmanager
def retry_after(delay_seconds: float, rate_limiter: Optional["RateLimiter"] = None):
    """Sleep for Retry-After and honor rate limiter before retrying."""
    time.sleep(max(0.0, delay_seconds))
    if rate_limiter:
        rate_limiter.wait()
    yield


class NullRateLimiter(RateLimiter):
    """No-op limiter for cases where throttling is optional."""

    def __init__(self):
        super().__init__(min_interval_seconds=0.0)

    def wait(self) -> None:
        return None

    def __enter__(self) -> "NullRateLimiter":
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> bool:
        return False
