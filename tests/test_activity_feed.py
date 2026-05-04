"""Tests for /app/activity feed page."""

from httpx import AsyncClient


async def test_activity_empty(logged_in_client: AsyncClient) -> None:
    response = await logged_in_client.get("/app/activity")
    assert response.status_code == 200
    assert "Активность" in response.text


async def test_activity_lists_created_task(logged_in_client: AsyncClient) -> None:
    proj = (await logged_in_client.post("/api/projects", json={"name": "Act"})).json()
    await logged_in_client.post("/api/tasks", json={"title": "JustMade", "project_id": proj["id"]})
    page = await logged_in_client.get("/app/activity")
    assert "JustMade" in page.text
    assert "Создал" in page.text
    assert "Act" in page.text


async def test_activity_lists_completed_task(logged_in_client: AsyncClient) -> None:
    t = (await logged_in_client.post("/api/tasks", json={"title": "Closed"})).json()
    await logged_in_client.post(f"/api/tasks/{t['id']}/complete")
    page = await logged_in_client.get("/app/activity")
    assert "Closed" in page.text
    assert "Завершил" in page.text


async def test_activity_lists_comment(logged_in_client: AsyncClient) -> None:
    t = (await logged_in_client.post("/api/tasks", json={"title": "Talk"})).json()
    await logged_in_client.post(f"/api/tasks/{t['id']}/comments", json={"body": "hello world note"})
    page = await logged_in_client.get("/app/activity")
    assert "Talk" in page.text
    assert "hello world note" in page.text
    assert "Комментарий к" in page.text


async def test_activity_link_in_sidebar(logged_in_client: AsyncClient) -> None:
    page = await logged_in_client.get("/app/today")
    assert "/app/activity" in page.text
    assert "Активность" in page.text
    assert "g v" in page.text  # shortcut listed in overlay
