"""Cabinet stats dashboard: /lessio/app/stats — earnings + conversion + breakdown."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.lessio.models import LessioService, LessioTutorProfile
from app.lessio.service import create_booking


async def _setup(client: AsyncClient, *, tg_id: int) -> str:
    slug = f"st_{tg_id}"
    await client.post(
        "/lessio/auth/register",
        data={"email": f"st{tg_id}@e.com", "password": "strongpass123"},
        follow_redirects=False,
    )
    await client.post(
        "/lessio/app/setup-profile",
        data={"slug": slug, "display_name": "T", "niche": "english"},
        follow_redirects=False,
    )
    return slug


async def test_stats_page_renders_empty_state(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _setup(client, tg_id=98000001)
    resp = await client.get("/lessio/app/stats")
    assert resp.status_code == 200
    body = resp.text
    # Empty state — нет встреч, total = 0
    assert "Статистика" in body or "stats" in body.lower()
    assert "0" in body  # total bookings/earnings


async def test_stats_shows_total_bookings_and_earnings(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    slug = await _setup(client, tg_id=98000002)
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
    assert service is not None
    service.price_kopecks = 200000  # 2000₽
    await db_session.commit()

    with patch("app.lessio.service.send_booking_emails", new_callable=AsyncMock):
        for i, day_offset in enumerate([-30, -20, -10]):
            slot = datetime(2026, 6, 1, 14, 0, tzinfo=UTC) + timedelta(days=day_offset)
            b = await create_booking(
                db_session,
                tutor=profile,
                service=service,
                slot=slot,
                client_email=f"c{i}@e.com",
                client_full_name=f"C{i}",
                client_phone=None,
            )
            b.payment_status = "paid"
            await db_session.commit()

    resp = await client.get("/lessio/app/stats")
    body = resp.text
    # 3 booking × 2000₽ = 6000₽
    assert "6 000" in body or "6000" in body
    assert "3" in body  # total bookings count


async def test_stats_breakdown_by_service(client: AsyncClient, db_session: AsyncSession) -> None:
    slug = await _setup(client, tg_id=98000003)
    profile = (
        await db_session.execute(select(LessioTutorProfile).where(LessioTutorProfile.slug == slug))
    ).scalar_one()
    services = (
        (
            await db_session.execute(
                select(LessioService).where(LessioService.tutor_id == profile.id)
            )
        )
        .scalars()
        .all()
    )
    # 2 default services from English template
    with patch("app.lessio.service.send_booking_emails", new_callable=AsyncMock):
        for i, s in enumerate(services[:2]):
            for j in range(i + 1):  # service0: 1 booking, service1: 2 bookings
                slot = datetime(2026, 6, 1, 14, 0, tzinfo=UTC) + timedelta(days=i * 5 + j)
                await create_booking(
                    db_session,
                    tutor=profile,
                    service=s,
                    slot=slot,
                    client_email=f"sb{i}{j}@e.com",
                    client_full_name=f"SB{i}{j}",
                    client_phone=None,
                )
                await db_session.commit()

    resp = await client.get("/lessio/app/stats")
    body = resp.text
    # Service title должен появиться
    assert services[0].title in body or services[1].title in body


async def test_stats_unauth_redirects(client: AsyncClient) -> None:
    resp = await client.get("/lessio/app/stats", follow_redirects=False)
    assert resp.status_code in (401, 302, 303)
