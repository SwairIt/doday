"""Tests for single-task duplication endpoint."""

from httpx import AsyncClient


async def test_duplicate_creates_sibling(logged_in_client: AsyncClient) -> None:
    proj = (await logged_in_client.post("/api/projects", json={"name": "Dup"})).json()
    src = (
        await logged_in_client.post(
            "/api/tasks",
            json={
                "title": "Тест",
                "project_id": proj["id"],
                "priority": "p2",
                "description": "Заметка",
            },
        )
    ).json()
    response = await logged_in_client.post(f"/api/tasks/{src['id']}/duplicate")
    assert response.status_code == 201
    new = response.json()
    assert new["id"] != src["id"]
    assert new["title"] == "Тест (копия)"
    assert new["priority"] == "p2"
    assert new["description"] == "Заметка"
    assert new["project_id"] == src["project_id"]
    assert new["parent_task_id"] == src["parent_task_id"]


async def test_duplicate_includes_subtasks(logged_in_client: AsyncClient) -> None:
    parent = (await logged_in_client.post("/api/tasks", json={"title": "P"})).json()
    await logged_in_client.post(
        "/api/tasks", json={"title": "C1", "parent_task_id": parent["id"]}
    )
    await logged_in_client.post(
        "/api/tasks", json={"title": "C2", "parent_task_id": parent["id"]}
    )
    new = (await logged_in_client.post(f"/api/tasks/{parent['id']}/duplicate")).json()
    assert new["title"] == "P (копия)"
    subs_html = (await logged_in_client.get(f"/htmx/tasks/{new['id']}/subtasks")).text
    assert "C1" in subs_html and "C2" in subs_html


async def test_duplicate_subtask_does_not_become_top_level(
    logged_in_client: AsyncClient,
) -> None:
    parent = (await logged_in_client.post("/api/tasks", json={"title": "P"})).json()
    child = (
        await logged_in_client.post(
            "/api/tasks", json={"title": "C", "parent_task_id": parent["id"]}
        )
    ).json()
    new_child = (await logged_in_client.post(f"/api/tasks/{child['id']}/duplicate")).json()
    assert new_child["parent_task_id"] == parent["id"]
    # Top-level list should NOT include the new subtask copy.
    top_level = (await logged_in_client.get("/api/tasks")).json()
    assert all(t["id"] != new_child["id"] for t in top_level)


async def test_duplicate_unknown_404(logged_in_client: AsyncClient) -> None:
    response = await logged_in_client.post(
        "/api/tasks/00000000-0000-0000-0000-000000000000/duplicate"
    )
    assert response.status_code == 404
