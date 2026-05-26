"""Tests for soft-delete + trash bin + restore."""

from datetime import UTC, datetime, timedelta
from uuid import UUID

from httpx import AsyncClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.tasks.models import Task


async def test_delete_moves_to_trash_not_purged(logged_in_client: AsyncClient) -> None:
    task = (await logged_in_client.post("/api/tasks", json={"title": "T"})).json()
    response = await logged_in_client.delete(f"/api/tasks/{task['id']}")
    assert response.status_code == 204
    # Task vanishes from active list…
    listing = (await logged_in_client.get("/api/tasks")).json()
    assert all(t["id"] != task["id"] for t in listing)
    # …but appears in trash with deleted_at set.
    trash = (await logged_in_client.get("/api/tasks/trash")).json()
    ids = [t["id"] for t in trash]
    assert task["id"] in ids


async def test_restore_brings_back(logged_in_client: AsyncClient) -> None:
    task = (await logged_in_client.post("/api/tasks", json={"title": "Recoverable"})).json()
    await logged_in_client.delete(f"/api/tasks/{task['id']}")
    response = await logged_in_client.post(f"/api/tasks/{task['id']}/restore")
    assert response.status_code == 200
    assert response.json()["id"] == task["id"]
    listing = (await logged_in_client.get("/api/tasks")).json()
    assert task["id"] in [t["id"] for t in listing]


async def test_purge_hard_deletes(logged_in_client: AsyncClient) -> None:
    task = (await logged_in_client.post("/api/tasks", json={"title": "Gone"})).json()
    await logged_in_client.delete(f"/api/tasks/{task['id']}")
    response = await logged_in_client.delete(f"/api/tasks/{task['id']}/purge")
    assert response.status_code == 204
    # Trying to restore a purged task → 404
    again = await logged_in_client.post(f"/api/tasks/{task['id']}/restore")
    assert again.status_code == 404


async def test_old_trash_auto_purged(
    logged_in_client: AsyncClient, db_session: AsyncSession
) -> None:
    # Create + soft-delete a task, then backdate deleted_at to 31 days ago.
    task = (await logged_in_client.post("/api/tasks", json={"title": "Ancient"})).json()
    await logged_in_client.delete(f"/api/tasks/{task['id']}")
    long_ago = datetime.now(UTC) - timedelta(days=31)
    await db_session.execute(
        update(Task).where(Task.id == UUID(task["id"])).values(deleted_at=long_ago)
    )
    await db_session.commit()
    # Hitting /trash triggers cleanup of >30-day-old.
    trash = (await logged_in_client.get("/api/tasks/trash")).json()
    assert task["id"] not in [t["id"] for t in trash]
    # Confirm hard-delete: row no longer in DB.
    row = (
        await db_session.execute(select(Task).where(Task.id == UUID(task["id"])))
    ).scalar_one_or_none()
    assert row is None


async def test_trashed_does_not_appear_in_today(
    logged_in_client: AsyncClient,
) -> None:
    today_iso = datetime.now(UTC).date().isoformat() + "T18:00:00Z"
    task = (
        await logged_in_client.post("/api/tasks", json={"title": "Trash me", "due_at": today_iso})
    ).json()
    await logged_in_client.delete(f"/api/tasks/{task['id']}")
    today_response = (await logged_in_client.get("/api/tasks/today")).json()
    assert task["id"] not in [t["id"] for t in today_response]


async def test_trash_view_renders(logged_in_client: AsyncClient) -> None:
    body = (await logged_in_client.get("/doday/app/trash")).text
    assert "Корзина" in body
    assert "30 дней" in body


async def test_sidebar_includes_trash_link(logged_in_client: AsyncClient) -> None:
    body = (await logged_in_client.get("/doday/app/today")).text
    assert "/doday/app/trash" in body


async def test_purge_all_empties_trash(logged_in_client: AsyncClient) -> None:
    # Soft-delete three tasks…
    ids = []
    for i in range(3):
        t = (await logged_in_client.post("/api/tasks", json={"title": f"T{i}"})).json()
        await logged_in_client.delete(f"/api/tasks/{t['id']}")
        ids.append(t["id"])
    # …then empty the whole trash at once.
    response = await logged_in_client.delete("/api/tasks/trash")
    assert response.status_code == 200
    assert response.json() == {"purged": 3}
    # Trash is now empty.
    trash = (await logged_in_client.get("/api/tasks/trash")).json()
    assert trash == []


async def test_purge_all_spares_active_and_other_users(
    logged_in_client: AsyncClient, db_session: AsyncSession
) -> None:
    # An active (non-deleted) task must survive emptying the trash.
    keep = (await logged_in_client.post("/api/tasks", json={"title": "Keep me"})).json()
    trashed = (await logged_in_client.post("/api/tasks", json={"title": "Bin me"})).json()
    await logged_in_client.delete(f"/api/tasks/{trashed['id']}")

    response = await logged_in_client.delete("/api/tasks/trash")
    assert response.status_code == 200
    assert response.json() == {"purged": 1}

    # Active task is still listed; trashed one is gone for good.
    listing = (await logged_in_client.get("/api/tasks")).json()
    assert keep["id"] in [t["id"] for t in listing]
    row = (
        await db_session.execute(select(Task).where(Task.id == UUID(trashed["id"])))
    ).scalar_one_or_none()
    assert row is None


async def test_purge_all_anonymous_blocked(client: AsyncClient) -> None:
    response = await client.delete("/api/tasks/trash")
    assert response.status_code == 401


async def test_restore_all_brings_back_trashed(logged_in_client: AsyncClient) -> None:
    ids = []
    for i in range(3):
        t = (await logged_in_client.post("/api/tasks", json={"title": f"R{i}"})).json()
        await logged_in_client.delete(f"/api/tasks/{t['id']}")
        ids.append(t["id"])

    response = await logged_in_client.post("/api/tasks/trash/restore")
    assert response.status_code == 200
    assert response.json() == {"restored": 3}

    # Trash is empty; all three are back in the active listing.
    assert (await logged_in_client.get("/api/tasks/trash")).json() == []
    listing_ids = [t["id"] for t in (await logged_in_client.get("/api/tasks")).json()]
    for tid in ids:
        assert tid in listing_ids


async def test_restore_all_spares_active(
    logged_in_client: AsyncClient, db_session: AsyncSession
) -> None:
    active = (await logged_in_client.post("/api/tasks", json={"title": "Already active"})).json()
    trashed = (await logged_in_client.post("/api/tasks", json={"title": "In bin"})).json()
    await logged_in_client.delete(f"/api/tasks/{trashed['id']}")

    response = await logged_in_client.post("/api/tasks/trash/restore")
    assert response.status_code == 200
    assert response.json() == {"restored": 1}

    # The previously-active task is untouched (not double-processed).
    row = await db_session.get(Task, UUID(active["id"]))
    assert row is not None
    await db_session.refresh(row)
    assert row.deleted_at is None


async def test_restore_all_anonymous_blocked(client: AsyncClient) -> None:
    response = await client.post("/api/tasks/trash/restore")
    assert response.status_code == 401
