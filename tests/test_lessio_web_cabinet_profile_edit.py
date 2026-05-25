"""Lessio cabinet: /lessio/app/settings — расширение, редактирование slug/display_name/niche/avatar_emoji."""

from __future__ import annotations

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.lessio.models import LessioTutorProfile


async def _setup(client: AsyncClient, *, tg_id: int) -> str:
    slug = f"pe_{tg_id}"
    await client.post(
        "/lessio/auth/register",
        data={"email": f"pe{tg_id}@e.com", "password": "strongpass123"},
        follow_redirects=False,
    )
    await client.post(
        "/lessio/app/setup-profile",
        data={"slug": slug, "display_name": "T", "niche": "english"},
        follow_redirects=False,
    )
    return slug


async def test_settings_page_shows_editable_slug_and_name(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Settings template должен включать input для slug, display_name, niche, avatar_emoji."""
    await _setup(client, tg_id=90000001)
    resp = await client.get("/lessio/app/settings")
    body = resp.text
    assert 'name="slug"' in body
    assert 'name="display_name"' in body
    assert 'name="niche"' in body
    assert 'name="avatar_emoji"' in body


async def test_settings_update_slug_and_display_name(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    initial_slug = await _setup(client, tg_id=90000002)
    resp = await client.post(
        "/lessio/app/settings",
        data={
            "slug": "new_slug_v2",
            "display_name": "Новое Имя",
            "niche": "ielts",
            "avatar_emoji": "🎓",
            "bio": "Обновлено",
            "default_meeting_url_template": "",
            "notification_email": "",
        },
        follow_redirects=False,
    )
    assert resp.status_code in (302, 303)

    # Old slug should not exist anymore
    old = (
        await db_session.execute(
            select(LessioTutorProfile).where(LessioTutorProfile.slug == initial_slug)
        )
    ).scalar_one_or_none()
    assert old is None

    updated = (
        await db_session.execute(
            select(LessioTutorProfile).where(LessioTutorProfile.slug == "new_slug_v2")
        )
    ).scalar_one()
    assert updated.display_name == "Новое Имя"
    assert updated.niche == "ielts"
    assert updated.avatar_emoji == "🎓"
    assert updated.bio == "Обновлено"


async def test_settings_rejects_duplicate_slug(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Если slug уже занят другим tutor — 400, slug не меняется."""
    # First tutor with target slug
    await client.post(
        "/lessio/auth/register",
        data={"email": "first@e.com", "password": "strongpass123"},
        follow_redirects=False,
    )
    await client.post(
        "/lessio/app/setup-profile",
        data={"slug": "claimed_slug", "display_name": "First", "niche": "english"},
        follow_redirects=False,
    )
    # Logout, register second
    await client.post("/auth/logout", follow_redirects=False)

    second_initial = await _setup(client, tg_id=90000003)

    resp = await client.post(
        "/lessio/app/settings",
        data={
            "slug": "claimed_slug",  # taken
            "display_name": "Second",
            "niche": "english",
            "avatar_emoji": "👨‍🏫",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 400

    # Slug must remain unchanged
    profile = (
        await db_session.execute(
            select(LessioTutorProfile).where(LessioTutorProfile.slug == second_initial)
        )
    ).scalar_one()
    assert profile.display_name == "T"  # not changed


async def test_settings_rejects_invalid_slug_format(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _setup(client, tg_id=90000004)
    resp = await client.post(
        "/lessio/app/settings",
        data={
            "slug": "Invalid Slug With Spaces!",
            "display_name": "X",
            "niche": "english",
            "avatar_emoji": "👨‍🏫",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 400


async def test_settings_keeps_unchanged_when_only_bio_updated(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Submit с тем же slug — должен пройти без 'занят' ошибки."""
    slug = await _setup(client, tg_id=90000005)
    resp = await client.post(
        "/lessio/app/settings",
        data={
            "slug": slug,  # same as own
            "display_name": "T",
            "niche": "english",
            "avatar_emoji": "👨‍🏫",
            "bio": "Just updated bio text",
        },
        follow_redirects=False,
    )
    assert resp.status_code in (302, 303)

    profile = (
        await db_session.execute(select(LessioTutorProfile).where(LessioTutorProfile.slug == slug))
    ).scalar_one()
    assert profile.bio == "Just updated bio text"
