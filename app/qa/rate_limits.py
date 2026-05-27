"""Sliding-window rate limits for Razbery user actions.

Reuses `app.auth.rate_limit` — single-process, in-memory. Sufficient for
single-uvicorn deployment.
"""

from __future__ import annotations

from enum import Enum

from app.auth import rate_limit as auth_rate_limit


class QAAction(Enum):
    ASK_QUESTION = ("qa.ask", 3, 3600.0)  # 3/hour
    ANSWER = ("qa.answer", 10, 3600.0)  # 10/hour
    VOTE = ("qa.vote", 60, 3600.0)  # 60/hour
    REPORT = ("qa.report", 10, 3600.0)  # 10/hour
    ACCEPT = ("qa.accept", 30, 3600.0)  # 30/hour

    def __init__(self, key_prefix: str, max_calls: int, per_seconds: float) -> None:
        self.key_prefix = key_prefix
        self.max_calls = max_calls
        self.per_seconds = per_seconds


# Stricter limits for low-rep users to slow new-account abuse
_LOW_REP_MULTIPLIER = 0.3
_LOW_REP_THRESHOLD = 5


def hit(action: QAAction, user_id: str, *, user_rep: int = 1) -> bool:
    """Record an action attempt. Returns True if allowed."""
    key = f"{action.key_prefix}:{user_id}"
    max_calls = action.max_calls
    if user_rep < _LOW_REP_THRESHOLD:
        max_calls = max(1, int(max_calls * _LOW_REP_MULTIPLIER))
    return auth_rate_limit.hit(key, max_calls=max_calls, per_seconds=action.per_seconds)
