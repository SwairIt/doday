"""Task service — CRUD, complete/uncomplete, reorder, list filters."""

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.projects.service import ensure_inbox, get_project
from app.tasks.models import Task, TaskPriority


class TaskNotFound(Exception):
    """Task does not exist or belongs to another user."""


async def get_task(session: AsyncSession, user_id: UUID, task_id: UUID) -> Task:
    task = await session.get(Task, task_id)
    if task is None or task.user_id != user_id:
        raise TaskNotFound(str(task_id))
    return task


async def create_task(
    session: AsyncSession,
    user_id: UUID,
    *,
    title: str,
    project_id: UUID | None = None,
    parent_task_id: UUID | None = None,
    description: str | None = None,
    due_at: datetime | None = None,
    due_date_only: bool = True,
    priority: TaskPriority = TaskPriority.P4,
) -> Task:
    if project_id is None:
        project = await ensure_inbox(session, user_id)
        project_id = project.id
    else:
        # Will raise ProjectNotFound if user doesn't own it.
        await get_project(session, user_id, project_id)

    if parent_task_id is not None:
        parent = await get_task(session, user_id, parent_task_id)
        if parent.parent_task_id is not None:
            raise ValueError("subtasks may not have their own subtasks (1 level only)")

    last = (
        await session.execute(
            select(Task)
            .where(Task.user_id == user_id, Task.project_id == project_id)
            .order_by(Task.position.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    position = (last.position + 1) if last else 0

    task = Task(
        user_id=user_id,
        project_id=project_id,
        parent_task_id=parent_task_id,
        title=title,
        description=description,
        due_at=due_at,
        due_date_only=due_date_only,
        priority=priority,
        position=position,
    )
    session.add(task)
    await session.commit()
    await session.refresh(task)
    return task


async def list_tasks(
    session: AsyncSession,
    user_id: UUID,
    *,
    project_id: UUID | None = None,
    include_completed: bool = False,
) -> list[Task]:
    stmt = select(Task).where(Task.user_id == user_id)
    if project_id is not None:
        stmt = stmt.where(Task.project_id == project_id)
    if not include_completed:
        stmt = stmt.where(Task.is_completed.is_(False))
    stmt = stmt.order_by(Task.position, Task.created_at)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def list_today(session: AsyncSession, user_id: UUID) -> list[Task]:
    """Tasks due today (in UTC) plus everything overdue. Excludes completed."""
    now = datetime.now(UTC)
    end_of_today = datetime(now.year, now.month, now.day, 23, 59, 59, tzinfo=UTC)
    stmt = (
        select(Task)
        .where(
            Task.user_id == user_id,
            Task.is_completed.is_(False),
            Task.due_at.is_not(None),
            Task.due_at <= end_of_today,
        )
        .order_by(Task.due_at, Task.priority, Task.position)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def list_upcoming(session: AsyncSession, user_id: UUID, *, days: int = 7) -> list[Task]:
    """Tasks due in the next N days (excluding overdue / today)."""
    now = datetime.now(UTC)
    start = datetime(now.year, now.month, now.day, 0, 0, 0, tzinfo=UTC) + timedelta(days=1)
    end = start + timedelta(days=days)
    stmt = (
        select(Task)
        .where(
            Task.user_id == user_id,
            Task.is_completed.is_(False),
            Task.due_at.is_not(None),
            and_(Task.due_at >= start, Task.due_at < end),
        )
        .order_by(Task.due_at, Task.priority, Task.position)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def list_in_range(
    session: AsyncSession,
    user_id: UUID,
    *,
    start: datetime,
    end: datetime,
) -> list[Task]:
    stmt = (
        select(Task)
        .where(
            Task.user_id == user_id,
            Task.due_at.is_not(None),
            and_(Task.due_at >= start, Task.due_at < end),
        )
        .order_by(Task.due_at, Task.priority)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def update_task(
    session: AsyncSession,
    user_id: UUID,
    task_id: UUID,
    *,
    title: str | None = None,
    description: str | None = None,
    due_at: datetime | None = None,
    due_date_only: bool | None = None,
    priority: TaskPriority | None = None,
    project_id: UUID | None = None,
    parent_task_id: UUID | None = None,
) -> Task:
    task = await get_task(session, user_id, task_id)
    if title is not None:
        task.title = title
    if description is not None:
        task.description = description
    if due_at is not None:
        task.due_at = due_at
    if due_date_only is not None:
        task.due_date_only = due_date_only
    if priority is not None:
        task.priority = priority
    if project_id is not None:
        await get_project(session, user_id, project_id)
        task.project_id = project_id
    if parent_task_id is not None:
        parent = await get_task(session, user_id, parent_task_id)
        if parent.parent_task_id is not None:
            raise ValueError("cannot nest subtasks deeper than one level")
        task.parent_task_id = parent_task_id
    await session.commit()
    await session.refresh(task)
    return task


async def complete_task(session: AsyncSession, user_id: UUID, task_id: UUID) -> Task:
    task = await get_task(session, user_id, task_id)
    if not task.is_completed:
        task.is_completed = True
        task.completed_at = datetime.now(UTC)
        await session.commit()
        await session.refresh(task)
    return task


async def uncomplete_task(session: AsyncSession, user_id: UUID, task_id: UUID) -> Task:
    task = await get_task(session, user_id, task_id)
    if task.is_completed:
        task.is_completed = False
        task.completed_at = None
        await session.commit()
        await session.refresh(task)
    return task


async def delete_task(session: AsyncSession, user_id: UUID, task_id: UUID) -> None:
    task = await get_task(session, user_id, task_id)
    await session.delete(task)
    await session.commit()


async def reorder_tasks(
    session: AsyncSession,
    user_id: UUID,
    project_id: UUID,
    ordered_ids: list[UUID],
) -> list[Task]:
    """Set position for each task in `ordered_ids` to its index. Validates ownership."""
    await get_project(session, user_id, project_id)

    result = await session.execute(
        select(Task).where(
            Task.user_id == user_id,
            Task.project_id == project_id,
            Task.id.in_(ordered_ids),
        )
    )
    tasks = {t.id: t for t in result.scalars().all()}
    for idx, tid in enumerate(ordered_ids):
        if tid not in tasks:
            raise TaskNotFound(str(tid))
        tasks[tid].position = idx
    await session.commit()
    return [tasks[tid] for tid in ordered_ids]
