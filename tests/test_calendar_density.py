"""Tests for the dense-month + day-modal + week-view calendar additions."""

from datetime import UTC, datetime

from httpx import AsyncClient


async def test_month_view_has_dense_toggle(logged_in_client: AsyncClient) -> None:
    body = (await logged_in_client.get("/app/calendar")).text
    assert "doday-cal-dense" in body
    # The dense / list toggle copy is one of these two strings.
    assert "Точки" in body or "Список" in body


async def test_month_view_has_clickable_more_when_overflow(
    logged_in_client: AsyncClient,
) -> None:
    today = datetime.now(UTC).date().isoformat() + "T18:00:00Z"
    for n in range(5):
        await logged_in_client.post(
            "/api/tasks", json={"title": f"Overflow {n}", "due_at": today}
        )
    body = (await logged_in_client.get("/app/calendar")).text
    # Server-rendered "+N ещё" is now a button (was just text before).
    assert "ещё" in body
    assert "openDay(" in body  # Alpine handler reference


async def test_week_view_renders(logged_in_client: AsyncClient) -> None:
    body = (await logged_in_client.get("/app/calendar?view=week")).text
    # 7 weekday names + week-grid id are unique to the week template.
    assert 'id="week-grid"' in body
    assert "Понедельник" in body
    assert "Воскресенье" in body


async def test_week_view_shows_tasks_in_correct_day(
    logged_in_client: AsyncClient,
) -> None:
    today_iso = datetime.now(UTC).date().isoformat() + "T18:00:00Z"
    await logged_in_client.post(
        "/api/tasks", json={"title": "WeekViewTask42", "due_at": today_iso}
    )
    body = (await logged_in_client.get("/app/calendar?view=week")).text
    assert "WeekViewTask42" in body


async def test_week_view_navigation_links_present(logged_in_client: AsyncClient) -> None:
    body = (await logged_in_client.get("/app/calendar?view=week")).text
    assert "?view=week&week=" in body  # prev/next week links
    assert "Эта неделя" in body
    assert "/app/calendar" in body  # back-to-month link
