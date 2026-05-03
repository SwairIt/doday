"""Tests for UI polish: keyboard shortcuts overlay, project description, comment edit."""

from httpx import AsyncClient


async def test_shortcuts_overlay_included(logged_in_client: AsyncClient) -> None:
    response = await logged_in_client.get("/app/today")
    assert response.status_code == 200
    assert "Горячие клавиши" in response.text
    assert "g + …" in response.text


async def test_project_description_appears_in_header(logged_in_client: AsyncClient) -> None:
    proj = (await logged_in_client.post("/api/projects", json={"name": "Desc"})).json()
    await logged_in_client.patch(
        f"/api/projects/{proj['id']}", json={"description": "Тестовое описание проекта"}
    )
    page = await logged_in_client.get(f"/app/projects/{proj['slug']}")
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
    page = await logged_in_client.get(f"/app/projects/{proj['slug']}")
    assert "data-quickadd-input" in page.text
