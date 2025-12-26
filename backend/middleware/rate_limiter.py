"""
Rate limiting middleware using slowapi.
Protects against abuse with configurable limits per endpoint.
"""

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi import Request, Response
from typing import Optional, Callable

from backend.config import get_settings

settings = get_settings()


def get_user_identifier(request: Request) -> str:
    """
    Get a unique identifier for rate limiting.
    Uses user ID if authenticated, otherwise falls back to IP address.
    """
    # Check for authenticated user in request state
    if hasattr(request.state, "user") and request.state.user:
        return f"user:{request.state.user.id}"

    # Check for token in authorization header (indicates authenticated request)
    auth_header = request.headers.get("authorization", "")
    if auth_header.startswith("Bearer "):
        # Use a hash of the token as identifier
        token = auth_header[7:]
        return f"token:{hash(token)}"

    # Fall back to IP address for unauthenticated requests
    return f"ip:{get_remote_address(request)}"


def get_key_func(request: Request) -> str:
    """Default key function that uses user identifier."""
    return get_user_identifier(request)


# Create limiter instance
# Uses in-memory storage by default, or Redis if configured
if settings.redis_url:
    from slowapi.middleware import SlowAPIMiddleware

    limiter = Limiter(
        key_func=get_key_func,
        storage_uri=settings.redis_url,
        enabled=settings.rate_limit_enabled,
    )
else:
    limiter = Limiter(
        key_func=get_key_func,
        enabled=settings.rate_limit_enabled,
    )


def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> Response:
    """Custom handler for rate limit exceeded errors."""
    from fastapi.responses import JSONResponse

    # Parse the limit from the exception
    limit_value = str(exc.detail) if hasattr(exc, "detail") else "Rate limit exceeded"

    return JSONResponse(
        status_code=429,
        content={
            "error": "rate_limit_exceeded",
            "message": "Too many requests. Please slow down.",
            "detail": limit_value,
            "retry_after": getattr(exc, "retry_after", 60),
        },
        headers={
            "Retry-After": str(getattr(exc, "retry_after", 60)),
            "X-RateLimit-Limit": limit_value,
        },
    )


# Rate limit decorator helpers
def submissions_limit() -> str:
    """Get rate limit string for submissions endpoint."""
    return f"{settings.rate_limit_submissions_per_hour}/hour"


def validate_limit() -> str:
    """Get rate limit string for validation endpoint."""
    return f"{settings.rate_limit_validate_per_hour}/hour"


def default_limit() -> str:
    """Get rate limit string for default endpoints."""
    return f"{settings.rate_limit_default_per_minute}/minute"
