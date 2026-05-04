"""Audience-aware empty state on /today when no tasks exist."""

from datetime import UTC, datetime

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.auth.security import hash_password


async def _login_as(
    client: AsyncClient, db_session: AsyncSession, email: str, audience: str | None
) -> None:
    user = User(
        email=email,
        password_hash=hash_password("strongpass123"),
        audience=audience,
        email_verified_at=datetime.now(UTC),
    )
    db_session.add(user)
    await db_session.commit()
    response = await client.post(
        "/auth/login", data={"email": email, "password": "strongpass123"}
    )
    assert response.status_code == 303


async def test_school_empty_state(client: AsyncClient, db_session: AsyncSession) -> None:
    await _login_as(client, db_session, "empty-school@x.test", "school")
    body = (await client.get("/app/today")).text
    assert "уроков и домашки" in body
    assert "/app/schedule" in body


async def test_company_empty_state(client: AsyncClient, db_session: AsyncSession) -> None:
    await _login_as(client, db_session, "empty-biz@x.test", "company")
    body = (await client.get("/app/today")).text
    assert "Ясный календарь" in body


async def test_personal_empty_state(client: AsyncClient, db_session: AsyncSession) -> None:
    await _login_as(client, db_session, "empty-me@x.test", "personal")
    body = (await client.get("/app/today")).text
    assert "Сегодня свободно" in body


async def test_default_empty_state(client: AsyncClient, db_session: AsyncSession) -> None:
    await _login_as(client, db_session, "empty-none@x.test", None)
    body = (await client.get("/app/today")).text
    assert "Сегодня всё чисто" in body
