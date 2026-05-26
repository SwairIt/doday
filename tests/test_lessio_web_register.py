"""Lessio web register-flow: /lessio/auth/register → /lessio/app/setup-profile → profile + services."""

from __future__ import annotations

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.lessio.models import LessioService, LessioTutorProfile


async def test_register_page_renders(client: AsyncClient) -> None:
    resp = await client.get("/lessio/auth/register")
    assert resp.status_code == 200
    body = resp.text
    assert "регистрация" in body.lower()
    assert 'name="email"' in body
    assert 'name="password"' in body


async def test_register_creates_user_and_redirects_to_setup(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    resp = await client.post(
        "/lessio/auth/register",
        data={"email": "tutor1@example.com", "password": "strongpass123"},
        follow_redirects=False,
    )
    assert resp.status_code in (302, 303)
    assert "/lessio/app/setup-profile" in resp.headers["location"]

    user = (
        await db_session.execute(select(User).where(User.email == "tutor1@example.com"))
    ).scalar_one_or_none()
    assert user is not None
    assert user.password_hash is not None


async def test_setup_profile_creates_tutor_and_services(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await client.post(
        "/lessio/auth/register",
        data={"email": "tutor2@example.com", "password": "strongpass123"},
        follow_redirects=False,
    )
    resp = await client.post(
        "/lessio/app/setup-profile",
        data={
            "slug": "anna_eng",
            "display_name": "Anna · English",
            "niche": "english",
            "bio": "5 лет опыта",
        },
        follow_redirects=False,
    )
    assert resp.status_code in (302, 303)
    assert resp.headers["location"].endswith("/lessio/app/today")

    profile = (
        await db_session.execute(
            select(LessioTutorProfile).where(LessioTutorProfile.slug == "anna_eng")
        )
    ).scalar_one()
    assert profile.display_name == "Anna · English"
    assert profile.bio == "5 лет опыта"

    services = (
        (
            await db_session.execute(
                select(LessioService).where(LessioService.tutor_id == profile.id)
            )
        )
        .scalars()
        .all()
    )
    assert len(services) >= 1
    assert any("Английский" in s.title for s in services)


async def test_setup_profile_rejects_duplicate_slug(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await client.post(
        "/lessio/auth/register",
        data={"email": "t3@e.com", "password": "strongpass456"},
        follow_redirects=False,
    )
    first = await client.post(
        "/lessio/app/setup-profile",
        data={"slug": "popular", "display_name": "First", "niche": "english"},
        follow_redirects=False,
    )
    assert first.status_code in (302, 303)

    # Switch identity: clear session cookie before second register.
    await client.post("/lessio/auth/logout", follow_redirects=False)
    await client.post(
        "/lessio/auth/register",
        data={"email": "t4@e.com", "password": "strongpass456"},
        follow_redirects=False,
    )
    resp = await client.post(
        "/lessio/app/setup-profile",
        data={"slug": "popular", "display_name": "Second", "niche": "english"},
        follow_redirects=False,
    )
    assert resp.status_code == 400
    assert "занят" in resp.text
