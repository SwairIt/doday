"""Tests for project duplication — copies sections + tasks (with parent links)."""

from httpx import AsyncClient


async def test_duplicate_creates_new_project(logged_in_client: AsyncClient) -> None:
    src = (await logged_in_client.post("/api/projects", json={"name": "Source"})).json()
    response = await logged_in_client.post(f"/api/projects/{src['id']}/duplicate")
    assert response.status_code == 201
    new = response.json()
    assert new["id"] != src["id"]
    assert "копия" in new["name"]


async def test_duplicate_copies_sections(logged_in_client: AsyncClient) -> None:
    src = (await logged_in_client.post("/api/projects", json={"name": "S"})).json()
    await logged_in_client.post("/api/sections", json={"project_id": src["id"], "name": "ColA"})
    await logged_in_client.post("/api/sections", json={"project_id": src["id"], "name": "ColB"})
    new = (await logged_in_client.post(f"/api/projects/{src['id']}/duplicate")).json()
    new_sections = (await logged_in_client.get(f"/api/sections?project_id={new['id']}")).json()
    names = {s["name"] for s in new_sections}
    assert {"ColA", "ColB"} == names


async def test_duplicate_copies_tasks_with_section_link(logged_in_client: AsyncClient) -> None:
    src = (await logged_in_client.post("/api/projects", json={"name": "S"})).json()
    sec = (
        await logged_in_client.post(
            "/api/sections", json={"project_id": src["id"], "name": "Doing"}
        )
    ).json()
    await logged_in_client.post(
        "/api/tasks",
        json={"title": "Task1", "project_id": src["id"], "section_id": sec["id"]},
    )

    new = (await logged_in_client.post(f"/api/projects/{src['id']}/duplicate")).json()
    new_tasks = (await logged_in_client.get(f"/api/tasks?project_id={new['id']}")).json()
    assert len(new_tasks) == 1
    assert new_tasks[0]["title"] == "Task1"
    assert new_tasks[0]["section_id"] is not None
    assert new_tasks[0]["section_id"] != sec["id"]


async def test_duplicate_preserves_parent_task_links(logged_in_client: AsyncClient) -> None:
    src = (await logged_in_client.post("/api/projects", json={"name": "S"})).json()
    parent = (
        await logged_in_client.post("/api/tasks", json={"title": "P", "project_id": src["id"]})
    ).json()
    await logged_in_client.post(
        "/api/tasks",
        json={"title": "C", "project_id": src["id"], "parent_task_id": parent["id"]},
    )

    new = (await logged_in_client.post(f"/api/projects/{src['id']}/duplicate")).json()
    parents = (await logged_in_client.get(f"/api/tasks?project_id={new['id']}")).json()
    assert len(parents) == 1
    new_parent = parents[0]
    assert new_parent["title"] == "P"
    subs_html = (await logged_in_client.get(f"/doday/htmx/tasks/{new_parent['id']}/subtasks")).text
    assert "C" in subs_html


async def test_duplicate_unknown_project(logged_in_client: AsyncClient) -> None:
    response = await logged_in_client.post(
        "/api/projects/00000000-0000-0000-0000-000000000000/duplicate"
    )
    assert response.status_code == 404
