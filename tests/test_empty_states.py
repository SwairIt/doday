"""Empty state on /today when no tasks exist — universal copy after audience removal."""

from datetime import UTC, datetime

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.auth.security import hash_password


async def _login_as(client: AsyncClient, db_session: AsyncSession, email: str) -> None:
    user = User(
        email=email,
        password_hash=hash_password("strongpass123"),
        email_verified_at=datetime.now(UTC),
    )
    db_session.add(user)
    await db_session.commit()
    response = await client.post("/auth/login", data={"email": email, "password": "strongpass123"})
    assert response.status_code == 303


async def test_default_empty_state(client: AsyncClient, db_session: AsyncSession) -> None:
    await _login_as(client, db_session, "empty-none@x.test")
    body = (await client.get("/doday/app/today")).text
    assert "Сегодня всё чисто" in body
