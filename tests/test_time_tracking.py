"""Tests for the time-tracking module."""

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import UUID

from httpx import AsyncClient
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.time_tracking.models import TimeEntry


async def test_start_returns_running_entry(logged_in_client: AsyncClient) -> None:
    task = (await logged_in_client.post("/api/tasks", json={"title": "T"})).json()
    response = await logged_in_client.post(f"/api/time/tasks/{task['id']}/start")
    assert response.status_code == 200
    body = response.json()
    assert body["task_id"] == task["id"]
    assert body["started_at"]


async def test_stop_calculates_duration(
    logged_in_client: AsyncClient, db_session: AsyncSession
) -> None:
    task = (await logged_in_client.post("/api/tasks", json={"title": "T2"})).json()
    started = (await logged_in_client.post(f"/api/time/tasks/{task['id']}/start")).json()
    # Backdate the start by 90s so duration math is non-zero and predictable.
    await db_session.execute(
        update(TimeEntry)
        .where(TimeEntry.id == UUID(started["id"]))
        .values(started_at=datetime.now(UTC) - timedelta(seconds=90))
    )
    await db_session.commit()
    stopped = await logged_in_client.post(f"/api/time/tasks/{task['id']}/stop")
    assert stopped.status_code == 200
    body = stopped.json()
    assert body["duration_seconds"] >= 88
    assert body["task_total_seconds"] >= 88


async def test_stop_without_running_400(logged_in_client: AsyncClient) -> None:
    task = (await logged_in_client.post("/api/tasks", json={"title": "Z"})).json()
    response = await logged_in_client.post(f"/api/time/tasks/{task['id']}/stop")
    assert response.status_code == 400


async def test_starting_new_timer_stops_old(
    logged_in_client: AsyncClient, db_session: AsyncSession
) -> None:
    a = (await logged_in_client.post("/api/tasks", json={"title": "A"})).json()
    b = (await logged_in_client.post("/api/tasks", json={"title": "B"})).json()
    await logged_in_client.post(f"/api/time/tasks/{a['id']}/start")
    await asyncio.sleep(0.05)
    await logged_in_client.post(f"/api/time/tasks/{b['id']}/start")

    today = (await logged_in_client.get("/api/time/today")).json()
    assert today["running_task_id"] == b["id"]


async def test_task_total_endpoint(logged_in_client: AsyncClient, db_session: AsyncSession) -> None:
    task = (await logged_in_client.post("/api/tasks", json={"title": "T3"})).json()
    body = (await logged_in_client.get(f"/api/time/tasks/{task['id']}")).json()
    assert body["total_seconds"] == 0
    assert body["running"] is False


async def test_today_total(logged_in_client: AsyncClient, db_session: AsyncSession) -> None:
    task = (await logged_in_client.post("/api/tasks", json={"title": "T4"})).json()
    started = (await logged_in_client.post(f"/api/time/tasks/{task['id']}/start")).json()
    # Backdate start so total > 0 even if test is fast.
    await db_session.execute(
        update(TimeEntry)
        .where(TimeEntry.id == UUID(started["id"]))
        .values(started_at=datetime.now(UTC) - timedelta(seconds=120))
    )
    await db_session.commit()
    body = (await logged_in_client.get("/api/time/today")).json()
    assert body["total_seconds"] >= 118


async def test_unknown_task_404(logged_in_client: AsyncClient) -> None:
    response = await logged_in_client.post(
        "/api/time/tasks/00000000-0000-0000-0000-000000000000/start"
    )
    assert response.status_code == 404
