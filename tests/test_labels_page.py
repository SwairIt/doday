"""Tests for /doday/app/labels management page."""

from httpx import AsyncClient


async def test_labels_page_empty(logged_in_client: AsyncClient) -> None:
    response = await logged_in_client.get("/doday/app/labels")
    assert response.status_code == 200
    assert "Лейблы" in response.text


async def test_labels_page_lists_existing(logged_in_client: AsyncClient) -> None:
    await logged_in_client.post("/api/labels", json={"name": "shopping", "color": "amber"})
    page = await logged_in_client.get("/doday/app/labels")
    assert "@shopping" in page.text


async def test_labels_page_shows_task_counts(logged_in_client: AsyncClient) -> None:
    label = (await logged_in_client.post("/api/labels", json={"name": "work"})).json()
    t = (await logged_in_client.post("/api/tasks", json={"title": "T"})).json()
    await logged_in_client.post(f"/doday/htmx/tasks/{t['id']}/labels/{label['id']}/toggle")
    page = await logged_in_client.get("/doday/app/labels")
    assert "@work" in page.text
    assert "1 задача" in page.text


async def test_labels_link_in_sidebar(logged_in_client: AsyncClient) -> None:
    page = await logged_in_client.get("/doday/app/today")
    assert "/doday/app/labels" in page.text
    assert "g l" in page.text
