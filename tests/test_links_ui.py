"""Tests that the task-detail panel renders the links section + JSON search."""

from httpx import AsyncClient


async def test_search_json_format(logged_in_client: AsyncClient) -> None:
    """`/htmx/search?q=...&format=json` returns a structured task list."""
    a = (await logged_in_client.post("/api/tasks", json={"title": "kangaroo task"})).json()
    r = await logged_in_client.get("/htmx/search?q=kangaroo&format=json")
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body["tasks"], list)
    ids = [t["id"] for t in body["tasks"]]
    assert a["id"] in ids
    found = next(t for t in body["tasks"] if t["id"] == a["id"])
    assert found["title"] == "kangaroo task"
    assert "project_name" in found


async def test_search_json_short_query(logged_in_client: AsyncClient) -> None:
    r = await logged_in_client.get("/htmx/search?q=x&format=json")
    assert r.status_code == 200
    assert r.json() == {"tasks": [], "projects": []}


async def test_task_detail_renders_links_panel(logged_in_client: AsyncClient) -> None:
    """The detail panel shipped HTML must include the links section + add-link UI."""
    a = (await logged_in_client.post("/api/tasks", json={"title": "Has links"})).json()
    body = (await logged_in_client.get(f"/htmx/tasks/{a['id']}/detail")).text
    assert "Связи" in body
    assert "Добавить связь" in body
    assert "/api/tasks/" in body
    assert "/links" in body


async def test_task_detail_shows_existing_links(logged_in_client: AsyncClient) -> None:
    """Existing links are rendered in the detail panel as clickable chips."""
    a = (await logged_in_client.post("/api/tasks", json={"title": "Source"})).json()
    b = (await logged_in_client.post("/api/tasks", json={"title": "Target task ABC"})).json()
    await logged_in_client.post(
        f"/api/tasks/{a['id']}/links",
        json={"target_task_id": b["id"], "note": "blocks"},
    )
    body = (await logged_in_client.get(f"/htmx/tasks/{a['id']}/detail")).text
    assert "Target task ABC" in body
    assert "blocks" in body
