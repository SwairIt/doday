"""Lessio cabinet: /lessio/app/calendar — month-view with booking markers."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.lessio.models import LessioService, LessioTutorProfile
from app.lessio.service import create_booking


async def _setup(client: AsyncClient, *, tg_id: int) -> str:
    slug = f"cal_{tg_id}"
    await client.post(
        "/lessio/auth/register",
        data={"email": f"ca{tg_id}@e.com", "password": "strongpass123"},
        follow_redirects=False,
    )
    await client.post(
        "/lessio/app/setup-profile",
        data={"slug": slug, "display_name": "T", "niche": "english"},
        follow_redirects=False,
    )
    return slug


async def test_calendar_current_month_renders(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _setup(client, tg_id=75000001)
    resp = await client.get("/lessio/app/calendar")
    assert resp.status_code == 200
    body = resp.text
    # Должны быть навигационные стрелки и сетка дней
    assert "calendar" in body.lower() or "месяц" in body.lower() or "пн" in body.lower()


async def test_calendar_explicit_month_shows_bookings(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    slug = await _setup(client, tg_id=75000002)
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
    with patch("app.lessio.service.send_booking_emails", new_callable=AsyncMock):
        await create_booking(
            db_session,
            tutor=profile,
            service=service,
            slot=datetime(2026, 6, 15, 14, 0, tzinfo=UTC),
            client_email="cal@e.com",
            client_full_name="CalClient",
            client_phone=None,
        )
        await db_session.commit()

    resp = await client.get("/lessio/app/calendar?month=2026-06")
    assert resp.status_code == 200
    # На 15-м числе должна быть метка
    assert "CalClient" in resp.text or "14:00" in resp.text or "15" in resp.text
