"""Task service — CRUD, complete/uncomplete, reorder, list filters."""

from calendar import monthrange
from datetime import UTC, date, datetime, timedelta
from uuid import UUID

from sqlalchemy import and_, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.projects.membership import is_member, member_project_ids
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
    if task is None:
        raise TaskNotFound(str(task_id))
    if not await is_member(session, task.project_id, user_id):
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
    """List tasks. By default hides subtasks (parent_task_id IS NOT NULL).

    When project_id is given, all members of that project see each other's
    tasks — the caller must have already verified membership via get_project.
    When project_id is None (personal views like Inbox/unfiltered), restrict
    to the user's own tasks.
    """
    if project_id is not None:
        # Project-scoped view: show all members' tasks in that project.
        stmt = select(Task).where(Task.project_id == project_id)
    else:
        # Personal view: only own tasks.
        stmt = select(Task).where(Task.user_id == user_id)
    if not include_completed:
        stmt = stmt.where(Task.is_completed.is_(False))
    if top_level_only:
        stmt = stmt.where(Task.parent_task_id.is_(None))
    # Soft-deleted tasks live in the trash bin, never in regular lists.
    stmt = stmt.where(Task.deleted_at.is_(None))
    # Pinned float to the top regardless of position; recent pins win ties.
    stmt = stmt.order_by(Task.pinned_at.desc().nulls_last(), Task.position, Task.created_at)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def list_subtasks(session: AsyncSession, user_id: UUID, parent_id: UUID) -> list[Task]:
    stmt = (
        select(Task)
        .where(
            Task.user_id == user_id,
            Task.parent_task_id == parent_id,
            Task.deleted_at.is_(None),
        )
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
            Task.deleted_at.is_(None),
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
            Task.deleted_at.is_(None),
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
            Task.deleted_at.is_(None),
        )
        .order_by(Task.completed_at.desc().nulls_last(), Task.updated_at.desc())
        .limit(limit)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def list_completed_today(
    session: AsyncSession, user_id: UUID, *, limit: int = 10
) -> list[Task]:
    """Tasks completed today (UTC), most-recent first — fuel for the
    'Recently completed' widget on /today."""
    today = datetime.now(UTC).date()
    stmt = (
        select(Task)
        .where(
            Task.user_id == user_id,
            Task.is_completed.is_(True),
            Task.completed_at.is_not(None),
            func.date(Task.completed_at) == today,
            Task.deleted_at.is_(None),
        )
        .order_by(Task.completed_at.desc().nulls_last())
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
            Task.deleted_at.is_(None),
        )
        .order_by(Task.due_at, Task.priority)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def list_trash(session: AsyncSession, user_id: UUID, *, max_age_days: int = 30) -> list[Task]:
    """Return non-purged, soft-deleted tasks newer than max_age_days.

    Older entries are auto-purged inside this call so the trash never grows
    forever. Cleanup is best-effort — a failure here just leaves the rows.
    """
    cutoff = datetime.now(UTC) - timedelta(days=max_age_days)
    # Hard-delete anything older than the window.
    await session.execute(
        delete(Task).where(
            Task.user_id == user_id,
            Task.deleted_at.is_not(None),
            Task.deleted_at < cutoff,
        )
    )
    await session.commit()

    stmt = (
        select(Task)
        .where(Task.user_id == user_id, Task.deleted_at.is_not(None))
        .order_by(Task.deleted_at.desc())
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def list_assigned_to_user(session: AsyncSession, user_id: UUID) -> list[Task]:
    """Open tasks assigned to this user across every project they belong to.

    Powers the "Назначено мне" view. Excludes completed and trashed tasks, and
    only spans projects where the user is a member (so a stale assignment in a
    project they were removed from never leaks). Tasks with a due date come
    first (earliest first), then the undated ones by priority/position.
    """
    project_ids = await member_project_ids(session, user_id)
    if not project_ids:
        return []
    stmt = (
        select(Task)
        .where(
            Task.assigned_to == user_id,
            Task.project_id.in_(project_ids),
            Task.is_completed.is_(False),
            Task.deleted_at.is_(None),
        )
        .order_by(Task.due_at.is_(None), Task.due_at, Task.priority, Task.position)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def restore_task(session: AsyncSession, user_id: UUID, task_id: UUID) -> Task:
    task = await get_task(session, user_id, task_id)
    task.deleted_at = None
    await session.commit()
    await session.refresh(task)
    return task


async def purge_task(session: AsyncSession, user_id: UUID, task_id: UUID) -> None:
    """Hard-delete from the trash (or anywhere). Use with care."""
    task = await get_task(session, user_id, task_id)
    await session.delete(task)
    await session.commit()


class _Unset:
    """Sentinel type so mypy can distinguish 'not provided' from explicit None."""


_SENTINEL = _Unset()


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
    assigned_to: UUID | None | _Unset = _SENTINEL,
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
    if not isinstance(assigned_to, _Unset):
        if assigned_to is None:
            task.assigned_to = None
        else:
            if not await is_member(session, task.project_id, assigned_to):
                raise ValueError("assigned user is not a member of the project")
            task.assigned_to = assigned_to
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


async def pin_task(session: AsyncSession, user_id: UUID, task_id: UUID) -> Task:
    """Pin a task to the top of every list. Idempotent — repins refresh the
    timestamp so the most-recently pinned task is shown first."""
    task = await get_task(session, user_id, task_id)
    task.pinned_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(task)
    return task


async def unpin_task(session: AsyncSession, user_id: UUID, task_id: UUID) -> Task:
    task = await get_task(session, user_id, task_id)
    task.pinned_at = None
    await session.commit()
    await session.refresh(task)
    return task


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
    """Soft-delete: move to trash. The row is hard-deleted after 30 days
    (or via /api/tasks/{id}/purge) by `list_trash`'s cleanup pass."""
    task = await get_task(session, user_id, task_id)
    task.deleted_at = datetime.now(UTC)
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
