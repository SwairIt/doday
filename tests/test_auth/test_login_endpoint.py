"""Integration tests for /auth/login and /auth/logout endpoints."""

from datetime import UTC, datetime

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.schemas import RegisterIn
from app.auth.service import register_user


async def _make_verified(db_session: AsyncSession, email: str = "kid@school.ru") -> None:
    user = await register_user(db_session, RegisterIn(email=email, password="strongpass123"))
    user.email_verified_at = datetime.now(UTC)
    await db_session.commit()


async def test_login_correct_credentials_sets_session(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _make_verified(db_session)
    response = await client.post(
        "/auth/login",
        data={"email": "kid@school.ru", "password": "strongpass123"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    # `?welcome=1` triggers dodayGoal('login') in base.html on first paint.
    assert response.headers["location"] == "/app/today?welcome=1"
    assert "session" in response.cookies


async def test_login_wrong_password(client: AsyncClient, db_session: AsyncSession) -> None:
    await _make_verified(db_session)
    response = await client.post(
        "/auth/login",
        data={"email": "kid@school.ru", "password": "wrong"},
    )
    assert response.status_code == 401
    assert "неверный" in response.text.lower()


async def test_login_unverified_allowed(client: AsyncClient, db_session: AsyncSession) -> None:
    # Soft verification: an unverified user can sign in and use the app.
    await register_user(
        db_session, RegisterIn(email="unverified@school.ru", password="strongpass123")
    )
    response = await client.post(
        "/auth/login",
        data={"email": "unverified@school.ru", "password": "strongpass123"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert "session" in response.cookies


async def test_logout_clears_session(client: AsyncClient, db_session: AsyncSession) -> None:
    await _make_verified(db_session)
    await client.post(
        "/auth/login",
        data={"email": "kid@school.ru", "password": "strongpass123"},
    )

    response = await client.post("/auth/logout", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/"


async def test_login_form_renders(client: AsyncClient) -> None:
    response = await client.get("/auth/login")
    assert response.status_code == 200
    assert "Вход" in response.text
