"""Tests for JSON search endpoint."""

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
