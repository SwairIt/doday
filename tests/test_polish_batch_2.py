"""Tests for the second polish batch — snooze popover, subtask-stats endpoint,
sound FX toggle."""

from httpx import AsyncClient


async def test_snooze_popover_in_task_row(logged_in_client: AsyncClient) -> None:
    proj = (await logged_in_client.post("/api/projects", json={"name": "P"})).json()
    await logged_in_client.post("/api/tasks", json={"title": "T", "project_id": proj["id"]})
    body = (await logged_in_client.get(f"/app/projects/{proj['slug']}")).text
    # New popover offers multiple presets, not just +1.
    assert "+ 1 день" in body
    assert "+ 3 дня" in body
    assert "+ 1 неделя" in body
    assert "+ 2 недели" in body
    assert "До следующего пн" in body


async def test_subtask_stats_endpoint(logged_in_client: AsyncClient) -> None:
    parent = (await logged_in_client.post("/api/tasks", json={"title": "P"})).json()
    c1 = (
        await logged_in_client.post(
            "/api/tasks", json={"title": "C1", "parent_task_id": parent["id"]}
        )
    ).json()
    await logged_in_client.post(
        "/api/tasks", json={"title": "C2", "parent_task_id": parent["id"]}
    )
    await logged_in_client.post(
        "/api/tasks", json={"title": "C3", "parent_task_id": parent["id"]}
    )
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
    r = await logged_in_client.get(
        "/api/tasks/00000000-0000-0000-0000-000000000000/subtask-stats"
    )
    assert r.status_code == 404


async def test_sound_fx_partial_included(logged_in_client: AsyncClient) -> None:
    body = (await logged_in_client.get("/app/today")).text
    assert "doday-sound-on" in body
    # Sound script reads localStorage flag and uses WebAudio.
    assert "AudioContext" in body
    assert "/toggle" in body  # hook regex pattern includes /toggle suffix


async def test_sound_toggle_in_profile(logged_in_client: AsyncClient) -> None:
    body = (await logged_in_client.get("/app/profile")).text
    assert "Звук завершения" in body
    assert "doday-sound-on" in body


async def test_subtask_badge_template_present(logged_in_client: AsyncClient) -> None:
    proj = (await logged_in_client.post("/api/projects", json={"name": "BP"})).json()
    parent = (
        await logged_in_client.post(
            "/api/tasks", json={"title": "Parent", "project_id": proj["id"]}
        )
    ).json()
    await logged_in_client.post(
        "/api/tasks", json={"title": "Child", "parent_task_id": parent["id"], "project_id": proj["id"]}
    )
    body = (await logged_in_client.get(f"/app/projects/{proj['slug']}")).text
    # The badge is rendered for parent (top-level) only — fetches stats client-side.
    assert "/subtask-stats" in body
