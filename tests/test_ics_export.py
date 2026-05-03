"""Tests for iCalendar (.ics) project export."""

from httpx import AsyncClient


async def test_ics_export_basic_envelope(logged_in_client: AsyncClient) -> None:
    proj = (await logged_in_client.post("/api/projects", json={"name": "IcalProj"})).json()
    response = await logged_in_client.get(f"/api/projects/{proj['id']}/export.ics")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/calendar")
    body = response.text
    assert body.startswith("BEGIN:VCALENDAR")
    assert "END:VCALENDAR" in body
    assert "VERSION:2.0" in body
    assert "PRODID:-//Doday//Project Export//EN" in body
    assert "X-WR-CALNAME:IcalProj" in body


async def test_ics_excludes_tasks_without_due(logged_in_client: AsyncClient) -> None:
    proj = (await logged_in_client.post("/api/projects", json={"name": "P"})).json()
    await logged_in_client.post("/api/tasks", json={"title": "NoDate", "project_id": proj["id"]})
    body = (await logged_in_client.get(f"/api/projects/{proj['id']}/export.ics")).text
    assert "NoDate" not in body
    assert "BEGIN:VEVENT" not in body


async def test_ics_includes_dated_task_as_event(logged_in_client: AsyncClient) -> None:
    proj = (await logged_in_client.post("/api/projects", json={"name": "P"})).json()
    await logged_in_client.post(
        "/api/tasks",
        json={
            "title": "Meet team",
            "project_id": proj["id"],
            "due_at": "2026-12-15T00:00:00Z",
            "due_date_only": True,
            "priority": "p1",
        },
    )
    body = (await logged_in_client.get(f"/api/projects/{proj['id']}/export.ics")).text
    assert "BEGIN:VEVENT" in body
    assert "END:VEVENT" in body
    assert "DTSTART;VALUE=DATE:20261215" in body
    assert "SUMMARY:[!1] Meet team" in body
    assert "STATUS:CONFIRMED" in body


async def test_ics_dated_with_time(logged_in_client: AsyncClient) -> None:
    proj = (await logged_in_client.post("/api/projects", json={"name": "P"})).json()
    await logged_in_client.post(
        "/api/tasks",
        json={
            "title": "Call",
            "project_id": proj["id"],
            "due_at": "2026-06-15T13:30:00Z",
            "due_date_only": False,
        },
    )
    body = (await logged_in_client.get(f"/api/projects/{proj['id']}/export.ics")).text
    assert "DTSTART:20260615T133000Z" in body


async def test_ics_recurrence_emits_rrule(logged_in_client: AsyncClient) -> None:
    proj = (await logged_in_client.post("/api/projects", json={"name": "P"})).json()
    await logged_in_client.post(
        "/api/tasks",
        json={
            "title": "Standup",
            "project_id": proj["id"],
            "due_at": "2026-06-15T00:00:00Z",
            "recurrence": "weekly",
        },
    )
    body = (await logged_in_client.get(f"/api/projects/{proj['id']}/export.ics")).text
    assert "RRULE:FREQ=WEEKLY" in body


async def test_ics_escapes_special_chars(logged_in_client: AsyncClient) -> None:
    proj = (await logged_in_client.post("/api/projects", json={"name": "P"})).json()
    await logged_in_client.post(
        "/api/tasks",
        json={
            "title": "Buy milk, bread; eggs",
            "project_id": proj["id"],
            "due_at": "2026-06-15T00:00:00Z",
        },
    )
    body = (await logged_in_client.get(f"/api/projects/{proj['id']}/export.ics")).text
    assert "Buy milk\\, bread\\; eggs" in body


async def test_ics_unknown_project_404(logged_in_client: AsyncClient) -> None:
    response = await logged_in_client.get(
        "/api/projects/00000000-0000-0000-0000-000000000000/export.ics"
    )
    assert response.status_code == 404
