"""Smoke-tests for /miniapp/* tab pages — auth-redirect + render."""

from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.tasks.models import TaskPriority
from app.tasks.service import create_task

PAGES = ["/miniapp/", "/miniapp/inbox", "/miniapp/calendar", "/miniapp/projects", "/miniapp/me"]


@pytest.mark.parametrize("path", PAGES)
async def test_miniapp_page_unauth_redirects_to_link(client: AsyncClient, path: str) -> None:
    r = await client.get(path, follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"] == "/miniapp/link"


@pytest.mark.parametrize("path", PAGES)
async def test_miniapp_page_authed_renders(logged_in_client: AsyncClient, path: str) -> None:
    r = await logged_in_client.get(path, follow_redirects=False)
    assert r.status_code == 200
    body = r.text
    assert "Doday" in body
    assert "miniapp-nav" in body  # bottom-nav present


async def test_miniapp_assets_js_served(client: AsyncClient) -> None:
    r = await client.get("/miniapp/assets/miniapp.js")
    assert r.status_code == 200
    assert "javascript" in r.headers["content-type"]
    assert "Telegram.WebApp" in r.text
    assert "applyTheme" in r.text
    assert "attemptAuth" in r.text
    # Auth-success on link-page should redirect to /miniapp/
    assert "if (onLinkPage)" in r.text or "onLinkPage" in r.text


async def test_miniapp_link_page_unauth_renders(client: AsyncClient) -> None:
    """/miniapp/link не требует auth — это onboarding-экран."""
    r = await client.get("/miniapp/link?telegram_user_id=12345")
    assert r.status_code == 200
    assert "Привяжи аккаунт Doday" in r.text
    assert "12345" in r.text
    assert "miniapp-nav" in r.text  # bottom-nav present


async def test_miniapp_link_authed_redirects_to_today(logged_in_client: AsyncClient) -> None:
    """Если юзер УЖЕ залогинен — onboarding не нужен, редирект на /."""
    r = await logged_in_client.get("/miniapp/link", follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"] == "/miniapp/"


async def test_api_parse_returns_preview(logged_in_client: AsyncClient) -> None:
    """MB2: /miniapp/api/parse возвращает разбор для quick-add preview."""
    r = await logged_in_client.post("/miniapp/api/parse", json={"text": "Покупки завтра !!"})
    assert r.status_code == 200
    data = r.json()
    assert "Покупки" in data["title"]
    assert data["due_at"]  # завтрашняя дата
    assert data["priority"] == "p3"  # !! = P3
    assert "label_names" in data


async def test_api_parse_unauth_401(client: AsyncClient) -> None:
    r = await client.post("/miniapp/api/parse", json={"text": "test"})
    assert r.status_code == 401


async def test_api_create_task_inbox(
    db_session: AsyncSession, logged_in_client: AsyncClient
) -> None:
    """MB2: POST /miniapp/api/tasks создаёт задачу в Inbox."""
    r = await logged_in_client.post(
        "/miniapp/api/tasks", json={"text": "Тестовая задача завтра !!"}
    )
    assert r.status_code == 201
    data = r.json()
    assert "Тестовая задача" in data["title"]
    assert data["priority"] == "p3"  # !! = P3
    assert data["due_at"]


async def test_api_create_task_empty_text_400(logged_in_client: AsyncClient) -> None:
    r = await logged_in_client.post("/miniapp/api/tasks", json={"text": "   "})
    assert r.status_code == 400


async def test_api_complete_task_toggles(
    db_session: AsyncSession, logged_in_client: AsyncClient
) -> None:
    """MB3-prep: POST /miniapp/api/tasks/<id>/complete переключает статус."""
    from sqlalchemy import select

    from app.auth.models import User
    from app.projects.service import ensure_inbox

    user = (
        await db_session.execute(select(User).where(User.email == "logged-in@example.com"))
    ).scalar_one()
    inbox = await ensure_inbox(db_session, user.id)
    from app.tasks.service import create_task as svc_create_task

    task = await svc_create_task(db_session, user.id, title="To complete", project_id=inbox.id)
    await db_session.commit()

    # First call — completes
    r = await logged_in_client.post(f"/miniapp/api/tasks/{task.id}/complete")
    assert r.status_code == 200
    assert r.json()["is_completed"] is True
    # Second call — un-completes
    r = await logged_in_client.post(f"/miniapp/api/tasks/{task.id}/complete")
    assert r.status_code == 200
    assert r.json()["is_completed"] is False


async def test_today_page_renders_overdue_and_today_tasks(
    db_session: AsyncSession, logged_in_client: AsyncClient
) -> None:
    """MB1: Today показывает просрочку, сегодняшние, прогресс-кольцо."""
    from sqlalchemy import select

    from app.auth.models import User

    user = (
        await db_session.execute(select(User).where(User.email == "logged-in@example.com"))
    ).scalar_one()
    from app.projects.service import ensure_inbox

    inbox = await ensure_inbox(db_session, user.id)

    # Задача overdue (вчера)
    yesterday = datetime.now(UTC) - timedelta(days=1)
    await create_task(
        db_session,
        user.id,
        title="Overdue task",
        project_id=inbox.id,
        due_at=yesterday,
        due_date_only=True,
        priority=TaskPriority.P1,
    )
    # Задача сегодня
    today = datetime.now(UTC)
    await create_task(
        db_session,
        user.id,
        title="Today task",
        project_id=inbox.id,
        due_at=today,
        due_date_only=True,
    )
    await db_session.commit()

    r = await logged_in_client.get("/miniapp/", follow_redirects=False)
    assert r.status_code == 200
    body = r.text
    assert "Overdue task" in body
    assert "Today task" in body
    assert "Просрочено" in body
    assert "P1" in body  # priority chip
