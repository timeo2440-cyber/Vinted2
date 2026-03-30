class VintedError(Exception):
    """Base exception for Vinted client errors."""
    pass


class VintedAuthError(VintedError):
    """Raised when session is invalid or cookies have expired."""
    pass


class VintedRateLimitError(VintedError):
    """Raised on HTTP 429 Too Many Requests."""
    def __init__(self, retry_after: int = 30):
        self.retry_after = retry_after
        super().__init__(f"Rate limited. Retry after {retry_after}s")


class VintedItemUnavailable(VintedError):
    """Raised when an item is already sold or reserved."""
    pass


class VintedCheckoutError(VintedError):
    """Raised when checkout fails."""
    pass


class VintedNetworkError(VintedError):
    """Raised on network/timeout errors."""
    pass
