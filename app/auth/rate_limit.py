"""Simple in-memory sliding-window rate limiter for auth endpoints.

Single-process only. For multi-instance deploys swap to Redis-backed limiter
(but our deployment is single-uvicorn for now).
"""

from collections import deque
from time import monotonic

_ATTEMPTS: dict[str, deque[float]] = {}


def hit(key: str, *, max_calls: int, per_seconds: float) -> bool:
    """Record an attempt for `key`. Returns True if allowed, False if over limit."""
    now = monotonic()
    bucket = _ATTEMPTS.get(key)
    if bucket is None:
        bucket = deque()
        _ATTEMPTS[key] = bucket

    # Drop entries outside the window.
    cutoff = now - per_seconds
    while bucket and bucket[0] < cutoff:
        bucket.popleft()

    if len(bucket) >= max_calls:
        return False
    bucket.append(now)
    return True


def reset(key: str) -> None:
    """Clear all recorded attempts for a key — call after a successful login."""
    _ATTEMPTS.pop(key, None)


def reset_all() -> None:
    """Clear every key — only for tests."""
    _ATTEMPTS.clear()


def client_key(request_ip: str | None, identifier: str) -> str:
    """Compose a key bucket for `identifier` from `request_ip` (or 'unknown')."""
    return f"{identifier}:{request_ip or 'unknown'}"
