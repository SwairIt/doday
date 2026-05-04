"""Tests for the habit tracker — CRUD, check-in idempotency, streak math."""

from datetime import UTC, datetime, timedelta
from uuid import UUID

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.habits.models import Habit, HabitCheckin


async def test_list_empty(logged_in_client: AsyncClient) -> None:
    response = await logged_in_client.get("/api/habits")
    assert response.status_code == 200
    assert response.json() == []


async def test_create_habit(logged_in_client: AsyncClient) -> None:
    response = await logged_in_client.post(
        "/api/habits", json={"name": "Drink water", "emoji": "💧", "color": "sky"}
    )
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Drink water"
    assert body["emoji"] == "💧"
    assert body["color"] == "sky"


async def test_checkin_creates_streak(logged_in_client: AsyncClient) -> None:
    habit = (await logged_in_client.post("/api/habits", json={"name": "Read"})).json()
    response = await logged_in_client.post(f"/api/habits/{habit['id']}/checkin")
    assert response.status_code == 200
    stats = response.json()
    assert stats["today_done"] is True
    assert stats["current_streak"] == 1


async def test_checkin_is_idempotent(logged_in_client: AsyncClient) -> None:
    habit = (await logged_in_client.post("/api/habits", json={"name": "X"})).json()
    await logged_in_client.post(f"/api/habits/{habit['id']}/checkin")
    response = await logged_in_client.post(f"/api/habits/{habit['id']}/checkin")
    stats = response.json()
    assert stats["current_streak"] == 1


async def test_uncheck_clears_today(logged_in_client: AsyncClient) -> None:
    habit = (await logged_in_client.post("/api/habits", json={"name": "Y"})).json()
    await logged_in_client.post(f"/api/habits/{habit['id']}/checkin")
    response = await logged_in_client.delete(f"/api/habits/{habit['id']}/checkin")
    stats = response.json()
    assert stats["today_done"] is False
    assert stats["current_streak"] == 0


async def test_archive_hides_habit(logged_in_client: AsyncClient) -> None:
    habit = (await logged_in_client.post("/api/habits", json={"name": "Z"})).json()
    response = await logged_in_client.delete(f"/api/habits/{habit['id']}")
    assert response.status_code == 204
    listing = (await logged_in_client.get("/api/habits")).json()
    assert listing == []


async def test_streak_three_days(logged_in_client: AsyncClient, db_session: AsyncSession) -> None:
    habit = (await logged_in_client.post("/api/habits", json={"name": "Streak"})).json()
    today = datetime.now(UTC).date()
    # Today's check-in via API.
    await logged_in_client.post(f"/api/habits/{habit['id']}/checkin")
    # Backdate two prior check-ins directly through the ORM.
    h = (await db_session.execute(select(Habit).where(Habit.id == UUID(habit["id"])))).scalar_one()
    for offset in (1, 2):
        db_session.add(
            HabitCheckin(
                habit_id=h.id,
                user_id=h.user_id,
                checkin_date=today - timedelta(days=offset),
            )
        )
    await db_session.commit()

    listing = (await logged_in_client.get("/api/habits")).json()
    assert listing[0]["current_streak"] == 3


async def test_view_renders(logged_in_client: AsyncClient) -> None:
    body = (await logged_in_client.get("/app/habits")).text
    assert "Привычки" in body
    assert "/api/habits" in body


async def test_unknown_habit_404(logged_in_client: AsyncClient) -> None:
    response = await logged_in_client.post(
        "/api/habits/00000000-0000-0000-0000-000000000000/checkin"
    )
    assert response.status_code == 404
