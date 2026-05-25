"""Dynamic per-tutor OG-image SVG render."""

from __future__ import annotations

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.lessio.og_image import render_tutor_og_svg
from app.lessio.service import auto_onboard_tutor, create_tutor_profile


async def test_og_svg_contains_display_name(db_session: AsyncSession) -> None:
    user, _ = await auto_onboard_tutor(db_session, telegram_user_id=80000001)
    tutor = await create_tutor_profile(
        db_session,
        user=user,
        slug="og_test",
        display_name="Анна · Английский",
        niche="english",
    )
    await db_session.commit()
    svg = render_tutor_og_svg(tutor)
    assert isinstance(svg, bytes)
    assert b"<svg" in svg
    assert "Анна".encode() in svg
    assert b'width="1200"' in svg
    assert b'height="630"' in svg


async def test_og_svg_escapes_html_chars(db_session: AsyncSession) -> None:
    user, _ = await auto_onboard_tutor(db_session, telegram_user_id=80000002)
    tutor = await create_tutor_profile(
        db_session,
        user=user,
        slug="og_xss",
        display_name="<script>alert(1)</script>",
        niche="english",
    )
    await db_session.commit()
    svg = render_tutor_og_svg(tutor)
    assert b"<script>" not in svg
    assert b"&lt;script&gt;" in svg


async def test_og_svg_endpoint(client: AsyncClient, db_session: AsyncSession) -> None:
    user, _ = await auto_onboard_tutor(db_session, telegram_user_id=80000003)
    await create_tutor_profile(
        db_session,
        user=user,
        slug="og_endpoint",
        display_name="SVG Tutor",
        niche="english",
    )
    await db_session.commit()
    resp = await client.get("/u/og_endpoint/og.svg")
    assert resp.status_code == 200
    assert "image/svg" in resp.headers["content-type"]
    assert b"SVG Tutor" in resp.content
    # 404 для unknown
    r404 = await client.get("/u/nonexistent_one/og.svg")
    assert r404.status_code == 404
