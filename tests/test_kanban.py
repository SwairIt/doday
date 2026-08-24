"""Tests for kanban view + cross-section drag (PATCH section_id)."""

from httpx import AsyncClient


async def test_kanban_view_renders(logged_in_client: AsyncClient) -> None:
    proj = (await logged_in_client.post("/api/projects", json={"name": "Kanban test"})).json()
    response = await logged_in_client.get(
        f"/app/projects/{proj['slug']}", params={"view": "kanban"}
    )
    assert response.status_code == 200
    assert "Без секции" in response.text  # default column for tasks without section
    assert "Kanban" in response.text or "Доска" in response.text


async def test_list_view_default_renders(logged_in_client: AsyncClient) -> None:
    proj = (await logged_in_client.post("/api/projects", json={"name": "P"})).json()
    response = await logged_in_client.get(f"/app/projects/{proj['slug']}")
    assert response.status_code == 200
    assert "Список" in response.text  # toggle label for current view


async def test_kanban_view_toggle_link_present(logged_in_client: AsyncClient) -> None:
    proj = (await logged_in_client.post("/api/projects", json={"name": "P"})).json()
    response = await logged_in_client.get(f"/app/projects/{proj['slug']}")
    assert "view=kanban" in response.text  # toggle target


async def test_patch_task_section_id_via_api(logged_in_client: AsyncClient) -> None:
    """Drag in kanban triggers PATCH /api/tasks/{id} with section_id."""
    proj = (await logged_in_client.post("/api/projects", json={"name": "P"})).json()
    section = (
        await logged_in_client.post(
            "/api/sections", json={"project_id": proj["id"], "name": "Doing"}
        )
    ).json()
    task = (
        await logged_in_client.post("/api/tasks", json={"title": "T", "project_id": proj["id"]})
    ).json()

    # Move task into the section
    patch = await logged_in_client.patch(
        f"/api/tasks/{task['id']}", json={"section_id": section["id"]}
    )
    assert patch.status_code == 200
    assert patch.json()["section_id"] == section["id"]


async def test_kanban_renders_sections_as_columns(logged_in_client: AsyncClient) -> None:
    proj = (await logged_in_client.post("/api/projects", json={"name": "Pp"})).json()
    await logged_in_client.post("/api/sections", json={"project_id": proj["id"], "name": "TodoCol"})
    await logged_in_client.post("/api/sections", json={"project_id": proj["id"], "name": "DoneCol"})

    response = await logged_in_client.get(
        f"/app/projects/{proj['slug']}", params={"view": "kanban"}
    )
    assert "TodoCol" in response.text
    assert "DoneCol" in response.text
