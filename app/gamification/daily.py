"""Daily challenge — deterministic random per (user_id, date).

Каждый день юзер получает один из нескольких вызовов (выбор детерминирован
по user_id+date, поэтому одинаков на всю сессию).
Если выполнил — +20 XP bonus.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, date, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.tasks.models import Task, TaskPriority


@dataclass
class Challenge:
    key: str
    emoji: str
    title: str  # короткий заголовок
    description: str  # подсказка как выполнить
    progress_fn: str  # JSON-key для прогресса
    target: int


CHALLENGES: list[Challenge] = [
    Challenge("close_5", "🎯", "Закрой 5 задач сегодня", "Просто 5 — любых.", "done_today", 5),
    Challenge(
        "close_p1", "🔥", "Закрой 1 P1-задачу", "Самый горячий приоритет.", "done_p1_today", 1
    ),
    Challenge(
        "zero_overdue", "✨", "Не оставь просрочки", "Закрой все overdue.", "overdue_zero", 1
    ),
    Challenge(
        "close_3_before_noon",
        "🌅",
        "3 задачи до полудня",
        "Решительное утро.",
        "done_before_noon",
        3,
    ),
    Challenge("close_10", "🌊", "10 задач сегодня", "День продуктивности.", "done_today", 10),
    Challenge(
        "close_recurring",
        "🔁",
        "Закрой повторяющуюся",
        "1 recurring сегодня.",
        "done_recurring_today",
        1,
    ),
]


def _pick_for(user_id: UUID, the_date: date) -> Challenge:
    """Deterministic random — sha1(user_id + date) → idx."""
    h = hashlib.sha1(
        f"{user_id}|{the_date.isoformat()}".encode(), usedforsecurity=False
    ).hexdigest()
    idx = int(h, 16) % len(CHALLENGES)
    return CHALLENGES[idx]


async def progress_for_today(session: AsyncSession, user_id: UUID) -> dict[str, object]:
    """Возвращает {challenge, progress, target, done} для current day."""
    today = datetime.now(UTC).date()
    ch = _pick_for(user_id, today)
    progress = 0

    if ch.progress_fn == "done_today":
        progress = int(
            (
                await session.execute(
                    select(func.count())
                    .select_from(Task)
                    .where(
                        Task.user_id == user_id,
                        Task.is_completed.is_(True),
                        Task.completed_at.is_not(None),
                        func.date(Task.completed_at) == today,
                    )
                )
            ).scalar_one()
        )
    elif ch.progress_fn == "done_p1_today":
        progress = int(
            (
                await session.execute(
                    select(func.count())
                    .select_from(Task)
                    .where(
                        Task.user_id == user_id,
                        Task.is_completed.is_(True),
                        Task.priority == TaskPriority.P1,
                        Task.completed_at.is_not(None),
                        func.date(Task.completed_at) == today,
                    )
                )
            ).scalar_one()
        )
    elif ch.progress_fn == "done_before_noon":
        progress = int(
            (
                await session.execute(
                    select(func.count())
                    .select_from(Task)
                    .where(
                        Task.user_id == user_id,
                        Task.is_completed.is_(True),
                        Task.completed_at.is_not(None),
                        func.date(Task.completed_at) == today,
                        func.extract("hour", Task.completed_at) < 12,
                    )
                )
            ).scalar_one()
        )
    elif ch.progress_fn == "done_recurring_today":
        progress = int(
            (
                await session.execute(
                    select(func.count())
                    .select_from(Task)
                    .where(
                        Task.user_id == user_id,
                        Task.is_completed.is_(True),
                        Task.recurrence.is_not(None),
                        Task.completed_at.is_not(None),
                        func.date(Task.completed_at) == today,
                    )
                )
            ).scalar_one()
        )
    elif ch.progress_fn == "overdue_zero":
        # progress=1 если нет overdue, иначе 0
        overdue_n = int(
            (
                await session.execute(
                    select(func.count())
                    .select_from(Task)
                    .where(
                        Task.user_id == user_id,
                        Task.is_completed.is_(False),
                        Task.deleted_at.is_(None),
                        Task.due_at.is_not(None),
                        func.date(Task.due_at) < today,
                    )
                )
            ).scalar_one()
        )
        progress = 1 if overdue_n == 0 else 0

    done = progress >= ch.target
    return {
        "key": ch.key,
        "emoji": ch.emoji,
        "title": ch.title,
        "description": ch.description,
        "progress": progress,
        "target": ch.target,
        "done": done,
    }
