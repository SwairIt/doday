"""Task service — CRUD, complete/uncomplete, reorder, list filters."""

from calendar import monthrange
from datetime import UTC, date, datetime, timedelta
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.projects.service import ensure_inbox, get_project
from app.tasks.models import Task, TaskPriority


class TaskNotFound(Exception):
    """Task does not exist or belongs to another user."""


def _shift_date(d: date, recurrence: str) -> date:
    """Compute the next occurrence date for a recurrence rule."""
    if recurrence == "daily":
        return d + timedelta(days=1)
    if recurrence == "weekly":
        return d + timedelta(days=7)
    if recurrence == "monthly":
        next_m = 1 if d.month == 12 else d.month + 1
        next_y = d.year + 1 if d.month == 12 else d.year
        last_day = monthrange(next_y, next_m)[1]
        return date(next_y, next_m, min(d.day, last_day))
    if recurrence == "yearly":
        # Feb 29 in non-leap → Feb 28
        try:
            return date(d.year + 1, d.month, d.day)
        except ValueError:
            return date(d.year + 1, d.month, d.day - 1)
    raise ValueError(f"unknown recurrence: {recurrence!r}")


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
    section_id: UUID | None = None,
    description: str | None = None,
    due_at: datetime | None = None,
    due_date_only: bool = True,
    priority: TaskPriority = TaskPriority.P4,
    recurrence: str | None = None,
) -> Task:
    if project_id is None:
        project = await ensure_inbox(session, user_id)
        project_id = project.id
    else:
        # Will raise ProjectNotFound if user doesn't own it.
        await get_project(session, user_id, project_id)

    if parent_task_id is not None:
        # Ownership check; nesting depth is unrestricted (UI can drill down).
        await get_task(session, user_id, parent_task_id)

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
        section_id=section_id,
        title=title,
        description=description,
        due_at=due_at,
        due_date_only=due_date_only,
        priority=priority,
        position=position,
        recurrence=recurrence,
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
    top_level_only: bool = True,
) -> list[Task]:
    """List tasks. By default hides subtasks (parent_task_id IS NOT NULL)."""
    stmt = select(Task).where(Task.user_id == user_id)
    if project_id is not None:
        stmt = stmt.where(Task.project_id == project_id)
    if not include_completed:
        stmt = stmt.where(Task.is_completed.is_(False))
    if top_level_only:
        stmt = stmt.where(Task.parent_task_id.is_(None))
    stmt = stmt.order_by(Task.position, Task.created_at)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def list_subtasks(session: AsyncSession, user_id: UUID, parent_id: UUID) -> list[Task]:
    stmt = (
        select(Task)
        .where(Task.user_id == user_id, Task.parent_task_id == parent_id)
        .order_by(Task.position, Task.created_at)
    )
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


async def list_completed(session: AsyncSession, user_id: UUID, *, limit: int = 200) -> list[Task]:
    """Most recently completed tasks (top-level only) for the history view."""
    stmt = (
        select(Task)
        .where(
            Task.user_id == user_id,
            Task.is_completed.is_(True),
            Task.parent_task_id.is_(None),
        )
        .order_by(Task.completed_at.desc().nulls_last(), Task.updated_at.desc())
        .limit(limit)
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
    section_id: UUID | None = None,
    clear_section: bool = False,
    recurrence: str | None = None,
) -> Task:
    from app.sections.service import get_section

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
        # Ownership check; nesting depth unrestricted.
        await get_task(session, user_id, parent_task_id)
        task.parent_task_id = parent_task_id
    if clear_section:
        task.section_id = None
    elif section_id is not None:
        section = await get_section(session, user_id, section_id)
        if section.project_id != task.project_id:
            raise ValueError("section belongs to a different project")
        task.section_id = section_id
    if recurrence is not None:
        task.recurrence = recurrence
    await session.commit()
    await session.refresh(task)
    return task


async def duplicate_task(session: AsyncSession, user_id: UUID, task_id: UUID) -> Task:
    """Clone a single task. Subtasks are copied recursively, parent stays sibling."""
    src = await get_task(session, user_id, task_id)
    parent_filter = (
        Task.parent_task_id.is_(None)
        if src.parent_task_id is None
        else Task.parent_task_id == src.parent_task_id
    )
    sibling_last = (
        await session.execute(
            select(Task)
            .where(
                Task.user_id == user_id,
                Task.project_id == src.project_id,
                parent_filter,
            )
            .order_by(Task.position.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    next_pos = (sibling_last.position + 1) if sibling_last else 0

    new_root = Task(
        user_id=user_id,
        project_id=src.project_id,
        parent_task_id=src.parent_task_id,
        section_id=src.section_id,
        title=src.title + " (копия)",
        description=src.description,
        due_at=src.due_at,
        due_date_only=src.due_date_only,
        priority=src.priority,
        position=next_pos,
        recurrence=src.recurrence,
    )
    session.add(new_root)
    await session.flush()

    # Recursively copy children depth-first.
    async def _copy_children(orig_id: UUID, new_parent_id: UUID) -> None:
        children = (
            (
                await session.execute(
                    select(Task)
                    .where(Task.user_id == user_id, Task.parent_task_id == orig_id)
                    .order_by(Task.position)
                )
            )
            .scalars()
            .all()
        )
        for c in children:
            new_c = Task(
                user_id=user_id,
                project_id=c.project_id,
                parent_task_id=new_parent_id,
                section_id=c.section_id,
                title=c.title,
                description=c.description,
                due_at=c.due_at,
                due_date_only=c.due_date_only,
                priority=c.priority,
                position=c.position,
                recurrence=c.recurrence,
            )
            session.add(new_c)
            await session.flush()
            await _copy_children(c.id, new_c.id)

    await _copy_children(src.id, new_root.id)
    await session.commit()
    await session.refresh(new_root)
    return new_root


async def complete_task(session: AsyncSession, user_id: UUID, task_id: UUID) -> Task:
    """Mark task complete. If `recurrence` is set, also spawn the next instance."""
    task = await get_task(session, user_id, task_id)
    if task.is_completed:
        return task

    task.is_completed = True
    task.completed_at = datetime.now(UTC)
    await session.commit()

    if task.recurrence and task.due_at is not None:
        next_date = _shift_date(task.due_at.date(), task.recurrence)
        next_due = datetime(
            next_date.year,
            next_date.month,
            next_date.day,
            task.due_at.hour,
            task.due_at.minute,
            tzinfo=UTC,
        )
        await create_task(
            session,
            user_id,
            title=task.title,
            project_id=task.project_id,
            section_id=task.section_id,
            description=task.description,
            due_at=next_due,
            due_date_only=task.due_date_only,
            priority=task.priority,
            recurrence=task.recurrence,
        )

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
