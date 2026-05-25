"""Lessio cabinet: /lessio/app/services — list + create + edit + toggle-active."""

from __future__ import annotations

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.lessio.models import LessioService, LessioTutorProfile


async def _setup(client: AsyncClient, *, tg_id: int) -> str:
    slug = f"svc_{tg_id}"
    await client.post(
        "/lessio/auth/register",
        data={"email": f"sv{tg_id}@e.com", "password": "strongpass123"},
        follow_redirects=False,
    )
    await client.post(
        "/lessio/app/setup-profile",
        data={"slug": slug, "display_name": "T", "niche": "english"},
        follow_redirects=False,
    )
    return slug


async def test_services_page_lists_default_services(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _setup(client, tg_id=72000001)
    resp = await client.get("/lessio/app/services")
    assert resp.status_code == 200
    # Default английский templates созданы при setup-profile
    assert "Английский" in resp.text


async def test_services_create_new(client: AsyncClient, db_session: AsyncSession) -> None:
    slug = await _setup(client, tg_id=72000002)
    resp = await client.post(
        "/lessio/app/services",
        data={
            "title": "Спецкурс TOEFL",
            "duration_minutes": "90",
            "price_kopecks": "300000",
        },
        follow_redirects=False,
    )
    assert resp.status_code in (302, 303)

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
    assert any(s.title == "Спецкурс TOEFL" for s in services)
    new = next(s for s in services if s.title == "Спецкурс TOEFL")
    assert new.duration_minutes == 90
    assert new.price_kopecks == 300000


async def test_services_toggle_active(client: AsyncClient, db_session: AsyncSession) -> None:
    slug = await _setup(client, tg_id=72000003)
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
    assert service.is_active is True

    resp = await client.post(
        f"/lessio/app/services/{service.id}/toggle-active", follow_redirects=False
    )
    assert resp.status_code in (302, 303)

    await db_session.refresh(service)
    assert service.is_active is False


async def test_services_edit(client: AsyncClient, db_session: AsyncSession) -> None:
    slug = await _setup(client, tg_id=72000004)
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
    original_title = service.title

    resp = await client.post(
        f"/lessio/app/services/{service.id}/edit",
        data={
            "title": "Обновлённое название",
            "duration_minutes": "45",
            "price_kopecks": "200000",
        },
        follow_redirects=False,
    )
    assert resp.status_code in (302, 303)

    await db_session.refresh(service)
    assert service.title == "Обновлённое название"
    assert service.title != original_title
    assert service.duration_minutes == 45
    assert service.price_kopecks == 200000
