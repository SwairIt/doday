"""HTTP-level tests for /api/projects."""

from httpx import AsyncClient


async def test_list_projects_requires_auth(client: AsyncClient) -> None:
    response = await client.get("/api/projects")
    assert response.status_code == 401


async def test_create_and_list_project(logged_in_client: AsyncClient) -> None:
    create = await logged_in_client.post(
        "/api/projects", json={"name": "Учёба", "color": "fuchsia"}
    )
    assert create.status_code == 201
    body = create.json()
    assert body["name"] == "Учёба"
    assert body["color"] == "fuchsia"
    assert body["is_inbox"] is False

    listed = await logged_in_client.get("/api/projects")
    assert listed.status_code == 200
    assert any(p["id"] == body["id"] for p in listed.json())


async def test_create_project_validates_color(logged_in_client: AsyncClient) -> None:
    response = await logged_in_client.post(
        "/api/projects", json={"name": "X", "color": "neon-yellow"}
    )
    assert response.status_code == 422


async def test_update_project(logged_in_client: AsyncClient) -> None:
    create = await logged_in_client.post("/api/projects", json={"name": "First", "color": "violet"})
    project_id = create.json()["id"]

    patch = await logged_in_client.patch(
        f"/api/projects/{project_id}", json={"name": "Renamed", "color": "rose"}
    )
    assert patch.status_code == 200
    assert patch.json()["name"] == "Renamed"
    assert patch.json()["color"] == "rose"


async def test_delete_project(logged_in_client: AsyncClient) -> None:
    create = await logged_in_client.post("/api/projects", json={"name": "Bye"})
    project_id = create.json()["id"]

    delete = await logged_in_client.delete(f"/api/projects/{project_id}")
    assert delete.status_code == 204

    after = await logged_in_client.get("/api/projects")
    assert all(p["id"] != project_id for p in after.json())


async def test_update_404_for_other_users_project(
    logged_in_client: AsyncClient,
) -> None:
    response = await logged_in_client.patch(
        "/api/projects/00000000-0000-0000-0000-000000000000",
        json={"name": "Nope"},
    )
    assert response.status_code == 404
