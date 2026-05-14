"""Tests for the unified /app/settings screen (Phase β)."""

from httpx import AsyncClient


async def test_settings_page_renders(logged_in_client: AsyncClient) -> None:
    r = await logged_in_client.get("/app/settings")
    assert r.status_code == 200
    assert "Настройки" in r.text


async def test_profile_redirects_to_settings(logged_in_client: AsyncClient) -> None:
    r = await logged_in_client.get("/app/profile", follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"] == "/app/settings"


async def test_settings_unauth_redirects(client: AsyncClient) -> None:
    r = await client.get("/app/settings", follow_redirects=False)
    assert r.status_code in (302, 303, 307)
