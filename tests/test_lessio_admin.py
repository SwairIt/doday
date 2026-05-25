"""Lessio admin endpoints — auth, list, stats, delete-by-email."""

from httpx import AsyncClient

from app.config import get_settings

# Set a known admin token for tests; reset_settings_cache is handled per-test below.
_TEST_TOKEN = "lessio-admin-token-for-tests-only"


def _ensure_token() -> None:
    settings = get_settings()
    settings.admin_token = _TEST_TOKEN


async def test_admin_waitlist_requires_token(client: AsyncClient) -> None:
    _ensure_token()
    # No header → 403
    response = await client.get("/api/admin/lessio/waitlist.json")
    assert response.status_code == 403


async def test_admin_waitlist_wrong_token_403(client: AsyncClient) -> None:
    _ensure_token()
    response = await client.get(
        "/api/admin/lessio/waitlist.json",
        headers={"X-Admin-Token": "wrong"},
    )
    assert response.status_code == 403


async def test_admin_waitlist_503_when_admin_token_empty(client: AsyncClient) -> None:
    settings = get_settings()
    saved = settings.admin_token
    settings.admin_token = ""
    try:
        response = await client.get(
            "/api/admin/lessio/waitlist.json",
            headers={"X-Admin-Token": "anything"},
        )
        assert response.status_code == 503
    finally:
        settings.admin_token = saved


async def test_admin_waitlist_list_and_stats(client: AsyncClient) -> None:
    _ensure_token()
    # Seed waitlist via the public endpoint to mirror real usage.
    for i, niche in enumerate(["english", "english", "ielts", "math"]):
        await client.post(
            "/lessio/waitlist",
            data={
                "email": f"user{i}@example.com",
                "niche": niche,
                "pain_point": "pain" if i % 2 == 0 else None,
            },
        )

    # List
    response = await client.get(
        "/api/admin/lessio/waitlist.json",
        headers={"X-Admin-Token": _TEST_TOKEN},
    )
    assert response.status_code == 200
    entries = response.json()
    assert len(entries) == 4
    emails = {e["email"] for e in entries}
    assert emails == {f"user{i}@example.com" for i in range(4)}

    # Stats
    response = await client.get(
        "/api/admin/lessio/waitlist/stats.json",
        headers={"X-Admin-Token": _TEST_TOKEN},
    )
    assert response.status_code == 200
    stats = response.json()
    assert stats["total"] == 4
    assert stats["by_niche"] == {"english": 2, "ielts": 1, "math": 1}
    assert stats["with_pain_point"] == 2
    assert stats["threshold_met"] is False
    assert stats["decision_threshold"] == 100


async def test_admin_delete_by_email(client: AsyncClient) -> None:
    _ensure_token()
    await client.post(
        "/lessio/waitlist",
        data={"email": "to-delete@example.com", "niche": "english"},
    )
    response = await client.delete(
        "/api/admin/lessio/waitlist/by-email",
        params={"email": "to-delete@example.com"},
        headers={"X-Admin-Token": _TEST_TOKEN},
    )
    assert response.status_code == 204

    # Verify gone via stats
    stats_response = await client.get(
        "/api/admin/lessio/waitlist/stats.json",
        headers={"X-Admin-Token": _TEST_TOKEN},
    )
    assert stats_response.json()["total"] == 0
