"""Tests for project completion progress bar in header."""

from httpx import AsyncClient


async def test_no_progress_bar_for_empty_project(logged_in_client: AsyncClient) -> None:
    proj = (await logged_in_client.post("/api/projects", json={"name": "Empty"})).json()
    page = await logged_in_client.get(f"/doday/app/projects/{proj['slug']}")
    assert page.status_code == 200
    # No tasks → no percentage marker.
    assert "%</span>" not in page.text


async def test_progress_bar_shows_percentage(logged_in_client: AsyncClient) -> None:
    proj = (await logged_in_client.post("/api/projects", json={"name": "Progr"})).json()
    t1 = (
        await logged_in_client.post("/api/tasks", json={"title": "A", "project_id": proj["id"]})
    ).json()
    await logged_in_client.post("/api/tasks", json={"title": "B", "project_id": proj["id"]})
    await logged_in_client.post("/api/tasks", json={"title": "C", "project_id": proj["id"]})
    await logged_in_client.post(f"/api/tasks/{t1['id']}/complete")

    page = await logged_in_client.get(f"/doday/app/projects/{proj['slug']}")
    # 1 of 3 done → 33%
    assert "33%" in page.text


async def test_kanban_view_also_shows_progress(logged_in_client: AsyncClient) -> None:
    proj = (await logged_in_client.post("/api/projects", json={"name": "K"})).json()
    t1 = (
        await logged_in_client.post("/api/tasks", json={"title": "A", "project_id": proj["id"]})
    ).json()
    t2 = (
        await logged_in_client.post("/api/tasks", json={"title": "B", "project_id": proj["id"]})
    ).json()
    await logged_in_client.post(f"/api/tasks/{t1['id']}/complete")
    await logged_in_client.post(f"/api/tasks/{t2['id']}/complete")

    page = await logged_in_client.get(
        f"/doday/app/projects/{proj['slug']}", params={"view": "kanban"}
    )
    # 2 of 2 done → 100%
    assert "100%" in page.text
    assert "2 / 2" in page.text
