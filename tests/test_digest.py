"""Tests for the morning email digest module.

Covers:
- gather_tasks_for partitions tasks correctly into overdue/today/tomorrow
- compose_subject pluralisation: 1 задача / 2-4 задачи / 5+ задач
- compose_text/html include all task titles with proper section headers
- send_morning_digest skips empty users (no tasks) → False, no email
- send_morning_digest sets last_sent_at on success
- /api/profile/morning-digest toggles the DB flag
- /api/digest/send-now requires auth (401) and works when logged in
- /api/digest/cron-trigger validates X-Cron-Token header
"""

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.auth.schemas import RegisterIn
from app.auth.service import register_user
from app.digest.service import (
    compose_html,
    compose_subject,
    compose_text,
    gather_tasks_for,
    send_morning_digest,
    send_morning_digests_for_all_users,
)
from app.projects.service import ensure_inbox
from app.tasks.models import TaskPriority
from app.tasks.service import create_task


@pytest.fixture
async def opted_in_user(db_session: AsyncSession) -> AsyncIterator[User]:
    user = await register_user(
        db_session, RegisterIn(email="digest@example.com", password="strongpass123")
    )
    user.email_verified_at = datetime.now(UTC)
    user.morning_digest_enabled = True
    await db_session.commit()
    await db_session.refresh(user)
    yield user


_FIXED_NOW = datetime(2026, 5, 9, 12, 0, 0, tzinfo=UTC)


async def _seed_tasks(session: AsyncSession, user: User) -> None:
    """Create one task each in: overdue, today, tomorrow, no-date.

    All due_at values are computed off `_FIXED_NOW` so the test is
    timezone- and clock-independent. Pass the same `_FIXED_NOW` into
    `gather_tasks_for` / `send_morning_digest` to assert deterministic
    bucketing.
    """
    inbox = await ensure_inbox(session, user.id)
    await create_task(
        session,
        user.id,
        title="Просрочка",
        project_id=inbox.id,
        priority=TaskPriority.P1,
        due_at=_FIXED_NOW - timedelta(days=2),
    )
    await create_task(
        session,
        user.id,
        title="Сегодня важное",
        project_id=inbox.id,
        priority=TaskPriority.P2,
        due_at=_FIXED_NOW + timedelta(hours=4),
    )
    await create_task(
        session,
        user.id,
        title="Завтра",
        project_id=inbox.id,
        priority=TaskPriority.P3,
        due_at=_FIXED_NOW + timedelta(days=1, hours=2),
    )
    await create_task(
        session, user.id, title="Без даты", project_id=inbox.id, priority=TaskPriority.P4
    )


# --- compose_* unit tests ---


def test_compose_subject_pluralisation() -> None:
    today = datetime(2026, 5, 9).date()
    assert "1 задача" in compose_subject(today, 1)
    assert "2 задачи" in compose_subject(today, 2)
    assert "3 задачи" in compose_subject(today, 3)
    assert "5 задач" in compose_subject(today, 5)
    assert "11 задач" in compose_subject(today, 11)
    assert "21 задача" in compose_subject(today, 21)
    assert "9 мая" in compose_subject(today, 5)


def test_compose_text_includes_all_sections() -> None:
    user = User(email="x@example.com", password_hash="x", audience="personal")
    now = datetime.now(UTC)
    overdue = [_make_task("Overdue1", TaskPriority.P1, now - timedelta(days=1))]
    today_tasks = [_make_task("Today1", TaskPriority.P2, now)]
    tomorrow = [_make_task("Tomorrow1", TaskPriority.P3, now + timedelta(days=1))]
    text = compose_text(
        user, now.date(), overdue, today_tasks, tomorrow, base_url="https://example.com"
    )
    assert "Overdue1" in text
    assert "Today1" in text
    assert "Tomorrow1" in text
    assert "Просрочено" in text
    assert "Сегодня" in text
    assert "Завтра" in text
    assert "https://example.com/app/today" in text
    assert "Тихий старт" in text  # personal-audience copy


def test_compose_html_escapes_task_titles() -> None:
    user = User(email="x@example.com", password_hash="x", audience=None)
    now = datetime.now(UTC)
    nasty = [_make_task("<script>alert(1)</script>", TaskPriority.P1, now)]
    html = compose_html(user, now.date(), nasty, [], [], base_url="https://example.com")
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


