"""Tests for /api/tasks/export.csv."""

from datetime import UTC, datetime

from httpx import AsyncClient


async def test_export_empty_account_has_header(logged_in_client: AsyncClient) -> None:
    response = await logged_in_client.get("/api/tasks/export.csv")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    body = response.text.lstrip("﻿")
    first_line = body.splitlines()[0]
    for col in ("id", "title", "project", "due_at", "priority"):
        assert col in first_line


async def test_export_includes_active_task(logged_in_client: AsyncClient) -> None:
    await logged_in_client.post("/api/tasks", json={"title": "CSV pls"})
    body = (await logged_in_client.get("/api/tasks/export.csv")).text
    assert "CSV pls" in body


async def test_export_excludes_completed_by_default(logged_in_client: AsyncClient) -> None:
    task = (await logged_in_client.post("/api/tasks", json={"title": "Done one"})).json()
    await logged_in_client.post(f"/htmx/tasks/{task['id']}/toggle")
    body = (await logged_in_client.get("/api/tasks/export.csv")).text
    assert "Done one" not in body


async def test_export_includes_completed_when_asked(logged_in_client: AsyncClient) -> None:
    task = (await logged_in_client.post("/api/tasks", json={"title": "Done two"})).json()
    await logged_in_client.post(f"/htmx/tasks/{task['id']}/toggle")
    body = (await logged_in_client.get("/api/tasks/export.csv?include_completed=true")).text
    assert "Done two" in body


async def test_export_strips_newlines_from_description(logged_in_client: AsyncClient) -> None:
    today_iso = datetime.now(UTC).date().isoformat() + "T18:00:00Z"
    await logged_in_client.post(
        "/api/tasks",
        json={"title": "Multi", "description": "Line 1\nLine 2\rLine 3", "due_at": today_iso},
    )
    body = (await logged_in_client.get("/api/tasks/export.csv")).text
    # Description must end up on a single CSV row — we replaced newlines with spaces.
    assert "Line 1 Line 2 Line 3" in body


async def test_export_attaches_filename(logged_in_client: AsyncClient) -> None:
    response = await logged_in_client.get("/api/tasks/export.csv")
    assert "doday-tasks.csv" in response.headers["content-disposition"]
