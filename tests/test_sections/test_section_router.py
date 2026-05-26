"""HTTP-level tests for /api/sections."""

from httpx import AsyncClient


async def test_create_section_via_api(logged_in_client: AsyncClient) -> None:
    proj = (await logged_in_client.post("/api/projects", json={"name": "Work"})).json()

    create = await logged_in_client.post(
        "/api/sections", json={"project_id": proj["id"], "name": "Todo"}
    )
    assert create.status_code == 201
    body = create.json()
    assert body["name"] == "Todo"
    assert body["project_id"] == proj["id"]
    assert body["position"] == 0


async def test_list_sections_for_project(logged_in_client: AsyncClient) -> None:
    proj = (await logged_in_client.post("/api/projects", json={"name": "P"})).json()
    await logged_in_client.post("/api/sections", json={"project_id": proj["id"], "name": "A"})
    await logged_in_client.post("/api/sections", json={"project_id": proj["id"], "name": "B"})

    listed = await logged_in_client.get("/api/sections", params={"project_id": proj["id"]})
    assert listed.status_code == 200
    names = [s["name"] for s in listed.json()]
    assert names == ["A", "B"]


async def test_update_section(logged_in_client: AsyncClient) -> None:
    proj = (await logged_in_client.post("/api/projects", json={"name": "P"})).json()
    s = (
        await logged_in_client.post("/api/sections", json={"project_id": proj["id"], "name": "Old"})
    ).json()

    patch = await logged_in_client.patch(f"/api/sections/{s['id']}", json={"name": "New"})
    assert patch.status_code == 200
    assert patch.json()["name"] == "New"


async def test_delete_section(logged_in_client: AsyncClient) -> None:
    proj = (await logged_in_client.post("/api/projects", json={"name": "P"})).json()
    s = (
        await logged_in_client.post("/api/sections", json={"project_id": proj["id"], "name": "S"})
    ).json()

    delete = await logged_in_client.delete(f"/api/sections/{s['id']}")
    assert delete.status_code == 204


async def test_htmx_create_section(logged_in_client: AsyncClient) -> None:
    proj = (await logged_in_client.post("/api/projects", json={"name": "P"})).json()
    response = await logged_in_client.post(
        "/doday/htmx/sections", data={"project_id": proj["id"], "name": "InlineSec"}
    )
    assert response.status_code == 200
    assert "InlineSec" in response.text
