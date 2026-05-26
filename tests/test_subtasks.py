"""Tests for subtasks (HTMX endpoints + service)."""

from httpx import AsyncClient


async def test_subtasks_list_empty(logged_in_client: AsyncClient) -> None:
    parent = await logged_in_client.post("/api/tasks", json={"title": "Parent"})
    parent_id = parent.json()["id"]

    response = await logged_in_client.get(f"/doday/htmx/tasks/{parent_id}/subtasks")
    assert response.status_code == 200
    assert "Подзадача" in response.text  # the inline-add placeholder


async def test_create_subtask_via_htmx(logged_in_client: AsyncClient) -> None:
    parent = await logged_in_client.post("/api/tasks", json={"title": "Parent"})
    parent_id = parent.json()["id"]

    response = await logged_in_client.post(
        f"/doday/htmx/tasks/{parent_id}/subtasks",
        data={"title": "Sub one"},
    )
    assert response.status_code == 200
    assert "Sub one" in response.text
    assert "task-row" in response.text


async def test_subtasks_listed_after_create(logged_in_client: AsyncClient) -> None:
    parent = await logged_in_client.post("/api/tasks", json={"title": "Parent"})
    parent_id = parent.json()["id"]

    await logged_in_client.post(f"/doday/htmx/tasks/{parent_id}/subtasks", data={"title": "S1"})
    await logged_in_client.post(f"/doday/htmx/tasks/{parent_id}/subtasks", data={"title": "S2"})

    listed = await logged_in_client.get(f"/doday/htmx/tasks/{parent_id}/subtasks")
    assert "S1" in listed.text
    assert "S2" in listed.text


async def test_subtasks_hidden_from_top_level_today(logged_in_client: AsyncClient) -> None:
    """Subtasks shouldn't pollute the Today view's top-level list."""
    from datetime import UTC, datetime

    today = datetime.now(UTC).replace(hour=23, minute=59).isoformat()
    parent = await logged_in_client.post("/api/tasks", json={"title": "ParentDue", "due_at": today})
    parent_id = parent.json()["id"]
    await logged_in_client.post(
        f"/doday/htmx/tasks/{parent_id}/subtasks", data={"title": "SubChild"}
    )

    today_view = await logged_in_client.get("/doday/app/today")
    assert today_view.status_code == 200
    assert "ParentDue" in today_view.text
    # SubChild has no due date so it shouldn't appear in Today regardless;
    # but the API list_tasks should also exclude it via top_level_only=True
    api = await logged_in_client.get("/api/tasks")
    titles = [t["title"] for t in api.json()]
    assert "ParentDue" in titles
    assert "SubChild" not in titles  # subtask hidden from top-level list
