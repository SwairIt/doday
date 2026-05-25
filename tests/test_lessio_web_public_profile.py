"""Public profile /u/<slug> — render + SEO meta + 404."""

from __future__ import annotations

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.lessio.service import (
    auto_onboard_tutor,
    create_services_from_template,
    create_tutor_profile,
)


async def test_unknown_slug_returns_404(client: AsyncClient) -> None:
    resp = await client.get("/u/nonexistent")
    assert resp.status_code == 404


async def test_public_profile_renders_with_services(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    user, _ = await auto_onboard_tutor(db_session, telegram_user_id=30000001)
    tutor = await create_tutor_profile(
        db_session,
        user=user,
        slug="anna_eng",
        display_name="Anna · English",
        niche="english",
        bio="5 лет опыта",
    )
    await create_services_from_template(db_session, tutor=tutor, niche="english")
    await db_session.commit()

    resp = await client.get("/u/anna_eng")
    assert resp.status_code == 200
    body = resp.text
    assert "Anna · English" in body
    assert "5 лет опыта" in body
    assert "Английский" in body  # service title from template


async def test_public_profile_has_seo_meta(client: AsyncClient, db_session: AsyncSession) -> None:
    user, _ = await auto_onboard_tutor(db_session, telegram_user_id=30000002)
    await create_tutor_profile(
        db_session,
        user=user,
        slug="seo_test",
        display_name="SEO Tutor",
        niche="english",
        bio="testing seo",
    )
    await db_session.commit()

    resp = await client.get("/u/seo_test")
    body = resp.text
    assert '<link rel="canonical" href="https://getdoday.ru/u/seo_test"' in body
    assert 'property="og:title"' in body
    assert 'property="og:url"' in body
    assert 'content="https://getdoday.ru/u/seo_test"' in body
    assert "application/ld+json" in body
    assert '"@type": "Person"' in body or '"@type":"Person"' in body
    assert "SEO Tutor" in body


async def test_inactive_profile_returns_404(client: AsyncClient, db_session: AsyncSession) -> None:
    user, _ = await auto_onboard_tutor(db_session, telegram_user_id=30000003)
    tutor = await create_tutor_profile(
        db_session, user=user, slug="inactive_one", display_name="Inactive"
    )
    tutor.is_active = False
    await db_session.commit()

    resp = await client.get("/u/inactive_one")
    assert resp.status_code == 404


async def test_sitemap_includes_active_tutors(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    user, _ = await auto_onboard_tutor(db_session, telegram_user_id=30000004)
    await create_tutor_profile(
        db_session, user=user, slug="sitemap_one", display_name="Sitemap Tutor"
    )
    # And an inactive one which must NOT appear
    user2, _ = await auto_onboard_tutor(db_session, telegram_user_id=30000005)
    inactive = await create_tutor_profile(
        db_session, user=user2, slug="sitemap_hidden", display_name="Hidden"
    )
    inactive.is_active = False
    await db_session.commit()

    resp = await client.get("/sitemap.xml")
    assert resp.status_code == 200
    body = resp.text
    assert "/u/sitemap_one" in body
    assert "/u/sitemap_hidden" not in body


async def test_robots_allows_u_prefix(client: AsyncClient) -> None:
    resp = await client.get("/robots.txt")
    assert resp.status_code == 200
    body = resp.text
    assert "Allow: /u/" in body
