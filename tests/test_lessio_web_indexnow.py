"""IndexNow integration: ping at setup-profile and on slug change in settings."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings


@pytest.fixture
def _indexnow_key(monkeypatch: pytest.MonkeyPatch) -> str:
    key = "abc123def456ghi7"
    monkeypatch.setattr(get_settings(), "indexnow_key", key)
    return key


async def test_indexnow_key_endpoint_serves_key(client: AsyncClient, _indexnow_key: str) -> None:
    resp = await client.get(f"/{_indexnow_key}.txt")
    assert resp.status_code == 200
    assert resp.text.strip() == _indexnow_key
    assert "text/plain" in resp.headers["content-type"]


async def test_indexnow_key_endpoint_404_when_not_configured(
    client: AsyncClient,
) -> None:
    resp = await client.get("/missing-key.txt")
    assert resp.status_code == 404


async def test_indexnow_key_endpoint_404_for_wrong_key(
    client: AsyncClient, _indexnow_key: str
) -> None:
    resp = await client.get("/wrong-key.txt")
    assert resp.status_code == 404


@patch("app.lessio.indexnow.ping_indexnow", new_callable=AsyncMock, return_value=True)
async def test_setup_profile_pings_indexnow(
    mock_ping: AsyncMock,
    client: AsyncClient,
    db_session: AsyncSession,
    _indexnow_key: str,
) -> None:
    await client.post(
        "/lessio/auth/register",
        data={"email": "in@e.com", "password": "strongpass123"},
        follow_redirects=False,
    )
    resp = await client.post(
        "/lessio/app/setup-profile",
        data={"slug": "indexnow_t", "display_name": "I", "niche": "english"},
        follow_redirects=False,
    )
    assert resp.status_code in (302, 303)
    mock_ping.assert_awaited_once()
    urls = mock_ping.await_args.kwargs["urls"]
    assert any("/u/indexnow_t" in u for u in urls)


@patch("app.lessio.indexnow.ping_indexnow", new_callable=AsyncMock, return_value=True)
async def test_settings_slug_change_pings_indexnow(
    mock_ping: AsyncMock,
    client: AsyncClient,
    db_session: AsyncSession,
    _indexnow_key: str,
) -> None:
    # Initial signup (ping #1)
    await client.post(
        "/lessio/auth/register",
        data={"email": "in2@e.com", "password": "strongpass123"},
        follow_redirects=False,
    )
    await client.post(
        "/lessio/app/setup-profile",
        data={"slug": "old_slug_x", "display_name": "X", "niche": "english"},
        follow_redirects=False,
    )
    mock_ping.reset_mock()

    # Change slug → ping again with new URL
    resp = await client.post(
        "/lessio/app/settings",
        data={
            "slug": "new_slug_x",
            "display_name": "X",
            "niche": "english",
            "avatar_emoji": "👨‍🏫",
        },
        follow_redirects=False,
    )
    assert resp.status_code in (302, 303)
    mock_ping.assert_awaited_once()
    urls = mock_ping.await_args.kwargs["urls"]
    assert any("/u/new_slug_x" in u for u in urls)
