"""Integration tests for the Doday Tasks landing page at /doday.

(Moved from `/` on 2026-05-25 when root became the studio hub — see tests/test_hub.py.)
"""

from datetime import UTC, datetime

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.schemas import RegisterIn
from app.auth.service import register_user


async def test_landing_anonymous_shows_login_links(client: AsyncClient) -> None:
    response = await client.get("/doday")
    assert response.status_code == 200
    assert "Войти" in response.text
    assert "Создать аккаунт" in response.text  # primary CTA
    assert "Doday" in response.text


async def test_landing_logged_in_redirects_to_app(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Logged-in users skip the marketing landing — straight to /app/today."""
    user = await register_user(
        db_session, RegisterIn(email="kid@school.ru", password="strongpass123")
    )
    user.email_verified_at = datetime.now(UTC)
    await db_session.commit()

    await client.post(
        "/auth/login",
        data={"email": "kid@school.ru", "password": "strongpass123"},
    )

    response = await client.get("/doday", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"] == "/app/today"
