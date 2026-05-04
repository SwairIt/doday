"""Smoke tests for the sprint widget visibility on /today."""

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
    response = await client.post("/auth/login", data={"email": email, "password": "strongpass123"})
    assert response.status_code == 303


async def test_sprint_widget_visible_for_company(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _login_as(client, db_session, "biz-sp@x.test", "company")
    body = (await client.get("/app/today")).text
    assert "Запустить спринт" in body
    assert "doday-sprint" in body


async def test_sprint_widget_hidden_for_school(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _login_as(client, db_session, "schooler-sp@x.test", "school")
    body = (await client.get("/app/today")).text
    assert "doday-sprint" not in body


async def test_sprint_widget_hidden_for_personal(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _login_as(client, db_session, "personal-sp@x.test", "personal")
    body = (await client.get("/app/today")).text
    assert "doday-sprint" not in body
