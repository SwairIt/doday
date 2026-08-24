"""Tests for project management: favorites, archive, reorder, edit."""

from httpx import AsyncClient


async def test_create_multiple_projects(logged_in_client: AsyncClient) -> None:
    p1 = (await logged_in_client.post("/api/projects", json={"name": "Project A"})).json()
    p2 = (await logged_in_client.post("/api/projects", json={"name": "Project B"})).json()
    p3 = (await logged_in_client.post("/api/projects", json={"name": "Project C"})).json()
    listing = (await logged_in_client.get("/api/projects")).json()
    names = [p["name"] for p in listing]
    assert "Project A" in names
    assert "Project B" in names
    assert "Project C" in names
    assert p1["slug"] != p2["slug"] != p3["slug"]


async def test_toggle_favorite(logged_in_client: AsyncClient) -> None:
    proj = (await logged_in_client.post("/api/projects", json={"name": "Fav"})).json()
    assert proj["is_favorite"] is False
    updated = (
        await logged_in_client.patch(f"/api/projects/{proj['id']}", json={"is_favorite": True})
    ).json()
    assert updated["is_favorite"] is True


async def test_archive_then_restore(logged_in_client: AsyncClient) -> None:
    proj = (await logged_in_client.post("/api/projects", json={"name": "Arch"})).json()
    await logged_in_client.patch(f"/api/projects/{proj['id']}", json={"is_archived": True})

    active = (await logged_in_client.get("/api/projects")).json()
    assert all(p["id"] != proj["id"] for p in active)

    archived = (await logged_in_client.get("/api/projects/archived")).json()
    assert any(p["id"] == proj["id"] for p in archived)

    await logged_in_client.patch(f"/api/projects/{proj['id']}", json={"is_archived": False})
    active2 = (await logged_in_client.get("/api/projects")).json()
    assert any(p["id"] == proj["id"] for p in active2)


async def test_update_description(logged_in_client: AsyncClient) -> None:
    proj = (await logged_in_client.post("/api/projects", json={"name": "Desc"})).json()
    updated = (
        await logged_in_client.patch(
            f"/api/projects/{proj['id']}", json={"description": "Quick brown fox"}
        )
    ).json()
    assert updated["description"] == "Quick brown fox"


async def test_reorder_projects(logged_in_client: AsyncClient) -> None:
    p1 = (await logged_in_client.post("/api/projects", json={"name": "First"})).json()
    p2 = (await logged_in_client.post("/api/projects", json={"name": "Second"})).json()
    p3 = (await logged_in_client.post("/api/projects", json={"name": "Third"})).json()

    reordered = (
        await logged_in_client.post(
            "/api/projects/reorder", json={"ids": [p3["id"], p1["id"], p2["id"]]}
        )
    ).json()
    non_inbox = [p for p in reordered if not p["is_inbox"]]
    non_inbox.sort(key=lambda p: p["position"])
    assert non_inbox[0]["name"] == "Third"
    assert non_inbox[1]["name"] == "First"
    assert non_inbox[2]["name"] == "Second"


async def test_archive_view_renders(logged_in_client: AsyncClient) -> None:
    proj = (await logged_in_client.post("/api/projects", json={"name": "ArchView"})).json()
    await logged_in_client.patch(f"/api/projects/{proj['id']}", json={"is_archived": True})
    response = await logged_in_client.get("/app/projects-archive")
    assert response.status_code == 200
    assert "ArchView" in response.text
    assert "Восстановить" in response.text


async def test_favorite_appears_in_sidebar_section(logged_in_client: AsyncClient) -> None:
    proj = (await logged_in_client.post("/api/projects", json={"name": "Pinned"})).json()
    await logged_in_client.patch(f"/api/projects/{proj['id']}", json={"is_favorite": True})
    response = await logged_in_client.get("/app/today")
    assert response.status_code == 200
    assert "Избранное" in response.text
    assert "Pinned" in response.text
