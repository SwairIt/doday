"""Smoke test for the undo-toast partial markup on /today."""

from httpx import AsyncClient


async def test_undo_toast_partial_present(logged_in_client: AsyncClient) -> None:
    body = (await logged_in_client.get("/app/today")).text
    assert "doday-task-deleted" in body
    assert "Удалено:" in body
    assert "Отменить" in body


async def test_delete_button_dispatches_event(logged_in_client: AsyncClient) -> None:
    from datetime import UTC, datetime

    today_iso = datetime.now(UTC).date().isoformat() + "T18:00:00Z"
    task = (
        await logged_in_client.post("/api/tasks", json={"title": "to-delete", "due_at": today_iso})
    ).json()
    body = (await logged_in_client.get("/app/today")).text
    # delete is now via context menu (data-ctx="delete"); undo toast listens for doday-task-deleted
    assert task["id"] in body
    assert 'data-ctx="delete"' in body
    assert "doday-task-deleted" in body
