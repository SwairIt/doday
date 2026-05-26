"""Smoke tests for the V3/L3/L4/C9/C7 batch."""

from datetime import UTC, datetime

from httpx import AsyncClient


async def test_sidebar_includes_mini_calendar(logged_in_client: AsyncClient) -> None:
    body = (await logged_in_client.get("/doday/app/today")).text
    # Mini-calendar references the markers endpoint and renders weekday headers.
    assert "/api/projects/calendar-markers" in body


async def test_calendar_markers_endpoint_returns_dates(
    logged_in_client: AsyncClient,
) -> None:
    today_iso = datetime.now(UTC).date().isoformat() + "T18:00:00Z"
    await logged_in_client.post("/api/tasks", json={"title": "Marker task", "due_at": today_iso})
    body = (await logged_in_client.get("/api/projects/calendar-markers")).json()
    assert "dates" in body
    assert datetime.now(UTC).date().isoformat() in body["dates"]


async def test_task_row_has_project_color_dot(logged_in_client: AsyncClient) -> None:
    today_iso = datetime.now(UTC).date().isoformat() + "T18:00:00Z"
    await logged_in_client.post("/api/tasks", json={"title": "ColorDotTask", "due_at": today_iso})
    body = (await logged_in_client.get("/doday/app/today")).text
    # Project color dot uses bg-{color}-400 with default 'violet'.
    assert "bg-violet-400" in body or "bg-slate-400" in body


async def test_task_row_double_click_handler_present(
    logged_in_client: AsyncClient,
) -> None:
    today_iso = datetime.now(UTC).date().isoformat() + "T18:00:00Z"
    await logged_in_client.post("/api/tasks", json={"title": "DblClickEdit", "due_at": today_iso})
    body = (await logged_in_client.get("/doday/app/today")).text
    assert "ondblclick" in body
    assert "/edit" in body


async def test_context_menu_partial_loaded(logged_in_client: AsyncClient) -> None:
    body = (await logged_in_client.get("/doday/app/today")).text
    assert "task-ctx-menu" in body
    assert 'data-ctx="prio-1"' in body
    assert 'data-ctx="due-today"' in body


async def test_calendar_has_month_picker(logged_in_client: AsyncClient) -> None:
    body = (await logged_in_client.get("/doday/app/calendar")).text
    assert 'type="month"' in body
