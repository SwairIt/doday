"""School-audience grouping of today's tasks by detected subject."""

from datetime import UTC, datetime

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.auth.security import hash_password


async def _login_school(client: AsyncClient, db_session: AsyncSession) -> None:
    user = User(
        email="schooler-grp@x.test",
        password_hash=hash_password("strongpass123"),
        audience="school",
        email_verified_at=datetime.now(UTC),
    )
    db_session.add(user)
    await db_session.commit()
    response = await client.post(
        "/auth/login", data={"email": "schooler-grp@x.test", "password": "strongpass123"}
    )
    assert response.status_code == 303


async def test_toggle_button_visible_for_school_with_subjects(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _login_school(client, db_session)
    today_iso = datetime.now(UTC).date().isoformat() + "T18:00:00Z"
    await client.post(
        "/api/tasks", json={"title": "Алгебра — параграф 5", "due_at": today_iso}
    )
    body = (await client.get("/app/today")).text
    assert "По предметам" in body or "Линейно" in body
    assert "doday-today-grouped" in body
    # subject group header should be in the rendered HTML
    assert "Алгебра" in body


async def test_toggle_hidden_when_no_today_tasks(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _login_school(client, db_session)
    body = (await client.get("/app/today")).text
    assert "doday-today-grouped" not in body


async def test_toggle_hidden_for_non_school(logged_in_client: AsyncClient) -> None:
    today_iso = datetime.now(UTC).date().isoformat() + "T18:00:00Z"
    await logged_in_client.post(
        "/api/tasks", json={"title": "Алгебра — задание", "due_at": today_iso}
    )
    body = (await logged_in_client.get("/app/today")).text
    assert "doday-today-grouped" not in body


async def test_unknown_subject_falls_into_no_subject_bucket(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _login_school(client, db_session)
    today_iso = datetime.now(UTC).date().isoformat() + "T18:00:00Z"
    await client.post(
        "/api/tasks", json={"title": "Подстричь газон", "due_at": today_iso}
    )
    body = (await client.get("/app/today")).text
    assert "Без предмета" in body
