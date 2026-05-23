"""Compute achievement state for a user from existing tables.

All checks are pure SQL — no extra storage. Cheap enough to run on each
/profile load (a handful of small queries).
"""

from datetime import UTC, date, datetime, timedelta
from typing import TypedDict
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.labels.models import task_labels
from app.projects.models import Project
from app.school.subjects import detect_subject
from app.tasks.models import Task


class AchievementDef(TypedDict):
    code: str
    emoji: str
    title: str
    description: str


ACHIEVEMENTS: list[AchievementDef] = [
    {
        "code": "first_task",
        "emoji": "🥚",
        "title": "Первая задача",
        "description": "Создал самую первую задачу.",
    },
    {
        "code": "first_done",
        "emoji": "✅",
        "title": "Первое выполненное",
        "description": "Закрыл первую задачу.",
    },
    {
        "code": "ten_done",
        "emoji": "🔟",
        "title": "10 задач",
        "description": "Закрыл 10 задач — почин!",
    },
    {
        "code": "hundred_done",
        "emoji": "🎯",
        "title": "100 задач",
        "description": "Закрыл сотню задач.",
    },
    {
        "code": "five_hundred_done",
        "emoji": "💯",
        "title": "500 задач",
        "description": "Полтыщи закрытых задач.",
    },
    {
        "code": "thousand_done",
        "emoji": "🏆",
        "title": "1000 задач",
        "description": "Тысяча. Уважение.",
    },
    {
        "code": "first_project",
        "emoji": "📁",
        "title": "Первый проект",
        "description": "Создал свой первый проект.",
    },
    {
        "code": "ten_projects",
        "emoji": "🗂️",
        "title": "10 проектов",
        "description": "Накопил 10 проектов.",
    },
    {
        "code": "streak_7",
        "emoji": "🔥",
        "title": "Серия 7 дней",
        "description": "Закрывал хотя бы по задаче 7 дней подряд.",
    },
    {
        "code": "streak_30",
        "emoji": "🌋",
        "title": "Серия 30 дней",
        "description": "Месяц подряд без пропусков.",
    },
    {
        "code": "streak_100",
        "emoji": "🔥🔥",
        "title": "Серия 100 дней",
        "description": "Сто дней подряд. Машина.",
    },
    {
        "code": "early_bird",
        "emoji": "🌅",
        "title": "Ранняя пташка",
        "description": "5 задач закрыто до 9:00 UTC.",
    },
    {
        "code": "night_owl",
        "emoji": "🌙",
        "title": "Сова",
        "description": "5 задач закрыто после 22:00 UTC.",
    },
    {
        "code": "all_priorities",
        "emoji": "✨",
        "title": "Все приоритеты",
        "description": "Использовал все 4 приоритета.",
    },
    {
        "code": "first_recurring",
        "emoji": "🔁",
        "title": "Повтор",
        "description": "Создал повторяющуюся задачу.",
    },
    {
        "code": "first_label",
        "emoji": "🏷️",
        "title": "Первый лейбл",
        "description": "Поставил лейбл хотя бы на одну задачу.",
    },
    {
        "code": "school_homework",
        "emoji": "📚",
        "title": "10 предметов",
        "description": "Завершил 10 школьных задач (с предметом в названии).",
    },
    {
        "code": "first_pin",
        "emoji": "📌",
        "title": "Закрепил",
        "description": "Закрепил задачу наверх.",
    },
]


