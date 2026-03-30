import asyncio
import random
import time


class AdaptiveRateLimiter:
    """
    Token bucket rate limiter with adaptive backoff.
    Slows down on 429 errors, speeds up on success.
    """

    def __init__(
        self,
        min_interval: float = 1.5,
        max_interval: float = 30.0,
        jitter: float = 0.2,
    ):
        self.min_interval = min_interval
        self.max_interval = max_interval
        self.jitter = jitter
        self.current_interval = min_interval * 1.5
        self._last_request: float = 0.0
        self._429_streak: int = 0

    async def acquire(self) -> None:
        """Wait until it's safe to make the next request."""
        now = time.monotonic()
        elapsed = now - self._last_request
        wait = self.current_interval - elapsed

        # Add jitter to avoid synchronization
        wait += random.uniform(-self.jitter, self.jitter)

        if wait > 0:
            await asyncio.sleep(wait)

        self._last_request = time.monotonic()

    def on_success(self) -> None:
        """Gradually decrease interval back toward minimum on success."""
        self._429_streak = 0
        self.current_interval = max(
            self.min_interval,
            self.current_interval * 0.95,
        )

    def on_rate_limited(self, retry_after: int = 30) -> None:
        """Exponentially increase interval on rate limit."""
        self._429_streak += 1
        self.current_interval = min(
            self.max_interval,
            max(retry_after, self.current_interval * 2),
        )

    def on_error(self) -> None:
        """Back off moderately on generic errors."""
        self.current_interval = min(
            self.max_interval,
            self.current_interval * 1.5,
        )

    @property
    def requests_per_minute(self) -> float:
        if self.current_interval <= 0:
            return 60.0
        return 60.0 / self.current_interval
