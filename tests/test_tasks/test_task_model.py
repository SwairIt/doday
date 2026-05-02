"""Tests for Task model — round-trip, default priority, cascade from project."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.projects.models import Project
from app.tasks.models import Task, TaskPriority


async def _seed(db_session: AsyncSession) -> tuple[User, Project]:
    user = User(email="t@school.ru", password_hash="argon2-fake")
    db_session.add(user)
    await db_session.commit()
    project = Project(user_id=user.id, name="Inbox", slug="inbox", is_inbox=True)
    db_session.add(project)
    await db_session.commit()
    return user, project


async def test_task_round_trip(db_session: AsyncSession) -> None:
    user, project = await _seed(db_session)
    due = datetime.now(UTC) + timedelta(days=1)
    task = Task(
        user_id=user.id,
        project_id=project.id,
        title="Сделать ДЗ",
        due_at=due,
        priority=TaskPriority.P2,
    )
    db_session.add(task)
    await db_session.commit()
    await db_session.refresh(task)

    assert task.id is not None
    assert task.is_completed is False
    assert task.priority is TaskPriority.P2
    assert task.due_date_only is True
    assert task.position == 0


async def test_task_default_priority_is_p4(db_session: AsyncSession) -> None:
    user, project = await _seed(db_session)
    task = Task(user_id=user.id, project_id=project.id, title="Anything")
    db_session.add(task)
    await db_session.commit()
    await db_session.refresh(task)
    assert task.priority is TaskPriority.P4


async def test_task_cascades_when_project_deleted(db_session: AsyncSession) -> None:
    user, project = await _seed(db_session)
    db_session.add(Task(user_id=user.id, project_id=project.id, title="X"))
    await db_session.commit()

    await db_session.execute(delete(Project).where(Project.id == project.id))
    await db_session.commit()

    remaining = (await db_session.execute(select(Task))).scalars().all()
    assert remaining == []
