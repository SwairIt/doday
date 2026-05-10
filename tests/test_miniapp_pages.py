"""Smoke-tests for /miniapp/* tab pages — auth-redirect + render."""

import pytest
from httpx import AsyncClient

PAGES = ["/miniapp/", "/miniapp/inbox", "/miniapp/calendar", "/miniapp/projects", "/miniapp/me"]


@pytest.mark.parametrize("path", PAGES)
async def test_miniapp_page_unauth_redirects_to_link(client: AsyncClient, path: str) -> None:
    r = await client.get(path, follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"] == "/miniapp/link"


@pytest.mark.parametrize("path", PAGES)
async def test_miniapp_page_authed_renders(logged_in_client: AsyncClient, path: str) -> None:
    r = await logged_in_client.get(path, follow_redirects=False)
    assert r.status_code == 200
    body = r.text
    assert "Doday" in body
    assert "miniapp-nav" in body  # bottom-nav present


async def test_miniapp_assets_js_served(client: AsyncClient) -> None:
    r = await client.get("/miniapp/assets/miniapp.js")
    assert r.status_code == 200
    assert "javascript" in r.headers["content-type"]
    assert "Telegram.WebApp" in r.text
    assert "applyTheme" in r.text
    assert "attemptAuth" in r.text
    # Auth-success on link-page should redirect to /miniapp/
    assert "if (onLinkPage)" in r.text or "onLinkPage" in r.text


async def test_miniapp_link_page_unauth_renders(client: AsyncClient) -> None:
    """/miniapp/link не требует auth — это onboarding-экран."""
    r = await client.get("/miniapp/link?telegram_user_id=12345")
    assert r.status_code == 200
    assert "Привяжи аккаунт Doday" in r.text
    assert "12345" in r.text
    assert "miniapp-nav" in r.text  # bottom-nav present


async def test_miniapp_link_authed_redirects_to_today(logged_in_client: AsyncClient) -> None:
    """Если юзер УЖЕ залогинен — onboarding не нужен, редирект на /."""
    r = await logged_in_client.get("/miniapp/link", follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"] == "/miniapp/"
