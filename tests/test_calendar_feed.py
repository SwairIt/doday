"""Tests for the account-wide iCalendar feed."""

from datetime import UTC, datetime

from httpx import AsyncClient


async def test_empty_account_returns_valid_calendar(logged_in_client: AsyncClient) -> None:
    response = await logged_in_client.get("/api/calendar/all.ics")
    assert response.status_code == 200
    body = response.text
    assert "BEGIN:VCALENDAR" in body
    assert "END:VCALENDAR" in body
    assert "PRODID:-//Doday//Account Feed" in body


async def test_dated_task_appears_as_event(logged_in_client: AsyncClient) -> None:
    today_iso = datetime.now(UTC).date().isoformat() + "T12:00:00Z"
    await logged_in_client.post(
        "/api/tasks", json={"title": "Calendar test task", "due_at": today_iso}
    )
    body = (await logged_in_client.get("/api/calendar/all.ics")).text
    assert "BEGIN:VEVENT" in body
    assert "Calendar test task" in body


async def test_undated_task_does_not_appear(logged_in_client: AsyncClient) -> None:
    await logged_in_client.post("/api/tasks", json={"title": "No date here"})
    body = (await logged_in_client.get("/api/calendar/all.ics")).text
    assert "No date here" not in body


async def test_content_type_is_ics(logged_in_client: AsyncClient) -> None:
    response = await logged_in_client.get("/api/calendar/all.ics")
    assert response.headers["content-type"].startswith("text/calendar")


async def test_completed_task_marked(logged_in_client: AsyncClient) -> None:
    today_iso = datetime.now(UTC).date().isoformat() + "T12:00:00Z"
    task = (
        await logged_in_client.post("/api/tasks", json={"title": "Done task", "due_at": today_iso})
    ).json()
    await logged_in_client.post(f"/htmx/tasks/{task['id']}/toggle")
    body = (await logged_in_client.get("/api/calendar/all.ics")).text
    assert "STATUS:COMPLETED" in body


async def test_profile_shows_subscription_url(logged_in_client: AsyncClient) -> None:
    body = (await logged_in_client.get("/app/profile")).text
    assert "Календарь-подписка" in body
    assert "/api/calendar/all.ics" in body
