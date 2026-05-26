"""Integration tests for the signed-in app shell (sidebar + topbar + content)."""

from httpx import AsyncClient


async def test_app_redirect_requires_auth(client: AsyncClient) -> None:
    # Legacy /app → 301 to /doday/app → 302 to /doday/app/today → 401 unauth
    response = await client.get("/app", follow_redirects=True)
    assert response.status_code == 401


async def test_today_view_renders_for_logged_in(
    logged_in_client: AsyncClient,
) -> None:
    response = await logged_in_client.get("/doday/app/today")
    assert response.status_code == 200
    assert "Сегодня" in response.text  # view title
    assert "Doday" in response.text  # brand
    assert "Inbox" in response.text  # sidebar item


async def test_htmx_toggle_completes_task(logged_in_client: AsyncClient) -> None:
    create = await logged_in_client.post("/api/tasks", json={"title": "X"})
    task_id = create.json()["id"]

    toggle = await logged_in_client.post(f"/doday/htmx/tasks/{task_id}/toggle")
    assert toggle.status_code == 200
    assert "task-row" in toggle.text  # rendered partial
    assert "line-through" in toggle.text  # completed styling

    second = await logged_in_client.post(f"/doday/htmx/tasks/{task_id}/toggle")
    assert second.status_code == 200
    assert "line-through" not in second.text  # un-completed


async def test_today_view_anonymous_blocked(client: AsyncClient) -> None:
    response = await client.get("/doday/app/today")
    assert response.status_code == 401
