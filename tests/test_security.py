"""Cross-cutting security behaviours: same-origin CSRF defence."""

from httpx import AsyncClient


async def test_cross_origin_post_blocked(logged_in_client: AsyncClient) -> None:
    """A state-changing POST presenting a foreign Origin is rejected (403)."""
    resp = await logged_in_client.post(
        "/api/billing/change-tier",
        json={"tier": "pro"},
        headers={"origin": "http://evil.example"},
    )
    assert resp.status_code == 403


async def test_cross_origin_via_referer_blocked(logged_in_client: AsyncClient) -> None:
    resp = await logged_in_client.post(
        "/api/billing/change-tier",
        json={"tier": "pro"},
        headers={"referer": "http://evil.example/attack"},
    )
    assert resp.status_code == 403


async def test_same_origin_post_allowed(logged_in_client: AsyncClient) -> None:
    """Same-origin Origin (matching the test Host 'test') passes CSRF check.

    Use a safe endpoint (downgrade to free) — upgrade-to-pro is now 402 Payment
    Required by design (security fix shipped with Telegram Stars 2026-05-24)."""
    resp = await logged_in_client.post(
        "/api/billing/change-tier",
        json={"tier": "free"},
        headers={"origin": "http://test"},
    )
    assert resp.status_code == 200


async def test_no_origin_post_allowed(logged_in_client: AsyncClient) -> None:
    """No Origin/Referer (server-to-server, or same-origin fetch) is not blocked."""
    resp = await logged_in_client.post("/api/billing/change-tier", json={"tier": "free"})
    assert resp.status_code == 200


async def test_cross_origin_get_not_blocked(logged_in_client: AsyncClient) -> None:
    """Safe methods are never CSRF-checked."""
    resp = await logged_in_client.get("/api/billing/me", headers={"origin": "http://evil.example"})
    assert resp.status_code == 200
