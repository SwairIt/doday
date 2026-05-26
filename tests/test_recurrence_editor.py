"""Tests that the inline recurrence editor in /doday/htmx/tasks/{id}/detail works."""

from datetime import UTC, datetime, timedelta

from httpx import AsyncClient


async def test_detail_panel_renders_recurrence_picker(logged_in_client: AsyncClient) -> None:
    """The detail panel always shows the recurrence section with picker controls."""
    t = (await logged_in_client.post("/api/tasks", json={"title": "T"})).json()
    body = (await logged_in_client.get(f"/doday/htmx/tasks/{t['id']}/detail")).text
    assert "Повтор" in body
    # All four cadence options must be available
    for val in ("daily", "weekly", "monthly", "yearly"):
        assert f'"recurrence": "{val}"' in body


async def test_set_recurrence_via_detail_endpoint(logged_in_client: AsyncClient) -> None:
    """PATCH /doday/htmx/tasks/{id}/detail with recurrence=weekly persists the value."""
    due = (datetime.now(UTC) + timedelta(days=1)).isoformat()
    t = (await logged_in_client.post("/api/tasks", json={"title": "Weekly", "due_at": due})).json()
    r = await logged_in_client.patch(
        f"/doday/htmx/tasks/{t['id']}/detail",
        data={"title": "Weekly", "description": "", "recurrence": "weekly"},
    )
    assert r.status_code == 200
    all_tasks = (await logged_in_client.get("/api/tasks")).json()
    refreshed = next(x for x in all_tasks if x["id"] == t["id"])
    assert refreshed["recurrence"] == "weekly"


async def test_clear_recurrence_via_detail_endpoint(logged_in_client: AsyncClient) -> None:
    """An empty recurrence value clears the rule."""
    due = (datetime.now(UTC) + timedelta(days=1)).isoformat()
    t = (
        await logged_in_client.post(
            "/api/tasks",
            json={"title": "Daily", "due_at": due, "recurrence": "daily"},
        )
    ).json()
    await logged_in_client.patch(
        f"/doday/htmx/tasks/{t['id']}/detail",
        data={"title": "Daily", "description": "", "recurrence": ""},
    )
    all_tasks = (await logged_in_client.get("/api/tasks")).json()
    refreshed = next(x for x in all_tasks if x["id"] == t["id"])
    assert refreshed["recurrence"] is None


async def test_omitting_recurrence_keeps_existing(logged_in_client: AsyncClient) -> None:
    """If the form doesn't include recurrence, the existing value is preserved."""
    due = (datetime.now(UTC) + timedelta(days=1)).isoformat()
    t = (
        await logged_in_client.post(
            "/api/tasks",
            json={"title": "M", "due_at": due, "recurrence": "monthly"},
        )
    ).json()
    await logged_in_client.patch(
        f"/doday/htmx/tasks/{t['id']}/detail",
        data={"title": "M", "description": "edited"},  # no recurrence field
    )
    all_tasks = (await logged_in_client.get("/api/tasks")).json()
    refreshed = next(x for x in all_tasks if x["id"] == t["id"])
    assert refreshed["recurrence"] == "monthly"
    assert refreshed["description"] == "edited"
