"""Tests for saved smart filters."""

from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.filters.service import list_for_filter
from app.tasks.models import TaskPriority
from app.tasks.service import create_task


async def _user(db_session: AsyncSession, email: str = "u@s.ru") -> User:
    u = User(email=email, password_hash="argon2-fake")
    db_session.add(u)
    await db_session.commit()
    return u


async def test_filter_overdue_returns_only_overdue(db_session: AsyncSession) -> None:
    user = await _user(db_session)
    yesterday = datetime.now(UTC) - timedelta(days=1)
    today_late = datetime.now(UTC).replace(hour=23, minute=59)
    far_future = datetime.now(UTC) + timedelta(days=30)

    await create_task(db_session, user.id, title="overdueA", due_at=yesterday)
    await create_task(db_session, user.id, title="todaytask", due_at=today_late)
    await create_task(db_session, user.id, title="future", due_at=far_future)
    await create_task(db_session, user.id, title="no-date")

    tasks = await list_for_filter(db_session, user.id, "overdue")
    titles = [t.title for t in tasks]
    assert "overdueA" in titles
    assert "todaytask" not in titles
    assert "future" not in titles
    assert "no-date" not in titles


async def test_filter_no_date_returns_only_undated(db_session: AsyncSession) -> None:
    user = await _user(db_session)
    await create_task(db_session, user.id, title="dated", due_at=datetime.now(UTC))
    await create_task(db_session, user.id, title="floaterA")
    await create_task(db_session, user.id, title="floaterB")

    tasks = await list_for_filter(db_session, user.id, "no-date")
    titles = {t.title for t in tasks}
    assert titles == {"floaterA", "floaterB"}


async def test_filter_high_priority(db_session: AsyncSession) -> None:
    user = await _user(db_session)
    await create_task(db_session, user.id, title="urgent", priority=TaskPriority.P1)
    await create_task(db_session, user.id, title="important", priority=TaskPriority.P2)
    await create_task(db_session, user.id, title="meh", priority=TaskPriority.P3)
    await create_task(db_session, user.id, title="whatever")  # default p4

    tasks = await list_for_filter(db_session, user.id, "high-priority")
    titles = {t.title for t in tasks}
    assert titles == {"urgent", "important"}


async def test_filter_this_week_includes_today_and_week(
    db_session: AsyncSession,
) -> None:
    user = await _user(db_session)
    today = datetime.now(UTC)
    in_3 = today + timedelta(days=3)
    next_month = today + timedelta(days=40)

    await create_task(db_session, user.id, title="todayitem", due_at=today)
    await create_task(db_session, user.id, title="soon", due_at=in_3)
    await create_task(db_session, user.id, title="far", due_at=next_month)

    tasks = await list_for_filter(db_session, user.id, "this-week")
    titles = {t.title for t in tasks}
    # We can't deterministically know if "soon" lands within current Mon-Sun
    # depending on which weekday today is. Always-true: "todayitem" in, "far" out.
    assert "todayitem" in titles
    assert "far" not in titles


async def test_filter_unknown_slug_raises(db_session: AsyncSession) -> None:
    user = await _user(db_session)
    with pytest.raises(KeyError):
        await list_for_filter(db_session, user.id, "frobnicate")


async def test_filter_endpoint_renders(logged_in_client: AsyncClient) -> None:
    response = await logged_in_client.get("/doday/app/filters/overdue")
    assert response.status_code == 200
    assert "Просрочено" in response.text


async def test_filter_endpoint_unknown_slug_404(logged_in_client: AsyncClient) -> None:
    response = await logged_in_client.get("/doday/app/filters/bogus")
    assert response.status_code == 404


async def test_filter_endpoint_anon_blocked(client: AsyncClient) -> None:
    response = await client.get("/doday/app/filters/overdue")
    assert response.status_code == 401


async def test_filter_excludes_subtasks(db_session: AsyncSession) -> None:
    """Subtasks shouldn't appear at top-level in filter results."""
    user = await _user(db_session)
    parent = await create_task(db_session, user.id, title="ParentNoDate")
    sub = await create_task(db_session, user.id, title="SubChild", parent_task_id=parent.id)
    assert sub.parent_task_id is not None

    tasks = await list_for_filter(db_session, user.id, "no-date")
    titles = [t.title for t in tasks]
    assert "ParentNoDate" in titles
    assert "SubChild" not in titles
