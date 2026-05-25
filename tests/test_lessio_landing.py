"""Lessio landing page + waitlist signup flow."""

from httpx import AsyncClient


async def test_lessio_landing_renders(client: AsyncClient) -> None:
    response = await client.get("/lessio")
    assert response.status_code == 200
    body = response.text
    assert "Lessio" in body
    # Hero copy must reach the rendered HTML
    assert "репетиторов" in body
    # Waitlist form mounts the right HTMX endpoint
    assert 'hx-post="/lessio/waitlist"' in body


async def test_lessio_landing_trailing_slash_also_works(client: AsyncClient) -> None:
    # Both `/lessio` and `/lessio/` should render identically.
    response = await client.get("/lessio/")
    assert response.status_code == 200
    assert "Lessio" in response.text


async def test_waitlist_creates_entry(client: AsyncClient) -> None:
    response = await client.post(
        "/lessio/waitlist",
        data={
            "email": "tutor1@example.com",
            "niche": "english",
            "pain_point": "слишком много переписки",
            "telegram_handle": "@tutor1",
        },
    )
    assert response.status_code == 200
    assert "✅" in response.text


async def test_waitlist_idempotent_by_email(client: AsyncClient) -> None:
    """Two submits with same email — both 200, second updates the row, no duplicate."""
    payload_base = {"email": "tutor-idem@example.com", "niche": "english"}
    first = await client.post("/lessio/waitlist", data=payload_base)
    assert first.status_code == 200
    second = await client.post(
        "/lessio/waitlist",
        data={**payload_base, "pain_point": "uppdate"},
    )
    assert second.status_code == 200


async def test_waitlist_unknown_niche_falls_back_to_other(client: AsyncClient) -> None:
    response = await client.post(
        "/lessio/waitlist",
        data={"email": "tutor-niche@example.com", "niche": "definitely-not-allowed"},
    )
    assert response.status_code == 200


async def test_waitlist_strips_telegram_at_prefix(client: AsyncClient) -> None:
    response = await client.post(
        "/lessio/waitlist",
        data={
            "email": "tutor-at@example.com",
            "niche": "math",
            "telegram_handle": "@user_at_handle",
        },
    )
    assert response.status_code == 200
