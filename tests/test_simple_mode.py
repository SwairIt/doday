"""Tests for the simplified-mode views (/app/simple/*)."""

from __future__ import annotations

from httpx import AsyncClient


async def test_simple_today_requires_auth(client: AsyncClient) -> None:
    response = await client.get("/app/simple/today")
    assert response.status_code == 401


async def test_simple_today_renders_for_authed_user(
    logged_in_client: AsyncClient,
) -> None:
    response = await logged_in_client.get("/app/simple/today")
    assert response.status_code == 200
    body = response.text
    assert "Doday" in body
    assert "simple" in body
    assert 'href="/app/today"' in body


async def test_simple_inbox_requires_auth(client: AsyncClient) -> None:
    response = await client.get("/app/simple/inbox")
    assert response.status_code == 401


async def test_simple_inbox_renders_for_authed_user(
    logged_in_client: AsyncClient,
) -> None:
    response = await logged_in_client.get("/app/simple/inbox")
    assert response.status_code == 200
    body = response.text
    assert "Inbox" in body
    assert "без даты" in body


async def test_simple_add_form_renders(logged_in_client: AsyncClient) -> None:
    response = await logged_in_client.get("/app/simple/add")
    assert response.status_code == 200
    body = response.text
    assert "Новая задача" in body
    assert 'name="title"' in body
    assert 'name="due_date"' in body


async def test_simple_add_submit_creates_task(
    logged_in_client: AsyncClient,
) -> None:
    response = await logged_in_client.post(
        "/app/simple/add",
        data={"title": "Купить молоко (test)", "due_date": ""},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/app/simple/inbox"

    inbox = await logged_in_client.get("/app/simple/inbox")
    assert inbox.status_code == 200
    assert "Купить молоко (test)" in inbox.text


async def test_simple_add_submit_with_due_date_redirects_today(
    logged_in_client: AsyncClient,
) -> None:
    from datetime import UTC, datetime

    today_iso = datetime.now(UTC).date().isoformat()
    response = await logged_in_client.post(
        "/app/simple/add",
        data={"title": "Задача на сегодня", "due_date": today_iso},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/app/simple/today"


async def test_simple_add_empty_title_redirects_back(
    logged_in_client: AsyncClient,
) -> None:
    response = await logged_in_client.post(
        "/app/simple/add",
        data={"title": "", "due_date": ""},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/app/simple/add"


async def test_simple_task_toggle_marks_complete(
    logged_in_client: AsyncClient,
) -> None:
    await logged_in_client.post(
        "/app/simple/add",
        data={"title": "Toggle test", "due_date": ""},
        follow_redirects=False,
    )
    inbox = await logged_in_client.get("/app/simple/inbox")
    assert "Toggle test" in inbox.text
    import re

    task_match = re.search(r'id="simple-task-([a-f0-9-]+)"', inbox.text)
    assert task_match is not None
    task_id = task_match.group(1)

    toggle = await logged_in_client.post(f"/app/simple/task/{task_id}/toggle")
    assert toggle.status_code == 200
    assert "line-through" in toggle.text


async def test_simple_task_delete_returns_empty(
    logged_in_client: AsyncClient,
) -> None:
    await logged_in_client.post(
        "/app/simple/add",
        data={"title": "Delete test", "due_date": ""},
        follow_redirects=False,
    )
    inbox = await logged_in_client.get("/app/simple/inbox")
    import re

    task_match = re.search(r'id="simple-task-([a-f0-9-]+)"', inbox.text)
    assert task_match is not None
    task_id = task_match.group(1)

    delete = await logged_in_client.post(f"/app/simple/task/{task_id}/delete")
    assert delete.status_code == 200
    assert delete.text.strip() == ""

    inbox_after = await logged_in_client.get("/app/simple/inbox")
    assert "Delete test" not in inbox_after.text


async def test_simple_settings_renders(logged_in_client: AsyncClient) -> None:
    response = await logged_in_client.get("/app/simple/settings")
    assert response.status_code == 200
    body = response.text
    assert "Настройки" in body
    assert "Тема" in body
    assert "Аккаунт" in body
    assert 'href="/app/today"' in body


async def test_simple_pages_have_sidebar_nav(logged_in_client: AsyncClient) -> None:
    """All simple-mode pages render the sidebar with 3 navigation links."""
    for path in ["/app/simple/today", "/app/simple/inbox", "/app/simple/settings"]:
        response = await logged_in_client.get(path)
        assert response.status_code == 200
        assert 'href="/app/simple/today"' in response.text
        assert 'href="/app/simple/inbox"' in response.text
        assert 'href="/app/simple/settings"' in response.text
        # back-to-full link is always available
        assert 'href="/app/today"' in response.text


async def test_simple_pages_have_add_button(logged_in_client: AsyncClient) -> None:
    """Today/Inbox/Settings show the header «Добавить» button linking to /add."""
    for path in ["/app/simple/today", "/app/simple/inbox", "/app/simple/settings"]:
        response = await logged_in_client.get(path)
        body = response.text
        # add-page itself shows «Отмена» instead, not «Добавить»
        if path == "/app/simple/add":
            assert "Отмена" in body
        else:
            assert "/app/simple/add" in body


async def test_simple_toggle_requires_auth(client: AsyncClient) -> None:
    response = await client.post("/app/simple/task/00000000-0000-0000-0000-000000000001/toggle")
    assert response.status_code == 401
