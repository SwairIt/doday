"""Tests for the second polish batch — snooze popover, subtask-stats endpoint,
sound FX toggle."""

from httpx import AsyncClient


async def test_snooze_popover_in_task_row(logged_in_client: AsyncClient) -> None:
    proj = (await logged_in_client.post("/api/projects", json={"name": "P"})).json()
    task = (
        await logged_in_client.post("/api/tasks", json={"title": "T", "project_id": proj["id"]})
    ).json()
    # β redesign: snooze dropdown removed from task row (moved to context-menu).
    # Verify snooze endpoint still works correctly.
    r = await logged_in_client.post(f"/doday/htmx/tasks/{task['id']}/snooze", data={"days": "1"})
    assert r.status_code == 200
    r3 = await logged_in_client.post(f"/doday/htmx/tasks/{task['id']}/snooze", data={"days": "3"})
    assert r3.status_code == 200
    r7 = await logged_in_client.post(f"/doday/htmx/tasks/{task['id']}/snooze", data={"days": "7"})
    assert r7.status_code == 200


async def test_subtask_stats_endpoint(logged_in_client: AsyncClient) -> None:
    parent = (await logged_in_client.post("/api/tasks", json={"title": "P"})).json()
    c1 = (
        await logged_in_client.post(
            "/api/tasks", json={"title": "C1", "parent_task_id": parent["id"]}
        )
    ).json()
    await logged_in_client.post("/api/tasks", json={"title": "C2", "parent_task_id": parent["id"]})
    await logged_in_client.post("/api/tasks", json={"title": "C3", "parent_task_id": parent["id"]})
    await logged_in_client.post(f"/api/tasks/{c1['id']}/complete")

    response = await logged_in_client.get(f"/api/tasks/{parent['id']}/subtask-stats")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 3
    assert body["done"] == 1


async def test_subtask_stats_zero_when_no_children(logged_in_client: AsyncClient) -> None:
    task = (await logged_in_client.post("/api/tasks", json={"title": "Solo"})).json()
    body = (await logged_in_client.get(f"/api/tasks/{task['id']}/subtask-stats")).json()
    assert body == {"total": 0, "done": 0}


async def test_subtask_stats_unknown_404(logged_in_client: AsyncClient) -> None:
    r = await logged_in_client.get("/api/tasks/00000000-0000-0000-0000-000000000000/subtask-stats")
    assert r.status_code == 404


async def test_sound_fx_partial_included(logged_in_client: AsyncClient) -> None:
    body = (await logged_in_client.get("/doday/app/today")).text
    assert "doday-sound-on" in body
    # Sound script reads localStorage flag and uses WebAudio.
    assert "AudioContext" in body
    assert "/toggle" in body  # hook regex pattern includes /toggle suffix


async def test_sound_toggle_in_profile(logged_in_client: AsyncClient) -> None:
    body = (await logged_in_client.get("/doday/app/settings")).text
    assert "Звук завершения" in body
    assert "doday-sound-on" in body


async def test_subtask_badge_template_present(logged_in_client: AsyncClient) -> None:
    proj = (await logged_in_client.post("/api/projects", json={"name": "BP"})).json()
    parent = (
        await logged_in_client.post(
            "/api/tasks", json={"title": "Parent", "project_id": proj["id"]}
        )
    ).json()
    child = (
        await logged_in_client.post(
            "/api/tasks",
            json={"title": "Child", "parent_task_id": parent["id"], "project_id": proj["id"]},
        )
    ).json()
    # β redesign: subtask-progress chip removed from task row (chip-overload collapse).
    # Verify the subtask-stats API endpoint still works (stats shown in detail panel).
    r = await logged_in_client.get(f"/api/tasks/{parent['id']}/subtask-stats")
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 1
    _ = child  # referenced to suppress unused-variable warning
