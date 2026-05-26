"""iCalendar feed: /lessio/app/calendar.ics?token=<X> — confirmed bookings RFC5545."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.lessio.models import LessioService, LessioTutorProfile
from app.lessio.service import create_booking


async def _setup(client: AsyncClient, *, tg_id: int) -> str:
    slug = f"ic_{tg_id}"
    await client.post(
        "/lessio/auth/register",
        data={"email": f"ic{tg_id}@e.com", "password": "strongpass123"},
        follow_redirects=False,
    )
    await client.post(
        "/lessio/app/setup-profile",
        data={"slug": slug, "display_name": "iCal Tutor", "niche": "english"},
        follow_redirects=False,
    )
    return slug


async def test_ical_settings_page_shows_subscribe_url(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """В settings есть subscribe URL для iCal feed."""
    await _setup(client, tg_id=120000001)
    resp = await client.get("/lessio/app/settings")
    body = resp.text
    assert "calendar.ics" in body or "ical" in body.lower()


async def test_ical_feed_returns_valid_calendar(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    slug = await _setup(client, tg_id=120000002)
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
            slot=datetime(2026, 7, 1, 14, 0, tzinfo=UTC),
            client_email="cal-client@e.com",
            client_full_name="Cal Client",
            client_phone=None,
        )
        await db_session.commit()

    # Get feed token from settings
    settings_html = (await client.get("/lessio/app/settings")).text
    import re

    m = re.search(r"calendar\.ics\?token=([\w\-\.\=]+)", settings_html)
    assert m, "Calendar token not found in settings"
    token = m.group(1)

    resp = await client.get(f"/lessio/app/calendar.ics?token={token}")
    assert resp.status_code == 200
    assert "text/calendar" in resp.headers["content-type"]
    body = resp.text
    assert "BEGIN:VCALENDAR" in body
    assert "END:VCALENDAR" in body
    assert "BEGIN:VEVENT" in body
    assert "SUMMARY:" in body
    assert "Cal Client" in body
    assert "DTSTART:20260701T140000Z" in body


async def test_ical_feed_wrong_token_404(client: AsyncClient) -> None:
    resp = await client.get("/lessio/app/calendar.ics?token=wrong-token")
    assert resp.status_code == 404


async def test_ical_feed_no_token_404(client: AsyncClient) -> None:
    resp = await client.get("/lessio/app/calendar.ics")
    assert resp.status_code in (404, 422)
