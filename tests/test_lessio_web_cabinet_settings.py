"""Lessio cabinet: /lessio/app/settings — view + update profile."""

from __future__ import annotations

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.lessio.models import LessioTutorProfile


async def _register_and_setup(client: AsyncClient, *, tg_id: int) -> str:
    slug = f"set_{tg_id}"
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


async def test_settings_page_renders(client: AsyncClient, db_session: AsyncSession) -> None:
    await _register_and_setup(client, tg_id=71000001)
    resp = await client.get("/lessio/app/settings")
    assert resp.status_code == 200
    body = resp.text
    assert 'name="bio"' in body
    assert 'name="default_meeting_url_template"' in body
    assert 'name="notification_email"' in body


async def test_settings_post_updates_profile(client: AsyncClient, db_session: AsyncSession) -> None:
    slug = await _register_and_setup(client, tg_id=71000002)
    resp = await client.post(
        "/lessio/app/settings",
        data={
            "bio": "Новое био",
            "default_meeting_url_template": "https://zoom.us/j/123",
            "notification_email": "notify@e.com",
        },
        follow_redirects=False,
    )
    assert resp.status_code in (302, 303)

    profile = (
        await db_session.execute(select(LessioTutorProfile).where(LessioTutorProfile.slug == slug))
    ).scalar_one()
    assert profile.bio == "Новое био"
    assert profile.default_meeting_url_template == "https://zoom.us/j/123"
    assert profile.notification_email == "notify@e.com"


async def test_settings_unauth_redirects(client: AsyncClient) -> None:
    resp = await client.get("/lessio/app/settings", follow_redirects=False)
    assert resp.status_code in (401, 302, 303)
