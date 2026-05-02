"""Integration tests for /auth/verify endpoint."""

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.schemas import RegisterIn
from app.auth.security import create_email_verification_token
from app.auth.service import register_user


async def test_verify_marks_user_verified(client: AsyncClient, db_session: AsyncSession) -> None:
    user = await register_user(
        db_session, RegisterIn(email="kid@school.ru", password="strongpass123")
    )
    token = create_email_verification_token(str(user.id))

    response = await client.get(f"/auth/verify?token={token}", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/auth/login"

    await db_session.refresh(user)
    assert user.email_verified_at is not None


async def test_verify_garbage_token_returns_400(client: AsyncClient) -> None:
    response = await client.get("/auth/verify?token=garbage")
    assert response.status_code == 400
    assert "недействительна" in response.text.lower()
