"""Lessio PWA: manifest + service worker для кабинета."""

from __future__ import annotations

from httpx import AsyncClient


async def test_pwa_manifest_endpoint(client: AsyncClient) -> None:
    resp = await client.get("/lessio/app/manifest.webmanifest")
    assert resp.status_code == 200
    assert "application/manifest" in resp.headers["content-type"] or resp.headers[
        "content-type"
    ].startswith("application/json")
    body = resp.json()
    assert body["name"] == "Lessio"
    assert body["start_url"] == "/lessio/app/today"
    assert body["display"] == "standalone"
    assert "icons" in body
    assert len(body["icons"]) >= 1


async def test_pwa_service_worker_endpoint(client: AsyncClient) -> None:
    resp = await client.get("/lessio/app/sw.js")
    assert resp.status_code == 200
    assert "javascript" in resp.headers["content-type"]
    body = resp.text
    # Минимальный SW: install + fetch (network-first)
    assert "addEventListener" in body
    assert "fetch" in body


async def test_cabinet_template_includes_manifest_link(
    client: AsyncClient,
) -> None:
    """Cabinet base shell должен ссылаться на manifest.webmanifest."""
    await client.post(
        "/lessio/auth/register",
        data={"email": "pwa@e.com", "password": "strongpass123"},
        follow_redirects=False,
    )
    await client.post(
        "/lessio/app/setup-profile",
        data={"slug": "pwa_t", "display_name": "P", "niche": "english"},
        follow_redirects=False,
    )
    resp = await client.get("/lessio/app/today")
    body = resp.text
    assert "manifest" in body
    assert "/lessio/app/manifest.webmanifest" in body or "manifest.webmanifest" in body
