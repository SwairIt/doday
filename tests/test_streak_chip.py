"""Tests for the topbar streak chip endpoint."""

from datetime import UTC, datetime, timedelta

from httpx import AsyncClient
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.tasks.models import Task


async def test_streak_zero_for_fresh_user(logged_in_client: AsyncClient) -> None:
    response = await logged_in_client.get("/api/stats/streak")
    assert response.status_code == 200
    body = response.json()
    assert body["current"] == 0
    assert body["longest"] == 0
    assert body["today_done"] is False


async def test_streak_one_after_today_completion(
    logged_in_client: AsyncClient, db_session: AsyncSession
) -> None:
    task = (await logged_in_client.post("/api/tasks", json={"title": "S"})).json()
    await logged_in_client.post(f"/htmx/tasks/{task['id']}/toggle")
    body = (await logged_in_client.get("/api/stats/streak")).json()
    assert body["current"] == 1
    assert body["today_done"] is True


async def test_streak_three_consecutive_days(
    logged_in_client: AsyncClient, db_session: AsyncSession
) -> None:
    today = datetime.now(UTC)
    # Create + complete 3 tasks on different consecutive days
    for offset in (0, 1, 2):
        completed_at = today - timedelta(days=offset)
        task = (await logged_in_client.post("/api/tasks", json={"title": f"T{offset}"})).json()
        await logged_in_client.post(f"/htmx/tasks/{task['id']}/toggle")
        if offset > 0:
            # Backdate the completion timestamp
            await db_session.execute(
                update(Task).where(Task.id == task["id"]).values(completed_at=completed_at)
            )
            await db_session.commit()
    body = (await logged_in_client.get("/api/stats/streak")).json()
    assert body["current"] == 3
    assert body["longest"] >= 3


async def test_streak_topbar_chip_renders(logged_in_client: AsyncClient) -> None:
    body = (await logged_in_client.get("/app/today")).text
    # the chip is loaded via fetch but its container markup is in topbar
    assert "/api/stats/streak" in body
