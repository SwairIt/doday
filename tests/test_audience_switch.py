"""Tests for changing the audience after registration via /api/profile/audience."""

from datetime import UTC, datetime

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.auth.security import hash_password
from app.auth.service import get_user_by_email


async def _login(client: AsyncClient, db_session: AsyncSession, audience: str | None) -> None:
    user = User(
        email="switcher@x.test",
        password_hash=hash_password("strongpass123"),
        audience=audience,
        email_verified_at=datetime.now(UTC),
    )
    db_session.add(user)
    await db_session.commit()
    response = await client.post(
        "/auth/login",
        data={"email": "switcher@x.test", "password": "strongpass123"},
    )
    assert response.status_code == 303


async def test_switch_to_company(client: AsyncClient, db_session: AsyncSession) -> None:
    await _login(client, db_session, "school")
    response = await client.post("/api/profile/audience", data={"audience": "company"})
    assert response.status_code == 200
    assert response.json() == {"audience": "company"}
    user = await get_user_by_email(db_session, "switcher@x.test")
    assert user is not None
    assert user.audience == "company"


async def test_clear_audience(client: AsyncClient, db_session: AsyncSession) -> None:
    await _login(client, db_session, "company")
    response = await client.post("/api/profile/audience", data={"audience": ""})
    assert response.status_code == 200
    assert response.json() == {"audience": None}
    user = await get_user_by_email(db_session, "switcher@x.test")
    assert user is not None
    assert user.audience is None


async def test_invalid_audience_rejected(client: AsyncClient, db_session: AsyncSession) -> None:
    await _login(client, db_session, "personal")
    response = await client.post("/api/profile/audience", data={"audience": "alien"})
    assert response.status_code == 422


async def test_sidebar_shows_audience_badge(client: AsyncClient, db_session: AsyncSession) -> None:
    await _login(client, db_session, "school")
    body = (await client.get("/app/today")).text
    assert "🎓" in body and "Учёба" in body


async def test_sidebar_no_badge_when_no_audience(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _login(client, db_session, None)
    body = (await client.get("/app/today")).text
    assert "Сменить режим" not in body


async def test_profile_page_shows_audience_picker(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _login(client, db_session, "personal")
    body = (await client.get("/app/profile")).text
    assert "Для чего туду-лист?" in body
    assert "/api/profile/audience" in body
    assert "Без темы" in body
