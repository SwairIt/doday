"""Lessio cabinet: /lessio/app/schedule — working_days + work hours + buffer."""

from __future__ import annotations

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.lessio.models import LessioTutorProfile


async def _setup(client: AsyncClient, *, tg_id: int) -> str:
    slug = f"sch_{tg_id}"
    await client.post(
        "/lessio/auth/register",
        data={"email": f"sc{tg_id}@e.com", "password": "strongpass123"},
        follow_redirects=False,
    )
    await client.post(
        "/lessio/app/setup-profile",
        data={"slug": slug, "display_name": "T", "niche": "english"},
        follow_redirects=False,
    )
    return slug


async def test_schedule_page_renders_defaults(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _setup(client, tg_id=74000001)
    resp = await client.get("/lessio/app/schedule")
    assert resp.status_code == 200
    body = resp.text
    # Default working_days = [1..5] = Mon-Fri, work_start=9*60, work_end=21*60, buffer=15
    assert 'name="work_start_hour"' in body
    assert 'name="work_end_hour"' in body
    assert 'name="buffer_minutes"' in body


async def test_schedule_post_updates_profile(client: AsyncClient, db_session: AsyncSession) -> None:
    slug = await _setup(client, tg_id=74000002)
    resp = await client.post(
        "/lessio/app/schedule",
        data={
            "working_days": ["1", "3", "5", "6"],  # Mon/Wed/Fri/Sat
            "work_start_hour": "10",
            "work_end_hour": "20",
            "buffer_minutes": "30",
        },
        follow_redirects=False,
    )
    assert resp.status_code in (302, 303)

    profile = (
        await db_session.execute(select(LessioTutorProfile).where(LessioTutorProfile.slug == slug))
    ).scalar_one()
    assert profile.working_days == [1, 3, 5, 6]
    assert profile.work_start_minute == 600  # 10:00
    assert profile.work_end_minute == 1200  # 20:00
    assert profile.buffer_minutes == 30


async def test_schedule_rejects_invalid_hours(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _setup(client, tg_id=74000003)
    resp = await client.post(
        "/lessio/app/schedule",
        data={
            "working_days": ["1"],
            "work_start_hour": "20",  # start after end
            "work_end_hour": "10",
            "buffer_minutes": "15",
        },
    )
    assert resp.status_code == 400
