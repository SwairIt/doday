"""Tutor-timezone overrides: settings select + cabinet views отображают в зоне tutor'а."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.lessio.models import LessioService, LessioTutorProfile
from app.lessio.service import create_booking


async def _setup(client: AsyncClient, *, tg_id: int) -> str:
    slug = f"tz_{tg_id}"
    await client.post(
        "/lessio/auth/register",
        data={"email": f"tz{tg_id}@e.com", "password": "strongpass123"},
        follow_redirects=False,
    )
    await client.post(
        "/lessio/app/setup-profile",
        data={"slug": slug, "display_name": "T", "niche": "english"},
        follow_redirects=False,
    )
    return slug


async def test_settings_shows_timezone_select_with_current_default(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _setup(client, tg_id=93000001)
    resp = await client.get("/lessio/app/settings")
    body = resp.text
    assert 'name="timezone"' in body
    assert "Europe/Moscow" in body  # default + один из option'ов
    assert "Asia/Yekaterinburg" in body or "UTC" in body  # ещё опции


async def test_settings_post_updates_timezone(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    slug = await _setup(client, tg_id=93000002)
    resp = await client.post(
        "/lessio/app/settings",
        data={
            "slug": slug,
            "display_name": "T",
            "niche": "english",
            "avatar_emoji": "👨‍🏫",
            "timezone": "Asia/Yekaterinburg",
        },
        follow_redirects=False,
    )
    assert resp.status_code in (302, 303)
    profile = (
        await db_session.execute(select(LessioTutorProfile).where(LessioTutorProfile.slug == slug))
    ).scalar_one()
    assert profile.timezone == "Asia/Yekaterinburg"


async def test_settings_rejects_invalid_timezone(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    slug = await _setup(client, tg_id=93000003)
    await client.post(
        "/lessio/app/settings",
        data={
            "slug": slug,
            "display_name": "T",
            "niche": "english",
            "avatar_emoji": "👨‍🏫",
            "timezone": "Mars/Olympus_Mons",  # invalid
        },
        follow_redirects=False,
    )
    # Должны редиректнуть OK (просто проигнорировать невалидную zone, оставить старую)
    profile = (
        await db_session.execute(select(LessioTutorProfile).where(LessioTutorProfile.slug == slug))
    ).scalar_one()
    # default sticks
    assert profile.timezone == "Europe/Moscow"


async def test_today_displays_booking_in_tutor_timezone(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Tutor с timezone='Europe/Moscow' (UTC+3) видит booking 14:00 UTC как 17:00 MSK."""
    from zoneinfo import ZoneInfo

    slug = await _setup(client, tg_id=93000004)
    profile = (
        await db_session.execute(select(LessioTutorProfile).where(LessioTutorProfile.slug == slug))
    ).scalar_one()
    service = (
        (
            await db_session.execute(
                select(LessioService).where(LessioService.tutor_id == profile.id)
            )
        )
        .scalars()
        .first()
    )
    # «Сегодня» считается в MSK. Берём 14:00 MSK сегодня → это будет в окне,
    # и при отображении должно превратиться в '14:00' с tz-label MSK.
    msk = ZoneInfo("Europe/Moscow")
    today_msk = datetime.now(msk).replace(hour=14, minute=0, second=0, microsecond=0)
    today_utc_slot = today_msk.astimezone(UTC)
    with patch("app.lessio.service.send_booking_emails", new_callable=AsyncMock):
        await create_booking(
            db_session,
            tutor=profile,
            service=service,
            slot=today_utc_slot,
            client_email="tzclient@e.com",
            client_full_name="TZ Client",
            client_phone=None,
        )
        await db_session.commit()

    resp = await client.get("/lessio/app/today")
    body = resp.text
    # MSK 14:00 показывается как '14:00' (а UTC-эквивалент был бы 11:00 — НЕ должно быть)
    assert "14:00" in body
    assert "MSK" in body
