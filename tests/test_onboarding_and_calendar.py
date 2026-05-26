"""Tests for onboarding card on /doday/app/today and calendar drag-drop wiring."""

from httpx import AsyncClient


async def test_onboarding_card_present_on_today(logged_in_client: AsyncClient) -> None:
    page = await logged_in_client.get("/doday/app/today")
    assert page.status_code == 200
    assert "Добро пожаловать в Doday" in page.text
    assert "doday-onboarded" in page.text  # localStorage key referenced in markup


async def test_calendar_chips_are_draggable(logged_in_client: AsyncClient) -> None:
    proj = (await logged_in_client.post("/api/projects", json={"name": "Cal"})).json()
    await logged_in_client.post(
        "/api/tasks",
        json={
            "title": "DragMe",
            "project_id": proj["id"],
            "due_at": "2026-12-15T00:00:00Z",
        },
    )
    page = await logged_in_client.get("/doday/app/calendar?month=2026-12")
    assert page.status_code == 200
    assert "DragMe" in page.text
    assert 'draggable="true"' in page.text
    assert "data-task-id=" in page.text
    assert "data-cal-day=" in page.text
    assert "Перетащи" in page.text  # drag hint copy can vary; just ensure it mentions drag


async def test_daily_goal_card_renders(logged_in_client: AsyncClient) -> None:
    page = await logged_in_client.get("/doday/app/today")
    assert page.status_code == 200
    assert "Цель на день" in page.text
    assert "doday-daily-goal" in page.text


async def test_daily_goal_count_reflects_completed_today(logged_in_client: AsyncClient) -> None:
    t1 = (await logged_in_client.post("/api/tasks", json={"title": "G1"})).json()
    t2 = (await logged_in_client.post("/api/tasks", json={"title": "G2"})).json()
    await logged_in_client.post(f"/api/tasks/{t1['id']}/complete")
    await logged_in_client.post(f"/api/tasks/{t2['id']}/complete")
    page = await logged_in_client.get("/doday/app/today")
    # Alpine x-data has `done: {{ done_today_count }}` rendered server-side.
    assert "done: 2" in page.text


async def test_calendar_drop_endpoint_works(logged_in_client: AsyncClient) -> None:
    """Drop fires PATCH /api/tasks/{id} with due_at — verify endpoint accepts it."""
    proj = (await logged_in_client.post("/api/projects", json={"name": "Cal2"})).json()
    task = (
        await logged_in_client.post(
            "/api/tasks",
            json={
                "title": "Reschedule",
                "project_id": proj["id"],
                "due_at": "2026-12-15T00:00:00Z",
            },
        )
    ).json()
    response = await logged_in_client.patch(
        f"/api/tasks/{task['id']}",
        json={"due_at": "2026-12-20T00:00:00Z", "due_date_only": True},
    )
    assert response.status_code == 200
    fetched = (await logged_in_client.get("/api/tasks")).json()
    saved = next(t for t in fetched if t["id"] == task["id"])
    assert saved["due_at"].startswith("2026-12-20")
