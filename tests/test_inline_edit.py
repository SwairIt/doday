"""Tests for inline edit endpoints (priority + due date popovers)."""

from httpx import AsyncClient


async def test_set_priority_via_htmx(logged_in_client: AsyncClient) -> None:
    task = (await logged_in_client.post("/api/tasks", json={"title": "T1"})).json()
    response = await logged_in_client.post(
        f"/doday/htmx/tasks/{task['id']}/priority", data={"priority": "p1"}
    )
    assert response.status_code == 200
    fetched = (await logged_in_client.get("/api/tasks?include_completed=true")).json()
    assert next(t for t in fetched if t["id"] == task["id"])["priority"] == "p1"


async def test_set_priority_invalid_value(logged_in_client: AsyncClient) -> None:
    task = (await logged_in_client.post("/api/tasks", json={"title": "T2"})).json()
    response = await logged_in_client.post(
        f"/doday/htmx/tasks/{task['id']}/priority", data={"priority": "p9"}
    )
    assert response.status_code == 400


async def test_set_due_date(logged_in_client: AsyncClient) -> None:
    task = (await logged_in_client.post("/api/tasks", json={"title": "T3"})).json()
    response = await logged_in_client.post(
        f"/doday/htmx/tasks/{task['id']}/due", data={"due": "2026-12-31"}
    )
    assert response.status_code == 200
    fetched = (await logged_in_client.get("/api/tasks")).json()
    due = next(t for t in fetched if t["id"] == task["id"])["due_at"]
    assert due is not None
    assert due.startswith("2026-12-31")


async def test_clear_due_date(logged_in_client: AsyncClient) -> None:
    created = await logged_in_client.post(
        "/api/tasks", json={"title": "T4", "due_at": "2026-06-15T00:00:00Z"}
    )
    task = created.json()
    response = await logged_in_client.post(f"/doday/htmx/tasks/{task['id']}/due", data={"due": ""})
    assert response.status_code == 200
    fetched = (await logged_in_client.get("/api/tasks")).json()
    assert next(t for t in fetched if t["id"] == task["id"])["due_at"] is None


async def test_set_due_invalid_format(logged_in_client: AsyncClient) -> None:
    task = (await logged_in_client.post("/api/tasks", json={"title": "T5"})).json()
    response = await logged_in_client.post(
        f"/doday/htmx/tasks/{task['id']}/due", data={"due": "not-a-date"}
    )
    assert response.status_code == 400
