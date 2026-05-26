"""Tests for UI polish: keyboard shortcuts overlay, project description, comment edit."""

from httpx import AsyncClient


async def test_shortcuts_overlay_included(logged_in_client: AsyncClient) -> None:
    response = await logged_in_client.get("/doday/app/today")
    assert response.status_code == 200
    assert "Горячие клавиши" in response.text
    assert "g + …" in response.text


async def test_project_description_appears_in_header(logged_in_client: AsyncClient) -> None:
    proj = (await logged_in_client.post("/api/projects", json={"name": "Desc"})).json()
    await logged_in_client.patch(
        f"/api/projects/{proj['id']}", json={"description": "Тестовое описание проекта"}
    )
    page = await logged_in_client.get(f"/doday/app/projects/{proj['slug']}")
    assert page.status_code == 200
    assert "Тестовое описание проекта" in page.text


async def test_comment_edit_via_api(logged_in_client: AsyncClient) -> None:
    task = (await logged_in_client.post("/api/tasks", json={"title": "T"})).json()
    c = (
        await logged_in_client.post(f"/api/tasks/{task['id']}/comments", json={"body": "v1"})
    ).json()
    updated = (await logged_in_client.patch(f"/api/comments/{c['id']}", json={"body": "v2"})).json()
    assert updated["body"] == "v2"


async def test_quickadd_input_is_focusable_via_data_attr(logged_in_client: AsyncClient) -> None:
    proj = (await logged_in_client.post("/api/projects", json={"name": "Q"})).json()
    page = await logged_in_client.get(f"/doday/app/projects/{proj['slug']}")
    assert "data-quickadd-input" in page.text


async def test_inline_edit_form_includes_description(logged_in_client: AsyncClient) -> None:
    task = (
        await logged_in_client.post(
            "/api/tasks", json={"title": "T", "description": "Initial body"}
        )
    ).json()
    html = (await logged_in_client.get(f"/doday/htmx/tasks/{task['id']}/edit")).text
    assert "Initial body" in html
    assert 'name="description"' in html


async def test_inline_edit_saves_description(logged_in_client: AsyncClient) -> None:
    task = (await logged_in_client.post("/api/tasks", json={"title": "T"})).json()
    response = await logged_in_client.patch(
        f"/doday/htmx/tasks/{task['id']}",
        data={"title": "T", "description": "Now with body"},
    )
    assert response.status_code == 200
    fetched = (await logged_in_client.get("/api/tasks?include_completed=true")).json()
    assert next(t for t in fetched if t["id"] == task["id"])["description"] == "Now with body"
