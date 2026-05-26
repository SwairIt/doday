"""Tests for the unified /doday/app/settings screen (Phase β)."""

from httpx import AsyncClient


async def test_settings_page_renders(logged_in_client: AsyncClient) -> None:
    r = await logged_in_client.get("/doday/app/settings")
    assert r.status_code == 200
    assert "Настройки" in r.text


async def test_profile_redirects_to_settings(logged_in_client: AsyncClient) -> None:
    r = await logged_in_client.get("/doday/app/profile", follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"] == "/doday/app/settings"


async def test_settings_unauth_redirects(client: AsyncClient) -> None:
    # /doday/app/* routes use RequiredUser which raises 401 (not a redirect)
    r = await client.get("/doday/app/settings", follow_redirects=False)
    assert r.status_code == 401
