"""Tests for the completed-tasks history page."""

from httpx import AsyncClient


async def test_done_view_empty_state(logged_in_client: AsyncClient) -> None:
    response = await logged_in_client.get("/doday/app/done")
    assert response.status_code == 200
    assert "Завершённые задачи" in response.text


async def test_done_view_lists_completed_task(logged_in_client: AsyncClient) -> None:
    task = (await logged_in_client.post("/api/tasks", json={"title": "DoneOne"})).json()
    await logged_in_client.post(f"/api/tasks/{task['id']}/complete")
    page = await logged_in_client.get("/doday/app/done")
    assert page.status_code == 200
    assert "DoneOne" in page.text
    assert "Сегодня" in page.text


async def test_done_view_excludes_active_tasks(logged_in_client: AsyncClient) -> None:
    await logged_in_client.post("/api/tasks", json={"title": "StillActive"})
    page = await logged_in_client.get("/doday/app/done")
    assert "StillActive" not in page.text


async def test_done_view_link_in_sidebar(logged_in_client: AsyncClient) -> None:
    page = await logged_in_client.get("/doday/app/today")
    assert "/doday/app/done" in page.text
    assert "Завершённые" in page.text


async def test_done_shortcut_in_overlay(logged_in_client: AsyncClient) -> None:
    page = await logged_in_client.get("/doday/app/today")
    assert "g d" in page.text
