"""Quick-add subject chips appear above the input only for school audience."""

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


async def test_school_user_sees_subject_chips(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _login_as(client, db_session, "school-q@x.test", "school")
    body = (await client.get("/app/today")).text
    assert "🔢 Алгебра" in body
    assert "📐 Геометрия" in body
    assert "⚛️ Физика" in body


async def test_company_user_does_not_see_subject_chips(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _login_as(client, db_session, "biz-q@x.test", "company")
    body = (await client.get("/app/today")).text
    assert "🔢 Алгебра" not in body
    assert "📐 Геометрия" not in body


async def test_no_audience_does_not_see_subject_chips(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _login_as(client, db_session, "none-q@x.test", None)
    body = (await client.get("/app/today")).text
    assert "🔢 Алгебра" not in body
