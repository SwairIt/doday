"""Google Calendar OAuth + busy-times sync."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.lessio.google_calendar import (
    decrypt_refresh_token,
    encrypt_refresh_token,
    fetch_google_busy_times,
)
from app.lessio.models import LessioService, LessioTutorProfile
from app.lessio.service import (
    auto_onboard_tutor,
    create_tutor_profile,
    find_free_slots,
)

# A future Monday/Tuesday (4–10 days out) so the past-filter in find_free_slots
# doesn't eat the test slots. Replaces the old hardcoded 2026-06-01/02 time-bomb.
_today = datetime.now(UTC).date()
_to_mon = (7 - _today.weekday()) % 7
_MONDAY = _today + timedelta(days=_to_mon if _to_mon >= 4 else _to_mon + 7)
_MON_Y, _MON_M, _MON_D = _MONDAY.year, _MONDAY.month, _MONDAY.day
_TUESDAY = _MONDAY + timedelta(days=1)
_TUE_Y, _TUE_M, _TUE_D = _TUESDAY.year, _TUESDAY.month, _TUESDAY.day

# ── Fernet encryption (no creds needed) ───────────────────────────────


def test_encrypt_decrypt_roundtrip() -> None:
    token = "1//0abcdef.refresh_token_value_xxxx"
    encrypted = encrypt_refresh_token(token)
    assert encrypted != token  # actually encrypted
    assert decrypt_refresh_token(encrypted) == token


def test_decrypt_invalid_returns_none() -> None:
    assert decrypt_refresh_token("bogus-not-fernet-token") is None
    assert decrypt_refresh_token("") is None


# ── Busy-times fetch (mocked HTTP) ────────────────────────────────────


@patch("app.lessio.google_calendar.httpx.AsyncClient")
async def test_fetch_google_busy_times_parses_events(
    mock_client_cls: AsyncMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "google_oauth_client_id", "fake-id")
    monkeypatch.setattr(get_settings(), "google_oauth_client_secret", "fake-secret")

    # Mock httpx context manager + responses
    mock_client = AsyncMock()
    mock_client_cls.return_value.__aenter__.return_value = mock_client

    # Refresh-token exchange
    mock_token_resp = AsyncMock()
    mock_token_resp.json = lambda: {"access_token": "fake-access", "expires_in": 3600}
    mock_token_resp.status_code = 200
    mock_token_resp.raise_for_status = lambda: None

    # FreeBusy query
    mock_freebusy_resp = AsyncMock()
    mock_freebusy_resp.json = lambda: {
        "calendars": {
            "primary": {
                "busy": [
                    {"start": f"{_MONDAY}T10:00:00Z", "end": f"{_MONDAY}T11:30:00Z"},
                    {"start": f"{_MONDAY}T14:00:00Z", "end": f"{_MONDAY}T15:00:00Z"},
                ]
            }
        }
    }
    mock_freebusy_resp.status_code = 200
    mock_freebusy_resp.raise_for_status = lambda: None
    mock_client.post.side_effect = [mock_token_resp, mock_freebusy_resp]

    intervals = await fetch_google_busy_times(
        refresh_token="dummy",
        date_from=datetime(_MON_Y, _MON_M, _MON_D, tzinfo=UTC),
        date_to=datetime(_TUE_Y, _TUE_M, _TUE_D, tzinfo=UTC),
    )
    assert len(intervals) == 2
    assert intervals[0][0] == datetime(_MON_Y, _MON_M, _MON_D, 10, 0, tzinfo=UTC)
    assert intervals[0][1] == datetime(_MON_Y, _MON_M, _MON_D, 11, 30, tzinfo=UTC)


@patch("app.lessio.google_calendar.httpx.AsyncClient")
async def test_fetch_busy_returns_empty_on_api_error(
    mock_client_cls: AsyncMock,
) -> None:
    mock_client = AsyncMock()
    mock_client_cls.return_value.__aenter__.return_value = mock_client
    mock_client.post.side_effect = Exception("Google API down")
    intervals = await fetch_google_busy_times(
        refresh_token="dummy",
        date_from=datetime(_MON_Y, _MON_M, _MON_D, tzinfo=UTC),
        date_to=datetime(_TUE_Y, _TUE_M, _TUE_D, tzinfo=UTC),
    )
    assert intervals == []


# ── find_free_slots integration ───────────────────────────────────────


@patch("app.lessio.service.fetch_google_busy_times", new_callable=AsyncMock)
async def test_find_free_slots_subtracts_google_busy(
    mock_fetch: AsyncMock, db_session: AsyncSession
) -> None:
    """Если tutor подключил Google Calendar, slots во время busy-events исключаются."""
    user, _ = await auto_onboard_tutor(db_session, telegram_user_id=99000001)
    tutor = await create_tutor_profile(db_session, user=user, slug="gcal_t", display_name="T")
    tutor.google_calendar_refresh_token = encrypt_refresh_token("fake-refresh")
    service = LessioService(
        tutor_id=tutor.id,
        title="60 мин",
        duration_minutes=60,
        price_kopecks=100000,
        price_stars=100,
    )
    db_session.add(service)
    await db_session.commit()

    # Mock: 10:00-11:30 UTC занято в GCal на пн 2026-06-01
    mock_fetch.return_value = [
        (
            datetime(_MON_Y, _MON_M, _MON_D, 10, 0, tzinfo=UTC),
            datetime(_MON_Y, _MON_M, _MON_D, 11, 30, tzinfo=UTC),
        )
    ]

    monday = datetime(_MON_Y, _MON_M, _MON_D, 0, 0, tzinfo=UTC)
    slots = await find_free_slots(
        db_session,
        tutor,
        date_from=monday,
        date_to=monday + timedelta(days=1),
        service=service,
    )
    # 10:15 был бы в обычном расписании (9:00, 10:15, 11:30, ...) — но GCal-busy
    # 10:00-11:30 его перекрывает. 11:30 на границе — должен остаться.
    assert datetime(_MON_Y, _MON_M, _MON_D, 10, 15, tzinfo=UTC) not in slots
    assert datetime(_MON_Y, _MON_M, _MON_D, 9, 0, tzinfo=UTC) in slots  # до busy
    mock_fetch.assert_awaited()


@patch("app.lessio.service.fetch_google_busy_times", new_callable=AsyncMock)
async def test_find_free_slots_skips_gcal_if_no_token(
    mock_fetch: AsyncMock, db_session: AsyncSession
) -> None:
    """Tutor без google_calendar_refresh_token — fetch не вызывается."""
    user, _ = await auto_onboard_tutor(db_session, telegram_user_id=99000002)
    tutor = await create_tutor_profile(db_session, user=user, slug="nogcal_t", display_name="T")
    # NO refresh_token
    service = LessioService(
        tutor_id=tutor.id,
        title="60 мин",
        duration_minutes=60,
        price_kopecks=100000,
        price_stars=100,
    )
    db_session.add(service)
    await db_session.commit()

    monday = datetime(_MON_Y, _MON_M, _MON_D, 0, 0, tzinfo=UTC)
    await find_free_slots(
        db_session,
        tutor,
        date_from=monday,
        date_to=monday + timedelta(days=1),
        service=service,
    )
    mock_fetch.assert_not_awaited()


# ── OAuth-flow router ─────────────────────────────────────────────────


async def test_oauth_connect_redirects_to_google(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.config import get_settings

    monkeypatch.setattr(
        get_settings(), "google_oauth_client_id", "fake-client-id.apps.googleusercontent.com"
    )
    monkeypatch.setattr(get_settings(), "google_oauth_client_secret", "fake-secret")
    # auth-ed tutor
    await client.post(
        "/lessio/auth/register",
        data={"email": "gc@e.com", "password": "strongpass123"},
        follow_redirects=False,
    )
    await client.post(
        "/lessio/app/setup-profile",
        data={"slug": "gc_t", "display_name": "G", "niche": "english"},
        follow_redirects=False,
    )
    resp = await client.get("/lessio/oauth/google/connect", follow_redirects=False)
    assert resp.status_code in (302, 307)
    loc = resp.headers["location"]
    assert "accounts.google.com" in loc
    assert "scope=" in loc
    assert "calendar.readonly" in loc


async def test_oauth_connect_503_when_not_configured(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "google_oauth_client_id", "")
    monkeypatch.setattr(get_settings(), "google_oauth_client_secret", "")
    await client.post(
        "/lessio/auth/register",
        data={"email": "gc2@e.com", "password": "strongpass123"},
        follow_redirects=False,
    )
    await client.post(
        "/lessio/app/setup-profile",
        data={"slug": "gc_t2", "display_name": "G", "niche": "english"},
        follow_redirects=False,
    )
    resp = await client.get("/lessio/oauth/google/connect", follow_redirects=False)
    assert resp.status_code == 503


async def test_oauth_disconnect_clears_token(client: AsyncClient, db_session: AsyncSession) -> None:
    await client.post(
        "/lessio/auth/register",
        data={"email": "gc3@e.com", "password": "strongpass123"},
        follow_redirects=False,
    )
    await client.post(
        "/lessio/app/setup-profile",
        data={"slug": "gc_t3", "display_name": "G", "niche": "english"},
        follow_redirects=False,
    )
    profile = (
        await db_session.execute(
            select(LessioTutorProfile).where(LessioTutorProfile.slug == "gc_t3")
        )
    ).scalar_one()
    profile.google_calendar_refresh_token = encrypt_refresh_token("fake-token")
    await db_session.commit()

    resp = await client.post("/lessio/oauth/google/disconnect", follow_redirects=False)
    assert resp.status_code in (302, 303)
    await db_session.refresh(profile)
    assert profile.google_calendar_refresh_token is None
