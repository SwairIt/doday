"""Tests for the school portal integration scaffold (CRUD + stub sync)."""

from httpx import AsyncClient


async def test_list_empty_initially(logged_in_client: AsyncClient) -> None:
    response = await logged_in_client.get("/api/school/integrations")
    assert response.status_code == 200
    assert response.json() == []


async def test_create_integration(logged_in_client: AsyncClient) -> None:
    response = await logged_in_client.post(
        "/api/school/integrations",
        data={"provider": "school_mo", "auth_token": "fake-token-1234567"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["provider"] == "school_mo"
    assert body["enabled"] is True
    assert body["last_sync_at"] is None


async def test_upsert_replaces_existing(logged_in_client: AsyncClient) -> None:
    await logged_in_client.post(
        "/api/school/integrations",
        data={"provider": "school_mo", "auth_token": "first-token-1234"},
    )
    await logged_in_client.post(
        "/api/school/integrations",
        data={"provider": "school_mo", "auth_token": "second-token-5678"},
    )
    listing = (await logged_in_client.get("/api/school/integrations")).json()
    assert len(listing) == 1


async def test_invalid_provider_rejected(logged_in_client: AsyncClient) -> None:
    response = await logged_in_client.post(
        "/api/school/integrations",
        data={"provider": "alien_portal", "auth_token": "fake-token-1234567"},
    )
    assert response.status_code == 422


async def test_short_token_rejected(logged_in_client: AsyncClient) -> None:
    response = await logged_in_client.post(
        "/api/school/integrations",
        data={"provider": "mesh", "auth_token": "x"},
    )
    assert response.status_code == 422


async def test_sync_returns_credentials_needed_error(logged_in_client: AsyncClient) -> None:
    await logged_in_client.post(
        "/api/school/integrations",
        data={"provider": "school_mo", "auth_token": "fake-token-1234567"},
    )
    response = await logged_in_client.post("/api/school/integrations/school_mo/sync")
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is False
    assert body["error"] is not None
    assert "auth_token" in body["error"] or "aupd_token" in body["error"]


async def test_sync_unknown_integration_404(logged_in_client: AsyncClient) -> None:
    response = await logged_in_client.post("/api/school/integrations/mesh/sync")
    assert response.status_code == 404


async def test_delete_integration(logged_in_client: AsyncClient) -> None:
    await logged_in_client.post(
        "/api/school/integrations",
        data={"provider": "mesh", "auth_token": "fake-token-1234567"},
    )
    response = await logged_in_client.delete("/api/school/integrations/mesh")
    assert response.status_code == 204
    listing = (await logged_in_client.get("/api/school/integrations")).json()
    assert listing == []


async def test_help_article_renders(logged_in_client: AsyncClient) -> None:
    body = (await logged_in_client.get("/help/school-integrations")).text
    assert "Школьный портал МО" in body
    assert "aupd_token" in body
    assert "dnevnik.mos.ru" in body


async def test_profile_shows_school_section(logged_in_client: AsyncClient) -> None:
    body = (await logged_in_client.get("/app/profile")).text
    assert "Школьный дневник" in body
    assert "/api/school/integrations" in body
