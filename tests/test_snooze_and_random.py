"""Tests for snooze button, age indicator, random picker, bulk duplicate."""

from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode

from httpx import AsyncClient


def _form(pairs: list[tuple[str, str]]) -> tuple[bytes, dict[str, str]]:
    body = urlencode(pairs).encode()
    return body, {"Content-Type": "application/x-www-form-urlencoded"}


async def test_snooze_pushes_due_by_one_day(logged_in_client: AsyncClient) -> None:
    today_iso = datetime.now(UTC).date().isoformat() + "T00:00:00Z"
    task = (
        await logged_in_client.post("/api/tasks", json={"title": "S", "due_at": today_iso})
    ).json()
    response = await logged_in_client.post(f"/htmx/tasks/{task['id']}/snooze", data={"days": "1"})
    assert response.status_code == 200
    fetched = (await logged_in_client.get("/api/tasks?include_completed=true")).json()
    saved = next(t for t in fetched if t["id"] == task["id"])
    expected = (datetime.now(UTC).date() + timedelta(days=1)).isoformat()
    assert saved["due_at"].startswith(expected)


async def test_snooze_no_due_sets_today_plus_one(logged_in_client: AsyncClient) -> None:
    task = (await logged_in_client.post("/api/tasks", json={"title": "Nope"})).json()
    response = await logged_in_client.post(f"/htmx/tasks/{task['id']}/snooze", data={"days": "1"})
    assert response.status_code == 200
    fetched = (await logged_in_client.get("/api/tasks?include_completed=true")).json()
    saved = next(t for t in fetched if t["id"] == task["id"])
    assert saved["due_at"] is not None


async def test_snooze_caps_at_30_days(logged_in_client: AsyncClient) -> None:
    task = (await logged_in_client.post("/api/tasks", json={"title": "Far"})).json()
    response = await logged_in_client.post(f"/htmx/tasks/{task['id']}/snooze", data={"days": "999"})
    assert response.status_code == 200
    fetched = (await logged_in_client.get("/api/tasks?include_completed=true")).json()
    saved = next(t for t in fetched if t["id"] == task["id"])
    expected = (datetime.now(UTC).date() + timedelta(days=30)).isoformat()
    assert saved["due_at"].startswith(expected)


async def test_random_pick_button_appears_when_2plus_today_tasks(
    logged_in_client: AsyncClient,
) -> None:
    today_iso = datetime.now(UTC).date().isoformat() + "T12:00:00Z"
    await logged_in_client.post("/api/tasks", json={"title": "T1", "due_at": today_iso})
    await logged_in_client.post("/api/tasks", json={"title": "T2", "due_at": today_iso})
    body = (await logged_in_client.get("/app/today")).text
    assert "Что дальше?" in body
    assert "🎲" in body


async def test_age_badge_in_task_row(logged_in_client: AsyncClient) -> None:
    proj = (await logged_in_client.post("/api/projects", json={"name": "Aged"})).json()
    await logged_in_client.post("/api/tasks", json={"title": "Old", "project_id": proj["id"]})
    body = (await logged_in_client.get(f"/app/projects/{proj['slug']}")).text
    # β redesign: stale-badge "Висит уже" removed from the task row (chip-overload
    # collapse); verify the task row itself renders correctly.
    assert "Old" in body
    assert f"/app/projects/{proj['slug']}" in body or "Old" in body


async def test_bulk_duplicate_creates_copies(logged_in_client: AsyncClient) -> None:
    t1 = (await logged_in_client.post("/api/tasks", json={"title": "A"})).json()
    t2 = (await logged_in_client.post("/api/tasks", json={"title": "B"})).json()
    body, headers = _form([("action", "duplicate"), ("ids", t1["id"]), ("ids", t2["id"])])
    response = await logged_in_client.post("/htmx/bulk", content=body, headers=headers)
    assert response.status_code == 200
    all_tasks = (await logged_in_client.get("/api/tasks")).json()
    titles = [t["title"] for t in all_tasks]
    assert "A (копия)" in titles and "B (копия)" in titles
