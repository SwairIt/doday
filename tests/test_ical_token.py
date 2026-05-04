"""Tests for the long-lived per-user ical token endpoints."""

from datetime import UTC, datetime

from httpx import AsyncClient


async def test_get_token_creates_one(logged_in_client: AsyncClient) -> None:
    response = await logged_in_client.get("/api/profile/ical-token")
    assert response.status_code == 200
    body = response.json()
    assert body["token"]
    assert len(body["token"]) >= 24
    assert body["url"].startswith("/api/calendar/feed/") and body["url"].endswith(".ics")


async def test_get_token_is_idempotent(logged_in_client: AsyncClient) -> None:
    first = (await logged_in_client.get("/api/profile/ical-token")).json()["token"]
    second = (await logged_in_client.get("/api/profile/ical-token")).json()["token"]
    assert first == second


async def test_rotate_changes_token(logged_in_client: AsyncClient) -> None:
    first = (await logged_in_client.get("/api/profile/ical-token")).json()["token"]
    rotated = (await logged_in_client.post("/api/profile/ical-token/rotate")).json()["token"]
    assert first != rotated
    again = (await logged_in_client.get("/api/profile/ical-token")).json()["token"]
    assert again == rotated


async def test_token_feed_works_without_cookie(
    logged_in_client: AsyncClient, client: AsyncClient
) -> None:
    today_iso = datetime.now(UTC).date().isoformat() + "T18:00:00Z"
    await logged_in_client.post(
        "/api/tasks", json={"title": "Token feed task", "due_at": today_iso}
    )
    token = (await logged_in_client.get("/api/profile/ical-token")).json()["token"]
    # `client` fixture has no auth cookies — proves token-only access works.
    response = await client.get(f"/api/calendar/feed/{token}.ics")
    assert response.status_code == 200
    assert "BEGIN:VCALENDAR" in response.text
    assert "Token feed task" in response.text


async def test_unknown_token_404(client: AsyncClient) -> None:
    response = await client.get("/api/calendar/feed/" + ("x" * 32) + ".ics")
    assert response.status_code == 404


async def test_short_token_404(client: AsyncClient) -> None:
    response = await client.get("/api/calendar/feed/short.ics")
    assert response.status_code == 404


async def test_old_token_invalid_after_rotate(
    logged_in_client: AsyncClient, client: AsyncClient
) -> None:
    old = (await logged_in_client.get("/api/profile/ical-token")).json()["token"]
    response_ok = await client.get(f"/api/calendar/feed/{old}.ics")
    assert response_ok.status_code == 200
    await logged_in_client.post("/api/profile/ical-token/rotate")
    response_after = await client.get(f"/api/calendar/feed/{old}.ics")
    assert response_after.status_code == 404
