"""Simple in-memory sliding-window rate limiter for auth endpoints.

Single-process only: uvicorn запускается с несколькими воркерами, поэтому
фактический лимит умножается на их число, а деплой (он же на каждый push)
обнуляет счётчики. Это защита от всплеска, а не от упорной атаки — для
регистрации настоящий лимит считается по таблице пользователей
(``app.auth.antibot``).
"""

from collections import deque
from time import monotonic

from fastapi import Request

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


def client_ip(request: Request) -> str | None:
    """Настоящий адрес клиента, который нельзя подделать заголовком.

    uvicorn на проде запущен с ``--forwarded-allow-ips='*'`` и берёт из
    ``X-Forwarded-For`` **самый левый** элемент — а его пишет сам клиент.
    Проверка на живом сервере показала: любой может прислать
    ``X-Forwarded-For: 1.2.3.4`` и обнулить себе все лимиты по IP.

    nginx дописывает реальный адрес **справа**
    (``$proxy_add_x_forwarded_for``), поэтому берём последний элемент —
    он проставлен нашим прокси, а не гостем.
    """
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        parts = [p.strip() for p in forwarded.split(",") if p.strip()]
        if parts:
            return parts[-1]
    return request.client.host if request.client else None
