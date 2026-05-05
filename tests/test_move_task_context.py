"""Tests for the 'move task to project' flow exposed via the context menu.

The actual move uses PATCH /api/tasks/{id} with {project_id}; tests cover
both the underlying endpoint and the rendered UI markup."""

from httpx import AsyncClient


async def test_move_task_to_another_project(logged_in_client: AsyncClient) -> None:
    src = (await logged_in_client.post("/api/projects", json={"name": "Source"})).json()
    dst = (await logged_in_client.post("/api/projects", json={"name": "Destination"})).json()
    t = (
        await logged_in_client.post(
            "/api/tasks", json={"title": "wandering", "project_id": src["id"]}
        )
    ).json()

    r = await logged_in_client.patch(
        f"/api/tasks/{t['id']}", json={"project_id": dst["id"]}
    )
    assert r.status_code == 200
    assert r.json()["project_id"] == dst["id"]


async def test_context_menu_renders_move_item(logged_in_client: AsyncClient) -> None:
    body = (await logged_in_client.get("/app/today")).text
    assert "Перенести в проект" in body
    assert "task-ctx-move-submenu" in body


async def test_context_menu_loads_projects_endpoint(logged_in_client: AsyncClient) -> None:
    """The submenu's JS calls /api/projects which must be reachable."""
    r = await logged_in_client.get("/api/projects")
    assert r.status_code == 200
    assert isinstance(r.json(), list)
