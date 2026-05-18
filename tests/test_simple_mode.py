"""Tests for the simplified-mode views."""

from __future__ import annotations

from httpx import AsyncClient


async def test_simple_today_requires_auth(client: AsyncClient) -> None:
    response = await client.get("/app/simple/today")
    assert response.status_code == 401


async def test_simple_today_renders_for_authed_user(
    logged_in_client: AsyncClient,
) -> None:
    response = await logged_in_client.get("/app/simple/today")
    assert response.status_code == 200
    body = response.text
    assert "Doday" in body
    assert "простой" in body
    assert 'href="/app/today"' in body
