"""Tests for task pin/unpin (закрепить наверх)."""

from datetime import UTC, datetime

from httpx import AsyncClient


async def test_pin_sets_pinned_at(logged_in_client: AsyncClient) -> None:
    task = (await logged_in_client.post("/api/tasks", json={"title": "Pin me"})).json()
    response = await logged_in_client.post(f"/api/tasks/{task['id']}/pin")
    assert response.status_code == 200
    assert response.json()["pinned_at"] is not None


async def test_unpin_clears_pinned_at(logged_in_client: AsyncClient) -> None:
    task = (await logged_in_client.post("/api/tasks", json={"title": "Pin me"})).json()
    await logged_in_client.post(f"/api/tasks/{task['id']}/pin")
    response = await logged_in_client.delete(f"/api/tasks/{task['id']}/pin")
    assert response.status_code == 200
    assert response.json()["pinned_at"] is None


async def test_pin_floats_task_to_top(logged_in_client: AsyncClient) -> None:
    a = (await logged_in_client.post("/api/tasks", json={"title": "Old"})).json()
    b = (await logged_in_client.post("/api/tasks", json={"title": "New"})).json()
    # without pinning, position-default ordering: A then B (creation order via position)
    listing = (await logged_in_client.get("/api/tasks")).json()
    assert listing[0]["id"] == a["id"]
    # pin B → it should jump to the top
    await logged_in_client.post(f"/api/tasks/{b['id']}/pin")
    listing = (await logged_in_client.get("/api/tasks")).json()
    assert listing[0]["id"] == b["id"]


async def test_pin_unknown_task_404(logged_in_client: AsyncClient) -> None:
    response = await logged_in_client.post("/api/tasks/00000000-0000-0000-0000-000000000000/pin")
    assert response.status_code == 404


async def test_pinned_badge_renders_in_today(logged_in_client: AsyncClient) -> None:
    today_iso = datetime.now(UTC).date().isoformat() + "T18:00:00Z"
    task = (
        await logged_in_client.post(
            "/api/tasks", json={"title": "Pinned today", "due_at": today_iso}
        )
    ).json()
    await logged_in_client.post(f"/api/tasks/{task['id']}/pin")
    body = (await logged_in_client.get("/app/today")).text
    assert "📌" in body
    assert "Pinned today" in body
