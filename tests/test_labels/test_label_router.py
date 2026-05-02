"""HTTP-level tests for /api/labels and attach/detach."""

from httpx import AsyncClient


async def test_list_requires_auth(client: AsyncClient) -> None:
    response = await client.get("/api/labels")
    assert response.status_code == 401


async def test_create_and_list_label(logged_in_client: AsyncClient) -> None:
    response = await logged_in_client.post("/api/labels", json={"name": "Срочно", "color": "rose"})
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Срочно"
    assert body["color"] == "rose"

    listed = await logged_in_client.get("/api/labels")
    assert any(lab["id"] == body["id"] for lab in listed.json())


async def test_attach_and_detach_label(logged_in_client: AsyncClient) -> None:
    label = (await logged_in_client.post("/api/labels", json={"name": "L"})).json()
    task = (await logged_in_client.post("/api/tasks", json={"title": "T"})).json()

    attach = await logged_in_client.post(f"/api/tasks/{task['id']}/labels/{label['id']}")
    assert attach.status_code == 204

    listed = await logged_in_client.get(f"/api/tasks/{task['id']}/labels")
    assert [lab["id"] for lab in listed.json()] == [label["id"]]

    detach = await logged_in_client.delete(f"/api/tasks/{task['id']}/labels/{label['id']}")
    assert detach.status_code == 204

    after = await logged_in_client.get(f"/api/tasks/{task['id']}/labels")
    assert after.json() == []


async def test_delete_label(logged_in_client: AsyncClient) -> None:
    label = (await logged_in_client.post("/api/labels", json={"name": "Bye"})).json()
    delete = await logged_in_client.delete(f"/api/labels/{label['id']}")
    assert delete.status_code == 204
