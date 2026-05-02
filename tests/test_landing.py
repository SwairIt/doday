"""Integration tests for the landing page (anonymous vs logged-in)."""

from datetime import UTC, datetime

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.schemas import RegisterIn
from app.auth.service import register_user


async def test_landing_anonymous_shows_login_links(client: AsyncClient) -> None:
    response = await client.get("/")
    assert response.status_code == 200
    assert "Войти" in response.text
    assert "Зарегистрироваться" in response.text


async def test_landing_logged_in_shows_email(client: AsyncClient, db_session: AsyncSession) -> None:
    user = await register_user(
        db_session, RegisterIn(email="kid@school.ru", password="strongpass123")
    )
    user.email_verified_at = datetime.now(UTC)
    await db_session.commit()

    await client.post(
        "/auth/login",
        data={"email": "kid@school.ru", "password": "strongpass123"},
    )

    response = await client.get("/")
    assert response.status_code == 200
    assert "kid@school.ru" in response.text
