"""Tests for unlimited subtask nesting depth."""

from httpx import AsyncClient


async def test_create_subtask_of_subtask(logged_in_client: AsyncClient) -> None:
    parent = (await logged_in_client.post("/api/tasks", json={"title": "L0"})).json()
    child = (
        await logged_in_client.post(
            "/api/tasks", json={"title": "L1", "parent_task_id": parent["id"]}
        )
    ).json()
    grandchild = await logged_in_client.post(
        "/api/tasks", json={"title": "L2", "parent_task_id": child["id"]}
    )
    assert grandchild.status_code == 201
    assert grandchild.json()["parent_task_id"] == child["id"]


async def test_create_three_levels_deep(logged_in_client: AsyncClient) -> None:
    a = (await logged_in_client.post("/api/tasks", json={"title": "A"})).json()
    b = (
        await logged_in_client.post("/api/tasks", json={"title": "B", "parent_task_id": a["id"]})
    ).json()
    c = (
        await logged_in_client.post("/api/tasks", json={"title": "C", "parent_task_id": b["id"]})
    ).json()
    d = await logged_in_client.post("/api/tasks", json={"title": "D", "parent_task_id": c["id"]})
    assert d.status_code == 201


async def test_reparent_to_subtask_via_patch(logged_in_client: AsyncClient) -> None:
    parent = (await logged_in_client.post("/api/tasks", json={"title": "P"})).json()
    child = (
        await logged_in_client.post(
            "/api/tasks", json={"title": "C", "parent_task_id": parent["id"]}
        )
    ).json()
    standalone = (await logged_in_client.post("/api/tasks", json={"title": "S"})).json()
    response = await logged_in_client.patch(
        f"/api/tasks/{standalone['id']}", json={"parent_task_id": child["id"]}
    )
    assert response.status_code == 200
    assert response.json()["parent_task_id"] == child["id"]
