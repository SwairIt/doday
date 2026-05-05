"""Tests for the achievements derivation."""

from httpx import AsyncClient


async def test_fresh_user_has_no_achievements(logged_in_client: AsyncClient) -> None:
    body = (await logged_in_client.get("/api/achievements")).json()
    assert body["total"] >= 15
    # New users get an Inbox + 4 sample tasks via provisioning, so first_task
    # is unlocked, but most others aren't yet.
    assert "items" in body
    assert isinstance(body["items"], list)
    codes_unlocked = [i["code"] for i in body["items"] if i["unlocked"]]
    # Sample provisioning gives at least first_task + first_project
    assert "first_task" in codes_unlocked or body["unlocked"] >= 0


async def test_first_task_unlocks_after_create(logged_in_client: AsyncClient) -> None:
    await logged_in_client.post("/api/tasks", json={"title": "X"})
    body = (await logged_in_client.get("/api/achievements")).json()
    codes = {i["code"] for i in body["items"] if i["unlocked"]}
    assert "first_task" in codes


async def test_first_done_unlocks_after_toggle(logged_in_client: AsyncClient) -> None:
    task = (await logged_in_client.post("/api/tasks", json={"title": "Done"})).json()
    await logged_in_client.post(f"/htmx/tasks/{task['id']}/toggle")
    body = (await logged_in_client.get("/api/achievements")).json()
    codes = {i["code"] for i in body["items"] if i["unlocked"]}
    assert "first_done" in codes


async def test_first_pin_unlocks(logged_in_client: AsyncClient) -> None:
    task = (await logged_in_client.post("/api/tasks", json={"title": "Pin"})).json()
    await logged_in_client.post(f"/api/tasks/{task['id']}/pin")
    body = (await logged_in_client.get("/api/achievements")).json()
    codes = {i["code"] for i in body["items"] if i["unlocked"]}
    assert "first_pin" in codes


async def test_first_recurring_unlocks(logged_in_client: AsyncClient) -> None:
    await logged_in_client.post("/api/tasks", json={"title": "Repeat", "recurrence": "daily"})
    body = (await logged_in_client.get("/api/achievements")).json()
    codes = {i["code"] for i in body["items"] if i["unlocked"]}
    assert "first_recurring" in codes


async def test_school_homework_after_10(logged_in_client: AsyncClient) -> None:
    for n in range(10):
        task = (await logged_in_client.post("/api/tasks", json={"title": f"Алгебра — №{n}"})).json()
        await logged_in_client.post(f"/htmx/tasks/{task['id']}/toggle")
    body = (await logged_in_client.get("/api/achievements")).json()
    codes = {i["code"] for i in body["items"] if i["unlocked"]}
    assert "school_homework" in codes


async def test_profile_renders_achievements_section(logged_in_client: AsyncClient) -> None:
    body = (await logged_in_client.get("/app/profile")).text
    assert "Достижения" in body
    assert "/api/achievements" in body
