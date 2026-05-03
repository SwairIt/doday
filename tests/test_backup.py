"""Tests for backup export/import endpoints."""

import json

from httpx import AsyncClient


async def test_export_returns_json_dump(logged_in_client: AsyncClient) -> None:
    proj = (await logged_in_client.post("/api/projects", json={"name": "Backup test"})).json()
    await logged_in_client.post("/api/tasks", json={"title": "Hello", "project_id": proj["id"]})
    response = await logged_in_client.get("/api/backup/export")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    assert "attachment" in response.headers["content-disposition"]
    data = response.json()
    assert data["format_version"] == 1
    assert any(p["name"] == "Backup test" for p in data["projects"])
    assert any(t["title"] == "Hello" for t in data["tasks"])


async def test_import_creates_new_entities(logged_in_client: AsyncClient) -> None:
    proj = (await logged_in_client.post("/api/projects", json={"name": "Original"})).json()
    section = (
        await logged_in_client.post(
            "/api/sections", json={"project_id": proj["id"], "name": "Sec1"}
        )
    ).json()
    await logged_in_client.post(
        "/api/tasks",
        json={"title": "Task A", "project_id": proj["id"], "section_id": section["id"]},
    )

    dump = (await logged_in_client.get("/api/backup/export")).json()
    files = {"file": ("backup.json", json.dumps(dump).encode(), "application/json")}
    result = await logged_in_client.post("/api/backup/import", files=files)
    assert result.status_code == 200
    counts = result.json()
    assert counts["projects"] >= 1
    assert counts["tasks"] >= 1
    assert counts["sections"] >= 1

    projects = (await logged_in_client.get("/api/projects")).json()
    assert sum(1 for p in projects if p["name"] == "Original") == 2


async def test_import_rejects_wrong_format(logged_in_client: AsyncClient) -> None:
    bad = {"format_version": 999, "projects": []}
    files = {"file": ("bad.json", json.dumps(bad).encode(), "application/json")}
    result = await logged_in_client.post("/api/backup/import", files=files)
    assert result.status_code == 400


async def test_import_rejects_invalid_json(logged_in_client: AsyncClient) -> None:
    files = {"file": ("garbage.json", b"not json at all {", "application/json")}
    result = await logged_in_client.post("/api/backup/import", files=files)
    assert result.status_code == 400


async def test_import_preserves_subtask_links(logged_in_client: AsyncClient) -> None:
    proj = (await logged_in_client.post("/api/projects", json={"name": "WithSubs"})).json()
    parent = (
        await logged_in_client.post(
            "/api/tasks", json={"title": "Parent", "project_id": proj["id"]}
        )
    ).json()
    await logged_in_client.post(
        "/api/tasks",
        json={"title": "Child", "project_id": proj["id"], "parent_task_id": parent["id"]},
    )

    dump = (await logged_in_client.get("/api/backup/export")).json()
    files = {"file": ("b.json", json.dumps(dump).encode(), "application/json")}
    result = await logged_in_client.post("/api/backup/import", files=files)
    assert result.status_code == 200
    assert result.json()["tasks"] == 2  # Parent + Child both re-imported

    parents = [
        t
        for t in (await logged_in_client.get("/api/tasks?include_completed=true")).json()
        if t["title"] == "Parent"
    ]
    assert len(parents) == 2  # original + imported

    for p in parents:
        subs_html = (await logged_in_client.get(f"/htmx/tasks/{p['id']}/subtasks")).text
        assert "Child" in subs_html
