"""Tests for subtasks (HTMX endpoints + service)."""

from httpx import AsyncClient


async def test_subtasks_list_empty(logged_in_client: AsyncClient) -> None:
    parent = await logged_in_client.post("/api/tasks", json={"title": "Parent"})
    parent_id = parent.json()["id"]

    response = await logged_in_client.get(f"/htmx/tasks/{parent_id}/subtasks")
    assert response.status_code == 200
    assert "Подзадача" in response.text  # the inline-add placeholder


async def test_create_subtask_via_htmx(logged_in_client: AsyncClient) -> None:
    parent = await logged_in_client.post("/api/tasks", json={"title": "Parent"})
    parent_id = parent.json()["id"]

    response = await logged_in_client.post(
        f"/htmx/tasks/{parent_id}/subtasks",
        data={"title": "Sub one"},
    )
    assert response.status_code == 200
    assert "Sub one" in response.text
    assert "task-row" in response.text


async def test_subtasks_listed_after_create(logged_in_client: AsyncClient) -> None:
    parent = await logged_in_client.post("/api/tasks", json={"title": "Parent"})
    parent_id = parent.json()["id"]

    await logged_in_client.post(f"/htmx/tasks/{parent_id}/subtasks", data={"title": "S1"})
    await logged_in_client.post(f"/htmx/tasks/{parent_id}/subtasks", data={"title": "S2"})

    listed = await logged_in_client.get(f"/htmx/tasks/{parent_id}/subtasks")
    assert "S1" in listed.text
    assert "S2" in listed.text


async def test_subtasks_hidden_from_top_level_today(logged_in_client: AsyncClient) -> None:
    """Subtasks shouldn't pollute the Today view's top-level list."""
    from datetime import UTC, datetime

    # Zero out seconds: .replace(hour=23, minute=59) kept the current seconds,
    # so once a minute the due time landed past end-of-day and CI went red.
    today = datetime.now(UTC).replace(hour=23, minute=59, second=0, microsecond=0).isoformat()
    parent = await logged_in_client.post("/api/tasks", json={"title": "ParentDue", "due_at": today})
    parent_id = parent.json()["id"]
    await logged_in_client.post(f"/htmx/tasks/{parent_id}/subtasks", data={"title": "SubChild"})

    today_view = await logged_in_client.get("/app/today")
    assert today_view.status_code == 200
    assert "ParentDue" in today_view.text
    # SubChild has no due date so it shouldn't appear in Today regardless;
    # but the API list_tasks should also exclude it via top_level_only=True
    api = await logged_in_client.get("/api/tasks")
    titles = [t["title"] for t in api.json()]
    assert "ParentDue" in titles
    assert "SubChild" not in titles  # subtask hidden from top-level list


async def test_task_due_at_the_very_end_of_day_is_in_today(logged_in_client: AsyncClient) -> None:
    """Срок 23:59:59.5 — это всё ещё сегодня.

    Раньше «Сегодня» сравнивалось с 23:59:59 включительно, и задача с
    дробными секундами из выборки выпадала.
    """
    from datetime import UTC, datetime

    due = datetime.now(UTC).replace(hour=23, minute=59, second=59, microsecond=500000)
    await logged_in_client.post(
        "/api/tasks", json={"title": "EdgeOfDay", "due_at": due.isoformat()}
    )
    titles = [t["title"] for t in (await logged_in_client.get("/api/tasks/today")).json()]
    assert "EdgeOfDay" in titles
