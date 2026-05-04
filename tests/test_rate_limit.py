"""Tests for rate-limiting on login + register endpoints."""

from httpx import AsyncClient

from app.auth.rate_limit import reset_all


async def test_register_rate_limit_kicks_in(client: AsyncClient) -> None:
    reset_all()
    # 5 attempts allowed per minute → 6th is 429.
    for _ in range(5):
        r = await client.post(
            "/auth/register",
            data={
                "email": "x@y.com",
                "password": "weakpass",
            },  # missing agree → 400, but rate-limiter still counts
        )
        assert r.status_code in (400, 422)
    r = await client.post(
        "/auth/register",
        data={"email": "x@y.com", "password": "weakpass"},
    )
    assert r.status_code == 429
    assert "Слишком" in r.text


async def test_login_rate_limit_per_email(client: AsyncClient) -> None:
    reset_all()
    # 10 wrong logins for the same email → 11th is 429.
    for _ in range(10):
        r = await client.post(
            "/auth/login",
            data={"email": "nobody@nowhere.com", "password": "wrong"},
        )
        assert r.status_code == 401
    r = await client.post(
        "/auth/login",
        data={"email": "nobody@nowhere.com", "password": "wrong"},
    )
    assert r.status_code == 429


async def test_login_rate_limit_does_not_block_other_emails(client: AsyncClient) -> None:
    reset_all()
    for _ in range(10):
        await client.post("/auth/login", data={"email": "a@b.com", "password": "wrong"})
    # Different email — fresh bucket.
    r = await client.post("/auth/login", data={"email": "c@d.com", "password": "wrong"})
    assert r.status_code == 401  # not 429


async def test_successful_login_resets_rate_limit(logged_in_client: AsyncClient) -> None:
    """Successful authentication clears the bucket so the user can keep going."""
    reset_all()
    # Burn 9 wrong tries for our test user.
    for _ in range(9):
        await logged_in_client.post(
            "/auth/login", data={"email": "logged-in@example.com", "password": "wrong"}
        )
    # Now log in successfully — should reset.
    r = await logged_in_client.post(
        "/auth/login",
        data={"email": "logged-in@example.com", "password": "strongpass123"},
        follow_redirects=False,
    )
    assert r.status_code == 303
    # Burn 10 more wrongs — still allowed because bucket was reset.
    for _ in range(10):
        rr = await logged_in_client.post(
            "/auth/login", data={"email": "logged-in@example.com", "password": "wrong"}
        )
        assert rr.status_code == 401, f"got {rr.status_code} — bucket not reset"
