"""Google Calendar OAuth + busy-times fetch (read-only sync).

Phase 2 опциональная фича. Tutor подключает Google Calendar в Settings —
получаем refresh_token, шифруем через Fernet (key derived из app_secret_key
PBKDF2), сохраняем в LessioTutorProfile.google_calendar_refresh_token.
Когда вычисляем find_free_slots → если refresh_token есть, exchange на
access_token + freebusy query → вычитаем busy-intervals из generated slots.

Scopes: ../auth/calendar.readonly — мы только читаем busy-times, не пишем
events. Write-back (наши booking появляются в GCal) — отдельная Phase 3 фича.
"""

from __future__ import annotations

import base64
from datetime import datetime as _dt

import httpx
import structlog
from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from app.config import get_settings

_log = structlog.get_logger(__name__)

GOOGLE_OAUTH_SCOPES = "https://www.googleapis.com/auth/calendar.readonly"
GOOGLE_OAUTH_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_OAUTH_TOKEN_URL = "https://oauth2.googleapis.com/token"  # noqa: S105
GOOGLE_FREEBUSY_URL = "https://www.googleapis.com/calendar/v3/freeBusy"


# ── Fernet encryption derived from app_secret_key ─────────────────────


def _fernet() -> Fernet:
    """Derive Fernet key from app_secret_key via PBKDF2 (deterministic — restart-safe)."""
    settings = get_settings()
    secret = (settings.app_secret_key or "lessio-dev-fallback").encode("utf-8")
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=b"lessio-google-calendar-v1",  # static — restart-safe
        iterations=100_000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(secret))
    return Fernet(key)


def encrypt_refresh_token(token: str) -> str:
    """Шифровать Google refresh-token для хранения в DB."""
    return _fernet().encrypt(token.encode("utf-8")).decode("utf-8")


def decrypt_refresh_token(encrypted: str) -> str | None:
    """Расшифровать. None при invalid/empty input — caller skip GCal sync."""
    if not encrypted:
        return None
    try:
        return _fernet().decrypt(encrypted.encode("utf-8")).decode("utf-8")
    except (InvalidToken, ValueError):
        return None


# ── Google API: refresh → access_token → freebusy ──────────────────────


async def _refresh_access_token(refresh_token: str) -> str | None:
    """Exchange refresh_token → access_token. Returns None при API error."""
    settings = get_settings()
    if not settings.google_oauth_client_id or not settings.google_oauth_client_secret:
        return None
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.post(
            GOOGLE_OAUTH_TOKEN_URL,
            data={
                "client_id": settings.google_oauth_client_id,
                "client_secret": settings.google_oauth_client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            },
        )
        r.raise_for_status()
        token: str | None = r.json().get("access_token")
        return token


async def fetch_google_busy_times(
    *, refresh_token: str, date_from: _dt, date_to: _dt
) -> list[tuple[_dt, _dt]]:
    """Returns list of (start_utc, end_utc) busy-intervals из Google Calendar.

    Аргументы: refresh_token (расшифрованный), date_from/date_to (timezone-aware).
    На любой ошибке возвращает [] — caller (find_free_slots) gracefully ignores.
    """
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # 1. Refresh → access_token
            settings = get_settings()
            if not settings.google_oauth_client_id:
                return []
            token_resp = await client.post(
                GOOGLE_OAUTH_TOKEN_URL,
                data={
                    "client_id": settings.google_oauth_client_id,
                    "client_secret": settings.google_oauth_client_secret,
                    "refresh_token": refresh_token,
                    "grant_type": "refresh_token",
                },
            )
            token_resp.raise_for_status()
            access_token = token_resp.json().get("access_token")
            if not access_token:
                return []

            # 2. FreeBusy query
            freebusy_resp = await client.post(
                GOOGLE_FREEBUSY_URL,
                headers={"Authorization": f"Bearer {access_token}"},
                json={
                    "timeMin": date_from.isoformat(),
                    "timeMax": date_to.isoformat(),
                    "items": [{"id": "primary"}],
                },
            )
            freebusy_resp.raise_for_status()
            data = freebusy_resp.json()
            busy_blocks = data.get("calendars", {}).get("primary", {}).get("busy", [])

            from datetime import UTC as _UTC

            result: list[tuple[_dt, _dt]] = []
            for block in busy_blocks:
                try:
                    start = _dt.fromisoformat(block["start"].replace("Z", "+00:00"))
                    end = _dt.fromisoformat(block["end"].replace("Z", "+00:00"))
                    if start.tzinfo is None:
                        start = start.replace(tzinfo=_UTC)
                    if end.tzinfo is None:
                        end = end.replace(tzinfo=_UTC)
                    result.append((start, end))
                except (KeyError, ValueError) as exc:
                    _log.warning("lessio_gcal_busy_parse_failed", block=block, error=str(exc))
            return result
    except Exception as exc:
        _log.warning("lessio_gcal_fetch_failed", error=str(exc))
        return []
