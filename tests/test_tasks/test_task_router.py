"""HTTP-level tests for /api/tasks."""

from datetime import UTC, datetime, timedelta

from httpx import AsyncClient


async def test_list_requires_auth(client: AsyncClient) -> None:
    response = await client.get("/api/tasks")
    assert response.status_code == 401


async def test_create_task_in_inbox_by_default(logged_in_client: AsyncClient) -> None:
    response = await logged_in_client.post("/api/tasks", json={"title": "Купить хлеб"})
    assert response.status_code == 201
    body = response.json()
    assert body["title"] == "Купить хлеб"
    assert body["is_completed"] is False
    assert body["priority"] == "p4"


async def test_complete_and_uncomplete_endpoint(logged_in_client: AsyncClient) -> None:
    create = await logged_in_client.post("/api/tasks", json={"title": "X"})
    task_id = create.json()["id"]

    done = await logged_in_client.post(f"/api/tasks/{task_id}/complete")
    assert done.status_code == 200
    assert done.json()["is_completed"] is True
    assert done.json()["completed_at"] is not None

    undone = await logged_in_client.post(f"/api/tasks/{task_id}/uncomplete")
    assert undone.status_code == 200
    assert undone.json()["is_completed"] is False


async def test_list_filters_by_project(logged_in_client: AsyncClient) -> None:
    proj = (await logged_in_client.post("/api/projects", json={"name": "Work"})).json()
    await logged_in_client.post("/api/tasks", json={"title": "in inbox"})
    await logged_in_client.post("/api/tasks", json={"title": "in work", "project_id": proj["id"]})

    in_proj = await logged_in_client.get("/api/tasks", params={"project_id": proj["id"]})
    assert in_proj.status_code == 200
    titles = [t["title"] for t in in_proj.json()]
    assert titles == ["in work"]


async def test_today_endpoint(logged_in_client: AsyncClient) -> None:
    yesterday = (datetime.now(UTC) - timedelta(days=1)).isoformat()
    await logged_in_client.post("/api/tasks", json={"title": "overdue", "due_at": yesterday})
    await logged_in_client.post("/api/tasks", json={"title": "no-date"})

    response = await logged_in_client.get("/api/tasks/today")
    assert response.status_code == 200
    titles = [t["title"] for t in response.json()]
    assert "overdue" in titles
    assert "no-date" not in titles


async def test_upcoming_endpoint(logged_in_client: AsyncClient) -> None:
    in_3 = (datetime.now(UTC) + timedelta(days=3)).isoformat()
    in_30 = (datetime.now(UTC) + timedelta(days=30)).isoformat()
    await logged_in_client.post("/api/tasks", json={"title": "soon", "due_at": in_3})
    await logged_in_client.post("/api/tasks", json={"title": "far", "due_at": in_30})

    response = await logged_in_client.get("/api/tasks/upcoming")
    titles = [t["title"] for t in response.json()]
    assert "soon" in titles
    assert "far" not in titles


async def test_delete_task(logged_in_client: AsyncClient) -> None:
    create = await logged_in_client.post("/api/tasks", json={"title": "Bye"})
    task_id = create.json()["id"]

    delete = await logged_in_client.delete(f"/api/tasks/{task_id}")
    assert delete.status_code == 204

    again = await logged_in_client.delete(f"/api/tasks/{task_id}")
    assert again.status_code == 404


async def test_patch_task(logged_in_client: AsyncClient) -> None:
    create = await logged_in_client.post("/api/tasks", json={"title": "Old"})
    task_id = create.json()["id"]
    patch = await logged_in_client.patch(
        f"/api/tasks/{task_id}", json={"title": "New", "priority": "p1"}
    )
    assert patch.status_code == 200
    assert patch.json()["title"] == "New"
    assert patch.json()["priority"] == "p1"


async def test_reorder_endpoint(logged_in_client: AsyncClient) -> None:
    proj = (await logged_in_client.post("/api/projects", json={"name": "Reorder"})).json()
    a = (
        await logged_in_client.post("/api/tasks", json={"title": "A", "project_id": proj["id"]})
    ).json()
    b = (
        await logged_in_client.post("/api/tasks", json={"title": "B", "project_id": proj["id"]})
    ).json()
    c = (
        await logged_in_client.post("/api/tasks", json={"title": "C", "project_id": proj["id"]})
    ).json()

    response = await logged_in_client.post(
        f"/api/projects/{proj['id']}/tasks/reorder",
        json={"ids": [c["id"], a["id"], b["id"]]},
    )
    assert response.status_code == 200
    assert [t["title"] for t in response.json()] == ["C", "A", "B"]
