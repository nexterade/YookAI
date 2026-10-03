"""Provider-neutral HTTP errors."""

class ProviderHTTPError(Exception):
    """Base exception for upstream provider HTTP failures."""
    status_code = None

class AuthError(ProviderHTTPError):
    status_code = 401

class PaymentError(ProviderHTTPError):
    status_code = 402

class RateLimitError(ProviderHTTPError):
    status_code = 429
