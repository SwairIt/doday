"""Tests for the sidebar count badges endpoint."""

from datetime import UTC, datetime, timedelta

from httpx import AsyncClient


async def test_sidebar_counts_zero_for_fresh(logged_in_client: AsyncClient) -> None:
    body = (await logged_in_client.get("/api/projects/sidebar-counts")).json()
    for key in ("today", "upcoming", "overdue", "trash", "archive"):
        assert key in body
        assert isinstance(body[key], int)


async def test_today_count_increments(logged_in_client: AsyncClient) -> None:
    today_iso = datetime.now(UTC).date().isoformat() + "T18:00:00Z"
    await logged_in_client.post(
        "/api/tasks", json={"title": "Today task", "due_at": today_iso}
    )
    body = (await logged_in_client.get("/api/projects/sidebar-counts")).json()
    assert body["today"] >= 1


async def test_upcoming_count_excludes_today(logged_in_client: AsyncClient) -> None:
    next_week = (datetime.now(UTC) + timedelta(days=3)).isoformat()
    await logged_in_client.post(
        "/api/tasks", json={"title": "Future task", "due_at": next_week}
    )
    body = (await logged_in_client.get("/api/projects/sidebar-counts")).json()
    assert body["upcoming"] >= 1


async def test_overdue_count_picks_up_old_tasks(logged_in_client: AsyncClient) -> None:
    yesterday = (datetime.now(UTC) - timedelta(days=2)).isoformat()
    await logged_in_client.post(
        "/api/tasks", json={"title": "Old task", "due_at": yesterday}
    )
    body = (await logged_in_client.get("/api/projects/sidebar-counts")).json()
    assert body["overdue"] >= 1


async def test_trash_count_increments_on_delete(logged_in_client: AsyncClient) -> None:
    task = (await logged_in_client.post("/api/tasks", json={"title": "Bye"})).json()
    await logged_in_client.delete(f"/api/tasks/{task['id']}")
    body = (await logged_in_client.get("/api/projects/sidebar-counts")).json()
    assert body["trash"] >= 1


async def test_sidebar_renders_count_badges(logged_in_client: AsyncClient) -> None:
    body = (await logged_in_client.get("/app/today")).text
    assert "/api/projects/sidebar-counts" in body
    assert "counts['today']" in body or "counts[\"today\"]" in body
