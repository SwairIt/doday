"""Tests for the school-only streak endpoint and widget."""

from datetime import UTC, datetime, timedelta

from httpx import AsyncClient
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.auth.security import hash_password
from app.tasks.models import Task


async def _login_school(client: AsyncClient, db_session: AsyncSession) -> None:
    user = User(
        email="streak-school@x.test",
        password_hash=hash_password("strongpass123"),
        audience="school",
        email_verified_at=datetime.now(UTC),
    )
    db_session.add(user)
    await db_session.commit()
    response = await client.post(
        "/auth/login", data={"email": "streak-school@x.test", "password": "strongpass123"}
    )
    assert response.status_code == 303


async def test_school_streak_zero_for_fresh(logged_in_client: AsyncClient) -> None:
    body = (await logged_in_client.get("/api/stats/school-streak")).json()
    assert body["current"] == 0
    assert body["longest"] == 0


async def test_school_task_increments_streak(
    logged_in_client: AsyncClient, db_session: AsyncSession
) -> None:
    task = (
        await logged_in_client.post("/api/tasks", json={"title": "Алгебра — параграф 5"})
    ).json()
    await logged_in_client.post(f"/htmx/tasks/{task['id']}/toggle")
    body = (await logged_in_client.get("/api/stats/school-streak")).json()
    assert body["current"] == 1
    assert body["today_done"] is True


async def test_non_school_task_does_not_count(logged_in_client: AsyncClient) -> None:
    task = (await logged_in_client.post("/api/tasks", json={"title": "Подстричь газон"})).json()
    await logged_in_client.post(f"/htmx/tasks/{task['id']}/toggle")
    body = (await logged_in_client.get("/api/stats/school-streak")).json()
    assert body["current"] == 0


async def test_three_day_school_streak(
    logged_in_client: AsyncClient, db_session: AsyncSession
) -> None:
    today = datetime.now(UTC)
    for offset in (0, 1, 2):
        task = (
            await logged_in_client.post("/api/tasks", json={"title": f"Физика — задача {offset}"})
        ).json()
        await logged_in_client.post(f"/htmx/tasks/{task['id']}/toggle")
        if offset > 0:
            await db_session.execute(
                update(Task)
                .where(Task.id == task["id"])
                .values(completed_at=today - timedelta(days=offset))
            )
            await db_session.commit()
    body = (await logged_in_client.get("/api/stats/school-streak")).json()
    assert body["current"] == 3


async def test_widget_renders_for_school(client: AsyncClient, db_session: AsyncSession) -> None:
    await _login_school(client, db_session)
    body = (await client.get("/app/today")).text
    assert "/api/stats/school-streak" in body
    assert "Школьная серия" in body
