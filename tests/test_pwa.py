"""Tests for PWA endpoints — manifest + service worker."""

import json

from httpx import AsyncClient


async def test_manifest_endpoint(client: AsyncClient) -> None:
    response = await client.get("/manifest.webmanifest")
    assert response.status_code == 200
    assert "manifest" in response.headers["content-type"]
    body = json.loads(response.text)
    assert body["name"] == "Doday — todo для всех"
    assert body["start_url"] == "/app/today"
    assert body["display"] == "standalone"
    assert len(body["icons"]) >= 1


async def test_service_worker_endpoint(client: AsyncClient) -> None:
    response = await client.get("/service-worker.js")
    assert response.status_code == 200
    assert "javascript" in response.headers["content-type"]
    assert "self.addEventListener" in response.text
    assert "doday-shell" in response.text


async def test_base_links_manifest(logged_in_client: AsyncClient) -> None:
    body = (await logged_in_client.get("/app/today")).text
    assert 'rel="manifest"' in body
    assert "/service-worker.js" in body
