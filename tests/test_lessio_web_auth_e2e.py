"""End-to-end auth flow для Lessio: register → cabinet → logout → /lessio → login → cabinet.

Цель — гарантировать что Lessio-tutor НИКОГДА не попадает в Doday-cabinet
(/doday/app/today) — только в /lessio/app/today. После logout — возврат на /lessio,
не на Doday hub /.
"""

from __future__ import annotations

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession


async def test_lessio_register_then_logout_then_login_keeps_user_in_lessio(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # 1. Register
    r1 = await client.post(
        "/lessio/auth/register",
        data={"email": "e2e@e.com", "password": "strongpass123"},
        follow_redirects=False,
    )
    assert r1.status_code in (302, 303)
    assert "/lessio/app/setup-profile" in r1.headers["location"]

    # 2. Setup profile
    r2 = await client.post(
        "/lessio/app/setup-profile",
        data={"slug": "e2e_t", "display_name": "E2E", "niche": "english"},
        follow_redirects=False,
    )
    assert r2.status_code in (302, 303)
    assert "/lessio/app/today" in r2.headers["location"]

    # 3. Cabinet works
    r3 = await client.get("/lessio/app/today")
    assert r3.status_code == 200
    assert "E2E" in r3.text

    # 4. Logout — Lessio-scoped (НЕ /auth/logout)
    r4 = await client.post("/lessio/auth/logout", follow_redirects=False)
    assert r4.status_code in (302, 303)
    assert r4.headers["location"] == "/lessio"

    # 5. После logout — cabinet 401
    r5 = await client.get("/lessio/app/today", follow_redirects=False)
    assert r5.status_code in (401, 302, 303)

    # 6. Login через Lessio endpoint
    r6 = await client.get("/lessio/auth/login")
    assert r6.status_code == 200
    assert 'action="/lessio/auth/login"' in r6.text

    r7 = await client.post(
        "/lessio/auth/login",
        data={"email": "e2e@e.com", "password": "strongpass123"},
        follow_redirects=False,
    )
    assert r7.status_code in (302, 303)
    # КЛЮЧЕВОЕ — должен попасть в /lessio/app/today, НЕ /doday/app/today
    assert r7.headers["location"] == "/lessio/app/today"
    assert "/doday/app/today" not in r7.headers["location"].replace("/lessio/app/today", "")

    # 7. Cabinet снова работает
    r8 = await client.get("/lessio/app/today")
    assert r8.status_code == 200
    assert "E2E" in r8.text


async def test_lessio_login_page_redirects_authed_user_to_cabinet(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await client.post(
        "/lessio/auth/register",
        data={"email": "authed@e.com", "password": "strongpass123"},
        follow_redirects=False,
    )
    # User уже залогинен из register → GET /lessio/auth/login должен сразу редирект
    r = await client.get("/lessio/auth/login", follow_redirects=False)
    assert r.status_code in (302, 303)
    assert "/lessio/app/today" in r.headers["location"]


async def test_lessio_login_wrong_password_401(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await client.post(
        "/lessio/auth/register",
        data={"email": "wrong@e.com", "password": "correctpass123"},
        follow_redirects=False,
    )
    await client.post("/lessio/auth/logout", follow_redirects=False)
    r = await client.post(
        "/lessio/auth/login",
        data={"email": "wrong@e.com", "password": "wrongpass456"},
        follow_redirects=False,
    )
    assert r.status_code == 401
    assert "Неверный" in r.text or "неверный" in r.text


async def test_lessio_landing_nav_login_links_to_lessio_not_doday(
    client: AsyncClient,
) -> None:
    """Landing nav «Войти» должна быть на /lessio/auth/login, НЕ /auth/login."""
    r = await client.get("/lessio")
    body = r.text
    assert 'href="/lessio/auth/login"' in body
    # /auth/login (без префикса) НЕ должно быть в landing — это Doday-login
    # Может быть в комментариях, проверяем только в href.
    import re

    doday_login_refs = re.findall(r'href="(/auth/login[^"]*)"', body)
    assert doday_login_refs == [], f"Landing leaks Doday login URLs: {doday_login_refs}"


async def test_lessio_register_page_footer_login_link_lessio_scoped(
    client: AsyncClient,
) -> None:
    r = await client.get("/lessio/auth/register")
    body = r.text
    assert 'href="/lessio/auth/login"' in body