async def compute_unlocked(session: AsyncSession, user_id: UUID) -> set[str]:
    """Run cheap aggregate queries; return codes of unlocked achievements."""
    unlocked: set[str] = set()

    total_tasks = (
        await session.execute(select(func.count()).select_from(Task).where(Task.user_id == user_id))
    ).scalar_one()
    if total_tasks > 0:
        unlocked.add("first_task")

    done = (
        await session.execute(
            select(func.count())
            .select_from(Task)
            .where(Task.user_id == user_id, Task.is_completed.is_(True))
        )
    ).scalar_one()
    if done >= 1:
        unlocked.add("first_done")
    if done >= 10:
        unlocked.add("ten_done")
    if done >= 100:
        unlocked.add("hundred_done")
    if done >= 500:
        unlocked.add("five_hundred_done")
    if done >= 1000:
        unlocked.add("thousand_done")

    project_count = (
        await session.execute(
            select(func.count()).select_from(Project).where(Project.user_id == user_id)
        )
    ).scalar_one()
    if project_count >= 1:
        unlocked.add("first_project")
    if project_count >= 10:
        unlocked.add("ten_projects")

    streak = await _current_streak(session, user_id)
    if streak >= 7:
        unlocked.add("streak_7")
    if streak >= 30:
        unlocked.add("streak_30")
    if streak >= 100:
        unlocked.add("streak_100")

    early_count = (
        await session.execute(
            select(func.count())
            .select_from(Task)
            .where(
                Task.user_id == user_id,
                Task.is_completed.is_(True),
                Task.completed_at.is_not(None),
                func.extract("hour", Task.completed_at) < 9,
            )
        )
    ).scalar_one()
    if early_count >= 5:
        unlocked.add("early_bird")

    late_count = (
        await session.execute(
            select(func.count())
            .select_from(Task)
            .where(
                Task.user_id == user_id,
                Task.is_completed.is_(True),
                Task.completed_at.is_not(None),
                func.extract("hour", Task.completed_at) >= 22,
            )
        )
    ).scalar_one()
    if late_count >= 5:
        unlocked.add("night_owl")

    distinct_priorities = (
        await session.execute(
            select(func.count(func.distinct(Task.priority))).where(Task.user_id == user_id)
        )
    ).scalar_one()
    if distinct_priorities >= 4:
        unlocked.add("all_priorities")

    has_recurring = (
        await session.execute(
            select(func.count())
            .select_from(Task)
            .where(Task.user_id == user_id, Task.recurrence.is_not(None))
        )
    ).scalar_one()
    if has_recurring >= 1:
        unlocked.add("first_recurring")

    has_label_link = (
        await session.execute(
            select(func.count())
            .select_from(task_labels)
            .join(Task, Task.id == task_labels.c.task_id)
            .where(Task.user_id == user_id)
        )
    ).scalar_one()
    if has_label_link >= 1:
        unlocked.add("first_label")

    school_done = await _school_completed_count(session, user_id)
    if school_done >= 10:
        unlocked.add("school_homework")

    has_pin = (
        await session.execute(
            select(func.count())
            .select_from(Task)
            .where(Task.user_id == user_id, Task.pinned_at.is_not(None))
        )
    ).scalar_one()
    if has_pin >= 1:
        unlocked.add("first_pin")

    return unlocked


async def _current_streak(session: AsyncSession, user_id: UUID) -> int:
    today = datetime.now(UTC).date()
    horizon = today - timedelta(days=400)
    rows = await session.execute(
        select(func.date(Task.completed_at))
        .where(
            Task.user_id == user_id,
            Task.is_completed.is_(True),
            Task.completed_at.is_not(None),
            func.date(Task.completed_at) >= horizon,
        )
        .distinct()
    )
    days_set: set[date] = set()
    for row in rows.all():
        d = row[0]
        if isinstance(d, date):
            days_set.add(d)
        elif d is not None:
            days_set.add(date.fromisoformat(str(d)))
    if not days_set:
        return 0
    if today in days_set:
        cursor = today
    elif (today - timedelta(days=1)) in days_set:
        cursor = today - timedelta(days=1)
    else:
        return 0
    streak = 0
    while cursor in days_set:
        streak += 1
        cursor -= timedelta(days=1)
    return streak


async def _school_completed_count(session: AsyncSession, user_id: UUID) -> int:
    rows = await session.execute(
        select(Task.title).where(
            Task.user_id == user_id,
            Task.is_completed.is_(True),
        )
    )
    return sum(1 for (title,) in rows.all() if detect_subject(title) is not None)
