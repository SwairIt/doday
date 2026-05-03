"""Custom filter service — CRUD + execute saved query against Task table."""

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.custom_filters.models import CustomFilter
from app.tasks.models import Task, TaskPriority


class CustomFilterNotFound(Exception):
    """Custom filter does not exist or does not belong to user."""


async def list_custom_filters(session: AsyncSession, user_id: UUID) -> list[CustomFilter]:
    result = await session.execute(
        select(CustomFilter)
        .where(CustomFilter.user_id == user_id)
        .order_by(CustomFilter.position, CustomFilter.created_at)
    )
    return list(result.scalars().all())


async def get_custom_filter(session: AsyncSession, user_id: UUID, filter_id: UUID) -> CustomFilter:
    obj = await session.get(CustomFilter, filter_id)
    if obj is None or obj.user_id != user_id:
        raise CustomFilterNotFound(str(filter_id))
    return obj


async def create_custom_filter(
    session: AsyncSession,
    user_id: UUID,
    *,
    name: str,
    color: str = "violet",
    query: dict[str, Any] | None = None,
) -> CustomFilter:
    last = (
        await session.execute(
            select(CustomFilter)
            .where(CustomFilter.user_id == user_id)
            .order_by(CustomFilter.position.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    obj = CustomFilter(
        user_id=user_id,
        name=name,
        color=color,
        query=query or {},
        position=(last.position + 1) if last else 0,
    )
    session.add(obj)
    await session.commit()
    await session.refresh(obj)
    return obj


async def update_custom_filter(
    session: AsyncSession,
    user_id: UUID,
    filter_id: UUID,
    *,
    name: str | None = None,
    color: str | None = None,
    query: dict[str, Any] | None = None,
) -> CustomFilter:
    obj = await get_custom_filter(session, user_id, filter_id)
    if name is not None:
        obj.name = name
    if color is not None:
        obj.color = color
    if query is not None:
        obj.query = query
    await session.commit()
    await session.refresh(obj)
    return obj


async def delete_custom_filter(session: AsyncSession, user_id: UUID, filter_id: UUID) -> None:
    obj = await get_custom_filter(session, user_id, filter_id)
    await session.delete(obj)
    await session.commit()


def _due_window_clauses(window: str | None) -> list[Any]:
    if not window or window == "any":
        return []
    now = datetime.now(UTC)
    today = now.date()
    start_today = datetime(today.year, today.month, today.day, 0, 0, tzinfo=UTC)
    end_today = start_today + timedelta(days=1)
    if window == "today":
        return [Task.due_at.is_not(None), Task.due_at >= start_today, Task.due_at < end_today]
    if window == "overdue":
        return [Task.due_at.is_not(None), Task.due_at < start_today]
    if window == "upcoming-7":
        end_window = start_today + timedelta(days=8)
        return [Task.due_at.is_not(None), Task.due_at >= end_today, Task.due_at < end_window]
    if window == "no-date":
        return [Task.due_at.is_(None)]
    return []


async def execute_custom_filter(
    session: AsyncSession, user_id: UUID, custom_filter: CustomFilter
) -> list[Task]:
    q = custom_filter.query or {}
    stmt = select(Task).where(Task.user_id == user_id, Task.parent_task_id.is_(None))

    if not q.get("include_completed"):
        stmt = stmt.where(Task.is_completed.is_(False))

    priorities = q.get("priorities") or []
    if priorities:
        try:
            prio_enums = [TaskPriority(p) for p in priorities]
            stmt = stmt.where(Task.priority.in_(prio_enums))
        except ValueError:
            pass

    project_ids = q.get("project_ids") or []
    if project_ids:
        stmt = stmt.where(Task.project_id.in_(project_ids))

    for clause in _due_window_clauses(q.get("due_window")):
        stmt = stmt.where(clause)

    text = (q.get("has_text") or "").strip().lower()
    if text:
        pattern = f"%{text}%"
        stmt = stmt.where(
            or_(
                func.lower(Task.title).like(pattern),
                func.lower(Task.description).like(pattern),
            )
        )

    stmt = stmt.order_by(Task.due_at.nulls_last(), Task.priority, Task.created_at)
    result = await session.execute(stmt)
    return list(result.scalars().all())