def _make_task(title: str, priority: TaskPriority, due_at: datetime) -> object:
    """Lightweight Task stand-in for compose_* unit tests (no DB)."""

    class _T:
        def __init__(self) -> None:
            self.title = title
            self.priority = priority
            self.due_at = due_at

    return _T()


# --- gather_tasks_for integration test ---


async def test_gather_tasks_for_partitions_correctly(
    db_session: AsyncSession, opted_in_user: User
) -> None:
    await _seed_tasks(db_session, opted_in_user)
    overdue, today_tasks, tomorrow = await gather_tasks_for(
        db_session, opted_in_user, now=_FIXED_NOW
    )
    titles_overdue = {t.title for t in overdue}
    titles_today = {t.title for t in today_tasks}
    titles_tomorrow = {t.title for t in tomorrow}
    assert "Просрочка" in titles_overdue
    assert "Сегодня важное" in titles_today
    assert "Завтра" in titles_tomorrow
    # Tasks without due_at are not included anywhere
    all_returned = titles_overdue | titles_today | titles_tomorrow
    assert "Без даты" not in all_returned


# --- send_morning_digest behaviour ---


async def test_send_morning_digest_skips_when_empty(
    db_session: AsyncSession, opted_in_user: User
) -> None:
    """No tasks at all → don't send anything (silent dry day)."""
    with patch("app.digest.service.aiosmtplib.send", new=AsyncMock()) as mock_send:
        sent = await send_morning_digest(db_session, opted_in_user)
    assert sent is False
    mock_send.assert_not_called()


async def test_send_morning_digest_sets_last_sent_at(
    db_session: AsyncSession, opted_in_user: User
) -> None:
    await _seed_tasks(db_session, opted_in_user)
    with patch("app.digest.service.aiosmtplib.send", new=AsyncMock()) as mock_send:
        sent = await send_morning_digest(db_session, opted_in_user, now=_FIXED_NOW)
    assert sent is True
    mock_send.assert_called_once()
    await db_session.refresh(opted_in_user)
    assert opted_in_user.morning_digest_last_sent_at is not None


async def test_send_morning_digests_for_all_users_dedups_today(
    db_session: AsyncSession, opted_in_user: User
) -> None:
    """Second call within the same day skips already-sent users."""
    await _seed_tasks(db_session, opted_in_user)
    with patch("app.digest.service.aiosmtplib.send", new=AsyncMock()) as mock_send:
        first = await send_morning_digests_for_all_users(db_session, now=_FIXED_NOW)
        second = await send_morning_digests_for_all_users(db_session, now=_FIXED_NOW)
    assert first["sent"] == 1
    assert second["sent"] == 0
    assert mock_send.call_count == 1


# --- profile toggle endpoint ---


async def test_profile_toggle_morning_digest(logged_in_client: AsyncClient) -> None:
    r = await logged_in_client.post("/api/profile/morning-digest", data={"enabled": "true"})
    assert r.status_code == 200
    assert r.json() == {"enabled": True}
    r = await logged_in_client.post("/api/profile/morning-digest", data={"enabled": "false"})
    assert r.status_code == 200
    assert r.json() == {"enabled": False}


# --- /api/digest endpoints ---


async def test_send_now_requires_auth(client: AsyncClient) -> None:
    r = await client.post("/api/digest/send-now")
    assert r.status_code == 401


async def test_send_now_skips_empty(logged_in_client: AsyncClient) -> None:
    """Logged-in user with no tasks → endpoint returns sent=false, reason=no-tasks."""
    with patch("app.digest.service.aiosmtplib.send", new=AsyncMock()):
        r = await logged_in_client.post("/api/digest/send-now")
    assert r.status_code == 200
    body = r.json()
    assert body["sent"] is False
    assert body["reason"] == "no-tasks"


async def test_cron_trigger_requires_token(client: AsyncClient) -> None:
    """Without proper X-Cron-Token, returns 503 (no token configured) or 403 (wrong)."""
    from app.config import get_settings

    settings = get_settings()
    # In test env settings.cron_token is empty → expect 503
    if not settings.cron_token:
        r = await client.post("/api/digest/cron-trigger")
        assert r.status_code == 503
    else:
        r = await client.post("/api/digest/cron-trigger", headers={"X-Cron-Token": "wrong"})
        assert r.status_code == 403
