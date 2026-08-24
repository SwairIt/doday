"""Tests for recurring picker in inline edit + project counts endpoint."""

from httpx import AsyncClient


async def test_edit_form_shows_recurrence_options(logged_in_client: AsyncClient) -> None:
    task = (await logged_in_client.post("/api/tasks", json={"title": "T"})).json()
    html = (await logged_in_client.get(f"/htmx/tasks/{task['id']}/edit")).text
    assert "Каждый день" in html
    assert "Каждую неделю" in html
    assert 'name="recurrence"' in html


async def test_edit_form_marks_existing_recurrence(logged_in_client: AsyncClient) -> None:
    task = (
        await logged_in_client.post("/api/tasks", json={"title": "T", "recurrence": "weekly"})
    ).json()
    assert task["recurrence"] == "weekly"
    html = (await logged_in_client.get(f"/htmx/tasks/{task['id']}/edit")).text
    # Radio for "weekly" should have the checked attribute (single space, but tolerate any).
    import re

    assert re.search(r'value="weekly"\s+checked', html) is not None


async def test_save_changes_recurrence(logged_in_client: AsyncClient) -> None:
    task = (await logged_in_client.post("/api/tasks", json={"title": "T"})).json()
    response = await logged_in_client.patch(
        f"/htmx/tasks/{task['id']}",
        data={"title": "T", "description": "", "recurrence": "monthly"},
    )
    assert response.status_code == 200
    fetched = (await logged_in_client.get("/api/tasks?include_completed=true")).json()
    assert next(t for t in fetched if t["id"] == task["id"])["recurrence"] == "monthly"


async def test_save_clears_recurrence(logged_in_client: AsyncClient) -> None:
    task = (
        await logged_in_client.post("/api/tasks", json={"title": "T", "recurrence": "daily"})
    ).json()
    await logged_in_client.patch(
        f"/htmx/tasks/{task['id']}",
        data={"title": "T", "description": "", "recurrence": ""},
    )
    fetched = (await logged_in_client.get("/api/tasks?include_completed=true")).json()
    assert next(t for t in fetched if t["id"] == task["id"])["recurrence"] is None


async def test_project_counts_endpoint(logged_in_client: AsyncClient) -> None:
    p1 = (await logged_in_client.post("/api/projects", json={"name": "Cnt1"})).json()
    p2 = (await logged_in_client.post("/api/projects", json={"name": "Cnt2"})).json()
    await logged_in_client.post("/api/tasks", json={"title": "A", "project_id": p1["id"]})
    await logged_in_client.post("/api/tasks", json={"title": "B", "project_id": p1["id"]})
    await logged_in_client.post("/api/tasks", json={"title": "C", "project_id": p2["id"]})
    counts = (await logged_in_client.get("/api/projects/counts")).json()
    assert counts.get(p1["id"]) == 2
    assert counts.get(p2["id"]) == 1


async def test_project_counts_excludes_completed(logged_in_client: AsyncClient) -> None:
    p = (await logged_in_client.post("/api/projects", json={"name": "Hide"})).json()
    t = (
        await logged_in_client.post("/api/tasks", json={"title": "Done", "project_id": p["id"]})
    ).json()
    await logged_in_client.post(f"/api/tasks/{t['id']}/complete")
    counts = (await logged_in_client.get("/api/projects/counts")).json()
    assert counts.get(p["id"], 0) == 0
