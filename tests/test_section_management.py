"""Tests for section rename + drag-to-reorder."""

from httpx import AsyncClient


async def test_rename_section_via_api(logged_in_client: AsyncClient) -> None:
    proj = (await logged_in_client.post("/api/projects", json={"name": "P"})).json()
    section = (
        await logged_in_client.post("/api/sections", json={"project_id": proj["id"], "name": "Old"})
    ).json()
    updated = (
        await logged_in_client.patch(f"/api/sections/{section['id']}", json={"name": "New"})
    ).json()
    assert updated["name"] == "New"


async def test_reorder_sections(logged_in_client: AsyncClient) -> None:
    proj = (await logged_in_client.post("/api/projects", json={"name": "P"})).json()
    a = (
        await logged_in_client.post("/api/sections", json={"project_id": proj["id"], "name": "A"})
    ).json()
    b = (
        await logged_in_client.post("/api/sections", json={"project_id": proj["id"], "name": "B"})
    ).json()
    c = (
        await logged_in_client.post("/api/sections", json={"project_id": proj["id"], "name": "C"})
    ).json()

    reordered = (
        await logged_in_client.post(
            "/api/sections/reorder",
            json={"project_id": proj["id"], "ids": [c["id"], a["id"], b["id"]]},
        )
    ).json()
    reordered.sort(key=lambda s: s["position"])
    assert [s["name"] for s in reordered] == ["C", "A", "B"]


async def test_reorder_rejects_foreign_section(logged_in_client: AsyncClient) -> None:
    proj_a = (await logged_in_client.post("/api/projects", json={"name": "PA"})).json()
    proj_b = (await logged_in_client.post("/api/projects", json={"name": "PB"})).json()
    sec_in_b = (
        await logged_in_client.post(
            "/api/sections", json={"project_id": proj_b["id"], "name": "ForeignSec"}
        )
    ).json()

    response = await logged_in_client.post(
        "/api/sections/reorder",
        json={"project_id": proj_a["id"], "ids": [sec_in_b["id"]]},
    )
    assert response.status_code == 400
