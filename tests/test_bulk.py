"""Tests for bulk task actions."""

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.tasks.models import Task


async def test_bulk_complete_marks_all_as_done(
    logged_in_client: AsyncClient, db_session: AsyncSession
) -> None:
    a = await logged_in_client.post("/api/tasks", json={"title": "A"})
    b = await logged_in_client.post("/api/tasks", json={"title": "B"})
    c = await logged_in_client.post("/api/tasks", json={"title": "C"})
    ids = [a.json()["id"], b.json()["id"], c.json()["id"]]

    response = await logged_in_client.post(
        "/htmx/bulk",
        data={"action": "complete", "ids": ids},
    )
    assert response.status_code == 200
    assert response.headers.get("HX-Refresh") == "true"

    rows = (
        (await db_session.execute(select(Task).where(Task.title.in_(["A", "B", "C"]))))
        .scalars()
        .all()
    )
    assert all(r.is_completed for r in rows)


async def test_bulk_delete_removes_all(
    logged_in_client: AsyncClient, db_session: AsyncSession
) -> None:
    a = await logged_in_client.post("/api/tasks", json={"title": "DelA"})
    b = await logged_in_client.post("/api/tasks", json={"title": "DelB"})

    response = await logged_in_client.post(
        "/htmx/bulk",
        data={"action": "delete", "ids": [a.json()["id"], b.json()["id"]]},
    )
    assert response.status_code == 200

    # Soft-delete moves them to trash. Rows still exist with deleted_at set,
    # but the active task list excludes them.
    rows = (
        (await db_session.execute(select(Task).where(Task.title.in_(["DelA", "DelB"]))))
        .scalars()
        .all()
    )
    assert len(rows) == 2
    assert all(r.deleted_at is not None for r in rows)
    listing = (await logged_in_client.get("/api/tasks")).json()
    titles = [t["title"] for t in listing]
    assert "DelA" not in titles and "DelB" not in titles


async def test_bulk_unknown_action_returns_400(
    logged_in_client: AsyncClient,
) -> None:
    a = await logged_in_client.post("/api/tasks", json={"title": "X"})
    response = await logged_in_client.post(
        "/htmx/bulk",
        data={"action": "frobnicate", "ids": [a.json()["id"]]},
    )
    assert response.status_code == 400


async def test_bulk_skips_unknown_ids_silently(
    logged_in_client: AsyncClient,
) -> None:
    a = await logged_in_client.post("/api/tasks", json={"title": "Real"})
    response = await logged_in_client.post(
        "/htmx/bulk",
        data={
            "action": "complete",
            "ids": [a.json()["id"], "00000000-0000-0000-0000-000000000000"],
        },
    )
    assert response.status_code == 200
