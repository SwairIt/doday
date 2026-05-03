"""Saved smart filters — predefined task queries."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.tasks.models import Task, TaskPriority

FilterSlug = Literal["overdue", "no-date", "high-priority", "this-week"]


@dataclass(frozen=True)
class FilterMeta:
    slug: FilterSlug
    name: str
    icon_path: str
    color: str  # tailwind hue token
    description: str


FILTERS: dict[str, FilterMeta] = {
    "overdue": FilterMeta(
        slug="overdue",
        name="Просрочено",
        icon_path="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z",
        color="rose",
        description="Задачи с дедлайном, который уже прошёл.",
    ),
    "no-date": FilterMeta(
        slug="no-date",
        name="Без даты",
        icon_path="M8 7V3m8 4V3M3 11h18M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z",
        color="slate",
        description="Задачи, которым не назначен срок.",
    ),
    "high-priority": FilterMeta(
        slug="high-priority",
        name="Высокий приоритет",
        icon_path="M3 21v-4m0 0V5a2 2 0 012-2h6.5l1 1H21l-3 6 3 6h-8.5l-1-1H5a2 2 0 00-2 2zm9-13.5V9",
        color="amber",
        description="P1 и P2 — самое срочное.",
    ),
    "this-week": FilterMeta(
        slug="this-week",
        name="На этой неделе",
        icon_path="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2",
        color="violet",
        description="Дедлайн в пределах текущей недели (Пн–Вс).",
    ),
}


async def list_for_filter(session: AsyncSession, user_id: UUID, slug: str) -> list[Task]:
    if slug not in FILTERS:
        raise KeyError(slug)

    now = datetime.now(UTC)
    today = now.date()

    base = select(Task).where(
        Task.user_id == user_id,
        Task.is_completed.is_(False),
        Task.parent_task_id.is_(None),
    )

    if slug == "overdue":
        start_of_today = datetime(today.year, today.month, today.day, 0, 0, tzinfo=UTC)
        stmt = base.where(Task.due_at.is_not(None), Task.due_at < start_of_today)
    elif slug == "no-date":
        stmt = base.where(Task.due_at.is_(None))
    elif slug == "high-priority":
        stmt = base.where(or_(Task.priority == TaskPriority.P1, Task.priority == TaskPriority.P2))
    elif slug == "this-week":
        # Monday this week 00:00 → next Monday 00:00
        monday = datetime(today.year, today.month, today.day, 0, 0, tzinfo=UTC) - timedelta(
            days=today.weekday()
        )
        next_monday = monday + timedelta(days=7)
        stmt = base.where(
            Task.due_at.is_not(None),
            Task.due_at >= monday,
            Task.due_at < next_monday,
        )
    else:  # pragma: no cover — guarded by 'slug not in FILTERS' above
        raise KeyError(slug)

    stmt = stmt.order_by(Task.due_at.nulls_last(), Task.priority, Task.created_at)
    result = await session.execute(stmt)
    return list(result.scalars().all())
