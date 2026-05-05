"""Service-level tests for tasks."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.projects.service import create_project, ensure_inbox
from app.tasks.models import TaskPriority
from app.tasks.service import (
    TaskNotFound,
    complete_task,
    create_task,
    delete_task,
    list_tasks,
    list_today,
    list_upcoming,
    reorder_tasks,
    uncomplete_task,
    update_task,
)


async def _user(db_session: AsyncSession, email: str = "u@s.ru") -> User:
    u = User(email=email, password_hash="argon2-fake")
    db_session.add(u)
    await db_session.commit()
    return u


async def test_create_task_defaults_to_inbox(db_session: AsyncSession) -> None:
    user = await _user(db_session)
    inbox = await ensure_inbox(db_session, user.id)

    task = await create_task(db_session, user.id, title="Hello")
    assert task.project_id == inbox.id
    assert task.priority is TaskPriority.P4
    assert task.is_completed is False
    assert task.position == 0


async def test_create_task_in_specific_project(db_session: AsyncSession) -> None:
    user = await _user(db_session)
    proj = await create_project(db_session, user.id, name="Work")
    task = await create_task(
        db_session, user.id, title="Report", project_id=proj.id, priority=TaskPriority.P1
    )
    assert task.project_id == proj.id
    assert task.priority is TaskPriority.P1


async def test_complete_and_uncomplete(db_session: AsyncSession) -> None:
    user = await _user(db_session)
    task = await create_task(db_session, user.id, title="X")

    completed = await complete_task(db_session, user.id, task.id)
    assert completed.is_completed is True
    assert completed.completed_at is not None

    again = await complete_task(db_session, user.id, task.id)
    assert again.completed_at == completed.completed_at  # idempotent

    uncompleted = await uncomplete_task(db_session, user.id, task.id)
    assert uncompleted.is_completed is False
    assert uncompleted.completed_at is None


async def test_list_excludes_completed_by_default(db_session: AsyncSession) -> None:
    user = await _user(db_session)
    a = await create_task(db_session, user.id, title="A")
    await create_task(db_session, user.id, title="B")
    await complete_task(db_session, user.id, a.id)

    visible = await list_tasks(db_session, user.id)
    assert {t.title for t in visible} == {"B"}

    everything = await list_tasks(db_session, user.id, include_completed=True)
    assert {t.title for t in everything} == {"A", "B"}


async def test_list_today_includes_overdue(db_session: AsyncSession) -> None:
    user = await _user(db_session)
    yesterday = datetime.now(UTC) - timedelta(days=1)
    today_late = datetime.now(UTC).replace(hour=23, minute=59, second=0, microsecond=0)
    tomorrow = datetime.now(UTC) + timedelta(days=2)

    await create_task(db_session, user.id, title="overdue", due_at=yesterday)
    await create_task(db_session, user.id, title="today", due_at=today_late)
    await create_task(db_session, user.id, title="future", due_at=tomorrow)
    await create_task(db_session, user.id, title="no-date")

    today = await list_today(db_session, user.id)
    titles = {t.title for t in today}
    assert "overdue" in titles
    assert "today" in titles
    assert "future" not in titles
    assert "no-date" not in titles


async def test_list_upcoming_excludes_today(db_session: AsyncSession) -> None:
    user = await _user(db_session)
    in_3_days = datetime.now(UTC) + timedelta(days=3)
    in_30_days = datetime.now(UTC) + timedelta(days=30)
    today_late = datetime.now(UTC).replace(hour=23, minute=59)

    await create_task(db_session, user.id, title="today", due_at=today_late)
    await create_task(db_session, user.id, title="soon", due_at=in_3_days)
    await create_task(db_session, user.id, title="far", due_at=in_30_days)

    upcoming = await list_upcoming(db_session, user.id, days=7)
    titles = [t.title for t in upcoming]
    assert "soon" in titles
    assert "today" not in titles
    assert "far" not in titles


async def test_update_task_changes_fields(db_session: AsyncSession) -> None:
    user = await _user(db_session)
    task = await create_task(db_session, user.id, title="Old title")
    updated = await update_task(db_session, user.id, task.id, title="New", priority=TaskPriority.P2)
    assert updated.title == "New"
    assert updated.priority is TaskPriority.P2


async def test_delete_task(db_session: AsyncSession) -> None:
    from uuid import uuid4

    user = await _user(db_session)
    task = await create_task(db_session, user.id, title="Bye")
    await delete_task(db_session, user.id, task.id)
    # Soft-delete: the row still exists with deleted_at set, so a second
    # delete is idempotent. Real "task not found" only fires for a missing UUID.
    await delete_task(db_session, user.id, task.id)
    with pytest.raises(TaskNotFound):
        await delete_task(db_session, user.id, uuid4())


async def test_task_isolation_per_user(db_session: AsyncSession) -> None:
    u1 = await _user(db_session, "a@s.ru")
    u2 = await _user(db_session, "b@s.ru")
    t = await create_task(db_session, u1.id, title="Mine")
    with pytest.raises(TaskNotFound):
        await complete_task(db_session, u2.id, t.id)


async def test_reorder_persists_positions(db_session: AsyncSession) -> None:
    user = await _user(db_session)
    proj = await create_project(db_session, user.id, name="X")
    a = await create_task(db_session, user.id, project_id=proj.id, title="A")
    b = await create_task(db_session, user.id, project_id=proj.id, title="B")
    c = await create_task(db_session, user.id, project_id=proj.id, title="C")

    reordered = await reorder_tasks(db_session, user.id, proj.id, [c.id, a.id, b.id])
    assert [t.title for t in reordered] == ["C", "A", "B"]
    assert reordered[0].position == 0
    assert reordered[1].position == 1
    assert reordered[2].position == 2
